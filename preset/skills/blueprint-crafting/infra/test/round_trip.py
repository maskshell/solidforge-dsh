#!/usr/bin/env python3
"""Executable-subset round-trip test (iteration I1, ADR #1).

Proves the plan-model handshake contract with parallel-development's plan_queue.py: the EXECUTABLE SUBSET (item_id / seq / depends_on / dod_ref) round-trips losslessly in BOTH directions. The non-executable fields are honestly tagged — upstream_only carried as extensions parallel-dev ignores; downstream_only blueprint_subset is the documented NON-lossless field (ADR #1: no upstream source; left empty / downstream-filled at round-trip).

Two fixtures (both self-contained stand-ins — workspace rule 7: the real exemplars are referenced, not copied):
  - golden/plan-model.golden.json  — an UPSTREAM-origin plan-model (what this skill produces; blueprint_subset empty).
  - golden/sample.queue.md         — a DOWNSTREAM-origin queue in plan_queue.py's format (items carry blueprint_subset values + open_decisions).

Tests:
  A. queue -> plan-model -> queue : executable subset lossless; the lifted plan-model conforms to the schema; projected items are plan_queue.py- compatible (item_id + executable fields, JSON-serializable).
  B. plan-model -> queue -> plan-model : executable subset lossless.
  C. cross-fixture : the two fixtures agree on the executable subset (they describe the same items — the contract is unambiguous).
  D. blueprint_subset honesty : upstream-origin projects to empty; a queue with blueprint_subset lifts to a plan-model that TAGS it downstream-origin (never misread as upstream-sourced); projection emits empty. This field is intentionally non-lossless (ADR #1) — asserted, not hidden.

Run:

    python3 infra/test/round_trip.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # plan_model_schema
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))  # plan_model

import plan_model as pm  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402

GOLDEN_PM = os.path.join(HERE, "golden", "plan-model.golden.json")
SAMPLE_QUEUE = os.path.join(HERE, "golden", "sample.queue.md")
EXECUTABLE = pm.EXECUTABLE_SUBSET


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_json(path):
    return json.loads(read(path))


def fail(msg):
    raise AssertionError(msg)


def _exec_set(items):
    """Map item_id -> its executable subset dict, for set comparison."""
    return {it["item_id"]: pm.executable_subset_of(it) for it in items}


def test_a_queue_to_plan_model_to_queue():
    """Direction A: a plan_queue.py-format queue lifts to a schema-valid plan-model and projects back with a lossless executable subset."""
    queue_text = read(SAMPLE_QUEUE)
    q_items_original = pm.parse_queue_items(queue_text)

    # lift -> plan-model
    plan_model = pm.lift_queue_to_plan_model(
        queue_text, authority_chain=["docs/arch-design.md", "docs/iteration-plan.md"]
    )
    errs = validate_plan_model(plan_model)
    if errs:
        fail(f"A: lifted plan-model violates schema: {errs}")

    # project -> queue items
    q_items_roundtripped = pm.project_plan_model_to_queue(plan_model)

    # executable subset lossless
    if _exec_set(q_items_original) != _exec_set(q_items_roundtripped):
        fail(
            f"A: executable subset NOT lossless on queue->pm->queue:\n"
            f"  before {_exec_set(q_items_original)}\n  after  {_exec_set(q_items_roundtripped)}"
        )

    # plan_queue.py compatibility: every projected item has item_id + the 4 executable fields and is JSON-serializable (re-emitting the ```json block works — that is what plan_queue.parse_queue_structure reads).
    for it in q_items_roundtripped:
        for field in EXECUTABLE:
            if field not in it:
                fail(
                    f"A: projected item {it.get('item_id')} missing executable field {field}"
                )
        json.dumps(it)  # raises if not serializable

    # D (partial): the queue had blueprint_subset values; the lifted plan-model PRESERVES them as data (provenance — the value is not dropped).
    # They are downstream_only by classification (subset_tags), so never misread as upstream-sourced. Projection then emits empty (this skill's canonical grain produces no blueprint_subset) — the documented NON-lossless field (ADR #1).
    lifted_items = plan_model["items"]
    preserved = [i for i in lifted_items if i.get("blueprint_subset")]
    if not preserved:
        fail(
            "A: sample queue items have blueprint_subset but lift dropped them (provenance lost)"
        )
    for it in q_items_roundtripped:
        if it.get("blueprint_subset"):
            fail(
                f"A: projected item {it['item_id']} emitted non-empty blueprint_subset "
                f"{it['blueprint_subset']} -> must be empty (downstream_only, no upstream source)"
            )
    print("  A (queue -> plan-model -> queue, executable subset lossless): PASS")


def test_b_plan_model_to_queue_to_plan_model():
    """Direction B: an upstream-origin plan-model projects to a queue and lifts back with a lossless executable subset."""
    golden = load_json(GOLDEN_PM)
    errs = validate_plan_model(golden)
    if errs:
        fail(f"B: golden plan-model violates schema: {errs}")

    q_items = pm.project_plan_model_to_queue(golden)
    pm_items_roundtripped = [pm.lift_queue_item(it) for it in q_items]

    if _exec_set(golden["items"]) != _exec_set(pm_items_roundtripped):
        fail(
            f"B: executable subset NOT lossless on pm->queue->pm:\n"
            f"  before {_exec_set(golden['items'])}\n  after  {_exec_set(pm_items_roundtripped)}"
        )

    # D (partial): upstream-origin golden has empty blueprint_subset throughout.
    for it in golden["items"]:
        if it.get("blueprint_subset"):
            fail(
                f"B: golden item {it['item_id']} has non-empty blueprint_subset (upstream-origin must be empty)"
            )
    for it in pm_items_roundtripped:
        if it.get("blueprint_subset"):
            fail(
                f"B: roundtripped item {it['item_id']} gained blueprint_subset (must stay empty)"
            )
    print("  B (plan-model -> queue -> plan-model, executable subset lossless): PASS")


def test_c_cross_fixture_agreement():
    """The two fixtures describe the same items — the executable subset is unambiguous across representations."""
    golden = load_json(GOLDEN_PM)
    q_items = pm.parse_queue_items(read(SAMPLE_QUEUE))
    if _exec_set(golden["items"]) != _exec_set(q_items):
        fail(
            f"C: golden plan-model and sample queue disagree on executable subset:\n"
            f"  golden {_exec_set(golden['items'])}\n  queue  {_exec_set(q_items)}"
        )
    print("  C (golden plan-model and sample queue agree on executable subset): PASS")


def test_d_blueprint_subset_honesty():
    """blueprint_subset is the documented NON-lossless field (ADR #1). Assert its semantics explicitly so a future change cannot silently make it lossless (which would misrepresent the contract) or drop the downstream value on lift."""
    # upstream-origin -> projects to empty
    golden = load_json(GOLDEN_PM)
    for it in pm.project_plan_model_to_queue(golden):
        assert it["blueprint_subset"] == [], (
            "D: upstream-origin must project empty blueprint_subset"
        )

    # downstream-origin queue -> lifts preserving the value (provenance as data);
    # downstream_only classification (not a per-item tag) conveys the origin.
    q_items = pm.parse_queue_items(read(SAMPLE_QUEUE))
    lifted = [pm.lift_queue_item(it) for it in q_items]
    preserved = [i for i in lifted if i.get("blueprint_subset")]
    if not preserved:
        fail(
            "D: sample queue items have blueprint_subset but lift dropped them (provenance lost)"
        )
    # and projection re-emits empty regardless (canonical grain has no upstream source)
    for it in [pm.project_plan_model_item(i) for i in lifted]:
        assert it["blueprint_subset"] == [], (
            "D: projection must always emit empty blueprint_subset"
        )
    print(
        "  D (blueprint_subset honesty: upstream-empty, downstream-preserved, non-lossless): PASS"
    )


def test_e_odp_resolution_carries():
    """odp2-design D2: the projection carries bc's ODP `resolution` into
    open_decisions (so pd can seed a resolved ODP, not re-ask it), and the lift
    carries it back. A resolved ODP -> entry WITH resolution; an unresolved ODP ->
    entry WITHOUT a resolution key (no spurious empty value). The executable subset
    is unaffected (open_decisions is upstream_only, not in EXECUTABLE_SUBSET)."""
    pm_item = {
        "item_id": "R1",
        "seq": 0,
        "depends_on": [],
        "dod_ref": "docs/x.md#r1",
        "odp_status": [
            {
                "id": "ODP-RESOLVED",
                "kind": "resolve-now",
                "resolution": "decided: option B",
            },
            {"id": "ODP-OPEN", "kind": "resolve-now"},  # unresolved — no resolution
        ],
    }
    # project -> queue grain
    q_item = pm.project_plan_model_item(pm_item)
    od = {d["id"]: d for d in q_item.get("open_decisions", [])}
    if (
        "ODP-RESOLVED" not in od
        or od["ODP-RESOLVED"].get("resolution") != "decided: option B"
    ):
        fail(f"E: resolved ODP did not carry its resolution into open_decisions: {od}")
    if "resolution" in od.get("ODP-OPEN", {}):
        fail(f"E: unresolved ODP must NOT carry a resolution key: {od['ODP-OPEN']}")
    # executable subset unaffected
    for f in EXECUTABLE:
        if q_item.get(f) != pm_item.get(f):
            fail(
                f"E: projection changed executable field {f}: {q_item.get(f)} != {pm_item.get(f)}"
            )
    # lift back -> plan-model grain; the carried resolution survives
    lifted = pm.lift_queue_item(q_item)
    ods = {o["id"]: o for o in lifted.get("odp_status", [])}
    if ods.get("ODP-RESOLVED", {}).get("resolution") != "decided: option B":
        fail(f"E: lift dropped the carried resolution: {ods}")
    if "resolution" in ods.get("ODP-OPEN", {}):
        fail(
            f"E: lift manufactured a resolution on the unresolved ODP: {ods['ODP-OPEN']}"
        )
    print(
        "  E (odp resolution carries project <-> lift; unresolved stays keyless): PASS"
    )


def main():
    print("round_trip (executable-subset losslessness, ADR #1):")
    failures = []
    tests = (
        test_a_queue_to_plan_model_to_queue,
        test_b_plan_model_to_queue_to_plan_model,
        test_c_cross_fixture_agreement,
        test_d_blueprint_subset_honesty,
        test_e_odp_resolution_carries,
    )
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        f"\nExecutable subset ({', '.join(EXECUTABLE)}) round-trips losslessly both directions."
    )
    print(
        "blueprint_subset is the documented non-lossless downstream_only field (ADR #1)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
