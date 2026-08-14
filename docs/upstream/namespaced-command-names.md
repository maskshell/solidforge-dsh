# RFC: plugin-namespaced slash commands (`/plugin:command`) in DSH

> Status: **proposed to upstream via GitHub Discussions** (2026-08-14). The
> upstream repository (`deepseek-ai/deepseek-harness`) currently states it
> cannot accept external pull requests (`CONTRIBUTING.md`); feature requests go
> through Discussions. The ready-to-apply patch is
> [`namespaced-command-names.patch`](namespaced-command-names.patch) in this
> directory.

## Problem

DSH slash-command names are one flat namespace:

- registration: `COMMAND_NAME = /^[a-z][a-z0-9_-]*$/u`
- parsing: `parseCommand()` inline `/^\/([a-z][a-z0-9_-]*)(?=$|[\t\n\r ])/u`

Both live in `packages/interaction/commands/src/index.ts`. Consequences for
plugin-style capability bundles (Claude Code plugins ported to DSH):

1. **No structural ownership.** Two plugins shipping a `deploy` command
   collide; layer order / scoped shadowing decides the winner, and neither
   author can prevent the collision by design.
2. **No ecosystem parity.** Claude Code addresses plugin commands as
   `/{plugin-id}:{command}` (the colon is the structural separator; each
   plugin skill also gets a generated `/plugin:skill` command). Ports must
   flatten or kebab-mangle names, losing both the convention and the guard.
3. **Kebab prefixes are not a substitute.** `/solidforge-arm-tools` cannot be
   mechanically split (is it `solidforge` + `arm-tools`, or
   `solidforge-arm` + `tools`?), and it stays convention-only — nothing stops
   a second plugin from registering the same name.

## Proposal

Allow **one optional namespace segment** in both regexes (kept in lockstep):

```text
[a-z][a-z0-9_-]*(?::[a-z][a-z0-9_-]*)?
```

- `/goal` — unchanged (namespace optional)
- `/solidforge:psv` — valid
- `/solidforge:`, `/:psv`, `/solidforge::psv`, `/a:b:c` — rejected (empty
  segment, bare segments, at most one colon)

The client slash pipeline tokenizes on whitespace and resolves menu entries
by exact name, so no client change is required; fuzzy menu discovery treats
`:` as an ordinary character (verified against `packages/client/ui-commands`
source).

## Evidence

- Patch: `docs/upstream/namespaced-command-names.patch` (against upstream
  `47f94385`, branch `feat/namespaced-command-names`).
- Tests: `packages/interaction/commands` — **58/58 pass** (vitest 4.1.8,
  pnpm 11.7.0), including the new positive/negative parse cases and the new
  registration-rejection cases.
- Upstream contact: posted to the repo's GitHub Discussions (Ideas) on
  2026-08-14:
  [deepseek-ai/deepseek-harness#1101](https://github.com/deepseek-ai/deepseek-harness/discussions/1101).

## Follow-up (separate RFC, not in this patch)

**Ownership enforcement**: a registry-level prefix→owner claim — the first
package registering a `namespace:` name claims the prefix; a different
package registering the same prefix fails loudly. This turns the prefix from
a convention into a collision guarantee. Open design points: claim
attribution (the `commands.register` service cannot see its caller), prefix
granularity, migration for existing flat names.

## Explicitly out of scope

- **Skill names stay kebab-only** (`/^[a-z0-9]+(?:-[a-z0-9]+)*$/`). The
  `/{plugin}:{skill}` UX is provided by the command layer, mirroring Claude
  Code (one generated slash command per plugin skill). Skill-name
  namespacing touches provider + catalog + `/name`-injection layers and is a
  separate, larger change.
- **Subagent names** — DSH subagents are prompt-instantiated (the `subagent`
  tool), with no per-plugin name registry to namespace.

## Ecosystem fallback (works today, no upstream change)

If upstream never adopts the grammar, a plugin can still honor
`/solidforge:*` lines itself: the client input-trigger pipeline adjudicates
`matchEnter` across registered sources in order, and the command source
returns undefined for lines it cannot parse (`:` names), so a plugin-owned
source registered later in the roster claims the line first non-undefined
wins. The SolidForge port may ship such a source in its own package
(`dsh-plugin` topic) as the colon-syntax path, with the grammar RFC as the
upstream-ward companion.
