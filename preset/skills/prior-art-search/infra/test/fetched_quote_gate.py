#!/usr/bin/env python3
"""NC-I5(a) -- the collision fetched-quote invariant gate (load-bearing L1/rule-3).

Asserts: a collision/uncited-relevant verdict WITHOUT a fetched prior-art quote in
`evidence` is DOWNGRADED to claim-inconclusive by coverage_driver.enforce_fetched_quote.
A collision/uncited-relevant WITH a quote is left intact. clear-under-search/inconclusive
are unaffected. This is the honesty invariant that keeps prior-art-search from asserting
a collision it cannot ground in fetched prior-art text (proposal §3; workspace rule 3;
design-decisions.md ADR #3 -- the check is a structural proxy, not a semantic proof).

Mirrors primary-source-verification's fetched_quote_gate.py (rule 7 -- copy the helper,
do NOT import a shared lib), adapted to the collision verdict set. Self-contained;
exits 0 on green, 1 on any failure. Stdlib-only. Run: python3 infra/test/fetched_quote_gate.py
"""

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import enforce_fetched_quote  # noqa: E402


def _v(claim_id: str, verdict: str, evidence: str) -> dict:
    sev = "blocker" if verdict == "collision" else "warning"
    return {
        "claim_id": claim_id,
        "verdict": verdict,
        "finding": {
            "defect_id": f"novelty-claim-{claim_id}",
            "severity": sev,
            "kind": f"claim-{verdict}",
            "location": "loc",
            "evidence": evidence,
        },
    }


def main() -> int:
    failures = []

    # 1. collision WITHOUT a quote -> downgraded to inconclusive
    out, down = enforce_fetched_quote(_v("NC1", "collision", ""))
    if not down or out["verdict"] != "inconclusive":
        failures.append("collision without quote was NOT downgraded")
    if (
        out["finding"]["kind"] != "claim-inconclusive"
        or out["finding"]["severity"] != "coverage"
    ):
        failures.append("downgraded finding kind/severity wrong")
    if out.get("downgraded_from") != "collision":
        failures.append("downgraded_from marker missing/wrong")

    # 2. uncited-relevant WITHOUT a quote -> downgraded
    out, down = enforce_fetched_quote(
        _v("NC2", "uncited-relevant", "vague hand-wave, no quote")
    )
    if not down or out["verdict"] != "inconclusive":
        failures.append("uncited-relevant without quote was NOT downgraded")

    # 3. collision WITH a fetched quote -> intact
    out, down = enforce_fetched_quote(
        _v("NC3", "collision", 'prior art says "we introduce C" -- collides')
    )
    if down or out["verdict"] != "collision":
        failures.append("collision WITH a quote was wrongly downgraded")

    # 4. uncited-relevant WITH a fetched quote -> intact
    out, down = enforce_fetched_quote(
        _v("NC4", "uncited-relevant", 'fetched: Smith "shows D" uncited here')
    )
    if down or out["verdict"] != "uncited-relevant":
        failures.append("uncited-relevant WITH a quote was wrongly downgraded")

    # 5. clear-under-search / inconclusive -> unaffected (no downgrade path)
    for v in ("clear-under-search", "inconclusive"):
        out, down = enforce_fetched_quote(
            {"claim_id": "NC5", "verdict": v, "finding": {}}
        )
        if down:
            failures.append(f"{v} was wrongly downgraded")

    if failures:
        print("FAIL: collision fetched-quote invariant gate")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: collision fetched-quote invariant gate (NC-I5a) -- "
        "quote-less collision/uncited-relevant downgraded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
