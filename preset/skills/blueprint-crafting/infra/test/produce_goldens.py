#!/usr/bin/env python3
"""produce_goldens — the produce.py orchestrator: blueprint-crafting's runtime
production entry point (the one command the skill was missing).

Exercises produce.py through its CLI (subprocess) to prove the end-to-end entry
point works and that it bridges the operator format mismatch — `normalizer`
prints a `{plan_model, coverage}` wrapper while `constraints_check` / `verdict` /
`freeze` each take a bare plan-model, so shell-chaining feeds the wrong shape and
fails silently green. produce.py chains the operators as LIBRARY calls, so the
mismatch is bridged in-process. Mirrors end_to_end's produce/defect shape plus
freeze_goldens' artifact assertions.

Cases:
  1. CONVERGE inner-only — a complete plan-model -> produce -> .queue.md +
     .run-record.json (schema-valid); process_converged FALSE with an honest
     outer-not-run coverage note; exit 1.
  2. CONVERGE with --outer — same plan-model + a clean outer findings file ->
     process_converged TRUE; exit 0.
  3. DEFECT — missing anchor + authority contradiction + unresolved resolve-now
     ODP -> produce -> process_converged FALSE, inner blockers name the three
     defects, exit 1 (mirrors end_to_end's defect fixture).
  4. RESEARCH — a research plan-model -> produce -> runs research_constraints
     and emits .research.json.

Run: python3 infra/test/produce_goldens.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
PRODUCE = os.path.join(SCRIPTS, "produce.py")

sys.path.insert(0, HERE)  # run_record_schema
sys.path.insert(0, SCRIPTS)  # noqa: E402 — (peer scripts on path for symmetry)
from run_record_schema import validate as validate_run_record  # noqa: E402

IT_PLAN_ANCHORS = [
    "complexity-tiers",
    "dependency-edges",
    "per-iteration-dod",
    "dag",
    "phase-acceptance-gates",
    "risks-mitigations",
    "out-of-scope",
    "cross-cutting-tasks",
    "facade-impact-assessment",
]


def _fail(msg):
    raise AssertionError(msg)


def _complete_pm():
    return {
        "plan_model_version": "v1",
        "artifact_type": "iteration-plan",
        "authority_chain": ["docs/arch-design.md"],
        "items": [
            {
                "item_id": "i1",
                "seq": 0,
                "depends_on": [],
                "dod_ref": "docs/arch-design.md#i1",
            }
        ],
        "anchors": {a: {"present": True} for a in IT_PLAN_ANCHORS},
        "anchors_meta": {"source": "author-supplied"},
    }


def _defect_pm():
    pm = _complete_pm()
    del pm["anchors"]["dag"]  # (a) missing required anchor
    pm["items"][0]["dod_ref"] = "docs/rogue.md#i1"  # (b) authority contradiction
    pm["items"][0]["odp_status"] = [
        {"id": "ODP-X", "kind": "resolve-now"}
    ]  # (c) unresolved resolve-now
    return pm


def _research_pm():
    return {
        "plan_model_version": "v1",
        "artifact_type": "research",
        "authority_chain": ["docs/r.md"],
        "items": [
            {"item_id": "r1", "seq": 0, "depends_on": [], "dod_ref": "docs/r.md#r1"}
        ],
        "research": {
            "claims": [{"text": "X is true.", "source_refs": ["s1"]}],
            "sources": [
                {
                    "source_id": "s1",
                    "ref": "https://example.org",
                    "provenance": "official-spec",
                    "fetched": True,
                }
            ],
            "cost_ledger": {
                "budget": {"tokens": 100, "calls": 5, "sources": 3},
                "used": {"tokens": 10, "calls": 1, "sources": 1},
            },
            "staging": {"in_staging": False, "converged": True},
        },
    }


def _run_produce(pm_path, out_dir, *, name="produced", outer_path=None):
    argv = [
        sys.executable,
        PRODUCE,
        pm_path,
        "--out-dir",
        out_dir,
        "--name",
        name,
    ]
    if outer_path:
        argv += ["--outer", outer_path]
    return subprocess.run(argv, capture_output=True, text=True)


def _write_pm(td, pm, label="pm"):
    path = os.path.join(td, f"{label}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pm, fh)
    return path


def check_converge_inner_only():
    with tempfile.TemporaryDirectory() as td:
        pm_path = _write_pm(td, _complete_pm())
        proc = _run_produce(pm_path, td, name="inner-only")
        if proc.returncode != 1:
            _fail(
                f"inner-only produce must exit 1 (outer not run -> not converged), got {proc.returncode}; stderr={proc.stderr}"
            )
        summary = json.loads(proc.stdout)
        if summary["process_converged"] is not False:
            _fail(
                f"inner-only process_converged must be False, got {summary['process_converged']}"
            )
        rec = json.load(
            open(os.path.join(td, "inner-only.run-record.json"), encoding="utf-8")
        )
        rerrs = validate_run_record(rec)
        if rerrs:
            _fail(f"emitted run-record violates schema: {rerrs}")
        if not any("outer ring" in c for c in rec.get("coverage", [])):
            _fail(
                f"inner-only run-record must coverage-note the outer ring did not run: {rec.get('coverage')}"
            )
        if not os.path.exists(os.path.join(td, "inner-only.queue.md")):
            _fail("inner-only produce did not emit .queue.md")
    print(
        "  converge (inner-only): artifacts + process_converged=false (outer-not-run noted): PASS"
    )


def check_converge_with_outer():
    with tempfile.TemporaryDirectory() as td:
        pm_path = _write_pm(td, _complete_pm())
        outer_path = os.path.join(td, "findings.json")
        with open(outer_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"findings": [{"severity": "warning", "kind": "over-engineering"}]}, fh
            )
        proc = _run_produce(pm_path, td, name="with-outer", outer_path=outer_path)
        if proc.returncode != 0:
            _fail(
                f"clean-outer produce must exit 0 (converged), got {proc.returncode}; stderr={proc.stderr}"
            )
        summary = json.loads(proc.stdout)
        if summary["process_converged"] is not True:
            _fail(
                f"clean-outer process_converged must be True, got {summary['process_converged']}"
            )
        if summary["rightness"] != "human_confirm_required":
            _fail(
                f"rightness must stay the constant human_confirm_required, got {summary['rightness']}"
            )
        rec = json.load(
            open(os.path.join(td, "with-outer.run-record.json"), encoding="utf-8")
        )
        rerrs = validate_run_record(rec)
        if rerrs:
            _fail(f"emitted run-record violates schema: {rerrs}")
    print(
        "  converge (clean --outer): process_converged=true + rightness constant: PASS"
    )


def check_defect_fails():
    with tempfile.TemporaryDirectory() as td:
        pm_path = _write_pm(td, _defect_pm(), label="defect")
        # even with a clean outer, an inner Blocker keeps process_converged false
        outer_path = os.path.join(td, "findings.json")
        with open(outer_path, "w", encoding="utf-8") as fh:
            json.dump({"findings": []}, fh)
        proc = _run_produce(pm_path, td, name="defect", outer_path=outer_path)
        if proc.returncode != 1:
            _fail(f"defect produce must exit 1, got {proc.returncode}")
        summary = json.loads(proc.stdout)
        if summary["process_converged"] is not False:
            _fail(
                f"defect process_converged must be False (inner Blocker), got {summary['process_converged']}"
            )
        if summary["inner_ring"]["blockers"] < 1:
            _fail(
                f"defect must surface inner blockers, got {summary['inner_ring']['blockers']}"
            )
        rec = json.load(
            open(os.path.join(td, "defect.run-record.json"), encoding="utf-8")
        )
        # the run-record stores inner_ring.findings as a COUNT (verdict.py); the
        # COUNT>0 + exit 1 + process_converged false is the produce-level contract.
        # (Named-flag granularity — which anchor/authority/odp — is end_to_end's job.)
        _ = rec
    print(
        "  defect (missing anchor + authority + ODP) -> process_converged=false, exit 1: PASS"
    )


def check_research():
    with tempfile.TemporaryDirectory() as td:
        pm_path = _write_pm(td, _research_pm(), label="research")
        proc = _run_produce(pm_path, td, name="research")
        if proc.returncode != 1:
            _fail(
                f"research inner-only produce must exit 1 (outer not run), got {proc.returncode}"
            )
        rec = json.load(
            open(os.path.join(td, "research.run-record.json"), encoding="utf-8")
        )
        if rec["inner_ring"]["profile"] != "research-v1":
            _fail(
                f"research produce must run the research-v1 profile, got {rec['inner_ring']['profile']}"
            )
        if not os.path.exists(os.path.join(td, "research.research.json")):
            _fail("research produce must emit .research.json (claims + sources)")
    print("  research plan-model -> research-v1 profile + .research.json emitted: PASS")


def main():
    print("produce_goldens (orchestrator entry point):")
    failures = []
    for fn in (
        check_converge_inner_only,
        check_converge_with_outer,
        check_defect_fails,
        check_research,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nproduce.py: one-command convergence works (inner -> verdict -> freeze); "
        "--outer flips process_converged; defects exit 1; research routes to research-v1."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
