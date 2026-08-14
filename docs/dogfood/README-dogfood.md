# Dogfood: psv → csr convergence run on the port's own README.md

The port running its own discipline on its own artifact (SolidForge's dogfood pattern, now
on DSH). Date: 2026-08-14 (session timestamp 00:40–01:10). Orchestrator: the solidforge
session (DeepSeek). Records: `README-csr.run.json` (input), `README-csr.convergence-record.json`
(engine output), `README-psv.verdicts.json` + `README-psv.coverage-record.json` (psv full-M).

## Frame (recorded before the run)

- **Artifact:** `README.md` (port repo root). **Authority:** port repo tree + installed preset
  (`~/.dsh/.agent-presets/solidforge/`) + upstream `maskshell/solidforge` + the paper.
- **Core claims (4):** C1 port identity + paper link; C2 structure claims (composition,
  5 skills, 22 agents, 3 plugins); C3 heterogeneous-provider config claims; C4 verification
  claims. **Size tier:** short (cap=2).

## psv GATE MODE judgment (before csr)

SKIPPED by the ODP-5 discriminator, non-authoritative: README is a short, predominantly
LOCAL-citation doc — "short docs never pay (gate ≈1.5 rounds vs ≤2 rounds max saved)". The
authoritative psv full-M run followed csr (below).

## csr rounds

**Round 1 — same-family leg (fresh-context doc-reviewer subagent).** 9 findings
(6 warnings + 3 coverage disclosures), 0 blockers. All 6 warnings fixed in the artifact
(classification of csr as process-axis; mount-validation pointer → `test/verification.md`;
references qualifier; stale 254→263 file count in the verification record; `$DSH_HOME`
consistency; paper-link fallback). The 3 coverage disclosures recorded with dispositions
(one substance-accepted → wording reworded to the by-design boundary; two recorded as
disclosures).

**Round 2 — same-family leg (fresh context, prior findings fed).** 2 warnings (residual
README-vs-port-design causal mismatch on the in-process boundary + a typo; arm-tools table
shorthand path). Both fixed; the two docs now agree on the by-design boundary.

**Round 3 — different-family leg (`hetero_doc_review.py`, provider `claude`, native auth).**
- Attempt 1 (sonnet, 420s): **cold-start timeout** — wrapper recorded
  `hetero-subprocess-timeout` malformation (conservative verdict, 0 findings). Documented
  fallback applied: retry on the haiku tier (install.md's cold-start guidance), 600s.
- Attempt 2 (haiku): **succeeded** — 2 findings:
  - `agent-count-mismatch` — **blocker**, "only 21 agent files"; its own evidence enumerates
    22 names. Independent verification: `ls preset/agents/*.agent.md | wc -l` = 22, name set
    identical to the README's claim. **Heterogeneous-oracle FALSE POSITIVE** — a live instance
    of the paper's §8.7 oracle-reliability problem, handled by the reconciliation table:
    different-family-only finding, independently verified, rejected with rationale.
  - `profiles-root-path-citation` — warning, accepted; README now names the full profile
    path.

## Engine judgment (converge.py, schema-validated with jsonschema 4.26)

| Round | Leg | Verdict | New blockers |
| --- | --- | --- | --- |
| 1 | same-family | pass | 0 |
| 2 | same-family | pass | 0 |
| 3 | different-family | rewrite | 1 (false positive) |

**`substantive_converged: false` · `stalemate: true` · `rightness: human_confirm_required`**
— prong_b (no new blocker for ≥2 rounds) fails on the round-3 blocker; the run hit the
short-tier cap, so the record escalates to the human, per the protocol (never silent-pick).
Core-claims coverage: 4/4.

## psv full-M (authoritative coverage record, after csr)

64 extracted claims (61 admissible, 3 inadmissible interpretive → escalate). Verdicts:
**60 verified · 0 refuted · 1 narrowed · 3 unverifiable** of 64.
- The one narrowed (C45): the docs described the env-resolution load order as
  "lowest-precedence-first" while the code loads highest-precedence-first via setdefault
  (net precedence identical). FIXED after the run — README + `.env.solidforge.example` now
  say "highest-precedence-first (setdefault — first-loaded wins, shell always wins)".
- Signal: `oracle_verified_under_known_coverage`; `rightness: human_confirm_required`;
  `correctness_converged` never appears. 3 escalations (C40/C52/C63 — interpretive claims).

## Honest reporting

- `axis_b_status` (round 3, historical): the heterogeneous oracle RAN on the
  then-default `claude` substrate (native auth — a real cross-provider subprocess),
  after one cold-start timeout retried on the documented fallback tier.
- The same-source ring ran first and is the reliability floor (paper §4.4(1)).
- The convergence-engine outcome is NOT silent-picked: the human adjudicates the round-3
  blocker below.

## Human adjudication (recorded 2026-08-14)

The round-3 blocker `agent-count-mismatch` is **REJECTED by the human adjudicator**:
independent verification is decisive — `ls preset/agents/*.agent.md | wc -l` = 22, and
the heterogeneous leg's own evidence enumerates 22 names while asserting 21. The
convergence-record is an immutable audit trail and stays as the engine emitted it
(`substantive_converged: false`, `stalemate: true`, `rightness:
human_confirm_required`); the human judgment rides ON TOP of it: the same-source ring
substantively converged (2 rounds, 0 blockers, 11 findings all reconciled), the
heterogeneous ring ran for real and its only blocker was a verified oracle false
positive — a live instance of the paper's §8.7 heterogeneous-oracle reliability
problem, which is itself the dogfood's most valuable output.

## Substrate redesign (post-dogfood, driven by human review)

The dogfood's round 3 exposed a porting error, caught by human review: the port had
inherited the upstream `claude -p` mechanism VERBATIM, but upstream REUSES its host
harness (the plugin lives inside Claude Code) while the DSH port was IMPORTING a foreign
harness. Heterogeneity is a different LLM, not a different harness. Fixed:

- **Default substrate = `dsh`**: the wrapper now spawns a fresh, stateless
  `dsh --profile headless` subprocess with a throwaway `DSH_HOME` pinning a different
  provider/model route (`substrate: dsh`, default `profiles/pi-ai.json`) — same harness,
  different LLM, out of process. Paper §8 open-problem-6 contingency resolved.
- **`substrate: claude-code` = labeled external-harness opt-in only** (never the default):
  `claude.json`/qwen/bigmodel/minimax profiles.
- Re-run under the new default: the leg fail-fasts honestly —
  `DSH-native provider 'pi-ai' needs the credential env var $PI_AI_API_KEY`
  (no route armed on this machine; NO foreign harness invoked, no Claude quota
  consumed, never silently green). Arming = set route + model in
  `profiles/pi-ai.json` + `PI_AI_API_KEY` in the three-tier env chain.
- Wiring suites re-pass with the substrate dispatch + fail-fast-cleanup branch covered
  (`hetero_review_wiring.py`).


## Round 4 — dual-hetero re-run under the DSH-native substrate (post-adjudication)

Both heterogeneous providers were armed (user-provided keys) and smoke-tested
end-to-end through the wrapper's own machinery: fresh `dsh --profile headless`
subprocesses, throwaway DSH_HOME, pi-ai hand-declared routes —
**zhipu (GLM-5.2, `https://open.bigmodel.cn/api/anthropic`) and minimax
(MiniMax-M3, `https://api.minimaxi.com/anthropic`) both rc=0 "OK"**; no foreign
harness in either path. (Route arming notes: pi-ai protocol id is
`anthropic-messages`; GLM refused explicit reasoningEffort levels, so the
wrapper now omits the key when a profile does not declare one.)

The real dual-hetero review of README.md (14 findings, `README-csr-hetero-round4.json`):

- **1 blocker (zhipu), fixed**: line 20 still named `claude -p` as the default
  while the config section + code say DSH-native — the discipline paragraph was
  pre-redesign residue; both providers flagged it independently (minimax as a
  warning) — a genuine cross-family agreement on a real defect.
- **7 warnings, fixed**: `$SOLIDFORGE_PRESET_ROOT` was load-bearing in docs but
  exported nowhere (now documented as an alias for
  `$DSH_HOME/.agent-presets/solidforge/`, wrappers resolve by walking up);
  workspace-armed parenthetical removed from the committed README (runtime state
  belongs to the gitignored `.env.solidforge`); three-tier list renumbered to
  match the code's actual load order (README + template); `HETERO_DOC_PROFILE`
  selector documented; skills-row wording corrected (customSkillDirs mounting);
  Verify-section full paths; hetero-review plugin source comments + tool
  description updated (and the live sfhet-4 package re-run as pkg-6).
- **2 coverage disclosures, recorded**: HETERO_DOC_PROFILE independence (verifier
  couldn't confirm; code-verified: `hetero_doc_review.py` reads it separately);
  plugin-source/tool-description staleness (fixed).
- **4 rejected — a SECOND class of heterogeneous-oracle false positives**:
  minimax reviewed the POST-fix artifact and concluded four round-1/2 findings
  were "inverted/stale/already-fixed" (`outcome-axis-count-was-backwards`,
  `f7-residual-already-fixed`, `arm-tools-path-was-full`,
  `dsh-home-was-not-hardcoded`). Each was valid against the PRE-fix artifact —
  the round-1/2 evidence quotes the pre-fix text, and the current text IS the
  fix. Disposition: rejected with rationale (false positives of the
  "stale-finding misread" kind, distinct from round 3's miscount kind).

Combined with round 3's miscount false positive, the dogfood now has **two
observed heterogeneous-oracle error modes with independent verification
resolutions** — both recorded, neither silently picked.

## Provider-profile merge + effort fix (human review, 2026-08-14)

Human review caught three things, all fixed:

1. **zhipu = BigModel = 智谱 — one family, one profile.** The split
   (`zhipu.json` dsh-substrate vs `bigmodel.json` claude-code substrate) was an
   artifact of the substrate migration and both confused users and looked like
   the foreign-harness pattern was still endorsed. FIXED: `bigmodel.json`
   DELETED; `zai-coding-cn.json` is the single GLM profile, DSH-native. The
   external-harness substrate remains ONLY for backends with no pi-ai route
   (`claude.json`, `qwen.json`).
2. **GLM supports reasoning effort** — the earlier "no effort" failure was the
   WRONG endpoint/protocol (the anthropic-compatible endpoint exposes no effort
   levels), not a GLM property. FIXED with the official route: catalog
   `zai-coding-cn` (openai-completions,
   `https://open.bigmodel.cn/api/coding/paas/v4`, model `glm-5.2` with
   thinkingLevelMap) — smoke rc=0 WITH `reasoningEffort: high`.
3. **Catalog routes over hand-declared ones**: `_prepare_dsh_home` now always
   emits the `llm-pi-ai` section (apiKeyEnv-only entries for catalog routes);
   MiniMax switched from a hand-declared route to the catalog `minimax-cn`
   (the `sk-cp-` key format is the CN platform; the international `minimax`
   route 401s with it). Both providers re-smoked rc=0 on catalog routes.

## Naming consolidation: route-derived everything (human review, 2026-08-14)

Profile = route = credential-var prefix, one namespace end to end: the profile
filename IS the pi-ai route (provider derives from it), and the credential var
derives from the route too — `<UPPERCASE(route)>_API_KEY` is pi-ai's OWN env
convention (verified against pi-ai's env-api-keys table: zai-coding-cn →
ZAI_CODING_CN_API_KEY, minimax-cn → MINIMAX_CN_API_KEY). The earlier
family-named vars (ZHIPU_API_KEY / MINIMAX_API_KEY) were port inventions that
broke the ecosystem convention; they are removed. `_credential_env` remains
only as an escape hatch for routes whose convention differs. Multi-provider
composition stays at the selector level (`HETERO_PROFILE=a,b`) — a profile is
an atomic arming unit (one route + one model + one credential), 1:1 by
construction, which is what keeps per-provider error attribution unambiguous.
Both providers re-smoked rc=0 under the derived vars.

## `_family` earns its keep: same-source guard (human review, 2026-08-14)

`_family` was dead metadata (nothing read it). It is now FUNCTIONAL: profiles
declare their model family, and the wrappers (1) REFUSE an orchestrator-family
route (fail-fast — DeepSeek routes can never be heterogeneous legs), (2) attach
an honest coverage note when a dual run's profiles share one family
(same-family duality adds no blind-spot diversity), and (3) note profiles that
declare no family (guard inactive — never silent). claude.json/qwen.json
declare `anthropic`/`qwen` too, so the guard spans both substrates. Wiring
suite covers all three branches.

## Family vocabulary = model lineage; qwen placeholder added (human review, 2026-08-14)

`_family` now names the MODEL LINEAGE — the paper's own family vocabulary
(DeepSeek/Qwen/GLM/Claude): `zai-coding-cn.json` → `glm` (zai/bigmodel/zhipu
are brands/platforms of one lineage), `claude.json` → `claude`,
`minimax-cn.json` → `minimax`, `qwen*.json` → `qwen`. The claude-code
`qwen3.json` was renamed `qwen.json` (version-free profile name; the pinned
model alias stays editable inside the profile). A DSH-native Qwen PLACEHOLDER
was added: `qwen-token-plan-cn.json` (pi-ai catalog gateway route — NOTE the
route is multi-family, so its `_family` names the PINNED model's lineage);
armed by setting `QWEN_TOKEN_PLAN_CN_API_KEY` (route-derived). All suites pass.
