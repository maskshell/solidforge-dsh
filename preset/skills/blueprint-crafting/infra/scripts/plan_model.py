#!/usr/bin/env python3
"""plan_model.py — the plan-model: field classification + queue round-trip helpers.

The plan-model is the normalized artifact this skill freezes and hands to parallel-development. Its handshake contract is the EXECUTABLE SUBSET (ADR #1): item_id / seq / depends_on / dod_ref round-trip losslessly with plan_queue.py's Phase -1 frozen queue. Every item field is classified into exactly one of three subsets (mirrored in the schema's subset_tags and here as constants):

  - EXECUTABLE   — the lossless round-trip contract (consumed by parallel-dev).
  - UPSTREAM_ONLY — metadata this skill sources; tagged, IGNORED downstream.
  - DOWNSTREAM_ONLY — blueprint_subset; NO upstream source, empty/downstream-filled.

The queue parser copies plan_queue.py's JSON_BLOCK_RE (workspace rule 7: copy-not-import; deleting parallel-development/ leaves this skill working standalone). lift/project are pure functions over dicts; round_trip.py exercises them both directions and asserts losslessness on the executable subset.

This is a library module imported by infra/test/round_trip.py. It is NOT a CLI driver yet — production authoring/freezing lands in I7. Run directly to print the field classification for inspection:

    python3 infra/scripts/plan_model.py
"""

import json
import re

# --- field classification (ADR #1) -------------------------------------------
# The single source of truth for the three-way split. Mirrored in infra/schemas/plan-model.schema.json's subset_tags. Keep in sync.

EXECUTABLE_SUBSET = ("item_id", "seq", "depends_on", "dod_ref")
UPSTREAM_ONLY = (
    "title",
    "scope",
    "source_location",
    "complexity",
    "risk",
    "odp_status",
    "constraints_profile",
    "parallel_group",
)
DOWNSTREAM_ONLY = ("blueprint_subset",)

SUBSET_TAGS = {
    "executable": list(EXECUTABLE_SUBSET),
    "upstream_only": list(UPSTREAM_ONLY),
    "downstream_only": list(DOWNSTREAM_ONLY),
}

# ADR #1: blueprint_subset (downstream_only) has no upstream source.
# At round-trip this skill leaves it EMPTY (project_plan_model_item emits []).
# When a downstream-origin queue carries values, lift preserves them as data, but the canonical upstream plan-model never sources them.

# Copied from plan_queue.py (workspace rule 7: copy-not-import). plan_queue.py extracts the first ```json fenced block and json.loads it; we parse identically so a queue it writes, we read, and vice versa.
JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def parse_queue_items(queue_text):
    """Extract the first ```json block (the item list) from a .queue.md document. Returns a list of item dicts. Raises ValueError if no/ malformed block (same contract as plan_queue.parse_queue_structure)."""
    m = JSON_BLOCK_RE.search(queue_text)
    if not m:
        raise ValueError(
            "no fenced ```json block found; the queue must carry its item "
            "structure in a ```json block under ## Items "
            "(see parallel-development/references/plan-driven-mode.md)"
        )
    try:
        items = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed json block: {e}") from e
    if not isinstance(items, list):
        raise ValueError("json block is not a list")
    return items


def executable_subset_of(item):
    """Project an item (plan-model OR queue grain) to its executable subset. depends_on defaults to [] when absent (a queue item may omit it)."""
    return {
        "item_id": item["item_id"],
        "seq": item["seq"],
        "depends_on": list(item.get("depends_on", [])),
        "dod_ref": item["dod_ref"],
    }


def lift_queue_item(q_item):
    """Queue item -> plan-model item.

    Carries the executable subset losslessly.
    Carries upstream_only descriptive fields (title/scope/source_location/parallel_group/open_decisions->odp_status) when the queue provides them (plan_queue.py's own queues carry these).
    The downstream_only blueprint_subset is PRESERVED as data when the queue carried a value (parallel-dev originated it), but it is downstream_only by classification (subset_tags) — a consumer never mistakes it for upstream-sourced.
    project_plan_model_item always re-emits it empty: this skill's canonical grain produces no blueprint_subset (ADR #1).

    Returns a plan-model item dict (schema-valid; validate with plan_model_schema).
    """
    pm = executable_subset_of(q_item)  # the lossless contract
    # upstream_only descriptive carry-through (queue-native fields)
    for field in ("title", "scope", "source_location", "parallel_group"):
        if field in q_item and q_item[field] is not None:
            pm[field] = q_item[field]
    # open_decisions (plan_queue grain) -> odp_status (plan-model grain).
    # Carry `resolution` through when the queue provides it (odp2-design D2), so a
    # resolved ODP survives a queue -> plan-model lift (no one-way leak).
    ods = q_item.get("open_decisions")
    if isinstance(ods, list):
        pm["odp_status"] = []
        for o in ods:
            if not (isinstance(o, dict) and o.get("id")):
                continue
            d = {"id": o["id"], "kind": o.get("kind", "deferred")}
            if o.get("resolution"):
                d["resolution"] = o["resolution"]
            pm["odp_status"].append(d)
    # downstream_only: blueprint_subset has no upstream source.
    # If the queue carried a value (parallel-dev originated it), we PRESERVE it as data for fidelity — but it is downstream_only by classification (subset_tags), so a consumer never mistakes it for an upstream-sourced value. project_* always re-emits empty (this skill's canonical grain produces no blueprint_subset).
    bs = q_item.get("blueprint_subset")
    pm["blueprint_subset"] = list(bs) if isinstance(bs, list) and bs else []
    return pm


def project_plan_model_item(pm_item):
    """Plan-model item -> queue item.

    Emits the executable subset (lossless).
    Carries upstream_only descriptive fields so the queue a human/parallel-dev reads stays readable. blueprint_subset is downstream_only with no upstream source -> emitted EMPTY (this skill does not fill it; parallel-development fills it at Phase 0).
    This is the explicit non-lossless field per ADR #1.
    """
    q = executable_subset_of(pm_item)  # the lossless contract
    for field in ("title", "scope", "source_location", "parallel_group"):
        if field in pm_item and pm_item[field] is not None:
            q[field] = pm_item[field]
    # odp_status -> open_decisions (queue grain) so plan_queue.py reads ODPs.
    # Carry bc's `resolution` through (odp2-design D2) so parallel-development can
    # seed a resolved ODP instead of re-asking a decision bc already closed. Absent
    # on unresolved ODPs (no spurious empty key).
    ods = pm_item.get("odp_status")
    if isinstance(ods, list) and ods:
        decisions = []
        for o in ods:
            if not (isinstance(o, dict) and o.get("id")):
                continue
            d = {"id": o["id"], "kind": o.get("kind", "deferred")}
            if o.get("resolution"):
                d["resolution"] = o["resolution"]
            decisions.append(d)
        q["open_decisions"] = decisions
    # downstream_only: empty at round-trip (no upstream source — ADR #1)
    q["blueprint_subset"] = []
    return q


def lift_queue_to_plan_model(
    queue_text,
    *,
    plan_model_version="v1",
    artifact_type="iteration-plan",
    authority_chain,
    conflict_rule=None,
):
    """Full queue document -> plan-model document."""
    q_items = parse_queue_items(queue_text)
    return {
        "plan_model_version": plan_model_version,
        "artifact_type": artifact_type,
        "authority_chain": list(authority_chain),
        **({"conflict_rule": conflict_rule} if conflict_rule else {}),
        "items": [lift_queue_item(it) for it in q_items],
        "subset_tags": {k: list(v) for k, v in SUBSET_TAGS.items()},
    }


def project_plan_model_to_queue(plan_model):
    """Plan-model document -> list of queue items (the ```json block contents)."""
    return [project_plan_model_item(it) for it in plan_model["items"]]


def assert_executable_lossless(label, original_items, roundtripped_items):
    """Assert each item's executable subset is unchanged across a round-trip.
    Returns None on success; raises AssertionError naming the first divergence."""
    by_id_a = {it["item_id"]: it for it in original_items}
    by_id_b = {it["item_id"]: it for it in roundtripped_items}
    if set(by_id_a) != set(by_id_b):
        raise AssertionError(
            f"{label}: item_id set changed — {set(by_id_a)} vs {set(by_id_b)}"
        )
    for iid in by_id_a:
        a = executable_subset_of(by_id_a[iid])
        b = executable_subset_of(by_id_b[iid])
        if a != b:
            raise AssertionError(
                f"{label}: executable subset diverged for {iid}:\n  before {a}\n  after  {b}"
            )


def main():
    """Print the field classification for inspection (no side effects)."""
    print("plan-model field classification (ADR #1):")
    print(json.dumps(SUBSET_TAGS, indent=2))
    print("\nexecutable subset = the lossless round-trip contract with plan_queue.py.")
    print("upstream_only     = tagged metadata this skill sources; ignored downstream.")
    print(
        "downstream_only   = blueprint_subset; no upstream source; empty/downstream-filled."
    )


if __name__ == "__main__":
    main()
