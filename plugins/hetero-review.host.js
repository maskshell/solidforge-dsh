// solidforge-hetero-review — the heterogeneous review ring as a first-class tool
// (paper §4.4, reference implementation §6). Registers `solidforge_hetero_review`,
// which delegates to the ported `hetero_review.py` wrapper: it spawns an OS-level
// subprocess of a DIFFERENT model family — DSH-NATIVE by default (a fresh,
// stateless `dsh --profile headless` session pinned to a different provider/model
// route); the upstream `claude -p` mechanism is a labeled external-harness opt-in
// only (substrate claude-code, never the default).
//
// The boundary is the discipline: in-process DSH subagents are SAME-SOURCE by
// construction (the DSH orchestrator is DeepSeek), so the heterogeneous oracle
// is physically out of process — additive and non-replacing over the same-source
// `code-reviewer` primary. The wrapper drives loop_state truthfully around the
// subprocess (ADR #39/#40).

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
  name: 'solidforge-hetero-review',
  inject: ['subprocess'],
  apply(ctx) {
    const harness = ctx.get('harness')
    if (harness === undefined) return

    const tool = harness.defineTool({
      name: 'solidforge_hetero_review',
      description: 'Run the OPT-IN different-family adversarial review leg: spawn hetero_review.py, which launches an out-of-process subprocess on a DIFFERENT model family — DSH-native default: a fresh stateless `dsh --profile headless` session pinned to a different provider/model route (armed profiles, e.g. zai-coding-cn / minimax-cn); the `claude -p` substrate is a labeled external-harness opt-in only — reviewing the diff against the frozen blueprint. ADVISORY + additive: the same-source code-reviewer stays primary; use this only for high-stakes items (ADR-level decisions, security/correctness-sensitive diffs, low-confidence same-source verdicts). Findings are violation-log-shaped with per-provider tags; on budget/turn cap the leg DEGRADES (never silently picks). Credentials resolve from the .env file tiers (project .env.solidforge > .env > preset-root .env.solidforge) — the harness scrubs shell credential vars from plugin-spawned subprocesses, so shell-exported keys are NOT visible to this tool; unarmed routes fail fast, never silently green.',
      parameters: {
        type: 'object',
        properties: {
          diff_ref: { type: 'string', description: 'Path (or git ref) of the diff to review, e.g. the working-tree diff file or HEAD..worktree.' },
          blueprint_ref: { type: 'string', description: 'Path to the frozen Intent Blueprint (authoritative reference).' },
          profile: { type: 'string', description: 'Provider profile name (DSH-native catalog routes, e.g. zai-coding-cn | minimax-cn | qwen-token-plan-cn; claude-code-substrate profiles only as the labeled external-harness opt-in) or comma-list for dual-/multi-different-family. Default: $HETERO_PROFILE; unset = fail-fast arming prompt.' },
          budget_usd: { type: 'number', description: 'Runaway backstop for the subprocess (default 4.0); not real cost for non-Anthropic backends.' },
          timeout: { type: 'number', description: 'Per-subprocess wall-clock cap in seconds (default 600 or $HETERO_TIMEOUT).' },
        },
        required: ['diff_ref', 'blueprint_ref'],
        additionalProperties: false,
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            verdict: { type: 'object', description: 'The violation-log-shaped findings, per-provider tagged; or a degraded marker.' },
            note: { type: 'string', description: 'Reconciliation guidance for the orchestrator.' },
          },
          required: ['verdict', 'note'],
          additionalProperties: false,
        },
        render(_args, value) {
          return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
        },
      },
      async execute(args, exec) {
        const cwd = projectCwd(exec)
        const argv = [PD_INFRA + '/scripts/hetero_review.py', '--embedded', '--diff', String(args.diff_ref), '--blueprint', String(args.blueprint_ref), ]
        if (typeof args.profile === 'string' && args.profile.length > 0) argv.push('--profile', args.profile)
        if (typeof args.budget_usd === 'number') argv.push('--budget-usd', String(args.budget_usd))
        if (typeof args.timeout === 'number') argv.push('--timeout', String(args.timeout))
        const python = await ctx.subprocess.resolveExecutable('python3', undefined, exec.signal)
        const handle = ctx.subprocess.spawn({
          argv: [python, ...argv],
          cwd,
          stdio: { stdin: { data: '' }, stdout: 'pipe', stderr: 'pipe' },
          graceMs: 15000,
          signal: exec.signal,
          env: { SOLIDFORGE_PROJECT_DIR: cwd },
        })
        let out = ''
        let err = ''
        for await (const chunk of handle.stdout) {
          out += chunk
          if (out.length > 1048576) break
        }
        for await (const chunk of handle.stderr) {
          err += chunk
          if (err.length > 65536) break
        }
        const outcome = await handle.done
        if (outcome.exitCode !== 0) {
          return {
            verdict: { degraded: true, provider: args.profile ?? 'default', error: err.trim() || ('exit ' + String(outcome.exitCode)) },
            note: 'different-family DEGRADED: adopt the same-source primary; persist the hetero-degraded fingerprint; never silently pick the hetero verdict.',
          }
        }
        let parsed = {}
        try {
          parsed = out.trim() === '' ? {} : JSON.parse(out)
        } catch {
          parsed = { raw: out.slice(0, 4000) }
        }
        return {
          verdict: parsed,
          note: 'Reconcile: both reported -> adopt; same-source only -> adopt (primary); different-family only -> strong signal, escalate for adjudication; neither -> pass.',
        }
      },
    })
    return harness.registerTool(ctx, tool)
  },
}
