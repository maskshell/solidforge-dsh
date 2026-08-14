#!/usr/bin/env python3
"""verdict.py — the two-field verdict-emitter (iteration I6).

Aggregates the inner ring (constraints_check I3 / research_constraints I4) and the outer ring (plan_reviewer I5 findings) into a spec run-record with exactly two verdict fields, kept structurally isolated (arch-design §5):

  - process_converged (process axis): high confidence, convergeable. true iff the inner ring passed AND the outer ring has no Blocker.
  - rightness (outcome axis): the CONSTANT 'human_confirm_required'. The outcome axis (is the artifact 'right') is out of this skill's scope — always human.

FIELD ISOLATION (the I6 DoD): rightness is set to the constant UNCONDITIONALLY — it never reads process_converged. The run-record schema reinforces this: rightness is an enum with exactly ONE value. A green process axis therefore can never change rightness. A consumer must not misread process_converged as outcome-axis success.

The outer-ring findings are supplied by the caller (the convergence loop spawns the plan_reviewer and passes its findings). When the outer ring did not run, the caller passes outer={} and the record carries a coverage note (process_converged stays False — no convergence without the outer ring). CLI:

    python3 infra/scripts/verdict.py <plan-model.json>   # inner-only emit (outer noted as not-run)
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RIGHTNESS = "human_confirm_required"  # the outcome-axis constant — NEVER depends on process_converged

CAVEAT = "rightness is human_confirm_required by design (outcome axis); a green process_converged is NOT outcome-axis success — do not misread the two (field isolation, arch-design §5)"


def _blockers(findings):
    return sum(
        1
        for f in (findings or [])
        if isinstance(f, dict) and f.get("severity") == "blocker"
    )


def emit(artifact_type, inner, outer):
    """Build the spec run-record. inner/outer are the ring results from the I3/I4 checker and the I5 reviewer respectively. rightness is the constant regardless."""
    inner_failures = inner.get("failures", []) if isinstance(inner, dict) else []
    inner_passed = bool(inner.get("passed", False)) and _blockers(inner_failures) == 0
    inner_blockers = _blockers(inner_failures)

    outer_findings = outer.get("findings", []) if isinstance(outer, dict) else []
    outer_blockers = _blockers(outer_findings)
    outer_ran = bool(outer) and ("findings" in (outer or {}))

    process_converged = (
        inner_passed and (inner_blockers == 0) and (outer_ran and outer_blockers == 0)
    )

    coverage = []
    if isinstance(inner, dict):
        coverage.extend(inner.get("coverage", []))
    if isinstance(outer, dict):
        coverage.extend(outer.get("coverage", []))
    if not outer_ran:
        coverage.append(
            "outer ring (plan_reviewer) did not run — process_converged cannot be true without it"
        )

    return {
        "artifact_type": artifact_type,
        "process_converged": process_converged,  # the convergeable field
        "rightness": RIGHTNESS,  # CONSTANT — never reads process_converged (field isolation)
        "inner_ring": {
            "passed": inner_passed,
            "blockers": inner_blockers,
            "findings": len(inner_failures),
            "profile": (inner or {}).get("profile", ""),
        },
        "outer_ring": {
            "passed": outer_ran and outer_blockers == 0,
            "blockers": outer_blockers,
            "findings": len(outer_findings),
        },
        "coverage": coverage,
        "caveats": [CAVEAT],
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: verdict.py <plan-model.json>")
    with open(sys.argv[1], encoding="utf-8") as fh:
        pm = json.load(fh)
    at = pm.get("artifact_type", "iteration-plan")
    # inner-only emit: run the right checker for the artifact type
    if at == "research":
        import research_constraints

        inner = research_constraints.check(pm)
        inner["profile"] = "research-v1"
    else:
        import constraints_check

        inner = constraints_check.check(pm)
    rec = emit(at, inner, outer={})  # outer not run in CLI mode
    print(json.dumps(rec, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
