// solidforge-loop-gates — structural enforcement of the SolidForge deterministic
// gates as DeepSeek Harness tool-event listeners (the DSH port of Claude Code's
// PreToolUse/PostToolUse hooks).
//
// - tools/pre-execute  -> blueprint_guard.py (deny edits to frozen anchors)
//                         counters.py pre (deny edits once the loop is terminal)
// - tools/post-execute -> fast_gate.py (decision:block feedback on lint/format
//                         failure so the agent self-corrects next turn)
//
// The listeners invoke the SAME stdlib Python scripts the parallel-development
// skill ships under infra/hooks/. This source lives OUTSIDE the agent's writable
// workspace — the schema-level discipline of the spec-gaming paper (Process/
// Outcome split §4.2): the agent can neither rewrite the gates nor disable them.
//
// The preset root is baked in at install time (__SOLIDFORGE_PRESET_ROOT__).

const PRESET_ROOT = '__SOLIDFORGE_PRESET_ROOT__'
const PD_INFRA = PRESET_ROOT + '/skills/parallel-development/infra'
const HOOKS = PD_INFRA + '/hooks'

const MUTATING_TOOLS = new Set(['edit', 'write'])
const FILE_ARG_KEYS = ['file_path', 'path', 'target']

function filePathOf(args) {
  if (args === null || typeof args !== 'object') return undefined
  for (const key of FILE_ARG_KEYS) {
    const value = args[key]
    if (typeof value === 'string' && value.length > 0) return value
  }
  return undefined
}

function projectCwd(exec) {
  const headerCwd = exec.agent !== undefined && exec.agent !== null
    && exec.agent.session !== undefined && exec.agent.session !== null
    && exec.agent.session.header !== undefined && exec.agent.session.header !== null
    ? exec.agent.session.header.cwd
    : undefined
  return typeof headerCwd === 'string' && headerCwd.length > 0 ? headerCwd : '.'
}

function gateMessage(callId, text) {
  const summary = text.length > 120 ? text.slice(0, 117) + '...' : text
  return {
    id: 'solidforge-gate-' + callId,
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'plugin', plugin: 'solidforge-loop-gates', form: 'notice', summary },
  }
}

return {
  name: 'solidforge-loop-gates',
  inject: ['subprocess'],
  async apply(ctx) {
    // Run one hook script with a JSON payload on stdin; returns parsed stdout
    // JSON ({} when the hook printed nothing) and rejects only on spawn failure.
    async function runHook(script, payload, extraArgs, cwd, signal) {
      const python = await ctx.subprocess.resolveExecutable('python3', undefined, signal)
      const handle = ctx.subprocess.spawn({
        argv: [python, script, ...extraArgs],
        cwd,
        stdio: { stdin: { data: JSON.stringify(payload) }, stdout: 'pipe', stderr: 'pipe' },
        graceMs: 8000,
        signal,
        env: { SOLIDFORGE_PROJECT_DIR: cwd },
      })
      let out = ''
      for await (const chunk of handle.stdout) {
        out += chunk
        if (out.length > 65536) break
      }
      await handle.done
      try {
        return out.trim() === '' ? {} : JSON.parse(out)
      } catch {
        return {}
      }
    }

    function denyReason(parsed) {
      const spec = parsed !== null && typeof parsed === 'object' ? parsed.hookSpecificOutput : undefined
      if (spec === undefined || spec === null) return undefined
      if (spec.permissionDecision === 'deny') return spec.permissionDecisionReason
      return undefined
    }

    // ── pre-execute: blueprint guard + terminal-state counter ────────────────
    ctx.on('tools/pre-execute', async (exec, next) => {
      const toolName = typeof exec.name === 'string' ? exec.name.toLowerCase() : ''
      if (!MUTATING_TOOLS.has(toolName)) return next()
      const filePath = filePathOf(exec.arguments)
      const cwd = projectCwd(exec)
      if (filePath !== undefined) {
        try {
          const guard = await runHook(HOOKS + '/blueprint_guard.py', {
            tool_name: exec.name,
            tool_input: { file_path: filePath },
          }, [], cwd, exec.signal)
          const reason = denyReason(guard)
          if (typeof reason === 'string') return { kind: 'deny', reason }
        } catch (error) {
          // A gate failure must not wedge the call: fall through to allow.
        }
      }
      try {
        const counters = await runHook(HOOKS + '/counters.py', {
          tool_name: exec.name,
          tool_input: {},
        }, ['pre'], cwd, exec.signal)
        const reason = denyReason(counters)
        if (typeof reason === 'string') return { kind: 'deny', reason }
      } catch (error) {
        // fall through to allow
      }
      return next()
    })

    // ── post-execute: fast gate feedback ─────────────────────────────────────
    ctx.on('tools/post-execute', async (exec, result, next) => {
      const downstream = await next()
      const toolName = typeof exec.name === 'string' ? exec.name.toLowerCase() : ''
      if (!MUTATING_TOOLS.has(toolName)) return downstream
      if (result !== null && result !== undefined && result.isError === true) return downstream
      const filePath = filePathOf(exec.arguments)
      if (filePath === undefined) return downstream
      const cwd = projectCwd(exec)
      let parsed = {}
      try {
        parsed = await runHook(HOOKS + '/fast_gate.py', {
          tool_name: exec.name,
          tool_input: { file_path: filePath },
        }, [], cwd, exec.signal)
      } catch (error) {
        return downstream
      }
      if (parsed !== null && typeof parsed === 'object' && parsed.decision === 'block') {
        const message = gateMessage(exec.callId, String(parsed.reason))
        if (downstream.kind === 'block') {
          return {
            kind: 'block',
            feedback: downstream.feedback,
            additionalContexts: [message, ...(downstream.additionalContexts ?? [])],
          }
        }
        return {
          ...downstream,
          additionalContexts: [message, ...(downstream.additionalContexts ?? [])],
        }
      }
      return downstream
    })
  },
}
