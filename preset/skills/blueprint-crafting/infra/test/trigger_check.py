#!/usr/bin/env python3
"""Bidirectional activation-boundary test for blueprint-crafting.

The skill's `description` frontmatter is the routing surface a model tokenizes at activation time.
This test asserts that surface partitions the request space correctly between blueprint-crafting and parallel-development — the activation collision risk called out in iteration-plan I0.

Data-driven by infra/test/activation.json (the trigger-phrase registry). Four assertions:

  1. POSITIVE COVERAGE (strict) — each activation-positive phrase has >=1 keyword in THIS skill's description. (If absent, a model tokenizing the description would not route a spec/design/plan/research request here.)
  2. NO POSITIVE STEAL (strict) — THIS skill's description does NOT contain any of parallel-development's distinctive trigger keywords (TDD / red-green / test-first / convergent-fix-loop). These are chosen so this skill can avoid them ENTIRELY — even in negation — so their presence would unambiguously steal code requests. (Generic code words like "implement"/"refactor"/"bug" are NOT in this list: this skill legitimately mentions them to route AWAY. Distinguishing a positive trigger from a routing-negation is not deterministically decidable from the description surface — the seam, ADR #8.)
  3. PARALLEL-DEV REACHABLE (strict, one global check) — parallel-development's description claims the implementation domain (contains "implement" or "code" or "feature"). Proves code-implementation requests have a home. Skipped with a note if parallel-development is absent (the skill still works standalone; workspace rule 7).
  4. SCOPE GUARD (strict, structural) — SKILL.md has a Scope Guard that names code implementation as out-of-scope and routes it to parallel-development (the misuse-hint mechanism mirroring parallel-development's Scope Guard step 1).

The `negative` list in activation.json documents routing intent (which requests should route to parallel-development) and is surfaced as a coverage note for human review; it is NOT machine-asserted per-keyword because of the positive-trigger-vs-routing-negation seam above. The machine-asserted safety is #2 (distinctive keywords absent).

The seam this test cannot close: activation routing is ultimately the model's call, not a deterministic router. This test asserts the description SURFACE partitions correctly; it cannot prove a model will always route correctly. See design-decisions.md ADR #8.

Run:

    python3 infra/test/trigger_check.py

Exits non-zero with actionable guidance if any assertion fails. Add a trigger case via infra/test/activation.json, not by editing this checker.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(ROOT, "SKILL.md")
REGISTRY = os.path.join(ROOT, "infra", "test", "activation.json")
PARALLEL_DEV_SKILL = os.path.normpath(
    os.path.join(ROOT, "..", "parallel-development", "SKILL.md")
)


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def extract_description(text):
    """Pull the `description` value out of YAML frontmatter.
    Handles block scalars (| and >) and inline scalars. Lowercased for keyword matching.
    Line-based to avoid regex newline traps in block scalars (mirrors disconnect_check)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    fm = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm.append(line)
    i = 0
    while i < len(fm) and not fm[i].startswith("description:"):
        i += 1
    if i >= len(fm):
        return ""
    head = fm[i][len("description:") :].strip()
    if head in ("|", ">", ""):
        body = []
        for line in fm[i + 1 :]:
            if line[:1] in (" ", "\t") or line.strip() == "":
                body.append(line.strip())
            else:
                break
        return " ".join(b for b in body if b).lower()
    return head.lower()


def main():
    reg = json.loads(read(REGISTRY) or "{}")
    skill_text = read(SKILL) or ""
    desc = extract_description(skill_text)
    if not desc:
        print("FAIL: could not extract a description from SKILL.md frontmatter")
        sys.exit(1)

    failures = []
    notes = []

    # 1. POSITIVE COVERAGE
    for entry in reg.get("positive", []):
        keys = [k.lower() for k in entry["keys"]]
        if not any(k in desc for k in keys):
            failures.append(
                f"POSITIVE phrase '{entry['phrase']}' has no keyword in the description "
                f"(looked for {keys}) -> add one of {keys} to the SKILL.md description"
            )

    # 2. NO POSITIVE STEAL (strict: distinctive keywords absent entirely)
    # 3. PARALLEL-DEV REACHABLE (strict, one global check)
    pd_text = read(PARALLEL_DEV_SKILL)
    distinctive = [k.lower() for k in reg.get("parallel_dev_distinctive", [])]
    stolen = [k for k in distinctive if k in desc]
    if stolen:
        failures.append(
            f"NO POSITIVE STEAL violated: this description contains parallel-development's "
            f"distinctive keyword(s) {stolen} -> remove them; they route code requests away "
            f"from this skill"
        )
    if pd_text is None:
        notes.append(
            f"parallel-development not found at {PARALLEL_DEV_SKILL}; PARALLEL-DEV REACHABLE "
            f"skipped (workspace-integration concern; this skill still works standalone)."
        )
    else:
        pd_desc = extract_description(pd_text)
        impl_claim = any(k in pd_desc for k in ("implement", "code", "feature"))
        if not impl_claim:
            failures.append(
                "PARALLEL-DEV REACHABLE violated: parallel-development's description does not claim the implementation domain (no 'implement'/'code'/'feature') -> code requests would have no home; align parallel-development's description"
            )
    # surface the negative list as a coverage note (not machine-asserted: the
    # positive-trigger-vs-routing-negation seam — ADR #8)
    neg_phrases = [e["phrase"] for e in reg.get("negative", [])]
    notes.append(
        f"routing intent (human review, not machine-asserted — ADR #8 seam): these should "
        f"route to parallel-development: {neg_phrases}"
    )

    # 4. SCOPE GUARD structural assertion (misuse-hint mechanism)
    has_scope_guard = (
        re.search(r"^#+\s*Scope Guard", skill_text, re.MULTILINE) is not None
    )
    if not has_scope_guard:
        failures.append(
            "SCOPE GUARD missing: SKILL.md has no 'Scope Guard' heading -> add one (mirrors parallel-development's Scope Guard step 1; emits out-of-scope for code)"
        )
    # the guard must name code implementation as out-of-scope AND route to parallel-development
    guard_block = ""
    m = re.search(r"(?ims)^#+\s*Scope Guard.*?(?=^#+\s)", skill_text)
    if m:
        guard_block = m.group(0)
    scope_ok = (
        "parallel-development" in guard_block
        and re.search(r"out-of-scope|out of scope", guard_block, re.IGNORECASE)
        is not None
        and re.search(r"implement|code", guard_block, re.IGNORECASE) is not None
    )
    if not scope_ok:
        failures.append(
            "SCOPE GUARD incomplete: the Scope Guard section must name code implementation as out-of-scope and route it to parallel-development (misuse hint)"
        )

    # report
    for n in notes:
        print("note: " + n)
    if failures:
        print("ACTIVATION-BOUNDARY FAILURES:")
        for f in failures:
            print("  - " + f)
        sys.exit(1)

    n_pos = len(reg.get("positive", []))
    n_neg = len(reg.get("negative", []))
    print(
        f"OK: activation boundary holds — {n_pos} positive phrases covered (strict), "
        f"{n_neg} negative phrases documented (routing intent; the strict guard is the "
        f"distinctive-keyword check), no distinctive-keyword theft, scope guard present."
    )
    print(
        "    (registry-driven: add a trigger case via infra/test/activation.json, "
        "not by editing this checker.)"
    )
    print(
        "    (caveat: activation routing is the model's call; this asserts the description "
        "surface — ADR #8.)"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
