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
