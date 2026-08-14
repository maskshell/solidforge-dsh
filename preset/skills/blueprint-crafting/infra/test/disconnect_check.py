#!/usr/bin/env python3
"""Disconnect + loading-chain checker for the blueprint-crafting skill.

Verifies the skill is structurally wired and the loading chain is unbroken at every decision-point doc — i.e. each capability is reachable at the POINT OF NEED, not just from some doc. This is what prevents a model following progressive disclosure (description -> SKILL.md -> docs/) from hitting a dead end. Mirrors parallel-development's disconnect_check.py (workspace rule 7: copy-not-import), adapted to this skill's doc-centric layout.

Checks (additive across iterations I0+I1; grows as I2-I7 land):

  - SKILL.md frontmatter: name + description present; description <=1024 chars (skill-creator quick_validate cap); SKILL.md <=500 lines (extract detail to docs/).
  - Loading chain: SKILL.md routes to the three authority docs (arch-design / iteration-plan / design-decisions), and each exists.
  - I0 activation boundary: infra/test/activation.json + trigger_check.py exist.
  - I1 handshake contract: infra/schemas/plan-model.schema.json + infra/test/plan_model_schema.py + infra/scripts/plan_model.py + infra/test/round_trip.py exist.
  - Link integrity: no broken markdown links across SKILL.md + docs/.

The per-artifact constraints-profile registry (constraints.json) lands at I3; this checker will verify it then. Run after any structural change:

    python3 infra/test/disconnect_check.py

Exits non-zero with actionable per-file guidance if any link is missing.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs")
INFRA = os.path.join(ROOT, "infra")
SKILL = os.path.join(ROOT, "SKILL.md")

AUTHORITY_DOCS = ["arch-design.md", "iteration-plan.md", "design-decisions.md"]
REQUIRED_FILES = {
    # I0 activation boundary
    "infra/test/activation.json": "the trigger-phrase registry (drives trigger_check.py)",
    "infra/test/trigger_check.py": "the bidirectional activation-boundary test",
    # I1 handshake contract
    "infra/schemas/plan-model.schema.json": "the plan-model schema (executable subset + tagged upstream/downstream fields)",
    "infra/test/plan_model_schema.py": "the stdlib plan-model schema validator (+ self-tests)",
    "infra/scripts/plan_model.py": "lift/project + EXECUTABLE_SUBSET constant (round-trip helpers)",
    "infra/test/round_trip.py": "the executable-subset round-trip assertion with plan_queue.py",
    # I5 outer-ring plan-reviewer (agent def moved to plugin top-level agents/ as
    # solidforge:plan-reviewer at Phase 4 cutover; this skill spawns it by scoped name)
    "infra/schemas/review-findings.schema.json": "the schema'd findings output contract for plan_reviewer",
    "infra/test/plan_reviewer_precision.py": "the plan_reviewer precision self-check (scaffolding gate + assert_precision)",
    # I2 normalizer
    "infra/scripts/normalizer.py": "the heterogeneous-format normalizer (graded extraction: latch / semantic-infer)",
    "infra/test/normalizer_goldens.py": "the 3-format normalizer goldens self-check",
    # I3 constraints-checker (registry-driven)
    "infra/scripts/constraints.json": "the per-artifact-type constraints-profile registry (rule 2)",
    "infra/scripts/constraints_check.py": "the inner-ring deterministic gate (anchors + authority + ODP)",
    "infra/test/constraints_check_goldens.py": "the constraints-checker goldens self-check (6 exemplars + negatives)",
    # I4 research-constraints (ADR #7 v1 subset)
    "infra/scripts/research_constraints.py": "the research constraints-profile (sources/staging/cost/provenance)",
    "infra/test/research_constraints_goldens.py": "the research v1 goldens self-check (fedaot-kb golden + negatives)",
    # I6 verdict-emitter + spec run-record
    "infra/schemas/run-record.schema.json": "the spec run-record schema (process_converged + rightness constant)",
    "infra/scripts/verdict.py": "the two-field verdict-emitter (rightness is a constant — field isolation)",
    "infra/test/run_record_schema.py": "the run-record stdlib validator (+ self-tests)",
    "infra/test/run_record.py": "the verdict field-isolation behavior test",
    # I7 end-to-end
    "infra/test/end_to_end.py": "the capstone: produce + converge + defect-repair + round-trip",
}

MAX_DESC_LEN = 1024
MAX_SKILL_LINES = 500


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def exists(path):
    return os.path.exists(path)


def description_text(text):
    """Lowercased description value from YAML frontmatter (block-scalar + inline). Line-based to avoid regex newline traps (mirrors parallel-development)."""
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
        return " ".join(b for b in body if b)
    return head


def main():
    skill = read(SKILL) or ""
    failures = []

    # --- frontmatter integrity ---
    lines = skill.splitlines()
    if not lines or lines[0].strip() != "---":
        failures.append(
            "SKILL.md has no YAML frontmatter -> add a `---`-delimited frontmatter block"
        )
    else:
        fm = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            fm.append(line)
        if not any(line.startswith("name:") for line in fm):
            failures.append(
                "frontmatter missing `name:` -> add `name: blueprint-crafting`"
            )
        desc = description_text(skill)
        if not desc:
            failures.append(
                "frontmatter missing `description:` -> add a description (the routing surface)"
            )
        elif len(desc) > MAX_DESC_LEN:
            failures.append(
                f"description is {len(desc)} chars (>{MAX_DESC_LEN} max) -> trim it "
                f"(skill-creator quick_validate rejects; hurts triggering)"
            )
    if len(lines) > MAX_SKILL_LINES:
        failures.append(
            f"SKILL.md is {len(lines)} lines (>{MAX_SKILL_LINES} ideal) -> extract detail to docs/"
        )

    # --- loading chain: SKILL.md routes to each authority doc, and each exists ---
    for doc in AUTHORITY_DOCS:
        doc_path = os.path.join(DOCS, doc)
        ref_inline = f"docs/{doc}"
        if not exists(doc_path):
            failures.append(f"authority doc missing: docs/{doc} -> create it")
        # the link may appear as docs/<doc> or docs/<doc#...>; check the bare path is referenced
        elif ref_inline not in skill:
            failures.append(
                f"LOADING-CHAIN BREAK: SKILL.md does not reference docs/{doc} -> add a link "
                f"(a model must reach the authority doc from SKILL.md at the point of need)"
            )

    # --- required infra files (I0 + I1 + I5 deliverables) ---
    for rel, why in REQUIRED_FILES.items():
        if not exists(os.path.join(ROOT, rel)):
            failures.append(f"missing {rel} -> create it ({why})")

    # --- agent definitions under infra/agents/ have valid frontmatter ---
    agents_dir = os.path.join(INFRA, "agents")
    if exists(agents_dir):
        for agent_file in sorted(
            f for f in os.listdir(agents_dir) if f.endswith(".agent.md")
        ):
            atext = read(os.path.join(agents_dir, agent_file)) or ""
            if not atext.startswith("---"):
                failures.append(
                    f"{agent_file} has no YAML frontmatter -> add a `---`-delimited frontmatter block"
                )
                continue
            if not any(
                line.startswith("name:")
                for line in atext.split("---", 2)[1].splitlines()
            ):
                failures.append(f"{agent_file} frontmatter missing `name:`")
            if not any(
                line.startswith("description:")
                for line in atext.split("---", 2)[1].splitlines()
            ):
                failures.append(
                    f"{agent_file} frontmatter missing `description:` (the agent trigger surface)"
                )
            # do NOT hardcode model/max_turns (workspace rule + global Agent Definition Conventions)
            fm = atext.split("---", 2)[1]
            if any(line.startswith("model:") for line in fm.splitlines()) or any(
                line.startswith("max_turns:") for line in fm.splitlines()
            ):
                failures.append(
                    f"{agent_file} hardcodes model/max_turns -> omit to inherit (workspace rule)"
                )

    # --- link integrity across SKILL.md + docs/ ---
    md_files = (
        [SKILL]
        + sorted(os.path.join(DOCS, f) for f in os.listdir(DOCS) if f.endswith(".md"))
        if exists(DOCS)
        else [SKILL]
    )
    link_re = re.compile(r"\]\(([^)]+\.md[^)]*)\)")
    fenced_re = re.compile(r"```.*?```", re.DOTALL)
    inline_re = re.compile(r"`[^`\n]*`")
    for md in md_files:
        text = read(md) or ""
        clean = fenced_re.sub("", text)
        clean = inline_re.sub("", clean)
        base = os.path.dirname(md)
        for tgt in link_re.findall(clean):
            if tgt.startswith("http"):
                continue
            path = tgt.split("#")[0]
            if path and not exists(os.path.join(base, path)):
                failures.append(f"broken link in {os.path.relpath(md, ROOT)} -> {tgt}")

    if failures:
        print("DISCONNECTS / LOADING-CHAIN BREAKS:")
        for f in failures:
            print("  - " + f)
        sys.exit(1)

    n_docs = len(AUTHORITY_DOCS)
    n_files = len(REQUIRED_FILES)
    print(
        f"OK: SKILL.md loadable, loading chain to {n_docs} authority doc(s) intact, "
        f"{n_files} required infra file(s) present, link integrity clean."
    )
    print(
        "    (grows additively: I3 adds the constraints.json registry check; I2+ add operator files.)"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
