# blueprint-crafting — Architecture Design (v0.4, proposal)

> Status: proposal (not implemented). This file + `iteration-plan.md` + `design-decisions.md` are the skill's "design + plan + decision log", on disk for review. This file deliberately follows the same convergence-doc pattern it advocates (§3) — i.e. the proposal itself must pass the §4 constraints-checker. That is dogfooding, and the first review assertion.
> **Authority chain**: this `arch-design.md` = authoritative spec; `iteration-plan.md` = execution blueprint (on conflict, **this file wins**); `design-decisions.md` = decision log (ADRs). ODP status: §9 is authoritative; `design-decisions.md` records the rationale.

## 1. Positioning and design philosophy

### What it is

`blueprint-crafting` produces **frozen, convergence-checked upstream artifacts** — product spec, architecture design, iteration plan, executable summary, and research — for `parallel-development` to consume as authoritative references. The two skills form a **specify → implement** pipeline:

```text
blueprint-crafting (specify)            parallel-development (implement)
  authors/rewrites/researches upstream    consumes the frozen plan-model
  converges each artifact on its          converges on "both rings clean"
  constraints-profile (process axis)
  ── frozen plan-model ──▶  plan_queue.py (Phase −1)
```

### Constrained production, not "check-only"

In reality most upstream artifacts arrive incomplete — so the skill does not merely validate; it **authors, rewrites, researches, and checks** them to convergence. Generation is not a deferred "v2"; it is core. The reframe that makes this honest:

> Every activity (author / rewrite / research / check) has a **constraints-profile** — the deterministic checks that form its convergence oracle. Constraints are the **process axis** (deterministic, high-confidence). Content correctness is the **outcome axis** (human only).

So production converges *through* its constraints, not by deferring to humans. The deterministic-first principle still holds — but it means **build the constraints layer first** (the oracle), not "ship a check-only milestone." There is no check-only milestone: production and checking are intertwined from the start.

**Example — research (modeled on `ws-wiki/fedaot-kb`)**: research is not free-form generation. Its constraints-profile is: sources-cited (every claim traceable to a fetched source), staging (output never direct-published; goes to a review/promote queue), trust/provenance tier, direction-normalized (idempotency key), cost-bounded, and a purity filter. Each is a deterministic gate. Only the research *conclusion's correctness* is the outcome axis (human). See `design-decisions.md` ADR #4.

### Core philosophy (from [[convergence-repair-loop]])

Producing upstream artifacts **is itself a convergence problem**, just with a different oracle. The two skills differ only in oracle:

- `parallel-development`'s inner-ring oracle is **deterministic** (compile / test / lint / architecture-contract).
- This skill's oracle has two layers: **semi-deterministic** (the constraints-profile checks on the normalized model) and **adversarial** (plan-review-repair).

So this skill reuses `parallel-development`'s dual-ring convergence architecture and swaps the oracle — the first principle of `convergence-repair-loop` projected onto the "document authoring" domain.

**Determinism boundary (honest)**: the inner-ring determinism holds **over the normalized plan-model, not over the source documents**. The normalizer's graded extraction is high-confidence on latches (frontmatter `todos[]` / latch tables) and low-confidence on prose (semantic-infer of DAG/dependencies). So "deterministic inner ring" here means [semi-deterministic extraction] → [deterministic constraints-check on the model] — structurally different from `parallel-development`, whose inner ring acts directly on machine-form source code. Maintainers must not read `process_converged` as source-document-level determinism (see `design-decisions.md` ADR #2).

### Process axis / outcome axis (the skill's first principle)

| Axis | Meaning | Who can judge | Confidence |
| --- | --- | --- | --- |
| **Process axis** (the convergence loop ran well) | the artifact's constraints-profile is satisfied + reviewer has no Blocker + decisions resolved + no drift | deterministic constraints-checker + adversarial reviewer | **high** — measurable, convergable |
| **Outcome axis** (is the artifact "right") | is this the right product / design / conclusion | only the user/market (Fault 1: user's real need ≠ team's understanding) | always `human_confirm_required` |

**"Good output" = process-axis convergence** — not "the artifact is correct." Two boundary conditions:

- **Process-axis convergence is not "the artifact is correct"**: even when every constraint is satisfied, the product direction or research conclusion may still be wrong (outcome axis).
- **"Is the direction/conclusion right" is not this skill's job**: the reviewer finds gaps / over-engineering / contradictions / blind spots; it does **not** judge "is this a good product direction" or "is this research conclusion true." That belongs to the outcome axis, left to humans.

This is the same principle as `parallel-development`'s Definition of Done, the run-record's `human_confirm_required: true`, and maturity caveat-2 (L4 outcome not self-provable) — moved upstream in the pipeline.

### What it does not do

- Does not converge "is this the correct product/design/conclusion" (outcome axis — human/market only).
- Does not implement code (`parallel-development`'s job).

## 2. System architecture

Dual ring acting on **documents**, with the inner ring organized around per-activity constraints-profiles:

```text
[ heterogeneous source formats: rich md / Cursor .plan.md / work-package ]
         │
         ▼
[ normalizer ] ── graded extraction (latch high-confidence / semantic-infer low-confidence)
         │                                          (NOTE: research artifacts do NOT go through the
         │                                           item-normalizer — `research-notes` is not an input
         │                                           format; `researcher` returns the research sub-object
         │                                           and the loop places it into plan_model["research"])
         ▼
[ plan-model ]  ← round-trip-compatible with plan_queue.py's frozen queue on the executable subset (§6)
         │
         ├─▶ [ inner ring: constraints-checker ] ── runs the artifact's constraints-profile:
         │       · completeness-checker     (anchors present — §3)
         │       · authority-chain-checker  (chain consistent)
         │       · research-constraints     (sources-cited / staging / trust / purity — §3 research)
         │       · ODP-tracker              (resolve-now all resolved?)
         │
         └─▶ [ outer ring: adversarial review ] ── independent plan-reviewer (plan-review-repair)
         │
         ▼
[ verdict emitter ] ── process_converged (high confidence) + rightness: human_confirm_required
         │
         ▼
[ frozen plan-model + spec run-record ] ──▶ parallel-development plan_queue.py
```

**Research sourcing** (research activity): multi-source web gathering is dispatched to the `solidforge:researcher` agent, which returns the `research` sub-object (`claims/sources/cost_ledger/staging`); the loop places it into `plan_model["research"]` (bypassing the item-normalizer, which has no research parser), and `research-constraints` converges it. Conclusion truth stays outcome axis (human).

**Frozen anchor**: produced documents are read-only-enforced during the authoring loop (mirroring `blueprint_guard`) to prevent drift across revision rounds.

## 3. Artifact contract: artifact types × convergence anchors × constraints-profile

Each artifact type **must** carry its anchors (checked on the normalized plan-model, not on source section names) AND satisfy its constraints-profile.

### Product spec (spec / PRD)

Anchors:

- JTBD (what job the user "hires" the product for)
- desired-outcome metrics (not a feature list)
- scope boundary (in-scope + explicitly out-of-scope)
- constraints and assumptions
- decisions already made
- testable acceptance criteria
- non-goals

### Architecture design (arch-design)

Anchors:

- positioning + explicit "what it does NOT do"
- layering and dependency direction
- key technical decisions + rationale
- cross-boundary contracts
- parallel boundaries (files_touched granularity)
- failure modes + degradation paths
- version strategy
- relationship to existing systems

### Iteration plan (iteration-plan)

Anchors:

- complexity tiers
- dependency edges
- per-iteration validation gate (DoD)
- DAG + parallel fan-out points
- phase acceptance gates
- risks and mitigations
- out-of-scope
- cross-cutting tasks
- facade impact assessment (for each user-visible capability the plan introduces/changes, list candidate facade locations — README, USER_GUIDE, GitHub About — that may need sync; a plan changing no user-visible behavior states so explicitly; content advisory per rule 4, presence required like every anchor)

### Executable summary (executable-plan / `.plan.md` / queue)

Anchors:

- machine-readable `todos[id/content/status]` (latch)
- authority deferral (points to spec/blueprint)
- first work-package
- cross-document `dod_ref`

### Research artifact (modeled on `ws-wiki/fedaot-kb`; v1 subset per ADR #7)

Anchors — the constraints-profile for research (v1 keeps the subset that defends research's universal failure modes; idempotency deferred, fedaot-kb purity dropped — see ADR #7):

- **sources-cited** (Blocker): every synthesized claim traceable to a fetched source
- **staging-via-convergence** (Blocker): research flows through the convergence loop before being frozen into the plan-model — never direct-published (defends against hallucination, timeliness, bias)
- **cost-bounded** (Blocker when exceeded): a declared cost budget; call/token/source counts tracked; early-terminate on threshold
- **provenance-tag** (warning): each source tagged by type (official-spec / peer-reviewed / vendor-doc / blog / unknown); full Tier1/2/3 promotion-gating deferred

### Cross-artifact mandates

- **Constraints-profile**: every artifact/activity carries its constraints-profile — the deterministic checks that form its convergence oracle (anchors + authority +, for research, sources/staging/trust/purity).
- **Authority-chain declaration**: spec > blueprint > summary > companion, with a conflict arbitration rule ("on conflict, X wins").
- **ODP status**: every open decision marked resolve-now (blocks convergence) or deferred.

## 4. Core operators

| Operator | Responsibility | Determinism |
| --- | --- | --- |
| `normalizer` | heterogeneous format → plan-model (graded extraction) | semi (prose inference honestly tagged low-confidence) |
| `constraints-checker` | runs the artifact's constraints-profile on the plan-model (completeness + authority + research-constraints + ODP) | **deterministic** (over the model) |
| `authority-chain-checker` | cross-document consistency (syntactic; semantic drift → outer ring) | **deterministic** (over the model) |
| `ODP-tracker` | resolve-now / deferred state | **deterministic** |
| `plan-reviewer` (outer ring) | independent agent, plan-review-repair, finds gaps/over-engineering/contradictions/blind spots | adversarial |
| `researcher` (research sourcing) | independent agent; gathers web + codebase sources, returns the `research` sub-object for the loop to place into `plan_model["research"]`; never judges truth | producer (constrained) |
| `verdict-emitter` | `process_converged` + `rightness: human_confirm_required` + coverage | deterministic output |
| `freeze` | emits the frozen artifacts a converged plan-model hands to `parallel-development` — the projected `.queue.md` + the spec `.run-record.json` (lifecycle step 6; composes `verdict-emitter` + projection; outer ring not run in CLI → coverage-noted) | deterministic output (composes existing operators) |
| `produce` (orchestrator) | the runtime production entry point — chains `constraints-check` / `research_constraints` → `verdict-emitter` → `freeze` as LIBRARY calls (the individual operator CLIs are not shell-pipeable: `normalizer` emits a `{plan_model, coverage}` wrapper while the others take a bare plan-model, so chaining them on the shell feeds the wrong shape and fails silently green); `--outer` injects the plan-reviewer findings to reach `process_converged` | deterministic output (composes existing operators) |

## 5. Convergence stop condition (process axis)

Process-axis convergence requires all of:

1. constraints-checker passes (the artifact's full constraints-profile is satisfied on the plan-model — anchors + authority +, for research, sources/staging/trust/purity).
2. authority-chain-checker passes (no cross-layer contradiction).
3. all resolve-now ODPs closed (deferred ODPs may remain).
4. outer-ring plan-reviewer has no Blocker.

Meeting all four produces a **spec run-record** (mirroring `parallel-development`'s run-record), with fields:

| Field | Meaning |
| --- | --- |
| `process_converged` | process-axis verdict (high confidence). `true` when all four conditions above hold. |
| `rightness` | **constant** `human_confirm_required` — the outcome axis is out of this skill's scope. This marks "not this skill's job", **not** "converged, pending a human stamp". |
| `coverage[]` | which constraints-profile checks ran / were skipped / degraded. |
| `caveats` | e.g. "outcome axis not self-provable". Consumers use the `rightness` constant and this field; do not misread as converged. |

## 6. Coordination with parallel-development

**Handshake = the executable subset of the plan-model**: this skill's frozen plan-model is **round-trip-compatible** with `parallel-development` `plan_queue.py`'s Phase −1 frozen queue on the **executable subset** (`item_id / seq / depends_on / dod_ref`), and is **not** globally isomorphic (see `design-decisions.md` ADR #1). Difference handling:

- This skill's plan-model **additionally carries** `complexity / risk / authority-chain / ODP-status` and the constraints-profile (upstream metadata) — tagged, ignored by `parallel-development`.
- `parallel-development`'s queue carries `blueprint_subset` (a code-execution concern) — no upstream source; left empty / marked "downstream-filled" at round-trip.

**Authority flow**: produced arch-design / iteration-plan become the "authoritative references this skill consumes" that `parallel-development`'s SKILL.md `scope.md` names.

**ODP flow**: upstream deferred ODPs re-surface at `parallel-development`'s plan-queue tail re-validation.

**Coupling mode (independence)**: this skill copies `parallel-development`'s patterns (disconnect_check / run-record schema / ODP semantics) and does not import its code — per workspace `CLAUDE.md` rule 7 (copy-not-import). Deleting `parallel-development/` leaves this skill working standalone.

**files_touched boundary**: this skill owns `blueprint-crafting/`; it does **not** write into `parallel-development/`. The two skills couple via an **artifact** (the frozen plan-model delivered as a file), not via file mutation.

## 7. Boundary validation, honest degradation, failure modes, and version strategy

### Scope Guard

- **In**: produce convergence-checked upstream artifacts (author / rewrite / research / check), each gated by its constraints-profile.
- **Out**: outcome axis ("correct product/direction/conclusion" — human only); code implementation (`parallel-development`).

### Honest degradation (`coverage` explicitly noted)

- prose dependency inference (semantic-infer) is lower-confidence than latch extraction — tagged.
- authority-chain drift is detectable only at the syntactic level; semantic drift → outer-ring reviewer.
- process-axis convergence ≠ outcome-axis correctness — verdict fields are kept separate.

### Failure modes (the skill's own)

| Failure mode | Trigger | Mitigation |
| --- | --- | --- |
| normalizer mis-tags a semantic-infer dependency as a latch | prose that looks like a latch | graded extraction carries a mandatory confidence field; checker never treats low-confidence as a Blocker (rule 4: heuristics are advisory, never Blocker) |
| constraints-checker false-positive (anchor format differs across formats) | same anchor appears differently in different formats | checker runs on the normalized plan-model, not the source doc |
| anchor under-detection on non-English / unusual-terminology prose | keyword map misses an anchor that is present (e.g. a language or phrasing beyond the bilingual aliases) | detection is heuristic and tagged `normalizer-extracted`, so a miss degrades to a coverage note — never a Blocker (ADR #12, rule 4); bilingual English+Chinese aliases cover the common case (ADR #15), and an author-supplied anchors map is authoritative when detection cannot be trusted |
| research claim published without a source | LLM synthesizes an unsourced fact | sources-cited is a Blocker constraint; staging-queue blocks direct publish (ADR #4) |
| reviewer emits a Blocker on a guess | uncertain semantic judgment | I5 DoD requires precision (hits the planted defect); rule 4 |
| plan-model schema evolution breaks round-trip | field add/remove | see "Version strategy" below |
| process-axis green misread as outcome-axis green | consumer misreads the verdict | field separation + run-record `caveats[]` gloss |

### Version strategy

- **plan-model schema evolves additively**: new fields are optional, default empty; removing a field or changing semantics requires a deprecation transition.
- **round-trip compatibility is a contract**: every schema change re-runs the I1 round-trip assertion (executable subset, lossless).
- **This document's own versioning**: v0.1 → v0.2 (review) → v0.3 (English + AI-reader clarity) → v0.4 (constrained-production reframe + research artifact + rename to blueprint-crafting); after freeze, additive changes only.

## 8. References and golden exemplars

- **common wiki**: `[[convergence-repair-loop]]`, `[[ai-coding-workflow-patterns]]`, `[[ux-development-gap]]`, `[[skill-optimization]]`, `[[research-pipeline]]`, `[[knowledge-trust-tiering]]`, `[[staging-area-pattern]]`.
- **golden exemplar (referenced, not copied)**: `ws-edu/physics_schema_mcp/docs/` (6 docs) + `.cursor/plans/*.plan.md` (artifact + authority-chain patterns); `ws-wiki/fedaot-kb` (research-constraints pattern: sources-cited / staging / trust-tier / purity / idempotency / cost-bound).
- **parallel-development**: plan-driven-mode, `plan_queue.py`, Intent Blueprint, run-record, `maturity.md`, `disconnect_check.py`.

## 9. Open Decision Points

| ODP | Question | Status |
| --- | --- | --- |
| ODP-1 | skill name | **decided**: `blueprint-crafting` (human-friendly; "blueprint" = the pre-build plan; pairs with parallel-development). See ADR #5. |
| ODP-2 | single skill with modes (spec/design/plan/research) vs a skill family | **decided (ADR #6)**: single skill with modes; artifact-type/activity is a mode parameter driven by the constraints-profile registry. |
| ODP-3 | relationship between plan-model and `plan_queue.py` | **decided (ADR #1)**: round-trip-compatible on the executable subset, not globally isomorphic; upstream metadata tagged, downstream `blueprint_subset` left empty. Implementation deferred. |
| ODP-4 | research constraints-profile: which source/trust/staging model exactly (adopt fedaot-kb's verbatim, or a subset) | **decided (ADR #7)**: v1 adopts the universal subset (sources-cited + staging-via-convergence + cost-bounded + provenance-tag); idempotency deferred; fedaot-kb purity dropped. |
| ODP-5 | SkillOpt-style self-optimization loop | deferred |
| ODP-6 | GUI/UI vs pure doc/CLI | deferred |

Decision log: `design-decisions.md` (ADR #1–#7).
