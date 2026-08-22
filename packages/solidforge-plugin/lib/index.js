// @maskshell/solidforge — the globally installed plugin face of SolidForge on
// the DeepSeek Harness. Mounted through the user patch layer of a dsh profile
// (`$DSH_HOME/profiles/<name>/cordis.patch.yml`), so every session of that
// profile gets it without preset switching.
//
// What this plugin does:
//
//   1. SKILLS (host layer): registers the five SolidForge skills read from the
//      preset directory, so every session's catalog and "/" menu list them.
//   2. COLON GESTURES: a root-level `agent/pre-step` waterfall listener
//      expands whitespace-bounded `/solidforge:<name>` tokens in user messages
//      into the rendered <skill_content> injection — the same gesture boundary
//      dsh-tool-skill uses for `/name` tokens. Full kebab-case names AND the
//      persona abbreviations (pd/bc/csr/psv/pas) resolve. This is the DSH
//      plugin-ecosystem answer to Claude Code's /plugin:skill commands.
//   3. COMMANDS: `/solidforge` (skill map + discipline one-liner) and
//      `/arm-tools` (Layer-2 arming procedure) steer their content to the
//      calling agent.
//   4. OPT-IN SWITCHES (patch-entry config):
//        persona: true — registers an additive `solidforge:discipline`
//          system-prompt section (order 50, after the deployment persona,
//          before tool guidance) carrying the two-axis discipline, the
//          abbreviation map, and the role-agent guidance for ANY preset.
//        gates: true — registers the structural gate subsystems
//          (lib/gates.js: tool-event gates, the rightness-invariant
//          run-record tool, the heterogeneous review tool) from the profile
//          root, so they fire for every session of the profile; un-armed
//          projects degrade honestly (UNVERIFIED notices, never silent).
//   The dynamic plugins in the preset's plugins/ dir remain the per-session
//   alternative when the global gates are off.
//
// Design constraints (verified against the deployment):
//   - The profile patch layer's root context is UNscoped, and scoped agent
//     events pass their filter for unscoped contexts, so a root-level
//     `agent/pre-step` listener receives every agent's steps.
//   - The preset is the single source of the skill bodies; this plugin reads
//     them live (no copy, no drift) and degrades honestly when the preset is
//     not installed (skills unregistered, gestures skipped, /arm-tools fails
//     loud — never silently green).
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'

export const name = 'solidforge'
export const inject = ['skills', 'systemPrompt']

const SKILLS = {
  'parallel-development': 'pd',
  'blueprint-crafting': 'bc',
  'cross-source-review': 'csr',
  'primary-source-verification': 'psv',
  'prior-art-search': 'pas',
}
const ABBREVIATIONS = Object.fromEntries(
  Object.entries(SKILLS).map(([full, abbreviation]) => [abbreviation, full]),
)
// Whitespace-bounded /solidforge:<name> token — same word-boundary shape as
// dsh-tool-skill's SKILL_GESTURE, so the token reads as one wherever it sits.
const COLON_GESTURE = /(^|\s)\/solidforge:([a-z0-9-]+)(?=\s|$)/g

function presetRoot() {
  const home = process.env.DSH_HOME ?? join(process.env.HOME ?? '', '.dsh')
  return join(home, '.agent-presets', 'solidforge')
}

/**
 * Parse the `name` / `description` frontmatter and body of one SKILL.md.
 * The description is a YAML block scalar (enforced by our CI suite), so the
 * parser only needs the block form.
 */
function parseSkillFile(raw) {
  const match = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(raw)
  if (match === null) return undefined
  const frontmatter = match[1]
  const nameMatch = /^name:[ \t]*([a-z0-9-]+)[ \t]*$/m.exec(frontmatter)
  const descriptionMatch = /^description:[ \t]*[|>][+-]?[ \t]*\n([\s\S]*?)(?=^[a-zA-Z][^:\n]*:[ \t]|\n---|$)/m.exec(frontmatter)
  if (nameMatch === null || descriptionMatch === null) return undefined
  const description = descriptionMatch[1]
    .split('\n')
    .map((line) => line.replace(/^ {1,2}/, ''))
    .join(' ')
    .replaceAll(/\s+/g, ' ')
    .trim()
  if (description.length === 0) return undefined
  return { name: nameMatch[1], description, content: match[2].trim() }
}

function escapeAttr(value) {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')
}

function escapeText(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

/** Byte-compatible with dsh-skill's renderSkillContent output shape. */
function renderSkillContent(skill) {
  return [
    `<skill_content name="${escapeAttr(skill.name)}">`,
    '<skill_resources>',
    `Base directory for this skill: ${escapeText(skill.resourceBase.path)}`,
    'Resolve relative paths mentioned by this skill against the base directory before using them. Load referenced resources only as needed.',
    '</skill_resources>',
    '',
    '<skill_instructions>',
    skill.content,
    '</skill_instructions>',
    '</skill_content>',
  ].join('\n')
}

function colonTokens(messages) {
  const tokens = []
  for (const message of messages) {
    if (message.source?.kind !== 'user') continue
    for (const block of message.content ?? []) {
      if (block.type !== 'text') continue
      for (const match of block.text.matchAll(COLON_GESTURE)) {
        const token = match[2]
        if (token !== undefined && !tokens.includes(token)) tokens.push(token)
      }
    }
  }
  return tokens
}


function presetHash(root) {
  const h = createHash('sha256')
  const files = []
  const walk = (dir) => {
    let entries
    try {
      entries = readdirSync(dir)
    } catch {
      return
    }
    entries.sort()
    for (const entry of entries) {
      if (entry === '.git' || entry === '__pycache__' || entry === '.ruff_cache') continue
      const full = join(dir, entry)
      let st
      try {
        st = statSync(full)
      } catch {
        continue
      }
      if (st.isDirectory()) {
        walk(full)
        continue
      }
      if (entry === '.DS_Store' || entry === '.preset-stamp.json' || entry.endsWith('.pyc')) continue
      files.push(full)
    }
  }
  walk(root)
  for (const full of files) {
    h.update(full.slice(root.length))
    h.update(readFileSync(full))
  }
  return h.digest('hex')
}

function presetStamp(root) {
  try {
    return JSON.parse(readFileSync(join(root, '.preset-stamp.json'), 'utf8'))
  } catch {
    return undefined
  }
}

function steerMessage(text, summary) {
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text }],
    source: { kind: 'plugin', plugin: 'solidforge', form: 'notice', summary },
  }
}

const SKILL_MAP = `SolidForge skills — three ways to invoke:
- COLON: /solidforge:parallel-development, /solidforge:blueprint-crafting,
  /solidforge:cross-source-review, /solidforge:primary-source-verification,
  /solidforge:prior-art-search — or by abbreviation, e.g. /solidforge:psv.
  The host pre-step boundary deterministically injects the rendered skill body.
- FLAT: the same five names (also listed in the GUI "/" menu) — a /name token
  anywhere in the user message is expanded the same way.
- PROMPT: full name OR abbreviation, e.g. "pd" or "psv → csr" — the solidforge
  preset's persona maps abbreviations to full names and loads via the skill tool.
  - pd = parallel-development  — implementation convergence (dual-ring loop)
  - bc = blueprint-crafting    — specify-side artifacts (PRD/arch/iteration plan)
  - csr = cross-source-review  — adversarial document convergence (process axis)
  - psv = primary-source-verification — per-claim fetched-source verification (outcome axis)
  - pas = prior-art-search     — novelty collision detection (outcome axis)
Chains in one line work too, e.g. "psv → csr → psv → bc → pd" (psv gate → csr converge → psv full-M → bc blueprint → pd implement).
Discipline one-liner: green gates prove process convergence, not correctness; rightness stays human_confirm_required.`

// ── structural gates subsystem (merged single-file; DSH packages are
// single-bundle by convention — relative imports are NOT loader-safe) ──
function registerGates(ctx, presetRoot, warn) {
  const subprocess = ctx.get('subprocess')
  const tools = ctx.get('tools')
  if (subprocess === undefined || tools === undefined) {
    warn('gates:true requested but subprocess/tools services unavailable — gates NOT registered (advisory mode)')
    return []
  }
  const PD_INFRA = presetRoot + '/skills/parallel-development/infra'
  const HOOKS = PD_INFRA + '/hooks'
  const disposers = []
  const gateFailures = new Map()

  async function runHook(script, payload, extraArgs, cwd, signal) {
    const python = await subprocess.resolveExecutable('python3', undefined, signal)
    const handle = subprocess.spawn({
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
  disposers.push(ctx.on('tools/pre-execute', async (exec, next) => {
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
      } catch {
        gateFailures.set(exec.callId, (gateFailures.get(exec.callId) || '') + ' blueprint_guard.py failed to run — treated as UNVERIFIED; ')
      }
    }
    try {
      const counters = await runHook(HOOKS + '/counters.py', {
        tool_name: exec.name,
        tool_input: {},
      }, ['pre'], cwd, exec.signal)
      const reason = denyReason(counters)
      if (typeof reason === 'string') return { kind: 'deny', reason }
    } catch {
      gateFailures.set(exec.callId, (gateFailures.get(exec.callId) || '') + ' counters.py failed to run — treated as UNVERIFIED; ')
    }
    return next()
  }))

  // ── post-execute: fast gate feedback ─────────────────────────────────────
  disposers.push(ctx.on('tools/post-execute', async (exec, result, next) => {
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
    } catch {
      const message = gateMessage(exec.callId, ' fast_gate.py failed to run — treated as UNVERIFIED (gate failure must never be silent).')
      if (downstream.kind === 'block') {
        return { kind: 'block', feedback: downstream.feedback, additionalContexts: [message, ...(downstream.additionalContexts ?? [])] }
      }
      return { ...downstream, additionalContexts: [message, ...(downstream.additionalContexts ?? [])] }
    }
    const notices = []
    const preFailure = gateFailures.get(exec.callId)
    if (typeof preFailure === 'string' && preFailure.length > 0) {
      notices.push(gateMessage(exec.callId, preFailure.trim()))
      gateFailures.delete(exec.callId)
    }
    if (parsed !== null && typeof parsed === 'object' && parsed.decision === 'block') {
      notices.push(gateMessage(exec.callId, String(parsed.reason)))
    }
    if (notices.length === 0) return downstream
    if (downstream.kind === 'block') {
      return {
        kind: 'block',
        feedback: downstream.feedback,
        additionalContexts: [...notices, ...(downstream.additionalContexts ?? [])],
      }
    }
    return {
      ...downstream,
      additionalContexts: [...notices, ...(downstream.additionalContexts ?? [])],
    }
  }))

  // ── run-record tool: rightness as a schema constant (§4.2) ──────────────
  async function runLoopRecord(cwd, signal) {
    const python = await subprocess.resolveExecutable('python3', undefined, signal)
    const handle = subprocess.spawn({
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

  disposers.push(tools.register({
    name: 'solidforge_run_record',
    description: 'Emit the normalized run record for the current convergence-loop task. The record carries the loop\'s machine-checkable `converged` / `dod_satisfied` axes VERBATIM from loop_state.py, plus the outcome axis `rightness`, which is a schema constant `human_confirm_required` ENFORCED BY THIS TOOL — the agent can never write a confirmed/auto-satisfied value, and no oracle verdict substitutes for human confirmation of correctness. Call it at every terminal loop status (converged / suspended / hard_terminated) so the run is auditable.',
    parameters: {
      type: 'object',
      properties: {},
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
    async execute(_args, exec) {
      const cwd = projectCwd(exec)
      const loop = await runLoopRecord(cwd, exec.signal)
      if (loop === undefined) {
        return {
          record: { error: 'loop_state.py run-record failed — run `loop_state.py init` first and reach a terminal status before emitting the record.' },
          rightness_note: 'rightness is a schema constant: human_confirm_required.',
        }
      }
      const record = { ...loop, rightness: 'human_confirm_required' }
      return {
        record,
        rightness_note: 'rightness is human_confirm_required by design — the loop cannot write it, the tool cannot write anything else, and a green process axis is never a correctness claim. Human confirmation is an out-of-band act, not a schema state.',
      }
    },
  }))

  // ── heterogeneous review tool (paper §4.4) ───────────────────────────────
  disposers.push(tools.register({
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
      const argv = [PD_INFRA + '/scripts/hetero_review.py', '--embedded', '--diff', String(args.diff_ref), '--blueprint', String(args.blueprint_ref)]
      if (typeof args.profile === 'string' && args.profile.length > 0) argv.push('--profile', args.profile)
      if (typeof args.budget_usd === 'number') argv.push('--budget-usd', String(args.budget_usd))
      if (typeof args.timeout === 'number') argv.push('--timeout', String(args.timeout))
      const python = await subprocess.resolveExecutable('python3', undefined, exec.signal)
      const handle = subprocess.spawn({
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
  }))

  return disposers
}

const DISCIPLINE_SECTION = `SolidForge discipline — added by the @maskshell/solidforge plugin (this session runs on a non-solidforge preset, or the preset plus this additive frame).

The SolidForge convergence discipline (the reference implementation of the paper "Specification Gaming as an Orthogonal Failure Axis in Autonomous Coding Loops"):
- Axis A — flow-control completeness: convergence loops run deterministic gates (fast gate, architecture-contract gate) and adversarial review until the gates go green. Green gates mean process_converged, nothing more.
- Axis B — verification-source decoupling: the oracle that judges the OUTPUT must not share your blind spots. Same-source self-endorsement is not a correctness claim. Run records carry a \`rightness\` field you cannot write — it is a schema constant (human_confirm_required); correctness is confirmed by a human out of band, never auto-satisfied by process success.
- Honesty rules: a gate that degrades is reported as degraded, never silently green; a heterogeneous oracle that did not run is reported as out-of-scope, never silently satisfied.

Skills — invoke by colon gesture (/solidforge:<name>), flat name (/<name>), or prompt name/abbreviation:
- pd = parallel-development — implementation convergence (dual-ring loop)
- bc = blueprint-crafting — specify-side artifacts (PRD/arch/iteration plan)
- csr = cross-source-review — adversarial document convergence (process axis)
- psv = primary-source-verification — per-claim fetched-source verification (outcome axis)
- pas = prior-art-search — novelty collision detection (outcome axis)
Chains in one line: "psv → csr → psv → bc → pd" (psv gate → csr converge → psv full-M → bc blueprint → pd implement).
Role agents: the preset's agents/*.agent.md prompts, spawned via the subagent tool (the full corpus ships with the solidforge preset). Deterministic gates are callable directly from the skills' infra/ directories; when the plugin's gates switch is enabled they also fire structurally as tool-event listeners. Project loop state: .solidforge/loop/ ($SOLIDFORGE_PROJECT_DIR overrides).`

export function apply(ctx, config = {}) {
  const root = presetRoot()
  const disposers = []
  const logger = ctx.logger
  const warn = (message) => {
    if (logger !== undefined && typeof logger.warn === 'function') logger.warn(`solidforge: ${message}`)
  }
  const persona = config.persona === true
  const gates = config.gates === true
  const commands = config.commands !== false
  const gestures = config.gestures !== false
  const skillsEnabled = config.skills !== false
  const status = {
    package: '@maskshell/solidforge',
    config: { persona, gates },
    presetRoot: root,
    presetHashNow: presetHash(root),
    presetStamp: presetStamp(root) ?? null,
    presetDrifted: undefined,
    skillsRegistered: 0,
    systemPromptSeen: false,
    sectionRegistered: false,
    commandsRegistered: 0,
    gatesRegistered: false,
    errors: [],
  }
  const fail = (phase, error) => {
    const message = error instanceof Error ? error.message : String(error)
    status.errors.push({ phase, message })
    warn(`${phase} failed: ${message}`)
  }
  status.presetDrifted = status.presetStamp === null
    ? 'no-stamp'
    : status.presetStamp.hash !== status.presetHashNow

  // Additive discipline section (order 50: after the deployment persona, before
  // tool guidance). It never replaces the preset's own persona.
  if (persona) {
    try {
      const systemPrompt = ctx.get('systemPrompt')
      status.systemPromptSeen = systemPrompt !== undefined
      if (systemPrompt === undefined) {
        warn('persona:true requested but the systemPrompt service is unavailable — section NOT registered')
      } else {
        disposers.push(systemPrompt.section({
          name: 'solidforge:discipline',
          order: 50,
          text: DISCIPLINE_SECTION,
        }))
        status.sectionRegistered = true
      }
    } catch (error) {
      fail('persona', error)
    }
  }

  const skills = ctx.get('skills')
  if (skills !== undefined && skillsEnabled) {
    try {
    for (const full of Object.keys(SKILLS)) {
      const dir = join(root, 'skills', full)
      const file = join(dir, 'SKILL.md')
      if (!existsSync(file)) {
        warn(`skill ${full} unavailable: ${file} missing (solidforge preset not installed?)`)
        continue
      }
      const parsed = parseSkillFile(readFileSync(file, 'utf8'))
      if (parsed === undefined) {
        warn(`skill ${full} unavailable: SKILL.md frontmatter did not parse`)
        continue
      }
      const dispose = skills.register({
        name: parsed.name,
        description: parsed.description,
        content: parsed.content,
        resourceBase: { kind: 'directory', path: dir },
      })
      disposers.push(dispose)
      status.skillsRegistered += 1
    }

    // Colon-gesture boundary: root ctx is unscoped, so this listener sees
    // every agent's pre-step batch (same delivery rule as dsh-tool-skill).
    const offGesture = gestures ? ctx.on('agent/pre-step', async ({ messages, signal }, next) => {
      const decision = await next()
      if (decision.kind === 'reject') return decision
      const tokens = colonTokens(messages)
      if (tokens.length === 0) return decision
      signal?.throwIfAborted()
      const injections = []
      for (const token of tokens) {
        const full = SKILLS[token] !== undefined ? token : ABBREVIATIONS[token]
        if (full === undefined) {
          warn(`unknown /solidforge:${token} token — skipped (not injected)`)
          continue
        }
        const dir = join(root, 'skills', full)
        const file = join(dir, 'SKILL.md')
        if (!existsSync(file)) continue
        const parsed = parseSkillFile(readFileSync(file, 'utf8'))
        if (parsed === undefined) continue
        injections.push({
          id: randomUUID(),
          role: 'user',
          content: [{
            type: 'text',
            text: renderSkillContent({ name: full, content: parsed.content, resourceBase: { kind: 'directory', path: dir } }),
          }],
          source: { kind: 'skill-invocation', name: full, form: 'instructions' },
        })
      }
      if (injections.length === 0) return decision
      return { kind: 'enter', messages: [...decision.messages, ...injections] }
    }) : undefined
    if (offGesture !== undefined) disposers.push(offGesture)
    } catch (error) {
      fail('skills+gesture', error)
    }
  }

  const commandsService = ctx.get('commands')
  if (commands !== undefined && commandsService !== undefined) {
    try {
    disposers.push(commandsService.register({
      name: 'solidforge-status',
      description: 'Report the @maskshell/solidforge runtime state (services seen, config, registrations, errors)',
      handler() {
        return { kind: 'success', text: JSON.stringify(status, null, 2) }
      },
    }))
    status.commandsRegistered += 1

    disposers.push(commandsService.register({
      name: 'solidforge',
      description: 'SolidForge skill reference map + discipline one-liner',
      handler(invocation) {
        invocation.agent.steer(steerMessage(SKILL_MAP, 'solidforge skill map'))
        return { kind: 'success', text: 'SolidForge skill map steered to the agent.' }
      },
    }))
    status.commandsRegistered += 1

    disposers.push(commandsService.register({
      name: 'arm-tools',
      description: 'Arm the current project for the SolidForge convergence loop (Layer 2 provisioning)',
      handler(invocation) {
        const file = join(root, 'commands', 'arm-tools.md')
        let procedure = ''
        try {
          procedure = readFileSync(file, 'utf8')
        } catch {
          procedure = ''
        }
        if (procedure.trim() === '') {
          return {
            kind: 'error',
            text: 'arm-tools procedure file unavailable — run: python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <project-dir>',
          }
        }
        invocation.agent.steer(steerMessage(
          'Follow this procedure exactly:\n\n' + procedure,
          'arm-tools procedure',
        ))
        return { kind: 'success', text: 'Arming procedure steered to the agent.' }
      },
    }))
    status.commandsRegistered += 1

  } catch (error) {
      fail('commands', error)
    }
  }

  // Structural gates (opt-in: gates:true covers every session of the profile).
  if (gates) {
    try {
      for (const dispose of registerGates(ctx, root, warn)) disposers.push(dispose)
      status.gatesRegistered = true
    } catch (error) {
      fail('gates', error)
    }
  }

  // Service-visibility probe: what does THIS context see? Written to disk so
  // the plugin's apply environment is observable from outside the process.
  try {
    const probe = {
      systemPrompt: ctx.get('systemPrompt') !== undefined,
      skills: ctx.get('skills') !== undefined,
      commands: ctx.get('commands') !== undefined,
      tools: ctx.get('tools') !== undefined,
      subprocess: ctx.get('subprocess') !== undefined,
      agents: ctx.get('agents') !== undefined,
    }
    probe.injectedSkills = ctx.skills !== undefined
    status.servicesSeen = probe
    const home = process.env.DSH_HOME ?? join(process.env.HOME ?? '', '.dsh')
    writeFileSync(join(home, '.solidforge-status.json'), JSON.stringify(status, null, 2) + '\n', 'utf8')
  } catch (error) {
    fail('status-file', error)
  }

  ctx.effect(() => () => {
    for (const dispose of disposers) dispose()
  })
}
