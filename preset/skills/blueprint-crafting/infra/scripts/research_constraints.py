#!/usr/bin/env python3
"""research_constraints.py — the research constraints-profile (iteration I4).

The research analog of constraints_check.py (I3). Where the I3 checker runs the non-research profiles (anchors + authority + ODP), this checker runs the RESEARCH profile (artifact_type="research") against the ADR #7 v1 subset modeled on ws-wiki/fedaot-kb:

  - sources-cited      (Blocker): every claim cites >=1 FETCHED source.
  - staging-via-convergence (Blocker): a frozen research artifact (out of staging) must have converged; freezing unreviewed research is the hallucination/timeliness/ bias defense.
  - cost-bounded       (Blocker when exceeded): used <= budget on each axis.
  - provenance-tag     (warning): each source tagged by type; unknown is advisory.

DEFERRED (ADR #7): direction-normalized idempotency; full Tier1/2/3 trust-tier.
DROPPED: fedaot-kb purity (KB-platform-specific; the artifact completeness-checker
covers its role).

The research data lives in the plan-model's optional `research` field (claims / sources / cost_ledger / staging). A research artifact without that field degrades to a coverage note (rule 3). CLI:

    python3 infra/scripts/research_constraints.py <plan-model.json>
"""

import json
import sys

COST_AXES = ("tokens", "calls", "sources")


def check(plan_model):
    """Run the research v1 profile. Returns {profile, passed, failures[], warnings[], coverage[]}. passed is True iff no blocker-severity failure."""
    res = {
        "profile": "research-v1",
        "passed": True,
        "failures": [],
        "warnings": [],
        "coverage": [],
    }
    if plan_model.get("artifact_type") != "research":
        res["coverage"].append(
            f"not a research artifact (artifact_type={plan_model.get('artifact_type')!r}); "
            f"the non-research profiles are checked by constraints_check.py (I3)"
        )
        return res
    r = plan_model.get("research")
    if r is None:
        res["coverage"].append(
            "research artifact has no `research` field (claims/sources/cost_ledger/staging) — "
            "cannot check the v1 profile; rule 3"
        )
        return res

    sources = {
        s.get("source_id"): s for s in r.get("sources", []) if isinstance(s, dict)
    }
    claims = r.get("claims", [])

    # 1. sources-cited (Blocker)
    for c in claims:
        cid = c.get("text", "")[:60]
        refs = c.get("source_refs", []) or []
        if not refs:
            res["failures"].append(
                {
                    "check": "sources-cited",
                    "severity": "blocker",
                    "claim": cid,
                    "msg": f"unsourced claim ({len(refs)} source_refs) — every claim must trace to a fetched source",
                }
            )
            continue
        for ref in refs:
            s = sources.get(ref)
            if s is None:
                res["failures"].append(
                    {
                        "check": "sources-cited",
                        "severity": "blocker",
                        "claim": cid,
                        "msg": f"claim cites unknown source {ref!r}",
                    }
                )
            elif not s.get("fetched"):
                res["failures"].append(
                    {
                        "check": "sources-cited",
                        "severity": "blocker",
                        "claim": cid,
                        "source_id": ref,
                        "msg": f"claim cites source {ref!r} that was not fetched",
                    }
                )

    # 2. staging-via-convergence (Blocker): frozen => must have converged
    st = r.get("staging", {}) or {}
    if not st.get("in_staging", True) and not st.get("converged", False):
        res["failures"].append(
            {
                "check": "staging-via-convergence",
                "severity": "blocker",
                "msg": "research frozen (out of staging) without convergence — must pass the convergence loop before freezing",
            }
        )

    # 3. cost-bounded (Blocker when exceeded)
    cl = r.get("cost_ledger", {}) or {}
    budget = cl.get("budget", {}) or {}
    used = cl.get("used", {}) or {}
    for axis in COST_AXES:
        cap = budget.get(axis)
        u = used.get(axis, 0)
        if cap is not None and u > cap:
            res["failures"].append(
                {
                    "check": "cost-bounded",
                    "severity": "blocker",
                    "axis": axis,
                    "msg": f"cost axis {axis} exceeded: used {u} > budget {cap}",
                }
            )

    # 4. provenance-tag (warning — rule 4: advisory, never Blocker)
    for s in r.get("sources", []):
        if s.get("provenance") in (None, "unknown"):
            res["warnings"].append(
                {
                    "check": "provenance-tag",
                    "source_id": s.get("source_id"),
                    "msg": f"source {s.get('source_id')!r} provenance is unknown — advisory (rule 4)",
                }
            )

    res["passed"] = not any(f.get("severity") == "blocker" for f in res["failures"])
    return res


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: research_constraints.py <plan-model.json>")
    with open(sys.argv[1], encoding="utf-8") as fh:
        pm = json.load(fh)
    res = check(pm)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
