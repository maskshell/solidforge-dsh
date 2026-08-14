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
different provider/model route (default `profiles/pi-ai.json`, arming =
route+model+`PI_AI_API_KEY`). The upstream `claude -p` mechanism is a labeled
external-harness opt-in (`substrate: claude-code`) only — heterogeneity is a different
LLM, not a different harness. Verified: both wrappers fail fast with the arming message
and no subprocess spawn when the route is unarmed; wiring suites pass including the new
DSH-home construction + fail-fast-cleanup branch.

## Heterogeneous arming + live dual-hetero run (2026-08-14)

User-provided keys armed two DSH-native heterogeneous profiles:
`profiles/zhipu.json` (GLM-5.2, open.bigmodel.cn anthropic endpoint) and
`profiles/minimax.json` (MiniMax-M3, api.minimaxi.com anthropic endpoint) — both
`substrate: dsh`, hand-declared pi-ai routes (`api: anthropic-messages`),
credentials in the gitignored workspace `.env.solidforge`
(`HETERO_PROFILE=zhipu,minimax`). End-to-end smoke: both providers rc=0 via fresh
`dsh --profile headless` subprocesses — zero foreign harness. Live dual-hetero
review of README.md: 14 findings, 1 real blocker + 7 warnings fixed, 4 rejected
as a second oracle-false-positive class (stale-finding misreads), trail in
`docs/dogfood/README-csr-hetero-round4.json` + `README-dogfood.md` round 4.
