// smoke.mjs — deterministic wiring test for @maskshell/solidforge's host half.
// Self-contained: builds a fixture preset (five minimal SKILL.md files) under
// a temp DSH_HOME, then exercises apply(ctx) with a mock context: skill
// registration, colon-gesture injection, command registration, and the
// honest-degrade paths. No network, no subprocess.
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const mod = await import(join(here, '..', 'lib', 'index.js'))

const SKILLS = {
  'parallel-development': 'parallel-development (pd) orchestrator: runs multiple AI agents in parallel on independent dev tasks.',
  'blueprint-crafting': 'blueprint-crafting (bc): Produces convergence-checked upstream artifacts — product spec (PRD), architecture design (arch-design), iteration plan, executable summary, and research.',
  'cross-source-review': 'cross-source-review (csr) — a same-family (同源, fresh-context) + different-family (异源) cross multi-round review engine that drives a doc-shaped artifact to SUBSTANTIVE convergence.',
  'primary-source-verification': 'primary-source-verification (psv) — a read-only, source-grounded, per-claim verifier that FETCHES each cited primary source and adjudicates a doc factual/citation claims.',
  'prior-art-search': 'prior-art-search (pas) — a read-only, search-grounded, per-novelty-claim collision detector that SEARCHES the prior-art corpus for a doc novelty claims.',
}

function buildFixture() {
  const home = mkdtempSync(join(tmpdir(), 'solidforge-home-'))
  for (const [name, description] of Object.entries(SKILLS)) {
    const dir = join(home, '.agent-presets', 'solidforge', 'skills', name)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'SKILL.md'), `---\nname: ${name}\ndescription: |\n  ${description}\n---\n\n# Body of ${name}\n\nSkill body line one.\nSkill body line two.\n`)
  }
  return home
}

function mockCtx() {
  const ctx = {
    registrations: [],
    commands: [],
    listeners: new Map(),
    effects: [],
    logger: { warn() {} },
    get(name) {
      if (name === 'skills') return { register: (reg) => { ctx.registrations.push(reg); return () => {} } }
      if (name === 'commands') return { register: (def) => { ctx.commands.push(def); return () => {} } }
      return undefined
    },
    on(name, listener) {
      const list = ctx.listeners.get(name) ?? []
      list.push(listener)
      ctx.listeners.set(name, list)
      return () => {}
    },
    effect(fn) {
      ctx.effects.push(fn)
      return () => {}
    },
  }
  return ctx
}

function preStep(ctx) {
  const list = ctx.listeners.get('agent/pre-step')
  assert.ok(list, 'agent/pre-step listener registered')
  assert.equal(list.length, 1, 'exactly one agent/pre-step listener')
  return list[0]
}

function userMessage(text) {
  return { id: 'u1', role: 'user', content: [{ type: 'text', text }], source: { kind: 'user' } }
}

// ── happy path (fixture preset present) ─────────────────────────────────────
{
  const home = buildFixture()
  const previous = process.env.DSH_HOME
  process.env.DSH_HOME = home
  try {
    const ctx = mockCtx()
    mod.apply(ctx)

    assert.equal(ctx.registrations.length, 5, 'five skills registered')
    for (const name of Object.keys(SKILLS)) {
      const reg = ctx.registrations.find((r) => r.name === name)
      assert.ok(reg, `skill ${name} registered`)
      assert.ok(reg.description.length > 20, `${name} description present`)
      assert.ok(reg.content.includes('\n'), `${name} content present`)
      assert.equal(reg.resourceBase.kind, 'directory')
    }

    assert.equal(ctx.commands.length, 2, 'two commands registered')
    assert.deepEqual(ctx.commands.map((c) => c.name).sort(), ['arm-tools', 'solidforge'])

    // colon gesture, full name
    const listener = preStep(ctx)
    const decision1 = await listener({ messages: [userMessage('/solidforge:psv verify the doc')], signal: undefined },
      async () => ({ kind: 'enter', messages: [userMessage('/solidforge:psv verify the doc')] }))
    assert.equal(decision1.kind, 'enter')
    assert.equal(decision1.messages.length, 2)
    assert.ok(decision1.messages[1].content[0].text.includes('<skill_content name="primary-source-verification">'))
    assert.equal(decision1.messages[1].source.kind, 'skill-invocation')

    // colon gesture, abbreviation
    const decision2 = await listener({ messages: [userMessage('run /solidforge:pd on this')], signal: undefined },
      async () => ({ kind: 'enter', messages: [userMessage('run /solidforge:pd on this')] }))
    assert.ok(decision2.messages[1].content[0].text.includes('<skill_content name="parallel-development">'))

    // unknown token: skipped, decision unchanged
    const decision3 = await listener({ messages: [userMessage('/solidforge:nope')], signal: undefined },
      async () => ({ kind: 'enter', messages: [userMessage('/solidforge:nope')] }))
    assert.equal(decision3.messages.length, 1, 'unknown token not injected')

    // non-user sources never forge a gesture
    const decision4 = await listener({
      messages: [{ id: 'a1', role: 'assistant', content: [{ type: 'text', text: '/solidforge:psv' }], source: { kind: 'model' } }],
      signal: undefined,
    }, async () => ({ kind: 'enter', messages: [] }))
    assert.equal(decision4.messages.length, 0, 'model message cannot forge a gesture')

    // reject passes through untouched
    const decision5 = await listener({ messages: [], signal: undefined }, async () => ({ kind: 'reject' }))
    assert.equal(decision5.kind, 'reject')
  } finally {
    process.env.DSH_HOME = previous
    rmSync(home, { recursive: true, force: true })
  }
}

// ── honest degrade: preset missing ──────────────────────────────────────────
{
  const empty = mkdtempSync(join(tmpdir(), 'solidforge-empty-'))
  const previous = process.env.DSH_HOME
  process.env.DSH_HOME = empty
  try {
    const ctx = mockCtx()
    mod.apply(ctx)
    assert.equal(ctx.registrations.length, 0, 'no skills registered without the preset')
    assert.equal(ctx.commands.length, 2, 'commands still registered')
    const armHandler = ctx.commands.find((c) => c.name === 'arm-tools').handler
    let steered = null
    const result = armHandler({ agent: { steer: (m) => { steered = m } } })
    assert.equal(result.kind, 'error', '/arm-tools fails loud without the preset')
    assert.equal(steered, null, 'nothing steered on failure')
  } finally {
    process.env.DSH_HOME = previous
    rmSync(empty, { recursive: true, force: true })
  }
}

console.log('solidforge-plugin smoke: PASS')
