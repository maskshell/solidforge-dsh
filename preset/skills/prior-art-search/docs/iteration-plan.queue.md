---
queue_version: v1
frozen_at: 2026-08-01
plan_ref: proposal.md
authority_chain:
  - proposal.md
  - iteration-plan.md
status: frozen
---

# Plan Queue — iteration-plan

FROZEN plan interpretation emitted by blueprint-crafting `freeze`. Read-only for the executor; revise only via the Revision Channel (`status` -> `revising` -> edit + queue_version bump -> `status: frozen`). See parallel-development `references/plan-driven-mode.md`.

## Summary (checkpoint view)

7 item(s). DoD source: proposal.md.

## Items

```json
[
  {
    "item_id": "NC-I0",
    "seq": 0,
    "depends_on": [],
    "dod_ref": "iteration-plan.md#NC-I0",
    "title": "scaffold + SKILL.md + scope-guard",
    "scope": "Loadable skill skeleton; Scope Guard routes code→pd/spec→bc/convergence→csr/cited→psv/novelty-collision→this; never novel_confirmed; weaker-oracle positioning.",
    "source_location": "iteration-plan.md §3 (NC-I0)",
    "open_decisions": [
      {
        "id": "name-lock",
        "kind": "deferred",
        "resolution": "Name 'prior-art-search' PROPOSED, pending human LOCK. Working name used throughout."
      }
    ],
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I1",
    "seq": 1,
    "depends_on": [
      "NC-I0"
    ],
    "dod_ref": "iteration-plan.md#NC-I1",
    "title": "schemas (collision-findings + collision-record)",
    "scope": "Copy psv LANDED doc-findings verbatim, extend kind with claim-collision/uncited-relevant/inconclusive (strict superset); collision-record with collisions_under_known_coverage + N/U/C/I/M; never novel_confirmed.",
    "source_location": "iteration-plan.md §3 (NC-I1)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I2",
    "seq": 2,
    "depends_on": [
      "NC-I1"
    ],
    "dod_ref": "iteration-plan.md#NC-I2",
    "title": "novelty-claim-extraction agent",
    "scope": "Enumerate atomic novelty claims (location + search target); distinguish from factual/citation (psv) + interpretive (escalate); extractor blind-spot caveat.",
    "source_location": "iteration-plan.md §4 (NC-I2)",
    "parallel_group": "post-I1",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I3",
    "seq": 3,
    "depends_on": [
      "NC-I1"
    ],
    "dod_ref": "iteration-plan.md#NC-I3",
    "title": "multi-source search + collision comparator",
    "scope": "Search prior art per claim; comparator assigns collision/uncited-relevant/clear-under-search/inconclusive with fetched QUOTE for collisions (mirrors psv fetched-quote); two-layer oracle caveat.",
    "source_location": "iteration-plan.md §4 (NC-I3)",
    "parallel_group": "post-I1",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I4",
    "seq": 4,
    "depends_on": [
      "NC-I2",
      "NC-I3"
    ],
    "dod_ref": "iteration-plan.md#NC-I4",
    "title": "coverage driver",
    "scope": "Drive extract→search→collision→coverage; emit collision-record (collisions_under_known_coverage: N/U/C/I of M) + findings; M=0 escalate; never novel_confirmed; quote-less → inconclusive.",
    "source_location": "iteration-plan.md §5 (NC-I4)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I5",
    "seq": 5,
    "depends_on": [
      "NC-I4"
    ],
    "dod_ref": "iteration-plan.md#NC-I5",
    "title": "self-gates + standard set",
    "scope": "(a) collision fetched-quote invariant gate; (b) shape-contract; (c) coverage-policy (counts; no novel_confirmed; M=0/I>0 escalate) + standard disconnect_check/plugin_layout/lint_self.",
    "source_location": "iteration-plan.md §5 (NC-I5)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "NC-I6",
    "seq": 6,
    "depends_on": [
      "NC-I5"
    ],
    "dod_ref": "iteration-plan.md#NC-I6",
    "title": "dogfood + 质量稳定 gate",
    "scope": "N≥3 real artifacts (≥1 with known prior-art collision — spec-gaming paper re-run); record coverage profile.",
    "source_location": "iteration-plan.md §5 (NC-I6)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
