---
queue_version: v1
frozen_at: 2026-06-22
plan_ref: docs/iteration-plan.md
authority_chain:
  - docs/arch-design.md
  - docs/iteration-plan.md
status: frozen
---

# Plan Queue — blueprint-crafting I0+I1 (sample fixture)

FROZEN plan interpretation (sample fixture mirroring plan_queue.py's queue format — see parallel-development/references/plan-driven-mode.md). Used by infra/test/round_trip.py to prove the executable-subset round-trip. This is a minimal stand-in, NOT a copy of any real queue (workspace rule 7: the real exemplars at ws-edu/physics_schema_mcp/docs/plan-queues/ are referenced, not copied).

This fixture represents a DOWNSTREAM-origin queue: its items carry `blueprint_subset` values (a parallel-development concern) and `open_decisions` (plan_queue grain) so the round-trip test exercises the lift's downstream-tagging and odp_status mapping.

## Items

```json
[
  {
    "seq": 0,
    "item_id": "bc-I0",
    "title": "scaffold + activation/routing",
    "scope": "SKILL.md + activation boundary",
    "source_location": "docs/iteration-plan.md section 3 (I0)",
    "depends_on": [],
    "dod_ref": "docs/iteration-plan.md#I0-done",
    "blueprint_subset": ["AC-activation"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 1,
    "item_id": "bc-I1",
    "title": "plan-model spec + schema + round-trip",
    "scope": "executable subset round-trips with plan_queue.py",
    "source_location": "docs/iteration-plan.md section 3 (I1)",
    "depends_on": ["bc-I0"],
    "dod_ref": "docs/iteration-plan.md#I1-done",
    "blueprint_subset": ["AC-roundtrip"],
    "parallel_group": null,
    "open_decisions": [
      {"id": "ODP-3", "kind": "resolve-now"}
    ]
  },
  {
    "seq": 2,
    "item_id": "bc-I2",
    "title": "normalizer (format -> plan-model)",
    "scope": "3 source formats each golden; graded extraction",
    "source_location": "docs/iteration-plan.md section 4 (I2)",
    "depends_on": ["bc-I1"],
    "dod_ref": "docs/iteration-plan.md#I2-done",
    "blueprint_subset": ["AC-normalize"],
    "parallel_group": "wave-A",
    "open_decisions": []
  }
]
```
