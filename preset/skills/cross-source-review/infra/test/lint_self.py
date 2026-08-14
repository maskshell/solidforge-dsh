#!/usr/bin/env python3
"""lint_self.py — dogfood lint gate: the skill lints its OWN infra with ruff.

The Fast Gate's check_python (ruff check + ruff format --check, see
parallel-development/infra/hooks/fast_gate.py) applied to this skill's own source.
A skill that dogfoods a deterministic inner ring must pass its own inner ring
(workspace rule 1). Mirrors parallel-development's lint_self.py (rule 7 — copy the
helper, do NOT import a shared lib; each gate stays independently deployable).

Self-contained (rule 7): duplicates the have()/emit() helpers rather than importing
a shared lib. Pure stdlib.

Config discovery: ruff is invoked WITHOUT --config. Ruff walks UP from each target
file and finds the CLOSEST config — the per-skill ruff.toml (selects E4/E7/E9/F,
mirroring pd's per-skill ruff.toml). This is the SAME invocation shape the Fast
Gate uses (parallel-development/infra/hooks/fast_gate.py:42-52 — `ruff check <file>`,
no --config) and the SAME shape pd's lint_self uses (cwd=ROOT, no --config). The
CSR-I3 different-family substrate (hetero_doc_review.py) is a copy-pattern of pd's
hetero_review.py (rule 7); enforcing the broader repo-root rule set on it would
force it to DIVERGE from its pd source. The per-skill ruff.toml exists precisely to
keep copy-pattern scripts linting under the SAME narrower standard as their pd source.

Line-length discipline: all lines kept <=88 chars so the file passes format --check
under BOTH the per-skill ruff.toml (default line-length 88) AND the repo-root
pyproject.toml (line-length 100). The two configs conflict on lines in the 88-100
range (per-skill wraps, repo-root joins); staying <=88 makes both agree.

Graceful-skip (rule 1 + rule 3 — never fake green): if ruff is absent, emit
passed:true with a coverage note. ruff is a dev tool, not an infra runtime
dependency — its absence is declared honestly, not masked.

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
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
TARGETS = [
    os.path.join(ROOT, "infra", "scripts"),
    os.path.join(ROOT, "infra", "test"),
]


def have(cmd):
    """True iff `cmd` is on $PATH (sh-based portability). Duplicated (rule 7)."""
    probe = subprocess.run(["sh", "-c", f"command -v {cmd}"], capture_output=True)
    return probe.returncode == 0


def _collect_py_files():
    """Gather every *.py under TARGETS (recursive). Empty list if none."""
    files = []
    for tgt in TARGETS:
        if not os.path.isdir(tgt):
            continue
        found = glob.glob(os.path.join(tgt, "**", "*.py"), recursive=True)
        files.extend(sorted(found))
    return files


def _fmt_failed(label, rc, out):
    """Build a violation-log detail string for a failed ruff invocation."""
    return f"{label} failed (rc={rc}):\n{out}".strip()


def run():
    """Run ruff check + ruff format --check on the skill's own infra.

    Returns (findings, coverage). findings is a list of violation-log-shaped
    dicts (severity/rule/file/line/detail/suggestion); a blocker severity marks
    a real lint violation. coverage carries the human-readable trail.
    """
    coverage = [
        "lint-self (dogfood; rule 1): ruff check + ruff format --check on "
        "infra/scripts + infra/test; config discovery -> per-skill ruff.toml "
        "(mirrors pd's lint_self + the actual Fast Gate invocation)"
    ]
    findings = []

    if not have("ruff"):
        coverage.append(
            "skipped: ruff not installed (`brew install ruff` or `pip install "
            "ruff`). ruff is a dev tool, not an infra runtime dependency "
            "(rule 1 skip path)."
        )
        return findings, coverage

    py_files = _collect_py_files()
    n_files = len(py_files)
    coverage.append(f"targets: {n_files} *.py file(s) under infra/scripts + infra/test")
    if not py_files:
        coverage.append("skipped: no *.py files to lint")
        return findings, coverage

    # Mirrors fast_gate.check_python: ruff check + ruff format --check. No
    # --config: config discovery finds the per-skill ruff.toml (the same
    # resolution the Fast Gate relies on when it fires on a CSR file edit).
    check = subprocess.run(
        ["ruff", "check", *py_files],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode not in (0, None):
        combined = check.stdout + check.stderr
        detail = _fmt_failed("ruff check", check.returncode, combined)
        findings.append(
            {
                "severity": "blocker",
                "rule": "ruff-check",
                "file": "infra/{scripts,test}",
                "line": 0,
                "detail": detail,
                "suggestion": (
                    "run `ruff check infra/scripts infra/test --fix`; do NOT "
                    "widen the per-skill ruff.toml rule set without "
                    "re-deriving the rule-7 rationale (the CSR-I3 substrate "
                    "mirrors pd's hetero_review.py)"
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
        combined = fmt.stdout + fmt.stderr
        detail = _fmt_failed("ruff format --check", fmt.returncode, combined)
        findings.append(
            {
                "severity": "blocker",
                "rule": "ruff-format",
                "file": "infra/{scripts,test}",
                "line": 0,
                "detail": detail,
                "suggestion": ("run `ruff format infra/scripts infra/test` and re-run"),
            }
        )
        coverage.append(f"ruff format --check: FAIL ({fmt.returncode})")
    else:
        coverage.append("ruff format --check: PASS (clean)")

    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4)."""
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
