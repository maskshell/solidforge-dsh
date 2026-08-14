#!/usr/bin/env python3
"""produce.py — the blueprint-crafting production entry point (orchestrator).

One command runs the deterministic convergence chain over an already-authored
plan-model and emits the frozen artifacts for parallel-development:

    constraints_check / research_constraints  ->  verdict.emit  ->  freeze

WHY THIS EXISTS (the gap it closes): blueprint-crafting had no runtime entry
point. The operators are Python libraries plus standalone CLIs that are NOT
shell-pipeable — `normalizer` prints a `{plan_model, coverage}` wrapper while
`constraints_check` / `verdict` / `freeze` each take a bare plan-model, so
chaining them on the shell feeds the wrong shape and fails silently green (the
checker sees artifact_type=None, finds no profile, and returns passed=True). An
LLM invoking the skill therefore explored `infra/scripts/*.py` to reverse-engineer
a CLI that did not exist. `produce.py` is that entry point: it chains the
operators as LIBRARY calls (no subprocess, no shell pipe), so the format mismatch
is bridged in-process and can never silently pass.

DIVISION OF LABOR (what this does NOT do — those stay the LLM's job):
  - Author the Markdown artifact and the plan-model's anchors/items: the LLM.
    `produce.py` takes an already-authored bare `plan-model.json`.
  - The outer ring (`solidforge:plan-reviewer`): an LLM agent, not run here. Pass
    its findings via `--outer` to reach `process_converged=true`; without `--outer`
    the run-record coverage-notes the outer ring did not run (process_converged
    false) — honest, never a silent green.

Pure stdlib. Composes existing operators (adds no convergence logic); the heavy
lifting is `freeze.freeze(..., outer=...)`, which already runs the inner ring +
verdict internally. `produce.py` is the thin orchestrator shell + the `--outer`
seam + a summary exit code.

CLI: produce.py <plan-model.json> [--out-dir <dir>] [--name <name>] [--outer <findings.json>]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, HERE
)  # freeze (which imports plan_model, verdict, constraints_check, research_constraints)

import freeze  # noqa: E402


def produce(plan_model, out_dir, *, name=None, outer=None):
    """Run the deterministic chain (inner -> verdict -> freeze) and emit artifacts.

    `outer` is the plan-reviewer findings dict ({"findings": [...]}), or None for
    inner-only. Returns the freeze.freeze() 3-tuple (queue_path, run_record_path,
    research_path). Thin wrapper over freeze.freeze(outer=...) — kept as a named
    entry so callers (tests, a future GUI) need not know the freeze kwarg."""
    return freeze.freeze(plan_model, out_dir, name=name, outer=outer)


def main():
    p = argparse.ArgumentParser(
        prog="produce.py",
        description=(
            "Production entry point: converge an authored plan-model and emit the "
            "frozen .queue.md + .run-record.json for parallel-development."
        ),
    )
    p.add_argument(
        "plan_model",
        help="path to a bare plan-model JSON (already authored: artifact_type + items + authority_chain + anchors)",
    )
    p.add_argument("--out-dir", default=".", help="output directory (default: cwd)")
    p.add_argument(
        "--name", default=None, help="artifact name (default: artifact_type)"
    )
    p.add_argument(
        "--outer",
        default=None,
        help="path to plan-reviewer findings JSON (absent = inner-only; process_converged stays false with an outer-not-run coverage note)",
    )
    args = p.parse_args()
    with open(args.plan_model, encoding="utf-8") as fh:
        plan_model = json.load(fh)
    outer = None
    if args.outer:
        with open(args.outer, encoding="utf-8") as fh:
            outer = json.load(fh)
    queue_path, run_record_path, research_path = produce(
        plan_model, args.out_dir, name=args.name, outer=outer
    )
    rec = json.load(open(run_record_path, encoding="utf-8"))
    print(
        json.dumps(
            {
                "process_converged": rec["process_converged"],
                "rightness": rec["rightness"],
                "queue": os.path.relpath(queue_path),
                "run_record": os.path.relpath(run_record_path),
                "research": os.path.relpath(research_path) if research_path else None,
                "inner_ring": {
                    "passed": rec["inner_ring"]["passed"],
                    "blockers": rec["inner_ring"]["blockers"],
                },
                "outer_ring": {
                    "passed": rec["outer_ring"]["passed"],
                    "blockers": rec["outer_ring"]["blockers"],
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if rec["process_converged"] else 1)


if __name__ == "__main__":
    main()
