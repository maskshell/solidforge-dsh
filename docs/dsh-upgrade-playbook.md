# DSH upgrade playbook — keeping this port compatible

This port rides DSH's composition and client contracts. DSH ships release
candidates with real contract changes, and **every upgrade so far has broken
something silently**: the session keeps running, and the failure only shows up
as a degraded heterogeneous leg, a missing menu row, a command that quietly
stops existing, or a new session that cannot be created.

This playbook is the checklist that turns those silent failures into loud ones.
It is derived from breaks that actually happened to this port, not from
speculation — each check cites the incident that motivated it.

## The four surfaces that break

| Surface | Failure shape | Fast signal |
|---|---|---|
| **Preset rows** (loader entries + `Config`) | the whole preset refuses to mount → **no new session can be created** while open sessions keep working | `scripts/check-preset-schema.py` |
| **Client bundle contract** | the bundle ships but `apply()` runs too early → a menu group silently never appears | package probe + `/` menu check |
| **Command registration** | `ctx.get('commands')` returns undefined → `/solidforge*` commands stop existing, and the text is delivered to the model instead | `/solidforge-status` execution |
| **Model catalog** | a pinned model id disappears from the installed catalog → that heterogeneous leg fails at request time (pi-ai resolves strictly) | `scripts/check-profile-catalog.py` |

## 0. Before upgrading

- Record `dsh --version` in the upgrade note (the port supports a moving target).
- Know that **the host half is module-cached**: a new install does NOT take effect
  in a running `dsh web` process. A restart is part of the upgrade, not an
  afterthought.

## 1. Deterministic gates (offline, seconds)

```bash
python3 scripts/check-preset-schema.py      # every preset row vs installed Config d.ts
python3 scripts/check-profile-catalog.py    # every profile model vs installed pi-ai catalog
bash scripts/ci-suites.sh                   # full suite (release metadata, lint, smoke, wiring)
```

All three fail loudly with the offending row/model named. When a DSH package is
not installed at all they print `SKIP` — that is an honest "not verified", never
a green.

**Both gates have been negative-tested**: restoring a removed package name or a
stale model id makes each exit non-zero. If a future edit makes them pass while
the failure is present, fix the gate first.

## 2. Package references (preset ↔ installed packages)

`check-preset-schema.py` covers this, but when it reports `unresolved`, the
shape of the break is almost always a **renamed or removed `@deepseek-ai/*`
package**. Compare what the preset names against what is installed:

```bash
# names the preset asks for, vs packages actually present
grep -o "name: '[^']*'" preset/agent.cordis.yml | sort -u
ls "$(dirname "$(command -v dsh)")/../node_modules/@deepseek-ai" 2>/dev/null || \
  ls ~/.npm/_npx/*/node_modules/@deepseek-ai | head -50
```

A stale reference fails the **whole** preset mount, which is why this is the
first check: it produces "new session does nothing".

## 3. Restart, then runtime checks

Restart `dsh web` (Ctrl-C, re-run, reopen the printed URL) and hard-refresh the
page (`Cmd+Shift+R`) — the client bundle is served from the server's composed
graph, so a stale page keeps the old modules.

Then check, in order:

1. **New session** — create one. Failure here means a preset row did not mount;
   the error text in the browser console/banner names the entry and the bad config.
2. **`/solidforge-status`** — must **execute** (return state), not reach the model.
   If it reaches the model, command registration is broken (see §4).
3. **`/` menu** — the solidforge group (10 candidates) must appear, and the skills
   group must list the five skills. An empty group with a healthy catalog means a
   **page snapshot taken before registration settled**: hard-refresh again.
4. **`~/.dsh/.solidforge-status.json`** — `skillsRegistered` should be 5 and
   `errors` empty. Note that the probe is written by **both** the patch-layer and
   preset instances (whichever writes last wins), so treat `servicesSeen` as
   instance-specific rather than global.

## 4. Command registration (the 0.2.0 trap)

0.2.0 made `CommandRuntime` a `TypertRemoteService` reachable only from *"a
command-injected child of an agent context"*. `ctx.get('commands')` outside such
a child returns `undefined`, and a plugin that guards on it **silently registers
nothing** — no error, empty `errors`.

The port registers through `ctx.inject(['commands'], (commandCtx) => …)`, the same
shape 0.2.0's own `dsh-plan-mode` / `dsh-permission-presets` use. If commands go
missing after an upgrade, first check whether the new `CommandRuntime` still
exposes `.commands` on the injected child, and update the callback accordingly.

## 5. Client bundle contract

The bundle must export the Cordis **service** list as `inject` (for example
`['inputTriggers']`), separately from `package.json`'s `dsh.client.inject`
(which lists *package* bundle dependencies). Missing the exported `inject` means
the module system runs `apply()` before the service exists; a guard like
`if (svc === undefined) return` then skips registration with no trace.

Diagnose with the boot graph in the browser console:

```js
window.__DSH_BOOT__.batches.map(b => b.url).find(u => u.includes('solidforge'))
```

A changed `rev` proves the server recomposed after an edit; an absent entry means
the service-side composition dropped the package.

## 6. Model catalog

pi-ai resolves models **strictly** ("rejects unserviceable models before settings
writes"), and a provider route ships only its own model ids. Re-pin after an
upgrade:

```bash
python3 scripts/check-profile-catalog.py
# source of truth: @earendil-works/pi-ai/dist/providers/data/<route>.json
```

The route's JSON is the same generated catalog the adapter consumes, so it cannot
drift from what the runtime resolves.

## 7. End-to-end: run one real heterogeneous review

The gates cannot see every contract. Finish an upgrade with one real run:

```bash
python3 preset/skills/parallel-development/infra/scripts/hetero_review.py \
  --embedded --diff <a meaningful diff> --blueprint AGENTS.md \
  --profile zai-coding-cn,minimax-cn
```

Success = both legs contribute findings (or degrade with a **reported** subtype),
never a silent same-source fallback. This is also the only way to exercise
`_prepare_dsh_home`, and 0.2.0 is exactly why this section exists: its
`settings.yaml` approach **stopped applying silently** — the file is imported
(renamed to `.imported`) but `agent-default-model` is not adopted, so the
subprocess kept the base default `deepseek-official` and died on its missing key,
appearing only as `dsh-subprocess-error` on both legs. The fix writes the profile
patch layer (`profiles/<profile>/cordis.patch.yml`) with id-targeted
`agent-default-model` and `llm-pi-ai` overrides. Any future deprecation of that
patch path will show up here first.

## The breaks we have actually seen

| Version | Break | Symptom | Fix |
|---|---|---|---|
| 0.1.5-rc.2 | `dsh-persona` config `text` → required `prefix` | preset refused to mount → new sessions failed, open sessions fine | preset row `config.prefix` |
| 0.1.5-rc.2 | client bundle must export `inject` (service list) | `/solidforge:` source never registered; bundle still shipped | export `inject = ['inputTriggers']` |
| 0.2.0-rc.2 | `dsh-workflow-worker-thread` removed → `dsh-workflow-ptc` | preset mount failed (whole preset) | mount `dsh-workflow-ptc` (same `provider` field) |
| 0.2.0-rc.2 | `CommandRuntime` → `TypertRemoteService` | commands silently unregistered | register via `ctx.inject(['commands'], …)` |
| 0.2.0-rc.2 | `settings.yaml` deprecated (per-profile settings) | `_prepare_dsh_home`'s `settings.yaml` **silently stopped applying**: the temp-home file is renamed to `.imported` but `agent-default-model` is not adopted, so the subprocess still resolved the base default `deepseek-official` and failed on its missing key — surfacing only as `dsh-subprocess-error` on every heterogeneous leg | write the profile **patch layer** (`profiles/<profile>/cordis.patch.yml`, id-targeted `agent-default-model` + `llm-pi-ai` config overrides) instead of `settings.yaml` |
