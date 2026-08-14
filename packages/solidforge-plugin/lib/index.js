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
//
// Design constraints (verified against the deployment):
//   - The profile patch layer's root context is UNscoped, and scoped agent
//     events pass their filter for unscoped contexts, so a root-level
//     `agent/pre-step` listener receives every agent's steps.
//   - The preset is the single source of the skill bodies; this plugin reads
//     them live (no copy, no drift) and degrades honestly when the preset is
//     not installed (skills unregistered, gestures skipped, /arm-tools fails
//     loud — never silently green).
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'

export const name = 'solidforge'

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

export function apply(ctx) {
  const root = presetRoot()
  const disposers = []
  const logger = ctx.logger
  const warn = (message) => {
    if (logger !== undefined && typeof logger.warn === 'function') logger.warn(`solidforge: ${message}`)
  }

  const skills = ctx.get('skills')
  if (skills !== undefined) {
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
    }

    // Colon-gesture boundary: root ctx is unscoped, so this listener sees
    // every agent's pre-step batch (same delivery rule as dsh-tool-skill).
    const offGesture = ctx.on('agent/pre-step', async ({ messages, signal }, next) => {
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
    })
    disposers.push(offGesture)
  }

  const commands = ctx.get('commands')
  if (commands !== undefined) {
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
  }

  ctx.effect(() => () => {
    for (const dispose of disposers) dispose()
  })
}
