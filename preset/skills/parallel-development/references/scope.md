# Skill Scope Boundary

The companion to SKILL.md's [Scope](../SKILL.md#scope) section. Holds the full scope statement, the structural reason certain tasks are out of scope, the Scope Guard behavior, and the misuse catalog with routing hints.

## Scope

This skill is an implementation execution engine, not a thinking engine.

- **Entry condition**: the task's primary deliverable is source or test code (new feature, bug fix, refactor, added/changed tests, or implementation- adjacent docs — status, trackers, API reference of code just written).
- **Deliverable**: converged code that passes the dual ring — inner Fast Gate + Architecture-Contract Gate + 附加条件; outer AI review against the frozen Intent Blueprint. See Definition of Done in SKILL.md.
- **Out of scope**: design authoring, product specs (PRD), and project roadmaps / iteration plans. These are inputs this skill *consumes* as authoritative references (an arch-design doc, an iteration plan, a frozen **DESIGN.md** from an external skill like Impeccable — see [external-skills.md](external-skills.md)), not artifacts it *produces*.

The hinge is the frozen Intent Blueprint. Everything upstream of code (architecture, roadmap, product spec) is input, not deliverable. All five workflows (feature-dev / bug-fix / refactoring / e2e-testing / documentation) act on a code diff as the deliverable.

## Why these tasks are out of scope

The skill's value scales with **step count × uncertainty** (see [maturity.md](maturity.md): per-step ~95% reliability collapses below 8% over fifty independent steps; the lever is flow control, not a smarter single prompt). The convergence loop's three mechanisms — circuit breaker, context folding, blueprint drift anchor — earn their keep on long, uncertain step chains.

Design review, PRD authoring, and roadmap planning are **short, high-clarity** tasks: they are about thinking clearly, not converging over many steps. On those tasks the loop's leverage is near zero, and a single strong pass from a specialist agent is both cheaper and better than misrouting into Phase 0. This is the structural reason they are out of scope — not an omission.

## Scope Guard (entry-time detection)

Runs as the first step of invocation, before Phase 0. If the primary deliverable is NOT source/test code (user asks to review a design doc, author a PRD, or write a project roadmap/iteration plan):

1. Emit a misuse hint naming the gap between expected quality and what this skill delivers (terse hints inline in SKILL.md; full table below).
2. Recommend the specialist route (see catalog).
3. Offer the choice: hand off to the specialist agent, or proceed knowing the skill adds little and may misroute into the freeze path.

The guard is **soft**: it reminds, does not refuse. Some out-of-scope requests are legitimate partial fits (e.g. a technical/acceptance PRD via Phase 0), and the user may knowingly choose to proceed.

## Misuse catalog

| Detected request | What this skill would do | Quality / expectation gap | Better route |
| --- | --- | --- | --- |
| **Review a design doc / architecture** | Outer-ring review is diff-to-blueprint; with no code diff it degrades to a generic single-pass critique | ≈ baseline Claude; no convergence-gated review; may misroute into freezing the design doc as an AC anchor | `architect` (for code PRs, `code-reviewer`) |
| **Write a PRD** | Phase 0 produces an Intent Blueprint (Use Cases + BDD Given/When/Then AC + NFR) | A *technical/acceptance* PRD, not a *product* PRD (no market, personas, business value); and it wants to proceed to code | `requirements-manager` |
| **Author a project roadmap / iteration plan** | Phase 3 produces a single-task implementation plan (files, complexity, steps) | Too granular and single-task for a project-level roadmap (multi-iteration DAG, gates, dependency edges) | `architect` (roadmap) or `Plan` (single-task plan) |
| **Pure Q&A / explanation (no deliverable)** | No workflow matches; nothing to converge | Skill machinery entirely inert | Direct answer; no agent needed |

## Distinguishing in-scope from out-of-scope docs

The guard keys on the **deliverable**, not the word "document":

- In scope: docs that accompany code just produced (implementation status, test-coverage matrix, API reference of written code) — these are the `documentation` workflow.
- Out of scope: docs that are themselves the deliverable for humans/stakeholders (design, spec, roadmap) — no code diff anchors them.

### Plan authoring vs plan execution (the carve-out)

A "plan" can be either, and the guard must distinguish them:

- **Authoring/designing a plan** (the plan doc is the deliverable — produce an iteration plan, roadmap, or feature plan from scratch) → **out of scope**. Route: `architect` / `requirements-manager`. This is the roadmap row above.
- **Executing a referenced plan** (the user @-references an existing plan AND the deliverable is code) → **in scope**. Enter **plan-driven mode** ([plan-driven-mode.md](plan-driven-mode.md)): the plan is consumed as a work-queue and chained item-by-item to convergence.

The distinguishing test: *is the plan being written, or being followed?*
Writing → out; following → plan-driven mode.
