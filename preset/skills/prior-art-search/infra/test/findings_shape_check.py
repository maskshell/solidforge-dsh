#!/usr/bin/env python3
"""NC-I5(b) -- collision-findings + collision-record shape-contract gate.

Asserts every coverage_driver emit path produces objects satisfying the two schema
contracts (structural validation, stdlib-only -- no jsonschema dep):
  - collision-findings: outcome_axis_respected (bool) + findings[]; each finding has
    defect_id/severity/kind/location/evidence; kind/severity in the prior-art-search
    enums (12 kinds = psv's 9 + 3 collision kinds).
  - collision-record: artifact/signal/counts/rightness/escalations present; counts has
    the 5 fields (clear_under_search/collisions/uncited_relevant/inconclusive/
    total_extracted); signal == collisions_under_known_coverage.

Mirrors primary-source-verification's findings_shape_check.py (rule 7), adapted to the
collision contracts. Self-contained; exits 0 on green. Run: python3 infra/test/findings_shape_check.py
"""

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

# psv's 9 kinds (preserved byte-for-byte) + prior-art-search's 3 collision kinds.
_KINDS = {
    "contradiction",
    "authority-chain-break",
    "scope-creep",
    "structural-gap",
    "citation-error",
    "coverage-gap",
    "claim-refuted",
    "claim-narrowed",
    "claim-unverifiable",
    "claim-collision",
    "claim-uncited-relevant",
    "claim-inconclusive",
}
_SEV = {"blocker", "warning", "coverage"}
_COUNT_FIELDS = {
    "clear_under_search",
    "collisions",
    "uncited_relevant",
    "inconclusive",
    "total_extracted",
}


def _check_finding(f: dict, failures: list) -> None:
    for field in ("defect_id", "severity", "kind", "location", "evidence"):
        if not f.get(field):
            failures.append(f"finding missing {field}: {f}")
    if f.get("kind") not in _KINDS:
        failures.append(f"finding kind not in enum: {f.get('kind')}")
    if f.get("severity") not in _SEV:
        failures.append(f"finding severity not in enum: {f.get('severity')}")


def _validate(
    collision_record: dict, collision_findings: dict, label: str, failures: list
) -> None:
    # collision-findings
    if collision_findings.get("outcome_axis_respected") is not True:
        failures.append(f"{label}: outcome_axis_respected not true")
    if not isinstance(collision_findings.get("findings"), list):
        failures.append(f"{label}: findings not a list")
    for f in collision_findings["findings"]:
        _check_finding(f, failures)
    # collision-record
    for field in ("artifact", "signal", "counts", "rightness", "escalations"):
        if field not in collision_record:
            failures.append(f"{label}: collision-record missing {field}")
    if collision_record.get("signal") != "collisions_under_known_coverage":
        failures.append(f"{label}: signal wrong")
    if collision_record.get("rightness") != "human_confirm_required":
        failures.append(f"{label}: rightness wrong")
    if set(collision_record.get("counts", {})) != _COUNT_FIELDS:
        failures.append(
            f"{label}: counts fields wrong: {set(collision_record.get('counts', {}))}"
        )
    if not isinstance(collision_record.get("escalations"), list):
        failures.append(f"{label}: escalations not a list")


def main() -> int:
    failures: list[str] = []

    # fixture A: mixed verdicts (collision+quote, clear-under-search, inconclusive)
    cr, cf = build_coverage(
        [
            {"claim_id": "NC1", "verdict": "clear-under-search"},
            {
                "claim_id": "NC2",
                "verdict": "collision",
                "finding": {
                    "defect_id": "nc2",
                    "severity": "blocker",
                    "kind": "claim-collision",
                    "location": "s1",
                    "evidence": 'prior art: "we introduce C"',
                },
            },
            {
                "claim_id": "NC3",
                "verdict": "inconclusive",
                "finding": {
                    "defect_id": "nc3",
                    "severity": "coverage",
                    "kind": "claim-inconclusive",
                    "location": "s2",
                    "evidence": "search could not cover",
                },
            },
            {
                # exercises claim-uncited-relevant kind + warning severity through
                # _check_finding (outer-ring coverage note: previously unexercised)
                "claim_id": "NC4",
                "verdict": "uncited-relevant",
                "finding": {
                    "defect_id": "nc4",
                    "severity": "warning",
                    "kind": "claim-uncited-relevant",
                    "location": "s3",
                    "evidence": 'fetched: Lee "surveys D" uncited here',
                },
            },
        ],
        "doc.md",
    )
    _validate(cr, cf, "fixture-A", failures)

    # fixture B: empty (M=0)
    cr, cf = build_coverage([], "empty.md")
    _validate(cr, cf, "fixture-B-empty", failures)

    if failures:
        print("FAIL: collision-findings shape-contract gate")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS: collision-findings + collision-record shape-contract gate (NC-I5b)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
