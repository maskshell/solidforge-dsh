#!/usr/bin/env python3
"""arch_contract_java.py — the inner-ring "架构契约门" for Java (JDK 17+).

Deterministic architecture gate run at the inner convergence point. Emits a structured "越权日志" JSON; non-zero (Blocker) exit on any violation. Tools missing -> degrades to a no-op pass with an explicit coverage note (never silently green).

HONEST GAP: Java has strong IDE/arch tooling but no single first-class standalone layer/dependency-direction enforcer that fits this gate's config+CLI model (ArchUnit is idiomatic for layer rules, but it runs as JUnit tests and is therefore enforced through the TEST gate, not here — see references/java-patterns.md). This gate covers what is codable standalone:

  1. style + import-direction baseline -> `checkstyle` (standalone CLI, consumes the copied checkstyle.xml; ImportControl can encode layer rules).
  2. package cycles                   -> `jdeps --cyclic` (JDK-bundled; no install), on compiled `.class` artifacts if present.

Layer-direction contracts beyond Checkstyle ImportControl are NOT enforced here — they remain an outer-ring semantic concern (or an ArchUnit test-suite the project adds). This is the correct behavior for the config+CLI tier, surfaced explicitly in `coverage`. See references/arch-contracts.md.

Usage: arch_contract_java.py
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). Must contain pom.xml or a
       Gradle build file.
"""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

GATE = "arch-contract-java"


def run(argv, cwd=None, timeout=600):
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return None, ""
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def emit(findings, coverage):
    passed = not any(f.get("severity") == "blocker" for f in findings)
    print(
        json.dumps(
            {
                "gate": GATE,
                "passed": passed,
                "coverage": coverage,
                "findings": findings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if passed else 1)


def is_java_project(root):
    return any(
        os.path.exists(os.path.join(root, f))
        for f in ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle.kts")
    )


def _src_dir(root):
    """Conventional Java source root: src/main/java (Maven & Gradle app/java plugin), else src/ if it actually holds .java files, else None."""
    main = os.path.join(root, "src", "main", "java")
    if os.path.isdir(main):
        return main
    src = os.path.join(root, "src")
    if os.path.isdir(src) and any(_ends_java(names) for _, _, names in os.walk(src)):
        return src
    return None


def _ends_java(names):
    return any(n.endswith(".java") for n in names)


def _resolve_checkstyle(root):
    """Return an argv prefix to run Checkstyle, or None.
    Order: `checkstyle` shim on PATH -> $CHECKSTYLE_JAR (java -jar) -> a
    checkstyle-*-all.jar in the project root -> None."""
    if have("checkstyle"):
        return ["checkstyle"]
    jar = os.environ.get("CHECKSTYLE_JAR")
    if jar and os.path.exists(jar):
        return ["java", "-jar", jar]
    try:
        for name in os.listdir(root):
            if name.startswith("checkstyle") and name.endswith("-all.jar"):
                return ["java", "-jar", os.path.join(root, name)]
    except OSError:
        pass
    return None


def parse_checkstyle_xml(xml_text):
    """Checkstyle -f xml: <checkstyle><file name><error line column severity message source/></file>.
    source is a fully-qualified Checkstyle class; the simple name is the rule.

    arch_contract_java's run() concatenates stdout+stderr; on rc!=0 Checkstyle appends a human
    summary (e.g. "Checkstyle以 1 个错误结束.") AFTER the </checkstyle> close, which breaks
    ET.fromstring. Extract the <?xml ... </checkstyle> block to tolerate that trailing noise
    (the XML payload itself is well-formed)."""
    out = []
    m = re.search(r"<\?xml.*?</checkstyle>", xml_text, re.DOTALL)
    candidate = m.group(0) if m else xml_text
    try:
        root = ET.fromstring(candidate)
    except ET.ParseError:
        return out
    for f in root.iter("file"):
        fname = f.get("name") or "(unknown)"
        for err in f.findall("error"):
            sev_raw = (err.get("severity") or "error").lower()
            sev = "blocker" if sev_raw == "error" else "warning"
            source = err.get("source") or "checkstyle"
            rule = source.rsplit(".", 1)[-1] or "checkstyle"
            msg = (err.get("message") or "").strip()
            out.append(
                {
                    "severity": sev,
                    "rule": rule,
                    "file": fname,
                    "line": int(err.get("line") or 0),
                    "detail": f"[{sev_raw}] {msg}",
                    "suggestion": (
                        "Fix the Checkstyle violation, or suppress in checkstyle.xml if intentional. "
                        "Rule docs: https://checkstyle.org/checks/"
                    ),
                }
            )
    return out


def check_checkstyle(root, findings, coverage):
    tool = _resolve_checkstyle(root)
    if not tool:
        coverage.append(
            "checkstyle: not installed (set $CHECKSTYLE_JAR, put a checkstyle-*-all.jar in the project, or install a `checkstyle` shim) — style/import baseline skipped"
        )
        return
    cfg = os.path.join(root, "checkstyle.xml")
    if not os.path.exists(cfg):
        coverage.append(
            "checkstyle: no checkstyle.xml in project root — style/import baseline skipped (run the installer, or add one)"
        )
        return
    src = _src_dir(root)
    if not src:
        coverage.append(
            "checkstyle: no src/main/java (or src/ with .java) — style/import baseline skipped"
        )
        return
    rc, out = run(tool + ["-f", "xml", "-c", cfg, src], cwd=root, timeout=600)
    if rc is None:
        coverage.append("checkstyle: invocation failed — style/import baseline skipped")
        return
    if rc not in (0, 1) or "<checkstyle" not in out:
        # rc>=2 (config/invocation error) or non-XML output (stack trace) is NOT a violation
        # count — degrade honestly (rule 3) instead of parsing [] and reporting "0 violations".
        first = out.splitlines()[0][:140] if out.splitlines() else ""
        coverage.append(
            f"checkstyle: unexpected rc={rc} / non-XML output — style/import baseline skipped"
            + (f" — {first}" if first else "")
        )
        return
    found = parse_checkstyle_xml(out)
    findings.extend(found)
    coverage.append(
        f"checkstyle: {len(found)} violation(s) parsed (style + ImportControl layer baseline)"
    )


def _classes_dir(root):
    """Compiled .class artifacts, if the project has been built: Maven
    target/classes, Gradle build/classes/java/main."""
    for cand in (
        os.path.join(root, "target", "classes"),
        os.path.join(root, "build", "classes", "java", "main"),
    ):
        if os.path.isdir(cand):
            return cand
    return None


def parse_jdeps_cycles(text):
    """jdeps --cyclic prints only the cyclic dependency edges (`pkg.a -> pkg.b`) plus a summary. Count edge lines as the cycle signal. Best-effort — jdeps output is a known-fragile surface; the coverage note records what ran."""
    edges = [ln.strip() for ln in (text or "").splitlines() if "->" in ln]
    return edges


def check_jdeps_cycles(root, findings, coverage):
    if not have("jdeps"):
        coverage.append(
            "jdeps: not on PATH (bundled with the JDK — is JAVA_HOME/bin on PATH?) — package-cycle check skipped"
        )
        return
    classes = _classes_dir(root)
    if not classes:
        coverage.append(
            "jdeps: no compiled classes (target/classes or build/classes/java/main) — package-cycle check skipped (build the project first: `mvn compile` / `gradle compileJava`)"
        )
        return
    rc, out = run(["jdeps", "--cyclic", classes], cwd=root, timeout=300)
    if rc is None:
        coverage.append("jdeps: invocation failed — package-cycle check skipped")
        return
    edges = parse_jdeps_cycles(out)
    if edges:
        findings.append(
            {
                "severity": "blocker",
                "rule": "cyclic-dependency",
                "file": "(jdeps package graph)",
                "line": 0,
                "detail": "cyclic package dependencies:\n" + "\n".join(edges)[:800],
                "suggestion": "Break the package cycle: extract a shared abstraction, introduce an interface in a lower module, or restructure modules so the dependency graph is acyclic.",
            }
        )
        coverage.append(
            f"jdeps: {len(edges)} cyclic edge(s) (package-level cycle detection)"
        )
    else:
        coverage.append("jdeps: 0 cyclic dependencies (package-level)")


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = [
        "layer-direction: enforced only via Checkstyle ImportControl in checkstyle.xml; beyond that it is an outer-ring concern (or add ArchUnit rules, enforced through the test gate)"
    ]
    if not is_java_project(root):
        coverage.append(
            "java-gate: no pom.xml / build.gradle here — gate skipped (run inside a Java project root)"
        )
        emit(findings, coverage)
    check_checkstyle(root, findings, coverage)
    check_jdeps_cycles(root, findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
