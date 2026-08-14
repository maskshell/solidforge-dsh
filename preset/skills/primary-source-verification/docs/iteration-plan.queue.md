---
queue_version: v1
frozen_at: 2026-07-31
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
    "item_id": "PSV-I0",
    "seq": 0,
    "depends_on": [],
    "dod_ref": "iteration-plan.md#PSV-I0",
    "title": "scaffold + SKILL.md + activation/scope-guard",
    "scope": "Loadable skill skeleton; Scope Guard routes code→pd, spec→bc, convergence→csr; positions psv as the outcome-axis per-claim verifier, additive to csr, never correctness_converged.",
    "source_location": "iteration-plan.md §3 (PSV-I0)",
    "open_decisions": [
      {
        "id": "name-lock",
        "kind": "deferred",
        "resolution": "Name 'primary-source-verification' is PROPOSED, pending human LOCK (proposal §9 Q1). Working name used throughout; lock at Phase-A acceptance."
      }
    ],
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I1",
    "seq": 1,
    "depends_on": [
      "PSV-I0"
    ],
    "dod_ref": "iteration-plan.md#PSV-I1",
    "title": "schemas (doc-findings extension + coverage-record)",
    "scope": "Copy csr doc-findings verbatim, extend kind with claim-refuted/claim-narrowed/claim-unverifiable (strict superset, csr's 6 preserved); new coverage-record carrying oracle_verified_under_known_coverage + N/R/W/K/M; evidence standard raised (fetched quote required).",
    "source_location": "iteration-plan.md §3 (PSV-I1)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I2",
    "seq": 2,
    "depends_on": [
      "PSV-I1"
    ],
    "dod_ref": "iteration-plan.md#PSV-I2",
    "title": "claim-extraction agent/prompt",
    "scope": "Enumerate atomic, source-admissible claims (location + adjudicating source); tag interpretive claims unverifiable; carry extractor blind-spot caveat (rule 3).",
    "source_location": "iteration-plan.md §4 (PSV-I2)",
    "parallel_group": "post-I1",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I3",
    "seq": 3,
    "depends_on": [
      "PSV-I1"
    ],
    "dod_ref": "iteration-plan.md#PSV-I3",
    "title": "source-fetch tooling + per-claim verdict comparator",
    "scope": "Fetch cited source → parsed text. Credential surface (novel-1): same-family runtime comparator (no isolated LLM token); open sources fetched without credential; paywalled → claim-unverifiable; csr's install.md LLM-token pattern does NOT apply (psv disclaims the substrate). Comparator assigns verified/refuted/narrowed/unverifiable with fetched-quote evidence; comparison blind-spot caveat.",
    "source_location": "iteration-plan.md §4 (PSV-I3)",
    "parallel_group": "post-I1",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I4",
    "seq": 4,
    "depends_on": [
      "PSV-I2",
      "PSV-I3"
    ],
    "dod_ref": "iteration-plan.md#PSV-I4",
    "title": "coverage driver (owns the §3 pipeline contract)",
    "scope": "Drive extract→fetch→verdict→coverage; emit coverage-record (oracle_verified_under_known_coverage: N/R/W/K of M) + doc-findings packet; NEVER correctness_converged; quote-less → unverifiable; M=0 (no admissible claims) → human escalation, distinct from K>0, never silent 0-of-0 (novel-2).",
    "source_location": "iteration-plan.md §5 (PSV-I4)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I5",
    "seq": 5,
    "depends_on": [
      "PSV-I4"
    ],
    "dod_ref": "iteration-plan.md#PSV-I5",
    "title": "self-gates + standard set",
    "scope": "(a) fetched-quote invariant gate (quote-less → unverifiable); (b) findings+coverage shape-contract; (c) offline coverage-policy (counts sum; no correctness_converged); + standard disconnect_check/plugin_layout/lint_self.",
    "source_location": "iteration-plan.md §5 (PSV-I5)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "PSV-I6",
    "seq": 6,
    "depends_on": [
      "PSV-I5"
    ],
    "dod_ref": "iteration-plan.md#PSV-I6",
    "title": "dogfood + 质量稳定 gate",
    "scope": "N≥3 real artifacts (≥1 long doc), ≥1 with a known misattribution psv catches via the fetched source (spec-gaming pre-fix draft is canonical); record measured coverage profile.",
    "source_location": "iteration-plan.md §5 (PSV-I6)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
