#!/usr/bin/env python3
"""check-stale-credential-docs.py — the deterministic inner-ring gate for
credential-var enumeration drift (ADR #54 SHARED-ENV ALIGNMENT).

The shipped dsh profiles read the CC-convention `*_ANTHROPIC_AUTH_TOKEN` vars
via `_credential_env` / `_token_env`; the route-derived `<ROUTE>_API_KEY` names
(ZAI_CODING_CN_API_KEY / MINIMAX_CN_API_KEY / QWEN_TOKEN_PLAN_CN_API_KEY) are
SUPERSEDED — they survive only as the wrapper's user-authored-profile fallback
and in historical narratives. A doc that mentions one of them WITHOUT an
explicit supersession marker teaches a stale arming recipe — the failure class
the ADR #54 review caught three times (USER_GUIDE, dogfood README ×3,
verification.md).

Rule (inverted polarity — the stale text's own words do NOT count as a
marker): in every scanned file, a block naming a legacy var is compliant ONLY
when the SAME block carries an explicit supersession marker — `SUPERSEDED`
or `ADR #54`. Words like "route-derived", "fallback", or "legacy" are the
stale convention's own vocabulary and are deliberately NOT markers (a block
saying "ROUTE-DERIVED (ZAI_CODING_CN_API_KEY …)" is exactly the stale text).

Scanned: every committed *.md, the .env.solidforge.example templates, and the
profile JSONs. Exempt: the design-decisions.md ADR body itself (the historical
record). Exit 1 on the first violation. Stdlib-only (rule 7 / ADR #1).
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

LEGACY_VAR_NAMES = (
    "ZAI_CODING_CN_API_KEY",
    "MINIMAX_CN_API_KEY",
    "QWEN_TOKEN_PLAN_CN_API_KEY",
    # qwen.json's pre-ADR-#54 convention var (now _token_env =
    # QWEN_TOKEN_PLAN_CN_ANTHROPIC_AUTH_TOKEN) — the same stale-recipe class
    "QWEN_ANTHROPIC_AUTH_TOKEN",
)

# the recipe-template spellings (pattern form) — also stale when unmarked
LEGACY_PATTERNS = (
    r"<UPPERCASE\(route\)>_API_KEY",
    r"<ROUTE>_API_KEY",
)

# a block is compliant only when it carries one of THESE markers (case-insensitive).
# Deliberately NOT markers: "route-derived" / "fallback" / "legacy" — the stale
# convention's own vocabulary would self-satisfy the gate.
MARKERS = ("SUPERSEDED", "ADR #54")

# the ADR body may narrate the historical names without a per-block marker
ADR_BODY = (
    REPO
    / "preset"
    / "skills"
    / "parallel-development"
    / "references"
    / "design-decisions.md"
)


def _legacy_hits(block: str):
    return any(v in block for v in LEGACY_VAR_NAMES) or any(
        re.search(p, block) for p in LEGACY_PATTERNS
    )


def _line_blocks(text: str):
    """Yield (start_line_1based, block_text) for each run of non-blank lines —
    line-number-accurate (unlike re.split on separators of variable length)."""
    lines = text.splitlines()
    start = None
    buf = []
    for i, line in enumerate(lines, 1):
        if line.strip():
            if start is None:
                start = i
            buf.append(line)
        elif start is not None:
            yield start, "\n".join(buf)
            start = None
            buf = []
    if start is not None:
        yield start, "\n".join(buf)


def check_text(path: Path, text: str) -> bool:
    """Return True when every legacy-var block carries a supersession marker."""
    for start_line, block in _line_blocks(text):
        if not _legacy_hits(block):
            continue
        if any(m.lower() in block.lower() for m in MARKERS):
            continue
        # report the first offending line WITHIN the unmarked block
        for i, line in enumerate(block.splitlines(), start_line):
            if any(v in line for v in LEGACY_VAR_NAMES) or any(
                re.search(p, line) for p in LEGACY_PATTERNS
            ):
                print(
                    f"stale credential var without supersession marker: "
                    f"{path.relative_to(REPO)}:{i}: {line.strip()[:120]}",
                    file=sys.stderr,
                )
                return False
        # no single line matched (defensive): report the block head
        print(
            f"stale credential var without supersession marker: "
            f"{path.relative_to(REPO)}:{start_line}: {block.strip()[:120]}",
            file=sys.stderr,
        )
        return False
    return True


def scanned_files():
    yield from sorted(REPO.rglob("*.md"))
    yield from sorted(REPO.rglob(".env.solidforge.example"))
    yield from sorted(REPO.rglob("profiles/*.json"))


def main():
    failed = []
    for path in scanned_files():
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        if path.resolve() == ADR_BODY.resolve():
            continue  # the ADR body is the historical record itself
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not check_text(path, text):
            failed.append(str(path.relative_to(REPO)))
    if failed:
        print(
            f"check-stale-credential-docs: {len(failed)} file(s) fail",
            file=sys.stderr,
        )
        return 1
    print(
        "check-stale-credential-docs: all legacy credential-var mentions are "
        "marked SUPERSEDED / ADR #54"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
