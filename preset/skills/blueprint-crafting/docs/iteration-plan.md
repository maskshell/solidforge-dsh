# blueprint-crafting — Iteration Plan

> Based on `docs/arch-design.md` (v0.4 proposal). This plan is the **execution blueprint**.
> Structured like `parallel-development`'s plan-driven-mode: complexity tier + dependency edges + **validation gate** (not calendar duration) = the only "done" criterion.
>
> **Authority chain**: `arch-design.md` = authoritative spec; this `iteration-plan.md` = execution blueprint (on conflict, **arch-design.md wins**); `design-decisions.md` = decision log.

## 0. Background and scope

- Current state: proposal frozen (`arch-design.md` v0.4); **no SKILL.md, no scripts, no checker**.
- Scope: zero → minimal viable skill that **authors/rewrites/researches/checks** upstream artifacts, converging each on its constraints-profile (process axis). This is **constrained production**, not "check-only" — see arch-design §1. Production activities (author / rewrite / research) are gated by the constraints-checker; the deterministic-first principle applies to the **constraints layer** (built first), not to a check-only milestone.
- The research activity's constraints-profile is modeled on `ws-wiki/fedaot-kb` (sources / staging / trust / purity / idempotency / cost-bound) — see arch-design §3 + ADR #4.

## 1. Estimation gauge (no day counts)

| Dimension | Meaning | Use |
| --- | --- | --- |
| **Complexity tier** S/M/L/XL | intrinsic difficulty: algorithm novelty × semantic-inference risk × integration surface | per-iteration risk + golden-vector density |
| **Dependency edge** | "X must exist before Y" | execution order + critical path |
| **Validation gate** | an objective "done" criterion: checker passes / exemplar round-trip / production-within-constraints | the unit of progress — no gate, no delivery |

Tier definitions: S = single algorithm, few edge cases; M = several subtleties; L = many subtleties stacked; XL = broad coverage + high integration + hard semantics.

## 2. Overview: iterations, complexity, dependencies, gates

| ID | Iteration | Complexity | Deps | Key validation gate (summary) |
| --- | --- | --- | --- | --- |
| I0 | scaffold + **activation/routing** | M | — | SKILL.md description passes a **trigger test** (activation-positive phrases route here; code-implementation requests route to parallel-development + misuse hint); scope-guard emits out-of-scope for "implement code" |
| I1 | plan-model spec + schema + **round-trip assertion** | M | I0 | plan-model fields defined; **executable subset** (item_id/seq/depends_on/dod_ref) round-trips losslessly with `plan_queue.py`'s frozen queue (ADR #1) |
| I2 | normalizer (format → plan-model) | L | I1 | 3 source formats (rich md / Cursor `.plan.md` / work-package) each golden; graded-extraction confidence tagged |
| I3 | constraints-checker (anchors + authority + ODP) | L | I1, I2 | per-artifact constraints-profiles covered (**profiles in a registry** — §10); the 6 `physics_schema_mcp` exemplars all pass |
| I4 | **research-constraints infrastructure** (sources / staging-via-convergence / cost-bound / provenance — v1 subset) | L | I3 | a research artifact with an unsourced claim → Blocker; research frozen without passing convergence → Blocker; `fedaot-kb` research golden passes the v1 profile (ADR #7) |
| I5 | outer-ring plan-reviewer (adversarial) | L | I2 | independent agent; **precision** — on planted-defect fixtures, hits the **correct** defect (not any Blocker) |
| I6 | verdict-emitter + spec run-record | M | I3, I4, I5 | `process_converged` + `human_confirm_required` (constant); field-isolation assertion |
| I7 | end-to-end: **produce + converge + repair** | M–L | I3, I4, I5, I6 | author/research an artifact within constraints → converge; **plus** a defect-injected fixture reaches `process_converged:false` → repair → flips to `true` |
| — | **Process-axis acceptance gate** | | I7 | see §6 |

> **First package**: do I0 + I1 together (scaffold + activation + plan-model contract are the foundation). After I1, I2 and I5 can parallelize. After I2, I3 runs; I4 follows I3 (research-constraints builds on the generic constraints-checker). I6 closes on I3/I4/I5.

## 3. Foundation layer (I0–I1)

### I0 scaffold + activation/routing — M

- **Goal**: a loadable skill skeleton + self-check framework + **correct activation boundary** (no collision with parallel-development).
- **Deliverables**: `blueprint-crafting/SKILL.md` (description's first line declares the constrained-production scope — author/rewrite/research/check upstream artifacts; scope guard; routes to these docs); `infra/test/` self-check placeholder (disconnect-style structural check); a **trigger test** — N activation-positive phrases ("author a spec", "write an arch-design", "produce an iteration-plan", "research X for the spec", "spec-driven") route here; N activation-negative phrases ("implement this feature", "write code", "fix this bug") route to parallel-development; a misuse-hint mechanism (mirroring parallel-development's Scope Guard step 1).
- **Done when**: SKILL.md is loadable; trigger test passes both directions; scope guard correctly emits out-of-scope for "implement code".
- **Basis**: arch-design §1 (does not implement code), §7 (scope guard); workspace `CLAUDE.md` rule 8 (loading chain / reachability).

### I1 plan-model spec + schema + round-trip assertion — M

- **Goal**: define the two-skill handshake contract (executable subset).
- **Deliverables**: plan-model field definition (**executable subset** item_id/seq/depends_on/dod_ref + upstream metadata complexity/risk/authority-chain/ ODP-status/constraints-profile, the latter tagged); a JSON schema (mirroring run-record.schema.json); a **round-trip assertion**: take a queue frozen by `plan_queue.py`, this skill's plan-model round-trips losslessly on the executable subset; `blueprint_subset` tagged "downstream-filled".
- **Done when**: schema passes the stdlib validator; round-trip lossless on the executable subset (**not** globally — ADR #1).
- **Basis**: arch-design §6 (executable-subset round-trip, ADR #1).

## 4. Normalize + constraints layer (I2–I4)

### I2 normalizer — L

- **Goal**: heterogeneous source format → plan-model, graded extraction.
- **Deliverables**: `normalizer.py`; one golden per source format (3); prose dependency inference tagged with **confidence** (into `coverage`).
- **Done when**: all 3 format goldens have complete fields; prose inference tagged "semantic-infer (low-confidence)"; frontmatter `todos[]` tagged "latch (high-confidence)".
- **Risk**: prose inference is heuristic — tag honestly, never a Blocker (rule 4).

### I3 constraints-checker (anchors + authority + ODP) — L

- **Goal**: inner-ring deterministic gate for the non-research profiles, a direct analog of `disconnect_check`.
- **Deliverables**: `constraints_check.py`; **per-artifact constraints-profiles defined in a registry (e.g. `constraints.json`), not hardcoded** (workspace rule 2); the checker runs the relevant profile on the plan-model; the 6 `physics_schema_mcp` exemplars all pass.
- **Done when**: all 6 exemplars satisfy their profile → pass; a fixture with one anchor removed → fail + names the missing anchor; an authority-chain contradiction → fail.
- **Basis**: arch-design §3 (anchors + cross-artifact mandates), §4.

### I4 research-constraints infrastructure — L

- **Goal**: the research constraints-profile as a real, enforced layer — the v1 subset (ADR #7), modeled on `ws-wiki/fedaot-kb`.
- **Deliverables**: `research_constraints.py` implementing the v1 profile: **sources-cited** (every claim → a fetched source; Blocker); **staging-via-convergence** (research flows through the convergence loop before being frozen into the plan-model — never direct- published; Blocker); **cost-bounded** (declared budget, early-terminate; Blocker when exceeded); **provenance-tag** (each source tagged official-spec / peer-reviewed / vendor-doc / blog / unknown; warning). Idempotency and full trust-tier are **deferved**; fedaot-kb purity is **dropped** (the artifact completeness-checker covers its role).
- **Done when**: a research artifact with an **unsourced** claim → Blocker; research frozen into the plan-model without passing the convergence loop → Blocker; a `fedaot-kb`-style research golden (sources + provenance tags + cost ledger) passes the v1 profile.
- **Basis**: arch-design §3 (research artifact), ADR #4 (the frame) + ADR #7 (the v1 subset). **ODP-4 resolved.**

## 5. Outer ring + close-out (I5–I7)

### I5 outer-ring plan-reviewer — L

- **Goal**: adversarial review (plan-review-repair).
- **Deliverables**: `plan_reviewer` agent (independent context, reports only, does not fix); planted-defect fixtures.
- **Done when**: ≥3 planted-defect fixtures where the reviewer **hits the correct defect** (**precision** — the Blocker corresponds to the planted defect, not any Blocker; workspace rule 4: no Blocker-on-a-guess); schema'd findings output.
- **Basis**: `[[ai-coding-workflow-patterns]]` plan-review-repair, diagnose/repair separation.

### I6 verdict-emitter + spec run-record — M

- **Goal**: two-field verdict, mirroring parallel-development's run-record.
- **Deliverables**: `verdict.py` (`process_converged` + `rightness: human_confirm_required` constant); spec run-record schema + validator.
- **Done when**: run-record passes schema; **field-isolation assertion**: a green process axis **never** changes the `rightness` field (it is a constant).

### I7 end-to-end: produce + converge + repair — M–L

- **Goal**: run the full chain on a real artifact, **producing** (authoring/researching) within constraints, and prove convergence (with repair).
- **Deliverables**: take an incomplete `physics_schema_mcp` artifact (or a seed), **author / research it to convergence** within its constraints-profile, emit plan-model + run-record; **plus a defect-injected fixture** (remove an anchor + inject an authority-chain contradiction + add an unsourced research claim + a resolve-now ODP) → assert `process_converged:false` with the correct flags → repair → flip to `true`.
- **Done when**: the produced artifact converges; the repair fixture flips; the produced plan-model round-trips with `plan_queue.py` on the executable subset.

## 6. Process-axis acceptance gate (after I7)

- All artifact types' constraints-profiles covered (registry-driven, including research).
- All 3 source formats' normalization goldens pass.
- An artifact can be **produced** (authored/researched) to convergence within constraints — not merely pass-through checked.
- The repair fixture flips convergence (convergence proof, not a demo).
- plan-model round-trips losslessly with `plan_queue.py` on the executable subset (ADR #1).
- Verdict field isolation holds (process-axis green ≠ outcome-axis green).
- Activation trigger test passes both directions (I0).

## 7. Dependencies and parallelism

```text
I0 scaffold+activation ─▶ I1 plan-model ─┬─▶ I2 normalizer ─▶ I3 constraints ─▶ I4 research-constraints ─┐
                                         │                                                        │
                                         └─▶ I5 reviewer (parallel from I2) ──────────────────────────────┤
                                                                                                  ▼
                                                          I6 verdict ◀── (I3+I4+I5) ───────────────┤
                                                                                                  ▼
                                                          I7 end-to-end (produce + converge + repair) ◀┘
```

**Parallel fan-out points**: after I1, I2 and I5 can run in parallel; I3 follows I2; I4 follows I3. I6 depends on I3/I4/I5. No XL iterations.

## 8. Risks and mitigations

| Risk | Iteration | Mitigation |
| --- | --- | --- |
| **activation collision** (with parallel-development on "plan"-type requests) | I0 | bidirectional trigger-test assertion; misuse hint |
| plan-model executable subset drifts from `plan_queue.py` | I1 | ADR #1; round-trip assertion in I1 DoD |
| prose dependency inference misjudged | I2 | tag semantic-infer low-confidence honestly; never a Blocker |
| checker false-positive (anchor format differs across formats) | I3 | checker runs on the normalized plan-model; profiles in a registry |
| **research constraint model too heavy / drifts from fedaot-kb** | I4 | ADR #4 frames it; ODP-4 resolves the exact subset within I4 |
| reviewer emits a Blocker on a guess | I5 | precision DoD; rule 4 |
| process-axis green misread as outcome-axis green | I6 | field-isolation assertion; run-record caveats gloss |
| **I7 only pass-through (demo, not convergence/production proof)** | I7 | produce-within-constraints + repair-fixture flip |
| exemplar reference drift (`physics_schema_mcp` / `fedaot-kb` change) | I7 | reference, do not copy; change triggers self-check |

## 9. Out of scope

- SkillOpt-style self-optimization loop (ODP-5 deferred).
- Skill-family split (ODP-2, resolve before I0).
- GUI/UI (ODP-6 deferred).
- Auto-promoting research from staging without human review (staging→promote stays
  human-gated; the skill converges the constraints-profile, not the promotion decision).

## 10. Cross-cutting tasks (across iterations)

| Task | Starts at | Note | Workspace rule |
| --- | --- | --- | --- |
| dogfooding self-check | I0 | this skill's own docs (arch-design + this file + design-decisions) must pass I3's checker | rule 1 |
| **registry/checker split** | I3 | constraints-profiles in a registry (`constraints.json`); checker reads it; adding a profile does not edit the checker | **rule 2** |
| **ADR log** | I1 | `design-decisions.md` (seed ADR #1–#5); non-obvious decisions go to an ADR | **rule 6** |
| **activation/reachability gate** | I0 | bidirectional trigger-test assertion (no collision with parallel-development) | **rule 8** |
| exemplar-as-golden-path | I3 | `physics_schema_mcp` doc family + `fedaot-kb` research pattern = golden; reference, do not copy | rule 7 |
| executable-subset round-trip assertion | I1 | re-run on every plan-model change | — |
| process/outcome-axis isolation review | I6 | re-assert field non-translation on every verdict change | rule 3 |
| research staging never bypassed | I4 | the staging queue is a Blocker constraint; promotion stays human-gated | — |

## Facade impact assessment

This plan builds `blueprint-crafting` itself — the specify-side meta-skill consumed by `parallel-development`. Its facade impact (per CLAUDE.md rule 5): **none at the end-user layer.** The project facade docs (README, USER_GUIDE, GitHub About) describe the plugin's user-facing skills + install flow; they do not enumerate bc's internal anchors, the plan-model schema, or the constraints-checker. So this build changed no end-user facade text. (This section exists because the iteration-plan profile requires the `facade-impact-assessment` anchor — dogfood: bc's own plan satisfies bc's own profile. A plan that DID change a user-visible capability would list the candidate facade sections here for sync.)

## Appendix: execution notes

- **First action**: ODP-2 is closed (single skill, ADR #6) and ODP-4 is closed (v1 subset,
  ADR #7); do I0 + I1 together. (ODP-1 is closed: `blueprint-crafting`.)
- **Every iteration**: write the golden fixture first (expected plan-model / check result /
  reviewer precision / research-constraint verdict), then implement; gate green = deliver.
- **I4 is the research-specific risk center**: the v1 subset is fixed (ADR #7); idempotency
  and full trust-tier remain deferred.
- **Review-revision tracking**: this v0.4 revision responds to the constrained-production
  reframe (drop "check-only v1"; add research artifact + constraints-profile + I4), the
  rename to `blueprint-crafting` (ODP-1 closed, ADR #5), and the fedaot-kb-grounded research
  model (ADR #4). See `design-decisions.md`.
