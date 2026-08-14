#!/usr/bin/env python3
"""PSV-I5(b) -- findings + coverage-record shape-contract gate.

Asserts every coverage_driver emit path produces objects satisfying the two
schema contracts (structural validation, stdlib-only -- no jsonschema dep):
  - doc-findings: outcome_axis_respected (bool) + findings[]; each finding has
    defect_id/severity/kind/location/evidence; kind/severity in the psv enums.
  - coverage-record: artifact/signal/counts/rightness/escalations present;
    counts has the 5 fields; signal == oracle_verified_under_known_coverage.

Mirrors csr's findings_shape_check / pd's adapter_shape_check (rule 7).
Self-contained; exits 0 on green. Run: python3 infra/test/findings_shape_check.py
"""

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

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
}
_SEV = {"blocker", "warning", "coverage"}
_COUNT_FIELDS = {"verified", "refuted", "narrowed", "unverifiable", "total_extracted"}


def _check_finding(f: dict, failures: list) -> None:
    for field in ("defect_id", "severity", "kind", "location", "evidence"):
        if not f.get(field):
            failures.append(f"finding missing {field}: {f}")
    if f.get("kind") not in _KINDS:
        failures.append(f"finding kind not in enum: {f.get('kind')}")
    if f.get("severity") not in _SEV:
        failures.append(f"finding severity not in enum: {f.get('severity')}")


def _validate(
    coverage_record: dict, doc_findings: dict, label: str, failures: list
) -> None:
    # doc-findings
    if doc_findings.get("outcome_axis_respected") is not True:
        failures.append(f"{label}: outcome_axis_respected not true")
    if not isinstance(doc_findings.get("findings"), list):
        failures.append(f"{label}: findings not a list")
    for f in doc_findings["findings"]:
        _check_finding(f, failures)
    # coverage-record
    for field in ("artifact", "signal", "counts", "rightness", "escalations"):
        if field not in coverage_record:
            failures.append(f"{label}: coverage-record missing {field}")
    if coverage_record.get("signal") != "oracle_verified_under_known_coverage":
        failures.append(f"{label}: signal wrong")
    if coverage_record.get("rightness") != "human_confirm_required":
        failures.append(f"{label}: rightness wrong")
    if set(coverage_record.get("counts", {})) != _COUNT_FIELDS:
        failures.append(
            f"{label}: counts fields wrong: {set(coverage_record.get('counts', {}))}"
        )
    if not isinstance(coverage_record.get("escalations"), list):
        failures.append(f"{label}: escalations not a list")
    # volatile-authority registry (fix B): when present, every entry is
    # {claim_ref, volatile_source} — the re-fetchability signal for claims
    # adjudicated against repo-external / unversioned sources.
    reg = coverage_record.get("volatile_authority_registry")
    if reg is not None:
        if not isinstance(reg, list):
            failures.append(f"{label}: volatile_authority_registry not a list")
        else:
            for entry in reg:
                if not isinstance(entry, dict):
                    failures.append(f"{label}: registry entry not an object: {entry}")
                    continue
                for field in ("claim_ref", "volatile_source"):
                    if not isinstance(entry.get(field), str) or not entry.get(field):
                        failures.append(
                            f"{label}: registry entry missing {field}: {entry}"
                        )


def main() -> int:
    failures: list[str] = []

    # fixture A: mixed verdicts
    cr, df = build_coverage(
        [
            {"claim_id": "C1", "verdict": "verified"},
            {
                "claim_id": "C2",
                "verdict": "refuted",
                "finding": {
                    "defect_id": "c2",
                    "severity": "blocker",
                    "kind": "claim-refuted",
                    "location": "s1",
                    "evidence": 'src: "q"',
                },
            },
            {
                "claim_id": "C3",
                "verdict": "unverifiable",
                "finding": {
                    "defect_id": "c3",
                    "severity": "coverage",
                    "kind": "claim-unverifiable",
                    "location": "s2",
                    "evidence": "paywalled",
                },
            },
        ],
        "doc.md",
    )
    _validate(cr, df, "fixture-A", failures)

    # fixture B: empty (M=0)
    cr, df = build_coverage([], "empty.md")
    _validate(cr, df, "fixture-B-empty", failures)

    # fixture C: volatile-authority registry (fix B)
    cr, df = build_coverage(
        [
            {"claim_id": "C1", "verdict": "verified"},
            {
                "claim_id": "C2",
                "verdict": "narrowed",
                "finding": {
                    "defect_id": "c2",
                    "severity": "warning",
                    "kind": "claim-narrowed",
                    "location": "s1",
                    "evidence": 'src: "q"',
                },
            },
        ],
        "volatile.md",
    )
    cr["volatile_authority_registry"] = [
        {
            "claim_ref": "C1",
            "volatile_source": "~/.dsh/sessions/-memory/project-x.md",
        },
        {"claim_ref": "C2", "volatile_source": "/tmp/clone (shallow)"},
    ]
    _validate(cr, df, "fixture-C-volatile-registry", failures)
    # negative: malformed registry entry must fail the shape gate (asserted on
    # a SEPARATE failures list — the expected negative is not a gate failure).
    bad = dict(cr)
    bad["volatile_authority_registry"] = [{"claim_ref": "C1"}]  # missing source
    bad_failures: list[str] = []
    _validate(bad, df, "fixture-C-bad-registry", bad_failures)
    if "fixture-C-bad-registry: registry entry missing volatile_source" not in (
        " ".join(bad_failures)
    ):
        failures.append("fixture-C-bad-registry: malformed registry entry NOT flagged")

    if failures:
        print("FAIL: findings shape-contract gate")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS: findings + coverage-record shape-contract gate (PSV-I5b)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
