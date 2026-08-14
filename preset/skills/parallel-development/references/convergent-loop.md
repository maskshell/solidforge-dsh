# Convergent Fix Loop (Dual-Ring Convergence)

The convergence repair loop. This is the deterministic core of the skill. Work is not done until this loop converges with both the inner ring (deterministic) and the outer ring (semantic) passing clean.

This loop is ONE of three orchestration primitives — it is model-driven, per-feature engineering convergence. It is NOT interchangeable with `ultracode`/Dynamic Workflows (script-driven cross-cutting sweeps) or `/loop` (meta/maintenance re-fire). For the differentiator, worked scenarios, and when each fits, see [orchestration-layers.md](orchestration-layers.md) (ADRs #32, #33).

Requires the opt-in deterministic infrastructure: see [install.md](install.md). Without it, the loop still runs but the gates are advisory (the agent runs them manually) instead of listener-enforced.

## Roles & contexts (who runs what)

The loop spans three roles in three contexts. Naming them removes the ambiguity of whether "the Coder" is the orchestrator or a subagent.

- **Orchestrator (main agent)** — owns the *control plane*: scheduling + conflict detection, dispatching the per-task Coder, running the Architecture-Contract Gate + 附加条件 at inner convergence, dispatching the outer reviewer, verdict dispatch + rollback, and emitting the run record. It holds a lightweight context (task graph, `files_touched`, task status, folded per-task results). It does NOT generate code.
- **Coder (per-task subagent)** — dispatched via the subagent tool under [role-agent-mapping.md](role-agent-mapping.md) (developer role). It does the implementation + inner-ring TDD churn for ONE task and self-corrects under the `fast_gate.py` `decision:block` until inner convergence. It returns the final Diff + a one-sentence folded inner summary (`loop_state.py summary`). Its voluminous churn stays in its own context and is discarded on return.
- **Reviewer (outer-ring subagent)** — independent `code-reviewer`; unchanged.

Two consequences, enforced elsewhere in this skill:

1. **Sequential ≠ direct.** Two tasks that conflict (shared `files_touched` / `depends_on`) occupy the SAME slot serialized — dispatch Coder A, await its return, then dispatch Coder B. Never concurrent (no write conflict), yet both still run as subagents (context isolation preserved). The orchestrator executes a task directly only as an exception (trivial single edit, or tight-coupling continuity a Diff + summary cannot bridge) — never as the default for "sequential". See [parallel-patterns.md](parallel-patterns.md) and ADR #14 in [design-decisions.md](design-decisions.md).
2. **Cross-task orchestrator context folding.** When a Coder returns, the orchestrator keeps ONLY {task status, files actually changed (from the Diff), the one-line folded summary}. It does not retain the task's inner stderr / iteration trail. The orchestrator's context therefore grows ~linearly with (task count × small folded record), not with total inner churn. This is the inner→outer fold applied at the task→orchestrator boundary (see Context folding below).

## Dual-axis layering (the organizing principle)

Primary axis = deterministic vs semantic. Secondary axis = cost.

- Inner ring = ALL deterministic checks.
  - Fast gate: lint / format / AOT-compile / single-file unit, ms~sec, every edit. Listener-enforced (`tools/post-execute` `fast_gate.py`). Lint failures remediate fix-in-ring; FORMAT failures block with commit-stratification guidance ([commit-stratification.md](commit-stratification.md)) — the format churn is isolated into a standalone `style:` commit instead of being inline-rewritten into the logic diff.
  - Architecture-contract gate: circular deps / layer isolation / concurrency baseline. Heavier. Runs at the inner convergence point, NOT every edit.
  - Gate附加条件 (additional pass conditions): Exit 0 alone is not a pass.
- Outer ring = only uncodable semantic checks. Independent `code-reviewer` subagent.

Codable architecture red lines stay in the inner ring. They must NOT leak into the expensive outer ring. See [arch-contracts.md](arch-contracts.md).

## Gate附加条件 (pass conditions beyond Exit 0)

A fast/arch gate that exits 0 is not a pass unless ALL hold:

- New-code coverage >= project threshold.
- No test marked skip / ignore / xfail counts as a pass.
- Suspect flaky tests re-run and pass stably (fixed seeds, stabilized fixtures).
- The test set is not shrunk relative to the Intent Blueprint (catches "delete the failing test to get Exit 0").

## Inner ring flow (Micro-Convergence)

1. The per-task Coder subagent edits (see [Roles & contexts](#roles--contexts-who-runs-what)). `tools/post-execute` `fast_gate.py` runs on the changed file.
2. On failure, `fast_gate.py` records the error fingerprint in loop-state, queries the breaker, and emits `decision:block` with the required action. the agent self-corrects next turn. The orchestrator treats any block as "inner red — short-circuit, do NOT enter the outer ring."
3. When the fast gate is clean across the changed set, run the architecture-contract gate (`arch_contract_<platform>.py`) at the convergence point. On any Blocker finding, fix in the inner ring and re-run. Never proceed to the outer ring on a red arch gate.
4. Verify the gate附加条件. Any miss → inner ring, not outer.
5. Both gates green + 附加条件 satisfied → inner converged. Take a snapshot (`snapshot.py create <task_id>`), set loop-state status to `inner_converged`, then transition to the outer ring.

> **Scope/belonging gate (task boundary):** after a Coder returns and before aggregation, run `scope_check.py --task-base <dispatch-ref> --files-touched <csv>` — the Coder's actual writes must be ⊆ its declared `files_touched` ∪ an allowlist. Correctness gates do not catch out-of-scope writes (an interrupted subagent once rewrote skill infra + deps and stayed green). On `flag`, discard the out-of-scope paths (`git checkout HEAD -- <paths>`), keep a coherent in-scope diff, or `snapshot.py restore`; never silently merge. Design + semantics: ADR #15 in [design-decisions.md](design-decisions.md).

## Outer ring flow (Macro-Convergence)

Spawn an independent `code-reviewer` subagent. It receives ONLY:

- The final Diff (not the inner stderr trail).
- The Intent Blueprint ref (`<blueprint_ref>`).
- L2 few-shot: a golden-path slice, or a cold-start pattern if none (Warning tier).
- A one-sentence folded inner summary (`loop_state.py summary`).
- An escalation package, if this review was triggered by an inner breaker.

The reviewer performs the triple-line check (quadruple-line when a `visual_ref` DESIGN.md is anchored — see [external-skills.md](external-skills.md)):

- Semantic line: abstraction level, naming, emergent coupling, design intent. Output structured findings WITH line numbers.
- Intent line: diff-to-blueprint. For each Core Use Case / AC: satisfied | partially-satisfied | missing, with file:line evidence. Flag any value hardcoded to bypass a failing test.
- Test-quality line (same-family): are the tests real AC checks or placeholders? Coverage of observable outcomes; assertions weakened to pass (loosened tolerance, commented-out asserts, swallowed exceptions, overfit fixtures); tests the diff deletes/renames (the inner AC→test-name set gate Blocks naked delete; this catches the weakenings it cannot). Same-family ceiling (ADR #38) — defends Goal Drift + Error Compounding, NOT test-quality spec gaming.
- Visual line (when a frozen DESIGN.md is anchored): diff-to-design. For each declared token / component / signature / a11y target: present | absent | drifted, with file:line evidence. Augmented by `/impeccable critique` (scored) + `audit`. The per-edit design findings come from Impeccable's detector hook (Seam B) — a Claude Code companion; in DSH the adapter degrades to a no-op until an equivalent exists.

Reviewer verdict dispatch:

- Pass → converge (`loop_state.py mark-converged`). NOTE (ADR #16): `mark-converged` REFUSES unless `record-outer` has been called (`outer.iterations >= 1`) — the Definition of Done (both rings) is now a state-machine invariant, not just a doc requirement, so a run that skipped the outer ring (e.g. direct execution) cannot be falsely marked converged. A refused `mark-converged` exits non-zero with guidance; the `build_run_record` backstop also exposes any bypassed converged-without-outer state via `dod_satisfied: false`.
- Semantic architecture issue → return for rewrite with line-numbered findings + local few-shot. Re-enter inner ring.
- Intent drift (code passes but lost blueprint intent) → HARD ROLLBACK: `snapshot.py restore <task_id>`, inject the reverse prompt (the lost UC/AC + the error path that caused it), regenerate. See Rollback below.
- Visual drift (code passes but lost a declared design token/component/signature; verdict `visual-drift`) → default **advisory rewrite**: re-enter the inner ring with the visual-line findings (no snapshot restore — visual drift is a fidelity gap, not a goal-anchor loss like intent drift). If the project opted in via `enforcement: strict` (a loop-controlled side-car signal, NOT a DESIGN.md field), visual drift → HARD ROLLBACK like intent drift.
- Blueprint defect (unreachable / self-contradictory / AC unsatisfiable) → Blueprint Revision Channel. See [intent-blueprint.md](intent-blueprint.md).

### different-family (different-family) adversarial review — opt-in additive outer ring (ADR #40)

The same-family `code-reviewer` above is PRIMARY and always runs. For HIGH-STAKES items — ADR-level decisions, security- or correctness-sensitive diffs, or a same-family verdict that is partially-satisfied / low-confidence — the orchestrator MAY add an different-family second opinion: spawn `infra/scripts/hetero_review.py`, which runs a non-interactive Claude Code subprocess (`claude -p --settings profiles/<backend>.json ...`) on a DIFFERENT model family (e.g. Claude / Qwen / GLM — in the DSH port DeepSeek is the orchestrator) as an ADVERSARIAL reviewer. The different-family prompt is "find what the primary MISSED or got wrong", NOT "validate" — without this it degenerates into rubber-stamping. Default items pay zero added cost (different-family does not run); the trigger is a human-judged classifier, not automated (ADR #40 (b); see [model-routing.md](model-routing.md)).

The different-family leg is ADDITIVE, never substitutive — it raises the ceiling without dropping the floor (different-family backends carry tool-call risk; the same-family primary is the reliability + cost floor). Reconciliation:

- both same-family + different-family report → high-confidence; adopt.
- same-family only → adopt (primary status).
- different-family only → strong signal (cross-family independent find = same-family blind spot); escalate for adjudication.
- neither → pass.
- different-family DEGRADED (a recoverable substrate error — budget cap / turn cap / provider overwhelm; `degraded:true` in the wrapper stdout) → the different-family leg contributed nothing; adopt the same-family primary (same as "same-family only"). NOT silent-pick — the `degraded` flag + a persisted `hetero-degraded-<subtype>` fingerprint distinguish it from a clean pass, and persistent degradation escalates via the thrashing breaker (ADR #41).

**Multi-round debate (the realistic pattern; ADR #40 (c)(d)).** A single different-family round rarely resolves disagreement. The ORCHESTRATOR drives the alternation (the wrapper does ONE different-family leg per call — it cannot spawn the in-process same-family primary, so the alternation is orchestrator-driven):

1. same-family primary reviews → findings A (the normal outer ring above).
2. orchestrator calls `hetero_review.py --prior-findings <A>` → different-family findings B.
3. same-family reviews again (respond or concede) → findings A'.
4. orchestrator calls `hetero_review.py --prior-findings <A'>` → findings B'.
   ... alternate until a termination fires.

Terminations (any one):

- **Converge**: a round returns zero new findings → adopt the merged findings.
- **No-movement early-exit**: the same disagreement fingerprint persists ≥2 rounds → the `loop_state` thrashing-fingerprint breaker fires; stop early, do not waste the remaining cap.
- **Cap**: `max_adversarial_rounds` (the count of different-family INVOCATIONS = `loop_state outer.iterations`, since each `hetero_review.py` call drives one `record-outer`) reached without convergence → the orchestrator records `loop_state.py record-outer --verdict adversarial-stalemate` and ESCALATES TO HUMAN. NEVER silently adopt either side on cap-hit — silent-pick defeats the different-family purpose (ADR #40 Rejected (f)).

The cap is bounded by `--max-budget-usd` per different-family subprocess (a hard cost breaker; default `--budget-usd 4.0` with headroom under the global 5.0 cap). The USD is a structural fiction for non-Anthropic backends — the API returns tokens, not price, so CC's USD ≠ real provider spend; treat `--budget-usd` as a runaway backstop, and the real provider-independent bounds as CC's turn limit + `step_cap_S` (ADR #42). If a review still trips the cap the wrapper DEGRADES (ADR #41) — verdict stays pass/rewrite from the other providers, the leg contributes nothing, and a `hetero-degraded-<subtype>` fingerprint is persisted; it does NOT force a rewrite. The same-family primary always responds after each different-family challenge, so the same-family final word is guaranteed BY CONSTRUCTION — no parity dependency on an odd/even cap. `hetero_review.py` drives `loop_state` truthfully around each subprocess call (ADR #39, ADR #40 (g)): `bump-iteration` per round, `record-outer` for the different-family verdict — so the run-record's `steps.inner` and `outer.iterations` stay honest.

## State machine: circuit breaker, escalation, global hard-termination

State lives in `.solidforge/loop/loop-state.json` (managed by `loop_state.py`).
The orchestrator calls `loop_state.py bump-iteration` at the start of each inner fix attempt and `add-budget` periodically; `fast_gate.py` records fingerprints on every failure.

> **Inline mode is NOT exempt from bookkeeping (ADR #39).** When the orchestrator runs the inner ring directly (the trivial-edit / tight-coupling / skill-self-maintenance carve-out, ADR #14), it STILL drives `bump-iteration` / `gate-fail` / `snapshot` every round. Inline exempts WHERE the edit happens, not WHETHER the bookkeeping happens — otherwise the run record's `steps.inner` under-reports (a 5-item inline plan once showed `steps.inner=0` despite real inner work). With the discipline, `steps.inner=0` cleanly means "the loop was never engaged". The DoD signal stays the outer review (ADR #16); this is telemetry discipline, not a gate.

Breaker trigger conditions (any one fires; priority hard-terminate > escalate > degrade/suspend):

| Condition | Action | What to do |
| --- | --- | --- |
| Any fingerprint count >= N (default 3) | `escalate` | Package fingerprint summary + paths tried; hand to the outer Reviewer. This is the ONLY inner->outer exception channel. |
| inner iteration >= M (default 8) | `degrade` | Split the task / narrow the convergence target; stabilize a sub-task locally. |
| M reached AND budget near exhaustion (>=80% of a cap) | `suspend` | Pause; output a diagnostic summary for human review. If a blueprint defect, open the Revision Channel. |
| total steps (inner + outer) >= step_cap_S (default 200) | `hard-terminate` | Provider-independent limit: the loop did not converge in work units. Capability signal (run record → `terminal_cause: step-capped` → `not-yet`). |
| token_T / cost_C exhausted, OR time_W exhausted | `hard-terminate` | Resource guard. Output the best snapshot + failure diagnosis and STOP. NOTE: time_W is a **hang/cost guard only** — wall-clock confounds provider throughput, so a time-cap hit is `terminal_cause: resource-capped` → `inconclusive` on capability, NOT a failure (ADR #6, #13). |

Query the breaker: `loop_state.py check-breakers` → `{action, reason}` with action in `ok | degrade | escalate | suspend | hard-terminate`. `fast_gate.py` calls `gate-fail <fingerprint>` which records and returns the action in one shot.

When a terminal status is set (`suspended` / `hard_terminated`), the `tools/pre-execute` `counters.py` listener DENIES further edits so a stalled task cannot keep thrashing.

## Event log + run record (L4 evidence)

`loop-state.json` is a *snapshot* — it is overwritten on every mutation, so the temporal sequence of breaker firings / outer verdicts / rollbacks would be lost. Two mechanisms preserve it and roll it up into a judgment-ready artifact:

- **Append-only event log (`events[]`)** — every anchor appends one event `{at, type, iteration, detail}` (bounded to the last 1000): `init`, each `bump-iteration`, each `gate-fail` (with `{fingerprint, action}`), each `mark-*` breaker (with `{action, reason}`), each `set-snapshot`, `set-blueprint-version`, and — wiring up the previously dead `outer` block — each outer review and rollback (below).
- **Outer-ring + rollback anchors (new)** — the `record-outer` and `mark-rollback` subcommands record the goal-drift and context-rot defense evidence that the snapshot alone never captured:
  - `loop_state.py record-outer --verdict {pass,rewrite,intent-drift,blueprint-defect,visual-drift,adversarial-stalemate} [--findings N] [--notes S]` — call after each outer review. `adversarial-stalemate` = the different-family multi-round debate hit `max_adversarial_rounds` without convergence (ADR #40 (e); P1-1). Bumps `outer.iterations` (previously a dead field) and appends an `outer-verdict` event. One outer review == one inner→outer context fold, so this is also the context-rot-defense trace.
  - `loop_state.py mark-rollback [--lost-uc UC]` — call on the intent-drift hard-rollback path. Appends a `rollback` event naming the lost use case.

**Task descriptor (declared at init, when the run is an L4 probe — ADR #38).** These flags (novel codebase, fuzzy requirements, high difficulty, unattended, horizon) declare **demand** (a demanding run that stress-tests capacity), NOT capacity criteria. Capacity = 3-degradation defense under convergence, independent of demand (is_l4_probe no longer gates l4-evidenced). Declare them honestly:

```bash
loop_state.py init --task-id <t> \
  --codebase-novelty novel --req-clarity fuzzy --difficulty high --attended false \
  --target-horizon-steps 60
```

Omit the flags for ordinary (non-probe) runs.

**Run record (emit at terminal status).** At `converged` / `suspended` / `hard_terminated`, emit the normalized record:

```bash
loop_state.py run-record          # -> .solidforge/loop/runs/<task>-<stamp>.json + stdout JSON
```

It conforms to `infra/schemas/run-record.schema.json`. The record aggregates `events[]` + state into outcome, steps (inner+outer), budget, every breaker firing with its trigger, top fingerprints, every outer verdict, and every rollback — no manual recording.

**`l4_assessment` block.** The record carries a computed `l4_assessment` block — the *instrumented form of the [maturity.md](maturity.md) rubric*.
It classifies `terminal_cause` provider-normally (`converged` / `suspended` / `resource-capped` / `step-capped` / `manual` / `non-terminal`) and derives a `provisional_verdict` ∈ {`l4-evidenced`, `not-yet`, `not-a-probe`, `inconclusive`}, and lists which maturity caveats the run can retire (`caveat-2-unproven-at-scale` when l4-evidenced).
A **resource-capped** termination (time/token/cost budget hit) is `inconclusive` — a slow provider's throughput must not be read as a capability failure (ADR #13); only **step-capped** is a capability signal. `human_confirm_required` is always `true` — task novelty / difficulty are human-declared, so the final L4 judgment stays human. See [maturity.md](maturity.md) § Closing the gap to proven L4.

## Context folding

At the inner->outer transition the orchestrator MUST NOT pass the dozens of inner trial logs to the reviewer. Instead:

- `loop_state.py summary` emits one folded sentence from the fingerprint log + status, e.g. "Inner converged after 3 iterations: direct persistence triggered same-fingerprint thrash (escalated), passed via service-layer decoupling."
- Only that sentence + Diff + blueprint + few-shot enter the reviewer's context.
- After outer review, the Coder keeps only: blueprint + distilled review feedback + last 1-2 inner iterations. Older inner trials are dropped.

### Cross-task orchestrator context folding

The same fold applies at the task→orchestrator boundary, not only inner→outer. When a Coder subagent returns, the orchestrator keeps ONLY {task status, files actually changed (from the Diff), the one-line folded summary}. It does not inline the task's inner stderr / iteration trail into its own context. This is what keeps the orchestrator lean across N tasks: its context grows ~linearly with (task count × small folded record), not with total inner-ring churn. See [Roles & contexts](#roles--contexts-who-runs-what) consequence 2.

## Rollback (snapshot granularity + hard rollback)

Snapshot granularity = the inner convergence point (both gates green, before outer ring), NOT every edit. Inner failure rolls back to the last snapshot (the previous outer-passed state or task start) so one bad step does not throw away valid prior results.

Commands (`snapshot.py`):

- `create <task_id>` — snapshot working tree; records ref in loop-state.
- `restore <task_id>` — restore working tree to the latest snapshot.
- `restore <ref>` — restore to a specific snapshot.
- `cleanup <task_id>` — delete the task's snapshots after convergence.

Hard rollback + reverse-prompt injection (intent-drift path):

1. Reviewer flags drift. Orchestrator runs `snapshot.py restore <task_id>`.
2. Orchestrator injects a reverse prompt: the lost UC/AC, the error path that caused the drift, and "regenerate WITHOUT repeating <anti-pattern>."
3. If post-rollback the loop still fails AND diagnosis points at a blueprint defect → open the Revision Channel (do NOT keep rolling back).

## Reviewer subagent prompt template

When spawning the outer-ring `code-reviewer`, structure the prompt as:

```text
Review this Diff against the Intent Blueprint and the L1 Constitution.
Inputs:
- Diff: <paste final diff>
- Blueprint: <blueprint_ref> (read it)
- L2 few-shot (Warning tier, mirror style only): <golden-path slice or cold-start pattern>
- Inner folded summary: <loop_state.py summary output>
<if escalated> Escalation package: inner breaker fired (same root cause repeated). The inner ring could not self-correct the following fingerprint: <summary>. Diagnose from a different angle. </if>

Produce TWO sections, every finding with file:line:
1. Semantic architecture: abstraction level / naming / emergent coupling / design intent. Severity: blocker | warning.
2. Intent alignment: for each Core Use Case and AC, state satisfied | partially-satisfied | missing with evidence. Flag any value hardcoded to bypass a failing test.
3. Test quality (same-family, severity: warning): are the tests real AC checks or placeholders? Flag (a) coverage gaps on the AC's observable outcomes (happy-path-only), (b) assertions weakened to pass — loosened tolerance, commented-out asserts, swallowed exceptions, overfit fixtures, (c) any test named in the blueprint's AC→test mapping that the diff removes or renames. The inner AC→test-name set gate (P1) Blocks the naked delete deterministically; you catch the weakenings it cannot see. SAME-FAMILY CEILING (ADR #38): you share the model's blind spot — you defend Goal Drift + Error Compounding, NOT test-quality spec gaming (weak assertions, overfit); state that gap honestly. different-family adversarial review is now PARTIAL via `infra/scripts/hetero_review.py` (ADR #40 — a different model-family second opinion the orchestrator may spawn alongside you); mutation testing remains the eventual engine-level oracle.
<if a frozen DESIGN.md (visual_ref) is anchored> 4. Visual fidelity: for each declared token / component / signature / a11y target in DESIGN.md, state present | absent | drifted with evidence. Severity: warning (visual drift is heuristic). </if>
Verdict: pass | rewrite | intent-drift | visual-drift | blueprint-defect | adversarial-stalemate (different-family debate cap-hit; ADR #40 (e) — escalate to human, never silent-pick).
```

## Phase sequence (full execution flow)

- Phase 0 (intent freeze): Planner produces and freezes the Intent Blueprint. No GREEN work without a frozen blueprint. See [intent-blueprint.md](intent-blueprint.md). For an L4 probe, `init` also declares the task descriptor (see Event log + run record above).
- Phase 1 (inner generation): Coder writes code; inner fast gate + arch-contract gate + gate附加条件 iterate until both green; snapshot on inner convergence.
- Phase 2 (context fold): clear inner noise; package final Diff + folded summary.
- Phase 3 (outer semantic review): reviewer with Diff + blueprint + L2 + folded summary; triple-line check (semantic + intent + test-quality; +visual when anchored). Record the verdict: `loop_state.py record-outer --verdict <v> --findings <n>`.
- Phase 4 (decision dispatch): pass → converge; semantic issue → rewrite; intent drift → hard rollback + reverse prompt (`loop_state.py mark-rollback --lost-uc <uc>`); blueprint defect → revision channel.
- Phase 5 (terminal): at `converged` / `suspended` / `hard_terminated`, emit the run record: `loop_state.py run-record` → `.solidforge/loop/runs/<task>-<stamp>.json` (conforms to `infra/schemas/run-record.schema.json`, carries the `l4_assessment` block).

## Mapping to DeepSeek Harness mechanisms

| Loop layer | DeepSeek Harness mechanism |
| --- | --- |
| Inner coder (per task) | developer subagent via the `subagent` tool (isolated context; inner churn discarded on return — see [Roles & contexts](#roles--contexts-who-runs-what)) |
| Scope/belonging (task boundary) | `scope_check.py` at the Coder→orchestrator handoff — actual writes ⊆ `files_touched` ∪ allowlist (ADR #15) |
| Inner fast gate | `tools/post-execute` listener `fast_gate.py` via the loop-gates plugin (decision:block on failure) |
| Inner arch-contract gate | Explicit script `arch_contract_<platform>.py` at convergence |
| Outer reviewer | Independent `code-reviewer` subagent (no write perms, isolated context) |
| Context folding | Minimal reviewer prompt (Diff + blueprint + folded summary; semantic + intent + test-quality lines) |
| Blueprint freeze | Read-only file + `tools/pre-execute` `blueprint_guard.py` |
| Breaker counters / hard-termination | loop-state.json + `counters.py` (denies edits when terminal) |
| Event log (temporal sequence) | `loop_state.py` appends to `events[]` at every anchor (bounded to last 1000) |
| Outer-ring verdict + rollback trace | `loop_state.py record-outer` / `mark-rollback` (wire up `outer` + rollback events) |
| Run record + L4 assessment | `loop_state.py run-record` at terminal status → `.solidforge/loop/runs/<task>-<stamp>.json` |

## Faithful alternatives (where the spec ideal meets DSH reality)

- Fast gate cannot prevent an edit (`tools/post-execute` runs after). Realized as decision:block + next-turn self-fix + short-circuit. Same observable fast-fail.
- Token budget T cannot be read by the listeners. Time budget W (reliable) + a token estimate from tool-call count. Documented as approximate.
- No kernel-level drift block. Realized as snapshot restore + the state machine refusing to advance a drift-flagged task.
