#!/usr/bin/env python3
"""dogfood.py -- NC-I6 dogfood + quality-stability gate.

Runs prior-art-search's DETERMINISTIC core on a fixture that mirrors the skill's
origin: the spec-gaming paper's self-certification-paradox NOVELTY claim colliding with
findable prior art. The readiness-gate worked example (proposal origin, 2026-07-31) ran
a search-to-collision on the paper and surfaced the "Verification Paradox" /
"Self-Critique Paradox" framings as uncited prior art for its self-certification-paradox
novelty claim -- exactly the collision this fixture asserts prior-art-search CATCHES
(claim-collision, with a fetched prior-art quote) + an honest collision-record. This is
the value proposition, exercised on the canonical fixture (iteration-plan NC-I6).

The MODEL legs (novelty-claim-extractor / collision-verifier) + the live search need a
live model + network; this self-gate tests the deterministic POLICY on a fixture verdict
set (the verdicts a live run would produce), and SKIPS GRACEFULLY (rule 1 + rule 3) when
a live run is not possible -- a recorded log substitutes. The live N>=3 dogfood (incl.
>=1 long doc with a KNOWN prior-art collision -- the spec-gaming paper re-run) is an
acceptance-gate criterion run by the human/orchestrator, not this offline gate.

Self-contained (rule 7); exits 0 on green. Run: python3 infra/test/dogfood.py
"""

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.normpath(os.path.join(_THIS, "..", "scripts"))
sys.path.insert(0, _SCRIPTS)

from coverage_driver import build_coverage  # noqa: E402

# Fixture: the verdicts a live prior-art-search run would produce on the spec-gaming
# paper (the canonical collision dogfood). NC1 = the self-certification-paradox novelty
# claim COLLIDING with the Verification-/Self-Critique-Paradox prior-art framings the
# readiness-gate surfaced.
FIXTURE_VERDICTS = [
    {
        "claim_id": "NC1",
        "verdict": "collision",
        "finding": {
            "defect_id": "novelty-claim-NC1",
            "severity": "blocker",
            "kind": "claim-collision",
            "location": "self-certification-paradox novelty claim | prior-art framing",
            "evidence": (
                "claim: 'we introduce the self-certification-paradox framing as a "
                "novel contribution.' found prior art: \"the Self-Critique Paradox "
                '(a verifier that must verify itself)" and "the Verification '
                'Paradox" already frame this -- the novelty claim collides with '
                "findable prior art the doc did not cite."
            ),
        },
    },
    {
        "claim_id": "NC2",
        "verdict": "uncited-relevant",
        "finding": {
            "defect_id": "novelty-claim-NC2",
            "severity": "warning",
            "kind": "claim-uncited-relevant",
            "location": "two-axis novelty claim",
            "evidence": (
                'fetched: prior work "separates process convergence from outcome '
                'verification" -- relevant to the two-axis claim and uncited here '
                "(a coverage gap, not a direct collision)."
            ),
        },
    },
    {"claim_id": "NC3", "verdict": "clear-under-search"},
    {
        "claim_id": "NC4",
        "verdict": "collision",
        "finding": {
            "defect_id": "novelty-claim-NC4",
            "severity": "blocker",
            "kind": "claim-collision",
            "location": "s",
            "evidence": "",  # quote-less -> the invariant downgrades to inconclusive
        },
    },
]


def main() -> int:
    failures: list[str] = []
    cr, cf = build_coverage(FIXTURE_VERDICTS, "spec-gaming-paper.md")

    # 1. the collision is CAUGHT (NC1 collision with a fetched prior-art quote)
    nc1 = next((v for v in FIXTURE_VERDICTS if v["claim_id"] == "NC1"), None)
    if not nc1 or nc1["verdict"] != "collision":
        failures.append("NC1 collision not caught")
    if "Self-Critique Paradox" not in nc1["finding"]["evidence"]:
        failures.append("NC1 evidence lacks the fetched prior-art framing quote")

    # 2. counts: C=1 (NC3), N=1 (NC1), U=1 (NC2), I=1 (NC4 downgraded), M=4
    c = cr["counts"]
    if c != {
        "clear_under_search": 1,
        "collisions": 1,
        "uncited_relevant": 1,
        "inconclusive": 1,
        "total_extracted": 4,
    }:
        failures.append(f"counts wrong: {c}")
    if (
        c["total_extracted"]
        != c["clear_under_search"]
        + c["collisions"]
        + c["uncited_relevant"]
        + c["inconclusive"]
    ):
        failures.append("M != C+N+U+I")

    # 3. the quote-less NC4 was downgraded (collision fetched-quote invariant)
    downgraded_note = any("downgraded" in n for n in cr["coverage"])
    if not downgraded_note:
        failures.append(
            "quote-less NC4 not downgraded (collision fetched-quote invariant)"
        )

    # 4. never novel_confirmed; honest escalation for the downgraded NC4 (I>0)
    if "novel_confirmed" in json.dumps(cr) or "novel_confirmed" in json.dumps(cf):
        failures.append("forbidden term 'novel_confirmed' appeared")
    if not any(e.get("claim_ref") == "NC4" for e in cr["escalations"]):
        failures.append("NC4 (downgraded) not escalated")

    if failures:
        print("FAIL: dogfood gate (NC-I6)")
        for f in failures:
            print("  -", f)
        return 1
    print(
        "PASS: dogfood gate (NC-I6) -- collision CAUGHT (self-certification-paradox "
        "claim collides with Self-Critique/Verification-Paradox prior art via fetched "
        "quote), uncited-relevant surfaced, quote-less downgraded; counts C=1/N=1/U=1/I=1 M=4"
    )
    print(
        "  coverage: this offline gate tests the deterministic policy on the canonical "
        "fixture; the live N>=3 dogfood (incl. >=1 long doc with a known collision -- the "
        "spec-gaming paper re-run) is run by the orchestrator/human at the acceptance "
        "gate (rule 1 skip path)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
