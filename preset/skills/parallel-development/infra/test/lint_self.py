#!/usr/bin/env python3
"""Self-lint gate: the skill lints its OWN infra — Python (ruff) AND docs (markdownlint).

Dogfooding — the Fast Gate's check_python (ruff check + ruff format --check, see hooks/fast_gate.py) applied to the skill's own source. Mirrors smoke_gates.py: SKIPS with a clear message if ruff is absent, because ruff is a dev tool, NOT an infra runtime dependency (ADR #1 — the infra itself stays stdlib-only). Rule set lives in ruff.toml.

ALSO lints the skill's own markdown (SKILL.md + references/ + docs/) with `markdownlint` (markdownlint-cli), applying the repo-root `.markdownlint.json` (tuned in ADR #17 — MD024 siblings_only, MD033 allowed_elements). Same dogfood + graceful-skip shape as ruff: markdownlint is a dev tool, so a missing binary prints a coverage note (advisory) rather than failing. NOTE: the binary is `markdownlint` (from `brew install markdownlint-cli`); `markdownlint-cli2` and `mdl` are alternative CLIs not detected here.

    python3 infra/test/lint_self.py
"""

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGETS = [
    os.path.join(ROOT, "infra", "hooks"),
    os.path.join(ROOT, "infra", "scripts"),
    os.path.join(ROOT, "infra", "install"),
    os.path.join(ROOT, "infra", "test"),
]


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def find_md_config(start):
    """Walk up from `start` to the nearest markdownlint config (.markdownlint.json /
    .markdownlintrc / .jsonc / .yaml / .yml). markdownlint-cli's auto-discovery is
    cwd-sensitive: it did NOT apply the repo-root `.markdownlint.json` when invoked from the
    skill root (it flagged MD013 which the config disables), so we resolve the config path
    and pass `--config` explicitly — deterministic, independent of cwd."""
    names = (
        ".markdownlint.json",
        ".markdownlintrc",
        ".markdownlint.jsonc",
        ".markdownlint.yaml",
        ".markdownlint.yml",
    )
    d = start
    while True:
        for name in names:
            cand = os.path.join(d, name)
            if os.path.isfile(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main():
    print("lint_self (dogfood: skill lints its own infra):")
    if not have("ruff"):
        print(
            "  SKIP (ruff not installed; `brew install ruff` or `pip install ruff`). "
            "ruff is a dev tool, not an infra runtime dependency (ADR #1)."
        )
        sys.exit(0)
    rc = 0
    # Mirrors fast_gate.check_python: ruff check (lint) + ruff format --check (format).
    # Format added 2026-06-23 — lint_self previously enforced only `ruff check`, so the skill could pass its own self-check yet fail its own fast_gate on format (the self-check-must-mirror-the-runtime-gate principle; same shape as ADR #20).
    proc = subprocess.run(["ruff", "check", *TARGETS], cwd=ROOT)
    rc |= proc.returncode
    fmt = subprocess.run(["ruff", "format", "--check", *TARGETS], cwd=ROOT)
    rc |= fmt.returncode
    # Markdown: the skill's own docs (all *.md under the skill root). markdownlint-cli
    # auto-discovery is cwd-sensitive (see find_md_config), so --config is passed explicitly.
    # Same graceful-skip shape as ruff: a missing markdownlint prints a coverage note
    # (advisory), never a silent green (rule 3) and never a hard fail for being unarmed.
    md_files = sorted(
        set(glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True))
        | {os.path.join(ROOT, "SKILL.md")}
    )
    md_files = [f for f in md_files if os.path.isfile(f)]
    md_cfg = find_md_config(ROOT)
    if have("markdownlint"):
        md_argv = ["markdownlint"]
        if md_cfg:
            md_argv += ["--config", md_cfg]
        mproc = subprocess.run([*md_argv, *md_files], cwd=ROOT)
        rc |= mproc.returncode
    else:
        print(
            "  markdown: SKIP (markdownlint not installed; `brew install markdownlint-cli`). "
            "Docs not linted this run (advisory)."
        )
    if rc == 0:
        print(
            "  PASS (the skill's own infra is clean by its own Fast Gate: ruff lint + format"
            "; markdown docs clean by markdownlint)"
        )
    else:
        print(
            "  FAIL (the skill does not pass its own lint/format/markdownlint — fix the findings above)"
        )
    sys.exit(rc)


if __name__ == "__main__":
    main()
