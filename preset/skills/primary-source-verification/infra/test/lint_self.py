#!/usr/bin/env python3
"""lint_self.py -- dogfood lint gate: the skill lints its OWN infra with ruff.

The Fast Gate's check_python (ruff check + ruff format --check) applied to this
skill's own source. A skill that dogfoods a deterministic inner ring must pass
its own inner ring (workspace rule 1). Mirrors cross-source-review's lint_self.py
(which mirrors parallel-development's -- rule 7: copy the helper, do NOT import
a shared lib; each gate stays independently deployable).

Self-contained (rule 7): duplicates have()/emit() rather than importing a shared
lib. Pure stdlib.

Config discovery: ruff is invoked WITHOUT --config. Ruff walks UP from each
target file and finds the CLOSEST config -- the per-skill ruff.toml (selects
E4/E7/E9/F, mirroring csr/pd). Same invocation shape as the Fast Gate.

Line-length discipline: all lines kept <=88 chars so the file passes format
--check under BOTH the per-skill ruff.toml (88) and the repo-root pyproject
(100).

Graceful-skip (rule 1 + rule 3 -- never fake green): if ruff is absent, emit
passed:true with a coverage note. ruff is a dev tool, not a runtime dependency.

Usage:
    python3 infra/test/lint_self.py
"""

import glob
import json
import os
import subprocess
import sys

GATE = "lint-self"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/primary-source-verification
TARGETS = [
    os.path.join(ROOT, "infra", "scripts"),
    os.path.join(ROOT, "infra", "test"),
]


def have(cmd):
    """True iff cmd is on $PATH (sh-based portability). Duplicated (rule 7)."""
    probe = subprocess.run(["sh", "-c", f"command -v {cmd}"], capture_output=True)
    return probe.returncode == 0


def _collect_py_files():
    files = []
    for tgt in TARGETS:
        if not os.path.isdir(tgt):
            continue
        found = glob.glob(os.path.join(tgt, "**", "*.py"), recursive=True)
        files.extend(sorted(found))
    return files


def _fmt_failed(label, rc, out):
    return f"{label} failed (rc={rc}):\n{out}".strip()


def run():
    coverage = [
        "lint-self (dogfood; rule 1): ruff check + ruff format --check on "
        "infra/scripts + infra/test; config discovery -> per-skill ruff.toml "
        "(mirrors csr/pd lint_self + the actual Fast Gate invocation)"
    ]
    findings = []

    if not have("ruff"):
        coverage.append(
            "skipped: ruff not installed. ruff is a dev tool, not an infra "
            "runtime dependency (rule 1 skip path)."
        )
        return findings, coverage

    py_files = _collect_py_files()
    n_files = len(py_files)
    coverage.append(f"targets: {n_files} *.py file(s) under infra/scripts + infra/test")
    if not py_files:
        coverage.append("skipped: no *.py files to lint")
        return findings, coverage

    check = subprocess.run(
        ["ruff", "check", *py_files], cwd=ROOT, capture_output=True, text=True
    )
    if check.returncode not in (0, None):
        detail = _fmt_failed(
            "ruff check", check.returncode, check.stdout + check.stderr
        )
        findings.append(
            {
                "severity": "blocker",
                "rule": "ruff-check",
                "file": "infra/{scripts,test}",
                "line": 0,
                "detail": detail,
                "suggestion": (
                    "run `ruff check infra/scripts infra/test --fix`; do NOT "
                    "widen the per-skill ruff.toml without re-deriving the "
                    "rule-7 rationale"
                ),
            }
        )
        coverage.append(f"ruff check: FAIL ({check.returncode})")
    else:
        coverage.append("ruff check: PASS (clean)")

    fmt = subprocess.run(
        ["ruff", "format", "--check", *py_files],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if fmt.returncode not in (0, None):
        detail = _fmt_failed(
            "ruff format --check", fmt.returncode, fmt.stdout + fmt.stderr
        )
        findings.append(
            {
                "severity": "blocker",
                "rule": "ruff-format",
                "file": "infra/{scripts,test}",
                "line": 0,
                "detail": detail,
                "suggestion": "run `ruff format infra/scripts infra/test` and re-run",
            }
        )
        coverage.append(f"ruff format --check: FAIL ({fmt.returncode})")
    else:
        coverage.append("ruff format --check: PASS (clean)")

    return findings, coverage


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


def main():
    findings, coverage = run()
    emit(findings, coverage)


if __name__ == "__main__":
    main()
