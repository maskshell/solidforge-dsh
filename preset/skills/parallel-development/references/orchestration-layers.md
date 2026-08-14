# Orchestration Layers — convergence loop vs `workflow` orchestration vs goal rounds

Three orchestration primitives operate at different layers. They overlap in shape (all "loop" or "fan-out agents") but are NOT interchangeable. This doc gives the differentiator and worked scenarios so a maintainer or user picks the right one and composes them correctly. Decisions recorded in ADR #32 and ADR #33 of [design-decisions.md](design-decisions.md).

> **Port note.** The upstream doc compared against two Claude Code built-ins (`ultracode` Dynamic Workflows and `/loop`). The DSH equivalents are the `workflow` tool (a JavaScript script the agent writes; the SCRIPT is the orchestrator, fanning work across subagents in phases — the port's direct analogue of `ultracode`) and the `goal` continuation rounds (same-session repeat-until-complete; the `ralph` tool is its fresh-agent variant). The routing advice below transfers verbatim: neither replaces the convergence loop.

## The three primitives (one term each)

- **Convergence loop** — this skill's `Convergent Fix Loop` ([convergent-loop.md](convergent-loop.md)): model-driven, stateful, deterministic-gated, circuit-breaker-bounded, context-folding. Runs inside ONE orchestrator invocation. Per-feature engineering convergence.
- **Workflow orchestration (`workflow` tool)** — DSH's script-driven fan-out: a JavaScript script the agent writes; the SCRIPT is the orchestrator (deterministic routing/loops/stop/phase-tracking), executed by the harness. Intermediate results stay in script variables, not the model context. Many agents per run. Trigger: the `workflow` tool. Cross-cutting/unknown-size/one-off sweeps.
- **Goal rounds (`goal` tools)** — DSH's repeat-until-complete driver: the agent re-fires itself on a completion objective until achieved or blocked. Meta/maintenance convergence (repeat a review-fix until clean).

## Differentiation

| | Convergence loop | `workflow` orchestration | goal rounds |
| --- | --- | --- | --- |
| Layer | engineering (per-feature) | meta / cross-cutting sweep | meta / maintenance |
| Who holds the plan | orchestrator main context (model-driven, stateful) | a JS script (deterministic) | the completion objective |
| Stop condition | gates + circuit breaker (Thrashing/cap/budget) | script condition (loop-until-done) | a clean pass / interval |
| Routing decision | semantic verdict (rewrite/rollback/revision — LLM judgment) | code (route/score/filter) | none (repeats the prompt) |
| Cost/run | predictable (deterministic gates, budgeted) | high (many agents; built for scale) | high (full-context re-fire, cache miss >5min) |
| Best for | per-feature converge with gates + breaker | repo-wide sweep, migration, cross-checked research | repeat-one-prompt-until-clean |

## Worked scenarios — single primitive

### A. Convergence loop — per-feature engineering convergence

Task: "Add OAuth2 login to the FastAPI backend + a React login screen, TDD."

Run: freeze Intent Blueprint (UC/AC/NFR) → RED (`tester`: pytest + Vitest) → GREEN (`backend-developer` + `frontend-developer` parallel) → inner ring [tools/post-execute fast-gate: ruff/eslint; arch-contract at convergence: no circular deps, layer isolation] → outer ring `code-reviewer` (semantic + diff-to-blueprint) → verdict (pass/rewrite/rollback/revision) → breaker.

Why this, not the others:

- Not a `workflow` — per-feature, known structure, predictable budget: avoid scripted orchestration for repeatable, well-defined tasks; a plain subagent dispatch is more efficient.
- Not goal rounds — one-shot converge with a state machine, not a repeat-until-clean meta task.

### B. `workflow` orchestration — cross-cutting sweep

Task: "Find every deprecated `oldCrypto.sign()` call across the 200-service monorepo and migrate it; verify each."

Run: workflow script (agent writes, harness executes) — scan → fan out ONE agent per call-site (worktree isolation) → each migrates + runs that service's tests → adversarial-verifier checks the transform → loop-until-no-failures → merge. Dozens-hundreds of agents, background, intermediate results in script variables (never your context).

Why this, not the others:

- Not convergence loop — the loop is per-feature; it has no deterministic "200-site fan-out" primitive. The orchestrator would walk 200 sites turn-by-turn (context bloat, slow).
- Not goal rounds — needs deterministic per-item parallel orchestration + verification, not a repeated objective.

### C. goal rounds — meta/maintenance convergence

Task: "Review the solidforge skill against AGENTS.md rules 1–12; fix violations; repeat until a full pass finds none."

Run: a goal with the completion objective re-fires "review + fix" → each pass a fresh lens → stop on a clean pass.

Why this, not the others:

- Not convergence loop — the loop converges USER features; this converges the SKILL itself. Different object, no Intent Blueprint/gates.
- Not a `workflow` — a single reviewer per pass needs no deterministic fan-out. (The multi-adversarial-reviewer version IS a workflow — see Complementary 2.)

## Worked scenarios — complementary (layered)

### 1. `workflow` sweep + convergence loop per-unit (B → A)

Task: "Vue 2 → Vue 3 across 80 components."

- Phase 1 — workflow: fan out one agent per component, codemod + adversarial verify, loop-until-all-migrated. Handles scale + determinism across 80 files.
- Phase 2 — convergence loop: for components needing non-mechanical changes (behavior shifted, API shape differs), run this skill per feature — Blueprint, TDD, gates, `code-reviewer` — to converge each. Handles the semantic per-unit verification the workflow's rubric-check cannot encode (arch-contract gates + outer-ring `code-reviewer` are deeper than a workflow verifier).

The workflow does the bulk mechanical work; the convergence loop does the semantic verification. Neither suffices alone.

### 2. goal rounds (single-thread meta) → upgradable to a workflow (multi-adversarial meta) (C → B)

Task: "Keep the skill rule-converged."

- Light (goal rounds): one reviewer per pass — sufficient for single-perspective review-fix-until-clean.
- Heavy (`workflow`): a workflow script fans out one adversarial reviewer per rule family (rule 1 self-gates / rule 5 enumerations / rule 10 writing / …) per pass, merges findings, loops until converged. Same meta-loop, multi-reviewer adversarial verification — for when single-perspective passes miss ripple defects.

Same meta pattern, two strengths. goal rounds are the low-cost version; a workflow is the high-assurance version.

### 3. blueprint `researcher` (in-loop) vs `/deep-research` (standalone) — same research pattern, two layers

Task: "Research the tradeoffs of 5 auth libraries."

- In-loop (skill's `researcher`): blueprint-crafting dispatches `researcher` → emits the `research` sub-object → `research_constraints` converges it (sources-cited/staging/cost/provenance — process axis). For "gather sources for THIS spec's open questions."
- Standalone (a `workflow` script): fans out web searches across angles, fetches + adversarially cross-checks, votes on each claim, synthesizes a cited report. For "investigate broadly; I want a standalone report."

Do not conflate (ADR #13 in blueprint `docs/design-decisions.md`): one is a producer feeding the skill's convergence; the other is a standalone report generator.

## Decision rule

- Per-feature, known structure, needs gates + breaker + semantic verdict → **convergence loop**.
- Cross-cutting, unknown-size, one-off, needs scale + adversarial verify → **`workflow` orchestration**.
- Repeat a single prompt until clean (meta/maintenance) → **`/loop`**.
- Compose: workflow for the sweep + convergence loop for per-unit convergence; `/loop` (or a multi-reviewer workflow) for the skill's self-maintenance.

## Do NOT

- Replace the convergence loop with a `ultracode` workflow script — loses gates + breaker + Intent-Blueprint state; the semantic verdict dispatch cannot become code (ADR #33).
- Replace the convergence loop with `/loop` — unbounded re-fire with no deterministic stop (ADR #32).
- Run a workflow that re-implements what this skill already does (double-spend).
