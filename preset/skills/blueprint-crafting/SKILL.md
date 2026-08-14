---
name: blueprint-crafting
description: |
  blueprint-crafting (bc): Produces convergence-checked upstream artifacts — product spec (PRD), architecture design (arch-design), iteration plan, executable summary, and research — that parallel-development consumes as authoritative references. Use it whenever the user wants to author, rewrite, research, or convergence-check an upstream artifact: "author a spec", "write an arch-design", "produce an iteration-plan", "research X for the spec", "spec-driven", "write a PRD", "author a roadmap", "write a design doc", "decision log". Each artifact converges on its constraints-profile (process axis: anchors + authority-chain + sources); content correctness stays human (outcome axis). NOT for implementing code — feature implementation, bug fixes, and refactors route to parallel-development. Specifier half of the specify then implement pipeline.
---

# Blueprint Crafting

> **DSH port.** Role agents are the preset's `agents/*.agent.md` prompts (spawn via the `subagent` tool); the deterministic convergence stays `infra/scripts/produce.py` (stdlib-only, unchanged).

Produces frozen, convergence-checked upstream artifacts — product spec, architecture design, iteration plan, executable summary, and research — for `parallel-development` to consume as authoritative references. The two skills form a **specify then implement** pipeline.

## Core Positioning

### Constrained production, not check-only

Most upstream artifacts arrive incomplete. This skill does not merely validate; it **authors, rewrites, researches, and checks** them to convergence. Every activity (author / rewrite / research / check) has a **constraints-profile** — the deterministic checks that form its convergence oracle.

- **Process axis** (the convergence loop ran well): the artifact's constraints-profile is satisfied + adversarial reviewer has no Blocker + decisions resolved + no drift. Deterministic, high-confidence, convergeable.
- **Outcome axis** (is the artifact right): is this the correct product / design / conclusion. Only the user/market can judge. Always `human_confirm_required`.

Good output = process-axis convergence, NOT "the artifact is correct." The two axes are kept separate in the verdict (see arch-design §1).

### What it does NOT do

- Does not converge "is this the correct product/design/conclusion" (outcome axis — human/market only).
- Does not implement code. That is `parallel-development`'s job.

## Scope

- **In**: produce convergence-checked upstream artifacts (author / rewrite / research / check), each gated by its constraints-profile.
- **Out**: outcome axis ("correct product/direction/conclusion" — human only); code implementation (`parallel-development`).

### Scope Guard (entry-time detection)

Runs as the first step of invocation, before any production work. The guard keys on the **deliverable**, not on the word "document":

- **In scope**: the deliverable is an upstream artifact itself (a spec, arch-design, iteration plan, executable summary, or research artifact) — produced or converged.
- **Out of scope**: the deliverable is source/test code (a feature, bug fix, refactor, or tests). Emit a misuse hint and route to `parallel-development`.

Misuse hints (terse; fire without loading the full scope detail):

- Implement a feature / fix a bug / refactor code → this skill produces the *spec*, not the *code*. Route: `parallel-development`.
- Execute/follow an existing plan to deliver code → that is plan-driven implementation, not artifact authoring. Route: `parallel-development` (plan-driven mode).
- "Is this the right product direction / is this research conclusion true?" → outcome axis, human only. This skill converges the constraints-profile, not the conclusion.

The guard is **soft**: it reminds and routes, does not refuse. A user may knowingly proceed on a partial fit.

## Quick Start

You are the producer: author the Markdown artifact, then run the deterministic convergence with `produce.py`. The outer ring (`agents/plan-reviewer.agent.md`) is an LLM agent you spawn separately — pass its findings via `--outer` to reach `process_converged`. Do not read `infra/scripts/*.py` to reverse-engineer operator CLIs; `produce.py` is the one entry point and chains the operators as libraries (the individual CLIs are not shell-pipeable — `normalizer` emits a `{plan_model, coverage}` wrapper while the others take a bare plan-model, so shell chaining fails silently green). `infra/test/end_to_end.py` shows the library-API shape (how the operators compose in Python) — it is a developer reference, NOT a `produce.py` CLI example; `produce.py` usage is steps 3–4 below, so do not read end_to_end to learn it.

Run in order; do not wait for the user between steps.

1. Author the artifact (your primary work — write Markdown) covering its anchors — arch-design §3 lists the per-type anchors, `infra/scripts/constraints.json` the profile each `artifact_type` must satisfy.

2. Build `plan-model.json`. Normalize a source with `normalizer.normalize(text, format=fmt)` (returns `{plan_model, coverage}` — keep the `plan_model` half) or construct it directly, then set `plan_model["anchors"]` for every required anchor (author-supplied is authoritative; the normalizer's keyword detection is an advisory fallback). The field contract — required top-level fields, every item field's semantics, and the `subset_tags` three-way classification (executable / upstream_only / downstream_only) — is `infra/schemas/plan-model.schema.json`; **every field carries a `description`, so author against the schema directly**. Do NOT read `plan_model.py` / `freeze.py` / `constraints_check.py` to reverse-engineer the fields — those are embody/check logic, not the contract; the schema is the single source of truth.

3. `python3 infra/scripts/produce.py plan-model.json --out-dir docs/` → runs the inner ring + freeze; prints `process_converged` (false until the outer ring is supplied) and writes `<name>.queue.md` + `.run-record.json`. Fix any named inner Blocker (anchor / authority / ODP) and re-run.

4. Spawn `agents/plan-reviewer.agent.md`; save its findings to `findings.json`; re-run `python3 infra/scripts/produce.py plan-model.json --outer findings.json --out-dir docs/` → `process_converged=true` on a clean outer ring.

If memory says the docs were already converged, read the frozen `.run-record.json` / `.queue.md` to judge whether re-converge is needed — the verdict lives in the run-record, not in the infra source.

## When This Skill Is Invoked

The operational entry point is `produce.py` (see Quick Start above) — the stages below are the conceptual lifecycle it orchestrates as library calls; you do not invoke the individual operator CLIs (they are not shell-pipeable).

Execute the convergence lifecycle for the detected artifact type and activity. The full target lifecycle (operators land across iterations I2–I7; see `docs/iteration-plan.md`):

1. **Scope Guard** (before any work) — out-of-scope (code) → misuse hint + route to `parallel-development`.
2. **Normalize** — heterogeneous source format (rich md / Cursor `.plan.md` / work-package) → plan-model, graded extraction (latch high-confidence / prose semantic-infer low-confidence). Note: `research-notes` is NOT a normalizer input format — research artifacts populate `plan_model["research"]` directly (see step 3), bypassing item-normalization, because the `research.{claims,sources,cost_ledger,staging}` shape has no item-parser. [iteration I2]

   Anchor detection (the completeness input to step 3) is bilingual keyword-based (English + Chinese; aliases in `constraints.json → anchor_detection`, ADR #15). It is a heuristic: the normalizer tags `anchors_meta.source = normalizer-extracted`, so an undetected anchor degrades to a coverage note — never a Blocker (ADR #12, rule 4). For a doc the keyword map under-detects (unusual terminology, a language beyond the aliases), author-supply the anchors map instead: set `plan_model.anchors` directly and `anchors_meta.source = author-supplied` — that map is authoritative, so a missing required anchor becomes a real Blocker (the honest, strong input for the inner ring).
3. **Constraints-check** (inner ring, deterministic over the plan-model) — run the artifact's constraints-profile: completeness (anchors), authority-chain, ODP-tracker, and (for research) sources-cited / staging / cost-bounded / provenance. For the research activity, multi-source web gathering is dispatched to the `agents/researcher.agent.md` agent (it returns the `research` sub-object; the loop places it into `plan_model["research"]`); the constraints-checker then converges it. Profiles live in a registry (`constraints.json`), not hardcoded. [iterations I3, I4]
4. **Adversarial review** (outer ring) — independent `agents/plan-reviewer.agent.md` finds gaps / over-engineering / contradictions / blind spots. [iteration I5]
5. **Verdict** — `process_converged` (high confidence) + `rightness: human_confirm_required` (constant). [iteration I6]
6. **Freeze** — frozen plan-model (round-trip-compatible with `parallel-development` `plan_queue.py` on the executable subset) + spec run-record. [iteration I7]

### Current build status

This is the **I0 scaffold**. Loaded and routing-correct; the operators above are built across I2–I7. What exists now:

- This SKILL.md (activation boundary + scope guard + routing to the design docs).
- The plan-model handshake contract: schema + round-trip assertion with `plan_queue.py` on the executable subset (iteration I1, ADR #1).
- The outer-ring `agents/plan-reviewer.agent.md` agent + findings schema + precision self-check (iteration I5; the agent definition is the deliverable; precision is an LLM eval, not a deterministic gate — ADR #10).
- The normalizer: heterogeneous source format (Cursor `.plan.md` / rich md / work-package) → plan-model with graded extraction (latch high-confidence / prose semantic-infer low-confidence). Heuristics advisory, never a Blocker (rule 4). Anchor detection is bilingual keyword-based (English + Chinese; ADR #15); an undetected anchor degrades to coverage (ADR #12), or author-supply the map for an authoritative check.
- The constraints-checker: inner-ring deterministic gate over the plan-model (anchors + authority-chain + resolve-now ODP), profiles in a registry (`constraints.json`), not hardcoded (rule 2).
- The research constraints-profile: the v1 subset (sources-cited / staging-via-convergence / cost-bounded = Blocker; provenance-tag = warning), modeled on `fedaot-kb` (ADR #4).
- The verdict-emitter + spec run-record: two-field verdict (`process_converged` + `rightness: human_confirm_required` constant), field-isolated — a green process axis never changes the outcome-axis constant.

**All iterations I0–I7 converged** (process-axis acceptance gate, iteration-plan §6, met): normalize → constraints-check → research-constraints → `agents/plan-reviewer.agent.md` → verdict → freeze, end-to-end (produce + defect-repair + round-trip proven in `end_to_end.py`).
The skill is at the process-axis acceptance gate; content correctness stays outcome axis (human).

## Authority Chain

- `docs/arch-design.md` = authoritative spec.
- `docs/iteration-plan.md` = execution blueprint (on conflict, arch-design wins).
- `docs/design-decisions.md` = decision log (ADRs).

## Self-Checks (Definition of Done)

A skill change is not done while any self-check fails (workspace rule 1). Run before
commit:

```bash
python3 skills/blueprint-crafting/infra/test/trigger_check.py      # bidirectional activation boundary
python3 skills/blueprint-crafting/infra/test/disconnect_check.py   # structure + loading-chain
python3 skills/blueprint-crafting/infra/test/plan_model_schema.py  # plan-model schema validator (self-tests)
python3 skills/blueprint-crafting/infra/test/round_trip.py         # executable-subset round-trip with plan_queue.py
python3 skills/blueprint-crafting/infra/test/plan_reviewer_precision.py  # plan_reviewer scaffolding gate (I5; precision eval is LLM, ADR #10)
python3 skills/blueprint-crafting/infra/test/normalizer_goldens.py       # 3-format normalizer goldens (I2; latch vs semantic-infer)
python3 skills/blueprint-crafting/infra/test/constraints_check_goldens.py # constraints-checker: 6 exemplars pass, anchor/authority fail (I3)
python3 skills/blueprint-crafting/infra/test/research_constraints_goldens.py # research v1: sources/staging/cost Blocker, provenance warning (I4)
python3 skills/blueprint-crafting/infra/test/run_record_schema.py  # run-record schema validator (I6)
python3 skills/blueprint-crafting/infra/test/run_record.py         # verdict field-isolation: rightness constant (I6)
python3 skills/blueprint-crafting/infra/test/end_to_end.py         # capstone: produce + converge + defect-repair + round-trip (I7)
python3 skills/blueprint-crafting/infra/test/freeze_goldens.py     # freeze operator: emits a pd-parseable .queue.md + schema-valid .run-record.json (Unit 3)
python3 skills/blueprint-crafting/infra/test/produce_goldens.py    # produce.py orchestrator: one-command convergence (inner -> verdict -> freeze) + --outer + defect/research
python3 skills/blueprint-crafting/infra/test/lint_self.py          # dogfood: lints this skill's own infra (ruff check + format; mirrors the fast_gate)
```

## Coordination with parallel-development

- **Handshake**: the executable subset of the plan-model (`item_id / seq / depends_on / dod_ref`) is round-trip-compatible with `plan_queue.py`'s Phase −1 frozen queue. NOT globally isomorphic — upstream-only metadata is tagged and ignored downstream; downstream-only `blueprint_subset` is left empty / "downstream-filled" (ADR #1).
- **Coupling mode (independence)**: this skill copies `parallel-development`'s patterns (disconnect_check, schema/validator, plan-queue parse) and does NOT import its code (workspace rule 7). Deleting `parallel-development/` leaves this skill working standalone.
- **files_touched boundary**: this skill owns `blueprint-crafting/`; it does not write into `parallel-development/`. The two couple via an artifact (the frozen plan-model), not via file mutation.

## Reference Files

- [arch-design.md](docs/arch-design.md) - authoritative architecture spec (positioning, dual-ring over documents, artifact contract × constraints-profile, core operators, convergence stop condition, coordination with parallel-development)
- [iteration-plan.md](docs/iteration-plan.md) - execution blueprint (iterations I0–I7, complexity tiers, dependency DAG, validation gates, process-axis acceptance gate)
- [design-decisions.md](docs/design-decisions.md) - ADR log (executable-subset round-trip, determinism over the model, constrained production, research constraints-profile, skill name, single-skill-with-modes, research v1 subset)
