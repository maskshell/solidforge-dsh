---
status: proposal (Phase 0 COMPLETE — PROCEED to Phase 1; see §6 Phase 0 RESULT)
anchors:
  - ADR #40 (the decision)
  - ADR #38 (异源 orthogonal axis)
  - ADR #39 (inline bookkeeping — closed from outside by the wrapper)
  - docs/tdd-improvement-proposals.md (same-source layer P1-P5, landed in 3f820f9)
---

# Heterogeneous-source (异源) orchestration proposal

> **Status: PROPOSAL — Phase 0 (measurement gate) has NOT run.** Do not implement past Phase 0 until it proves BOTH (a) 异源 incremental value over same-source AND (b) cross-family tool-call reliability. The decision is ADR #40; this doc is the operational plan.

## 1. Goal & constraints

- **Goal**: let the convergence loop run a **per-stage heterogeneous adversarial review** — a different model family (异源) as an additive second opinion on the same-source reviewer — operationalizing ADR #38's orthogonal 异源 axis without waiting for mutation testing.
- **Why additive, not substitutive**: 异源 raises the ceiling without dropping the floor. The same-source reviewer (ADR #16) stays PRIMARY and always runs; 异源 is opt-in, on high-stakes items only. Dropping same-source would forfeit the reliability floor (异源 non-Claude backends carry tool-call risk) and the cost floor.
- **Verified mechanical facts** (anchor the design — do not re-derive):
  - Claude Code provider config is **process-level**: `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`. The built-in Agent tool's `model` param is a **tier enum** (`haiku`/`sonnet`/`opus`/`fable`) with NO per-call `base_url`/`api_key`/`env` → an in-process subagent **cannot** cross providers.
  - This session proves multi-provider-via-Anthropic-compatible-endpoint works (BigModel GLM-5.2 + tier remapping).
  - Non-interactive CC (verified v2.1.197) is a **structured programmatic agent surface**: `--output-format json --json-schema` (typed return), `--input-format stream-json --include-hook-events` (streaming + gate observability), `--settings`/`--model`/`--agents` (per-process config), `--bg` + `claude agents` (background-agent primitive), `--max-budget-usd`/`--fallback-model`.
- **Rejected substrates** (do not re-litigate — see ADR #40 Rejected): custom Agent SDK harness (strands skills); global LiteLLM as primary (unnecessary — kept as fallback); built-in tier routing (cannot cross providers); model-as-tool as primary (loses agent capability — kept as degraded fallback); single-round 异源 (rarely converges); cap-hit silent-pick (defeats the purpose).

## 2. Architecture: non-interactive CC wrapper as the 异源 layer

```text
交互式 Claude Code (orchestrator, 主 provider = GLM via BigModel, 不变)
   │  外环 / 异源阶段: 调 wrapper 工具
   ▼
infra/scripts/hetero_review.py  (thin bash/python wrapper)
   │  per-role profile:  --settings profiles/<backend>.json --model <alias>
   │  structured return: --output-format json --json-schema <findings-schema>
   │  gate observable:  --include-hook-events  (drives loop_state — closes ADR #39)
   │  cost breaker:     --max-budget-usd
   │  session:          --no-session-persistence (default stateless per invocation — ADR #40(h))
   ▼
非交互 CC 子进程 (independent env → independent provider; 异源 reasoning happens here)
   │  inherits: SKILL.md / hooks / Skills / MCP  (skill substrate NOT stranded)
   │  NOTE: tool-call reliability of the non-Claude backend is a Phase 0 gate, not assumed (Morph caveat)
   ▼
DeepSeek v4 pro / flash / GLM-4.7 / …  (routed per role)
```

The wrapper owns the debate loop, the cap, the reconciliation, and the `loop_state` driving. The orchestrator (interactive CC) stays on its primary provider unchanged.

## 3. Routing policy (per stage)

| Stage | Mode | Provider (example) | Always? | Role |
| --- | --- | --- | --- | --- |
| author (main orchestrator) | interactive CC, unchanged | GLM 5.2 (BigModel) | yes | deep reasoning + format-reliable; no added risk |
| adversarial review (同源 / same-source) | in-process / interactive | GLM (primary) | **yes (primary)** | fast, cheap, Claude-grade tool discipline, reliable floor |
| adversarial review (异源 / hetero-source) | non-interactive subprocess | DeepSeek v4 pro | **opt-in (high-stakes)** | adversarial second opinion; cross-family blind-spot check |
| research (researcher / Explore) | non-interactive or tier | DeepSeek flash / GLM-4.7 | as needed | fan-out; cost-dominated |
| normalize / constraints-check / freeze / fast_gate / arch-contract | deterministic code | — (no model) | — | model-independent |
| inner-ring Coder (GREEN) | same-source (default) | GLM | yes | highest tool-call-reliability risk (Morph); consider异源 LAST |

异源 priority: **reviewer > research > Coder**. The reviewer is the safest 异源 entry point (read-only + structured findings, narrow tool surface, tolerable偶发 malformation).

## 4. Multi-round adversarial debate (the realistic pattern)

A single 异源 round rarely resolves disagreement. The reviewer stage is a **capped multi-round debate**, not a one-shot second opinion.

### Loop

```text
round 0: 同源 reviewer (primary) reviews artifact              → findings A
round 1: 异源 reviewer reviews (artifact + A), adversarial      → findings B  (agree / new / rebut)
round 2: 同源 reviews (artifact + A + B), respond or concede    → findings A'
round 3: 异源 reviews (... + A')                                 → findings B'
… alternate until a termination condition fires
```

The 异源 prompt is **adversarial** ("find what the primary missed or got wrong", NOT "validate A"). Without this, the loop degenerates into rubber-stamping — the main failure mode; measure it in Phase 0.

### Termination (three conditions, any one fires)

1. **Converge**: ≥1 round with zero new findings AND no open disagreement → adopt merged findings.
2. **No-movement early-exit**: the same disagreement fingerprint persists ≥2 rounds (both sides repeating) → irreducible, stop early, do not waste the remaining cap. Reuses `loop_state`'s thrashing-fingerprint breaker.
3. **Cap**: `max_adversarial_rounds` reached without convergence → cap-hit policy.

### Cap (the bound)

- `max_adversarial_rounds` = the maximum number of **异源 invocations** (NOT total rounds). The same-source primary always responds after each 异源 challenge, so the same-source final-word is guaranteed **by construction** — no parity dependency on an odd/even cap (the earlier "odd cap" framing was underspecified; 异源-review Round 1, Important).
- `cap=0` = opt-out (异源 does not run); `cap=1` = one 异源 challenge + one same-source response (the minimum for any 异源); default conservative (e.g. 2); per-item overridable (blueprint risk field / plan_queue flag).
- `--max-budget-usd` on each 异源 subprocess — hard cost breaker, prevents runaway.

### Cap-hit policy (load-bearing — do NOT silently pick)

On cap exhaustion without convergence:

- **Escalate to human** (outcome axis) — irreducible disagreement is human territory.
- Record outer verdict `adversarial-stalemate` (new value) in `outer_verdicts[]`.
- **NEVER** "timeout → trust same-source" — that spends 异源 cost and discards it on timeout. This is a documented rejection (ADR #40 Rejected (f)), not an implementation liberty.

### Reconciliation (when the debate does converge)

| Findings | Action |
| --- | --- |
| both 同源 + 异源 report | high-confidence; adopt |
| 同源 only | adopt (primary status) |
| 异源 only | **strong signal** (cross-family independent find = same-source blind spot exposed); escalate for adjudication |
| neither | pass |

### Cost model

- **Default item** (low/medium risk): same-source reviewer only — zero added cost, identical to today.
- **Opt-in item** (high-stakes): same-source + 异源 × ≤ cap rounds + reconciliation — up to ~2×cap model calls.
- Deterministic stages, author, research: unchanged (same-source).
- The multi-round cost **raises the opt-in bar** — 异源 debate is for genuinely high-stakes work, not every item.

## 5. Integration with existing skills (extend, NOT replace)

- **Do not strand**: parallel-dev / blueprint-crafting SKILL.md, hooks, deterministic infra stay — the non-interactive subprocess inherits them.
- **Extend**: the reviewer agent gains a 异源 path (calls the wrapper); the same-source path remains primary and default.
- **ADR #40** is the decision anchor; this doc is the plan.
- **Rule-5 enumeration ripple** (when Phase 2 lands): `install.md` (异源 reviewer config), `maturity.md` caveat 13 (异源 partial defense now landed — update from "future"), `convergent-loop.md` reviewer prompt (异源 option + the `adversarial-stalemate` verdict), reviewer agent defs (异源 path).

## 6. Phases (validation-gated)

### Phase 0 — measurement gate (DECIDES whether to proceed)

Benchmark N real diffs (e.g. commits `3f820f9` / `6fccb05`, or synthetic) each through:

1. same-source reviewer (GLM);
2. 异源 reviewer (DeepSeek via non-interactive CC, single round);
3. a 2-3 item sub-set through the multi-round debate (cap=3).

Measure:

- **异源 incremental value**: does 异源 catch materially different issues than same-source? (decides (a))
- **Cross-family tool-call reliability**: does the DeepSeek subprocess complete cleanly, or hit tool-call malformation? (decides (b) — the Morph caveat)
- **Convergence vs thrash rate** in multi-round: informs the default cap value.

**Gate**: proceed to Phase 1 iff (a) 异源 catches materially different issues AND (b) tool-call reliability is above threshold. Else stop, stay same-source, and record 异源 as an honest unresolved gap (ADR #38, rule 3) — or fall back to model-as-tool (degraded, no tool surface).

**"Materially different" rubric** (异源-review Round 1, Suggestion — removes the measurer-decides conflict): a finding is materially different iff it identifies a defect category (correctness/security/performance/maintainability) OR a code/doc location NOT covered by the same-source reviewer's findings. Rephrased same-defect-on-same-location is NOT materially different.

**Dogfood status**: the adversarial review run while writing this proposal IS a Phase 0 data point (n=1) — it measures 异源 incremental value + tool-call reliability on a single real artifact. It is NOT the full N-item benchmark. The full gate needs N≥3 diverse items before trusting the异源 value judgment.

### Phase 0 RESULT (completed — PROCEED, with refined understanding)

Ran n=3 proper-protocol items (same-source-primary-first via independent GLM headless subprocess, then 异源 DeepSeek) + the cache probe.

| Measurement | Result | Verdict |
| --- | --- | --- |
| 异源 incremental value | item 1 (doc/ADR #39): 异源 1 unique / GLM 3. item 2 (code/coverage gate): 异源 0 unique / GLM 3 (BOTH found the same Critical). item 3 (mixed/AC-mapping): 异源 4 unique / GLM 4 unique. **5 unique material 异源 findings across 2/3 items.** | PASS — but COMPLEMENTARY, not superior |
| Cross-family tool-call reliability | 12/12 clean invocations (6 dogfood + 6 Phase-0); DeepSeek wielded Read/Grep/Glob/**Bash** reliably incl. code-review (ran `go tool cover`, `git show`, grep). | PASS — Morph caveat did NOT manifest |
| Convergence | 2/2 dogfood debates converged in cap=2. | PASS |
| Cache support | DeepSeek **AUTO-CACHES** via its own Context Caching (dashboard: ~99% hit rate; `input_cache_hit_tokens` massively exceeds `input_cache_miss_tokens`). The Phase-0 probe's `cache_creation=0`/`cache_read=0` was a **REPORTING GAP** (Anthropic-format usage fields ≠ DeepSeek dashboard), not a caching gap. Claude Code's `cache_control` markers are redundant — DeepSeek caches automatically on prefix similarity, no explicit markers needed. | CACHE ACTIVE — stateless benefits from prefix amortization |

**Gate verdict: PROCEED to Phase 1**, with these load-bearing refinements:

1. **异源 value is COMPLEMENTARY, not superior.** It catches a different *category* (enforcement-gaps / silent-failure-modes / diagnostic-UX) that same-source misses; same-source catches rule-10 / mechanical / doc-quality that 异源 misses. Both contribute; neither dominates. The reconciliation "both-report → high-confidence" rule is itself a value: even when 异源 adds no *unique* finding (item 2), independent cross-family agreement on a Critical is high-confidence confirmation.
2. **异源 value is ITEM-DEPENDENT** — high on doc/spec/mixed (item 3: 4 unique), low/zero on pure-code (item 2: 0 unique; mechanical bugs dominate and same-source catches them). **Opt-in scoping favors doc/spec/mixed high-stakes items.**
3. **DeepSeek auto-caches** (corrected post-Phase-0 — the earlier "no cache" conclusion was a measurement-surface error: the probe read Anthropic-format `cache_creation/read_input_tokens` fields which DeepSeek reports as 0, but DeepSeek's own dashboard shows ~99% cache-hit rate via its Context Caching). Stateless default benefits from prefix amortization. Claude Code's `total_cost_usd` may over-report (basing cost on Anthropic `input_tokens` pricing, not DeepSeek's cache-aware billing).
4. **The earlier dogfood counts (10, 11) were inflated** by author-self-review (weak same-source). With independent same-source, 异源's per-item unique contribution is ~0–4 (complementary), not 10+.
5. **The independent-same-source-primary leg is load-bearing** — 异源 value measured against author-self-review is an upper bound (Critical-2 of the dogfood). Phase 0 used independent GLM headless subprocesses, giving honest numbers.

**Side output — real defects found** (n=3 review doubled as a real review of commit `3f820f9`; both sources agreed → high-confidence): `parse_coverage_go` regex never matches real `go tool cover -func` output (Critical); `_run_coverage_gate` unconditional sweep when threshold=None; intent-blueprint heading ≠ parser regex; plus several Important. These are flagged for a follow-up fix commit (separate from this proposal).

### Phase 1 — minimal 异源 reviewer (core landing)

- `infra/scripts/hetero_review.py`: given diff + blueprint ref + findings-schema, spawn `claude -p --settings profiles/<backend>.json --model <alias> --output-format json --json-schema <findings-schema> --permission-mode bypassPermissions --no-session-persistence -p "<prompt>"`, capture typed findings. (`--permission-mode` choices verified v2.1.197: `acceptEdits`/`auto`/`bypassPermissions`/`default`/`dontAsk`/`plan`.)
- `infra/scripts/profiles/<backend>.json`: the 异源 provider settings.
- findings schema: reuse `violation_log` schema, or define a review-findings schema.
- **Wrapper drives `loop_state` from day one** (ADR #39 — moved here from Phase 3 after 异源-review Round 1, Important): the wrapper calls `bump-iteration`/`gate-fail`/`record-outer` around the subprocess; `--include-hook-events` observes the gates. Do NOT defer — Phase 1-2 run records must be truthful, not knowingly `steps.inner=0`.
- **Schema delta** (异源-review Round 1, Critical): add `adversarial-stalemate` to the `outer_verdict` enum in `run-record.schema.json` + the `record-outer` argparse `choices` (one line each). This is a minimal, acknowledged schema addition (the earlier "no schema change" framing was wrong).
- Wire as a tool the reviewer agent calls, OR as the outer-ring spawn in the convergence loop.
- **Dogfood**: run it as the outer ring on the next real skill change; compare findings to same-source. NOTE: a faithful dogfood runs the SAME-SOURCE primary first (recorded), THEN 异源 — the writing of this proposal ran 异源 only (n=1 probe), which is a Phase 0 data point but not the full additive flow.

### Phase 2 — codify (rules 5 / 6)

- ADR #40 is already the anchor (land it if not yet).
- `references/model-routing.md`: the per-stage routing policy (§3 table as the source).
- Rule-5 ripple (§5).
- Multi-round debate + cap + `adversarial-stalemate` verdict wired into the wrapper.

### Phase 3 — expand

- research-tier routing (haiku slot → cheap backend).
- per-item routing in plan-driven mode (plan_queue wrapper picks profile per item).
- (ADR #39 inner-ring bookkeeping from the wrapper landed in Phase 1, not here.)

### No Phase 4

The rejected custom-Agent-SDK-harness path stays rejected (ADR #40; the SWOT showed non-interactive CC dominates for this workspace). If non-interactive CC + the LiteLLM fallback (§7 row 2) prove insufficient at Phase 0-3 scale, revisit the ADR #40 decision then — do not pre-plan a harness. Documenting the rejected path in ADR #40 is sufficient.

## 7. Risks & exit conditions

| Risk | Trigger | Exit action |
| --- | --- | --- |
| Morph caveat bites (异源 tool-call flakiness) | Phase 0 reliability < threshold | reviewer stays same-source; accept ADR #38 gap (rule 3); or degrade to model-as-tool (single prompt, no tool surface) |
| Process-per-agent overhead unacceptable | Phase 3 long-plan latency/memory | switch to LiteLLM (one process, tier routing) as the fallback substrate |
| Non-interactive CC flag drift | a CC upgrade breaks the wrapper | pin version; document the flag surface used; `--bare` as floor |
| 异源 findings overlap heavily with same-source | Phase 0 shows no material增量 | 异源 not worth the cost; stay same-source; record as ADR #38 honest conclusion |
| Rubber-stamp degeneration | 异源 concedes without real challenge | tighten the adversarial prompt; measure in Phase 0; if persistent, 异源 adds no value — exit |
| Cap-hit rate too high | most opt-in items stall at cap | default cap too high OR reviewers too far apart; lower cap, raise opt-in bar, or re-evaluate 异源 value |

## 8. Immediate next step

**Phase 0 measurement script** is the gate. Two data points decide everything: 异源 incremental value + cross-family tool-call reliability (+ convergence/thrash rate for the default cap).

The Phase 0 script itself dogfoods ADR #39: it drives `loop_state` (`bump-iteration` / `record-outer`) truthfully — Phase 0 may inline these calls directly (the production wrapper `hetero_review.py` is a Phase 1 deliverable; Phase 0 need not depend on it), and exercises the non-interactive-CC structured-return path end-to-end.
