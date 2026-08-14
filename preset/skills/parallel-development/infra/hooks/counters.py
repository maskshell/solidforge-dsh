#!/usr/bin/env python3
"""counters.py — PreToolUse hook: terminal-state gatekeeper.

Distinct from fast_gate.py (which fires only on an active lint failure and records fingerprints). counters.py guards the OTHER direction: once the loop state machine has reached a terminal state (suspended / hard_terminated), it DENIES further edits so a stalled task cannot keep thrashing past the breaker.

Subcommands:
  pre  — run as a PreToolUse hook (deny edits while terminal)
  post — no-op (kept for settings compatibility; accounting is done in fast_gate)
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import detect_toolchain as dt  # noqa: E402

TERMINAL_STATUSES = {"converged", "suspended", "hard_terminated"}


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def loop_status():
    ls = dt.loop_state_path()
    if not os.path.exists(ls):
        return None
    try:
        proc = subprocess.run(
            ["python3", ls, "get"], capture_output=True, text=True, timeout=10
        )
        return json.loads(proc.stdout) if proc.stdout.strip() else None
    except Exception:
        return None


def pre():
    state = loop_status()
    if not state:
        sys.exit(0)
    status = state.get("status")
    if status in TERMINAL_STATUSES:
        diag = state.get("suspend") or {}
        if status == "converged":
            deny(
                "Loop is converged — the task is closed and its run-record is final. "
                "Edits after convergence would invalidate the record; open a NEW task "
                "(loop_state.py init --task-id <new>) for follow-up work."
            )
        deny(
            f"Loop is {status} — edits blocked by the circuit breaker. "
            f"Diagnosis: {diag.get('diagnosis', 'n/a')}. "
            "Do not retry the same approach. For suspended tasks, surface the summary for human review "
            "(or open the Blueprint Revision Channel if is_blueprint_defect). "
            "For hard_terminated tasks, output the best snapshot + diagnosis and stop."
        )
    sys.exit(0)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    if mode == "pre":
        pre()
    # "post" and anything else: no-op
    sys.exit(0)


if __name__ == "__main__":
    main()
