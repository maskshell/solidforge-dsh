# Plan-Driven Mode (multi-item plan chaining)

Plan-driven mode lets the skill execute a **multi-item plan** end-to-end — chaining its items to convergence one after another without yielding to the user between items — instead of stopping after the first item converges.

It is the answer to a control-flow gap, not a capability gap: the default lifecycle is single-task (`freeze → converge → report → yield`), so a prompt like "按照 @plan 开始迭代" completes ONE item, reports, and stops — even at low context. Plan-driven mode adds the missing outer loop.

## When it triggers

Enter plan-driven mode when ALL hold:

- The request @-references a plan document (iteration plan, feature plan,
  Cursor `.plan.md`, roadmap, etc.).
- The deliverable is **source/test code** (executing the plan, not authoring it).
- The plan is plausibly multi-item (≥2 work items).

This is the carve-out from the Scope Guard: **executing** a referenced plan is IN scope (code deliverable); **authoring/designing** a plan is OUT of scope (route to `requirements-manager` / `architect`). See [scope.md](scope.md).

## Architecture: lift the frozen-anchor pattern one layer

The semantic act — "read this heterogeneous plan into a sequence of items" — is done **once**, frozen into a structured `plan-queue`, then the chaining loop runs **deterministically** over the frozen queue. This is the Intent Blueprint pattern (semantic intent → frozen structured anchor → converge against it) applied to the plan itself.

```text
[ plan @ref (heterogeneous) ] ──(normalize, once)──▶ [ frozen plan-queue.md ]
                                                              │  structure: item_id/seq/scope/
                                                              │  source_location/depends_on/
                                                              │  dod_ref/blueprint_subset/parallel_group
                                                              ▼
                  upfront checkpoint (user confirms the read) ──▶ [ chaining loop ]
                                                              │  per item: claim → freeze sub-scope →
                                                              │  lifecycle → converge → tick → next
                                                              │  cross-item breaker (plan_queue.py)
                                                              ▼
                                                      [ aggregate report ]
```

Two artifacts, cleanly separated:

- **Frozen structure** = the markdown queue file (`docs/plan-queues/<name>.queue.md`), read-only guarded (revision channel only). Holds the immutable plan interpretation.
- **Mutable status** = `<project>/.solidforge/loop/plan-queue-state.json`, owned by `plan_queue.py`. Holds per-item progress + breaker counters only — never duplicates structure.

`plan_queue.py` reads structure from the markdown, mutates only status. No duplication, no drift.

## Phase −1: the normalizer (the semantic core)

An **agent act** (the orchestrator or a `Plan` subagent), guided by this file.
It reads the referenced plan (+ its authority chain) and emits the frozen queue.
Graded extraction — latch structure where present, semantic-infer where not:

| Source signal | Extraction mode |
| --- | --- |
| Cursor `todos[]` frontmatter; iteration-plan tables; decomposition tables | **Latch** (structural — high confidence) |
| Prose deps ("前置/并发/不相交文件"); mermaid graphs; absent deps | **Semantic-infer** (low confidence — flag it) |
| Freeform scope text | **Semantic-summarize** |

Six capabilities the real plan formats force (calibrated against `docs/iteration-plan.md`, `docs/renderer-richness-plan.md`, and a Cursor `.plan.md`):

1. **Plan-native grain.** Do NOT canonicalize grain. An iteration-plan yields `I0..I17`; a feature plan yields `Coder-L/M/E/G`; a Cursor plan yields work packages like `foundation-i0-i2`. `item_id` stays plan-native.
2. **`dod_ref` resolution.** Per-item DoD frequently lives OUTSIDE the plan — in a referenced blueprint (AC-0..5) or a master plan's 验证闸口. Follow the reference chain; record the resolved pointer, not a copy.
3. **Resume-aware.** Read existing progress markers (commit-hash logs, 待办 sections, `status:` fields) → seed item status → chaining resumes, never restarts.
4. **Sequence-intent extraction.** Plans often encode execution order in prose ("先 Coder-P0+Coder-0 → 收敛 → 并发 Coder-L/M/E/G"). Lift "前置/并发/不相交文件" into `depends_on` + `parallel_group`.
5. **Authority chain.** Record "冲突以 X 为准" rules in the queue header so later conflicts resolve deterministically.
6. **Single source of truth for the rubric.** The queue references the blueprint/master-plan for DoD; it does not restate it.
7. **Open Decision Points (ODP) register.** Surface every point where the plan requires a choice, split into resolve-now (decided at the checkpoint) and deferred (pegged to a later item's outcome). See Open Decision Points below.

## Queue format

A markdown file at `docs/plan-queues/<name>.queue.md`:

- YAML-ish frontmatter: `queue_version`, `frozen_at`, `plan_ref`, `authority_chain` (list), `status` (`frozen` | `revising`).
- A human-readable summary (for the checkpoint).
- A fenced ```json block under `## Items` carrying the machine-parseable structure (stdlib `json` — no YAML dependency).

`plan_queue.py` extracts the first ```json fenced block and `json.loads` it.

Template:

````markdown
---
queue_version: v1
frozen_at: 2026-06-20
plan_ref: docs/renderer-richness-plan.md
authority_chain:
  - docs/iteration-plan.md
status: frozen
---

# Plan Queue — <feature>

FROZEN plan interpretation. Read-only for the Coder; revise only via the Revision Channel (`status` -> `revising` -> edit -> version bump -> `frozen`).
See [plan-driven-mode.md](../../<skill>/references/plan-driven-mode.md).

## Summary (checkpoint view)

<one paragraph: N items at <grain>, sequencing intent, DoD source>

## Items

```json
[
  {
    "seq": 0,
    "item_id": "Coder-P0",
    "title": "AC-0 origin-on-canvas contract test",
    "scope": "lock the default-origin invariant; test-only",
    "source_location": "renderer-richness-plan.md §三 Coder-P0",
    "depends_on": [],
    "dod_ref": "docs/intent-blueprints/renderer-richness-v2.blueprint.md#AC-0",
    "blueprint_subset": ["AC-0"],
    "parallel_group": "wave-1"
  },
  {
    "seq": 1,
    "item_id": "Coder-0",
    "title": "note framework + overlay label wiring",
    "scope": "4 draw tools gain optional note; overlay_fits[].label -> legend",
    "source_location": "renderer-richness-plan.md §三 Coder-0",
    "depends_on": [],
    "dod_ref": "docs/intent-blueprints/renderer-richness-v2.blueprint.md#AC-3",
    "blueprint_subset": ["AC-3"],
    "parallel_group": "wave-1"
  },
  {
    "seq": 2,
    "item_id": "Coder-L",
    "title": "inclined_plane_experiment P1 richness",
    "scope": "rope car->pulley->bucket + timer/tape/power/wedge + car-with-wheels + 8 labels",
    "source_location": "renderer-richness-plan.md §三 Coder-L",
    "depends_on": ["Coder-P0", "Coder-0"],
    "dod_ref": "docs/intent-blueprints/renderer-richness-v2.blueprint.md#AC-1",
    "blueprint_subset": ["AC-1"],
    "parallel_group": "wave-2"
  }
]
```
````

## Frozen-anchor semantics (guard + revision channel)

Identical mechanism to the Intent Blueprint (see [intent-blueprint.md](intent-blueprint.md)), lifted one layer:

- **Read-only guard.** `blueprint_guard.py` (tools/pre-execute) DENIES edits to any `**/plan-queues/*.queue.md` whose frontmatter `status: frozen`.
- **Revision channel** — the only change path. Mid-chain, if an item turns out mis-scoped or a dependency was read wrong: set `status: revising` (guard unlocks), edit, bump `queue_version`, set `status: frozen` (re-locks). Then `plan_queue.py sync` to pick up structural changes while preserving status.

## The chaining loop

For each item in `seq` order, respecting `depends_on` (and `parallel_group` as a fan-out hint to the concurrency scheduler):

1. `plan_queue.py next-item` → lowest-`seq` pending item whose deps are all `converged` (else: stall/deadlock reported).
2. `plan_queue.py claim <item_id>` → `in_progress`.
3. **Freeze sub-scope.** If `blueprint_subset` → derive a per-item mini-blueprint (the claimed ACs) as this item's Phase-0 anchor. If `dod_ref` is inline → use it directly. `claim` already drove `loop_state.py init --task-id <item>` automatically (the plan_queue↔loop_state wiring hook — the agent no longer runs init manually; derive the mini-blueprint first if `blueprint_subset`, so the hook's `--blueprint-ref` carries it — falls back to the master queue_ref otherwise). **Rich path**: if `plan_queue.detect_producer` reports `blueprint-crafting`, seed the Phase-0 anchor from bc's spec in the `authority_chain` (derive, don't re-imagine — see [intent-blueprint.md](intent-blueprint.md) §Rich path).
4. Run the **existing** lifecycle (Phase 0 → phases → Convergent Fix Loop) to convergence for THIS item. **Rich path (research→inform)**: if a research artifact (bc's `.research.json` or any free-form research doc — R2: research is free-form input, not gated to bc's format) is referenced via the queue's `authority_chain`, surface its content to the Coder (`plan_queue.py research-content --research-ref <path>`) so implementation is informed by the rationale (charter R5).
5. On converge: `plan_queue.py complete <item_id>` — the hook drives `loop_state mark-converged` (**REFUSES unless `record-outer` ran** — spawn the code-reviewer + `loop_state.py record-outer --verdict <v>` first; this enforces the per-item dual-ring DoD at the state machine) + `run-record` (per-item). On block: `plan_queue.py block <item_id> --root-cause <fp>` — hook drives `loop_state mark-suspend` + `run-record`. On skip: `plan_queue.py skip <item_id> --reason <t>` — hook drives `loop_state set-status skipped` + `run-record`. (resets the consecutive-failure counter; see [docs/plan-driven-loop-state-wiring-design.md](../docs/plan-driven-loop-state-wiring-design.md).)
6. **Do not report to the user between items** — emit one progress line only.
7. **Tail re-validation** (bounded, optional): after an item, if later items' scopes plausibly shifted on this item's outcome → revision channel.
8. Advance. When no pending item remains → `plan_queue.py aggregate` → report.

## Cross-item breaker (`plan_queue.py`)

Same philosophy as `loop_state.py` breakers, scope raised one layer:

- **Consecutive-item failure** (≥ `cap_consecutive`, default 3 items blocked on the same normalized root-cause class) → **suspend** for human review (the cross-item analog of thrashing).
- **Total-items cap** (`cap_total_items`, default 50) → **hard-terminate** (runaway plan / misread).
- **Deadlock**: pending items remain but none have deps satisfied → report stall.

Per-item convergence still uses `loop_state.py`'s inner breakers unchanged — the two layers compose (inner = within-item; cross-item = across-items).

## Resume

`plan_queue.py init --queue-ref <path>` is **idempotent and merge-preserving**: re-reading the structure never clobbers existing `converged`/`blocked` status for matching `item_id`s. So a session can re-enter, call `init`, and chaining resumes at the first non-converged item. This is what fixes "stopped after iteration 1" across sessions.

## Mandatory upfront checkpoint

Because plan interpretation is semantic and formats are heterogeneous, after Phase −1 the skill MUST surface the frozen queue and get user confirmation before chaining: item count, grain, dependency graph, DoD sources, resume point. Heterogeneity is exactly why this cannot be skipped — it is the highest-error step. (On resume: still show the queue + which items are already converged.)

## Open Decision Points (resolve-before-running gate)

A plan run drops below L4 wherever a human must decide mid-loop. Phase −1 enumerates every such point as an **Open Decision Point (ODP)**, per item, so none is left loose. Two kinds:

- **resolve-now** — decidable from the plan + context before chaining. Resolved at the mandatory checkpoint. **`claim` refuses any item with an unresolved resolve-now ODP** (the `plan_queue.py` gate) — the deterministic "no loose ends" rule that keeps the loop autonomous.
- **deferred** — genuinely depends on an earlier item's outcome. NOT resolved upfront; pegged to a trigger ("decide after item X, based on Y") and re-surfaced at that item's tail re-validation. Deferred ODPs do NOT block `claim`.

Autonomy vs silent-choice: when running unattended, the skill **proposes a default and proceeds** for resolve-now ODPs unless the user overrides at the checkpoint — but every defaulted resolution is recorded via `resolve-odp --defaulted` and appears in the event log / run record (auditable, not silent).

Queue format: each item may carry `open_decisions:
[{id, kind, question, default?, trigger?}]` in its ```json block. CLI:
`plan_queue.py resolve-odp <item> <odp_id> --resolution <text> [--defaulted]`.

## Commit policy (autonomous, post-convergence)

Committing is otherwise a hidden per-stage human stall. Make it a frozen run-level policy instead — decided once at `loop_state.py init --commit <policy>`, applied by the orchestrator at convergence:

- `auto-per-stage` (default): on a **feature branch** (never `main`), one commit per converged stage — per converged task in single-task mode (after `mark-converged`); in plan-driven mode, per LOGICAL CHANGE, not per queue item: a plan's items usually batch into ONE commit (code+docs+records together, or code / records as two), because queue-item completion state lives in the run-record, never in git history. The message carries BUSINESS content (problem → change → tradeoffs → docs); loop metadata (item_id, outer-ring verdicts, DoD refs) stays out of commit messages. No confirmation.
- `manual`: the orchestrator does not commit; the user commits (legacy behavior).
- `none`: no commits.

Safety: the commit fires ONLY at convergence (inner + outer rings clean), so broken/WIP code is never committed; and it lands on a feature branch, so it is reversible and reviewable. The default policy **authorizes autonomous commits for the skill's runs**, overriding the usual "commit only when asked" default; set `--commit manual` to opt out. A per-stage commit may itself be STRATIFIED — a pure-format `style:` commit isolated ahead of the logic commit when the stage touched legacy-unformatted files: see [commit-stratification.md](commit-stratification.md).

## Honesty: an L3 semantic router over the L4 per-task kernel

- Per-task convergence (inner ring + outer ring) remains L4-capable — objective gate (tests / doc_gate), deterministic.
- Plan-driven chaining (normalization + cross-item orchestration) is an **L3 semantic router** — plans have no objective oracle, so "did I read the plan right?" cannot be deterministically answered.
- The router is the reliability bottleneck. Mitigations (frozen queue + checkpoint + revision channel + resume + cross-item breaker) **audit** the semantic risk; they do not eliminate it. Do not claim L4 for the composite. See [maturity.md](maturity.md).

## CLI reference (`infra/scripts/plan_queue.py`)

Pure stdlib; JSON state at `<project>/.solidforge/loop/plan-queue-state.json` (gitignored). Mirrors `loop_state.py` conventions.

```bash
plan_queue.py init --queue-ref <path>           # parse markdown structure; seed status (resume-preserving)
plan_queue.py next-item                         # print next runnable item (deps satisfied) or {done: true}
plan_queue.py claim <item_id>                   # -> in_progress (REFUSES if item has unresolved resolve-now ODPs)
plan_queue.py resolve-odp <item_id> <odp_id> --resolution <t> [--defaulted]  # resolve a resolve-now ODP (unblocks claim)
plan_queue.py complete <item_id>                # -> converged; reset consecutive-failure counter
plan_queue.py block <item_id> --root-cause <fp> # -> blocked; bump counter; check breaker
plan_queue.py skip <item_id> --reason <text>    # -> skipped
plan_queue.py sync                              # re-read markdown structure; preserve status (post-revision)
plan_queue.py check-breaker                     # print cross-item breaker action
plan_queue.py aggregate                         # per-item outcome rollup (for the final report)
plan_queue.py summary                           # one-line progress
plan_queue.py get                               # dump JSON state
```
