#!/usr/bin/env python3
"""plan_queue ↔ loop_state wiring — the claim/complete/block/skip hooks drive loop_state
deterministically (per docs/plan-driven-loop-state-wiring-design.md). Closes the kindly
gap where loop_state stayed empty (counters 0, l4 placeholder) despite plan-queue 4/4
converged: the hooks now drive per-item loop_state bookkeeping from plan_queue at the
code layer, not from agent prose.

Cases (subprocess plan_queue.py + loop_state.py — the hooks live in the CLI dispatch):
  1. claim → loop_state init (loop-state.json task_id = item)
  2. complete w/o record-outer → refused (exit non-zero; enforces per-item dual-ring DoD, ADR #16)
  3. complete w/ record-outer → mark-converged + runs/<item>-<stamp>.json
  4. block → loop_state suspended + runs/<item>.json
  5. skip → loop_state status=skipped + runs/<item>.json

Run: python3 infra/test/plan_queue_loop_state_wiring.py
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
PLAN_QUEUE = os.path.join(SCRIPTS, "plan_queue.py")
LOOP_STATE = os.path.join(SCRIPTS, "loop_state.py")

QUEUE_MD = (
    "## Items\n\n```json\n"
    '[{"item_id":"I0","seq":0,"depends_on":[],"dod_ref":"docs/x.md#I0"},'
    '{"item_id":"I1","seq":1,"depends_on":["I0"],"dod_ref":"docs/x.md#I1"}]\n'
    "```\n"
)


def _run(py_script, args, cwd, env):
    return subprocess.run(
        [sys.executable, py_script] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _env(td):
    return {**os.environ, "SOLIDFORGE_PROJECT_DIR": td}


def _loop_state(td):
    p = os.path.join(td, ".solidforge", "loop", "loop-state.json")
    return json.load(open(p)) if os.path.exists(p) else None


def _runs(td, item):
    return glob.glob(
        os.path.join(td, ".solidforge", "loop", "runs", f"{item}-*.json")
    )


def _setup(td):
    """Write queue.md + init plan_queue state. Returns the queue path."""
    qpath = os.path.join(td, "q.queue.md")
    with open(qpath, "w", encoding="utf-8") as fh:
        fh.write(QUEUE_MD)
    r = _run(PLAN_QUEUE, ["init", "--queue-ref", qpath], td, _env(td))
    assert r.returncode == 0, f"plan_queue init failed: {r.stderr or r.stdout}"
    return qpath


def check_claim_drives_loop_state_init():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        r = _run(PLAN_QUEUE, ["claim", "I0"], td, _env(td))
        assert r.returncode == 0, f"claim failed: {r.stderr or r.stdout}"
        ls = _loop_state(td)
        assert ls is not None and ls.get("task_id") == "I0", (
            f"claim did not init loop_state (task_id=I0): {ls}"
        )
    print("  claim -> loop_state init (task_id=item): PASS")


def check_complete_refused_without_outer():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _run(PLAN_QUEUE, ["claim", "I0"], td, _env(td))
        r = _run(PLAN_QUEUE, ["complete", "I0"], td, _env(td))
        assert r.returncode != 0, f"complete must refuse w/o outer ring: {r.stdout}"
        assert "refused" in (r.stdout + r.stderr).lower(), (
            f"refusal not surfaced: {r.stdout}{r.stderr}"
        )
    print("  complete w/o record-outer -> refused (non-zero): PASS")


def check_complete_with_outer_marks_converged():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _run(PLAN_QUEUE, ["claim", "I0"], td, _env(td))
        ro = _run(LOOP_STATE, ["record-outer", "--verdict", "pass"], td, _env(td))
        assert ro.returncode == 0, f"record-outer failed: {ro.stderr or ro.stdout}"
        r = _run(PLAN_QUEUE, ["complete", "I0"], td, _env(td))
        assert r.returncode == 0, f"complete w/ outer must pass: {r.stdout}{r.stderr}"
        recs = _runs(td, "I0")
        assert recs, f"complete w/ outer must emit runs/I0-*.json: {td}"
        rec = json.load(open(recs[0]))
        assert (
            rec.get("final_status") == "converged" and rec.get("converged") is True
        ), f"run-record not converged: {rec.get('final_status')}"
    print("  complete w/ record-outer -> mark-converged + runs/<item>.json: PASS")


def check_block_drives_loop_state_suspend():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _run(PLAN_QUEUE, ["claim", "I0"], td, _env(td))
        r = _run(
            PLAN_QUEUE,
            ["block", "I0", "--root-cause", "ruff format fail"],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"block failed: {r.stdout}{r.stderr}"
        ls = _loop_state(td)
        assert ls and ls.get("status") == "suspended", (
            f"block did not suspend loop_state: {ls}"
        )
        assert _runs(td, "I0"), "block must emit runs/I0-*.json"
    print("  block -> loop_state suspended + runs/<item>.json: PASS")


def check_skip_drives_loop_state_terminal():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _run(PLAN_QUEUE, ["claim", "I0"], td, _env(td))
        r = _run(
            PLAN_QUEUE,
            ["skip", "I0", "--reason", "conscious bypass"],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"skip failed: {r.stdout}{r.stderr}"
        ls = _loop_state(td)
        assert ls and ls.get("status") == "skipped", (
            f"skip did not set loop_state skipped: {ls}"
        )
        assert _runs(td, "I0"), "skip must emit runs/I0-*.json"
    print("  skip -> loop_state status=skipped + runs/<item>.json: PASS")


def main():
    print("plan_queue ↔ loop_state wiring (claim/complete/block/skip hooks):")
    failures = []
    for fn in (
        check_claim_drives_loop_state_init,
        check_complete_refused_without_outer,
        check_complete_with_outer_marks_converged,
        check_block_drives_loop_state_suspend,
        check_skip_drives_loop_state_terminal,
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
        "\nwiring: plan_queue hooks drive loop_state per-item "
        "(init / mark-converged / run-record)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
