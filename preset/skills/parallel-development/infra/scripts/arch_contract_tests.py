#!/usr/bin/env python3
"""arch_contract_tests.py — the inner-ring "测试门" (test gate / TDAI).

Cross-ecosystem. Runs at the inner convergence point. Test failures are first- class Blocker inputs to the convergence loop (the test suite is the Agent's objective function). Emits structured "越权日志" JSON findings; non-zero (Blocker) exit on any failure. Tools missing -> degrades to a no-op pass with an explicit coverage note.

Per-ecosystem structured output (per fact-check; not all tools do JSON):
  Python : pytest + pytest-json-report (--json-report-file -> JSON)
  Web    : vitest run --reporter=json --outputFile=<path>   (JSON)
  Rust   : cargo nextest run --junit-out=<path>  (JUnit XML) if nextest present;
           else `cargo test` text (panic-line parse). NB: `cargo test --message-format=json` does NOT emit test-result events.
  Swift  : `swift test` text (file:line: error: ...)  — no JSON available
  Java   : `mvn test` / `gradle test` -> JUnit XML (Surefire / Gradle test-results; reused parse_junit_xml). Wrapper (mvnw/gradlew) preferred over system tool.

Parsing is split into pure functions (parse_*) for offline unit testing; the check_* wrappers do tool resolution + invocation only.

Usage: arch_contract_tests.py [project_path]
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

GATE = "arch-contract-tests"


def run(argv, cwd=None, timeout=600):
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


# --- pure parsers (canned-JSON unit testable) --------------------------------


def parse_pytest(report):
    """pytest-json-report: {tests:[{nodeid, outcome, call:{longrepr}}]}."""
    out = []
    for t in (report or {}).get("tests") or []:
        if t.get("outcome") not in ("failed", "error"):
            continue
        nodeid = t.get("nodeid", "test")
        file = nodeid.split("::")[0]
        longrepr = str((t.get("call") or {}).get("longrepr") or "").strip()
        tail = longrepr.splitlines()[-1] if longrepr else "failed"
        out.append(
            {
                "severity": "blocker",
                "rule": "test-failure",
                "file": file,
                "line": 0,
                "detail": f"{nodeid}: {tail[:400]}",
                "suggestion": "Fix the failing test or the code under test so the test passes.",
            }
        )
    return out


def parse_vitest(report):
    """vitest --reporter=json: {testResults:[{name, assertionResults:[{fullName,status,location,failureMessages}]}]}."""
    out = []
    for tr in (report or {}).get("testResults") or []:
        for ar in tr.get("assertionResults") or []:
            if ar.get("status") != "failed":
                continue
            loc = ar.get("location") or {}
            msg = (ar.get("failureMessages") or ["failed"])[0]
            out.append(
                {
                    "severity": "blocker",
                    "rule": "test-failure",
                    "file": tr.get("name", "(file)"),
                    "line": int(loc.get("line", 0) or 0),
                    "detail": f"{ar.get('fullName')}: {str(msg).strip().splitlines()[0][:400]}",
                    "suggestion": "Fix the failing test or the code under test.",
                }
            )
    return out


def parse_junit_xml(xml_text):
    """JUnit XML (nextest --junit-out, and any JUnit producer).
    <testsuite><testcase classname name file? line?><failure|error>msg</...></testcase>"""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for tc in root.iter("testcase"):
        fail = next((c for c in list(tc) if c.tag in ("failure", "error")), None)
        if fail is None:
            continue
        cls = tc.get("classname") or ""
        name = tc.get("name") or "test"
        file = tc.get("file") or cls.replace(".", "/") or "(unknown)"
        line = int(tc.get("line") or 0)
        msg = fail.get("message") or (fail.text or "").strip() or "failed"
        out.append(
            {
                "severity": "blocker",
                "rule": "test-failure",
                "file": file,
                "line": line,
                "detail": f"{cls}.{name}: {str(msg).strip().splitlines()[0][:400]}",
                "suggestion": "Fix the failing test or the code under test.",
            }
        )
    return out


_SWIFT_FAIL_RE = re.compile(r"^(.+?):(\d+):\s*error:\s*(.+)$")


def parse_swift_test(text):
    """swift test prints `<file>:<line>: error: <details>` per failing assertion."""
    out = []
    for line in (text or "").splitlines():
        m = _SWIFT_FAIL_RE.match(line.strip())
        if m:
            out.append(
                {
                    "severity": "blocker",
                    "rule": "test-failure",
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "detail": m.group(3).strip()[:400],
                    "suggestion": "Fix the failing assertion or the code under test so the test passes.",
                }
            )
    return out


# Matches both legacy `panicked at 'msg', file:line:col` and Rust 1.73+
# `thread 'name' (id) panicked at file:line:col:` (location, no quoted message).
_CARGO_PANIC_RE = re.compile(r"panicked at (?:'[^']*',\s*)?(\S+):(\d+):\d+")


def parse_cargo_test_text(text):
    """cargo test human output: panic lines carry `panicked at ... file:line:col`."""
    out = []
    for m in _CARGO_PANIC_RE.finditer(text or ""):
        out.append(
            {
                "severity": "blocker",
                "rule": "test-failure",
                "file": m.group(1),
                "line": int(m.group(2)),
                "detail": f"cargo test panic at {m.group(1)}:{m.group(2)}",
                "suggestion": "Fix the failing test or the code under test.",
            }
        )
    return out


def parse_go_test(text):
    """`go test -json` emits NDJSON events: {Action, Package, Test, Output, ...}.
    Action == 'fail' (a package or individual test failed) -> one Blocker finding. Under
    `-race` a data race surfaces as a failed test (Action == 'fail') with the race in Output.
    Consumes the output of check_go (`go test -race -json ./...`)."""
    out = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if ev.get("Action") != "fail":
            continue
        pkg = ev.get("Package") or "(package)"
        test = ev.get("Test") or ""
        out_lines = (ev.get("Output") or "").strip().splitlines()
        tail = out_lines[-1][:300] if out_lines else "failed"
        name = f"{pkg}::{test}" if test else pkg
        out.append(
            {
                "severity": "blocker",
                "rule": "test-failure",
                "file": pkg,
                "line": 0,
                "detail": f"{name}: {tail}",
                "suggestion": (
                    "Fix the failing test or the code under test so it passes (a data race "
                    "under -race is undefined behavior per the Go memory model)."
                ),
            }
        )
    return out


# --- Intent Blueprint AC->test mapping reader (P4 baseline) -------------------

# Header of the mapping section, e.g. `## Acceptance-Criteria -> Test Mapping`.
# Requires an arrow (`->` or `→`) between "Criteria" and "Test" so a loose title
# carrying the four words but no arrow (e.g. "Acceptance Criteria to Test Mapping
# Notes") is NOT mistaken for the section. Case-insensitive.
_AC_TEST_MAP_HEADER_RE = re.compile(
    r"^##\s+Acceptance[\s-]+Criteria\s*(?:->|→)\s*Test\s+Mapping", re.IGNORECASE
)
# `- AC-1 -> test_x` / `- AC-1 → tests/t.py::test_x`. ID is lenient (AC-1, AC1,
# or any token); arrow is ASCII `->` or Unicode `→`; value is the rest of the
# line (a test name / nodeid, NOT a bare file path — see parse_ac_test_map doc).
_AC_TEST_LINE_RE = re.compile(
    r"^\s*[-*]\s+([A-Za-z][\w-]*)\s*(?:->|→)\s*(\S(?:.*\S)?)\s*$"
)


def parse_ac_test_map(text):
    """Read the Intent Blueprint's `Acceptance-Criteria -> Test Mapping` section.

    Returns `{ac_id: [test_name, ...]}` in declaration order. Recognizes both
    `AC-1 -> name` and `AC-1 → name`. Only lines inside the mapping section are
    parsed: the section opens at its H2 header and closes at the next same-or-
    higher-level heading (H1 or H2); deeper headings (H3+) are content inside
    the section, not terminators. So a `->` in NFR prose or under a later H1 is
    ignored. An absent or empty section returns `{}`.

    The value is a test name or nodeid (e.g. `test_user_registration` or
    `tests/test_auth.py::test_user_registration`), NOT a bare file path — the
    test-name set gate (P1) verifies each mapped test exists against the
    per-language collected set, so the value must be a name the collector emits.
    Whether the mapped test actually verifies the AC stays outer-ring (semantic),
    not this gate's claim. Absent mapping -> P1 degrades to count + coverage note
    (rule 3).
    """
    out = {}
    in_section = False
    for line in (text or "").splitlines():
        if line.startswith("#"):
            # Same-or-higher-level heading (H1/H2) opens (if it is the section
            # header) or closes the section; a deeper heading (H3+) is content
            # and does not toggle the section.
            level = len(line) - len(line.lstrip("#"))
            if level <= 2:
                in_section = level == 2 and bool(_AC_TEST_MAP_HEADER_RE.match(line))
            continue
        if not in_section:
            continue
        m = _AC_TEST_LINE_RE.match(line)
        if not m:
            continue
        ac_id, name = m.group(1), m.group(2).strip()
        out.setdefault(ac_id, []).append(name)
    return out


# --- P1: per-language test-name collectors + cross-language set diff ----------


def collect_pytest_names(text):
    """`pytest --collect-only -q` -> list of nodeids (`file::test[::case]`).
    One nodeid per line; summary lines (`N tests collected`, `no tests`) and the
    long `<Module>` form are skipped. The runner must pass `-q` for the flat form.
    """
    names = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("<"):
            continue
        if "collected" in s or "selected" in s or "no tests" in s:
            continue
        if "::" in s:
            names.append(s)
    return names


def collect_rust_names(text):
    """`cargo test -- --list` -> list of full test paths. Each line is
    `<fullname>: test`; the trailing `: test` is stripped."""
    names = []
    suffix = ": test"
    for line in (text or "").splitlines():
        s = line.rstrip()
        if s.endswith(suffix):
            names.append(s[: -len(suffix)].strip())
    return names


_GO_TEST_NAME_RE = re.compile(r"^(Test|Benchmark|Example|Fuzz)\w*$")


def collect_go_names(text):
    """`go test -list .` -> list of Test/Benchmark/Example/Fuzz names. Summary
    lines (`ok`, `FAIL`, `?`, `---`) do not start with those prefixes and are
    skipped."""
    names = []
    for line in (text or "").splitlines():
        s = line.strip()
        if _GO_TEST_NAME_RE.match(s):
            names.append(s)
    return names


def collect_vitest_names(text):
    """`vitest list` (best-effort) -> list of `file > name` strings. Strips a
    leading status glyph and keeps lines containing ` > `. vitest list output is
    version-dependent, so this is best-effort; an unrecognized shape yields [] and
    the runner emits a coverage note (rule 3)."""
    names = []
    for line in (text or "").splitlines():
        s = line.strip().lstrip("✓✗↓*·• ").strip()
        if " > " in s:
            names.append(s)
    return names


def leaf_test_name(name):
    """The leaf test identifier: the segment after the last `::` (pytest/cargo
    nodeid) or ` > ` (vitest), else the name itself. Lets a mapping declared with
    a bare function name (`test_x`) match a collected nodeid (`tests/t.py::test_x`).
    """
    for sep in ("::", " > "):
        if sep in name:
            return name.rsplit(sep, 1)[-1]
    return name


def missing_mapped_tests(ac_test_map, names_full, names_leaf):
    """Cross-language set diff: each mapped test name must appear in the collected
    set. A name is present if it equals a full collected name OR a collected leaf.
    Returns one Blocker finding per missing name (rule `test-name-missing`), with
    the AC id in the detail for traceability. Empty/absent mapping -> [] (the
    caller degrades to a coverage note, rule 3).

    Leaf matching is intentionally coarse: a bare-name mapping (`test_x`) matches
    any same-named leaf across the repo, so it answers "does this test exist?" not
    "is it the intended one?". Use a nodeid/full mapping for unambiguous identity;
    whether the test actually verifies the AC stays outer-ring (semantic)."""
    out = []
    full = set(names_full or [])
    leaf = set(names_leaf or [])
    for ac_id, names in (ac_test_map or {}).items():
        for name in names:
            if name in full or name in leaf:
                continue
            out.append(
                {
                    "severity": "blocker",
                    "rule": "test-name-missing",
                    "file": "(blueprint)",
                    "line": 0,
                    "detail": (
                        f"{ac_id} -> {name}: declared in the AC->test mapping but "
                        "not found in the collected test set (deleted, renamed, or "
                        "never written)."
                    ),
                    "suggestion": (
                        "Restore the test (or correct the mapping) so the declared "
                        "name appears in the per-language collected set."
                    ),
                }
            )
    return out


# --- P3: per-language coverage parsers + threshold finding (warning) ----------

_COVERAGE_TOTAL_RE = re.compile(
    r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)\s*%", re.MULTILINE
)
_GO_COVERAGE_TOTAL_RE = re.compile(r"^total:.*?(\d+(?:\.\d+)?)\s*%", re.MULTILINE)
_GO_COVERAGE_RE = re.compile(r"coverage:\s+(\d+(?:\.\d+)?)%\s+of statements")
# Tarpaulin prints per-file `NN% coverage` lines BEFORE the `Result:` aggregate;
# only the Result line is the overall number.
_RUST_COVERAGE_RESULT_RE = re.compile(
    r"Result:\s+(\d+(?:\.\d+)?)\s*%\s*coverage", re.IGNORECASE
)
# A coverage floor on the measured metric (line/statement coverage, or bare
# "coverage" = line by default). REQUIRES a threshold operator so a bare number
# near "coverage" (e.g. `coverage tool version 7`, `coverage scope is 3`) does not
# masquerade as a floor.
_NFR_COVERAGE_FLOOR_RE = re.compile(
    r"(?:line|lines|statement|statements)?\s*coverage\s*"
    r"(?:>=?|≥|minimum|at least|min(?:imum)?|floor|targets?|targeted|exceeds?)\s*"
    r"(\d{1,3}(?:\.\d+)?)",
    re.IGNORECASE,
)
# Non-line metrics the gate does NOT measure (it measures line/statement coverage).
_NON_LINE_COVERAGE_RE = re.compile(
    r"\b(?:branch|function|method|func)\s+coverage", re.IGNORECASE
)


def parse_coverage_pytest(text):
    """`coverage report` / pytest-cov term output -> the TOTAL line's % (float),
    or None. Matches `TOTAL  <stmts>  <miss>  NN%` (multi-col spacing tolerant)."""
    m = _COVERAGE_TOTAL_RE.search(text or "")
    return float(m.group(1)) if m else None


def parse_coverage_go(text):
    """`go tool cover -func` aggregate (`total: NN%`) preferred; else the
    `go test -cover` per-package line (`coverage: NN% of statements`). Returns
    float or None."""
    m = _GO_COVERAGE_TOTAL_RE.search(text or "")
    if m:
        return float(m.group(1))
    m = _GO_COVERAGE_RE.search(text or "")
    return float(m.group(1)) if m else None


def parse_coverage_rust(text):
    """`cargo tarpaulin` (Stdout) -> the aggregate `Result: NN.NN% coverage`
    value, or None. Real tarpaulin output prints per-file `NN% coverage` lines
    BEFORE the `Result:` aggregate; a bare first-match would report a per-file
    value and FALSE-NEGATIVE (suppress real warnings). Without a Result line the
    aggregate is unknown -> None (the IO wrapper degrades, rule 3)."""
    m = _RUST_COVERAGE_RESULT_RE.search(text or "")
    return float(m.group(1)) if m else None


def parse_coverage_vitest(text):
    """vitest coverage text table -> the `All files` row's first % (overall
    stmts), or None. Best-effort — reporter format is version-dependent; the IO
    wrapper notes when unrecognized (rule 3)."""
    for line in (text or "").splitlines():
        s = line.strip().lstrip("| ")
        if s.lower().startswith("all files"):
            m = re.search(r"(\d+(?:\.\d+)?)", s)
            if m:
                return float(m.group(1))
    return None


def parse_blueprint_coverage_min(text):
    """Read the Intent Blueprint's NFR section for a line-coverage floor. Returns
    the MAX coverage % declared with a threshold operator on a coverage-mentioning
    NFR bullet (e.g. `line coverage >= 80%`, `coverage minimum 75`), or None.

    Scoped to the NFR section. Non-line metrics (branch/function/method coverage)
    are skipped — the gate measures line/statement coverage only, so a `branch
    coverage >= 95%` NFR is NOT treated as a line floor. A bare number near
    "coverage" without a threshold operator (`coverage tool version 7`, `coverage
    scope is 3`) is NOT a floor. MAX across coverage-mentioning NFR bullets;
    branch/func floors are ignored (the gate measures line only)."""
    floors = []
    in_nfr = False
    for line in (text or "").splitlines():
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level <= 2:
                low = line.lower()
                in_nfr = "non-functional" in low and "requirement" in low
            continue
        if not in_nfr or "coverage" not in line.lower():
            continue
        if _NON_LINE_COVERAGE_RE.search(line):
            continue  # branch/function/method coverage — gate measures line only
        for m in _NFR_COVERAGE_FLOOR_RE.finditer(line):
            val = float(m.group(1))
            if 0 <= val <= 100:
                floors.append(val)
    return max(floors) if floors else None


def coverage_finding(lang, percent, threshold, where):
    """Build a `coverage-below-threshold` WARNING finding, or None. None when:
    no measurement, no threshold declared (default = measure-only, rule 3), or
    coverage meets the threshold. Severity is warning (not blocker) — coverage is
    a heuristic proxy ('execution coverage, not assertion quality', maturity.md
    caveat 13); rule 4: heuristic checks never block."""
    if percent is None or threshold is None or percent >= threshold:
        return None
    return {
        "severity": "warning",
        "rule": "coverage-below-threshold",
        "file": where,
        "line": 0,
        "detail": (
            f"{lang}: {percent:.1f}% coverage < {threshold:.1f}% NFR threshold. "
            "Execution coverage, not assertion quality (maturity.md caveat 13)."
        ),
        "suggestion": (
            "Add or restore tests for uncovered lines, or revise the NFR threshold "
            "via the Blueprint Revision Channel."
        ),
    }


# --- IO wrappers -------------------------------------------------------------


def _is_python(root):
    import glob

    return any(
        os.path.exists(os.path.join(root, m))
        for m in ("pyproject.toml", "setup.py", "setup.cfg")
    ) or bool(glob.glob(os.path.join(root, "requirements*.txt")))


def check_pytest(root, findings, coverage):
    if not have("pytest"):
        coverage.append("pytest: not installed — Python test gate skipped")
        return
    fd, jp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        rc, _out, err = run(
            [
                "pytest",
                "--json-report",
                f"--json-report-file={jp}",
                "-q",
                "--no-header",
                "-rA",
            ],
            cwd=root,
            timeout=600,
        )
        if rc is None:
            coverage.append("pytest: invocation failed — skipped")
            return
        try:
            with open(jp, "r", encoding="utf-8") as fh:
                report = json.load(fh)
        except (OSError, json.JSONDecodeError):
            coverage.append(
                "pytest: --json-report produced no report (is pytest-json-report installed?) — skipped"
            )
            return
        found = parse_pytest(report)
        findings.extend(found)
        coverage.append(
            f"pytest: {len(found)} failed test(s)"
            + (
                f" (note: stderr {err.strip()[:80]})"
                if "unrecognized arguments" in err
                else ""
            )
        )
    finally:
        try:
            os.unlink(jp)
        except OSError:
            pass


def _resolve_vitest(root):
    """Resolve vitest: project-local node_modules/.bin/vitest first, else PATH.

    Mirrors _resolve_tsc (arch_contract_web.py). vitest is version-coupled to the
    project (v1/v2/v3 config API differ), so the project's PINNED version must run —
    a bare `vitest` on PATH would version-diverge. Local-first also avoids a false-skip
    when vitest is a devDep but not installed globally (node_modules/.bin is not on PATH).
    """
    local = os.path.join(root, "node_modules", ".bin", "vitest")
    if os.path.exists(local):
        return [local]
    return ["vitest"] if have("vitest") else None


def check_vitest(root, findings, coverage):
    if not os.path.exists(os.path.join(root, "package.json")):
        coverage.append("vitest: no package.json — Web test gate skipped")
        return
    vitest = _resolve_vitest(root)
    if not vitest:
        coverage.append(
            "vitest: not installed (no node_modules/.bin/vitest and `vitest` not on PATH) "
            "— Web test gate skipped (install: `npm i -D vitest`)"
        )
        return
    jp = os.path.join(root, ".vitest-pd-result.json")
    rc, _out, err = run(
        [*vitest, "run", "--reporter=json", f"--outputFile={jp}"],
        cwd=root,
        timeout=600,
    )
    if rc is None:
        coverage.append("vitest: invocation failed — skipped")
        return
    try:
        with open(jp, "r", encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, json.JSONDecodeError):
        coverage.append("vitest: no JSON report produced — skipped")
        return
    finally:
        try:
            os.unlink(jp)
        except OSError:
            pass
    found = parse_vitest(report)
    findings.extend(found)
    coverage.append(f"vitest: {len(found)} failed test(s)")


def check_rust(root, findings, coverage):
    if not (have("cargo") and os.path.exists(os.path.join(root, "Cargo.toml"))):
        coverage.append(
            "cargo: not installed or no Cargo.toml — Rust test gate skipped"
        )
        return
    if have("cargo-nextest"):
        fd, jp = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            rc, _out, _err = run(
                ["cargo", "nextest", "run", "--no-tests=warn", f"--junit-out={jp}"],
                cwd=root,
                timeout=600,
            )
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    xml_text = fh.read()
            except OSError:
                xml_text = ""
            found = parse_junit_xml(xml_text)
            findings.extend(found)
            coverage.append(f"cargo nextest (JUnit XML): {len(found)} failed test(s)")
        finally:
            try:
                os.unlink(jp)
            except OSError:
                pass
        return
    # Fallback: cargo test human output (no JSON test events available).
    rc, out, err = run(["cargo", "test", "--no-fail-fast"], cwd=root, timeout=600)
    if rc is None:
        coverage.append("cargo test: invocation failed — skipped")
        return
    found = parse_cargo_test_text((out or "") + "\n" + (err or ""))
    findings.extend(found)
    if found:
        coverage.append(f"cargo test (text parse): {len(found)} failed test(s)")
    elif rc != 0:
        tail = "\n".join(
            [line for line in (out or "").splitlines() if line.strip()][-6:]
        )
        findings.append(
            {
                "severity": "blocker",
                "rule": "test-failure",
                "file": "Cargo.toml",
                "line": 0,
                "detail": f"cargo test failed (no panic line parsed); tail:\n{tail[:400]}",
                "suggestion": "Inspect the cargo test output; fix the failing test or code. Install cargo-nextest for precise JUnit-XML parsing.",
            }
        )
        coverage.append(
            "cargo test (text parse): 1 failed run (coarse — no panic line)"
        )
    else:
        coverage.append("cargo test (text parse): 0 failures")


def check_swift(root, findings, coverage):
    if not (have("swift") and os.path.exists(os.path.join(root, "Package.swift"))):
        coverage.append(
            "swift: not installed or no Package.swift — Swift test gate skipped"
        )
        return
    rc, out, err = run(["swift", "test"], cwd=root, timeout=600)
    if rc is None:
        coverage.append("swift test: invocation failed — skipped")
        return
    # xctest routes its output differently in TTY vs non-TTY; parse both streams.
    found = parse_swift_test((out or "") + "\n" + (err or ""))
    findings.extend(found)
    coverage.append(f"swift test: {len(found)} failed assertion(s)")


def _java_test_plan(root):
    """Return (kind, argv_or_None, reports_dir). Maven preferred (pom.xml), else Gradle (build.gradle / .kts). The argv prefers the project wrapper (mvnw/gradlew — pins the build-tool version) over a system mvn/gradle. argv is None when neither wrapper nor system tool is available."""
    if os.path.exists(os.path.join(root, "pom.xml")):
        mvnw = os.path.join(root, "mvnw")
        argv = (
            [mvnw, "test"]
            if os.path.exists(mvnw)
            else (["mvn", "test"] if have("mvn") else None)
        )
        return "maven", argv, os.path.join(root, "target", "surefire-reports")
    if any(
        os.path.exists(os.path.join(root, f))
        for f in ("build.gradle", "build.gradle.kts")
    ):
        gradlew = os.path.join(root, "gradlew")
        argv = (
            [gradlew, "test"]
            if os.path.exists(gradlew)
            else (["gradle", "test"] if have("gradle") else None)
        )
        return "gradle", argv, os.path.join(root, "build", "test-results", "test")
    return None, None, None


def check_java(root, findings, coverage):
    import glob

    kind, argv, reports = _java_test_plan(root)
    if kind is None:
        return  # not a Java project — no coverage noise
    if argv is None:
        coverage.append(
            f"{kind}: no mvnw/gradlew wrapper and no system {kind} on PATH — Java test gate skipped"
        )
        return
    # Java builds can be slow (cold dependency resolution); allow more time than the default.
    rc, _out, err = run(argv, cwd=root, timeout=900)
    if rc is None:
        coverage.append(f"{kind} test: invocation failed — Java test gate skipped")
        return
    xmls = sorted(glob.glob(os.path.join(reports, "*.xml")))
    found = []
    for x in xmls:
        try:
            with open(x, "r", encoding="utf-8") as fh:
                found.extend(parse_junit_xml(fh.read()))
        except OSError:
            continue
    findings.extend(found)
    coverage.append(
        f"{kind} (JUnit XML): {len(found)} failed test(s) from {len(xmls)} report file(s)"
    )


def check_go(root, findings, coverage):
    if not (have("go") and os.path.exists(os.path.join(root, "go.mod"))):
        coverage.append("go: not installed or no go.mod — Go test gate skipped")
        return
    # `-race` (ThreadSanitizer-backed) is Go's canonical concurrency baseline and the ONLY
    # first-class Go concurrency check — there is no static equivalent (unlike Python's
    # sync-in-async ast scan or Swift's -strict-concurrency), so it runs here in the TEST
    # gate, not the arch gate. A data race surfaces as Action == 'fail' (undefined behavior
    # per the Go memory model). `go test -json` always emits the NDJSON event stream to
    # stdout, even on failure. The -race overhead is acceptable: this gate runs at the inner
    # convergence point, not per-edit.
    rc, out, _err = run(
        ["go", "test", "-race", "-json", "./..."], cwd=root, timeout=600
    )
    if rc is None:
        coverage.append("go test: invocation failed — Go test gate skipped")
        return
    if rc == 124:
        coverage.append("go test: timed out — Go test gate skipped")
        return
    found = parse_go_test(out or "")
    findings.extend(found)
    coverage.append(f"go test -race (JSON): {len(found)} failed test(s)/race(s)")


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
    """Dirs (relative to root; '' == root) that directly contain any of the marker file `names`. Bounded walk that prunes build/dep/cache dirs. Root is depth 0, so a root-level marker and a nested one (frontend in a subdir, backend in another) are handled by the same loop — a mixed FE+BE repo runs BOTH vitest and mvn/gradle."""
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


# --- P1: test-name collectors (IO wrappers) + AC->test-name set gate driver ---


def _run_collect_pytest(root):
    """`pytest --collect-only -q` -> (names, coverage_note_or_None)."""
    if not have("pytest"):
        return [], "pytest collect: not installed — skipped"
    rc, out, _err = run(["pytest", "--collect-only", "-q"], cwd=root, timeout=300)
    if rc is None:
        return [], "pytest collect: invocation failed — skipped"
    return collect_pytest_names(out or ""), None


def _run_collect_rust(root):
    """`cargo test -- --list` -> (names, note_or_None). Compiles then lists; one
    `: test` line per test across all cargo test binaries."""
    if not (have("cargo") and os.path.exists(os.path.join(root, "Cargo.toml"))):
        return [], None
    rc, out, _err = run(["cargo", "test", "--", "--list"], cwd=root, timeout=600)
    if rc is None:
        return [], "cargo collect: invocation failed — skipped"
    return collect_rust_names(out or ""), None


def _run_collect_go(root):
    """`go test -list . ./...` -> (names, note_or_None). Lists without running.
    `./...` matches check_go's package scope so a mapped test in a subpackage is
    enumerated (without it, only the cwd package is listed -> false Blocker)."""
    if not (have("go") and os.path.exists(os.path.join(root, "go.mod"))):
        return [], None
    rc, out, _err = run(["go", "test", "-list", ".", "./..."], cwd=root, timeout=300)
    if rc is None:
        return [], "go collect: invocation failed — skipped"
    return collect_go_names(out or ""), None


def _run_collect_vitest(root):
    """`vitest list` -> (names, note_or_None). Best-effort (version-dependent)."""
    if not os.path.exists(os.path.join(root, "package.json")):
        return [], None
    vitest = _resolve_vitest(root)
    if not vitest:
        return [], "vitest collect: not installed — skipped"
    rc, out, _err = run([*vitest, "list"], cwd=root, timeout=300)
    if rc is None:
        return [], "vitest collect: invocation failed — skipped"
    names = collect_vitest_names(out or "")
    note = (
        None
        if names
        else "vitest collect: no names parsed (list format unrecognized / version-dependent)"
    )
    return names, note


def collect_all_test_names(root):
    """Run every per-language collector in every dir holding its marker. Returns
    (names_full_set, names_leaf_set, coverage_notes). Polyglot-safe: a mixed
    FE+BE repo runs vitest + pytest + ... and unions the names. Swift and Java
    have no collector yet (rule 3: not implemented -> not faked)."""
    full = set()
    notes = []

    def _sweep(markers, runner):
        for d in find_marker_dirs(root, markers):
            names, note = runner(_at(root, d))
            full.update(names)
            if note:
                notes.append(f"{d or '.'}: {note}")

    _sweep(
        ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
        _run_collect_pytest,
    )
    _sweep(["Cargo.toml"], _run_collect_rust)
    _sweep(["go.mod"], _run_collect_go)
    _sweep(["package.json"], _run_collect_vitest)
    leaf = {leaf_test_name(n) for n in full}
    return full, leaf, notes


# --- P3: coverage IO wrappers + gate driver ----------------------------------


def _run_coverage_pytest(root):
    """`coverage run -m pytest` + `coverage report` -> (percent, note_or_None)."""
    if not (have("coverage") and have("pytest")):
        return None, "coverage: coverage.py/pytest absent — install pytest-cov"
    # try/finally so the .coverage artifact (written by `coverage run` to cwd by
    # default — NOT gitignored in the host repo) is removed even on timeout/parse-miss.
    # Mirrors _run_coverage_go's pattern.
    prof = os.path.join(root, ".coverage")
    try:
        rc, _out, _err = run(
            ["coverage", "run", "-m", "pytest", "-q", "--no-header"],
            cwd=root,
            timeout=600,
        )
        if rc is None:
            return None, "pytest coverage: invocation failed — skipped"
        if rc == 124:
            return None, "pytest coverage: timed out — skipped"
        _rc, out, _e = run(["coverage", "report"], cwd=root, timeout=120)
        pct = parse_coverage_pytest(out or "")
        return pct, (
            None if pct is not None else "pytest coverage: no TOTAL line parsed"
        )
    finally:
        try:
            os.unlink(prof)
        except OSError:
            pass


def _run_coverage_go(root):
    """`go test -coverprofile` + `go tool cover -func` -> (percent, note_or_None)."""
    if not (have("go") and os.path.exists(os.path.join(root, "go.mod"))):
        return None, None
    prof = os.path.join(root, ".coverage-pd.out")
    # try/finally so a timeout/parse-miss still removes the profile artifact
    # (it is not gitignored in the host repo).
    try:
        rc, _out, _err = run(
            ["go", "test", f"-coverprofile={prof}", "./..."], cwd=root, timeout=600
        )
        if rc is None:
            return None, "go coverage: invocation failed — skipped"
        if rc == 124:
            return None, "go coverage: timed out — skipped"
        _rc, out, _e = run(
            ["go", "tool", "cover", f"-func={prof}"], cwd=root, timeout=120
        )
        pct = parse_coverage_go(out or "")
        return pct, (None if pct is not None else "go coverage: no total line parsed")
    finally:
        try:
            os.unlink(prof)
        except OSError:
            pass


def _run_coverage_rust(root):
    """`cargo tarpaulin --skip-clean --out Stdout` -> (percent, note_or_None).
    Heavy (runs the suite)."""
    if not (
        have("cargo-tarpaulin") and os.path.exists(os.path.join(root, "Cargo.toml"))
    ):
        return (
            None,
            "rust coverage: cargo-tarpaulin absent — install: cargo install cargo-tarpaulin",
        )
    rc, out, _err = run(
        ["cargo", "tarpaulin", "--skip-clean", "--out", "Stdout"], cwd=root, timeout=900
    )
    if rc is None:
        return None, "rust coverage: invocation failed — skipped"
    if rc == 124:
        return None, "rust coverage: timed out — skipped"
    pct = parse_coverage_rust(out or "")
    return pct, (None if pct is not None else "rust coverage: no % line parsed")


def _run_coverage_vitest(root):
    """`vitest run --coverage` -> (percent, note_or_None). Needs
    @vitest/coverage-v8; reporter format is version-dependent (best-effort)."""
    if not os.path.exists(os.path.join(root, "package.json")):
        return None, None
    vitest = _resolve_vitest(root)
    if not vitest:
        return None, "vitest coverage: vitest absent — skipped"
    rc, out, _err = run([*vitest, "run", "--coverage"], cwd=root, timeout=600)
    if rc is None:
        return None, "vitest coverage: invocation failed — skipped"
    if rc == 124:
        return None, "vitest coverage: timed out — skipped"
    pct = parse_coverage_vitest(out or "")
    return pct, (
        None
        if pct is not None
        else "vitest coverage: no All-files row parsed (install @vitest/coverage-v8; reporter version-dependent)"
    )


def _run_coverage_gate(root, threshold, findings, coverage):
    """P3 coverage gate. Measures execution coverage per language across marker
    dirs. Emits a `coverage-below-threshold` WARNING ONLY when the blueprint
    declares an NFR floor (threshold is not None). When threshold is None, the
    gate is inactive (NO sweep — avoids running full instrumented test suites for
    informational-only coverage; aligns with the loop-integration-cost cheap-gate
    rule). WARNING, never Blocker — coverage is a heuristic proxy ('execution
    coverage, not assertion quality', caveat 13); rule 4."""
    if threshold is None:
        coverage.append("coverage gate: inactive (no NFR coverage floor declared)")
        return

    def _sweep(markers, runner, lang):
        for d in find_marker_dirs(root, markers):
            pct, note = runner(_at(root, d))
            tag = f"{lang}@{d or '.'}"
            if pct is not None:
                finding = coverage_finding(lang, pct, threshold, _at(root, d))
                if finding:
                    findings.append(finding)
                coverage.append(
                    f"{tag}: {pct:.1f}% coverage"
                    + (" (below NFR threshold — warning)" if finding else "")
                )
            elif note:
                coverage.append(f"{tag}: {note}")

    _sweep(
        ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
        _run_coverage_pytest,
        "pytest",
    )
    _sweep(["Cargo.toml"], _run_coverage_rust, "rust")
    _sweep(["go.mod"], _run_coverage_go, "go")
    _sweep(["package.json"], _run_coverage_vitest, "vitest")


def _loop_state_blueprint_ref():
    """Read the frozen Intent Blueprint path from the project's loop-state.json.
    Returns None when absent/unreadable (free path / no frozen blueprint) -> P1
    degrades to a no-op (rule 3)."""
    path = os.path.join(
        os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd(),
        ".solidforge",
        "parallel-dev",
        "loop-state.json",
    )
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("blueprint_ref")
    except (OSError, json.JSONDecodeError):
        return None


def _read_blueprint_text():
    """Return (text_or_None, ref_or_None) for the frozen Intent Blueprint read via
    the project's loop-state.json. (None, None) when no frozen blueprint (free
    path) — callers degrade (rule 3). Both AC->test mapping (P1) and the NFR
    coverage floor (P3) are parsed from this single read."""
    ref = _loop_state_blueprint_ref()
    if not ref:
        return None, None
    try:
        with open(ref, "r", encoding="utf-8") as fh:
            return fh.read(), ref
    except OSError:
        return None, ref


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = []
    attempted = False
    # Run each ecosystem's test runner in EVERY dir holding its marker — root AND nested. This is what makes a mixed frontend+backend repo run both vitest and mvn/gradle test.
    for d in find_marker_dirs(
        root, ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
    ):
        attempted = True
        check_pytest(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["package.json"]):
        attempted = True
        check_vitest(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["Cargo.toml"]):
        attempted = True
        check_rust(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["Package.swift"]):
        attempted = True
        check_swift(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["pom.xml", "build.gradle", "build.gradle.kts"]):
        attempted = True
        check_java(_at(root, d), findings, coverage)
    for d in find_marker_dirs(root, ["go.mod"]):
        attempted = True
        check_go(_at(root, d), findings, coverage)
    if not attempted:
        coverage.append("test-gate: no recognized test runner / project here")
    # Read the frozen Intent Blueprint once; both gates below parse it.
    bp_text, bp_ref = _read_blueprint_text()
    # P1: AC->test-name set gate. When the mapping is present, collect per-language
    # names and Block on any declared name missing from the collected set (blocks
    # naked "delete the failing test"). When absent, a documented no-op (rule 3) —
    # it does NOT Block on count alone (count-comparison was rejected: it misses
    # name replacement).
    ac_map = parse_ac_test_map(bp_text or "")
    if ac_map:
        names_full, names_leaf, cnotes = collect_all_test_names(root)
        coverage.extend(cnotes)
        if not names_full:
            # All collectors degraded/absent — set-diff would flag EVERY mapped
            # name as missing (false Blocker). Degrade instead (rule 4: no Blocker
            # on empty evidence). Phase-0-found (both sources agreed).
            declared = sum(len(v) for v in ac_map.values())
            coverage.append(
                f"AC->test-name gate: degraded — no test names collected "
                f"(collector absent/failed for all {declared} declared name(s)); "
                "set-diff skipped (rule 4)"
            )
        else:
            missing = missing_mapped_tests(ac_map, names_full, names_leaf)
            findings.extend(missing)
            declared = sum(len(v) for v in ac_map.values())
            coverage.append(
                f"AC->test-name gate: {len(missing)} missing declared name(s) of "
                f"{declared} declared; {len(names_full)} collected"
            )
    elif bp_ref:
        coverage.append(
            f"AC->test-name gate: blueprint {bp_ref} has no AC->test mapping "
            "section — gate inactive (rule 3; declare one to enable the set-diff)"
        )
    # P3: per-language coverage gate (warning-level). Measures execution coverage
    # in every marker dir; emits a coverage-below-threshold WARNING per language
    # only when the blueprint declares an NFR floor. Default (no floor): measure-
    # only + coverage note (rule 3). WARNING, never Blocker — coverage is a
    # heuristic proxy ('execution coverage, not assertion quality', caveat 13);
    # rule 4: heuristic checks never block.
    cov_threshold = parse_blueprint_coverage_min(bp_text or "")
    _run_coverage_gate(root, cov_threshold, findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
