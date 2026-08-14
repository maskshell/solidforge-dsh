#!/usr/bin/env python3
"""check-skill-frontmatter.py — deterministic guard over the preset's SKILL.md
frontmatter against the DSH skill-filesystem parser's strictness.

The deployment parses frontmatter with the `yaml` package: an inline
`description: <text>` whose text contains ": " (e.g. "Phase A: ...") fails with
"nested mappings are not allowed in compact mappings", and the provider
SILENTLY drops the skill from the catalog (menu, skill tool, model catalog).
This check enforces the one shape that cannot regress that way:

- `name:` must equal the directory name (kebab-case);
- `description:` must be a BLOCK scalar (`|` or `>-`), never inline.

Block scalars accept any content, including ": ", so future edits cannot
silently re-introduce the hazard.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_ROOT = HERE.parent / "preset" / "skills"

SKILL_NAMES = [
    "parallel-development",
    "blueprint-crafting",
    "cross-source-review",
    "primary-source-verification",
    "prior-art-search",
]

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BLOCK_DESC_RE = re.compile(r"^description:[ \t]*(\||>-)([ \t]*)$", re.MULTILINE)
INLINE_DESC_RE = re.compile(r"^description:[ \t]*[^ \t|>\n]", re.MULTILINE)


def frontmatter(text: str) -> str:
    """Return the raw frontmatter block (without fences) or '' when absent."""
    m = re.match(r"^---\n([\s\S]*?)\n---\n", text)
    return m.group(1) if m else ""


def main() -> int:
    failures = []
    for name in SKILL_NAMES:
        path = SKILLS_ROOT / name / "SKILL.md"
        if not path.is_file():
            failures.append(f"{name}: SKILL.md missing")
            continue
        fm = frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            failures.append(f"{name}: missing YAML frontmatter fence")
            continue
        name_m = re.search(r"^name:[ \t]*(\S+)[ \t]*$", fm, re.MULTILINE)
        if name_m is None or name_m.group(1) != name:
            failures.append(
                f"{name}: frontmatter name={name_m.group(1) if name_m else None!r} "
                f"must equal the directory name"
            )
        if name_m is not None and not KEBAB_RE.match(name_m.group(1)):
            failures.append(f"{name}: skill name {name_m.group(1)!r} is not kebab-case")
        if INLINE_DESC_RE.search(fm) or not BLOCK_DESC_RE.search(fm):
            failures.append(
                f"{name}: description must be a BLOCK scalar (description: | or >-) "
                "— inline descriptions can contain ': ' and get silently dropped "
                "by the deployment's strict YAML frontmatter parser"
            )
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(
        f"PASS: {len(SKILL_NAMES)} SKILL.md frontmatter blocks meet the block-scalar contract"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
