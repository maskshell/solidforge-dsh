#!/usr/bin/env python3
"""research-constraints goldens self-check (iteration I4).

Asserts the I4 DoD (iteration-plan §4) for the research v1 profile (ADR #7):
  - a fedaot-kb-style research golden PASSES (claims sourced+fetched, staged after convergence, cost within budget, provenance tagged);
  - an UNSOURCED claim -> Blocker (sources-cited);
  - research FROZEN WITHOUT convergence -> Blocker (staging-via-convergence);
  - cost EXCEEDED -> Blocker (cost-bounded);
  - provenance UNKNOWN -> warning, NOT a Blocker (rule 4: advisory);
  - a non-research artifact degrades to a coverage note (dispatched to I3).

All fixtures are schema-valid (plan-model.schema.json). Run:

    python3 infra/test/research_constraints_goldens.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))

import research_constraints  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402

GOLDEN = os.path.join(HERE, "golden", "research")


def _load(name):
    with open(os.path.join(GOLDEN, name), encoding="utf-8") as fh:
        return json.load(fh)


def _fail(msg):
    raise AssertionError(msg)


def _schema_ok(name):
    errs = validate_plan_model(_load(name))
    if errs:
        _fail(f"{name}: not schema-valid: {errs}")


def check_golden_passes():
    name = "golden-fedaot-research.json"
    _schema_ok(name)
    res = research_constraints.check(_load(name))
    if not res["passed"]:
        _fail(f"golden: expected PASS, got failures {res['failures']}")
    print(
        "  fedaot-kb research golden passes v1 (sourced + staged-after-convergence + cost-ok + provenance): PASS"
    )


def check_unsourced_blocks():
    name = "negative-unsourced-claim.json"
    _schema_ok(name)
    res = research_constraints.check(_load(name))
    if res["passed"]:
        _fail("unsourced: expected FAIL, got PASS")
    if not any(
        f.get("check") == "sources-cited" and f.get("severity") == "blocker"
        for f in res["failures"]
    ):
        _fail(f"unsourced: expected a sources-cited blocker, got {res['failures']}")
    print("  unsourced claim -> sources-cited Blocker: PASS")


def check_frozen_without_convergence_blocks():
    name = "negative-frozen-without-convergence.json"
    _schema_ok(name)
    res = research_constraints.check(_load(name))
    if res["passed"]:
        _fail("frozen-without-convergence: expected FAIL, got PASS")
    if not any(f.get("check") == "staging-via-convergence" for f in res["failures"]):
        _fail(
            f"frozen: expected staging-via-convergence failure, got {res['failures']}"
        )
    print("  frozen-without-convergence -> staging-via-convergence Blocker: PASS")


def check_cost_exceeded_blocks():
    name = "negative-cost-exceeded.json"
    _schema_ok(name)
    res = research_constraints.check(_load(name))
    if res["passed"]:
        _fail("cost-exceeded: expected FAIL, got PASS")
    cb = [f for f in res["failures"] if f.get("check") == "cost-bounded"]
    if not cb or not any(f.get("axis") == "tokens" for f in cb):
        _fail(
            f"cost-exceeded: expected cost-bounded/tokens failure, got {res['failures']}"
        )
    print("  cost exceeded -> cost-bounded Blocker (axis=tokens): PASS")


def check_provenance_is_warning_not_blocker():
    name = "provenance-unknown-warning.json"
    _schema_ok(name)
    res = research_constraints.check(_load(name))
    # provenance unknown must be a WARNING, and the artifact must still PASS (rule 4)
    if not res["passed"]:
        _fail(
            f"provenance-unknown: should still PASS (warning only), got failures {res['failures']}"
        )
    if not any(w.get("check") == "provenance-tag" for w in res["warnings"]):
        _fail(
            f"provenance-unknown: expected a provenance-tag warning, got warnings {res['warnings']}"
        )
    print(
        "  provenance unknown -> warning (not Blocker); artifact still passes (rule 4): PASS"
    )


def check_non_research_degrades():
    pm = {
        "plan_model_version": "v1",
        "artifact_type": "iteration-plan",
        "authority_chain": ["docs/x.md"],
        "items": [
            {"item_id": "x", "seq": 0, "depends_on": [], "dod_ref": "docs/x.md#x"}
        ],
    }
    res = research_constraints.check(pm)
    if not res["passed"] or not res["coverage"]:
        _fail(f"non-research: should degrade (pass + coverage note), got {res}")
    print("  non-research artifact degrades to coverage (dispatched to I3): PASS")


def main():
    print("research_constraints_goldens (I4):")
    failures = []
    for fn in (
        check_golden_passes,
        check_unsourced_blocks,
        check_frozen_without_convergence_blocks,
        check_cost_exceeded_blocks,
        check_provenance_is_warning_not_blocker,
        check_non_research_degrades,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nresearch v1 subset enforced: sources-cited/staging/cost = Blocker, provenance = warning (ADR #7). Idempotency + full trust-tier deferred; fedaot-kb purity dropped."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
