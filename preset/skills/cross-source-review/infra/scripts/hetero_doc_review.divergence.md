# hetero_doc_review.py — divergence log (CSR-I3, Phase-A interface-compat)

> Authority: `docs/proposal.md` §5 / F3 (Phase-A compatibility constraint), §9 Q3 (no
> loop_state dependency); `docs/iteration-plan.md` §CSR-I3 (Phase-A compat constraint).
>
> Purpose: list EVERY intentional divergence from `parallel-development`'s
> `infra/scripts/hetero_review.py` (the copy-pattern source — rule 7) and ASSERT the
> preserved function-signature contract, so the Phase-B B1/B3 decision (proposal §5)
> stays data-driven rather than invalidated by silent drift. A future maintainer can
> see the drift is deliberate.
>
> Source file baseline: `skills/parallel-development/infra/scripts/hetero_review.py` as of
> commit `e40f328` (the copy-pattern source — rule 7). Line counts are NOT tracked here —
> they drift on any reformat (csr-doc-1 caught a stale 955/930 vs actual 954/928). Re-derive
> structural compatibility via the preserved-signature table + the divergence list below,
> not line counts. (Net delta is negative — loop_state driving was removed, change #4.)

## Preserved function-signature CONTRACT (Phase-A compat — proposal §5 / F3)

The following signatures are preserved EXACTLY (interface-level, not implementation).
Phase-B B1 (pd imports this substrate) / B3 (shared lib) can rely on them.

| Function | Preserved signature | Body status |
| --- | --- | --- |
| `_materialize_profile` | `(name) -> <temp-path-str>` | near-verbatim (temp suffix + error message adapted — see change #0c) |
| `_claude_argv` | `(profile, model, schema_json, prompt, budget_usd, allowed_tools, observe_hooks) -> list[str]` | verbatim (same flag surface, CC v2.1.201) |
| `run_claude` | `(argv, timeout_s, dry_run, dry_findings, dry_malform=False, dry_budget=False) -> dict` | signature preserved; DEGRADE handling EXACT (ADR #41); ADDED the `_stdout_indicates_success` success-quirk guard before the substrate-error parse (see minor divergence); docstring annotations adapted |
| `_parse_cc_substrate_error` | `(raw) -> (subtype\|None, errors[list])` | verbatim (ADR #41 — preserved EXACTLY) |
| `_validate_findings_shape` | `(obj) -> str` (malformation fingerprint, '' on success) | signature preserved; validation LOGIC diverges — see change #3 |

Also preserved verbatim (not in the explicit contract list, but part of the substrate):

- `_load_dotenv` / `_load_dotenv_file` / `_project_root_for_env` / `_ENV_VAR_RE` / `_expand_env_values` / `_resolve_token_var` — provider-template + token-injection pattern (ADR #40).
- `_parse_json_return` / `_parse_stream_json` / `_extract_text` / `_try_json` / `_extract_json_object` / `_JSON_FENCE_RE` — fence-aware JSON parse.
- `DEGRADABLE_CC_SUBTYPES` — frozenset of recoverable CC subtypes (ADR #41), byte-identical.
- `_read_schema` — trivial schema reader.
- The FLAG-SURFACE MANIFEST docstring block — structure preserved; the `--json-schema` line names `doc-findings.schema.json` (was `violation-log.schema.json`) — faithful doc-adaptation, not a drift.
- The `--dry-run` / `--dry-run-malform` / `--dry-run-budget` offline paths (needed by CSR-I5's offline gate).
- The multi-provider merge (`per_provider` loop + provider-tagging when >1 backend + aggregate).
- Self-contained, pure stdlib, exits 0 on success (rule 7).

## Intentional divergences (the 5 mandated CSR-I3 changes + minor consequences)

### Change 1 — CLI surface (doc-domain: a doc has no diff/blueprint)

- `--diff` (required) → REMOVED.
- `--blueprint` (required) → REMOVED.
- `--artifact` (required) → ADDED (the doc under review).
- `--authority` (optional, default `""`) → ADDED (the authoritative reference; empty = self-contained — verify against the doc's own internal consistency).
- `--task-id`, `--embedded`, `--project-dir` → REMOVED (loop_state args — see change #4).
- `--profile` env-var default → `HETERO_DOC_PROFILE` (was `HETERO_PROFILE`) — keeps the doc wrapper's provider selection independent from pd's. The flag name `--profile` is unchanged.
- `--timeout` env-var default → `int(os.environ.get("HETERO_DOC_TIMEOUT", "600"))` (was a bare `default=600`) — mirrors pd's `HETERO_TIMEOUT`; keeps the per-call wait cap configurable without touching model selection (ADR #43). The flag name + the 600 default (when the env is unset) are unchanged.
- KEPT: `--profile`, `--model`, `--budget-usd`, `--allowed-tools`, `--timeout`, `--observe-hooks`, `--round-index`, `--prior-findings`, `--findings-schema`, `--dry-run`, `--dry-run-malform`, `--dry-run-budget`.

### Change 2 — adversarial_prompt (CODE-shaped → DOC-shaped)

- pd's prompt hunts `correctness bugs, security issues, performance problems, maintainability defects, loading-chain / rule-5 reachability gaps` against a diff + blueprint.
- This copy hunts the Q2 6 doc defect kinds (`contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` / `citation-error` / `coverage-gap`) against `--artifact` (optionally checked against `--authority`, or self-contained).
- BARRED from outcome-axis (proposal §2): does NOT judge whether the doc is "right".
- Returns a doc-findings object (was violation-log).
- KEPT: the prior-findings framing ("find what the primary MISSED, not what it already found") fed via `--prior-findings`.
- Signature changed: `(diff_ref, blueprint_ref, prior_findings, round_no)` → `(artifact_ref, authority_ref, prior_findings, round_no)`. This function is NOT in the preserved-contract list.

### Change 3 — findings schema (violation-log → doc-findings)

- `FINDINGS_SCHEMA` default → `infra/schemas/doc-findings.schema.json` (was `violation-log.schema.json`).
- `_validate_findings_shape` — signature `(obj) -> str` PRESERVED; validation LOGIC diverges:
  - accepts top-level `outcome_axis_respected` (bool) + `findings` (list) — was just `findings` (list).
  - per-finding `severity` ∈ {blocker, warning, coverage} — was {blocker, warning}. The `coverage` severity is PRESERVED per proposal §9 Q2 / plan-reviewer novel-3 (the reviewer's honest-disclosure mechanism, rule 3; DISTINCT from the `coverage-gap` KIND).
  - per-finding `kind` ∈ the 6 Q2 doc kinds — NEW check (violation-log had no `kind`).
- Two NEW malformation fingerprints introduced (doc-domain): `hetero-missing-outcome-axis`, `hetero-bad-kind`. The existing fingerprints (`hetero-not-object`, `hetero-missing-findings`, `hetero-finding-malformed`, `hetero-bad-severity`) are preserved verbatim.
- The `dry_findings` canned return is doc-findings-shaped `{"outcome_axis_respected": True, "findings": []}` — was violation-log-shaped `{"gate", "passed", "coverage", "findings"}`.

### Change 4 — REMOVE loop_state driving (proposal Q3: no loop_state dependency)

The doc domain does NOT drive pd's `loop_state` state machine. The CSR-I4 convergence driver (built separately) calls this wrapper once per round and assembles the convergence-record itself.

- DELETED: `_run_loop_state`, `LOOP_STATE_PY` constant, `drive_lifecycle` function + its call.
- DELETED: the `glob` import (was only used inside `drive_lifecycle` for run-record path resolution).
- The wrapper now runs ONE 异源 review and PRINTS a clean result dict:
  `{verdict, degraded, degraded_providers, findings_count, findings, coverage, malformation, providers}`.
- The `notes` field (pd feeds it to loop_state `record-outer`) and `run_record` field are DROPPED from the result.

### Change 5 — module docstring updated

- Describes the doc-domain purpose; points to `proposal.md` §3/§5/§8/§9 Q2+Q3 and `iteration-plan.md` §CSR-I3; notes it is a copy-pattern of pd's `hetero_review.py` (rule 7); records the exit-code contract.

## Minor consequential divergences (drift hygiene — not CSR-I3 mandates)

- Exit code semantics. pd always exits 0 because its loop_state/driver interprets the verdict. This wrapper is STANDALONE (no loop_state — proposal Q3), so it surfaces malformation via exit 1 for the CSR-I4 subprocess contract: `0` = produced a usable result (pass OR rewrite-due-to-blocker OR degrade — read the structured fields for which); `1` = malformation (could NOT parse a usable return); `2` = argument/IO error.
- `_extract_coverage` NEW helper. Doc-domain: the reviewer's "could not verify X" disclosures arrive as `coverage`-severity findings (the schema has NO top-level `coverage` array, unlike violation-log). The helper collects their evidence/location strings for the coverage trail. `per_provider.model_coverage` is sourced via this helper (was `(findings_obj or {}).get("coverage", [])`).
- `_load_prior` fallback shape. On a non-JSON prior, the synthetic stub is doc-findings-shaped `[{severity, kind:"citation-error", location:"prior-findings", evidence}]` — was violation-log-shaped `[{severity, rule, detail}]`. Prior is prompt-context only (never validated); the shape change is cosmetic consistency.
- `_resolve_profile_path` error message. Dropped the pd-specific "see model-routing.md" reference (cross-source-review has no model-routing.md). Now reads "Committed templates live in infra/scripts/profiles/.".
- `_materialize_profile` temp suffix. `-hetero-doc-<name>.json` (was `-hetero-<name>.json`) — domain-distinct, helps debugging when both wrappers run in the same project.
- `_materialize_profile` missing-token error message. Dropped the pd-specific "See model-routing.md." trailer. The convention-explanation body is preserved.
- `run_claude` + `_parse_json_return` + `_parse_stream_json` docstring annotations. "violation-log-shaped" → "doc-findings-shaped"; "P1-7 wiring test" → "CSR-I5 wiring gate". The LOGIC is preserved exactly; only docstring prose adapts.
- `_load_dotenv` docstring reframed to host-generic language (was pd's "Solid Forge vars" / "arm-provisioned default" — solidforge-centric wording in portable code). The BODY is unchanged (still reads `<cwd>/.env.solidforge` then `<cwd>/.env`, CWD-based — portable: csr reads the invoking project's env). The provisioning model + custom-provider guide live in `references/install.md`.
- `run_claude` ADDED the `_stdout_indicates_success(raw)` guard before the substrate-error parse: a non-zero exit WITH a success envelope (CC `subtype:"success"`) short-circuits to the normal parse — the result is usable. Surfaced by the CSR-I6 dogfood on a long doc (a CC backend quirk: `subtype:"success"` + `is_error:true` + non-zero exit; the wrapper had malformationed `hetero-cc-error:success`, discarding the result). ADR #41 DEGRADE handling unchanged (a genuinely-degraded/error envelope still degrades/malforms). pd's copy does NOT have this guard yet — candidate B2 pattern-refresh if pd hits the same quirk on its domain. The `run_claude` SIGNATURE is unchanged (preserved-contract).

## Supporting infra created alongside the wrapper (rule 7 — mirror the exemplar)

- `infra/scripts/profiles/deepseek.json` — sanitized copy of pd's `profiles/deepseek.json` (routing-only, no secret). The `_comment` cites CSR-I3 / rule 7 (copy-pattern) and notes DeepSeek's auto-cache rate (cold-start transient; ADR #43).
- `../../ruff.toml` (skill root) — MIRRORED VERBATIM from `skills/parallel-development/ruff.toml`: selects `E4/E7/E9/F` only (real bug-catchers, no style churn), ignores E501. Necessary so the substrate (which deliberately uses `try/except/pass` and an `if/else` for the ADR #41 fingerprint logic, exactly like pd's source) lints under the SAME standard as its pd source. The repo-root `pyproject.toml` selects the broader `E/F/W/I/UP/B/SIM` set; this per-skill override is deliberate and matches pd exactly. Do NOT "widen" it without re-deriving the rule-7 rationale.
- `open(..., "r", encoding="utf-8")` → `open(..., encoding="utf-8")` at 4 sites (`_read_schema`, `_load_prior`, `_load_dotenv_file`, `_materialize_profile`). Behavior-preserving (read is the default); the UP015 lint is enforced under the repo-root config but not under the per-skill override — this cleanup keeps the file clean under EITHER config.

## Verification (CSR-I3 DoD)

- `uv run --no-project --with ruff ruff check skills/cross-source-review/infra/scripts/hetero_doc_review.py` → `All checks passed!` (under the per-skill `ruff.toml`).
- `python3 -c "import ast; ast.parse(open(...).read())"` → `AST PARSE OK`.
- `--dry-run` → exit 0, `{verdict: pass, findings_count: 0, findings: [], degraded: false, ...}`.
- `--dry-run-malform` → exit 1, `verdict: rewrite`, `malformation: "dry-run-malform"`, coverage notes the malformation.
- `--dry-run-budget` → exit 0 (ADR #41 — degrade is NOT a malformation), `degraded: true`, `degraded_providers: [{provider: deepseek, subtype: error_max_budget_usd, ...}]`.
- `_materialize_profile("deepseek")` → resolves `profiles/deepseek.json` + reads `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` from `.env.solidforge` (via `_load_dotenv`), writes a chmod-600 temp, injects the token, preserves BASE_URL routing (token NOT printed in the verification).
