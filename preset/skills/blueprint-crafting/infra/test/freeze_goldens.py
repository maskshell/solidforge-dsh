#!/usr/bin/env python3
"""freeze_goldens — the freeze operator (Unit 3): a plan-model freezes to a
.queue.md that plan_queue.py-format parsing reads back, AND a .run-record.json
that conforms to run-record.schema.json. Composes project_plan_model_to_queue +
verdict.emit (inner-only); the outer ring is an LLM eval and is not run
(coverage-noted — ADR #10).

Run: python3 infra/test/freeze_goldens.py
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # plan_model_schema, run_record_schema
sys.path.insert(
    0, os.path.normpath(os.path.join(HERE, "..", "scripts"))
)  # freeze, plan_model

import freeze  # noqa: E402
import plan_model as pm  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402
from run_record_schema import validate as validate_run_record  # noqa: E402

GOLDEN_PM = os.path.join(HERE, "golden", "plan-model.golden.json")


def _fail(msg):
    raise AssertionError(msg)


def check_freeze_emits_both_artifacts():
    with open(GOLDEN_PM, encoding="utf-8") as fh:
        plan_model = json.load(fh)
    errs = validate_plan_model(plan_model)
    if errs:
        _fail(f"golden plan-model invalid: {errs}")
    with tempfile.TemporaryDirectory() as td:
        q, r, res = freeze.freeze(
            plan_model, td, name="frozen-golden", frozen_at="2026-06-26"
        )
        # .queue.md exists + is plan_queue.py-format (```json block under ## Items)
        if not os.path.exists(q):
            _fail(f"freeze did not write .queue.md: {q}")
        text = open(q, encoding="utf-8").read()
        if "## Items" not in text:
            _fail("queue.md missing the ## Items section plan_queue.py expects")
        if "status: frozen" not in text:
            _fail("queue.md frontmatter missing 'status: frozen'")
        # the items in the ```json block round-trip the golden's item_ids
        items = pm.parse_queue_items(text)
        golden_ids = {it["item_id"] for it in plan_model["items"]}
        frozen_ids = {it["item_id"] for it in items}
        if golden_ids != frozen_ids:
            _fail(
                f"freeze queue item_ids diverged from the plan-model: {golden_ids} vs {frozen_ids}"
            )
        # rich-path-design D2: every emitted item carries the producer marker so pd
        # can detect blueprint-crafting origin (fail-safe to the free path if absent).
        for it in items:
            if it.get("producer") != "blueprint-crafting":
                _fail(
                    f"frozen item {it.get('item_id')} missing the producer marker: "
                    f"producer={it.get('producer')!r}"
                )
        # .run-record.json exists + conforms + carries the rightness constant
        if not os.path.exists(r):
            _fail(f"freeze did not write .run-record.json: {r}")
        rec = json.load(open(r, encoding="utf-8"))
        rerrs = validate_run_record(rec)
        if rerrs:
            _fail(f"emitted run-record violates schema: {rerrs}")
        if rec.get("rightness") != "human_confirm_required":
            _fail(
                f"run-record rightness must be the constant human_confirm_required: {rec.get('rightness')}"
            )
        if "process_converged" not in rec:
            _fail("run-record missing process_converged")
        # outer ring is an LLM eval -> not run in CLI -> process_converged is False,
        # honestly coverage-noted (not a silent green).
        if rec.get("process_converged") is not False:
            _fail(
                "process_converged must be False when the outer ring did not run "
                f"(got {rec.get('process_converged')})"
            )
        if not any("outer ring" in c for c in rec.get("coverage", [])):
            _fail(
                f"run-record must coverage-note the outer ring did not run: {rec.get('coverage')}"
            )
        # the iteration-plan golden carries no research -> no .research.json
        if res is not None:
            _fail(f"iteration-plan golden must not emit a .research.json: {res}")
    print(
        "  freeze emits a pd-parseable .queue.md + a schema-valid .run-record.json: PASS"
    )


def check_freeze_emits_research():
    """charter R5 (research->inform): freeze emits the research payload (claims +
    sources) as a sibling .research.json when the plan-model carries research, so
    pd can surface the rationale to the Coder. cost_ledger/staging are NOT emitted
    (bc-internal convergence detail)."""
    research_pm = {
        "plan_model_version": "v1",
        "artifact_type": "research",
        "authority_chain": ["docs/spec.md"],
        "items": [
            {"item_id": "r1", "seq": 0, "depends_on": [], "dod_ref": "docs/r.md#r1"}
        ],
        "research": {
            "claims": [
                {"text": "Library X supports feature Y.", "source_refs": ["s1"]}
            ],
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
        },
    }
    with tempfile.TemporaryDirectory() as td:
        q, r, res = freeze.freeze(research_pm, td, name="frozen-research")
        if res is None:
            _fail("research plan-model must emit a .research.json (got None)")
        if not os.path.exists(res):
            _fail(f"freeze did not write .research.json: {res}")
        payload = json.load(open(res, encoding="utf-8"))
        if payload.get("claims") != research_pm["research"]["claims"]:
            _fail(f".research.json claims diverged: {payload.get('claims')}")
        if payload.get("sources") != research_pm["research"]["sources"]:
            _fail(f".research.json sources diverged: {payload.get('sources')}")
        if "cost_ledger" in payload or "staging" in payload:
            _fail(
                f".research.json must NOT carry bc-internal cost_ledger/staging: {list(payload)}"
            )
    print("  freeze emits .research.json (claims + sources; no bc internals): PASS")


def main():
    print("freeze_goldens (Unit 3 + R5 research):")
    failures = []
    for fn in (check_freeze_emits_both_artifacts, check_freeze_emits_research):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nfreeze: .queue.md (pd-parseable) + .run-record.json (schema-valid) emitted."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
