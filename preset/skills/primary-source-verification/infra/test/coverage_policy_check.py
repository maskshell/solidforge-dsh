#!/usr/bin/env python3
"""PSV-I5(c) -- offline coverage-policy gate.

Asserts the deterministic policy invariants on coverage_driver output:
  - counts sum: total_extracted == verified + refuted + narrowed + unverifiable.
  - M=0 (no admissible claims) -> exactly one escalation 'no surface'.
  - K>0 -> one escalation per unverifiable claim.
  - the forbidden term 'correctness_converged' NEVER appears in any emitted
    object (rule 3 + proposal §9 Q3).
  - signal is always oracle_verified_under_known_coverage.

Mirrors csr's convergence_policy_check (offline, no network). Self-contained;
exits 0 on green. Run: python3 infra/test/coverage_policy_check.py
"""

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

FORBIDDEN = "correctness_converged"


def _f(claim_id: str, verdict: str, quote: bool = True) -> dict:
    ev = 'src "q"' if quote else ""
    return {
        "claim_id": claim_id,
        "verdict": verdict,
        "finding": {
            "defect_id": claim_id,
            "severity": "coverage",
            "kind": f"claim-{verdict}",
            "location": "s",
            "evidence": ev,
        },
    }


def _sums_ok(counts: dict) -> bool:
    return counts["total_extracted"] == (
        counts["verified"]
        + counts["refuted"]
        + counts["narrowed"]
        + counts["unverifiable"]
    )


def _no_forbidden(obj: dict) -> bool:
    return FORBIDDEN not in json.dumps(obj)


def main() -> int:
    failures: list[str] = []

    # 1. M=0 -> exactly one 'no surface' escalation
    cr, df = build_coverage([], "empty.md")
    if not _sums_ok(cr["counts"]) or cr["counts"]["total_extracted"] != 0:
        failures.append("M=0: counts not summing to 0")
    no_surface = [e for e in cr["escalations"] if "no surface" in e["reason"]]
    if len(no_surface) != 1:
        failures.append(
            f"M=0: expected 1 'no surface' escalation, got {len(no_surface)}"
        )

    # 2. K>0 -> one escalation per unverifiable claim; no 'no surface' (M>0)
    cr, df = build_coverage(
        [_f("C1", "unverifiable"), _f("C2", "unverifiable"), _f("C3", "verified")],
        "d.md",
    )
    k_esc = [e for e in cr["escalations"] if e.get("claim_ref")]
    if len(k_esc) != 2:
        failures.append(f"K=2: expected 2 claim escalations, got {len(k_esc)}")
    if not _sums_ok(cr["counts"]):
        failures.append("K>0: counts don't sum")

    # 3. mixed; sums; forbidden term absent everywhere
    cr, df = build_coverage(
        [
            _f("C1", "verified"),
            _f("C2", "refuted"),
            _f("C3", "narrowed"),
            _f("C4", "unverifiable"),
        ],
        "d.md",
    )
    if not _sums_ok(cr["counts"]):
        failures.append("mixed: counts don't sum")
    if cr["counts"]["total_extracted"] != 4:
        failures.append("mixed: M != 4")
    if not _no_forbidden(cr) or not _no_forbidden(df):
        failures.append("forbidden term 'correctness_converged' appeared")
    if cr["signal"] != "oracle_verified_under_known_coverage":
        failures.append("signal wrong")

    # 4. unrecognized verdict value -> sum invariant FAILS (total=len, not bucket
    #    sum) + a data-integrity escalation fires. This makes _sums_ok a REAL
    #    check, not a tautology (outer-ring W3).
    cr, df = build_coverage(
        [
            {"claim_id": "C1", "verdict": "VERIFIED-typo"},
            {
                "claim_id": "C2",
                "verdict": "refuted",
                "finding": {
                    "defect_id": "c2",
                    "severity": "blocker",
                    "kind": "claim-refuted",
                    "location": "s",
                    "evidence": 'src "q"',
                },
            },
        ],
        "d.md",
    )
    if _sums_ok(cr["counts"]):
        failures.append(
            "unrecognized verdict: sum invariant should FAIL (total != N+R+W+K)"
        )
    if cr["counts"]["total_extracted"] != 2:
        failures.append(
            f"unrecognized verdict: total should be 2 (len), got {cr['counts']['total_extracted']}"
        )
    if not any("data integrity" in e["reason"] for e in cr["escalations"]):
        failures.append("unrecognized verdict: no data-integrity escalation")

    if failures:
        print("FAIL: coverage-policy gate")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: coverage-policy gate (PSV-I5c) -- sums, M=0/K>0 escalation, no correctness_converged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
