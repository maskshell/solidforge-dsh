#!/usr/bin/env python3
"""constraints_check.py — inner-ring deterministic gate (iteration I3).

Runs the artifact's constraints-profile on the normalized plan-model (ADR #2: determinism holds over the MODEL, not the source). Profile = required anchors (completeness) + authority-chain consistency + resolve-now-ODP-resolved. The profiles live in constraints.json (the registry — workspace rule 2); this checker reads it and never hardcodes a profile. Adding a profile = edit the registry, not this file. The research profile is separate (research_constraints.py, I4).

Severity (workspace rule 4): only REAL violations are Blockers — a missing required anchor, an undeclared authority doc, an unresolved resolve-now ODP. ABSENCE of the anchors map is NOT a Blocker — it degrades to a coverage note (rule 3: honest degradation; the checker cannot verify what was not extracted).

Imported by infra/test/constraints_check_goldens.py. CLI:

    python3 infra/scripts/constraints_check.py <plan-model.json>
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "constraints.json")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def _dod_doc(dod_ref):
    """The doc-path portion of a dod_ref (before '#'), only if it looks like a clean path. 'docs/spec.md#jtbd' -> 'docs/spec.md'; a verbose DoD cell (a sentence, has spaces) -> '' (not a reference).
    Guards against false authority contradictions on rich-md sources where dod_ref may carry the DoD description text."""
    if not dod_ref:
        return ""
    doc = dod_ref.split("#", 1)[0].strip()
    if doc and " " not in doc and ("/" in doc or doc.endswith(".md")):
        return doc
    return ""


def check(plan_model, registry=None):
    """Run the plan-model's constraints-profile.
    Returns {artifact_type, profile_found, passed, failures[], coverage[]}. passed is True iff no blocker-severity failure."""
    reg = registry or load_registry()
    profiles = reg.get("profiles", {})
    artifact_type = plan_model.get("artifact_type")
    result = {
        "artifact_type": artifact_type,
        "profile_found": artifact_type in profiles,
        "passed": True,
        "failures": [],
        "coverage": [],
    }

    profile = profiles.get(artifact_type)
    if not profile:
        result["coverage"].append(
            f"no constraints-profile for artifact_type {artifact_type!r} (research is I4; "
            f"unknown types degrade — not checked)"
        )
        return result

    chain = plan_model.get("authority_chain", [])
    items = plan_model.get("items", [])

    # 1. anchors (completeness) — absence degrades to coverage, a gap is a Blocker
    anchors_map = plan_model.get("anchors")
    anchors_meta = plan_model.get("anchors_meta", {}) or {}
    heuristic = anchors_meta.get("source") == "normalizer-extracted"
    if anchors_map is None:
        result["coverage"].append(
            "anchors map absent — anchor completeness not checked (the source was not "
            "anchor-extracted, or this is a structural plan-model); rule 3"
        )
    else:
        for req in profile.get("anchors", []):
            entry = anchors_map.get(req)
            satisfied = isinstance(entry, dict) and entry.get("present")
            if not satisfied:
                if heuristic:
                    # the anchors map came from heuristic keyword detection (the normalizer);
                    # an undetected anchor may be a detector miss, not a real absence -> degrade to a coverage note (rule 4: no Blocker-on-a-heuristic-miss).
                    result["coverage"].append(
                        f"required anchor '{req}' for {artifact_type} not detected by the "
                        f"normalizer (heuristic; rule 4 — advisory, not a Blocker)"
                    )
                else:
                    # author-supplied map is authoritative: a gap is a real Blocker
                    result["failures"].append(
                        {
                            "check": "anchor",
                            "severity": "blocker",
                            "anchor": req,
                            "msg": f"required anchor '{req}' for {artifact_type} is missing or not present",
                        }
                    )

    # 2. authority-chain consistency — undeclared dod_ref doc is a contradiction
    for it in items:
        doc = _dod_doc(it.get("dod_ref", ""))
        if doc and doc not in chain:
            result["failures"].append(
                {
                    "check": "authority",
                    "severity": "blocker",
                    "item_id": it.get("item_id"),
                    "msg": (
                        f"item {it.get('item_id')} dod_ref references '{doc}' which is not "
                        f"declared in authority_chain {chain} — authority contradiction"
                    ),
                }
            )

    # 3. resolve-now ODPs must be resolved (carry a resolution)
    for it in items:
        for odp in it.get("odp_status", []) or []:
            if (
                odp.get("kind") == "resolve-now"
                and not str(odp.get("resolution", "")).strip()
            ):
                result["failures"].append(
                    {
                        "check": "odp",
                        "severity": "blocker",
                        "item_id": it.get("item_id"),
                        "odp_id": odp.get("id"),
                        "msg": (
                            f"item {it.get('item_id')} has unresolved resolve-now ODP "
                            f"'{odp.get('id')}' (no resolution) — blocks convergence"
                        ),
                    }
                )

    result["passed"] = not any(
        f.get("severity") == "blocker" for f in result["failures"]
    )
    return result


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: constraints_check.py <plan-model.json>")
    with open(sys.argv[1], encoding="utf-8") as fh:
        pm = json.load(fh)
    res = check(pm)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
