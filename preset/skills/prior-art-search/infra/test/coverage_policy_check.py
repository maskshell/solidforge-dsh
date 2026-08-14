#!/usr/bin/env python3
"""NC-I5(c) -- offline coverage-policy gate.

Asserts the deterministic policy invariants on coverage_driver output:
  - counts sum: total_extracted == clear_under_search + collisions + uncited_relevant
    + inconclusive  (M = C + N + U + I).
  - M=0 (no extractable novelty claims) -> exactly one escalation 'no novelty surface'.
  - I>0 -> one escalation per inconclusive claim.
  - the forbidden term 'novel_confirmed' NEVER appears in any emitted object
    (rule 3 + proposal §8 Q3).
  - signal is always collisions_under_known_coverage.

Mirrors primary-source-verification's coverage_policy_check.py (rule 7), adapted to the
collision verdict set. Self-contained (no network); exits 0 on green.
Run: python3 infra/test/coverage_policy_check.py
"""

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

FORBIDDEN = "novel_confirmed"


def _f(claim_id: str, verdict: str, quote: bool = True) -> dict:
    ev = 'prior art "q"' if quote else ""
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
        counts["clear_under_search"]
        + counts["collisions"]
        + counts["uncited_relevant"]
        + counts["inconclusive"]
    )


def _no_forbidden(obj: dict) -> bool:
    return FORBIDDEN not in json.dumps(obj)


def main() -> int:
    failures: list[str] = []

    # 1. M=0 -> exactly one 'no novelty surface' escalation
    cr, cf = build_coverage([], "empty.md")
    if not _sums_ok(cr["counts"]) or cr["counts"]["total_extracted"] != 0:
        failures.append("M=0: counts not summing to 0")
    no_surface = [e for e in cr["escalations"] if "no novelty surface" in e["reason"]]
    if len(no_surface) != 1:
        failures.append(
            f"M=0: expected 1 'no novelty surface' escalation, got {len(no_surface)}"
        )
    if not _no_forbidden(cr) or not _no_forbidden(cf):
        failures.append("M=0: forbidden term 'novel_confirmed' appeared")

    # 2. I>0 -> one escalation per inconclusive claim; no 'no novelty surface' (M>0)
    cr, cf = build_coverage(
        [
            _f("NC1", "inconclusive"),
            _f("NC2", "inconclusive"),
            _f("NC3", "clear-under-search"),
        ],
        "d.md",
    )
    i_esc = [e for e in cr["escalations"] if e.get("claim_ref")]
    if len(i_esc) != 2:
        failures.append(f"I=2: expected 2 claim escalations, got {len(i_esc)}")
    if not _sums_ok(cr["counts"]):
        failures.append("I>0: counts don't sum")
    if not _no_forbidden(cr):
        failures.append("I>0: forbidden term 'novel_confirmed' appeared")

    # 3. mixed; sums; forbidden term absent everywhere; clear-under-search counted only
    cr, cf = build_coverage(
        [
            _f("NC1", "clear-under-search"),
            _f("NC2", "collision"),
            _f("NC3", "uncited-relevant"),
            _f("NC4", "inconclusive"),
        ],
        "d.md",
    )
    if not _sums_ok(cr["counts"]):
        failures.append("mixed: counts don't sum")
    if cr["counts"]["total_extracted"] != 4:
        failures.append("mixed: M != 4")
    # clear-under-search counted, NOT a finding (3 findings: collision/uncited/inconclusive)
    if len(cf["findings"]) != 3:
        failures.append(
            f"mixed: expected 3 findings (clear-under-search counted only), got {len(cf['findings'])}"
        )
    if not _no_forbidden(cr) or not _no_forbidden(cf):
        failures.append("forbidden term 'novel_confirmed' appeared")
    if cr["signal"] != "collisions_under_known_coverage":
        failures.append("signal wrong")

    # 4. unrecognized verdict value -> sum invariant FAILS (total=len, not bucket sum)
    #    + a data-integrity escalation fires. Makes _sums_ok a REAL check, not a tautology.
    cr, cf = build_coverage(
        [
            {"claim_id": "NC1", "verdict": "CLEAR-typo"},
            {
                "claim_id": "NC2",
                "verdict": "collision",
                "finding": {
                    "defect_id": "nc2",
                    "severity": "blocker",
                    "kind": "claim-collision",
                    "location": "s",
                    "evidence": 'prior art "q"',
                },
            },
        ],
        "d.md",
    )
    if _sums_ok(cr["counts"]):
        failures.append(
            "unrecognized verdict: sum invariant should FAIL (total != C+N+U+I)"
        )
    if cr["counts"]["total_extracted"] != 2:
        failures.append(
            f"unrecognized verdict: total should be 2 (len), got {cr['counts']['total_extracted']}"
        )
    if not any("data integrity" in e["reason"] for e in cr["escalations"]):
        failures.append("unrecognized verdict: no data-integrity escalation")
    if not _no_forbidden(cr) or not _no_forbidden(cf):
        failures.append("unrecognized: forbidden term 'novel_confirmed' appeared")

    if failures:
        print("FAIL: coverage-policy gate")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: coverage-policy gate (NC-I5c) -- sums, M=0/I>0 escalation, "
        "no novel_confirmed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
