# Full-project review (dogfood, 2026-08-14)

Orchestrator: the solidforge session (DeepSeek). Legs: deterministic inner ring
(52 suites, ruff) + two same-source adversarial reviewers (code, docs) + one
heterogeneous doc leg (`hetero_doc_review.py`, provider zai-coding-cn/GLM-5.2 on
`docs/port-design.md`). pas skipped (the project claims realizability, not
novelty — no overclaim to collision-check); psv covered by the standing README
record (the new claims are internal-consistency claims, csr's domain).

## Deterministic inner ring (baseline before the review)

45 suites green locally (one jsonschema-gated fixture quirk); ruff clean.

## Code reviewer (same-source) — 15 findings, all reconciled

- **BLOCKER `loop-state-clobber / false-convergence-stamp`** — the hetero-review
  plugin invoked `hetero_review.py` WITHOUT `--embedded`, so the wrapper's
  standalone cycle re-`init`ed loop_state (wiping the caller's in-progress loop
  state) and `mark-converged` a task that never converged. FIXED: the plugin now
  passes `--embedded` (orchestrator owns init/mark-converged/run-record); live
  plugin updated (sfhet-4/pkg-9).
- `schema-vs-code mismatch` (run-record plugin injected a top-level `summary`
  the schema forbids). FIXED: injection removed; live plugin updated
  (sfrec-3/pkg-8).
- `silent gate fail-open` (empty catches turned gate crashes into silent
  greens). FIXED: pre-execute failures now surface honest "treated as
  UNVERIFIED" notices via the post-execute listener; live plugin updated
  (sfgate-2/pkg-7).
- `stale default` (tool description "or pi-ai"), `field-name mismatch`
  (`process_converged` naming in tool contract). FIXED (descriptions).
- `substrate default contradicts documented default`
  (`tmpl.get("substrate", "claude-code")` silently routed profiles without a
  substrate field to the FOREIGN harness). FIXED: default is now `dsh` in both
  wrappers.
- `docstring contradicts code` (stale namespace-isolation claim). FIXED.
- `env-chain precedence silently broken in plugin context` (harness scrubs
  shell credential vars from plugin-spawned subprocesses). FIXED by honest
  documentation in the tool description + guides.
- `terminal-state set inconsistency` (counters did not deny edits after
  `converged`). FIXED: `converged` joins TERMINAL_STATUSES with a dedicated
  message (post-convergence edits would invalidate the record).
- `copy-pattern drift` (csr's `_stdout_indicates_success` guard missing in pd).
  FIXED: ported into `hetero_review.py`.
- `stale strings in profiles` (ZHIPU_API_KEY/qwen3/pi-ai remnants). FIXED: swept.
- `portability` (BSD `stat -f` in sync-paper.sh). FIXED: GNU/BSD fallback.
- `self-check suites not wired into CI` (lint_self ×5, arm_neutral_config,
  research_constraints_goldens). FIXED: added to ci-suites.sh (52 suites now).
- `environment-gated gate check` (malformed-input rejection jsonschema-gated).
  FIXED: stdlib structural pre-check in converge.py — which also closed the
  long-standing fixture quirk (all 52 suites now pass without jsonschema).
- `structural enforcement not guaranteed by composition` (manual plugin
  activation). RECORDED (deliberate design tradeoff, documented in the preset).
- Coverage disclosures recorded (advisory mode when plugins absent; bash-tool
  bypass of per-file gates; throwaway-home assertions unit-level only).

## Doc reviewer (same-source) — 9 findings, all reconciled

- `W1 run-record-field-name` (docs named `process_converged` for pd records;
  the field is `converged`/`dod_satisfied`). FIXED across README/guides/
  port-design/plugins.
- `W2 family-label` (port-design said `_family: zhipu`; code says `glm`).
  FIXED.
- `W3 hetero-substrate-contradiction` (map line 29 stale parenthetical).
  FIXED.
- `W4 stale-profile-refs` (verification.md pi-ai/zhipu/minimax era). FIXED with
  explicit evolution note.
- `W5 env-example-stale` (PI_AI_API_KEY/zhipu,minimax remnants). FIXED.
- `W6 cff-invalid-status` (top-level `status` is not a CFF 1.2.0 key).
  FIXED: removed; draft note moved to `notes`.
- `W7 round-count` (papers README "4-round reconvergence" vs record's
  `rounds_run: 3`). FIXED.
- `C1 verbatim-carryover-unverifiable` + `C2 upstream-facts-unverifiable`.
  FIXED by softening (upstream tree not vendored) + hedging the harness-internal
  claim.

## Heterogeneous leg (zai-coding-cn) — 11 findings on port-design.md, reconciled

- **BLOCKER `hetero-verbatim-vs-rederive`** — §1 listed the hetero wrappers as
  "transferred unchanged / byte-for-byte / no harness references" while §4 calls
  them the substantive re-derivation. REAL contradiction the same-source doc
  reviewer missed. FIXED: §1 carves them out as the §4 exception.
- BLOCKER `zai-family-value-wrong` — duplicate of W2 (already fixed before the
  leg's report was read). FIXED.
- warning `substrate-default-contradicts-code` — duplicate of the code fix.
  FIXED.
- warning `only-substantive-rederivation-vs-additions` — §4's "only substantive
  re-derivation" vs §2/§3 additions. FIXED: qualified to "of the hetero
  mechanism".
- `lsp-plugin-noop-unverifiable` — no LSP adapters exist; claim dropped. FIXED.
- `dsh-substrate-enumeration-incomplete` — qwen placeholder omitted. FIXED.
- `outer-ring-shortcircuit-claim-unverifiable` — §3 overclaimed what the plugin
  does. FIXED: attributed to the skill's orchestrator rule.
- `upstream-relative-claims-unverifiable` (byte-for-byte/removed/reproduced).
  FIXED by softening; the byte-for-byte claim is additionally bounded by the §1
  carve-out.

## Post-review state

- 52/52 deterministic suites green locally (no jsonschema needed), ruff clean.
- Live plugins updated: sfgate-2/pkg-7, sfrec-3/pkg-8, sfhet-4/pkg-9.
- All three structural fixes verified by suites; the two copy-pattern wrappers
  re-aligned.
