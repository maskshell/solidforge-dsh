# Verification Record

Evidence collected during the porting session (all reproducible from the repo).

## Preset mount validation

`agentPresets.standingKeyFor('solidforge')` → **ok** (twice: initial composition, and the final
composition after the tool-cordis row was removed). The tool-cordis removal was itself driven
by mount validation: the row registers process-global Host inspect providers and collided with
the `cordis` preset already mounted in this process — the same collision any multi-preset
process would hit.

## Live structural-gate verification (this session, plugins running)

| Gate | Trigger | Observed |
| --- | --- | --- |
| `fast_gate.py` (tools/post-execute) | `write` of a Python file with an unused import | Block reason returned to the model: "Fast-gate failed (ruff check) on test/gate-probe.py: ... F401 ... Breaker=OK: fix in the inner ring..." |
| `fast_gate.py` (format) | `write` of `plugin_layout.py` with a formatting drift | Block reason with commit-stratification guidance; fixed in-ring by running `ruff format`, then the check passed. |
| `blueprint_guard.py` (tools/pre-execute) | `edit` of a `status: frozen` blueprint | Call denied BEFORE dispatch with the revision-channel reason; file md5 unchanged (`82cf3a55...` before and after). |

## Deterministic infra suites (workspace `preset/`, all rc=0 unless noted)

- parallel-development: `plugin_layout` PASS · `disconnect_check` PASS · `run_record` PASS (6/6
  scenarios, rightness constant present) · `run_record_schema` PASS · `violation_log_schema`
  PASS · `adapter_shape_check` PASS · `arm_copy_config` PASS · `arm_report_gates` PASS (37/37) ·
  `arm_revert` PASS (31/31) · `hetero_review_wiring` PASS · `plan_queue_detect` PASS ·
  `plan_queue_loop_state_wiring` PASS · `scope_check` PASS (43/43) · `smoke_gates` PASS ·
  `drift_check` rc=0.
- blueprint-crafting: `produce_goldens` PASS · `constraints_check_goldens` PASS ·
  `plan_model_schema` PASS · `run_record_schema` PASS (rightness enum-of-one asserted) ·
  `run_record` PASS ("Field isolation holds: rightness is the constant
  'human_confirm_required' in every record") · `freeze_goldens`, `normalizer_goldens`,
  `end_to_end`, `round_trip`, `plan_reviewer_precision`, `trigger_check` PASS.
- cross-source-review / primary-source-verification / prior-art-search: every suite rc=0.
  Inherited upstream quirk (reproduced on the unported tree): csr's
  `converge_fixtures/verify.py` malformed-finding case expects the jsonschema-path message;
  `pip install jsonschema` restores the intended path.

## Installation

`bash scripts/install.sh` → `~/.dsh/.agent-presets/solidforge/` (263 files on a clean
install, counted as `find <installed> -type f` excluding `.DS_Store` and `*.pyc`;
plugin sources baked with the absolute preset root). The installed tree's own layout +
run-record suites pass (run above).

## Dogfood: psv → csr convergence run on README.md (2026-08-14)

The port ran its own discipline on its own README — trail + records in `docs/dogfood/`:
`README-dogfood.md` (narrative), `README-csr.run.json` + `README-csr.convergence-record.json`
(schema-validated with jsonschema 4.26 from the upstream venv), `README-psv.verdicts.json` +
`README-psv.coverage-record.json`. Outcome: 2 same-source rounds pass (0 blockers, 11
findings reconciled — 9 fixed / 2 recorded disclosures); different-family leg (claude, native
auth) ran after one cold-start timeout retry and produced 1 false-positive blocker (its own
evidence enumerates 22 agent files while asserting 21; independent count = 22) + 1 warning
(fixed). Engine: `substantive_converged: false`, `stalemate: true`, `rightness:
human_confirm_required` — escalated to the human for adjudication, never silent-picked.
psv full-M: 60 verified / 0 refuted / 1 narrowed (fixed post-run) / 3 unverifiable of 64;
`oracle_verified_under_known_coverage`.

## Substrate redesign (post-dogfood, human review)

The hetero wrappers' default substrate is now DSH-NATIVE: `substrate: dsh` spawns a
fresh stateless `dsh --profile headless` subprocess with a throwaway DSH_HOME pinning a
different provider/model route (unarmed = fail-fast arming prompt; no placeholder
profile ships — the pi-ai.json placeholder of the intermediate state was removed in the
naming consolidation, see below). The upstream `claude -p` mechanism is a labeled
external-harness opt-in (`substrate: claude-code`) only — heterogeneity is a different
LLM, not a different harness. Verified: both wrappers fail fast with the arming message
and no subprocess spawn when the route is unarmed; wiring suites pass including the new
DSH-home construction + fail-fast-cleanup branch.

## Heterogeneous arming + live dual-hetero run (2026-08-14)

User-provided keys armed two DSH-native heterogeneous profiles — then named
`profiles/zhipu.json` and `profiles/minimax.json` (hand-declared pi-ai routes, later
replaced by the catalog routes `zai-coding-cn` / `minimax-cn` with route-derived
credential vars `ZAI_CODING_CN_API_KEY` / `MINIMAX_CN_API_KEY`; `HETERO_PROFILE`
now names those routes). The historical names below document the evolution —
current profiles/ dir ships claude.json, minimax-cn.json, qwen-token-plan-cn.json,
qwen.json, zai-coding-cn.json. End-to-end smoke: both providers rc=0 via fresh
`dsh --profile headless` subprocesses — zero foreign harness. Live dual-hetero
review of README.md: 14 findings, 1 real blocker + 7 warnings fixed, 4 rejected
as a second oracle-false-positive class (stale-finding misreads), trail in
`docs/dogfood/README-csr-hetero-round4.json` + `README-dogfood.md` round 4.

## Skill slash-surface verification + frontmatter fix (2026-08-14)

Verified against the shipped `dsh-client-ui-skill` / `dsh-tool-skill` packages and
live in the running GUI (playwright): DSH skills ARE slash-surfaced — the `/`
input-trigger source lists `skill.list` candidates, and a `/name` token anywhere
in the user message is deterministically expanded at the host pre-step boundary.
This corrected an earlier wrong claim that skills were model-side only.

Live GUI check then exposed a REAL catalog bug: only 3 of the 5 preset skills
appeared in the `/` menu. Root cause, reproduced with the deployment's own
`yaml` parser: `primary-source-verification` and `prior-art-search` carried
inline single-line `description:` values containing ": " (e.g. "GATE MODE
(2026-08): …", "Phase A: EXPLICIT …"), which the strict parser rejects
("nested mappings are not allowed in compact mappings") and the skill
provider SILENTLY drops. Fix: all three single-line descriptions (incl.
cross-source-review, the latent hazard) converted to `|` block scalars; the
deployment parser now parses 5/5. Regression guard:
`scripts/check-skill-frontmatter.py` (CI suite 53) enforces name==dirname and
block-scalar descriptions.

## Global plugin face (`@maskshell/solidforge`, 2026-08-14)

DSH-native answer to Claude Code's plugin model: a profile-patch-layer package
instead of preset switching. Mechanics verified from the deployment's sources
before building: the profile's `cordis.patch.yml` is the user patch layer
(hot-reloaded, HMR); `insert` entries mount root-level rows; root contexts are
unscoped, and scoped `agent/pre-step` events pass their filter for unscoped
contexts, so a root listener sees every agent's step; the Loader resolves row
names from the profile directory's `node_modules`. The plugin registers the
five skills into the HOST layer (any session's catalog), listens for
whitespace-bounded `/solidforge:<name>` tokens (full names or abbreviations,
same word-boundary shape as `dsh-tool-skill`'s gesture) and injects
byte-compatible `<skill_content>` at the pre-step boundary, and registers
`/solidforge` + `/arm-tools` (replacing the retired `commands.host.js`
dynamic plugin — dynamic plugins die with the process; the package persists).

Live verification (playwright, real GUI, PTC-preset session): `/solidforge`
executed (command row + steered map + model step consuming it);
`/solidforge:psv say hi` submitted as a plain user message → the pre-step
listener injected `primary-source-verification` (transcript injection row)
and the model answered in the skill's discipline ("coverage disclosure, not a
correctness verdict"). This session's own model catalog gained all five
skills after HMR — host-layer registration observable from a non-solidforge
session. One install-script bug found and fixed along the way: the patch
entry was first written as `[- insert:` (invalid YAML), silently failing
`parsePatchList`; the writer now replaces the `[]` token itself.

Tests: `packages/solidforge-plugin/tests/smoke.mjs` (self-contained fixture;
CI suite 54). Uninstall: `scripts/install-global.sh --revert`.

## Loader contract findings (2026-08-14, follow-up to the global plugin face)

Two loader contracts discovered the hard way, both now encoded in the design:

1. **`inject` is the service bridge.** A patch-layer `insert` entry whose
   plugin declares no `inject` runs in a context that sees NONE of the app's
   services (probe: systemPrompt/skills/commands/tools/subprocess/agents all
   undefined). Declaring `inject: ['skills', 'systemPrompt']` makes exactly
   those services (plus the parent chain: agents, systemPrompt) visible and
   registration works (skillsRegistered=5, sectionRegistered=true, zero
   errors — verified via the package's `.solidforge-status.json` probe on a
   fresh `dsh --profile web` boot).
2. **The patch-layer context cannot see `commands`/`tools`/`subprocess` at
   all** (they live in preset scopes). Commands therefore moved to a
   solidforge PRESET row of the same package (`config: {commands: true,
   gestures: false, skills: false}`), and the gates stay with the per-session
   dynamic plugins. The profile patch layer owns skills + gestures + the
   discipline section only.
3. **HMR reload wedges**: the running web process's patch-layer watcher stops
   reloading after a failed cycle (the duplicate-entry era); entry definition
   changes alone do not re-import the package module. Fresh boots always
   apply cleanly. A web-process restart is required after structural patch
   changes.

## npm distribution (2026-08-14)

Published `@maskshell/solidforge` to npm (versions 0.1.0, 0.1.1; the first
publish of the newly created `@maskshell` scope hit the registry's
new-scope packument lag — tarballs/version docs/dist-tags live while the
packument builds). Publish flow: `npm publish --otp` blocked (account has
publish-2FA), then a granular access token succeeded once the scope existed.
Future releases: npm trusted publishing (OIDC) via
`.github/workflows/publish.yml` (`workflow_dispatch` / `v*` tags, no tokens) —
configure once on the npm website for the package after first publish.
Upstream discussion updated: deepseek-ai/deepseek-harness#1101 (comment
18015751) carries the shipped-package summary plus the two loader-contract
findings as extension-surface feedback.

## npm license correction (2026-08-14)

The first publish declared `license: MIT` by mistake; the repo and the
upstream (maskshell/solidforge) are Apache-2.0. Fixed in 0.1.2:
`license: Apache-2.0` + LICENSE/NOTICE shipped inside the tarball (files
whitelist), README footer updated. 0.1.0/0.1.1 keep their historical MIT
metadata (npm does not allow editing published versions); the npm page
renders the latest version's license, now correct.

## Upstream-sync audit (2026-08-22)

Audited upstream maskshell/solidforge history since the port basis (08-13/14):

- 407c7be (08-13) format-failure commit stratification — ALREADY PORTED
  (fast_gate remediation guidance + smoke coverage).
- eeff1c5 (08-22, upstream ADR #53) deepseek review-leg default demotion —
  NOT APPLICABLE by construction: the port removed same-source deepseek
  legs entirely; lesson recorded as our ADR #53.
- cbfde40 (08-22, upstream ADR #54) rustfmt --edition hardcode false-positive
  generator — WE HAD THE BUG (fast_gate.py check_rust hardcoded --edition
  2021). Fix ported verbatim + the upstream test surface (6 resolution
  fixtures + edition-2024 let-chains e2e + 2021 control); local run green.
  Recorded as our ADR #52.

## Preset version stamp (2026-08-22)

install.sh now writes `.preset-stamp.json` (source_commit, installed_at,
content hash). scripts/preset-stamp.py `check` compares the installed preset
against BOTH its own stamp (post-install drift) and the CURRENT repo's would-be
install (preset/ + baked plugins) — so the "fixed in repo but stale deployed
preset" failure mode (the 0.1.2-vs-fix confusion) is detected deterministically.
install-global.sh warns on staleness (the plugin face reads the preset live);
the plugin's /solidforge-status + probe file report presetHashNow /
presetStamp / presetDrifted. Smoke covers stamp matching/mismatch/no-stamp.

## Stale-preset detection nuance (2026-08-22)

The plugin's /solidforge-status stamp fields (presetHashNow/presetStamp/
presetDrifted) require a web-process restart to appear: the loader caches the
loaded package MODULE per process (config hot-reload re-runs apply() with the
cached module — lib changes do not re-import). The CLI-level check
(install-global.sh -> preset-stamp.py check) is immediate and was verified
live: after the stamp commit, reinstall printed
"OK: preset in sync (commit cf6eba3d, installed 2026-08-22T16:32:52+0800)".
A same-process lib change therefore needs a restart — noted, not buried.

## DSH update compatibility audit (2026-08-23)

The deployment's dsh updated in place (0.1.0-rc.6 -> 0.1.1-rc.2; checkout
files refreshed 08-22 10:25, web process started 10:59 on the new version —
so every live E2E since then already ran against 0.1.1-rc.2). Re-audited
every seam the patch depends on against the CURRENT sources:

- dsh-commands: COMMAND_NAME /^[a-z][a-z0-9_-]*$/ unchanged (the colon-grammar
  RFC is still pending upstream — kebab names unaffected).
- dsh-system-prompt: PromptSection {name, order, text} unchanged.
- dsh-skill: SkillRegistration shape unchanged.
- dsh-tool-skill: SKILL_GESTURE + agent/pre-step injection boundary unchanged.
- dsh-agent-loop: agent/pre-step waterfall payload unchanged.
- dsh-scope: unscoped-pass filter unchanged (root listeners still see all
  scoped events — the patch layer's gesture/persona design holds).
- dsh-tools: tools/pre-execute + tools/post-execute waterfall signatures
  unchanged (the dynamic gate plugins hold).

Clean-room verification: fresh `dsh --profile web` boot of the CURRENT
checkout with our patch layer -> probe shows skillsRegistered=5,
sectionRegistered=true, errors=[], servicesSeen identical. Verdict:
COMPATIBLE.

One operational finding (unrelated to the update): the three session-owned
dynamic plugins were gone from the process when the audit began — they are
per-session activations and do not survive session resumptions; re-activated
(sfgat-1 / sfrec-2 / sfhet-3). This is the documented per-session activation
model, not a regression.

## Gates moved to the preset row (2026-08-23)

The structural gates migrated from session-owned dynamic plugins to the
solidforge PRESET row (`config: {commands: true, gestures: false, skills:
false, gates: true}`) — the preset scope sees tools/subprocess, so the same
package registers the tool-event gates, run-record, and hetero-review tools
there. They survive session resumptions (the recurring dynamic-plugin
re-activation burden is gone for solidforge sessions). Verified on a fresh
boot of the current dsh: probe shows gatesRegistered=true, commandsRegistered
=3, skillsRegistered=0, errors=[] with all six services visible. The dynamic
plugins remain the LEGACY selective path — never both (double gates).

## Persistent client half (B) — /solidforge:* menu completion (2026-08-23)

The colon gesture lacked GUI completion (the menu only lists flat skill
names); the persistent client half closes it. Two seams found the hard way,
both now gated in check-release-metadata.py: (1) the package's exports map
did not expose ./package.json — clientModules' resolveMeta does
require.resolve('<pkg>/package.json') and got ERR_PACKAGE_PATH_NOT_EXPORTED,
silently skipping the module; (2) install-global.sh did not copy
lib/client.js. Fix: exports {'.', './client', './package.json'} + the copy
line + the gate assertions. Verified on a fresh web-profile boot (3099): the
served graph contains @maskshell/solidforge with the bundle route
/plugins/@maskshell/solidforge/client.js. The 3080 process picks it up on
its next restart (clientModules caches package metadata per process).

## Colon token UI-decoration root cause + upstream patch (2026-08-23)

User-observed: a sent /solidforge:psv message renders split ("/solidforge" +
":psv say hi"). Root cause from the shipped source: projectUserText's
plain-token scan /(^|\s)(\/[\w-]+|...)/gu — \w- excludes ":", so the chip
decorates only the leading part. The stored message and the host-side
injection are untouched (the injection firing proves the token stayed
intact) — cosmetic, but misleading. Fix prepared upstream (one-line regex +
unit test): docs/upstream/colon-token-decoration.patch; posted to #1101.

## Public-surface vetting lesson (2026-08-24, internal operational control)

The show-your-plugins post's first screenshot captured the real workspace
name (dianplus) from the GUI sidebar — a public exposure of a private
identifier that required crop/retake remediation. Two internal-control
failures, both ours:

1. The screenshot was taken from the LIVE 3080 session store without vetting
   the frame for private identifiers before posting.
2. The remediation loop (crop → retake → retake) was then NARRATED in the
   public update comment, exposing the incident itself.

Rule going forward (internal, not a public artifact): any capture destined
for a public surface must be taken from an isolated/scrubbed environment
(e.g. a throwaway DSH_HOME instance, sidebar collapsed, workspace names
absent) and frame-vetted for identifiers BEFORE posting; remediation of an
internal operational failure is recorded here, never in the public post.
