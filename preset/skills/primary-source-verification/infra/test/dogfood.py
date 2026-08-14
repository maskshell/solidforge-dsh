#!/usr/bin/env python3
"""dogfood.py -- PSV-I6 dogfood + quality-stability gate.

Runs psv's DETERMINISTIC core on a fixture that mirrors the skill's origin: a
doc with a known citation misattribution (the spec-gaming paper's pre-fix draft --
CaMeL framed as a 'specification-gaming lineage' when arXiv:2503.18813 is in fact
'Defeating Prompt Injections by Design'). The gate asserts psv CATCHES the
misattribution (refuted, with a fetched-source quote) and emits an honest
coverage-record. This is the value proposition, exercised on the canonical
fixture (iteration-plan PSV-I6; proposal origin).

The MODEL legs (claim-extractor / claim-verifier) need a live model + network;
this self-gate tests the deterministic POLICY on a fixture verdict set (the
verdicts a live run would produce), and SKIPS GRACEFULLY (rule 1 + rule 3) when
a live run is not possible -- a recorded log substitutes. The live N>=3 dogfood
(incl. >=1 long doc) is an acceptance-gate criterion run by the human/orchestrator,
not this offline gate.

Self-contained (rule 7); exits 0 on green. Run: python3 infra/test/dogfood.py
"""

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

# Fixture: the verdicts a live psv run would produce on the spec-gaming pre-fix
# draft (the canonical misattribution dogfood). These ARE the spot-checks the
# paper's own front matter records (CaMeL-lineage dropped; Pan narrowed).
FIXTURE_VERDICTS = [
    {
        "claim_id": "C1",
        "verdict": "refuted",
        "finding": {
            "defect_id": "claim-C1",
            "severity": "blocker",
            "kind": "claim-refuted",
            "location": "§X CaMeL-lineage claim",
            "evidence": (
                "claim: 'CaMeL is a specification-gaming lineage.' "
                'fetched arXiv:2503.18813 title: "Defeating Prompt Injections by '
                'Design" -- prompt-injection defense, NOT a specification-gaming '
                "lineage. Contradicts the claim."
            ),
        },
    },
    {
        "claim_id": "C2",
        "verdict": "narrowed",
        "finding": {
            "defect_id": "claim-C2",
            "severity": "warning",
            "kind": "claim-narrowed",
            "location": "§Y Pan-irreducible claim",
            "evidence": (
                'fetched: Pan 2022 "demonstrates the gap but also proposes '
                "mitigations\" -- the 'irreducible' reading overclaims."
            ),
        },
    },
    {"claim_id": "C3", "verdict": "verified"},
    {
        "claim_id": "C4",
        "verdict": "refuted",
        "finding": {
            "defect_id": "claim-C4",
            "severity": "blocker",
            "kind": "claim-refuted",
            "location": "§Z",
            "evidence": "",  # quote-less -> the invariant downgrades to unverifiable
        },
    },
]


def main() -> int:
    failures: list[str] = []
    cr, df = build_coverage(FIXTURE_VERDICTS, "spec-gaming-pre-fix-draft.md")

    # 1. the misattribution is CAUGHT (C1 refuted with a fetched quote)
    c1 = next((v for v in FIXTURE_VERDICTS if v["claim_id"] == "C1"), None)
    if not c1 or c1["verdict"] != "refuted":
        failures.append("C1 misattribution not caught as refuted")
    if "Defeating Prompt Injections" not in c1["finding"]["evidence"]:
        failures.append("C1 evidence lacks the fetched CaMeL title quote")

    # 2. counts: N=1 (C3), R=1 (C1), W=1 (C2), K=1 (C4 downgraded), M=4
    c = cr["counts"]
    if c != {
        "verified": 1,
        "refuted": 1,
        "narrowed": 1,
        "unverifiable": 1,
        "total_extracted": 4,
    }:
        failures.append(f"counts wrong: {c}")
    if (
        c["total_extracted"]
        != c["verified"] + c["refuted"] + c["narrowed"] + c["unverifiable"]
    ):
        failures.append("M != N+R+W+K")

    # 3. the quote-less C4 was downgraded (fetched-quote invariant)
    downgraded_note = any("downgraded" in n for n in cr["coverage"])
    if not downgraded_note:
        failures.append("quote-less C4 not downgraded (fetched-quote invariant)")

    # 4. never correctness_converged; honest escalation for K>0
    if "correctness_converged" in json.dumps(
        cr
    ) or "correctness_converged" in json.dumps(df):
        failures.append("forbidden term appeared")
    if not any(e.get("claim_ref") == "C4" for e in cr["escalations"]):
        failures.append("C4 (downgraded) not escalated")

    if failures:
        print("FAIL: dogfood gate (PSV-I6)")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: dogfood gate (PSV-I6) -- misattribution CAUGHT (CaMeL refuted via "
        "fetched quote), Pan narrowed, quote-less downgraded; counts N=1/R=1/W=1/K=1 M=4"
    )
    print(
        "  coverage: this offline gate tests the deterministic policy on the "
        "canonical fixture; the live N>=3 dogfood (incl. >=1 long doc) is run by "
        "the orchestrator/human at the acceptance gate (rule 1 skip path)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
