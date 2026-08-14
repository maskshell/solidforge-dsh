# plan-driven ↔ loop_state wiring — design

> Status: **IMPLEMENTED** (see `plan_queue.py` claim/complete/block/skip hooks → `loop_state`). Fixes the plan-driven bookkeeping gap surfaced in the kindly project: `loop_state` counters empty (`inner.iteration: 0`, `outer.iterations: 0`, `l4: not-a-probe`) despite `plan-queue-state` showing 4/4 items converged.
>
> Related: [convergent-loop.md](../references/convergent-loop.md) (single-task kernel), [plan-driven-mode.md](../references/plan-driven-mode.md) (chaining), [maturity.md](../references/maturity.md) (L3/L4 split).

## Context (CGC-confirmed root cause)

In kindly, plan-driven runs left `loop_state` empty while `plan-queue-state.json` recorded 4/4 converged. CGC confirmed the structural root: **`loop_state` has zero Python callers** — `find_importers loop_state = 0`; `find_callers record_fingerprint` are all internal to `loop_state.main`. Every bookkeeping anchor (`mark-converged` / `bump-iteration` / `record-outer` / `run-record`) is driven **only by the LLM agent at runtime** (CLI subprocess per SKILL/convergent-loop.md prose), except `gate-fail` (driven by the `fast_gate.py` hook — reliable). `plan_queue.complete` (`plan_queue.py:550-568`) updates plan-queue state only — it does **not** drive `loop_state`.

plan-driven mode amplifies this: the agent jumps to `complete` without running the per-item `loop_state` lifecycle (`init` → converge inner+outer → `mark-converged` → `run-record`) that `plan-driven-mode.md:150-152` requires. So `plan_queue` records 4/4 converged; `loop_state` records nothing; `l4` (which hangs off `loop_state`) is placeholder. **Bookkeeping reliability = agent reliability**, and the agent is unreliable here.

## Design semantics (governs the fix — read before judging alternatives)

- `plan-driven-mode.md:200`: **per-task convergence (inner + outer) is the L4 kernel.**
- `plan-driven-mode.md:202`: **plan-driven chaining is an L3 semantic router — do NOT claim L4 for the composite.**

∴ the fix is **NOT "add a plan-level L4 aggregate"** (that would claim L4 for the L3 router, violating :202). The fix is to make the **per-item L4 kernel** (`loop_state`) actually run for each plan-driven item, so each item gets a real per-item `l4_assessment`, and the composite honestly stays L3.

## Fix — wire plan_queue ↔ loop_state at the per-item lifecycle anchors (code-layer, deterministic)

Two hooks in `plan_queue.py`, both subprocess `loop_state` (not agent-driven) — mirror how `fast_gate.py` already subprocesses `loop_state.py gate-fail`:

**Hook 1 — `claim` → `loop_state init` (per-item).** `plan-driven-mode.md:150` already says "Re-run `loop_state.py init --blueprint-ref <mini-or-master>`" after claim — but leaves it to the agent. Move it into `plan_queue claim`: after setting status `in_progress`, subprocess `loop_state.py init --task-id <item_id> --blueprint-ref <ref>` (rich path: `--upstream` from `detect_producer`). `loop-state.json` is now always "the current item's"; the previous item's record was already persisted to `runs/` by Hook 2 before the next `claim`.

**Hook 2 — `complete` → `loop_state mark-converged` + `run-record` (per-item).** In `plan_queue complete` (`plan_queue.py:550-568`), after `record_event("complete")` and before `save()`:

1. subprocess `loop_state.py mark-converged` — **REFUSES unless `record-outer` was called** (`outer.iterations >= 1`, ADR #16). On refusal (agent skipped the outer ring), `complete` exits non-zero with guidance ("run the outer review + `loop_state.py record-outer` first"). This enforces the per-item dual-ring DoD at the state-machine layer, not in prose.
2. subprocess `loop_state.py run-record` → persists `runs/<item_id>-<stamp>.json` (per-item, with a real `l4_assessment` from the kernel).

`block` / `skip` similarly drive `loop_state` to a terminal status + `run-record`, so a non-converged item also leaves a record (no silent gap).

## What this does NOT do (honesty)

- **No plan-level L4** — plan-driven chaining is L3 (`plan-driven-mode.md:202`); per-item `l4` stays per-item (L4 kernel). `plan_queue aggregate` keeps its current job (per-item converged/blocked + cross-item breaker); it does **not** synthesize a composite `l4`.
- **Does not drive inner/outer convergence itself** — the hooks drive `loop_state` *bookkeeping* only (`init` / `mark-converged` / `run-record`). The actual inner (Coder + gates) and outer (`plan-reviewer`) work stays the agent's; the hooks just refuse `complete` if the agent skipped outer, forcing it back. (Mirrors bc's `produce.py` lesson: deterministic bookkeeping/orchestration beats agent-prose-driven.)

## Tensions / open questions

1. **`complete` refuses without outer — stricter than today.** plan-driven agents that skip outer (to save cost) will hit refusal. Intended (closes the false-convergence hole, matches ADR #16) but changes plan-driven UX — flag in `plan-driven-mode.md`.
2. **Per-item outer cost.** Every plan-driven item now must run an outer review (`plan-reviewer` spawn) to pass `complete`. `plan-driven-mode.md:200` already says per-task = inner+outer (L4 kernel), so this is design-correct, but it's a real cost increase. Open (deferred): is per-item outer always warranted, or should low-drift-risk items have a lighter outer? Current design enforces uniformly.
3. **`loop-state.json` is single-file (current item).** Per-item `init` overwrites it; the per-item record is persisted to `runs/` by Hook 2 before the next item's `init`. Verify no consumer assumes `loop-state.json` is multi-item cumulative (it isn't — it's the current task's; `run-record` is the durable per-item artifact).
4. **Hook 1 `--blueprint-ref` source.** `claim` needs the per-item mini-blueprint ref. `plan-driven-mode.md:150` says the agent derives it from `blueprint_subset`; if the agent hasn't derived it yet, the hook falls back to the master blueprint ref (and notes it). Mini-blueprint derivation stays the agent's job; the hook just won't block on it.
5. **`skip` has no loop_state terminal status.** `block` maps cleanly to `mark-suspend` / `set-status`; `skip` is a conscious bypass (`plan_queue` resets the failure streak) — neither converge nor block. Define `skip` → `loop_state set-status` to a non-converged terminal + `run-record`, OR extend loop_state with a `skipped` status. Lean: reuse `set-status` (no new status) — decide at implementation.
6. **Per-item `l4` will mostly be `not-a-probe` for plan-driven items.** plan-driven items are usually short (< the 60-step L4-probe horizon, `maturity.md:74`), so per-item `l4_assessment.provisional_verdict` is `not-a-probe` — that's **correct** (the item isn't an L4 probe), not a bug. **Hook 2's value is the per-item run-record (real convergence evidence: steps / breakers / outer verdict), NOT an l4 true-value** — which only L4-probe-grade items get. Consistent with plan-driven = L3 (composite) + per-task = L4 (kernel, meaningful only for probe-grade items). Do not read "Hook 2 gives every item a real l4" — it gives every item a real *record*; l4 stays probe-gated.

## Implementation

- `plan_queue.py`: Hook 1 (in `claim` handler → subprocess `loop_state.py init`); Hook 2 (in `complete` handler → subprocess `mark-converged` then `run-record`; on `mark-converged` refusal, exit non-zero with guidance); mirror for `block`/`skip` (terminal + `run-record`). Reuse a `loop_state_path()`-style resolver (mirror `fast_gate.py:168-177`).
- Tests: `plan_queue` wiring test — `claim` drives `loop_state init` (`loop-state.json` task_id = item); `complete` without `record-outer` → refusal (non-zero); `complete` with `record-outer` → `mark-converged` + `runs/<item>.json`; `block`/`skip` → terminal record.
- Docs: `plan-driven-mode.md:150/152` (the hooks now drive `loop_state` deterministically — agent no longer manually inits/marks); ADR #37. (`convergent-loop.md` is the single-task kernel doc and does not mention plan-driven — the wiring note belongs in `plan-driven-mode.md`, not there.)

## Verification

- pd self-tests green (rule 1): existing suite unchanged + new plan_queue↔loop_state wiring tests.
- Manual e2e (temp project): plan-driven run of 2 items → each leaves `runs/<item>-<stamp>.json` with a real `l4_assessment` (not placeholder); `complete`-without-outer refused; `plan_queue aggregate` shows per-item converged (no composite l4).
- Re-run the kindly scenario: plan-driven 4 items → 4 per-item run-records with real l4; `loop-state.json` = last item's; `plan-queue-state` = 4/4 (unchanged authority).

## ADR (rule 6)

- Decision: wire `plan_queue`→`loop_state` at `claim`/`complete` (code-layer subprocess), not agent-prose-driven; `complete` enforces `record-outer` (per-item dual-ring DoD) by refusing otherwise.
- Rejected: (a) plan-level L4 aggregate — violates `plan-driven-mode.md:202` (chaining is L3, not L4); (b) leave `loop_state` driving to agent prose — CGC proved the agent doesn't drive it (counters empty in kindly); (c) drive inner/outer from the hook — hooks are bookkeeping only; convergence work (Coder + reviewer) stays the agent's.
