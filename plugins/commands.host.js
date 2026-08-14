// solidforge-commands — the preset's human-facing slash commands.
//
// DSH's command registry is PLUGIN-OWNED (ctx.commands.register), not
// filesystem-discovered — the preset's commands/arm-tools.md is therefore NOT
// auto-mounted. This plugin closes that gap:
//
//   /arm-tools   steer the full arm-tools procedure (commands/arm-tools.md)
//                to the agent, so it provisions the current project.
//   /solidforge  steer the skill-reference map (names + abbreviations) plus
//                the discipline one-liner.
//
// Skills are a DIFFERENT surface (verified against the shipped
// dsh-client-ui-skill + dsh-tool-skill packages): the GUI "/" menu lists them
// via the `skill` input-trigger source, and a `/name` token (full kebab-case
// name) anywhere in the user message is deterministically expanded to the
// rendered skill body at the host pre-step boundary — no skill-tool call
// needed. A host command wins over a same-named skill. Abbreviations
// (pd/bc/csr/psv/pas) are prompt-only: the persona maps them to full names.

const PRESET_ROOT = '__SOLIDFORGE_PRESET_ROOT__'
const COMMANDS_DIR = PRESET_ROOT + '/commands'

function steerMessage(text, summary) {
  return {
    id: 'solidforge-command-' + Date.now() + '-' + Math.floor(Math.random() * 1e6),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'plugin', plugin: 'solidforge-commands', form: 'notice', summary },
  }
}

const SKILL_MAP = `SolidForge skills — two invocation channels:
- SLASH: /parallel-development, /blueprint-crafting, /cross-source-review,
  /primary-source-verification, /prior-art-search (also listed in the GUI "/"
  menu). A /name token anywhere in the user message is expanded by the host
  pre-step boundary into the rendered skill body — deterministic, no skill-tool
  call needed. Full kebab-case names only; a host command with the same name
  wins over the skill.
- PROMPT: full name OR abbreviation, e.g. "pd" or "psv → csr" — the persona
  maps abbreviations to full names and the agent loads the skill via the skill
  tool.
  - pd = parallel-development  — implementation convergence (dual-ring loop)
  - bc = blueprint-crafting    — specify-side artifacts (PRD/arch/iteration plan)
  - csr = cross-source-review  — adversarial document convergence (process axis)
  - psv = primary-source-verification — per-claim fetched-source verification (outcome axis)
  - pas = prior-art-search     — novelty collision detection (outcome axis)
Chains in one line work too, e.g. "psv → csr → psv → bc → pd" (psv gate → csr converge → psv full-M → bc blueprint → pd implement).
Discipline one-liner: green gates prove process convergence, not correctness; rightness stays human_confirm_required.`

return {
  name: 'solidforge-commands',
  inject: ['subprocess'],
  async apply(ctx) {
    const commands = ctx.get('commands')
    if (commands === undefined) return
    const disposers = []

    disposers.push(commands.register({
      name: 'solidforge',
      description: 'SolidForge skill reference map + discipline one-liner',
      handler(invocation) {
        invocation.agent.steer(steerMessage(SKILL_MAP, 'solidforge skill map'))
        return { kind: 'success', text: 'SolidForge skill map steered to the agent.' }
      },
    }))

    disposers.push(commands.register({
      name: 'arm-tools',
      description: 'Arm the current project for the SolidForge convergence loop (Layer 2 provisioning)',
      handler: async (invocation) => {
        let procedure
        try {
          const cat = await ctx.subprocess.resolveExecutable('cat', undefined, invocation.signal)
          const handle = ctx.subprocess.spawn({
            argv: [cat, COMMANDS_DIR + '/arm-tools.md'],
            cwd: PRESET_ROOT,
            stdio: { stdin: { data: '' }, stdout: 'pipe', stderr: 'pipe' },
            graceMs: 8000,
            signal: invocation.signal,
          })
          let out = ''
          for await (const chunk of handle.stdout) {
            out += chunk
            if (out.length > 65536) break
          }
          for await (const chunk of handle.stderr) {
            // drain; cat emits nothing on stderr for a readable file
          }
          await handle.done
          procedure = out
        } catch (error) {
          procedure = ''
        }
        if (procedure.trim() === '') {
          return { kind: 'error', text: 'arm-tools procedure file unavailable — run: python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <project-dir>' }
        }
        invocation.agent.steer(steerMessage(
          'Follow this procedure exactly:\n\n' + procedure,
          'arm-tools procedure'
        ))
        return { kind: 'success', text: 'Arming procedure steered to the agent.' }
      },
    }))

    ctx.effect(() => () => {
      for (const dispose of disposers) dispose()
    })
  },
}
