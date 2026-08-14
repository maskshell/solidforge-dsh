# SolidForge User Guide

> [中文版](USER_GUIDE.md). Organized as: install → run your first convergence → go deeper on demand. Prerequisite: a working DeepSeek Harness (`dsh` on PATH, `$DSH_HOME` initialized).

## Contents

1. [Install & activate](#1-install--activate)
2. [Arm a project](#2-arm-a-project)
3. [Run your first convergence](#3-run-your-first-convergence)
4. [Run records and rightness](#4-run-records-and-rightness)
5. [Configure heterogeneous review](#5-configure-heterogeneous-review)
6. [When to use each of the five skills](#6-when-to-use-each-of-the-five-skills)
7. [Tuning and FAQ](#7-tuning-and-faq)

---

## 1. Install & activate

```bash
git clone https://github.com/maskshell/solidforge-dsh.git && cd solidforge-dsh
bash scripts/install.sh     # → $DSH_HOME/.agent-presets/solidforge/ (idempotent)
```

- **Session-level activation**: pick the **solidforge** preset when starting a session. The session gets the five skills, 22 role agents, and the SolidForge persona; the `/solidforge` and `/arm-tools` slash commands become available once the `commands` plugin runs (below).
- **Structural plugins (optional, recommended)**: four dynamic Cordis plugins turn the gates and invariants into structural enforcement (their code lives outside your workspace — the agent cannot edit it):
  - `loop-gates` — fast gate / blueprint guard / terminal counters on every edit/write (`tools/pre-execute` deny + `tools/post-execute` block feedback);
  - `run-record` — the `solidforge_run_record` tool, forcing `rightness: human_confirm_required`;
  - `hetero-review` — the `solidforge_hetero_review` tool, one-call out-of-process heterogeneous review;
  - `commands` — the `/solidforge` (skill-abbreviation cheat sheet + discipline one-liner) and `/arm-tools` (arm procedure injection) slash commands. DSH's command registry is plugin-owned (`ctx.commands.register`, not filesystem-discovered), so the preset's `commands/arm-tools.md` is not auto-mounted — this plugin is the channel that exposes it.

  Activation: in a cordis-toolset session (e.g. the `cordis` preset), `cordis_define` + `cordis_run` each of `$DSH_HOME/.agent-presets/solidforge/plugins/*.host.js` (baked absolute preset root). **Why not bundled in the preset**: the row that would enable defining them in-preset (`tool-cordis`) registers process-global providers and collides with the `cordis` preset in a multi-preset process — the same deliberate omission as the `standard` preset.
- Without the plugins everything still works: the gate scripts are directly callable from `infra/` (advisory mode).

## 2. Arm a project

The preset never mutates your project, so each target project needs one explicit provisioning (Layer 2):

```bash
python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <your-project>
# optional: --with-tools adds gate tools to the project's own dev deps;
#           --scaffold-configs vale,semgrep,spectral generates external-tool templates
```

Arming (idempotent; `--revert --apply` reverses):

- copies architecture-contract configs for DETECTED languages (skipped honestly when none are detected);
- appends the **L1 Constitution** (uncodable red lines) to the project's `AGENTS.md`;
- copies the Intent Blueprint template + cold-start patterns to `docs/intent-blueprints/_templates/`;
- appends loop runtime state (`.solidforge/loop/`) + `.env`/`.env.solidforge` to `.gitignore`;
- copies `.env.solidforge.example` (hetero-config placeholder, no real tokens);
- prints the gate status table (missing tools degrade loudly, never silently green).

## 3. Run your first convergence

In a solidforge session on an armed project, say:

> "Implement X in parallel, TDD" / "Fix this bug, tests first" / "Refactor module Y, preserving behavior"

The agent freezes the Intent Blueprint (or consumes an existing one) → dispatches RED/GREEN subagents → enters the convergence loop: **inner ring** (per-edit fast gate; at convergence, the architecture-contract gate + no-test-shrink + coverage conditions) → **outer ring** (a same-source `code-reviewer` subagent hunts adversarial findings, semantic line + intent line) → converge/rewrite/rollback by verdict. Breakers watch throughout: same fingerprint ≥3 → escalate to the outer ring; inner ≥8 → degrade/split; budget exhausted → hard-terminate with a diagnosis.

State lives in `.solidforge/loop/loop-state.json` (`loop_state.py summary`).

## 4. Run records and rightness

Every terminal status (converged / suspended / hard_terminated) should emit a run record — via the plugin's `solidforge_run_record` tool, or `python3 <preset>/skills/parallel-development/infra/scripts/loop_state.py run-record` (files land in `.solidforge/loop/runs/`).

Two fields, always separate:

| Field | Meaning | Who writes it |
| --- | --- | --- |
| `converged` / `dod_satisfied` (pd records; bc records: `process_converged`) | both rings green, DoD met (machine-checkable) | the loop / scripts |
| `rightness` | whether the conclusion is correct | **nobody can** — schema constant `human_confirm_required`; correctness is an out-of-band human act |

**Reading the discipline**: green ≠ right. "It ran to completion, therefore it's correct" has no schema exit in this system.

## 5. Configure heterogeneous review

Heterogeneity = **same harness, different LLM, out of process**: the wrapper spawns a fresh, stateless `dsh --profile headless` subprocess whose throwaway `DSH_HOME` pins `agent-default-model` to a pi-ai catalog route of a **different model family**. Three steps:

1. **Create a profile** (filename = route): `cp profiles/minimax-cn.json profiles/<route>.json`, edit `model` and `_family` (the model lineage, used by the same-source guard);
2. **Fill the key**: the credential var is route-derived (`<UPPERCASE(route)>_API_KEY`, pi-ai's own convention), placed anywhere in the three-tier chain: `shell > <project>/.env.solidforge > <project>/.env > <preset-root>/.env.solidforge`;
3. **Select**: `HETERO_PROFILE=<route-a>,<route-b>` (pd leg) and `HETERO_DOC_PROFILE` (csr leg, independent) in `.env.solidforge`.

Built-in guards: a profile whose `_family` is the orchestrator's lineage (deepseek) is REFUSED; a dual run sharing one family gets an honest coverage note ("no blind-spot diversity"); an undeclared `_family` is noted ("guard inactive"). No provider configured → fail-fast with an arming prompt — **never a silent fallback**.

When it runs (protocol): the hetero leg is **opt-in** for high-stakes items only (ADR-level decisions / security-correctness-sensitive / low-confidence same-source verdicts); the same-source ring always runs first, heterogeneity is additive. Reconciliation: both → adopt; same-only → adopt (primary); hetero-only → escalate to a human; neither → pass; hetero degraded (timeout/quota) → adopt same-source, with a fingerprint.

## 6. When to use each of the five skills

| Skill | Use when | Produces | Note |
| --- | --- | --- | --- |
| `parallel-development` | Implementing code: features/bugfixes/refactors/TDD/parallel agents | Converged code + run record | An execution engine, not a thinking engine; PRDs/arch docs go to the next row |
| `blueprint-crafting` | Author/rewrite PRDs, arch designs, iteration plans, executable summaries, research | A frozen, convergence-checked Intent Blueprint | Produces the technical/acceptance PRD, not the product PRD |
| `cross-source-review` | A high-quality document needs adversarial convergence (requirements/design/wiki) | Converged doc + convergence-record | PROCESS axis; it does not judge whether the doc is "right" (outcome axis — human) |
| `primary-source-verification` | Checking a doc's citations/factual claims | Per-claim verdicts + coverage-record | The FETCHED source is the oracle; `oracle_verified_under_known_coverage`, never `correctness_converged` |
| `prior-art-search` | Checking a doc's novelty claims | Per-claim collision verdicts + collision-record | Backward, uncited prior art; never `novel_confirmed` |

csr's ODP-5 discriminator: short docs / predominantly local-citation docs skip the psv gate (csr alone); external-citation-heavy or long docs run psv GATE MODE first (GO/NO-GO), and the authoritative full-M psv record follows csr convergence.


### Combining skills: typical chains

After the per-skill table, the composition table — the skills form the paper's §6 specify→implement pipeline:

| Chain | Trigger utterance (example) | Artifact chain | Honest boundary |
| --- | --- | --- | --- |
| `csr → bc → pd` | "Converge this design doc, then implement it" | convergence-record → frozen blueprint (PRD/arch/iteration plan) → converged code + run-record | csr never judges rightness; bc's rightness stays `human_confirm_required` |
| `psv → csr` | "This doc cites many external sources — verify first, then converge" | gate record (non-authoritative) → convergence-record → full-M coverage-record (the only authoritative one) | psv never emits `correctness_converged`; K>0 escalates to a human |
| `psv + pas` | "Check this paper's citations AND its novelty claims" | coverage-record + collision-record (the two outcome axes in parallel) | pas never emits `novel_confirmed` |
| `psv → csr → bc → pd` | "From this citation-bearing spec, deliver a working implementation" | all four records, end to end | hetero leg opt-in; not-run/degraded reported honestly |

**Full-chain walkthrough** (`psv → csr → bc → pd`):

> "Here is a requirements draft `docs/req.md` with external citations — deliver a working implementation from it."

1. **psv GATE MODE** — the claim-extractor enumerates load-bearing claims → per-claim adjudication against fetched sources → GO/NO-GO. Short / mostly-local-citation docs skip this step (ODP-5 discriminator, saves ~1.5 rounds).
2. **csr** — same-source `doc-reviewer` multi-round adversarial review + the hetero leg for high-risk items (out-of-process, different family). Per-round findings get per-finding dispositions (fix/reject/escalate) → `substantive_converged`. **It converges the PROCESS axis; whether the requirements are right stays yours.**
3. **bc** — plan-reviewer outer ring + deterministic inner ring (constraints-check) → produce and FREEZE the Intent Blueprint. Once frozen, the guard denies edits; changes go through the revision channel only.
4. **pd** — RED/GREEN subagents dispatched in parallel against the blueprint → dual-ring convergence → breakers watching → a run-record at the terminal status (`converged`/`dod_satisfied` strictly separated from the constant `rightness`).
5. **psv full-M (closing, rule-13 docs only)** — after csr convergence, the authoritative per-claim coverage record over the final text.


**Explicit notation** (write the abbreviations straight into the prompt — the most reliable trigger):

```
> psv → csr → psv → bc → pd       take docs/req.md from citation check to a working implementation
> csr → bc → pd                   converge docs/design.md, freeze the blueprint, then implement
> psv + pas                       run citation verification and novelty collision over docs/paper.md in parallel
> pd                              run the implementation convergence loop on the current task
```

Abbreviation map (full names and abbreviations both trigger):

| Abbrev | Skill | Abbrev | Skill |
| --- | --- | --- | --- |
| `pd` | parallel-development | `psv` | primary-source-verification |
| `bc` | blueprint-crafting | `pas` | prior-art-search |
| `csr` | cross-source-review | | |

### How to reference them in DSH

- **Skills are model-side**: write the full name or abbreviation in your prompt (e.g. `pd`, `psv → csr`) and the agent loads the matching SKILL.md through the skill tool. DSH does **not** expose skills as `/pd`-style slash commands (unlike Claude Code's `/skill-name`) — just write the name.
- **The two slash commands** come from the `commands` plugin (§1): `/solidforge` injects the abbreviation table above plus the discipline one-liner into the agent; `/arm-tools` injects the full arming procedure from `commands/arm-tools.md`. They feed content to the agent — they are not the skills themselves.
- The most reliable trigger remains writing the chain abbreviations into the prompt, e.g. `psv → csr → psv → bc → pd`.

## 7. Tuning and FAQ

**Tuning** (`loop_state.py init` flags): inner cap `M=8`, thrash threshold `N=3`, token cap 2M, time cap 1800s, cost cap 5.0, step cap 200. The time axis is the reliable one; tokens are an estimate.

**FAQ**:

- *"no heterogeneous provider configured"* — expected: the fail-fast default. Arm per §5, or consciously forgo heterogeneity.
- *"/solidforge and /arm-tools don't resolve"* — the `commands` plugin is not activated in this session; `cordis_define` + `cordis_run` `plugins/commands.host.js` per §1. Skills are unaffected (write the name/abbreviation directly).
- *"profile X (route Y) needs the credential env var $Z"* — the key is missing from the three-tier chain; the var name is route-derived (§5).
- *Hetero leg `hetero-subprocess-timeout`* — cold start is transient; raise `--timeout` or drop a tier per the docs — never remap the route alias to dodge it.
- *A gate tool is missing* — that gate degrades with a coverage note, never fakes green; `--with-tools` fills the gaps.
- *Test set must not shrink / hard-coded bypass* — the inner gates (AC→test-name mapping + extra conditions) block these; the blueprint guard blocks frozen-doc edits.
- *I want to change the discipline* — read `preset/skills/parallel-development/references/design-decisions.md` (the ADR log) first, then run the `infra/test/` suites.

**Self-checks** (each skill ships a set under `infra/test/`; a selection):

```bash
python3 preset/skills/parallel-development/infra/test/hetero_review_wiring.py
python3 preset/skills/parallel-development/infra/test/plugin_layout.py
python3 preset/skills/blueprint-crafting/infra/test/run_record_schema.py
python3 preset/skills/cross-source-review/infra/scripts/converge_fixtures/verify.py
```

Fuller verification evidence (including this repo's self-review with two heterogeneous false-positive cases): [test/verification.md](test/verification.md) and [docs/dogfood/](docs/dogfood/).
