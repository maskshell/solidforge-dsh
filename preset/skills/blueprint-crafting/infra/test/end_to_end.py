#!/usr/bin/env python3
"""end-to-end: produce + converge + repair (iteration I7, the capstone).

Wires the operators built in I2–I6 into the full chain and proves the three I7 DoD outcomes (iteration-plan §5 + §6 process-axis acceptance gate):

  1. PRODUCE + CONVERGE — normalize a seed artifact -> plan-model, author its anchors, run the constraints-checker, emit a run-record with process_converged; the produced plan-model is schema-valid and round-trips with plan_queue.py on the executable subset. (Research variant too.)
  2. DEFECT -> FAIL -> REPAIR -> FLIP — a defect-injected fixture (missing anchor + authority contradiction + unresolved resolve-now ODP; research variant: unsourced claim) yields process_converged=false with the correct named flags, then REPAIR flips it to true (the convergence proof, not a demo).
  3. ROUND-TRIP — the produced plan-model round-trips losslessly on the executable subset (re-affirms ADR #1 at the end of the pipeline).

The outer ring (plan_reviewer) is an LLM eval; for the deterministic self-check it is represented by a passed-in clean/warning-only outer so process_converged is deterministic. Running the actual reviewer is the ADR #10 eval. Run:

    python3 infra/test/end_to_end.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))

import normalizer  # noqa: E402
import constraints_check  # noqa: E402
import research_constraints  # noqa: E402
import verdict  # noqa: E402
import plan_model as pmm  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402

RICH_MD_SEED = os.path.join(HERE, "golden", "normalizer", "rich-md", "source.md")
IT_PLAN_ANCHORS = [
    "complexity-tiers",
    "dependency-edges",
    "per-iteration-dod",
    "dag",
    "phase-acceptance-gates",
    "risks-mitigations",
    "out-of-scope",
    "cross-cutting-tasks",
    "facade-impact-assessment",
]


def _fail(msg):
    raise AssertionError(msg)


def _complete_anchors():
    return {a: {"present": True} for a in IT_PLAN_ANCHORS}


def _outer_clean():
    return {
        "findings": [{"severity": "warning", "kind": "over-engineering"}],
        "coverage": [],
    }


# --- 1. produce + converge ---------------------------------------------------


def produce_iteration_plan_converges():
    with open(RICH_MD_SEED, encoding="utf-8") as fh:
        seed = fh.read()
    pm = normalizer.normalize(seed)["plan_model"]
    pm["anchors"] = _complete_anchors()  # the author step: declare anchors satisfied
    errs = validate_plan_model(pm)
    if errs:
        _fail(f"produce: produced plan-model not schema-valid: {errs}")
    inner = constraints_check.check(pm)
    if not inner["passed"] or inner["failures"]:
        _fail(
            f"produce: inner ring should pass on a complete artifact, got {inner['failures']}"
        )
    if any("anchors map absent" in c for c in inner["coverage"]):
        _fail("produce: anchors map was supplied but checker still says 'absent'")
    rec = verdict.emit("iteration-plan", inner, _outer_clean())
    if not rec["process_converged"]:
        _fail(
            f"produce: expected process_converged=True, got False ({rec['inner_ring']}/{rec['outer_ring']})"
        )
    return pm  # reused by the round-trip test


def produce_research_converges():
    r = {
        "claims": [{"text": "X is true.", "source_refs": ["s1"]}],
        "sources": [
            {
                "source_id": "s1",
                "ref": "https://example.org",
                "provenance": "official-spec",
                "fetched": True,
            }
        ],
        "cost_ledger": {
            "budget": {"tokens": 100, "calls": 5, "sources": 3},
            "used": {"tokens": 10, "calls": 1, "sources": 1},
        },
        "staging": {"in_staging": False, "converged": True},
    }
    pm = {
        "plan_model_version": "v1",
        "artifact_type": "research",
        "authority_chain": ["docs/r.md"],
        "items": [
            {"item_id": "r1", "seq": 0, "depends_on": [], "dod_ref": "docs/r.md#r1"}
        ],
        "research": r,
    }
    inner = research_constraints.check(pm)
    inner["profile"] = "research-v1"
    if not inner["passed"]:
        _fail(f"produce-research: research inner should pass, got {inner['failures']}")
    rec = verdict.emit("research", inner, _outer_clean())
    if not rec["process_converged"]:
        _fail("produce-research: expected process_converged=True")
    print("  research produce -> converge (sources/staging/cost clean): PASS")


# --- 2. defect -> fail -> repair -> flip -------------------------------------


def _defect_iteration_plan():
    pm = {
        "plan_model_version": "v1",
        "artifact_type": "iteration-plan",
        "authority_chain": ["docs/arch-design.md"],
        "items": [
            {
                "item_id": "d-1",
                "seq": 0,
                "depends_on": [],
                "dod_ref": "docs/rogue-plan.md#d1",  # (b) authority contradiction
                "odp_status": [
                    {"id": "ODP-X", "kind": "resolve-now"}
                ],  # (c) unresolved resolve-now
            },
        ],
        "anchors": {a: {"present": True} for a in IT_PLAN_ANCHORS if a != "dag"},
    }  # (a) missing anchor
    return pm


def defect_injected_fails_with_correct_flags():
    pm = _defect_iteration_plan()
    res = constraints_check.check(pm)
    if res["passed"]:
        _fail("defect: expected FAIL, got PASS")
    checks = {f.get("check") for f in res["failures"]}
    if "anchor" not in checks:
        _fail(f"defect: missing the anchor failure (dag), got {res['failures']}")
    if not any(f.get("anchor") == "dag" for f in res["failures"]):
        _fail(f"defect: anchor failure must name 'dag', got {res['failures']}")
    if "authority" not in checks:
        _fail(f"defect: missing the authority failure, got {res['failures']}")
    if "odp" not in checks:
        _fail(f"defect: missing the odp failure, got {res['failures']}")
    # the run-record reflects it (outer clean, but inner Blocker => not converged)
    rec = verdict.emit("iteration-plan", res, _outer_clean())
    if rec["process_converged"]:
        _fail("defect: process_converged must be False while inner has Blockers")
    print(
        "  defect fixture -> process_converged=False, 3 named flags (anchor/authority/odp): PASS"
    )


def repair_flips_to_converged():
    pm = _defect_iteration_plan()
    # REPAIR all three defects
    pm["anchors"]["dag"] = {"present": True}  # restore anchor
    pm["items"][0]["dod_ref"] = (
        "docs/arch-design.md#d1"  # point into the authority chain
    )
    pm["items"][0]["odp_status"][0]["resolution"] = (
        "decided: proceed with option B"  # resolve ODP
    )
    res = constraints_check.check(pm)
    if not res["passed"]:
        _fail(f"repair: expected PASS after repair, got {res['failures']}")
    rec = verdict.emit("iteration-plan", res, _outer_clean())
    if not rec["process_converged"]:
        _fail(
            f"repair: process_converged must flip to True, got False ({rec['inner_ring']})"
        )
    print(
        "  repair (restore anchor + fix authority + resolve ODP) -> process_converged=True FLIPPED: PASS"
    )


def research_defect_fails_then_repairs():
    pm = {
        "plan_model_version": "v1",
        "artifact_type": "research",
        "authority_chain": ["docs/r.md"],
        "items": [
            {"item_id": "r1", "seq": 0, "depends_on": [], "dod_ref": "docs/r.md#r1"}
        ],
        "research": {
            "claims": [{"text": "Unsourced claim.", "source_refs": []}],  # defect
            "sources": [],
            "cost_ledger": {
                "budget": {"tokens": 100, "calls": 5, "sources": 3},
                "used": {"tokens": 1, "calls": 1, "sources": 0},
            },
            "staging": {"in_staging": False, "converged": True},
        },
    }
    bad = research_constraints.check(pm)
    if bad["passed"]:
        _fail("research-defect: expected sources-cited Blocker")
    # repair: cite a fetched source
    pm["research"]["sources"] = [
        {
            "source_id": "s1",
            "ref": "https://example.org",
            "provenance": "peer-reviewed",
            "fetched": True,
        }
    ]
    pm["research"]["claims"][0]["source_refs"] = ["s1"]
    good = research_constraints.check(pm)
    if not good["passed"]:
        _fail(f"research-repair: expected PASS, got {good['failures']}")
    print(
        "  research defect (unsourced) -> fail -> repair (cite fetched source) -> pass: PASS"
    )


# --- 3. round-trip of the produced plan-model --------------------------------


def produced_plan_model_round_trips(produced_pm):
    queue_items = pmm.project_plan_model_to_queue(produced_pm)
    lifted = [pmm.lift_queue_item(qi) for qi in queue_items]
    # executable subset must be lossless
    pmm.assert_executable_lossless("e2e produce", produced_pm["items"], lifted)
    # and the lifted items are individually schema-valid (no stray tags)
    for it in lifted:
        errs = validate_plan_model(
            {
                "plan_model_version": "v1",
                "artifact_type": "iteration-plan",
                "authority_chain": produced_pm["authority_chain"],
                "items": [it],
            }
        )
        if errs:
            _fail(f"round-trip: lifted item not schema-valid: {errs}")
    print(
        "  produced plan-model round-trips losslessly on the executable subset (ADR #1): PASS"
    )


def main():
    print("end_to_end (I7):")
    failures = []
    try:
        produced = produce_iteration_plan_converges()
        print(
            "  iteration-plan produce (normalize -> author anchors -> check -> verdict): PASS"
        )
    except AssertionError as e:
        failures.append(str(e))
        print(f"  produce_iteration_plan_converges: FAIL — {e}")
        produced = None
    for fn in (
        produce_research_converges,
        defect_injected_fails_with_correct_flags,
        repair_flips_to_converged,
        research_defect_fails_then_repairs,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
    if produced is not None:
        try:
            produced_plan_model_round_trips(produced)
        except AssertionError as e:
            failures.append(str(e))
            print(f"  produced_plan_model_round_trips: FAIL — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nEnd-to-end: produce converges; defect-injected fails with named flags; repair flips to true; produced plan-model round-trips. Process-axis acceptance gate met."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
