# SolidForge: Port Design & Re-derivation

This document is the port's design rationale: how each discipline of the paper
*spec-gaming-orthogonal-axis.md* is realized on the DeepSeek Harness, and where
the port re-derives (rather than copies) the reference implementation.

The upstream reference implementation is **SolidForge for Claude Code** (a Claude Code plugin). This
project — SolidForge on the DeepSeek Harness — is the `solidforge` agent preset in `~/.dsh/.agent-presets/solidforge/`,
developed from this workspace. A mechanical mapping table lives in
[claude-code-to-dsh-map.md](claude-code-to-dsh-map.md); this document is the
argument-level re-derivation.

## 1. What transfers unchanged (the discipline is harness-independent)

SolidForge's core is a set of **deterministic, stdlib-only Python programs** that
own the convergence loop's state and gates:

- `loop_state.py` — state machine + circuit breakers (thrash N=3, inner cap M=8,
  budget caps) + append-only event log + run-record rollup with the
  `l4_assessment` block (the per-run self-assessment of paper §6);
- `fast_gate.py` / `blueprint_guard.py` / `counters.py` — the per-edit gates
  (cheap lint/format; frozen-anchor read-only guard; terminal-state deny);
- `arch_contract_*.py` — the deterministic architecture-contract gates
  (cycles, layer isolation, API contracts, supply chain, tests, coverage);
- `snapshot.py` / `plan_queue.py` / `scope_check.py` — rollback, plan chaining,
  scope boundary;
- `produce.py` / `converge.py` / `coverage_driver.py` — the blueprint-crafting,
  cross-source-review, and primary-source/prior-art deterministic verifiers;
- `hetero_review.py` / `hetero_doc_review.py` — the cross-provider subprocess
  wrappers (paper §4.4's mechanism, verbatim);
- the JSON schemas carrying the Process/Outcome split — including the
  `rightness` enum with exactly one value (`human_confirm_required`).

None of this references a harness; it references a project directory and env
vars. The port renames the two env seams (`$CLAUDE_PROJECT_DIR` →
`$SOLIDFORGE_PROJECT_DIR`, `$CLAUDE_PLUGIN_ROOT` → `$SOLIDFORGE_PRESET_ROOT`)
and the state directory (`.claude/parallel-dev/` → `.solidforge/loop/`) and
otherwise carries the programs byte-for-byte, tests included. The state machine
semantics — Thrashing → escalate, cap → degrade, budget → hard-terminate, and
the salience defenses (test set must not shrink, no hard-coded bypass, AC→test
name mapping) — are identical because they are the same code.

## 2. The Process/Outcome split, made implementation-level in DSH

Paper §4.2 demands that `rightness` be a **schema invariant the agent cannot
write**, not a prompted rule. Upstream enforces this in the JSON schemas
(enum-of-one) held in plugin code outside the workspace. The port keeps that
enforcement *and adds a stronger seam that DSH makes natural*:

- **`solidforge-run-record` plugin** (`plugins/run-record.host.js`): a harness-side
  tool. Its `execute()` runs in the harness process, reads the loop's own
  `process_converged` emission verbatim, and appends
  `rightness: "human_confirm_required"` — a constant baked into plugin source the
  agent cannot edit (dynamic-plugin sources live outside the session workspace
  and are immutable between activations). There is no code path in the tool that
  writes any other value. The confirmed-correct judgment remains an out-of-band
  human act; the field is a permanent conservative guard, not a state machine
  that reaches "solved" — exactly the paper's anti-gaming property.

- The file-based schemas (bc/csr/psv/pas) still validate the constant for the
  record files the deterministic scripts emit, so both seams agree.

## 3. Hooks become tool-event listeners (structural, not conventional)

Claude Code fires `PreToolUse`/`PostToolUse` hooks per edit. DSH's equivalent is
the tool registry's `tools/pre-execute` / `tools/post-execute` waterfall events
— and they are *strictly stronger* as a structural seam: listeners are plugins
in the harness process, not project files. The **`solidforge-loop-gates`**
plugin (`plugins/loop-gates.host.js`) wires:

| Gate | DSH event | Effect |
| --- | --- | --- |
| `blueprint_guard.py` | `tools/pre-execute` (edit/write) | `{kind:'deny', reason}` — frozen-anchor edits are blocked before dispatch |
| `counters.py pre` | `tools/pre-execute` (edit/write) | deny once the loop state is terminal — a stalled task cannot thrash |
| `fast_gate.py` | `tools/post-execute` (edit/write) | `decision:block` becomes an `additionalContexts` user message; the agent self-corrects next turn, the orchestrator short-circuits the outer ring |

The listeners invoke the same Python gate scripts with the same stdin payload
shape, so the deterministic behavior is byte-identical to upstream. A gate
failure inside the listener can never wedge the tool call (falls through to
allow), and the spawned gate subprocesses are bound to the tool call's abort
signal.

## 4. The heterogeneous ring: the decoupling boundary, re-derived

Paper §4.4's worked example is "a Claude orchestrator reviewed by a
DeepSeek/Qwen/GLM subprocess". The DSH port inverts it: **the DSH orchestrator
is DeepSeek**, so DeepSeek is the same-source family, and the heterogeneous set
is any DIFFERENT provider/model route served by the DSH harness itself (the
pi-ai adapter's routes: Qwen, GLM/BigModel, MiniMax, …):

- `profiles/deepseek.json` is **removed** from the ported profile dirs (it would
  be same-source); the default becomes FAIL-FAST (`HETERO_PROFILE`/`HETERO_DOC_PROFILE` unset →
  arming prompt); the worked dsh-substrate profiles are `zai-coding-cn.json` (`_family:
  zhipu`, effort-supported) and `minimax-cn.json` (`_family: minimax`).
- **The substrate re-derivation (fixed after dogfood round 3).** The first port
  pass copied the upstream mechanism verbatim — `claude -p --settings <profile>` —
  which REUSES the host harness upstream (the plugin lives inside Claude Code)
  but IMPORTS a foreign harness in DSH. Heterogeneity is a different LLM, not a
  different harness: the port now spawns a fresh, stateless **`dsh --profile
  headless`** subprocess whose throwaway `DSH_HOME` pins a different
  provider/model route (`substrate: dsh`, default = FAIL-FAST arming prompt (no placeholder profile; arm one per the shipped `zai-coding-cn.json`/`minimax-cn.json` examples)) —
  same harness, different model family, out of process. The `claude -p` path
  survives only as an explicitly labeled external-harness opt-in
  (`substrate: claude-code`) for Anthropic-compatible-only backends, never the
  default. This is the paper's §8 open-problem-6 contingency resolved: a
  first-class-multi-provider harness re-derives the decoupling boundary by
  keeping the heterogeneous oracle a separate fresh process with its own
  provider pin, instead of inheriting it from a single-provider SDK. The
  boundary ("the heterogeneous ring is additive and non-replacing; the
  same-source ring always runs first") is kept **by design**: the same-source
  in-process ring runs first as the cost/reliability floor, and no global
  in-process multi-provider router is used. Whether the DSH in-process
  subagent/workflow paths could route to another provider is a harness detail
  this boundary does not depend on — the decoupling claim rests on the
  out-of-process leg.
- The **`solidforge-hetero-review`** plugin exposes the leg as a first-class
  tool with the reconciliation contract (both/same-only/hetero-only/neither;
  cap-hit degrades, never silently picks).

This is the port's only *substantive* re-derivation (not a rename), and it is
the mirror image the paper itself names as tier-2 decoupling.

## 5. The agent corpus becomes prompt files

DSH has no filesystem role-agent registry; its `subagent` tool instantiates
children from prompts. The 22 SolidForge agents therefore port as the preset's
`agents/*.agent.md` role-prompt corpus (frontmatter kept; tool names mapped
`Read/Glob/Grep/Bash/Edit/Write/WebSearch` → `read/glob/grep/bash/edit/write/
web_search`; `mcp__*` tools apply only when that MCP server is configured).
Every skill instruction that said "spawn `solidforge:<name>`" now says "spawn
the `agents/<name>.agent.md` role prompt via the `subagent` tool". The role
semantics — same-source adversarial reviewer as the Axis-A outer ring, read-only
tools, context folding — are unchanged.

## 6. Scope line (what the port deliberately does not carry)

- Each upstream skill's `docs/` convergence trail (historical maintainer-facing
  records) — the port keeps its own trail in this repo.
- Claude-Code-only companion integrations (Impeccable detector, official LSP
  plugins): their adapters are ported and degrade to coverage-noted no-ops;
  the reference docs say so.
- A benchmark evaluation: like the upstream, this port is evidence of
  *realizability*, not efficacy (paper §6, §8.3).

## 7. Known upstream quirks inherited

- `cross-source-review/infra/scripts/converge_fixtures/verify.py`'s
  malformed-finding case expects the jsonschema-path error message
  ("malformed finding ... evidence"); without `jsonschema` installed the
  core-reconciliation path fires first with "findings without disposition", so
  that one case fails. Reproduced on the unported upstream tree — inherited,
  not a port regression. `pip install jsonschema` restores the intended path.
