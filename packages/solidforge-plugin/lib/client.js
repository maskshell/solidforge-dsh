// lib/client.js — the PERSISTENT client half of @maskshell/solidforge (B).
// Registers a '/'-trigger input-trigger source listing the
// /solidforge:<name> colon candidates so the GUI menu offers completion for
// the gesture. The injection itself stays host-side (the patch-layer
// agent/pre-step listener); onPick only inserts the literal token. No
// matchEnter: the line flows as a user message and the host boundary
// expands it. Self-contained __ModuleLoader__ artifact (no imports) —
// the dsh client-module system serves this file as a bundle route for every
// page that mounts the package.
window.__ModuleLoader__.load({
  id: '@maskshell/solidforge',
  factory: (require) => {
    var module = { exports: {} }
    var exports = module.exports

    const SKILLS = [
      ['parallel-development', 'pd', 'implementation convergence (dual-ring loop)'],
      ['blueprint-crafting', 'bc', 'specify-side artifacts (PRD/arch/iteration plan)'],
      ['cross-source-review', 'csr', 'adversarial document convergence (process axis)'],
      ['primary-source-verification', 'psv', 'per-claim fetched-source verification (outcome axis)'],
      ['prior-art-search', 'pas', 'novelty collision detection (outcome axis)'],
    ]

    function apply(ctx) {
      const inputTriggers = ctx.get('inputTriggers')
      if (inputTriggers === undefined) return
      const source = {
        trigger: '/',
        name: 'solidforge',
        async candidates(_session, { query, signal }) {
          if (signal !== undefined && signal.aborted) return []
          const list = []
          for (const [full, abbr, description] of SKILLS) {
            list.push({ name: 'solidforge:' + full, description: full + ' (' + abbr + ') — ' + description })
            list.push({ name: 'solidforge:' + abbr, description: abbr + ' = ' + full })
          }
          return list.filter((entry) => entry.name.startsWith(query ?? ''))
        },
        onPick({ candidate }) {
          return { text: '/' + candidate.name + ' ' }
        },
        warm() {},
      }
      return ctx.effect(() => inputTriggers.registerSource(source), 'solidforge: colon source')
    }

    exports.apply = apply
    return module.exports
  },
})
