# Concept Mapping: SolidForge for Claude Code → SolidForge (DeepSeek Harness)

One table per surface. Left column: SolidForge for Claude Code (upstream). Right column: SolidForge on the DeepSeek Harness (this project, the `solidforge` preset) and how the mapping was re-derived.

## Harness seams

| SolidForge for Claude Code | SolidForge on DeepSeek Harness (this project) | Notes |
| --- | --- | --- |
| Plugin (`skills/`, `agents/`, `hooks/`, `commands/`) | Agent preset `~/.dsh/.agent-presets/solidforge/` (`skills/`, `agents/`, `commands/`, `plugins/`) | A preset is the DSH unit that carries skills + role prompts + composition. |
| `/plugin install` + enable | Select the preset for a session | The composition mounts once per session under a standing scope. |
| `$CLAUDE_PLUGIN_ROOT` | `$SOLIDFORGE_PRESET_ROOT` | Baked into the plugin sources at install time; skills resolve their own base dir via the `skill-filesystem` provider's `baseUrl` wiring (not the skill tool). |
| Skills (SKILL.md, Claude Code native) | The same five skills in the preset's `skills/`, listed in the GUI `/` menu and injectable via a `/name` token (see below) | DSH skill invocation is a slash pipeline, not a per-skill command: the client `skill` input-trigger source feeds the `/` menu from `skill.list`, and the host pre-step boundary (`dsh-tool-skill`) expands any whitespace-delimited `/name` token naming a user-invocable skill into the rendered `<skill_content>` — menu picks, hand-typed tokens, and TUI/ACP prompts all take the same path. A host command wins over a same-named skill; prompt-only abbreviations (`pd`/`bc`/`csr`/`psv`/`pas`) are persona-mapped to full names. |
| `$CLAUDE_PROJECT_DIR` | `$SOLIDFORGE_PROJECT_DIR` (fallback: cwd) | Same semantics: project root for gates and loop state. |
| `.claude/parallel-dev/loop-state.json` | `.solidforge/loop/loop-state.json` | Loop state + runs + snapshots moved under `.solidforge/loop/`. |
| Project memory `CLAUDE.md` | `AGENTS.md` (DSH auto-injects it) | arm.py appends the L1 Constitution + Gate-Toolchain note to `AGENTS.md`. |
| PreToolUse hooks (`blueprint_guard.py`, `counters.py`) | `tools/pre-execute` waterfall listeners (loop-gates plugin) | Same Python scripts; the plugin feeds them the same payload shape and honors `permissionDecision: deny`. |
| PostToolUse hook (`fast_gate.py`) | `tools/post-execute` waterfall listeners (loop-gates plugin) | `decision:block` becomes an `additionalContexts` user message — the model self-corrects next turn, same observable fast-fail. |
| `/solidforge:arm-tools` command | arm-tools command (same procedure, same `arm.py`); `/solidforge` cheat-sheet command | Layer-2 project provisioning unchanged; targets `AGENTS.md`. The commands are registered by the global plugin face (`@maskshell/solidforge`, mounted through the profile patch layer) — any session, any preset. |
| `/solidforge:<skill>` (per-skill generated command) | `/solidforge:<skill>` colon gestures — the same addressing, implemented by the `@maskshell/solidforge` plugin's `agent/pre-step` listener (whitespace-bounded tokens, full names or `pd`/`bc`/`csr`/`psv`/`pas`) | DSH's command grammar rejects `:` in names, so the plugin claims the gesture at the pre-step boundary instead of the command registry — zero harness changes, same observable behavior as Claude Code (deterministic `<skill_content>` injection). Making colon names a first-class command-grammar feature is the upstream RFC in `docs/upstream/`. |
| Scoped subagents `solidforge:<name>` (13–22) | `agents/<name>.agent.md` role prompts spawned via the `subagent` tool | DSH subagents are prompt-instantiated; the role corpus is the preset's `agents/` dir. |
| Built-in `ultracode` workflows / `/loop` | `workflow` tool / goal rounds (`ralph` = fresh-agent variant) | Documented in `references/orchestration-layers.md`. |

## The paper's disciplines

| Paper concept | In SolidForge for Claude Code | In this project |
| --- | --- | --- |
| Axis A — flow-control completeness | Dual-ring convergence loop (fast gate + arch-contract gate, state machine, snapshot rollback) | Identical mechanics: same `loop_state.py` state machine, same gates, ported with only the documented env/path renames (stdlib-only Python; the upstream tree is not vendored, so verbatim identity is stated, not re-checkable here). |
| Axis B — verification-source decoupling | Cross-provider `claude -p` subprocess (`hetero_review.py`), profiles deepseek/qwen/bigmodel/minimax | **Re-derived twice**: (1) the DSH orchestrator IS DeepSeek, so `deepseek` is removed and the heterogeneous set is any different-family route; (2) the substrate is DSH-native — `substrate: dsh` spawns a fresh stateless `dsh --profile headless` subprocess with a throwaway DSH_HOME pinning a different provider/model (same harness, different LLM, out of process); the upstream `claude -p` mechanism survives only as a labeled external-harness opt-in (`substrate: claude-code`), never the default. The boundary is preserved, not bridged — no global in-process multi-provider router. |
| Process/Outcome split (§4.2) | `rightness` enum constant in run-record schemas (bc/csr/psv/pas) | Schemas ported verbatim (constant intact) **plus** the `solidforge-run-record` plugin: a harness-side tool whose execute() is outside the agent's writable workspace and forces `rightness: human_confirm_required` on every record it emits. |
| Salient-gaming structural discipline (§4.3) | Frozen blueprint guard, AC→test-name set gate, no-shrink rule, hard-coded-bypass rollback | Identical: `blueprint_guard.py` / `arch_contract_tests.py` / `snapshot.py` ported; the guard now fires from `tools/pre-execute` deny. |
| Platform-imposed decoupling boundary (§4.4) | Claude Code's process-level provider binding forces heterogeneity out of process | The port does not rely on in-process routing semantics either way (whether the DSH in-process subagent/workflow paths could route to another provider is a harness detail the boundary does not depend on) — the heterogeneous ring stays an OS subprocess — a fresh stateless `dsh --profile headless` session pinned to a different model family (the upstream `claude -p` mechanism survives only as a labeled external-harness opt-in). The port's `model-routing.md` documents the inversion of the paper's worked example. |
| Per-run self-assessment (§6) | `l4_assessment` block + `axis_b_status` observability | Ported with `loop_state.py run-record`; `axis_b_status` honest-reporting discipline carried in the persona + SKILL.md. |

## What was deliberately NOT carried

- The maintainer-facing `docs/` convergence trails of each skill (historical records of the upstream development process). The port carries its own trail in this repo's `docs/`.
- Companion integrations that only exist in the Claude Code ecosystem (Impeccable as a first-class gate; LSP plugins). Their adapters are ported and degrade to coverage-noted no-ops until a DSH equivalent exists.
- The upstream `plugin.json`/`hooks.json` manifests — their DSH equivalents are `agent.cordis.yml` + the plugin sources.
