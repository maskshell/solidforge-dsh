#!/usr/bin/env python3
"""loop_state.py — state machine + circuit breakers for the convergence loop.

The single source of truth for inner-ring iteration counts, error fingerprints (Thrashing detection), token/time/cost budgets, the append-only event log, and the run-record / L4-assessment rollup. Lives at <project>/.solidforge/loop/loop-state.json (gitignored, derived state).

Invoked two ways:
  - by the orchestrator (SKILL.md / convergent-loop.md) at well-defined points:
      init / bump-iteration / reset-inner / set-snapshot / add-budget / set-status / mark-escalation / mark-suspend / mark-hard-terminated / mark-converged / set-blueprint-version / record-outer / mark-rollback / run-record
  - by hooks and the arch-contract gate to query/record:
      gate-fail <fingerprint>   record + check-breakers (used by fast_gate)
      record-fingerprint <fp>   record only
      check-breakers            action token only
      summary                   one-line folded summary
      get                       dump full JSON

Every anchor also appends to the append-only `events[]` log (the temporal sequence of breaker firings / outer verdicts / rollbacks — see build_run_record).

Breaker priority: hard-terminate > escalate > degrade/suspend > ok.
  - hard-terminate : any global budget cap hit (token_T / time_W / cost_C)
  - escalate       : any fingerprint count >= thrash_N (the inner->outer exception)
  - degrade        : inner.iteration >= cap_M (split / narrow scope)
  - suspend        : cap_M reached AND budget near exhaustion (>=80% of a cap)

Pure stdlib. Exits 0 on success; non-zero only on argument/IO errors.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# Defaults (overridable via `init` flags)
DEFAULT_CAP_M = 8
DEFAULT_THRASH_N = 3
DEFAULT_TOKEN_CAP_T = 2_000_000
DEFAULT_TIME_CAP_W = 1800
DEFAULT_COST_CAP_C = 5.0
BUDGET_NEAR_RATIO = 0.8
EVENT_CAP = 1000
DEFAULT_TARGET_HORIZON = 60
DEFAULT_STEP_CAP_S = 200
# Autonomous-commit policy (L4: remove the per-commit human stall).
# Applied by the orchestrator at convergence — feature branch, post-gate, templated message.
# See references/plan-driven-mode.md §Commit policy.
DEFAULT_COMMIT_POLICY = "auto-per-stage"


def project_root():
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def state_dir():
    return os.path.join(project_root(), ".solidforge", "loop")


def state_file():
    return os.path.join(state_dir(), "loop-state.json")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_fingerprint(raw):
    """Stable fingerprint: project-relative + rule id + message stem, no
    shifting line numbers."""
    s = str(raw).strip()
    s = re.sub(r":\d+(?=:|(?=\s)|$)", "", s)  # drop :123 line refs
    s = re.sub(r"\bline\s+\d+", "line N", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def default_state(
    task_id="task", blueprint_ref=None, blueprint_version="v0", upstream=None
):
    return {
        "task_id": task_id,
        "task_started_at": now_iso(),
        "blueprint_ref": blueprint_ref,
        "blueprint_version": blueprint_version,
        "upstream": upstream,
        "inner": {
            "iteration": 0,
            "cap_M": DEFAULT_CAP_M,
            "fingerprint_log": [],
            "thrash_N": DEFAULT_THRASH_N,
            "last_snapshot": None,
        },
        "outer": {"iterations": 0, "last_verdict": None},
        "budget": {
            "token_used": 0,
            "token_cap_T": DEFAULT_TOKEN_CAP_T,
            "elapsed_seconds": 0,
            "time_cap_W": DEFAULT_TIME_CAP_W,
            "cost_used": 0.0,
            "cost_cap_C": DEFAULT_COST_CAP_C,
        },
        "status": "inner_running",
        "escalation": None,
        "suspend": None,
        "blueprint_revision": None,
        "events": [],
        "task": None,
        "step_cap_S": DEFAULT_STEP_CAP_S,
        "commit_policy": DEFAULT_COMMIT_POLICY,
    }


def load():
    path = state_file()
    if not os.path.exists(path):
        return default_state()
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(state):
    os.makedirs(state_dir(), exist_ok=True)
    with open(state_file(), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


# --- mutations ---------------------------------------------------------------


def record_fingerprint(state, raw_fp):
    inner = state.setdefault("inner", {})
    log = inner.setdefault("fingerprint_log", [])
    fp = normalize_fingerprint(raw_fp)
    for entry in log:
        if entry.get("fingerprint") == fp:
            entry["count"] = entry.get("count", 0) + 1
            entry["last_at"] = now_iso()
            return fp
    log.append({"fingerprint": fp, "count": 1, "last_at": now_iso()})
    return fp


def check_breakers(state):
    """Return (action, reason). action in ok|degrade|escalate|suspend|hard-terminate."""
    b = state.get("budget", {})
    inner = state.get("inner", {})

    used_tok = b.get("token_used", 0)
    cap_T = b.get("token_cap_T", DEFAULT_TOKEN_CAP_T)
    elapsed = b.get("elapsed_seconds", 0)
    cap_W = b.get("time_cap_W", DEFAULT_TIME_CAP_W)
    used_cost = b.get("cost_used", 0.0)
    cap_C = b.get("cost_cap_C", DEFAULT_COST_CAP_C)

    # Provider-independent hard limit: total steps (inner + outer). Wall-clock time below is a hang/cost guard only — it confounds provider throughput and must not be the capability/convergence signal. See ADR #6, #13.
    steps_total = inner.get("iteration", 0) + state.get("outer", {}).get(
        "iterations", 0
    )
    cap_S = state.get("step_cap_S", DEFAULT_STEP_CAP_S)
    if cap_S and steps_total >= cap_S:
        return "hard-terminate", f"step cap exhausted ({steps_total}/{cap_S})"

    if used_tok >= cap_T:
        return "hard-terminate", f"token budget exhausted ({used_tok}/{cap_T})"
    if elapsed >= cap_W:
        return "hard-terminate", f"time budget exhausted ({elapsed}s/{cap_W}s)"
    if used_cost >= cap_C:
        return "hard-terminate", f"cost budget exhausted ({used_cost}/{cap_C})"

    log = inner.get("fingerprint_log", [])
    N = inner.get("thrash_N", DEFAULT_THRASH_N)
    tripped = [e for e in log if e.get("count", 0) >= N]
    if tripped:
        names = ", ".join(e["fingerprint"] for e in tripped)
        return "escalate", f"thrashing on repeated root cause (>= {N}x): {names}"

    it = inner.get("iteration", 0)
    M = inner.get("cap_M", DEFAULT_CAP_M)
    if it >= M:
        near = (
            used_tok >= BUDGET_NEAR_RATIO * cap_T
            or elapsed >= BUDGET_NEAR_RATIO * cap_W
            or used_cost >= BUDGET_NEAR_RATIO * cap_C
        )
        if near:
            return (
                "suspend",
                f"iteration cap reached ({it}/{M}) and budget near exhaustion",
            )
        return "degrade", f"iteration cap reached ({it}/{M})"

    return "ok", "all clear"


def summary(state):
    inner = state.get("inner", {})
    log = inner.get("fingerprint_log", [])
    top = sorted(log, key=lambda e: e.get("count", 0), reverse=True)[:3]
    fp_part = (
        "; ".join(f"{e['fingerprint']} x{e['count']}" for e in top)
        if top
        else "no recurring failures"
    )
    return (
        f"Inner status={state.get('status')}, "
        f"iteration {inner.get('iteration', 0)}/{inner.get('cap_M', DEFAULT_CAP_M)}, "
        f"last_snapshot={inner.get('last_snapshot')}. Fingerprints: {fp_part}."
    )


# --- event log + run record (the L4-evidence rollup) ------------------------

NON_OK_BREAKERS = ("escalate", "degrade", "suspend", "hard-terminate")


def record_event(state, etype, detail=None):
    """Append to the append-only event log (bounded to the last EVENT_CAP)."""
    events = state.setdefault("events", [])
    events.append(
        {
            "at": now_iso(),
            "type": etype,
            "iteration": state.get("inner", {}).get("iteration", 0),
            "detail": detail or {},
        }
    )
    if len(events) > EVENT_CAP:
        del events[: len(events) - EVENT_CAP]


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def runs_dir():
    return os.path.join(state_dir(), "runs")


def derive_outcome(status):
    if status == "converged":
        return "converged"
    if status == "hard_terminated":
        return "hard_terminated"
    if status == "suspended":
        return "suspended"
    return "non-terminal"


def derive_terminal_cause(state, outcome, steps_total):
    """Provider-normalized classification of WHY the run ended. Drives the
    l4_assessment verdict so a slow-provider resource cap is 'inconclusive'
    (not a capability failure), distinct from a step-cap (a capability signal).
    See ADR #13."""
    if outcome == "converged":
        return "converged"
    if outcome == "suspended":
        return "suspended"
    if outcome == "non-terminal":
        return "non-terminal"
    # hard_terminated: which axis actually tripped?
    b = state.get("budget", {})
    if (
        b.get("token_used", 0) >= b.get("token_cap_T", DEFAULT_TOKEN_CAP_T)
        or b.get("elapsed_seconds", 0) >= b.get("time_cap_W", DEFAULT_TIME_CAP_W)
        or b.get("cost_used", 0.0) >= b.get("cost_cap_C", DEFAULT_COST_CAP_C)
    ):
        return "resource-capped"
    cap_S = state.get("step_cap_S", DEFAULT_STEP_CAP_S)
    if cap_S and steps_total >= cap_S:
        return "step-capped"
    return "manual"


def build_run_record(state):
    """Aggregate events + state into the normalized run record (conforms to infra/schemas/run-record.schema.json). Includes the computed l4_assessment block — the instrumented form of references/maturity.md's rubric."""
    inner = state.get("inner", {})
    outer = state.get("outer", {})
    b = state.get("budget", {})
    task = state.get("task")
    status = state.get("status", "")
    outcome = derive_outcome(status)
    events = state.get("events", [])

    breakers = []
    outer_verdicts = []
    rollbacks = []
    for e in events:
        et = e.get("type")
        d = e.get("detail") or {}
        if et == "gate-fail" and d.get("action") in NON_OK_BREAKERS:
            breakers.append(
                {
                    "action": d["action"],
                    "reason": d.get("fingerprint") or d.get("reason") or "fingerprint",
                    "at_iteration": e.get("iteration", 0),
                    "at": e.get("at", ""),
                }
            )
        elif et == "breaker" and d.get("action") in NON_OK_BREAKERS:
            breakers.append(
                {
                    "action": d["action"],
                    "reason": d.get("reason", "breaker"),
                    "at_iteration": e.get("iteration", 0),
                    "at": e.get("at", ""),
                }
            )
        elif et == "outer-verdict":
            outer_verdicts.append(
                {
                    "verdict": d.get("verdict"),
                    "findings_count": d.get("findings_count", 0),
                    "at": e.get("at", ""),
                }
            )
        elif et == "rollback":
            rollbacks.append({"lost_uc": d.get("lost_uc", ""), "at": e.get("at", "")})

    log = inner.get("fingerprint_log", [])
    top = sorted(log, key=lambda x: x.get("count", 0), reverse=True)[:3]
    top_fps = [
        {"fingerprint": x.get("fingerprint", ""), "count": x.get("count", 1)}
        for x in top
    ]

    inner_it = inner.get("iteration", 0)
    outer_it = outer.get("iterations", 0)
    steps_total = inner_it + outer_it
    target = (task or {}).get("target_horizon_steps", DEFAULT_TARGET_HORIZON)

    horizon_met = steps_total >= target
    terminal_cause = derive_terminal_cause(state, outcome, steps_total)
    # Defense flags are decoupled from raw outcome and driven by terminal_cause, so a slow-provider resource cap does NOT flip them to False (ADR #13).
    outer_reviews = len(outer_verdicts)
    # DoD honesty backstop (ADR #16): "converged" without an outer-ring review did NOT meet the Definition of Done. mark-converged now refuses that (primary guard); this is the defense-in-depth for legacy/bypassed states (e.g. `set-status converged`). outcome_met tracks DoD, not raw status, and dod_satisfied exposes the verdict at the top level.
    dod_satisfied = (outcome == "converged") and (outer_reviews >= 1)
    outcome_met = dod_satisfied
    error_compounding_defended = terminal_cause != "step-capped"
    goal_drift_defended = terminal_cause in ("converged", "resource-capped")
    context_rot_defended = outer_reviews >= 1

    is_l4_probe = bool(
        task
        and task.get("codebase_novelty") == "novel"
        and task.get("requirement_clarity") == "fuzzy"
        and task.get("difficulty") == "high"
        and task.get("attended") is False
    )
    # Capacity/demand split (fedaot-wiki ai-coding-agent-maturity re-alignment, ADR #38):
    # capacity = 3-degradation defense under convergence. horizon + is_l4_probe are DEMAND
    # (run-lifetime + task-difficulty), NOT capacity ("运行生存期是 demand 的时间外显量纲").
    capacity_l4 = (
        terminal_cause == "converged"
        and error_compounding_defended
        and goal_drift_defended
        and context_rot_defended
    )
    if capacity_l4:
        provisional = "l4-evidenced"  # capacity met — regardless of demand
    elif terminal_cause == "resource-capped":
        provisional = "inconclusive"
    elif is_l4_probe:
        provisional = "not-yet"  # demanding run, capacity not yet met
    else:
        provisional = (
            "not-a-probe"  # non-probe + capacity-not-met (enum kept for back-compat)
        )
    # caveat-2 is demand-weighted (ADR #38): only a probe-grade (is_l4_probe)
    # capacity-met run retires it. A non-probe l4-evidenced run (e.g. self-edit)
    # has capacity but lacks probe-grade demand → does NOT retire caveat-2.
    caveats = (
        ["caveat-2-unproven-at-scale"]
        if (provisional == "l4-evidenced" and is_l4_probe)
        else []
    )

    record = {
        "task_id": state.get("task_id", "task"),
        "started_at": state.get("task_started_at", ""),
        "ended_at": now_iso(),
        # Process/Outcome split (paper §4.2 / §6): rightness is a CONSTANT the
        # deterministic emitter always writes and the agent can never vary —
        # process_converged is never a correctness claim.
        "rightness": "human_confirm_required",
        "outcome": outcome,
        "final_status": status or "unknown",
        "converged": outcome == "converged",
        "dod_satisfied": dod_satisfied,
        "steps": {"inner": inner_it, "outer": outer_it, "total": steps_total},
        "budget": {
            "token_used": b.get("token_used", 0),
            "token_cap": b.get("token_cap_T", DEFAULT_TOKEN_CAP_T),
            "time_used": b.get("elapsed_seconds", 0),
            "time_cap": b.get("time_cap_W", DEFAULT_TIME_CAP_W),
            "cost_used": b.get("cost_used", 0.0),
            "cost_cap": b.get("cost_cap_C", DEFAULT_COST_CAP_C),
        },
        "breakers_fired": breakers,
        "top_fingerprints": top_fps,
        "outer_verdicts": outer_verdicts,
        "rollbacks": rollbacks,
        "l4_assessment": {
            "is_l4_probe": is_l4_probe,
            "provisional_verdict": provisional,
            "terminal_cause": terminal_cause,
            "horizon_met": horizon_met,
            "outcome_met": outcome_met,
            "error_compounding_defended": error_compounding_defended,
            "goal_drift_defended": goal_drift_defended,
            "context_rot_defended": context_rot_defended,
            "steps_total": steps_total,
            "target_horizon_steps": target,
            "breakers_fired_count": len(breakers),
            "rollbacks_count": len(rollbacks),
            "outer_reviews": outer_reviews,
            "caveats_addressed": caveats,
            "human_confirm_required": True,
        },
    }
    if state.get("blueprint_ref"):
        record["blueprint_ref"] = state["blueprint_ref"]
    if state.get("blueprint_version") and state.get("blueprint_version") != "v0":
        record["blueprint_version"] = state["blueprint_version"]
    if state.get("upstream"):
        record["upstream"] = state["upstream"]
    if task:
        record["task"] = {
            "codebase_novelty": task.get("codebase_novelty"),
            "requirement_clarity": task.get("requirement_clarity"),
            "difficulty": task.get("difficulty"),
            "attended": task.get("attended"),
            "declared_at": task.get("declared_at", ""),
            "target_horizon_steps": task.get(
                "target_horizon_steps", DEFAULT_TARGET_HORIZON
            ),
        }
    return record


# --- CLI ---------------------------------------------------------------------


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="loop_state.py", description="convergence-loop state machine"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s_init = sub.add_parser("init")
    s_init.add_argument("--task-id", default="task")
    s_init.add_argument("--blueprint-ref", default=None)
    s_init.add_argument("--blueprint-version", default="v0")
    s_init.add_argument(
        "--upstream",
        default=None,
        help="upstream-provenance JSON object (rich path; from `plan_queue.py upstream-provenance <queue_ref>`)",
    )
    s_init.add_argument("--cap-m", type=int, default=DEFAULT_CAP_M)
    s_init.add_argument("--thrash-n", type=int, default=DEFAULT_THRASH_N)
    s_init.add_argument("--token-cap", type=int, default=DEFAULT_TOKEN_CAP_T)
    s_init.add_argument("--time-cap", type=int, default=DEFAULT_TIME_CAP_W)
    s_init.add_argument("--cost-cap", type=float, default=DEFAULT_COST_CAP_C)
    s_init.add_argument(
        "--codebase-novelty", choices=["novel", "familiar"], default=None
    )
    s_init.add_argument("--req-clarity", choices=["fuzzy", "specd"], default=None)
    s_init.add_argument(
        "--difficulty", choices=["high", "moderate", "low"], default=None
    )
    s_init.add_argument("--attended", choices=["true", "false"], default=None)
    s_init.add_argument(
        "--target-horizon-steps", type=int, default=DEFAULT_TARGET_HORIZON
    )
    s_init.add_argument("--step-cap", type=int, default=DEFAULT_STEP_CAP_S)
    s_init.add_argument(
        "--commit",
        choices=["auto-per-stage", "manual", "none"],
        default=DEFAULT_COMMIT_POLICY,
        help="autonomous-commit policy applied at convergence (default: auto-per-stage)",
    )

    sub.add_parser("bump-iteration")
    s_fp = sub.add_parser("record-fingerprint")
    s_fp.add_argument("fingerprint")
    s_gf = sub.add_parser("gate-fail")
    s_gf.add_argument("fingerprint")

    sub.add_parser("reset-inner")
    s_snap = sub.add_parser("set-snapshot")
    s_snap.add_argument("ref")

    s_bud = sub.add_parser("add-budget")
    s_bud.add_argument("--tokens", type=int, default=0)
    s_bud.add_argument("--seconds", type=int, default=0)
    s_bud.add_argument("--cost", type=float, default=0.0)

    s_st = sub.add_parser("set-status")
    s_st.add_argument("status")

    s_bp = sub.add_parser("set-blueprint-version")
    s_bp.add_argument("version")

    s_susp = sub.add_parser("mark-suspend")
    s_susp.add_argument("--blueprint-defect", action="store_true")
    s_susp.add_argument("--reason", default="manual suspend")

    sub.add_parser("mark-escalation")
    sub.add_parser("mark-hard-terminated")
    sub.add_parser("mark-converged")

    s_ro = sub.add_parser("record-outer")
    s_ro.add_argument(
        "--verdict",
        # adversarial-stalemate: the different-family multi-round debate hit max_adversarial_rounds
        # without convergence (ADR #40 (e)). NEVER resolves by silent-pick — the wrapper
        # escalates to human. Added by hetero-orchestration Phase 1 (P1-1).
        choices=[
            "pass",
            "rewrite",
            "intent-drift",
            "blueprint-defect",
            "visual-drift",
            "adversarial-stalemate",
        ],
        required=True,
    )
    s_ro.add_argument("--findings", type=int, default=0)
    s_ro.add_argument("--notes", default="")

    s_rb = sub.add_parser("mark-rollback")
    s_rb.add_argument("--lost-uc", default="")

    s_rr = sub.add_parser("run-record")
    s_rr.add_argument("--out", default=None)

    sub.add_parser("check-breakers")
    sub.add_parser("summary")
    sub.add_parser("get")

    args = p.parse_args(argv)
    state = load()

    if args.cmd == "init":
        upstream = None
        if args.upstream:
            try:
                upstream = json.loads(args.upstream)
            except json.JSONDecodeError:
                sys.exit(
                    f"error: --upstream must be a JSON object, got: {args.upstream}"
                )
            if not isinstance(upstream, dict):
                sys.exit(
                    f"error: --upstream must be a JSON object, got: {type(upstream).__name__}"
                )
        state = default_state(
            args.task_id, args.blueprint_ref, args.blueprint_version, upstream=upstream
        )
        state["inner"]["cap_M"] = args.cap_m
        state["inner"]["thrash_N"] = args.thrash_n
        state["budget"]["token_cap_T"] = args.token_cap
        state["budget"]["time_cap_W"] = args.time_cap
        state["budget"]["cost_cap_C"] = args.cost_cap
        if args.codebase_novelty:
            state["task"] = {
                "codebase_novelty": args.codebase_novelty,
                "requirement_clarity": args.req_clarity or "specd",
                "difficulty": args.difficulty or "low",
                "attended": (args.attended != "false") if args.attended else True,
                "declared_at": now_iso(),
                "target_horizon_steps": args.target_horizon_steps,
            }
        state["step_cap_S"] = args.step_cap
        state["commit_policy"] = args.commit
        record_event(state, "init", {"task_declared": bool(state.get("task"))})
        save(state)
        print(json.dumps({"ok": True, "state_file": state_file()}))

    elif args.cmd == "bump-iteration":
        state.setdefault("inner", {})["iteration"] = (
            state.get("inner", {}).get("iteration", 0) + 1
        )
        record_event(state, "iteration")
        save(state)
        print(json.dumps({"iteration": state["inner"]["iteration"]}))

    elif args.cmd == "record-fingerprint":
        fp = record_fingerprint(state, args.fingerprint)
        save(state)
        print(json.dumps({"fingerprint": fp}))

    elif args.cmd == "gate-fail":
        fp = record_fingerprint(state, args.fingerprint)
        action, reason = check_breakers(state)
        record_event(
            state, "gate-fail", {"fingerprint": fp, "action": action, "reason": reason}
        )
        save(state)
        print(
            json.dumps(
                {
                    "recorded": fp,
                    "action": action,
                    "reason": reason,
                    "summary": summary(state),
                }
            )
        )

    elif args.cmd == "reset-inner":
        inner = state.setdefault("inner", {})
        inner["iteration"] = 0
        inner["fingerprint_log"] = []
        state["status"] = "inner_running"
        save(state)
        print(json.dumps({"reset": True}))

    elif args.cmd == "set-snapshot":
        state.setdefault("inner", {})["last_snapshot"] = args.ref
        record_event(state, "snapshot", {"ref": args.ref})
        save(state)
        print(json.dumps({"last_snapshot": args.ref}))

    elif args.cmd == "add-budget":
        b = state.setdefault("budget", {})
        b["token_used"] = b.get("token_used", 0) + args.tokens
        b["elapsed_seconds"] = b.get("elapsed_seconds", 0) + args.seconds
        b["cost_used"] = round(b.get("cost_used", 0.0) + args.cost, 6)
        save(state)
        print(json.dumps({"budget": b}))

    elif args.cmd == "set-status":
        state["status"] = args.status
        save(state)
        print(json.dumps({"status": args.status}))

    elif args.cmd == "set-blueprint-version":
        state["blueprint_version"] = args.version
        state.setdefault("blueprint_revision", {})
        state["blueprint_revision"]["new_version"] = args.version
        record_event(state, "blueprint-revised", {"version": args.version})
        save(state)
        print(json.dumps({"blueprint_version": args.version}))

    elif args.cmd == "mark-escalation":
        action, reason = check_breakers(state)
        state["status"] = "escalated"
        state["escalation"] = {
            "reason": reason,
            "fingerprints": state.get("inner", {}).get("fingerprint_log", []),
        }
        record_event(state, "breaker", {"action": action, "reason": reason})
        save(state)
        print(json.dumps({"status": "escalated", "reason": reason}))

    elif args.cmd == "mark-suspend":
        state["status"] = "suspended"
        state["suspend"] = {
            "reason": args.reason,
            "is_blueprint_defect": args.blueprint_defect,
            "diagnosis": summary(state),
        }
        record_event(state, "breaker", {"action": "suspend", "reason": args.reason})
        save(state)
        print(
            json.dumps(
                {"status": "suspended", "is_blueprint_defect": args.blueprint_defect}
            )
        )

    elif args.cmd == "mark-hard-terminated":
        action, reason = check_breakers(state)
        state["status"] = "hard_terminated"
        state["suspend"] = {
            "reason": f"hard-terminate: {reason}",
            "diagnosis": summary(state),
        }
        record_event(state, "breaker", {"action": action, "reason": reason})
        save(state)
        print(json.dumps({"status": "hard_terminated", "reason": reason}))

    elif args.cmd == "mark-converged":
        # DoD guard (ADR #16): convergence REQUIRES the outer ring to have run (record-outer).
        # Refuse fail-loud — like blueprint_guard / counters — so a false "converged" is impossible regardless of how the orchestrator behaved (e.g. direct execution that bypasses bump-iteration / record-outer).
        # No state mutation on refusal; the error tells the orchestrator what to do.
        if state.get("outer", {}).get("iterations", 0) < 1:
            msg = (
                "DoD violation (ADR #16): mark-converged refused — no outer-ring "
                "review recorded (outer.iterations=0). The Definition of Done requires "
                "the outer ring: spawn the code-reviewer subagent and call "
                "`record-outer --verdict <v>` first, then mark-converged; or "
                "`set-status inner_converged` if you are not at the terminal phase. "
                "status left unchanged."
            )
            print(
                json.dumps(
                    {"status": state.get("status"), "refused": True, "error": msg}
                )
            )
            sys.exit(1)
        state["status"] = "converged"
        record_event(state, "converged")
        save(state)
        print(json.dumps({"status": "converged"}))

    elif args.cmd == "record-outer":
        outer = state.setdefault("outer", {})
        outer["iterations"] = outer.get("iterations", 0) + 1
        outer["last_verdict"] = args.verdict
        record_event(
            state,
            "outer-verdict",
            {
                "verdict": args.verdict,
                "findings_count": args.findings,
                "notes": args.notes,
            },
        )
        save(state)
        print(
            json.dumps(
                {"outer_iterations": outer["iterations"], "last_verdict": args.verdict}
            )
        )

    elif args.cmd == "mark-rollback":
        record_event(state, "rollback", {"lost_uc": args.lost_uc})
        save(state)
        print(json.dumps({"rollback": True, "lost_uc": args.lost_uc}))

    elif args.cmd == "run-record":
        record = build_run_record(state)
        os.makedirs(runs_dir(), exist_ok=True)
        out_path = args.out or os.path.join(
            runs_dir(), f"{state.get('task_id', 'task')}-{stamp()}.json"
        )
        blob = json.dumps(record, indent=2, ensure_ascii=False)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(blob + "\n")
        print(blob)

    elif args.cmd == "check-breakers":
        action, reason = check_breakers(state)
        print(json.dumps({"action": action, "reason": reason}))

    elif args.cmd == "summary":
        print(summary(state))

    elif args.cmd == "get":
        print(json.dumps(state, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
