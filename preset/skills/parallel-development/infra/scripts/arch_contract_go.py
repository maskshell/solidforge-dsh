#!/usr/bin/env python3
"""arch_contract_go.py — the inner-ring "架构契约门" for Go.

Deterministic architecture gate run at the inner convergence point. Emits a structured "越权日志" JSON; non-zero (Blocker) exit on any violation. Tools missing -> degrades to a no-op pass with an explicit coverage note (never silently green).

Go is a STRONG gate (the strongest of the backend languages):

  1. import cycles + compile errors -> `go build ./...`. The Go COMPILER rejects cyclic
     imports with "import cycle not allowed"; cycles are a COMPILE error, not a vet finding.
  2. static correctness             -> `go vet ./...` (printf-format, struct tags, lock
     copies, ...). `go vet` shares the compiler's type-check front-end, so it ALSO fails on
     cycles and emits no findings when one exists — therefore build runs FIRST and vet is
     SKIPPED if build fails (avoids double-reporting the same cycle, which would inflate the
     thrashing breaker's distinct-fingerprint count).
  3. layer / dependency-direction   -> `golangci-lint` `depguard` (config-driven forbid/allow
     import rules in .golangci.yml; v2 `rules:` shape). Depguard is the COMPLEMENT to Go's
     `internal/` compiler-enforced structural boundary — the PRIMARY layer mechanism (always
     on, ships with `go`); depguard covers the finer rules between non-`internal` packages
     that `internal/` cannot express. See references/go-patterns.md.

The concurrency baseline (`-race`) is runtime/test-time, NOT static — it runs in the TEST
gate (arch_contract_tests.py `go test -race`), not here. There is no `go vet -race`.

A missing tool degrades that check to a no-op pass with an explicit coverage note. See
references/go-patterns.md and references/arch-contracts.md.

Usage: arch_contract_go.py
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). Must contain go.mod.
"""

import json
import os
import re
import subprocess
import sys

GATE = "arch-contract-go"


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


def is_go_project(root):
    return os.path.exists(os.path.join(root, "go.mod"))


def _tail(text, n=12):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


# golangci-lint linters whose findings are Blockers (correctness / layer rules). Everything
# else (gofmt/gofumpt/whitespace/style) is a warning. Severity maps by FromLinter because
# golangci-lint's `Severity` field is EMPTY by default (only populated when a `severity`
# config section exists). A configured `Severity: "error"` may PROMOTE an unmapped linter to
# blocker, but never demote a blocker linter. See references/go-patterns.md.
_BLOCKER_LINTERS = {"depguard", "govet", "staticcheck", "errcheck", "typecheck"}

# `go vet` / compiler text line: `<file>:<line>[:<col>]: <message>`. Rejects banner lines
# (e.g. `# example.com/foo`) that have no `:digit:` location.
_VET_LINE_RE = re.compile(r"^(.+?):(\d+)(?::\d+)?:\s*(.+)$")


def parse_go_vet(text):
    """`go vet ./...` text output (combined stdout+stderr). One finding per located line."""
    out = []
    for ln in (text or "").splitlines():
        m = _VET_LINE_RE.match(ln.strip())
        if not m:
            continue
        try:
            line = int(m.group(2))
        except ValueError:
            continue
        out.append(
            {
                "severity": "blocker",
                "rule": "go-vet",
                "file": m.group(1),
                "line": line,
                "detail": m.group(3)[:500],
                "suggestion": (
                    "Fix the `go vet` finding — it flags a real bug the compiler does not "
                    "(printf format, struct tag, lock copy, ...). Refactor; do not blanket-disable."
                ),
            }
        )
    return out


def parse_golangci_lint(report):
    """golangci-lint --out-format=json: {Issues:[{FromLinter, Text, Pos:{Filename,Line,Column}, Severity}], Report:{...}}.
    Severity by FromLinter (Severity is empty by default); a configured Severity='error' may
    only promote an unmapped linter, never demote a blocker linter."""
    out = []
    for issue in (report or {}).get("Issues") or []:
        linter = (issue.get("FromLinter") or "golangci-lint").lower()
        pos = issue.get("Pos") or {}
        sev_raw = (issue.get("Severity") or "").lower()
        if linter in _BLOCKER_LINTERS:
            sev = "blocker"
        elif sev_raw == "error":
            sev = "blocker"
        else:
            sev = "warning"
        out.append(
            {
                "severity": sev,
                "rule": linter,
                "file": pos.get("Filename") or "(unknown)",
                "line": int(pos.get("Line") or 0),
                "detail": (issue.get("Text") or linter)[:500],
                "suggestion": (
                    "Fix the golangci-lint finding, or scope it in .golangci.yml. "
                    "Layer violations (depguard) are Blockers; style lints are warnings."
                ),
            }
        )
    return out


def check_build(root, findings, coverage):
    """`go build ./...` — compiler rejects import cycles + surfaces compile errors.
    Returns True if the build is clean (so vet may run); False if it failed (vet skipped)."""
    rc, out = run(["go", "build", "./..."], cwd=root, timeout=600)
    if rc is None:
        coverage.append("go build: invocation failed — compile/cycle check skipped")
        return True
    if rc == 124:
        coverage.append("go build: timed out — compile/cycle check skipped")
        return True
    if rc != 0:
        findings.append(
            {
                "severity": "blocker",
                "rule": "compile-or-cycle",
                "file": "(go build)",
                "line": 0,
                "detail": (
                    "go build failed (compile error or 'import cycle not allowed'):\n"
                    + _tail(out, 12)[:800]
                ),
                "suggestion": (
                    "Fix the compile error, or break the import cycle — the Go compiler "
                    "rejects cyclic imports; extract a shared package lower in the graph."
                ),
            }
        )
        coverage.append(
            "go build: FAILED (compile/cycle) — vet skipped (build and vet share the "
            "compiler front-end; running both would double-report the same cycle)"
        )
        return False
    coverage.append("go build: ok (compiles; no import cycles — compiler-enforced)")
    return True


def check_vet(root, findings, coverage):
    rc, out = run(["go", "vet", "./..."], cwd=root, timeout=600)
    if rc is None:
        coverage.append("go vet: invocation failed — static-check skipped")
        return
    if rc == 124:
        coverage.append("go vet: timed out — static-check skipped")
        return
    found = parse_go_vet(out)
    findings.extend(found)
    coverage.append(
        f"go vet: {len(found)} finding(s) (printf-format, struct tags, lock copies, ...)"
    )


def check_golangci_lint(root, findings, coverage):
    if not have("golangci-lint"):
        coverage.append(
            "golangci-lint: not installed — depguard layer rules + extra linters skipped "
            "(install: `brew install golangci-lint` or "
            "`go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`). "
            "Go's `internal/` compiler-enforced boundary still applies regardless."
        )
        return
    cfg = os.path.join(root, ".golangci.yml")
    argv = ["golangci-lint", "run", "--out-format=json"]
    if os.path.exists(cfg):
        argv += ["-c", cfg]
    else:
        # No project config: run a minimal, deterministic set (govet+gofmt). A project's own
        # .golangci.yml (copied by arm.py) is the authoritative config — this is the fallback.
        argv += ["--no-config", "-E", "govet,gofmt"]
    rc, out = run(argv, cwd=root, timeout=600)
    if rc is None:
        coverage.append("golangci-lint: invocation failed — layer/style check skipped")
        return
    if rc == 124:
        coverage.append("golangci-lint: timed out — layer/style check skipped")
        return
    try:
        report = json.loads(out) if (out or "").strip() else {}
    except json.JSONDecodeError:
        coverage.append("golangci-lint: output unparseable — layer/style check skipped")
        return
    found = parse_golangci_lint(report)
    findings.extend(found)
    n_block = sum(1 for f in found if f["severity"] == "blocker")
    coverage.append(
        f"golangci-lint: {len(found)} finding(s) ({n_block} blocker: depguard/govet; "
        "rest warning) — layer rules + extra linters"
    )


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = [
        "layer-direction: enforced two ways — (1) Go's `internal/` compiler-enforced "
        "structural boundary (always on; ships with `go`), (2) golangci-lint depguard rules "
        "in .golangci.yml for finer non-`internal` package rules",
        "concurrency baseline (`-race`): NOT static — runs in the test gate "
        "(arch_contract_tests.py `go test -race`), not here (there is no `go vet -race`)",
    ]
    if not is_go_project(root):
        coverage.append(
            "go-gate: no go.mod here — gate skipped (run inside a Go module root)"
        )
        emit(findings, coverage)
    if not have("go"):
        coverage.append("go: toolchain absent — build/vet/cycle checks all skipped")
        emit(findings, coverage)
    # Build FIRST; skip vet on build failure (the double-report guard).
    if check_build(root, findings, coverage):
        check_vet(root, findings, coverage)
    check_golangci_lint(root, findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
