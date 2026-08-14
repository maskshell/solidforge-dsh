#!/usr/bin/env python3
"""plan_reviewer precision self-check (iteration I5).

The plan_reviewer is the OUTER RING — an adversarial LLM agent. Its precision ("does it hit the CORRECT planted defect, not any defect, and not a guess") is therefore an EVAL, not a deterministic compile (workspace rule 4: heuristics/ LLM judgments are advisory, never a deterministic Blocker). This mirrors agent-crafter's own split: validate_agent.py (deterministic) vs evaluate_agent.py (LLM, optional). See design-decisions.md ADR #10.

So this script has TWO layers:

  1. DETERMINISTIC GATE (runs in the gate suite; must pass) — validates the scaffolding that makes a precision eval meaningful:
       - each fixture's plan-model conforms to plan-model.schema.json (so the planted defect is SEMANTIC, not structural — the inner ring would not catch it; that is precisely the outer ring's job);
       - each defect.json declares id/kind/severity/location/ground_truth;
       - GROUND TRUTH: the planted defect's markers are actually present in the fixture's plan-model (the fixture is honest — the defect is really there, where expected_findings says);
       - each expected_findings.json conforms to review-findings.schema.json;
       - PRECISION TARGET: expected_findings references the planted defect_id with the correct severity + kind.

  2. PRECISION ASSERTION (deterministic GIVEN a reviewer's output) — assert_precision(reviewer_output, fixture). The convergence loop spawns the plan_reviewer agent on a fixture, captures its JSON, then calls this to check it hit the correct defect (defect_id / severity / kind / location) and respected the outcome axis. The LLM spawn is the non-deterministic part; this check is fully deterministic once the output exists. CLI:
         python3 plan_reviewer_precision.py --check-output <findings.json> <fixture>

Run the gate:

    python3 infra/test/plan_reviewer_precision.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # within-skill reuse of the stdlib validator
from plan_model_schema import _validate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMAS = os.path.join(ROOT, "infra", "schemas")
FIXTURES_DIR = os.path.join(HERE, "golden", "plan_reviewer")

PLAN_MODEL_SCHEMA = os.path.join(SCHEMAS, "plan-model.schema.json")
FINDINGS_SCHEMA = os.path.join(SCHEMAS, "review-findings.schema.json")

FIXTURES = [
    "fixture-01-contradiction",
    "fixture-02-over-engineering",
    "fixture-03-unfalsifiable-dod",
]


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_schema(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_against(obj, schema_path):
    """Stdlib JSON-Schema validation (reuses plan_model_schema._validate)."""
    schema = load_schema(schema_path)
    return _validate(obj, schema, schema.get("$defs", {}), "$")


def _flatten_markers(ground_truth):
    """All substring markers declared in a defect's ground_truth (strings + list members), each of which must appear somewhere in the fixture's plan-model."""
    out = []
    for v in ground_truth.values():
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            out.extend(s for s in v if isinstance(s, str))
    return out


def _item_scope_text(plan_model):
    """Concatenation of every item's scope (lowercased) — the search corpus for ground-truth markers. Defects are planted in item.scope (upstream_only, free text) so the reviewer reads them there."""
    return " \n ".join(
        str(it.get("scope", "")) for it in plan_model.get("items", [])
    ).lower()


def validate_fixture(name):
    """Layer 1: deterministic scaffolding validation for one fixture. Raises AssertionError with an actionable message on any failure."""
    d = os.path.join(FIXTURES_DIR, name)
    pm = load_json(os.path.join(d, "plan-model.json"))
    defect = load_json(os.path.join(d, "defect.json"))
    expected = load_json(os.path.join(d, "expected_findings.json"))

    # 1. plan-model is schema-valid -> the defect is semantic, not structural
    errs = validate_against(pm, PLAN_MODEL_SCHEMA)
    if errs:
        raise AssertionError(f"{name}: plan-model violates schema: {errs}")

    # 2. defect spec is well-formed
    for f in ("id", "kind", "severity", "location", "description", "ground_truth"):
        if f not in defect:
            raise AssertionError(f"{name}: defect.json missing field '{f}'")
    for f in ("severity", "kind"):
        valid = {
            "severity": ("blocker", "warning", "coverage"),
            "kind": ("gap", "over-engineering", "contradiction", "blind-spot"),
        }[f]
        if defect[f] not in valid:
            raise AssertionError(f"{name}: defect.{f}={defect[f]!r} not in {valid}")

    # 3. GROUND TRUTH: the planted defect's markers are actually in the plan-model
    corpus = _item_scope_text(pm)
    missing = [
        m for m in _flatten_markers(defect["ground_truth"]) if m.lower() not in corpus
    ]
    if missing:
        raise AssertionError(
            f"{name}: ground-truth markers not present in plan-model item scopes: {missing} "
            f"-> the fixture does not actually plant the defect it claims (dishonest fixture)"
        )

    # 4. expected_findings conforms to the findings schema
    errs = validate_against(expected, FINDINGS_SCHEMA)
    if errs:
        raise AssertionError(f"{name}: expected_findings violates schema: {errs}")

    # 5. PRECISION TARGET: expected_findings hits the planted defect precisely
    hits = [f for f in expected["findings"] if f["defect_id"] == defect["id"]]
    if not hits:
        raise AssertionError(
            f"{name}: expected_findings has no finding with defect_id={defect['id']!r} "
            f"(the precision target must reference the planted defect)"
        )
    hit = hits[0]
    if hit["severity"] != defect["severity"] or hit["kind"] != defect["kind"]:
        raise AssertionError(
            f"{name}: expected finding severity/kind "
            f"({hit['severity']}/{hit['kind']}) != defect ({defect['severity']}/{defect['kind']})"
        )
    if expected.get("outcome_axis_respected") is not True:
        raise AssertionError(
            f"{name}: expected_findings.outcome_axis_respected must be true"
        )


def assert_precision(reviewer_output, fixture_name):
    """Layer 2: deterministic precision check GIVEN a reviewer's JSON output. Returns (ok, message). The LLM spawn is non-deterministic; this check is not.

    A PRECISE review: finds a finding that corresponds to the planted defect (matched by location — the item(s) the defect lives in — OR by a direct defect_id hit in the non-blind case), at the planted severity + kind, and respects the outcome axis.
    A blind reviewer uses defect_id 'novel-N' (it cannot know the planted ids), so defect_id is informational, not the match key; location + severity + kind are the substantive precision signal.
    """
    errs = validate_against(reviewer_output, FINDINGS_SCHEMA)
    if errs:
        return False, f"reviewer output violates findings schema: {errs}"
    defect = load_json(os.path.join(FIXTURES_DIR, fixture_name, "defect.json"))
    if reviewer_output.get("outcome_axis_respected") is not True:
        return False, "reviewer judged the outcome axis (out of bounds)"
    findings = reviewer_output.get("findings", [])
    # direct defect_id hit (non-blind case, e.g. expected_findings)
    by_id = [f for f in findings if f.get("defect_id") == defect["id"]]
    # blind hit: finding whose location/evidence references the planted defect's item(s)
    item_ids = [
        w.split(".")[0] for w in defect["location"].lower().replace(" vs ", " ").split()
    ]
    item_ids = [i for i in item_ids if i and not i.startswith(("docs/", "http"))]

    def _refs_item(f):
        hay = (f.get("location", "") + " " + f.get("evidence", "")).lower()
        return any(iid in hay for iid in item_ids)

    by_loc = [f for f in findings if item_ids and _refs_item(f)]
    candidates = by_id or by_loc
    if not candidates:
        return False, (
            f"missed the planted defect {defect['id']!r} at items {item_ids}; "
            f"found defect_ids={[f.get('defect_id') for f in findings]}"
        )
    # among the candidates, at least one must classify correctly (severity + kind)
    for hit in candidates:
        if hit["severity"] == defect["severity"] and hit["kind"] == defect["kind"]:
            return True, (
                f"precise hit on {defect['id']} ({defect['severity']}/{defect['kind']}) "
                f"[matched defect_id={hit.get('defect_id')!r}]"
            )
    sev_kinds = [f"{f['severity']}/{f['kind']}" for f in candidates]
    return False, (
        f"found the defect location but misclassified: got {sev_kinds}, "
        f"expected {defect['severity']}/{defect['kind']}"
    )


def main():
    # CLI: check a saved reviewer output against a fixture (Layer 2)
    if len(sys.argv) >= 4 and sys.argv[1] == "--check-output":
        findings_path, fixture = sys.argv[2], sys.argv[3]
        if fixture not in FIXTURES:
            sys.exit(f"unknown fixture {fixture!r}; choose from {FIXTURES}")
        ok, msg = assert_precision(load_json(findings_path), fixture)
        print(("PRECISE: " if ok else "IMPRECISE: ") + msg)
        sys.exit(0 if ok else 1)

    # Layer 1: deterministic gate
    print("plan_reviewer_precision (I5):")
    failures = []
    for name in FIXTURES:
        try:
            validate_fixture(name)
            print(
                f"  {name}: fixture valid, ground-truth present, precision target sound — PASS"
            )
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {name}: FAIL — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)

    print(f"\n{len(FIXTURES)} fixtures are eval-ready (scaffolding valid).")
    print("PRECISION EVAL (non-deterministic, LLM — NOT a gate; rule 4 / ADR #10):")
    print(
        "  spawn the plan_reviewer agent on each fixture's plan-model.json, capture its JSON,"
    )
    print(
        "  then:  python3 plan_reviewer_precision.py --check-output <findings.json> <fixture>"
    )
    print("  A PRECISE review hits the planted defect_id at the planted severity/kind.")
    sys.exit(0)


if __name__ == "__main__":
    main()
