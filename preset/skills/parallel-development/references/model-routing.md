# Model routing — per-stage provider policy (DSH port)

> Single source of truth for WHICH model family runs at WHICH stage of the convergence loop. Authority: ADR #40 (`design-decisions.md §40`) + the operational plan. On conflict, ADR #40 wins.
>
> **Port note.** The upstream file assumed a GLM/Claude orchestrator and treated DeepSeek as a heterogeneous backend. The DSH port inverts this: the orchestrator runs on DeepSeek (deepseek-v4-pro), so DeepSeek is the SAME-SOURCE family and the heterogeneous set becomes Claude (native), Qwen, GLM/BigModel, MiniMax. The paper's example (§4.1 tier-2) — "a Claude orchestrator reviewed by a DeepSeek/Qwen/GLM subprocess" — is realized here in its mirror image: a DeepSeek orchestrator reviewed by a Claude/Qwen/GLM subprocess. Everything else (additive non-replacing, opt-in high-stakes only, subprocess boundary) is unchanged.

## Routing policy (per stage)

| Stage | Mode | Provider (example) | Always? | Role |
| --- | --- | --- | --- | --- |
| author (main orchestrator) | interactive DSH session | DeepSeek v4 pro | yes | deep reasoning + format-reliable; no added risk |
| adversarial review (same-source) | in-process `subagent` tool | DeepSeek (primary) | **yes (primary)** | fast, cheap, tool discipline, reliable floor |
| adversarial review (different-family) | non-interactive subprocess (`hetero_review.py`) | Claude / Qwen / GLM | **opt-in (high-stakes)** | adversarial second opinion; cross-family blind-spot check |
| research (researcher / Explore fan-out) | non-interactive subprocess or tier | DeepSeek flash / Qwen flash | as needed | fan-out; cost-dominated |
| normalize / constraints-check / freeze / fast_gate / arch-contract | deterministic code | — (no model) | — | model-independent |
| inner-ring Coder (GREEN) | same-source (default) | DeepSeek | yes | highest tool-call-reliability risk; consider different-family LAST |

## different-family priority

**reviewer > research > Coder.** The reviewer is the safest different-family entry point (read-only + structured findings, narrow tool surface, tolerable occasional malformation). The inner-ring Coder carries the highest tool-call-reliability risk and is the LAST different-family candidate — it is same-source by default.

## Research-tier routing (Phase 3, P3-1)

The research / Explore fan-out tier is cost-dominated (multi-source gathering, broad read) — a cheap backend is the right tier. In the DSH port it may run either same-source (a spawned DeepSeek subagent) or cross-family via the SAME non-interactive-CLI substrate as the different-family reviewer (proven by `hetero_review.py`):

```bash
claude -p --settings profiles/qwen.json --model flash \
  --output-format json --permission-mode bypassPermissions \
  --no-session-persistence --max-budget-usd <cap> \
  --allowedTools "WebSearch WebFetch Read Grep Glob" \
  -p "<research prompt>"
```

Notes:

- This is NOT a new engine — it reuses the `profiles/<backend>.json` provider configs + the `claude -p` spawning pattern. The orchestrator spawns it directly for research fan-out (analogous to how it spawns `hetero_review.py` for the different-family review).
- The research prompt is NOT adversarial (unlike the reviewer) — it gathers + cites. Trust/provenance on research findings stays the blueprint-crafting `research_constraints.py` oracle (sources-cited / staging / cost-bounded), NOT the cheap backend's judgment.
- The per-item binding (WHICH plan-queue items route research to the cheap backend) is the Phase 3 P3-2 `hetero` hint on plan-queue items.
- Reliability caveat: the cheap-backend tool-call reliability on research tools is a measured property, not assumed.

## Opt-in trigger (the different-family reviewer)

The different-family reviewer runs ONLY on high-stakes items; default items pay zero added cost (same-source only). The trigger conditions (ADR #40 (b)):

- ADR-level decisions.
- security- or correctness-sensitive diffs.
- a same-source verdict that is partially-satisfied or low-confidence.

This trigger list is the ADR #40 (b) prose — a **human-judged classifier, NOT an automated one**. The orchestrator decides per item; there is no deterministic gate that forces different-family. Per-item automation (a `hetero` hint on plan-queue items) lands in Phase 3 (P3-2) and is itself a recommendation the human judge can override.

## Substrate

different-family runs as a fresh, stateless OS subprocess spawned by
`infra/scripts/hetero_review.py`. **Two substrates, one boundary** — the profile's
`substrate` field selects the leg's runtime; heterogeneity means a DIFFERENT LLM,
and the DEFAULT keeps it on the SAME harness:

- **`substrate: dsh` (the port's default).** The wrapper
  builds a throwaway `DSH_HOME` whose `settings.yaml` pins `agent-default-model`
  to the profile's provider route + model, and spawns
  `dsh --profile headless "<adversarial prompt>"` — a fresh, stateless DSH session
  on a DIFFERENT provider/model family. Same harness, different LLM, out of
  process. This is the paper's §4.4 boundary re-derived for a harness with
  first-class multi-provider routing (§8 open problem 6): the decoupling boundary
  is preserved BY DESIGN (fresh process, no global router), without importing a
  foreign harness.
- **`substrate: claude-code` (explicit opt-in ONLY, `profiles/claude.json` +
  `qwen.json` — backends with no pi-ai route).** The upstream mechanism — `claude -p --settings
  <profile>` repointing an Anthropic-compatible endpoint. It drags the Claude
  Code CLI into a DSH run (a FOREIGN harness), so it is never the default; it
  exists for backends that expose only an Anthropic-compatible surface.

```bash
# DSH-native (default): same harness, different LLM
dsh --profile headless "<adversarial prompt>"      # DSH_HOME=<throwaway>, provider pin via settings.yaml
# External-harness opt-in: the upstream mechanism, explicitly labeled
claude -p --settings profiles/<backend>.json --model <alias> ...
```

The subprocess is a fresh, stateless session; it does NOT inherit the DSH
session's in-process subagent substrate. The wrapper drives `loop_state`
truthfully around the subprocess (ADR #39, ADR #40 (g)). See
[convergent-loop.md](convergent-loop.md) § different-family adversarial review
for the multi-round debate loop + cap + termination semantics.

**Credential namespacing is per-substrate.** dsh-substrate profiles declare
`_credential_env` (the DSH adapter's own `apiKeyEnv`, e.g. `PI_AI_API_KEY`) — the
provider's native key IS the correct credential for its own DSH adapter. The
`<NAME>_ANTHROPIC_AUTH_TOKEN` convention applies ONLY to claude-code-substrate
profiles (it namespaces the credential to the Anthropic gateway).

**Provider profile + API key** (current post-consolidation shape):

- **Profile filename = the ROUTE** (`profiles/zai-coding-cn.json`, `minimax-cn.json`,
  `qwen-token-plan-cn.json`; claude-code substrate: `claude.json`, `qwen.json`) —
  one route + one model + one credential per file (1:1 by construction);
  multi-provider composes at the SELECTOR level (`HETERO_PROFILE=a,b`).
- **Substrate per profile** (`substrate: dsh` default | `claude-code` labeled
  external-harness opt-in). dsh-substrate profiles ride the installed pi-ai
  CATALOG routes (endpoint + protocol + models inherited; only apiKeyEnv is
  declared). The wrapper refuses a profile whose `_family` is the orchestrator's
  lineage (same-source), and honesty-notes same-family dual runs + undeclared
  families (never silent).
- **Credential var is ROUTE-DERIVED**: `<UPPERCASE(route)>_API_KEY` — pi-ai's own
  env convention (`zai-coding-cn` → `ZAI_CODING_CN_API_KEY`, `minimax-cn` →
  `MINIMAX_CN_API_KEY`); `_credential_env` is only an escape hatch. The
  claude-code substrate keeps the legacy `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN`
  convention (namespaced to the Anthropic gateway — the provider's native key is
  NEVER read by THAT substrate).
- The token is NOT in the profile. Set it in your shell, the arm-provisioned
  `.env.solidforge` (shell wins), or your app `.env` — the wrapper reads the
  three-tier DSH chain (`shell > project .env.solidforge > project .env >
  preset-root .env.solidforge`; the preset root is the dir holding
  `agent.cordis.yml`, resolved by walking up from the script).
  `cp .env.solidforge.example .env.solidforge` to start (the `.example` is
  committed; `.env.solidforge` is gitignored).
- **Provider selection**: `--profile <name>` (a NAME, not a path) or
  `export HETERO_PROFILE=<a,b>`. Default: UNSET = fail-fast arming prompt —
  never a silent fallback.
- **Add a provider** (zero code change): `cp profiles/minimax-cn.json
  profiles/<route>.json` + edit model/_family + set `<ROUTE>_API_KEY` in the
  env chain → `hetero_review.py --profile <route>` works.
- **Dual-/multi-different-family**: `--profile a,b` runs each backend
  independently and merges findings, each tagged with its `provider`.
  Pick two profiles NEITHER of which is the orchestrator's lineage — e.g. in a
  DeepSeek-orchestrated project, `zai-coding-cn` + `minimax-cn`.
  Enforced by the wrapper: same-lineage refusal + dual-family honesty notes
  (see above).
- Set `--budget-usd` with headroom (default 4.0, under the global 5.0 cap) — it
  is a runaway backstop, NOT real cost: for non-Anthropic backends the API
  returns tokens only (no price field), so the CLI's USD is structurally
  disconnected from provider spend (ADR #42). The reliable provider-independent
  bounds are the CLI's turn limit + `step_cap_S`. A cold multi-tool review is
  token-heavy regardless, so keep headroom; if a review still trips the cap it
  DEGRADES (verdict stays pass/rewrite from the other providers; ADR #41), not
  rewrites.

- **Subprocess timeout**: `--timeout <seconds>` (default 600, or `$HETERO_TIMEOUT`). A cold large diff can exceed 600s and return a `hetero-subprocess-timeout` malformation. For a known-cold large review: raise `--timeout` (e.g. 1200–1800s) to keep the top tier, OR drop to `--model haiku` (→ the profile's flash alias) for that call. Do NOT remap the profile alias to dodge a timeout — cold-start is transient, and a global alias remap permanently sacrifices review depth on warm calls (ADR #43). Set `HETERO_TIMEOUT` in `.env.solidforge` to fix the cap per-project.

## Reconciliation (same-source + different-family findings)

| Findings | Action |
| --- | --- |
| both same-source + different-family report | high-confidence; adopt |
| same-source only | adopt (primary status) |
| different-family only | strong signal (cross-family independent find = same-source blind spot); escalate for adjudication |
| neither | pass |
| different-family DEGRADED (substrate error: budget/turn cap, provider overwhelm) | adopt the same-source primary (different-family contributed nothing); `degraded:true` + a persisted `hetero-degraded-<subtype>` fingerprint distinguish it from a clean pass (ADR #41) |

## Cost model

- Default item (low/medium risk): same-source reviewer only — zero added cost.
- Opt-in item (high-stakes): same-source + different-family × ≤ cap rounds + reconciliation.
- Deterministic stages, author, research: unchanged (same-source) except the opt-in research-tier routing (Phase 3, P3-1).

Note (ADR #42 / #41): `--budget-usd` is a runaway breaker, not an accounting figure — for non-Anthropic backends the CLI's `total_cost_usd` is structurally fictional (the API returns tokens, not price). It defaults to 4.0 (headroom under the global 5.0 cap); the reliable provider-independent bounds are the CLI's turn limit + `step_cap_S`. A review that still trips the cap DEGRADES (`degraded:true`, persisted `hetero-degraded-error_max_budget_usd` fingerprint), not rewrites.

## Out of scope

- different-family as the PRIMARY reviewer (rejected — it would drop the reliability + cost floor; ADR #40 (b) Rejected).
- cap-hit silent-pick ("timeout → trust same-source") — rejected; cap-hit escalates to human (ADR #40 Rejected (f)).
- The inner-ring Coder as a different-family candidate before the reviewer + research tiers are proven.
