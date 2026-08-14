---
name: cross-source-review
description: cross-source-review (csr) — a same-family (同源, fresh-context) + different-family (异源) cross multi-round review engine that drives a doc-shaped artifact to SUBSTANTIVE convergence. Use it when a high-quality document needs adversarial cross-source review to convergence — "cross-review this requirements doc", "converge this design doc", "异源 review this spec/wiki page", "drive 同源+异源 review on this artifact". Produces a converged artifact + an honest convergence-record. NOT for code review (route to parallel-development), spec/arch-design authoring (blueprint-crafting), or research gathering (blueprint-crafting researcher). Does NOT judge whether the doc is "right" (outcome-axis — human). Phase A activation is EXPLICIT invocation (load this skill by name); auto-routing is deferred.
---

# Cross Source Review

> **DSH port.** Role agents are the preset's `agents/*.agent.md` prompts (spawn via the `subagent` tool); the different-family leg (`hetero_doc_review.py`) spawns an out-of-process CLI subprocess — in DSH the orchestrator is DeepSeek, so the heterogeneous default is `claude` (native auth), qwen3/bigmodel/minimax via profiles.

Drives **same-family** (fresh-context) + **different-family** (cross-family) LLM multi-round review to **substantive convergence** on doc-shaped artifacts — a requirements input before `blueprint-crafting`, a design doc, a wiki page. It is the missing convergence layer upstream of `blueprint-crafting` (which is process-axis, same-family only) and reusable externally (e.g. fedaot wiki review).

## Core Positioning

### Substantive convergence, not zero-finding

A persistent adversarial reviewer always finds finer citation flaws; demanding zero findings loops forever. **Substantive convergence** = the core claims are coverage-verified AND no new BLOCKER-class finding appears for ≥2 rounds. Advisory findings never block (workspace rule 4). Caps bound the loop; cap-hit escalates to the human, never silent-pick (pd ADR #40 (e)).

### Process-axis, not outcome-axis

The skill converges a doc's PROCESS-AXIS quality (well-formed, internally consistent, citation-accurate, coverage-complete). Whether the doc captures the RIGHT requirement is OUTCOME-AXIS — human only. The convergence-record carries `substantive_converged` (process) and never claims outcome correctness.

### Same-family primary; different-family additive

The same-family leg (fresh-context, same family) is PRIMARY and always runs. The different-family leg (cross-family, e.g. DeepSeek) is an opt-in adversarial second opinion that catches same-family blind spots. Both legs are read-only and barred from outcome-axis judgment.

## Scope

- **In**: drive same-family + different-family cross multi-round review of a doc-shaped artifact to substantive convergence; emit the converged artifact + a convergence-record.
- **Out**: code review (`parallel-development`); spec/arch-design authoring (`blueprint-crafting`); research gathering (`blueprint-crafting` researcher); outcome-axis judgment (human).

### Scope Guard (entry-time detection)

- Deliverable is source/test code, or a code diff under review → route to `parallel-development`.
- Deliverable is authoring/rewriting a spec, arch-design, iteration-plan, or research → route to `blueprint-crafting`.
- The request is "is this the right requirement / right conclusion?" → outcome-axis, human only.

The guard is soft (remind + route, not refuse). Phase A relies on **explicit invocation** (`/cross-source-review`); the 3-way `trigger_check` activation partition is DEFERRED to maturation (proposal §9 Q4) — explicit invocation minimizes, but does not zero, routing collision, which is why a Scope Guard still ships.

## Quick Start

You are the orchestrator. The legs are read-only agents/subprocesses; the driver alternates them. Run in order; do not wait for the user between rounds.

**Act from this Quick Start — don't reverse-engineer the legs.** The protocol is this section; the legs are INVOKED, not read: spawn the `agents/doc-reviewer.agent.md` role prompt (its system prompt is its own — do NOT open `agents/doc-reviewer.agent.md`); run `hetero_doc_review.py` (the different-family leg — throughout this skill, the `hetero_*` code prefix names the different-family substrate) via the step-2 CLI (do NOT read its source — the CLI is the contract). Do not hand-validate the schemas — `converge.py` does that; you pass each leg's findings to it. Open `references/install.md` ONLY on a first run in a new project if the provider token/profile is not already clear from the env. The different-family leg's provider(s) are selected by the wrapper from `HETERO_DOC_PROFILE` (settable in `<cwd>/.env.solidforge`; comma-list = dual-different-family; default `claude`) — do NOT pass a hardcoded `--profile`. Each profile's token is its `<NAME>_ANTHROPIC_AUTH_TOKEN` env var (e.g. `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`) — the SOLE source for that profile; do NOT look for or set `<NAME>_API_KEY` (namespace isolation — the `_ANTHROPIC_AUTH_TOKEN` suffix scopes the credential to this substrate; see install.md). The wrapper self-loads `<cwd>/.env.solidforge` then `<cwd>/.env` (shell wins) before reading the token, so a token set in `.env.solidforge` is absent from the shell env — do NOT preflight the token via `echo $VAR` / `os.environ` (a false negative); run the step-2 wrapper directly, which fail-fasts with a clear error if the token is genuinely missing.

1. **Frame** — identify the artifact under review + its authoritative reference (a source doc, or "self-contained / no external authority"). **Enumerate the core claims** (the load-bearing assertions each leg must verify — the coverage-verified prong checks these; omit them and that prong is vacuously true). **Declare the size tier**: short (cap=2) for a single-section / few-claim doc; long (cap=5–7) for a multi-section doc (heuristic: ≥~5 sections or ≥~300 lines — orchestrator judgment, stated in the record).

2. **Round loop** (same-family ↔ different-family, orchestrator-driven) — each round:
   - Run the **same-family leg** — spawn the `agents/doc-reviewer.agent.md` role prompt (a fresh, independent context; it returns a doc-findings object).
   - Reconcile: revise the artifact per accepted findings, or reject a finding with rationale. RECORD each finding's disposition at reconcile time (the producing step for the record's per-round dispositions — fix A): `fixed` = accepted, artifact revised; `rejected` = declined, with rationale (incl. coverage disclosures — not defects, carried in coverage notes); `escalated` = different-family-only findings, escalating to the human (the skill's only named escalation target).
   - Run the **different-family leg** — from the **project root** (the wrapper reads `<cwd>/.env.solidforge`), invoke `python3 "${CLAUDE_PLUGIN_ROOT}/skills/cross-source-review/infra/scripts/hetero_doc_review.py" --artifact <doc> --authority <ref-or-empty> --prior-findings <round-json>` on the revised artifact (fed the same-family findings as prior, so it hunts the gap, not restatements) → doc-findings. **Do NOT pass `--profile`** — the wrapper resolves the provider(s) from `HETERO_DOC_PROFILE` (loaded from `<cwd>/.env.solidforge`, shell wins; comma-list = dual-different-family; default `claude`); a hardcoded `--profile` silently drops every other configured provider. Use the absolute path; do NOT `cd` into the skill dir — cwd must stay at the project root or the token will not resolve.
   - Reconcile again. Apply the per-round reconciliation table (both-report→adopt; same-family-only→adopt; different-family-only→escalate; neither→pass; DEGRADED→adopt same-family).

3. **Convergence judgment** — substantive_converged when core claims are coverage-verified AND no new Blocker for ≥2 rounds. If the cap is hit without convergence → `adversarial-stalemate`, escalate to human (never silent-pick). Verify each leg's factual/citation claims against source independently — do not blind-trust either source.

4. **Emit** — the converged artifact + a `convergence-record` (`infra/schemas/convergence-record.schema.json`): rounds — each carrying the reconciled findings AND their per-finding dispositions, so a reader can list what was found and what was done about it (retention fix A; the counts-only record is obsolete) — `substantive_converged`, coverage notes, stalemate flag.

The pluggable seam: the driver takes `findings-schema` as a parameter (default doc-findings; a future code-shaped caller passes `violation-log`) and the same-family leg as a callback (default `agents/doc-reviewer.agent.md`). This keeps a future code-domain caller a thin adaptation, not a rewrite (proposal §3).

## Authority Chain

- `docs/proposal.md` = authoritative design (master; SUBSTANTIVE-CONVERGED).
- `docs/iteration-plan.md` = execution blueprint (Phase A work-items CSR-I0–CSR-I6).
- `docs/proposal.convergence.md` = the proposal's own cross-review trail (the skill dogfooded on its own design).

## Coordination with blueprint-crafting / parallel-development

- `primary-source-verification` (psv) is the outcome-axis additive layer (per-claim fetched-source verification). GATE MODE: when rule-13 conditions hold, psv runs FIRST as a load-bearing-claims gate (GO/NO-GO batch signal; the gate record is NOT a coverage record); its load-bearing list becomes this skill's core-claims frame; the authoritative full-M psv record follows this skill's convergence. See the psv SKILL.md.

- `blueprint-crafting` stays PURE (process-axis, same-family `plan-reviewer`, deterministic inner ring). It MAY call this skill for a different-family outer pass on its draft — calling a skill, not importing code.
- `parallel-development` owns code review. The different-family substrate here is a copy-PATTERN of pd's `infra/scripts/hetero_review.py` (workspace rule 7 — self-contained deployability; proposal §5 — Phase-B copy-vs-share is evidence-gated, NOT pre-committed); the function-signature contract is preserved + divergences logged for Phase-B viability.
- **Phase-A coordination note**: the bc/pd routing + call relationships above are CSR-side design intent. The reciprocal bc/pd Scope-Guard hints are DEFERRED per proposal §7 / Q4 (Phase A is explicit-invocation only); a reader following these claims into bc/pd will not yet find them mirrored there.
- `files_touched` boundary: this skill owns `cross-source-review/`. It does not modify bc or pd. Phase B (pd adopting this substrate: B1 import / B2 copy / B3 shared-lib) is evidence-gated and out of Phase-A scope.

## Self-Checks (Definition of Done)

A skill change is not done while any self-check fails (workspace rule 1). Run before commit:

```bash
python3 skills/cross-source-review/infra/test/disconnect_check.py        # structure + loading-chain
python3 skills/cross-source-review/infra/test/plugin_layout.py           # plugin.json + hooks.json + agents well-formed
python3 skills/cross-source-review/infra/test/findings_shape_check.py    # every leg emit path produces a doc-findings-valid object (mirror adapter_shape_check)
python3 skills/cross-source-review/infra/test/convergence_policy_check.py # offline caps + stalemate + reconcile + core-claims-coverage round-trip (mirror hetero_review_wiring)
python3 skills/cross-source-review/infra/test/lint_self.py               # dogfood: lints this skill's own infra (ruff)
python3 skills/cross-source-review/infra/test/dogfood.py                 # runs the skill's own convergence loop on its own SKILL.md (skips gracefully when no API tokens; recorded log substitutes)
```

## Reference Files

- [proposal.md](docs/proposal.md) — authoritative design (the 3-skill inventory, non-goals, Phase-A ownership, Phase-B landing points, the §9 locked decisions).
- [iteration-plan.md](docs/iteration-plan.md) — Phase-A execution blueprint (CSR-I0–CSR-I6, DoD, DAG, risks).
- [install.md](references/install.md) — provisioning: the one token var, `.env` resolution, adding a custom provider profile + the token-var naming rule. csr is env-armed (no arm command — its gates are self-gates).
