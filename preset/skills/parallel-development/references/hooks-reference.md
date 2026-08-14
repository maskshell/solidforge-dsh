# Gate Listeners Reference (DeepSeek Harness tool events)

On-demand reference. The verified DSH tool-pipeline events this skill's deterministic gates rely on, and the `solidforge-loop-gates` plugin that wires them. Read before editing any file under `infra/hooks/` or the plugin sources under the port's `plugins/`. Semantics were confirmed against `dsh-tools` (`tools/pre-execute` / `tools/post-execute` waterfall contracts) in the DSH deployment this preset mounts on.

## How DSH runs the gates

DSH has no hook files: a plugin in the preset listens to the tool registry's waterfall events. The `solidforge-loop-gates` plugin (a dynamic Cordis plugin defined from the port's `plugins/loop-gates.host.js`) registers `ctx.on('tools/pre-execute')` and `ctx.on('tools/post-execute')` listeners that invoke the SAME stdlib Python scripts this skill ships under `infra/hooks/`. The plugin code lives OUTSIDE the agent's writable workspace — the schema-level part of the spec-gaming discipline (§4.2 of the paper): the agent can neither rewrite the gate scripts nor disable the listeners.

| Mechanism | Verified behavior |
| --- | --- |
| `tools/post-execute` (waterfall) | Runs AFTER a tool call settles. A listener may accept, replace, enrich, or BLOCK the normalized result before the model sees it. The fast gate uses this to annotate the result with a `decision:block` reason (the model self-corrects next turn); it cannot undo the edit, matching Claude Code's tools/post-execute. |
| `tools/pre-execute` (waterfall) | Runs BEFORE dispatch. A listener may allow, deny, or ask. The blueprint guard and the terminal-state counter use this to truly BLOCK a call (`deny`), matching tools/pre-execute. |
| Event payload | `exec` carries the tool `name`, parsed `args` (e.g. `file_path` for `edit`/`write`), and the caller agent. Scope-filtered: an agent-scoped listener receives only that agent's calls. |
| Mounting scope | The plugin is defined per session (`cordis_define` + `cordis_run`) from a source file the agent cannot edit; the preset ships the source, the harness executes it. |
| `$SOLIDFORGE_PROJECT_DIR` | Env override for the project root, usable when invoking `infra/hooks/*.py` directly; default is the process cwd. |

## The one unavoidable gap and its faithful alternative

`tools/post-execute` cannot prevent an edit, only react to it. So "the fast gate blocks bad edits" is realized as: the listener runs the gate after the edit; on failure it emits `decision:block` + reason so the agent self-corrects on the next turn, and the orchestrator treats any block as "inner red — short-circuit, do not enter the outer ring". This preserves the spec's fast-fail semantics. `tools/pre-execute` (true pre-block) is reserved for where it is genuinely needed: the frozen-blueprint guard and the terminal-state counter.

## Per-gate contract (what each script fulfills)

| Gate | Event | Mechanism | Contract |
| --- | --- | --- | --- |
| `fast_gate.py` | `tools/post-execute` (on `edit`/`write` results) | `decision:block` on failure | per-file cheap lint/format; records fingerprint in loop-state; queries breaker; emits reason incl. the breaker action; the reason's remediation SPLITS by tool — lint failures (`ruff check`/`eslint`/`swift-format`) → fix-in-ring, format failures (`ruff format`/`google-java-format`/`gofmt`/`rustfmt`) → commit-stratification guidance ([commit-stratification.md](commit-stratification.md)) |
| `blueprint_guard.py` | `tools/pre-execute` (on `edit`/`write`) | deny | blocks Edit/Write to a `status:frozen` blueprint; the only legitimate change path is the revision channel |
| `counters.py` | `tools/pre-execute` (on any mutating call) | deny when terminal | stops edits once loop-state is `suspended`/`hard_terminated`, so a stalled task cannot keep thrashing |

Shared library: `infra/hooks/lib/detect_toolchain.py` (`classify`, `resolve_tool`, `read_payload`, `emit_block`, `deny_block`, `loop_state_path`, `project_root`).

## How to test a gate

Pipe a JSON payload on stdin (same payload shape the plugin passes). A pass is silent (exit 0); a block prints the decision JSON.

```bash
echo '{"tool_name":"edit","tool_input":{"file_path":"/abs/path/app/bad.py"}}' \
  | SOLIDFORGE_PROJECT_DIR=/abs/path python3 infra/hooks/fast_gate.py
```

## Live verification (that listeners actually fire per tool call)

The stdin simulation above proves the gate LOGIC. To prove gates FIRE in a live DSH session, mount the `solidforge-loop-gates` plugin (from the port's `plugins/loop-gates.host.js`) in a session on the `solidforge` preset and run a real tool call:

1. **Pre-execute blueprint_guard**: ask the agent to edit a `status:frozen` blueprint. The guard denies; the agent receives the denial reason and the file is unchanged (md5 identical before/after).
2. **Post-execute fast_gate**: ask the agent to add an unused `import` to a `.py` file. ruff catches F401; the listener emits `decision:block` and the model receives "fast gate is blocking because ruff detected … unused".

The plugin's pre-execute `deny` overrides an allowed permission preset — which is exactly how the guard stays authoritative. This method is deliberately NOT in `smoke_gates.py` (it needs a live harness round per check — too slow for the fast suite); run it manually when you change gate wiring.

For the full arming procedure, see [install.md](install.md). For how the gates fit the convergence loop, see [convergent-loop.md](convergent-loop.md). For why the gates are Python/stdlib and other non-obvious choices, see [design-decisions.md](design-decisions.md).
