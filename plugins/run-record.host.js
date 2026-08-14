// solidforge-run-record — the Process/Outcome split as a schema-level invariant
// (paper §4.2, reference implementation §6). Registers a `solidforge_run_record`
// tool whose execute() lives OUTSIDE the agent's writable workspace.
//
// The invariant: `rightness` is an enum the agent cannot write. The tool forces
// `rightness: "human_confirm_required"` on EVERY record it emits — the constant
// is baked into this plugin code, not into any project file the agent could
// rewrite. `process_converged` (the loop's machine-checkable axis) is taken
// verbatim from loop_state.py's own run-record emission; correctness is never
// auto-satisfied by process success.

const PRESET_ROOT = '__SOLIDFORGE_PRESET_ROOT__'
const PD_INFRA = PRESET_ROOT + '/skills/parallel-development/infra'

function projectCwd(exec) {
  const headerCwd = exec.agent !== undefined && exec.agent !== null
    && exec.agent.session !== undefined && exec.agent.session !== null
    && exec.agent.session.header !== undefined && exec.agent.session.header !== null
    ? exec.agent.session.header.cwd
    : undefined
  return typeof headerCwd === 'string' && headerCwd.length > 0 ? headerCwd : '.'
}

return {
  name: 'solidforge-run-record',
  inject: ['subprocess'],
  apply(ctx) {
    const harness = ctx.get('harness')
    if (harness === undefined) return

    async function runLoopRecord(cwd, signal) {
      const python = await ctx.subprocess.resolveExecutable('python3', undefined, signal)
      const handle = ctx.subprocess.spawn({
        argv: [python, PD_INFRA + '/scripts/loop_state.py', 'run-record'],
        cwd,
        stdio: { stdin: { data: '' }, stdout: 'pipe', stderr: 'pipe' },
        graceMs: 15000,
        signal,
        env: { SOLIDFORGE_PROJECT_DIR: cwd },
      })
      let out = ''
      for await (const chunk of handle.stdout) {
        out += chunk
        if (out.length > 262144) break
      }
      const outcome = await handle.done
      if (outcome.exitCode !== 0) return undefined
      try {
        return out.trim() === '' ? undefined : JSON.parse(out)
      } catch {
        return undefined
      }
    }

    const tool = harness.defineTool({
      name: 'solidforge_run_record',
      description: 'Emit the normalized run record for the current convergence-loop task. The record carries the loop\\'s machine-checkable `process_converged` axis VERBATIM from loop_state.py, plus the outcome axis `rightness`, which is a schema constant `human_confirm_required` ENFORCED BY THIS TOOL — the agent can never write a confirmed/auto-satisfied value, and no oracle verdict substitutes for human confirmation of correctness. Call it at every terminal loop status (converged / suspended / hard_terminated) so the run is auditable.',
      parameters: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'One-line folded summary of the run (status + gates + breaker state).' },
        },
        required: [],
        additionalProperties: false,
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            record: { type: 'object', description: 'The emitted run record (loop_state.py shape + the rightness constant).' },
            rightness_note: { type: 'string', description: 'Invariant reminder: what the rightness constant means.' },
          },
          required: ['record', 'rightness_note'],
          additionalProperties: false,
        },
        render(_args, value) {
          return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
        },
      },
      async execute(args, exec) {
        const cwd = projectCwd(exec)
        const loop = await runLoopRecord(cwd, exec.signal)
        if (loop === undefined) {
          return {
            record: { error: 'loop_state.py run-record failed — run `loop_state.py init` first and reach a terminal status before emitting the record.' },
            rightness_note: 'rightness is a schema constant: human_confirm_required.',
          }
        }
        // The invariant. This line is the port of the paper's §4.2 schema
        // constant: no branch in this tool ever writes another value.
        const record = { ...loop, rightness: 'human_confirm_required' }
        if (typeof args.summary === 'string' && args.summary.length > 0) record.summary = args.summary
        return {
          record,
          rightness_note: 'rightness is human_confirm_required by design — the loop cannot write it, the tool cannot write anything else, and process_converged is never a correctness claim. Human confirmation is an out-of-band act, not a schema state.',
        }
      },
    })
    return harness.registerTool(ctx, tool)
  },
}
