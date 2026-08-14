#!/usr/bin/env python3
"""Behavioral test for the run-record / L4-assessment pipeline.

Companion to disconnect_check.py (structure) and smoke_gates.py (arch-gate behavior). This verifies the run-record BEHAVIOR: drive loop_state.py through a full convergence-loop scenario in a temp project, emit the run record, and assert (a) it conforms to run-record.schema.json and (b) the l4_assessment rollup matches the scenario's task descriptor + observed events. Run:

    python3 infra/test/run_record.py
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

from run_record_schema import validate as validate_run_record

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "infra", "scripts", "loop_state.py")


def ls(args, project_dir):
    """Run loop_state.py with SOLIDFORGE_PROJECT_DIR=project_dir; return parsed JSON stdout."""
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=project_dir)
    proc = subprocess.run(
        ["python3", SCRIPT] + args,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"loop_state.py {args} failed (rc={proc.returncode}): {proc.stderr}"
    )
    out = proc.stdout.strip()
    try:
        return json.loads(out) if out else {}
    except json.JSONDecodeError:
        return {"_raw": out}


def run_record_of(project_dir):
    return ls(["run-record"], project_dir)


def assert_conforms(record, label):
    errs = validate_run_record(record)
    assert not errs, f"{label}: run record violates schema: {errs}"


def scenario_a_l4_evidenced():
    d = tempfile.mkdtemp(prefix="pdrun_a_")
    ls(
        [
            "init",
            "--task-id",
            "probeA",
            "--blueprint-ref",
            "bp.md",
            "--blueprint-version",
            "v1",
            "--codebase-novelty",
            "novel",
            "--req-clarity",
            "fuzzy",
            "--difficulty",
            "high",
            "--attended",
            "false",
            "--target-horizon-steps",
            "60",
        ],
        d,
    )
    for _ in range(65):
        ls(["bump-iteration"], d)
    for _ in range(3):
        ls(["gate-fail", "app/svc.py:ruff:undefined name"], d)
    ls(["record-outer", "--verdict", "rewrite", "--findings", "3"], d)
    ls(["record-outer", "--verdict", "pass"], d)
    ls(["mark-converged"], d)
    rec = run_record_of(d)
    assert_conforms(rec, "A")
    a = rec["l4_assessment"]
    assert rec["outcome"] == "converged", f"A: outcome={rec['outcome']}"
    assert rec["steps"]["total"] >= 60, f"A: steps.total={rec['steps']['total']}"
    assert a["terminal_cause"] == "converged", (
        f"A: terminal_cause={a['terminal_cause']}"
    )
    assert a["is_l4_probe"] is True, (
        "A: should be an L4 probe (novel+fuzzy+high+unattended)"
    )
    assert a["outer_reviews"] == 2, f"A: outer_reviews={a['outer_reviews']}"
    assert a["breakers_fired_count"] >= 1, (
        "A: expected >=1 breaker firing from the 3x gate-fail"
    )
    assert a["provisional_verdict"] == "l4-evidenced", (
        f"A: provisional={a['provisional_verdict']}"
    )
    assert "caveat-2-unproven-at-scale" in a["caveats_addressed"], (
        f"A: caveats={a['caveats_addressed']}"
    )
    assert a["human_confirm_required"] is True, "A: human confirm always required"
    assert glob.glob(os.path.join(d, ".solidforge", "loop", "runs", "probeA-*.json")), (
        "A: run-record file not written"
    )
    print("  A (l4-evidenced): PASS")


def scenario_b_not_a_probe():
    d = tempfile.mkdtemp(prefix="pdrun_b_")
    # init WITHOUT a task descriptor -> not an L4 probe even if it converges cleanly.
    ls(["init", "--task-id", "probeB"], d)
    for _ in range(10):
        ls(["bump-iteration"], d)
    ls(["record-outer", "--verdict", "pass"], d)
    ls(["mark-converged"], d)
    rec = run_record_of(d)
    assert_conforms(rec, "B")
    a = rec["l4_assessment"]
    assert a["is_l4_probe"] is False, "B: no task descriptor -> not a probe"
    # ADR #38 capacity/demand split: capacity (3-degradation defense under convergence)
    # is met regardless of demand (is_l4_probe). This non-probe run converged cleanly
    # with an outer review -> l4-evidenced (was not-a-probe under the old demand-gated logic).
    assert a["provisional_verdict"] == "l4-evidenced", (
        f"B: provisional={a['provisional_verdict']}"
    )
    assert a["caveats_addressed"] == [], (
        f"B: non-probe l4-evidenced does NOT retire caveat-2 (demand-weighted; ADR #38), got {a['caveats_addressed']}"
    )
    print("  B (non-probe capacity-met -> l4-evidenced): PASS")


def scenario_c_inconclusive():
    d = tempfile.mkdtemp(prefix="pdrun_c_")
    # A slow provider exhausts the time budget and the run hard-terminates on a RESOURCE cap. Capability is NOT judged a failure — provisional=inconclusive.
    ls(
        [
            "init",
            "--task-id",
            "probeC",
            "--codebase-novelty",
            "novel",
            "--req-clarity",
            "fuzzy",
            "--difficulty",
            "high",
            "--attended",
            "false",
            "--target-horizon-steps",
            "60",
        ],
        d,
    )
    ls(["add-budget", "--seconds", "99999"], d)
    ls(["mark-hard-terminated"], d)
    rec = run_record_of(d)
    assert_conforms(rec, "C")
    a = rec["l4_assessment"]
    assert a["terminal_cause"] == "resource-capped", (
        f"C: terminal_cause={a['terminal_cause']}"
    )
    assert a["provisional_verdict"] == "inconclusive", (
        f"C: provisional={a['provisional_verdict']}"
    )
    assert a["caveats_addressed"] == [], (
        f"C: caveats should be empty, got {a['caveats_addressed']}"
    )
    assert a["error_compounding_defended"] is True, (
        "C: resource cap must NOT flip compounding flag to False"
    )
    print("  C (inconclusive / resource-capped): PASS")


def scenario_d_not_yet_step_capped():
    d = tempfile.mkdtemp(prefix="pdrun_d_")
    # Ran past the provider-independent step cap without converging — this IS a capability signal (couldn't self-correct in work-units). provisional=not-yet.
    ls(
        [
            "init",
            "--task-id",
            "probeD",
            "--codebase-novelty",
            "novel",
            "--req-clarity",
            "fuzzy",
            "--difficulty",
            "high",
            "--attended",
            "false",
            "--target-horizon-steps",
            "60",
            "--step-cap",
            "10",
        ],
        d,
    )
    for _ in range(12):
        ls(["bump-iteration"], d)
    ls(["mark-hard-terminated"], d)
    rec = run_record_of(d)
    assert_conforms(rec, "D")
    a = rec["l4_assessment"]
    assert a["terminal_cause"] == "step-capped", (
        f"D: terminal_cause={a['terminal_cause']}"
    )
    assert a["error_compounding_defended"] is False, "D: step-capped = compounding won"
    assert a["provisional_verdict"] == "not-yet", (
        f"D: provisional={a['provisional_verdict']}"
    )
    print("  D (not-yet / step-capped): PASS")


def scenario_e_dod_guard_and_backstop():
    d = tempfile.mkdtemp(prefix="pdrun_e_")
    ls(["init", "--task-id", "probeE"], d)
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=d)

    # 1) mark-converged WITHOUT an outer review -> REFUSED (DoD guard, ADR #16).
    proc = subprocess.run(
        ["python3", SCRIPT, "mark-converged"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode != 0, (
        "E: mark-converged without an outer review must be REFUSED (rc!=0)"
    )
    refused = json.loads(proc.stdout)
    assert refused.get("refused") is True, f"E: expected refused=true, got {refused}"
    st = ls(["get"], d)
    assert st["status"] != "converged", (
        f"E: status must NOT flip to converged on refusal, got {st['status']}"
    )

    # 2) Honesty backstop: bypass via `set-status converged` (the raw escape hatch the guard does not cover) -> the record must expose the DoD violation.
    ls(["set-status", "converged"], d)
    rec = run_record_of(d)
    assert_conforms(rec, "E")
    assert rec["outcome"] == "converged", f"E: outcome={rec['outcome']}"
    assert rec["dod_satisfied"] is False, (
        "E: converged-without-outer -> dod_satisfied must be False"
    )
    assert rec["l4_assessment"]["outcome_met"] is False, (
        "E: outcome_met must track DoD (False here)"
    )
    assert rec["l4_assessment"]["context_rot_defended"] is False, (
        "E: 0 outer reviews -> context_rot not defended"
    )
    # ADR #38: non-probe + capacity-not-met -> not-a-probe (narrowed semantics — was
    # "non-probe" under the old demand-gate; now "non-probe AND capacity-not-met").
    assert rec["l4_assessment"]["provisional_verdict"] == "not-a-probe", (
        f"E: non-probe + capacity-not-met -> not-a-probe, got {rec['l4_assessment']['provisional_verdict']}"
    )

    # 3) Run the outer ring properly -> mark-converged succeeds, DoD satisfied.
    ls(["record-outer", "--verdict", "pass"], d)
    ls(["mark-converged"], d)  # must NOT refuse now (outer.iterations >= 1)
    rec2 = run_record_of(d)
    assert rec2["dod_satisfied"] is True, (
        "E: after an outer review -> dod_satisfied must be True"
    )
    assert rec2["l4_assessment"]["outcome_met"] is True, (
        "E: outcome_met True once DoD is met"
    )
    print("  E (DoD guard + honesty backstop): PASS")


def scenario_f_upstream_carried():
    """odp2-design D1 (Unit 5 emission wiring): `loop_state.py init --upstream <json>`
    records upstream provenance and the emitted run-record carries it (absent when
    not set, on the free path). Drives the real CLI (same harness as scenarios a-e)."""
    up = {
        "producer": "blueprint-crafting",
        "process_converged": False,
        "profile": "iteration-plan",
    }
    with tempfile.TemporaryDirectory() as td:
        ls(["init", "--task-id", "t", "--upstream", json.dumps(up)], td)
        rec = run_record_of(td)
        assert_conforms(rec, "upstream")
        assert rec.get("upstream") == up, (
            f"run-record dropped the upstream set at init: {rec.get('upstream')}"
        )
    with tempfile.TemporaryDirectory() as td:
        ls(["init", "--task-id", "t2"], td)
        rec = run_record_of(td)
        assert_conforms(rec, "no-upstream")
        assert "upstream" not in rec, (
            f"run-record gained upstream when none was set: {rec.get('upstream')}"
        )
    print(
        "  F: run-record carries upstream from `init --upstream` (absent when unset): ok"
    )


def main():
    print("run_record:")
    failures = []
    scenarios = (
        scenario_a_l4_evidenced,
        scenario_b_not_a_probe,
        scenario_c_inconclusive,
        scenario_d_not_yet_step_capped,
        scenario_e_dod_guard_and_backstop,
        scenario_f_upstream_carried,
    )
    for fn in scenarios:
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        f"\nRun-record pipeline behaves correctly across all {len(scenarios)} scenarios."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
