#!/usr/bin/env python3
"""freeze.py — the freeze operator (lifecycle step 6).

Emits the two frozen artifacts a converged plan-model hands to parallel-development:
  - <name>.queue.md        — the projected plan-queue. parallel-development's
                             plan_queue.py parses the fenced ```json block under
                             ## Items (rich-path-design D1).
  - <name>.run-record.json — the spec run-record (process_converged + the rightness
                             constant), so parallel-development can record upstream
                             provenance (odp2-verdict-design D1).

Composes existing operators (plan_model.project_plan_model_to_queue +
verdict.emit + constraints_check / research_constraints); adds NO new convergence
logic. The outer ring (plan_reviewer) is an LLM eval and is NOT run in CLI mode —
process_converged reflects only what ran (coverage-noted), mirroring verdict.py.
A fully-converged (process_converged=true) freeze is the agent's job (it runs the
outer reviewer); this CLI emits the structural artifacts deterministically.

Pure stdlib. CLI: freeze.py <plan-model.json> [--out-dir <dir>] [--name <name>]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # plan_model, verdict, constraints_check, research_constraints

import plan_model as pm  # noqa: E402
import verdict  # noqa: E402
import constraints_check  # noqa: E402
import research_constraints  # noqa: E402


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def format_queue_md(plan_model, *, frozen_at=None, status="frozen"):
    """Format a plan-model as a .queue.md document.

    parallel-development's plan_queue.py parses the fenced ```json block under
    ## Items (no YAML dependency); the frontmatter is YAML-ish for the human /
    checkpoint view only. Items come from project_plan_model_to_queue (executable
    subset + readable upstream_only + open_decisions incl. resolution + empty
    blueprint_subset).
    """
    frozen_at = frozen_at or _now_iso()
    authority_chain = list(plan_model.get("authority_chain") or [])
    plan_ref = authority_chain[0] if authority_chain else "(none)"
    items = pm.project_plan_model_to_queue(plan_model)
    # rich-path-design D2: stamp each item with a per-item producer marker so pd
    # can detect blueprint-crafting origin (fail-safe to the free path when absent).
    # Emission-only metadata: project_plan_model_item does not add it (the plan-model
    # schema is additionalProperties:false), and lift_queue_item ignores unknown
    # fields, so it never re-enters a plan-model.
    plan_model_version = plan_model.get("plan_model_version", "v1")
    for it in items:
        it["producer"] = "blueprint-crafting"
        it["plan_model_version"] = plan_model_version
    name = plan_model.get("artifact_type", "plan")
    lines = [
        "---",
        "queue_version: v1",
        f"frozen_at: {frozen_at}",
        f"plan_ref: {plan_ref}",
    ]
    if authority_chain:
        lines.append("authority_chain:")
        lines.extend(f"  - {a}" for a in authority_chain)
    else:
        lines.append("authority_chain: []")
    lines.append(f"status: {status}")
    lines += ["---", "", f"# Plan Queue — {name}", ""]
    lines.append(
        "FROZEN plan interpretation emitted by blueprint-crafting `freeze`. "
        "Read-only for the executor; revise only via the Revision Channel "
        "(`status` -> `revising` -> edit + queue_version bump -> `status: frozen`). "
        "See parallel-development `references/plan-driven-mode.md`."
    )
    chain_note = plan_ref if plan_ref != "(none)" else "no authority chain"
    lines += [
        "",
        "## Summary (checkpoint view)",
        "",
        f"{len(items)} item(s). DoD source: {chain_note}.",
        "",
    ]
    lines += [
        "## Items",
        "",
        "```json",
        json.dumps(items, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return "\n".join(lines)


def freeze(plan_model, out_dir, *, name=None, frozen_at=None, outer=None):
    """Emit the frozen artifacts for a plan-model to out_dir.

    Returns (queue_path, run_record_path, research_path). research_path is None
    when the plan-model carries no research sub-object. Runs the inner ring
    (constraints_check or research_constraints) to emit the run-record via
    verdict. The outer ring is an LLM eval; pass its findings via `outer` (a dict
    like {"findings": [...]}) to reach process_converged=true — absent, the record
    coverage-notes the outer ring did not run (process_converged false). The freeze
    CLI passes outer=None (inner-only); produce.py injects the reviewer findings.
    """
    os.makedirs(out_dir, exist_ok=True)
    name = name or plan_model.get("artifact_type", "plan")
    at = plan_model.get("artifact_type", "iteration-plan")
    if at == "research":
        inner = research_constraints.check(plan_model)
        inner["profile"] = "research-v1"
    else:
        inner = constraints_check.check(plan_model)
    rec = verdict.emit(at, inner, outer=outer or {})
    run_record_path = os.path.join(out_dir, f"{name}.run-record.json")
    with open(run_record_path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
    queue_md = format_queue_md(plan_model, frozen_at=frozen_at)
    queue_path = os.path.join(out_dir, f"{name}.queue.md")
    with open(queue_path, "w", encoding="utf-8") as fh:
        fh.write(queue_md)
    # research->inform (charter R5): emit the research payload (claims + sources)
    # as a sibling <name>.research.json so parallel-development can surface the
    # rationale to the Coder. cost_ledger/staging are bc-internal convergence
    # detail — not emitted. None when the plan-model has no research.
    research_path = None
    research = plan_model.get("research") or {}
    if isinstance(research, dict) and research.get("claims"):
        research_path = os.path.join(out_dir, f"{name}.research.json")
        with open(research_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "claims": research.get("claims", []),
                    "sources": research.get("sources", []),
                },
                fh,
                indent=2,
                ensure_ascii=False,
            )
    return queue_path, run_record_path, research_path


def main():
    p = argparse.ArgumentParser(
        prog="freeze.py",
        description="Freeze a plan-model to a .queue.md + .run-record.json",
    )
    p.add_argument("plan_model", help="path to a plan-model JSON file")
    p.add_argument("--out-dir", default=".", help="output directory (default: cwd)")
    p.add_argument(
        "--name", default=None, help="artifact name (default: artifact_type)"
    )
    args = p.parse_args()
    with open(args.plan_model, encoding="utf-8") as fh:
        plan_model = json.load(fh)
    queue_path, run_record_path, research_path = freeze(
        plan_model, args.out_dir, name=args.name
    )
    rec = json.load(open(run_record_path, encoding="utf-8"))
    print(
        json.dumps(
            {
                "queue": os.path.relpath(queue_path),
                "run_record": os.path.relpath(run_record_path),
                "research": os.path.relpath(research_path) if research_path else None,
                "process_converged": rec["process_converged"],
                "rightness": rec["rightness"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
