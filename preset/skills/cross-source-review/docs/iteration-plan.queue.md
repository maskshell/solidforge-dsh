---
queue_version: v1
frozen_at: 2026-07-07
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
    "item_id": "CSR-I0",
    "seq": 0,
    "depends_on": [],
    "dod_ref": "iteration-plan.md#csr-i0",
    "title": "scaffold + SKILL.md + activation/scope-guard",
    "scope": "Loadable skill skeleton; Scope Guard routes code->parallel-development / spec-authoring->blueprint-crafting; Q4 explicit-invocation noted (3-way trigger_check deferred).",
    "source_location": "proposal.md §2, §6, §9 Q4",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I1",
    "seq": 1,
    "depends_on": [
      "CSR-I0"
    ],
    "dod_ref": "iteration-plan.md#csr-i1",
    "title": "schemas: doc-findings + convergence-record",
    "scope": "doc-findings.schema.json (generalize bc review-findings; v1 kind enum = 6 Q2 kinds; severity keeps bc {blocker,warning,coverage} - coverage is honest-disclosure, distinct from coverage-gap KIND) + convergence-record.schema.json (fields name-aligned to loop_state run-record; no code dep).",
    "source_location": "proposal.md §9 Q2, Q3",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I2",
    "seq": 2,
    "depends_on": [
      "CSR-I1"
    ],
    "dod_ref": "iteration-plan.md#csr-i2",
    "title": "same-source leg: skill-local doc-reviewer agent",
    "scope": "Fresh-context, read-only, outcome-axis-barred doc-reviewer agent returning doc-findings shape; NOT plan-reviewer (plan-model-shaped).",
    "source_location": "proposal.md §3, §9 Q5; FX-05",
    "parallel_group": "legs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I3",
    "seq": 3,
    "depends_on": [
      "CSR-I1"
    ],
    "dod_ref": "iteration-plan.md#csr-i3",
    "title": "heterogeneous substrate: copy-pattern hetero_review.py, doc-adapted",
    "scope": "Copy-pattern pd hetero_review.py (FLAG-SURFACE MANIFEST, token-injection, fence-aware parse, substrate-error DEGRADE, multi-provider merge) with a DOC prompt + doc-findings schema; no --diff/--blueprint hard-require. Preserve function-signature contract + divergence log.",
    "source_location": "proposal.md §3, §5, §8; hetero_review.py is the pattern source",
    "parallel_group": "legs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I4",
    "seq": 4,
    "depends_on": [
      "CSR-I2",
      "CSR-I3"
    ],
    "dod_ref": "iteration-plan.md#csr-i4",
    "title": "convergence loop driver",
    "scope": "Orchestrate 同源<->异源 multi-round debate: caps by artifact size (short=2/long=5-7), substantive-convergence BOTH prongs (no-new-Blocker AND core-claims-coverage; not zero-finding), per-round reconciliation table, cap->human, adversarial-stalemate, don't-blind-trust-either; OWNS the proposal §3 pluggable-seam (findings-schema as parameter + 同源-leg as callback); emit convergence-record.",
    "source_location": "proposal.md §3 (policy + reconciliation table)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I5",
    "seq": 5,
    "depends_on": [
      "CSR-I4"
    ],
    "dod_ref": "iteration-plan.md#csr-i5",
    "title": "self-gates (Q6) + standard set",
    "scope": "Three skill-specific gates (dogfood own loop on own SKILL.md - SKIPS gracefully w/o API tokens, recorded log substitutes; findings shape-contract mirror adapter_shape_check; offline convergence-policy mirror hetero_review_wiring + core-claims-coverage fixture) PLUS standard (disconnect_check/plugin_layout/lint_self).",
    "source_location": "proposal.md §9 Q6",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "CSR-I6",
    "seq": 6,
    "depends_on": [
      "CSR-I5"
    ],
    "dod_ref": "iteration-plan.md#csr-i6",
    "title": "dogfood + 质量稳定 gate (Q7)",
    "scope": "Run the skill on N>=3 real docs (>=1 long-doc cap=5-7 + own SKILL.md as one of the N); record a measured convergence profile.",
    "source_location": "proposal.md §5, §9 Q7",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
