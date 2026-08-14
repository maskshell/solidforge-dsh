#!/usr/bin/env python3
"""Self-lint gate: blueprint-crafting lints its OWN infra Python with ruff.

Dogfooding — the fast_gate's check_python (ruff check + ruff format --check; the gate lives in the parallel-development skill at infra/hooks/fast_gate.py) applied to this skill's own source. Mirrors parallel-development/infra/test/lint_self.py: SKIPS with a clear message if ruff is absent (ruff is a dev tool, not an infra runtime dependency).

Added 2026-06-23 so blueprint-crafting's self-checks mirror the repo-wide fast_gate — the self-check-must-mirror-the-runtime-gate principle (same shape as ADR #20 for the manifest). Without it, this skill could pass its self-checks yet fail the fast_gate on lint/format (which is what surfaced a latent 18-error / 16-format-file debt).

    python3 infra/test/lint_self.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGETS = [
    os.path.join(ROOT, "infra", "scripts"),
    os.path.join(ROOT, "infra", "test"),
]


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def main():
    print("lint_self (dogfood: blueprint-crafting lints its own infra):")
    if not have("ruff"):
        print(
            "  SKIP (ruff not installed; `brew install ruff` or `pip install ruff`). "
            "ruff is a dev tool, not an infra runtime dependency."
        )
        sys.exit(0)
    rc = 0
    # Mirrors fast_gate.check_python: ruff check (lint) + ruff format --check (format).
    proc = subprocess.run(["ruff", "check", *TARGETS], cwd=ROOT)
    rc |= proc.returncode
    fmt = subprocess.run(["ruff", "format", "--check", *TARGETS], cwd=ROOT)
    rc |= fmt.returncode
    if rc == 0:
        print(
            "  PASS (blueprint-crafting's own infra is clean by the fast_gate: lint + format)"
        )
    else:
        print(
            "  FAIL (blueprint-crafting does not pass its own lint/format — fix the findings above)"
        )
    sys.exit(rc)


if __name__ == "__main__":
    main()
