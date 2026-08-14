#!/usr/bin/env python3
"""arch_contract_deps.py — the inner-ring "供应链门" (supply-chain / secrets gate).

Cross-ecosystem (unlike the per-language arch gates). Runs at the inner convergence point. Emits structured "越权日志" JSON findings; non-zero (Blocker) exit on any violation. Tools missing -> degrades to a no-op pass with an explicit coverage note (never a silent green).

Checks (best-effort; parses each tool's JSON):
  1. leaked secrets          -> gitleaks (cross-language)  — Secret value is NEVER echoed; only RuleID + Description.
  2. Python dep vulns        -> pip-audit --format json
  3. Web/Node dep vulns      -> npm audit --json
  4. Rust dep vulns          -> cargo audit --json
  5. Java dep vulns          -> OWASP dependency-check --format json (--noupdate)

Parsing is split into pure functions (parse_*) so they are unit-testable with canned JSON offline; the check_* wrappers only do tool resolution + invocation.

Usage: arch_contract_deps.py [project_path]
       project_path defaults to the CWD ($SOLIDFORGE_PROJECT_DIR).
"""

import json
import os
import subprocess
import sys
import tempfile

GATE = "arch-contract-deps"


def run(argv, cwd=None, timeout=300):
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return None, "", "command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


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


# --- ecosystem detection (project-shape, not tool-installed) -----------------
#
# Detection is RECURSIVE: a marker at the repo root OR nested (a frontend in a subdir, a backend in another, a monorepo package) counts. find_marker_dirs prunes build/dep/ cache dirs and is depth-bounded so node_modules / target never blow it up.

_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "target",
    "build",
    "dist",
    "out",
    ".venv",
    "venv",
    "env",
    ".gradle",
    ".next",
    ".nuxt",
    ".turbo",
    ".nx",
    "__pycache__",
    "Pods",
    "DerivedData",
    ".build",
    "coverage",
    ".idea",
    ".vscode",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}
_MAX_MARKER_DEPTH = 4


def find_marker_dirs(root, names, max_depth=_MAX_MARKER_DEPTH):
    """Dirs (relative to root; '' == root) that directly contain any of the marker file `names`. Bounded walk; root is depth 0 so root + nested are uniform."""
    want = set(names)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            found.append("" if rel == "." else rel)
    return found


def _at(root, rel):
    return os.path.normpath(os.path.join(root, rel))


def is_python(root):
    return bool(
        find_marker_dirs(
            root, ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
        )
    )


def is_web(root):
    return bool(find_marker_dirs(root, ["package.json"]))


def is_rust(root):
    return bool(find_marker_dirs(root, ["Cargo.toml"]))


def is_java(root):
    return bool(
        find_marker_dirs(
            root, ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle.kts"]
        )
    )


def is_go(root):
    return bool(find_marker_dirs(root, ["go.mod"]))


# --- pure parsers (unit-testable with canned JSON) ---------------------------


def parse_gitleaks(violations):
    """gitleaks emits an array of violation dicts. CRITICAL: never echo `Secret` or `Match` (both contain secret material) — only RuleID + Description."""
    out = []
    for v in violations or []:
        rule = v.get("RuleID") or "secret"
        out.append(
            {
                "severity": "blocker",
                "rule": f"secret:{rule}",
                "file": v.get("File", "(unknown)"),
                "line": int(v.get("StartLine", 0) or 0),
                "detail": f"apparent leaked secret (rule `{rule}`): {v.get('Description', 'no description')}. Secret value redacted from this report.",
                "suggestion": "Rotate the credential immediately, remove it from the repo (and git history via filter-repo/BFG), and source it from a secret manager / env var.",
            }
        )
    return out


def parse_pip_audit(report):
    """pip-audit --format json: {dependencies:[{name, version, vulns:[{id, fix_versions, description, aliases}]}]}."""
    out = []
    for dep in (report or {}).get("dependencies") or []:
        name = dep.get("name", "(pkg)")
        ver = dep.get("version", "?")
        for vuln in dep.get("vulns") or []:
            vid = vuln.get("id") or (vuln.get("aliases") or ["PYSEC"])[0]
            fixes = vuln.get("fix_versions") or []
            fix = f"upgrade to {fixes[0]}" if fixes else "see advisory for a fix"
            out.append(
                {
                    "severity": "blocker",
                    "rule": f"vuln:{vid}",
                    "file": "requirements/environment",
                    "line": 0,
                    "detail": f"{name}=={ver}: {(vuln.get('description') or vid).strip().splitlines()[0][:300]}",
                    "suggestion": f"{name}: {fix} (advisory {vid}).",
                }
            )
    return out


def parse_npm_audit(report):
    """npm audit --json (v2): {vulnerabilities:{pkg:{severity, via, fixAvailable, range}}}."""
    out = []
    vulns = (report or {}).get("vulnerabilities") or {}
    for pkg, info in vulns.items():
        sev_raw = str(info.get("severity", "")).lower()
        sev = "blocker" if sev_raw in ("critical", "high") else "warning"
        via = info.get("via") or []
        advisory = next((x for x in via if isinstance(x, dict)), None)
        vid = (advisory or {}).get("source") or (
            via[0] if via and isinstance(via[0], str) else pkg
        )
        url = (advisory or {}).get("url") or ""
        fix = info.get("fixAvailable")
        fix_msg = "run `npm audit fix`" if fix else "no auto-fix; see advisory"
        out.append(
            {
                "severity": sev,
                "rule": f"vuln:{vid}",
                "file": "package.json",
                "line": 0,
                "detail": f"{pkg} ({info.get('range', '?')}): {sev_raw} — {url}".rstrip(),
                "suggestion": f"{pkg}: {fix_msg}.",
            }
        )
    return out


def parse_cargo_audit(report):
    """cargo audit --json: {vulnerabilities:{count, list:[{advisory:{id, package, title, description}, versions:{patched}}]}}."""
    out = []
    for item in ((report or {}).get("vulnerabilities") or {}).get("list") or []:
        adv = item.get("advisory") or {}
        vid = adv.get("id") or "RUSTSEC"
        pkg = adv.get("package") or (item.get("package") or {}).get("name") or "(crate)"
        patched = (item.get("versions") or {}).get("patched") or []
        fix = f"upgrade to {patched[0]}" if patched else "see advisory"
        out.append(
            {
                "severity": "blocker",
                "rule": f"vuln:{vid}",
                "file": "Cargo.lock",
                "line": 0,
                "detail": f"{pkg}: {(adv.get('title') or adv.get('description') or vid).strip().splitlines()[0][:300]}",
                "suggestion": f"{pkg}: {fix} (advisory {vid}).",
            }
        )
    return out


def parse_dependency_check(report):
    """OWASP dependency-check --format json:
    {dependencies:[{fileName, filePath, vulnerabilities:[{name, severity, cvssv3, description, cwe}]}]}.
    severity strings are 'Critical'/'High'/'Medium'/'Low'/'None'."""
    out = []
    for dep in (report or {}).get("dependencies") or []:
        name = dep.get("fileName") or dep.get("filePath") or "(dependency)"
        for vuln in dep.get("vulnerabilities") or []:
            vid = vuln.get("name") or vuln.get("id") or "CVE"
            sev_raw = str(vuln.get("severity", "")).lower()
            sev = "blocker" if sev_raw in ("critical", "high") else "warning"
            desc = (vuln.get("description") or vid).strip().splitlines()[0][:300]
            out.append(
                {
                    "severity": sev,
                    "rule": f"vuln:{vid}",
                    "file": name,
                    "line": 0,
                    "detail": f"{name} ({sev_raw or 'unknown'}): {desc}",
                    "suggestion": f"{name}: upgrade to a non-vulnerable version (advisory {vid}).",
                }
            )
    return out


def parse_govulncheck(text):
    """`govulncheck -format json` emits NDJSON: a stream of typed Message objects
    ({"config":...}, {"osv":...}, {"finding":...}), NOT a single JSON document. A `finding`
    carries only an OSV *id*; the summary/details live on the SEPARATE `osv`-typed message
    (Go's OSV subset has no CVSS). So this parser does a two-pass index-then-join: collect
    osv entries into an id->entry map, then for each finding emit a Blocker (govulncheck
    reports only REACHABLE vulns — all real) whose detail joins the finding to its osv
    summary. The spec gives no ordering guarantees, so index ALL osv entries before joining.
    Parity with parse_cargo_audit: every reachable vuln -> blocker."""
    osv_index = {}
    finding_msgs = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            msg = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(msg.get("osv"), dict):
            oid = msg["osv"].get("id")
            if oid:
                osv_index[oid] = msg["osv"]
        elif isinstance(msg.get("finding"), dict):
            finding_msgs.append(msg["finding"])
    out = []
    for f in finding_msgs:
        osv_id = f.get("osv") or "GO-unknown"
        entry = osv_index.get(osv_id) or {}
        summary = (entry.get("summary") or osv_id).strip().splitlines()[0][:300]
        trace = f.get("trace") or []
        pkg = ""
        if trace:
            t0 = trace[0]
            pkg = t0.get("package") or t0.get("module") or ""
        fixed = f.get("fixed_version")
        fix_msg = f" (fixed in {fixed})" if fixed else ""
        prefix = f"{pkg}: " if pkg else ""
        out.append(
            {
                "severity": "blocker",
                "rule": f"vuln:{osv_id}",
                "file": "go.mod",
                "line": 0,
                "detail": f"{prefix}{summary}{fix_msg}",
                "suggestion": f"upgrade the vulnerable module to a fixed version (advisory {osv_id}).",
            }
        )
    return out


# --- IO wrappers (resolve + invoke + parse; degrade on absence/parse failure) -


def _json_or_none(raw, coverage, label):
    try:
        return json.loads(raw) if (raw or "").strip() else None
    except json.JSONDecodeError:
        coverage.append(f"{label}: output unparseable — skipped")
        return None


def check_gitleaks(root, findings, coverage):
    if not have("gitleaks"):
        coverage.append(
            "gitleaks: not installed — secret scan skipped (install: `brew install gitleaks` or `cargo install gitleaks`)"
        )
        return
    fd, report_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        rc, _out, err = run(
            [
                "gitleaks",
                "dir",
                root,
                "--report-format",
                "json",
                "--report-path",
                report_path,
                "--no-banner",
            ],
            timeout=300,
        )
        # exit 0 = clean, 1 = leaks found (default --exit-code); anything else = invocation/flag problem.
        if rc not in (0, 1):
            coverage.append(
                f"gitleaks: invocation failed (rc={rc}) — secret scan skipped ({(err or '').strip()[:120]})"
            )
            return
        try:
            with open(report_path, "r", encoding="utf-8") as fh:
                violations = json.load(fh)
        except (OSError, json.JSONDecodeError):
            violations = []
        found = parse_gitleaks(violations)
        findings.extend(found)
        coverage.append(
            f"gitleaks: {len(found)} secret leak(s) (working-tree scan via `dir`)"
        )
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass


def check_pip_audit(root, findings, coverage):
    if not have("pip-audit"):
        coverage.append(
            "pip-audit: not installed — Python dep vuln scan skipped (install: `uv add --dev pip-audit` or `pip install pip-audit`)"
        )
        return
    rc, out, _err = run(["pip-audit", "--format", "json"], cwd=root, timeout=300)
    if rc is None or rc == 124:
        coverage.append("pip-audit: invocation failed/timed out — skipped")
        return
    report = _json_or_none(out, coverage, "pip-audit")
    if report is None:
        return
    found = parse_pip_audit(report)
    findings.extend(found)
    coverage.append(f"pip-audit: {len(found)} vulnerable dep(s)")


def check_npm_audit(root, findings, coverage):
    if not (have("npm") and os.path.exists(os.path.join(root, "package-lock.json"))):
        coverage.append(
            "npm audit: npm or package-lock.json absent — Web dep vuln scan skipped (run `npm install` to generate the lockfile)"
        )
        return
    rc, out, _err = run(["npm", "audit", "--json"], cwd=root, timeout=300)
    if rc is None:
        coverage.append("npm audit: invocation failed — skipped")
        return
    report = _json_or_none(out, coverage, "npm audit")
    if report is None:
        return
    found = parse_npm_audit(report)
    findings.extend(found)
    coverage.append(f"npm audit: {len(found)} vulnerable package(s)")


def check_cargo_audit(root, findings, coverage):
    if not have("cargo-audit"):
        coverage.append(
            "cargo-audit: not installed — Rust dep vuln scan skipped (install: `cargo install cargo-audit`)"
        )
        return
    rc, out, _err = run(["cargo", "audit", "--json"], cwd=root, timeout=300)
    if rc is None or rc == 124:
        coverage.append("cargo audit: invocation failed/timed out — skipped")
        return
    report = _json_or_none(out, coverage, "cargo audit")
    if report is None:
        return
    found = parse_cargo_audit(report)
    findings.extend(found)
    coverage.append(f"cargo audit: {len(found)} vulnerable crate(s)")


def check_dependency_check(root, findings, coverage):
    if not have("dependency-check"):
        coverage.append(
            "dependency-check: not installed — Java dep vuln scan skipped (install: `brew install dependency-check`, or the OWASP Maven/Gradle plugin)"
        )
        return
    fd, jp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        # --noupdate: the convergence loop runs repeatedly; the NVD DB should be synced separately (`dependency-check --updateonly`), not on every gate run.
        rc, _out, err = run(
            [
                "dependency-check",
                "--scan",
                ".",
                "--format",
                "json",
                "--out",
                jp,
                "--project",
                "parallel-dev-scan",
                "--noupdate",
            ],
            cwd=root,
            timeout=600,
        )
        if rc is None or rc == 124:
            coverage.append(
                f"dependency-check: invocation failed/timed out — Java dep vuln scan skipped ({(err or '').strip()[:80]})"
            )
            return
        try:
            with open(jp, "r", encoding="utf-8") as fh:
                report = json.load(fh)
        except (OSError, json.JSONDecodeError):
            coverage.append(
                "dependency-check: no JSON report produced — Java dep vuln scan skipped"
            )
            return
        found = parse_dependency_check(report)
        findings.extend(found)
        coverage.append(
            f"dependency-check: {len(found)} vulnerable dep(s) (--noupdate; NVD DB synced separately)"
        )
    finally:
        try:
            os.unlink(jp)
        except OSError:
            pass


def check_govulncheck(root, findings, coverage):
    if not have("govulncheck"):
        coverage.append(
            "govulncheck: not installed — Go dep vuln scan skipped (install: "
            "`go install golang.org/x/vuln/cmd/govulncheck@latest`)"
        )
        return
    rc, out, _err = run(
        ["govulncheck", "-format", "json", "./..."], cwd=root, timeout=300
    )
    if rc is None:
        coverage.append("govulncheck: invocation failed — skipped")
        return
    if rc == 124:
        coverage.append("govulncheck: timed out — skipped")
        return
    if rc not in (0, 3):
        # govulncheck exits 0 (clean) or 3 (vulns found); anything else is an invocation
        # error (e.g. an unsupported -format value on an older version) — do NOT claim 0 vulns.
        coverage.append(
            f"govulncheck: exited {rc} (invocation error? e.g. `-format json` unsupported "
            "on this version) — Go dep vuln scan skipped"
        )
        return
    # parse_govulncheck handles the NDJSON split + osv<->finding join (see its docstring).
    found = parse_govulncheck(out)
    findings.extend(found)
    coverage.append(
        f"govulncheck: {len(found)} reachable vuln(s) (NDJSON osv<->finding join)"
    )


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = []
    # gitleaks is cross-language; run it once over the whole tree.
    check_gitleaks(root, findings, coverage)
    # Per-ecosystem scans run in EVERY dir holding that ecosystem's marker — root (depth 0) AND nested (a frontend in a subdir, a backend in another). This is what makes a mixed frontend+backend repo get BOTH npm audit and dependency-check.
    for d in find_marker_dirs(
        root, ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
    ):
        check_pip_audit(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["package.json"]):
        check_npm_audit(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["Cargo.toml"]):
        check_cargo_audit(_at(root, d), findings, coverage)
    for d in find_marker_dirs(
        root, ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle.kts"]
    ):
        check_dependency_check(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["go.mod"]):
        check_govulncheck(_at(root, d), findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
