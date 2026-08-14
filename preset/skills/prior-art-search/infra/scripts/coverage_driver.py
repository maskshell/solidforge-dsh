#!/usr/bin/env python3
"""coverage_driver.py -- prior-art-search's deterministic coverage core (NC-I4).

Takes the per-claim collision verdicts (from collision-verifier) and emits:
  - a collision-record (collisions_under_known_coverage + C/N/U/I of M)
  - a collision-findings packet (collision / uncited-relevant / inconclusive findings)

Enforces the load-bearing invariants (proposal §3 / §8 Q3, design-decisions.md ADR #1/#3/#7):
  - fetched-quote invariant: a collision/uncited-relevant finding WITHOUT a fetched
    prior-art quote in `evidence` is DOWNGRADED to claim-inconclusive (rule 3 + L1).
  - M = C + N + U + I (total_extracted == clear_under_search + collisions + uncited_relevant
    + inconclusive).
  - M=0 -> escalation 'no novelty surface on this artifact'; I>0 -> one escalation per
    inconclusive claim. Never a silent pass.
  - signal is ALWAYS collisions_under_known_coverage; novel_confirmed NEVER appears in any
    emitted object.

The fetched-quote check is a STRUCTURAL PROXY (evidence non-empty AND contains a quote
marker), not a semantic proof that the quote is real or the collision genuine -- a model
could fabricate or misread a quote. That limit is disclosed in the collision-record's
`coverage` notes (rule 3: never silently green). Stdlib-only; no runtime deps.

CLI:
    python3 coverage_driver.py <verdicts.json> [--artifact <ref>]
        verdicts.json = list of {claim_id, verdict, finding?}  (collision-verifier outputs)
        stdout = {"coverage_record": {...}, "findings": {"outcome_axis_respected": true, ...}}
"""

import argparse
import json
import sys

SIGNAL = "collisions_under_known_coverage"
FORBIDDEN_TERM = "novel_confirmed"
_RIGHTNESS = "human_confirm_required"


def _has_fetched_quote(evidence: str) -> bool:
    """Structural proxy: evidence is non-empty and contains a quote marker.

    A real fetched prior-art quote is prose-quoted (contains a `"`) or explicitly tags
    itself (`fetched:`/`source:`/`quote:`). Empty or marker-less evidence fails the proxy
    -> downgrade. Documented limit: this cannot prove the quote is genuine or the collision
    real, only that a quote was supplied (design-decisions.md ADR #3).
    """
    if not evidence:
        return False
    low = evidence.lower()
    return (
        ('"' in evidence)
        or ("fetched" in low)
        or ("source:" in low)
        or ("quote:" in low)
    )


def enforce_fetched_quote(verdict: dict) -> tuple[dict, bool]:
    """Downgrade a quote-less collision/uncited-relevant verdict to inconclusive.

    Returns (verdict, downgraded). Uses a cid fallback so claim_id is never None (W2);
    rewrites finding to claim-inconclusive / severity coverage with a non-empty location
    (W1). Tags the downgraded verdict with an internal `downgraded_from` marker so
    build_coverage emits a distinct escalation reason (C1: a downgraded collision is NOT
    'search could not cover' -- the search found a collision but the quote was missing).
    The marker is internal; it never reaches the emitted record.
    """
    original = verdict.get("verdict")
    if original in ("collision", "uncited-relevant"):
        finding = verdict.get("finding") or {}
        if not _has_fetched_quote(finding.get("evidence", "")):
            cid = verdict.get("claim_id", finding.get("defect_id", "claim"))
            downgraded = {
                "claim_id": cid,
                "verdict": "inconclusive",
                "downgraded_from": original,
                "finding": {
                    "defect_id": finding.get("defect_id", cid),
                    "severity": "coverage",
                    "kind": "claim-inconclusive",
                    "location": finding.get("location")
                    or f"claim {cid} (location unavailable)",
                    "evidence": (
                        finding.get("evidence", "")
                        or "no fetched prior-art quote supplied -- downgraded per the "
                        "fetched-quote invariant (rule 3 + L1)"
                    ),
                },
            }
            return downgraded, True
    return verdict, False


def build_coverage(verdicts: list[dict], artifact: str) -> tuple[dict, dict]:
    """Build the collision-record + collision-findings packet from per-claim verdicts."""
    # 1. enforce the fetched-quote invariant (downgrade collision/uncited-relevant -> inconclusive)
    cleaned = []
    downgrades = 0
    for v in verdicts:
        cv, down = enforce_fetched_quote(v)
        if down:
            downgrades += 1
        cleaned.append(cv)

    # 2. count. m = ALL verdicts (not the bucket sum) so an unrecognized verdict value
    #    surfaces as C+N+U+I != M (a data-integrity escalation), never a silent misleading M=0.
    c = sum(1 for v in cleaned if v.get("verdict") == "clear-under-search")
    n = sum(1 for v in cleaned if v.get("verdict") == "collision")
    u = sum(1 for v in cleaned if v.get("verdict") == "uncited-relevant")
    i = sum(1 for v in cleaned if v.get("verdict") == "inconclusive")
    m = len(cleaned)
    unrecognized = m - (c + n + u + i)

    # 3. findings packet (collision / uncited-relevant / inconclusive). clear-under-search is
    #    counted only (no defect). Synthesize a minimal claim-inconclusive finding if a verdict
    #    lacks one, so the packet is complete (an inconclusive verdict is itself a finding).
    findings = []
    for v in cleaned:
        if v.get("verdict") in ("collision", "uncited-relevant", "inconclusive"):
            f = v.get("finding")
            if not f:
                cid = v.get("claim_id", "claim")
                f = {
                    "defect_id": cid,
                    "severity": "coverage",
                    "kind": "claim-inconclusive",
                    "location": f"claim {cid} (location unavailable)",
                    "evidence": f"verdict={v.get('verdict')} without a finding body",
                }
            findings.append(f)
    collision_findings = {"outcome_axis_respected": True, "findings": findings}

    # 4. escalations (I>0 one per claim; M=0 one 'no novelty surface'; unrecognized data-integrity)
    escalations = []
    if m == 0:
        escalations.append(
            {
                "reason": (
                    "no extractable novelty claims -- prior-art-search has no "
                    "novelty surface on this artifact"
                )
            }
        )
    for v in cleaned:
        if v.get("verdict") == "inconclusive":
            cid = v.get("claim_id")
            if v.get("downgraded_from"):
                reason = (
                    f"{v['downgraded_from']} found but fetched quote missing -- downgraded "
                    "to inconclusive; re-run search to re-quote"
                )
            else:
                reason = "search could not cover this claim"
            entry = {"reason": reason}
            if cid:
                entry["claim_ref"] = cid
            escalations.append(entry)
    if unrecognized > 0:
        escalations.append(
            {
                "reason": (
                    f"data integrity: {unrecognized} verdict(s) had unrecognized values "
                    "(not collision/uncited-relevant/clear-under-search/inconclusive)"
                )
            }
        )

    coverage_notes = [
        (
            "extractor blind-spot: claims neither author nor extractor identify as "
            "novelty are absent from M (rule 3)"
        ),
        (
            "comparison blind-spot: 'clear-under-search' means no collision was found, "
            "not that none exists"
        ),
        (
            "selection-side weakness: the searched corpus is recall-limited and ranking-biased; "
            "found text is model-extracted (oracle-weakness layer 2 of 2)"
        ),
        (
            "fetched-quote invariant is a structural proxy (evidence non-empty + quote marker); "
            "a supplied quote may be fabricated or misread -- the blocker stands in-schema "
            "while this proxy limit is named, not folded into severity (ADR #3)"
        ),
    ]
    if downgrades:
        coverage_notes.append(
            f"{downgrades} collision/uncited-relevant verdict(s) downgraded to claim-inconclusive "
            "(fetched-quote invariant)"
        )

    collision_record = {
        "artifact": artifact,
        "signal": SIGNAL,
        "counts": {
            "clear_under_search": c,
            "collisions": n,
            "uncited_relevant": u,
            "inconclusive": i,
            "total_extracted": m,
        },
        "rightness": _RIGHTNESS,
        "escalations": escalations,
        "coverage": coverage_notes,
    }
    return collision_record, collision_findings


def _assert_no_forbidden(obj: dict) -> None:
    """Defense in depth: the forbidden term never appears as a key or value."""
    blob = json.dumps(obj)
    assert FORBIDDEN_TERM not in blob, (
        f"forbidden term {FORBIDDEN_TERM!r} appeared in emitted object"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="prior-art-search driver: collision verdicts -> collision-record + findings."
    )
    ap.add_argument(
        "verdicts", help="path to a JSON list of {claim_id, verdict, finding?} objects."
    )
    ap.add_argument(
        "--artifact",
        default="<artifact>",
        help="artifact path/ref for the collision-record.",
    )
    args = ap.parse_args()

    with open(args.verdicts) as fh:
        verdicts = json.load(fh)

    collision_record, collision_findings = build_coverage(verdicts, args.artifact)
    _assert_no_forbidden(collision_record)
    _assert_no_forbidden(collision_findings)

    json.dump(
        {"coverage_record": collision_record, "findings": collision_findings},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
