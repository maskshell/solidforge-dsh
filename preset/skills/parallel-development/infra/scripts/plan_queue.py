#!/usr/bin/env python3
"""plan_queue.py — multi-item plan chaining: queue bookkeeping + cross-item breaker.

Companion to loop_state.py. loop_state drives convergence WITHIN one item; plan_queue drives progress ACROSS items of a frozen plan-queue. The two layers compose: per-item lifecycle uses loop_state unchanged; plan_queue tracks which item is current, item-level outcomes, and the cross-item breaker.

Two artifacts, cleanly separated (see references/plan-driven-mode.md):
  - Frozen STRUCTURE: docs/plan-queues/<name>.queue.md — read-only guarded by blueprint_guard.py (status: frozen). Holds the immutable plan interpretation (item_id/seq/depends_on/dod_ref/blueprint_subset/...). plan_queue READS it.
  - Mutable STATUS: <project>/.solidforge/loop/plan-queue-state.json (gitignored, derived). Holds per-item status + breaker counters ONLY. plan_queue OWNS it; it never duplicates structure.

The markdown queue carries its structure in a fenced ```json block under "## Items" so this script can parse it with stdlib json (no YAML dependency).

CLI mirrors loop_state.py conventions. Pure stdlib. Exits 0 on success; non-zero only on argument/IO/parse errors.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_CAP_CONSECUTIVE = 3  # K: consecutive item blocks on same root-cause -> suspend
DEFAULT_CAP_TOTAL_ITEMS = 50  # runaway-plan guard
EVENT_CAP = 500

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_CONVERGED = "converged"
STATUS_BLOCKED = "blocked"
STATUS_SKIPPED = "skipped"
TERMINAL = (STATUS_CONVERGED, STATUS_BLOCKED, STATUS_SKIPPED)

JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

# loop_state.py lives alongside this script. The claim/complete/block/skip hooks
# subprocess it to drive per-item bookkeeping deterministically (plan-driven-mode.md
# wiring — the agent no longer manually inits/marks; see docs/plan-driven-loop-state-wiring-design.md).
# Mirror of fast_gate.py's loop_state subprocess pattern.
LOOP_STATE_PY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "loop_state.py"
)


def project_root():
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def state_dir():
    return os.path.join(project_root(), ".solidforge", "loop")


def state_file():
    return os.path.join(state_dir(), "plan-queue-state.json")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_loop_state(argv):
    """subprocess `loop_state.py <argv>` at the project root. Returns (rc, output).

    Drives per-item loop_state bookkeeping deterministically from the plan_queue
    claim/complete/block/skip hooks. rc != 0 means loop_state refused or errored (e.g.
    mark-converged refusal when the outer ring didn't run — ADR #16); callers fail loud.
    """
    proc = subprocess.run(
        [sys.executable, LOOP_STATE_PY] + argv,
        cwd=project_root(),
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def normalize_fingerprint(raw):
    """Stable root-cause class: lowercase, collapse whitespace, drop line refs.
    Mirrors loop_state.normalize_fingerprint so cross-item thrash is comparable."""
    s = str(raw).strip()
    s = re.sub(r":\d+(?=:|(?=\s)|$)", "", s)
    s = re.sub(r"\bline\s+\d+", "line N", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


# --- frozen-structure parsing (read-only) ------------------------------------


def resolve_path(ref):
    """Resolve a queue_ref that may be project-relative. Prefer CWD, then project_root() (SOLIDFORGE_PROJECT_DIR) — mirrors how loop_state roots state."""
    if not ref:
        return ref
    if os.path.isabs(ref) or os.path.exists(ref):
        return ref
    return os.path.join(project_root(), ref)


def parse_queue_structure(queue_ref):
    """Read the markdown queue, extract the first ```json block under ## Items, return {item_id: {seq, depends_on, title, dod_ref, blueprint_subset, parallel_group, ...}}. Raises ValueError on malformed/missing structure."""
    path = resolve_path(queue_ref)
    if not queue_ref or not os.path.exists(path):
        raise ValueError(f"queue file not found: {queue_ref}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    m = JSON_BLOCK_RE.search(text)
    if not m:
        raise ValueError(
            f"no fenced ```json block found in {queue_ref}; "
            "the queue must carry its item structure in a ```json block under ## Items "
            "(see references/plan-driven-mode.md)"
        )
    try:
        items = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed json block in {queue_ref}: {e}") from e
    if not isinstance(items, list):
        raise ValueError(f"json block in {queue_ref} is not a list")
    structure = {}
    for it in items:
        iid = it.get("item_id")
        if not iid:
            raise ValueError(f"queue item missing item_id: {it}")
        structure[iid] = it
    return structure


def detect_producer(structure):
    """Rich-path detection (rich-path-design D2). Return the producer marker on a
    parsed queue structure, or None when absent — the caller then takes the free
    path. blueprint-crafting's `freeze` stamps every item with
    `producer: blueprint-crafting`; a plain (free-path) queue has no such marker.

    Fail-safe by design: an empty structure, a None structure, or a structure with
    no marker all return None (never raise) — detection must never block, worst case
    the caller re-normalizes (today's free-path behavior)."""
    if not structure:
        return None
    for it in structure.values():
        producer = it.get("producer") if isinstance(it, dict) else None
        if producer:
            return producer
    return None


def build_upstream_provenance(queue_ref):
    """Read bc's sibling .run-record.json and return the upstream-provenance
    sub-object for pd's run-record ({producer, process_converged, profile}), or
    None. Rich path only: None unless the queue is blueprint-crafting-origin
    (detect_producer) AND the sibling <name>.run-record.json exists + carries
    process_converged. Fail-safe: any miss / parse error -> None (pd omits
    `upstream`, validates normally — odp2-verdict-design D1)."""
    try:
        structure = parse_queue_structure(queue_ref)
    except (ValueError, OSError):
        return None
    if detect_producer(structure) != "blueprint-crafting":
        return None
    rr_path = re.sub(r"\.queue\.md$", ".run-record.json", queue_ref or "")
    if not rr_path or not os.path.exists(rr_path):
        return None
    try:
        with open(rr_path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "producer": "blueprint-crafting",
        "process_converged": bool(rec.get("process_converged", False)),
        "profile": (rec.get("inner_ring") or {}).get("profile", ""),
    }


def read_research(research_ref):
    """Read research: SCHEMA-AWARE but NOT schema-gated (charter R5 + R2).

    When the content carries bc's research schema ({claims, sources}), it is
    PARSED for precise identification — the Coder gets the structured claims + the
    sources backing them (充分利用 bc's 成果), not opaque text. When it does not
    (a cited report, a markdown doc, any free-form research), the content is
    returned as-is. The schema is NEVER a gate: non-conforming research is still
    accepted, just less structured. None only when the file is missing/unreadable.

    Returns {kind: "research-json", claims, sources} when bc's schema is present,
    else {kind: "free-form", content}. The research-ref is discovered at the
    orchestration layer (e.g. via the queue's authority_chain)."""
    if not research_ref or not os.path.exists(research_ref):
        return None
    try:
        with open(research_ref, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    # best-effort: bc's structured .research.json -> parse (precise; no gate)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"kind": "free-form", "content": text}
    if isinstance(payload, dict) and ("claims" in payload or "sources" in payload):
        return {
            "kind": "research-json",
            "claims": payload.get("claims") or [],
            "sources": payload.get("sources") or [],
        }
    return {"kind": "free-form", "content": payload}


def queue_name(queue_ref):
    base = os.path.basename(queue_ref or "")
    return re.sub(r"\.queue\.md$", "", base) or "queue"


# --- mutable status state ----------------------------------------------------


def default_state(queue_ref):
    return {
        "queue_ref": queue_ref,
        "queue_name": queue_name(queue_ref),
        "plan_ref": None,
        "total_items": 0,
        "items": {},  # item_id -> {seq, status, attempts, failure_fps}
        "cross_item": {
            "consecutive_failures": 0,
            "cap_consecutive": DEFAULT_CAP_CONSECUTIVE,
            "cap_total_items": DEFAULT_CAP_TOTAL_ITEMS,
        },
        "started_at": now_iso(),
        "status": "chaining",  # chaining|done|suspended|hard_terminated
        "events": [],
    }


def load():
    path = state_file()
    if not os.path.exists(path):
        return default_state(None)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(state):
    os.makedirs(state_dir(), exist_ok=True)
    with open(state_file(), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


def record_event(state, etype, detail=None):
    events = state.setdefault("events", [])
    events.append({"at": now_iso(), "type": etype, "detail": detail or {}})
    if len(events) > EVENT_CAP:
        del events[: len(events) - EVENT_CAP]


def seed_from_structure(state, structure, plan_ref=None):
    """Merge markdown structure into status state. Resume-preserving: existing item statuses are kept; new item_ids seeded pending; dropped item_ids removed. seq is mirrored from structure (status state carries seq for ordering even without re-reading markdown, but depends_on stays in markdown only)."""
    items = state.setdefault("items", {})
    live = set(structure)
    for iid, spec in structure.items():
        if iid not in items:
            items[iid] = {
                "seq": spec.get("seq", 0),
                "status": STATUS_PENDING,
                "attempts": 0,
                "failure_fps": [],
                "odps": {},  # odp_id -> {status, resolution, defaulted} (mutable resolutions)
            }
        else:
            items[iid]["seq"] = spec.get("seq", items[iid].get("seq", 0))
    # rich-path (odp2-verdict-design D2): seed resolved ODPs bc carried (an
    # open_decision with a `resolution`) so `claim` will not re-ask a decision bc
    # already closed. Idempotent + resume-preserving: never overwrites a resolution
    # the operator already set. Plain (free-path) queues carry no resolution -> no-op.
    for iid, spec in structure.items():
        if not isinstance(spec, dict):
            continue
        odps = items[iid].setdefault("odps", {})
        for d in spec.get("open_decisions") or []:
            if not (isinstance(d, dict) and d.get("id") and d.get("resolution")):
                continue
            if d["id"] not in odps:  # don't clobber an operator-set resolution
                odps[d["id"]] = {
                    "status": "resolved",
                    "resolution": d["resolution"],
                    "defaulted": False,
                }
    for iid in [k for k in items if k not in live]:
        del items[iid]
    state["total_items"] = len(structure)
    if plan_ref:
        state["plan_ref"] = plan_ref
    state["queue_name"] = state.get("queue_name") or queue_name(state.get("queue_ref"))
    return state


# --- cross-item breaker ------------------------------------------------------


def check_breaker(state):
    """Return (action, reason). action in ok|suspend|hard-terminate."""
    ci = state.get("cross_item", {})
    total = state.get("total_items", 0)
    cap_total = ci.get("cap_total_items", DEFAULT_CAP_TOTAL_ITEMS)
    if cap_total and total > cap_total:
        return (
            "hard-terminate",
            f"total-items cap exceeded ({total}/{cap_total}); plan likely misread",
        )
    consec = ci.get("consecutive_failures", 0)
    cap_c = ci.get("cap_consecutive", DEFAULT_CAP_CONSECUTIVE)
    if cap_c and consec >= cap_c:
        return (
            "suspend",
            f"consecutive item failures (>= {cap_c}) on repeated root-cause class",
        )
    return "ok", "all clear"


def pick_next(state, structure):
    """Return the next runnable item_id, or None.

    Priority:
      1. any in_progress item (resume an interrupted item);
      2. lowest-seq pending item whose depends_on are all converged;
      3. None.
    Also detects deadlock (pending items remain, none runnable)."""
    items = state.get("items", {})
    # 1. resume in-flight
    for iid, st in items.items():
        if st.get("status") == STATUS_IN_PROGRESS:
            return iid, None
    # 2. lowest-seq pending with deps satisfied
    status_of = {iid: st.get("status") for iid, st in items.items()}
    candidates = [
        iid for iid, st in items.items() if st.get("status") == STATUS_PENDING
    ]

    def deps_ok(iid):
        return all(
            status_of.get(dep) == STATUS_CONVERGED
            for dep in (structure.get(iid, {}).get("depends_on") or [])
        )

    runnable = [iid for iid in candidates if deps_ok(iid)]
    if runnable:
        return min(runnable, key=lambda i: items[i].get("seq", 0)), None
    # 3. deadlock?
    if candidates:
        blocked_deps = {
            iid: [
                d
                for d in (structure.get(iid, {}).get("depends_on") or [])
                if status_of.get(d) != STATUS_CONVERGED
            ]
            for iid in candidates
        }
        return None, {
            "deadlock": True,
            "pending": candidates,
            "unsatisfied_deps": blocked_deps,
        }
    return None, None


def all_terminal(state):
    items = state.get("items", {})
    return bool(items) and all(st.get("status") in TERMINAL for st in items.values())


def resolve_now_odp_ids(structure, iid):
    """resolve-now Open Decision Point ids for an item, from the frozen markdown structure. (Deferred ODPs are excluded — they re-surface at tail re-validation, not at claim.)"""
    spec = structure.get(iid, {})
    return [
        odp.get("id")
        for odp in spec.get("open_decisions", [])
        if odp.get("kind") == "resolve-now" and odp.get("id")
    ]


def unresolved_resolve_now_ids(state, structure, iid):
    """resolve-now ODP ids for an item NOT yet marked resolved in status state.
    These block `claim` — no loose ends before an item runs (the L4 autonomy gate: every decision is either resolved, defaulted-and-logged, or explicitly deferred-with-trigger)."""
    resolved = state.get("items", {}).get(iid, {}).get("odps", {})
    return [
        oid
        for oid in resolve_now_odp_ids(structure, iid)
        if resolved.get(oid, {}).get("status") != "resolved"
    ]


def merged_item(state, structure, iid):
    """Merge frozen structure + mutable status for display."""
    st = state.get("items", {}).get(iid, {})
    spec = structure.get(iid, {})
    return {
        "item_id": iid,
        "seq": spec.get("seq", st.get("seq", 0)),
        "title": spec.get("title", ""),
        "scope": spec.get("scope", ""),
        "source_location": spec.get("source_location", ""),
        "depends_on": spec.get("depends_on", []),
        "dod_ref": spec.get("dod_ref", ""),
        "blueprint_subset": spec.get("blueprint_subset", []),
        "parallel_group": spec.get("parallel_group"),
        "status": st.get("status", STATUS_PENDING),
        "attempts": st.get("attempts", 0),
        "open_decisions": spec.get("open_decisions", []),
        "unresolved_resolve_now": unresolved_resolve_now_ids(state, structure, iid),
    }


def summary(state):
    items = state.get("items", {})
    counts = {
        s: 0
        for s in [
            STATUS_PENDING,
            STATUS_IN_PROGRESS,
            STATUS_CONVERGED,
            STATUS_BLOCKED,
            STATUS_SKIPPED,
        ]
    }
    current = None
    for iid, st in items.items():
        counts[st.get("status", STATUS_PENDING)] = (
            counts.get(st.get("status", STATUS_PENDING), 0) + 1
        )
        if st.get("status") == STATUS_IN_PROGRESS:
            current = iid
    n = len(items)
    action, reason = check_breaker(state)
    return (
        f"Queue {state.get('queue_name', '?')}: "
        f"{counts[STATUS_CONVERGED] + counts[STATUS_SKIPPED]}/{n} resolved "
        f"(converged={counts[STATUS_CONVERGED]} blocked={counts[STATUS_BLOCKED]} skipped={counts[STATUS_SKIPPED]} "
        f"pending={counts[STATUS_PENDING]}), current={current or '-'}. "
        f"Breaker: {action} ({reason})."
    )


# --- CLI ---------------------------------------------------------------------


def require_structure(state):
    queue_ref = state.get("queue_ref")
    if not queue_ref:
        sys.exit("error: no queue_ref in state; run `init --queue-ref <path>` first")
    return parse_queue_structure(queue_ref)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="plan_queue.py", description="multi-item plan chaining state"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s_init = sub.add_parser("init")
    s_init.add_argument("--queue-ref", required=True)
    s_init.add_argument("--plan-ref", default=None)

    sub.add_parser("next-item")
    s_claim = sub.add_parser("claim")
    s_claim.add_argument("item_id")
    s_complete = sub.add_parser("complete")
    s_complete.add_argument("item_id")
    s_block = sub.add_parser("block")
    s_block.add_argument("item_id")
    s_block.add_argument("--root-cause", required=True)
    s_skip = sub.add_parser("skip")
    s_skip.add_argument("item_id")
    s_skip.add_argument("--reason", default="")
    s_ro = sub.add_parser("resolve-odp")
    s_ro.add_argument("item_id")
    s_ro.add_argument("odp_id")
    s_ro.add_argument("--resolution", required=True)
    s_ro.add_argument(
        "--defaulted",
        action="store_true",
        help="mark this resolution as an auto-default (audited in the run record)",
    )
    sub.add_parser("sync")
    sub.add_parser("check-breaker")
    s_up = sub.add_parser("upstream-provenance")
    s_up.add_argument("--queue-ref", required=True)
    s_rc = sub.add_parser("research-content")
    s_rc.add_argument("--research-ref", required=True)
    sub.add_parser("aggregate")
    sub.add_parser("summary")
    sub.add_parser("get")

    args = p.parse_args(argv)
    state = load()

    if args.cmd == "init":
        structure = parse_queue_structure(args.queue_ref)
        has_prior = os.path.exists(state_file())
        prior = load() if has_prior else {}
        state = default_state(args.queue_ref)
        if has_prior:
            # faithful resume: keep all mutable progress; only refresh structure
            state["items"] = prior.get("items", {})
            state["cross_item"] = prior.get("cross_item", state["cross_item"])
            state["status"] = prior.get("status", "chaining")
            state["events"] = prior.get("events", [])
            state["started_at"] = prior.get("started_at", state["started_at"])
        seed_from_structure(state, structure, plan_ref=args.plan_ref)
        record_event(
            state, "init", {"total_items": state["total_items"], "resumed": has_prior}
        )
        save(state)
        print(
            json.dumps(
                {"ok": True, "state_file": state_file(), "summary": summary(state)}
            )
        )

    elif args.cmd == "next-item":
        structure = require_structure(state)
        iid, stall = pick_next(state, structure)
        if iid is None:
            if all_terminal(state):
                state["status"] = "done"
                save(state)
                print(json.dumps({"done": True, "summary": summary(state)}))
            elif stall:
                print(json.dumps({"stalled": True, **stall, "summary": summary(state)}))
            else:
                print(json.dumps({"done": True, "summary": summary(state)}))
        else:
            print(
                json.dumps(
                    {
                        "item": merged_item(state, structure, iid),
                        "summary": summary(state),
                    }
                )
            )

    elif args.cmd == "claim":
        if args.item_id not in state.setdefault("items", {}):
            sys.exit(f"error: unknown item_id {args.item_id}")
        structure = require_structure(state)
        unresolved = unresolved_resolve_now_ids(state, structure, args.item_id)
        if unresolved:
            # L4 autonomy gate: refuse to start an item with unresolved resolve-now decisions — no loose ends.
            # Deferred ODPs do NOT block (they re-surface at tail re-validation). Fail loud, no mutation.
            sys.exit(
                f"error: item {args.item_id} has unresolved resolve-now open decisions: "
                f"{', '.join(unresolved)}. Resolve before claiming via "
                f"`plan_queue.py resolve-odp {args.item_id} <odp_id> --resolution <text> [--defaulted]`. "
                f"(Deferred ODPs do not block claiming.)"
            )
        st = state["items"][args.item_id]
        st["status"] = STATUS_IN_PROGRESS
        st["attempts"] = st.get("attempts", 0) + 1
        record_event(
            state, "claim", {"item_id": args.item_id, "attempt": st["attempts"]}
        )
        # plan-driven ↔ loop_state Hook 1: per-item loop_state init. plan-driven-mode.md:150
        # required this but left it to the agent (which skipped it -> empty loop_state, the
        # kindly gap). --blueprint-ref falls back to the queue_ref (master); the agent may
        # re-init with a per-item mini-blueprint from blueprint_subset (Tension 4).
        rc, out = _run_loop_state(
            [
                "init",
                "--task-id",
                args.item_id,
                "--blueprint-ref",
                state.get("queue_ref") or "",
            ]
        )
        if rc != 0:
            sys.exit(
                f"error: loop_state init for item {args.item_id} failed: {out.strip()}"
            )
        save(state)
        # P3-2 per-item different-family routing hint (ADR #40): surface the item's `hetero` field
        # (off|on, default off) from the frozen queue so the orchestrator knows to spawn
        # hetero_review.py for this item's outer ring. The hint is a RECOMMENDATION the
        # human-judged opt-in (model-routing.md) can override — different-family value is item-kind
        # dependent (Phase 0 RESULT point 2: high on doc/mixed, near-zero on pure-code).
        item_spec = (
            structure.get(args.item_id, {}) if isinstance(structure, dict) else {}
        )
        hetero_hint = (
            item_spec.get("hetero", "off") if isinstance(item_spec, dict) else "off"
        )
        print(
            json.dumps(
                {
                    "item_id": args.item_id,
                    "status": STATUS_IN_PROGRESS,
                    "attempt": st["attempts"],
                    "hetero": hetero_hint,
                }
            )
        )

    elif args.cmd == "complete":
        if args.item_id not in state.setdefault("items", {}):
            sys.exit(f"error: unknown item_id {args.item_id}")
        st = state["items"][args.item_id]
        st["status"] = STATUS_CONVERGED
        state.setdefault("cross_item", {})["consecutive_failures"] = 0
        record_event(state, "complete", {"item_id": args.item_id})
        # plan-driven ↔ loop_state Hook 2: mark-converged (REFUSES w/o record-outer, ADR #16
        # — enforces per-item dual-ring DoD at the state machine, not prose) + run-record
        # (per-item convergence evidence; l4 is per-item L4-kernel, mostly not-a-probe for
        # short items — Tension 6).
        rc, out = _run_loop_state(["mark-converged"])
        if rc != 0:
            sys.exit(
                f"error: loop_state mark-converged refused for item {args.item_id} "
                f"(outer ring didn't run?): {out.strip()}"
            )
        rc, out = _run_loop_state(["run-record"])
        if rc != 0:
            sys.exit(
                f"error: loop_state run-record for item {args.item_id} failed: {out.strip()}"
            )
        if all_terminal(state):
            state["status"] = "done"
        save(state)
        print(
            json.dumps(
                {
                    "item_id": args.item_id,
                    "status": STATUS_CONVERGED,
                    "summary": summary(state),
                }
            )
        )

    elif args.cmd == "block":
        if args.item_id not in state.setdefault("items", {}):
            sys.exit(f"error: unknown item_id {args.item_id}")
        st = state["items"][args.item_id]
        st["status"] = STATUS_BLOCKED
        fp = normalize_fingerprint(args.root_cause)
        st.setdefault("failure_fps", []).append(fp)
        ci = state.setdefault("cross_item", {})
        ci["consecutive_failures"] = ci.get("consecutive_failures", 0) + 1
        action, reason = check_breaker(state)
        record_event(
            state,
            "block",
            {"item_id": args.item_id, "root_cause": fp, "action": action},
        )
        # plan-driven ↔ loop_state hook: a blocked item is non-converged terminal in
        # loop_state too — mark-suspend (records the root-cause) + run-record (evidence).
        rc, out = _run_loop_state(["mark-suspend", "--reason", fp])
        if rc != 0:
            sys.exit(
                f"error: loop_state mark-suspend for item {args.item_id} failed: {out.strip()}"
            )
        rc, out = _run_loop_state(["run-record"])
        if rc != 0:
            sys.exit(
                f"error: loop_state run-record for item {args.item_id} failed: {out.strip()}"
            )
        if action in ("suspend", "hard-terminate"):
            state["status"] = "suspended" if action == "suspend" else "hard_terminated"
        save(state)
        print(
            json.dumps(
                {
                    "item_id": args.item_id,
                    "status": STATUS_BLOCKED,
                    "breaker": action,
                    "reason": reason,
                    "summary": summary(state),
                }
            )
        )

    elif args.cmd == "skip":
        if args.item_id not in state.setdefault("items", {}):
            sys.exit(f"error: unknown item_id {args.item_id}")
        state["items"][args.item_id]["status"] = STATUS_SKIPPED
        # a conscious skip breaks the consecutive-failure streak (intervention), same as a complete — otherwise a single stuck item could trip the cross-item breaker forever after being deliberately bypassed.
        state.setdefault("cross_item", {})["consecutive_failures"] = 0
        record_event(state, "skip", {"item_id": args.item_id, "reason": args.reason})
        # plan-driven ↔ loop_state hook: a skipped item is non-converged; loop_state has no
        # "skipped" status, so set-status accepts the string (Tension 5). run-record outcome
        # is non-terminal, honestly reflecting "not converged".
        rc, out = _run_loop_state(["set-status", "skipped"])
        if rc != 0:
            sys.exit(
                f"error: loop_state set-status for item {args.item_id} failed: {out.strip()}"
            )
        rc, out = _run_loop_state(["run-record"])
        if rc != 0:
            sys.exit(
                f"error: loop_state run-record for item {args.item_id} failed: {out.strip()}"
            )
        if all_terminal(state):
            state["status"] = "done"
        save(state)
        print(json.dumps({"item_id": args.item_id, "status": STATUS_SKIPPED}))

    elif args.cmd == "resolve-odp":
        if args.item_id not in state.setdefault("items", {}):
            sys.exit(f"error: unknown item_id {args.item_id}")
        odps = state["items"][args.item_id].setdefault("odps", {})
        odps[args.odp_id] = {
            "status": "resolved",
            "resolution": args.resolution,
            "defaulted": args.defaulted,
        }
        # Audit defaulted resolutions — the "propose-default-and-proceed" path must not be silent (see plan-driven-mode.md §Open Decision Points).
        record_event(
            state,
            "resolve-odp",
            {
                "item_id": args.item_id,
                "odp_id": args.odp_id,
                "defaulted": args.defaulted,
            },
        )
        save(state)
        print(
            json.dumps(
                {
                    "item_id": args.item_id,
                    "odp_id": args.odp_id,
                    "status": "resolved",
                    "defaulted": args.defaulted,
                }
            )
        )

    elif args.cmd == "sync":
        structure = parse_queue_structure(state.get("queue_ref") or "")
        seed_from_structure(state, structure)
        record_event(state, "sync", {"total_items": state["total_items"]})
        save(state)
        print(
            json.dumps(
                {
                    "synced": True,
                    "total_items": state["total_items"],
                    "summary": summary(state),
                }
            )
        )

    elif args.cmd == "check-breaker":
        action, reason = check_breaker(state)
        print(json.dumps({"action": action, "reason": reason}))

    elif args.cmd == "upstream-provenance":
        # rich path: bridge bc's sibling run-record -> pd's run-record `upstream`
        # field. None on the free path or when the sibling is absent (fail-safe).
        print(json.dumps(build_upstream_provenance(args.queue_ref)))

    elif args.cmd == "research-content":
        # charter R5 + R2 (research->inform): read a research artifact as FREE-FORM
        # content (bc's .research.json OR any research doc) for the orchestrator to
        # surface to the Coder. None when absent.
        print(json.dumps(read_research(args.research_ref)))

    elif args.cmd == "aggregate":
        items = state.get("items", {})
        rollup = [
            {
                "item_id": iid,
                "seq": st.get("seq", 0),
                "status": st.get("status"),
                "attempts": st.get("attempts", 0),
            }
            for iid, st in sorted(items.items(), key=lambda kv: kv[1].get("seq", 0))
        ]
        counts = {}
        for r in rollup:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        out = {
            "queue_name": state.get("queue_name"),
            "queue_ref": state.get("queue_ref"),
            "plan_ref": state.get("plan_ref"),
            "total_items": state.get("total_items", 0),
            "final_status": state.get("status"),
            "counts": counts,
            "items": rollup,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))

    elif args.cmd == "summary":
        print(summary(state))

    elif args.cmd == "get":
        print(json.dumps(state, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
