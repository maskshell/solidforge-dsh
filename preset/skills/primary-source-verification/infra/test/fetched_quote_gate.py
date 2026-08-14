#!/usr/bin/env python3
"""PSV-I5(a) -- the fetched-quote invariant gate (the load-bearing L1/rule-3 check).

Asserts: a refuted/narrowed verdict WITHOUT a fetched-source quote in `evidence`
is DOWNGRADED to claim-unverifiable by coverage_driver.enforce_fetched_quote.
A refuted/narrowed WITH a quote is left intact. verified/unverifiable are
unaffected. This is the honesty invariant that keeps psv from asserting a
contradiction it cannot ground in fetched text (proposal §3; workspace rule 3).

Self-contained (rule 7); exits 0 on green, 1 on any failure. Stdlib-only.
Run: python3 infra/test/fetched_quote_gate.py
"""

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import enforce_fetched_quote  # noqa: E402


def _v(claim_id: str, verdict: str, evidence: str) -> dict:
    return {
        "claim_id": claim_id,
        "verdict": verdict,
        "finding": {
            "defect_id": f"claim-{claim_id}",
            "severity": "blocker" if verdict == "refuted" else "warning",
            "kind": f"claim-{verdict}",
            "location": "loc",
            "evidence": evidence,
        },
    }


def main() -> int:
    failures = []

    # 1. refuted WITHOUT a quote -> downgraded to unverifiable
    out, down = enforce_fetched_quote(_v("C1", "refuted", ""))
    if not down or out["verdict"] != "unverifiable":
        failures.append("refuted without quote was NOT downgraded")
    if (
        out["finding"]["kind"] != "claim-unverifiable"
        or out["finding"]["severity"] != "coverage"
    ):
        failures.append("downgraded finding kind/severity wrong")

    # 2. narrowed WITHOUT a quote -> downgraded
    out, down = enforce_fetched_quote(_v("C2", "narrowed", "vague hand-wave, no quote"))
    if not down or out["verdict"] != "unverifiable":
        failures.append("narrowed without quote was NOT downgraded")

    # 3. refuted WITH a fetched quote -> intact
    out, down = enforce_fetched_quote(
        _v("C3", "refuted", 'source says "X is defense" -- contradicts lineage')
    )
    if down or out["verdict"] != "refuted":
        failures.append("refuted WITH a quote was wrongly downgraded")

    # 4. narrowed WITH a fetched quote -> intact
    out, down = enforce_fetched_quote(
        _v("C4", "narrowed", 'fetched: Pan "demonstrates but mitigates"')
    )
    if down or out["verdict"] != "narrowed":
        failures.append("narrowed WITH a quote was wrongly downgraded")

    # 5. verified / unverifiable -> unaffected (no downgrade path)
    for v in ("verified", "unverifiable"):
        out, down = enforce_fetched_quote(
            {"claim_id": "C5", "verdict": v, "finding": {}}
        )
        if down:
            failures.append(f"{v} was wrongly downgraded")

    if failures:
        print("FAIL: fetched-quote invariant gate")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: fetched-quote invariant gate (PSV-I5a) -- quote-less refuted/narrowed downgraded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
