# cross-source-review — Iteration Plan (Phase A)

> Based on `docs/proposal.md` (SUBSTANTIVE-CONVERGED, human-accepted 2026-07-07). This
> plan is the **execution blueprint** for Phase A. Structured like `blueprint-crafting`'s
> own plan-driven mode: complexity tier + dependency edges + **validation gate** (not
> calendar duration) = the only "done" criterion.
>
> **Authority chain**: `proposal.md` = authoritative design (master); this
> `iteration-plan.md` = execution blueprint (on conflict, **proposal.md wins**). The
> proposal's §9 decisions are locked inputs; this plan shapes them into work-items, it
> does not re-debate them. `proposal.convergence.md` is a sibling process-log (FX-## evidence), not an authority.

## 0. Background and scope

- Current state: proposal frozen + cross-source-reviewed (`proposal.convergence.md`); **no
  `SKILL.md`, no schemas, no agents, no substrate, no self-gates**.
- Scope (Phase A): zero → a doc-domain-native same-family+different-family convergence engine that drives
  cross-source multi-round review to **substantive convergence** on doc-shaped artifacts.
  bc stays pure (process-axis, same-family plan-reviewer); the new skill owns different-family for docs and
  may be called by bc for a different-family pass on a bc draft.
- Phase A **copies** the different-family substrate pattern from `parallel-development`'s
  `hetero_review.py` (workspace rule 7 — copy-patterns-not-code; NOT extract). Phase B
  (B1 import / B2 copy / B3 shared-lib) is **out of scope** — evidence-gated, decided later.

## 1. Estimation gauge (no day counts)

| Dimension | Meaning | Use |
| --- | --- | --- |
| **Complexity tier** S/M/L/XL | intrinsic difficulty: substrate novelty × convergence-semantics risk × integration surface | per-iteration risk + gate density |
| **Dependency edge** | "X must exist before Y" | execution order + critical path |
| **Validation gate** | an objective "done" criterion: schema validates / shape-contract gate green / dogfood converges | the unit of progress — no gate, no delivery |

Tier definitions: S = single artifact, few edge cases; M = several subtleties; L = many subtleties stacked (substrate port + semantics); XL = broad coverage + high integration + hard semantics. No XL iterations in Phase A.

## 2. Overview: iterations, complexity, dependencies, gates

| ID | Iteration | Complexity | Deps | Key validation gate (summary) |
| --- | --- | --- | --- | --- |
| CSR-I0 | scaffold + `SKILL.md` + activation/scope-guard | M | — | `SKILL.md` loadable; Scope Guard routes code→`parallel-development` / spec-authoring→`blueprint-crafting`; Q4 explicit-invocation noted (3-way `trigger_check` DEFERRED) |
| CSR-I1 | schemas (doc-findings + convergence-record) | M | CSR-I0 | both JSON schemas validate; doc-findings `kind` enum = the 6 Q2 kinds; `severity` keeps bc's `coverage` level; convergence-record fields name-aligned to `loop_state` run-record |
| CSR-I2 | same-family leg: skill-local doc-reviewer agent | M | CSR-I1 | agent defined (fresh-context, read-only, barred from outcome-axis); returns doc-findings shape; NOT `plan-reviewer` (Q5/FX-05) |
| CSR-I3 | different-family substrate: copy-pattern `hetero_review.py`, doc-adapted | L | CSR-I1 | spawns DeepSeek via raw `claude -p` with a DOC prompt + doc schema; no `--diff`/`--blueprint` hard-require; fence-aware parse + substrate-error DEGRADE + multi-provider merge carry over |
| CSR-I4 | convergence loop driver (owns the §3 pluggable-seam contract) | L | CSR-I2, CSR-I3 | drives a full same-family↔different-family cross-round; caps by artifact size; substantive-convergence BOTH prongs (no-new-Blocker AND core-claims-coverage); findings-schema is a parameter + same-family leg is a callback; emits a convergence-record |
| CSR-I5 | self-gates (Q6) + standard set | L | CSR-I4 | 3 skill-specific gates green (dogfood own loop on own `SKILL.md` [skips gracefully w/o tokens]; findings shape-contract; offline convergence-policy incl. core-claims-coverage) PLUS standard (`disconnect_check` / `plugin_layout` / `lint_self`) |
| CSR-I6 | dogfood + 质量稳定 gate (Q7) | M–L | CSR-I5 | N ≥ 3 real docs, ≥ 1 long-doc (cap=5–7) substantive-converged, + own `SKILL.md`; measured convergence profile recorded |
| — | **Phase-A acceptance gate** | | CSR-I6 | see §6 |

> **First package**: CSR-I0 + CSR-I1 together (scaffold + schema contract are the
> foundation). After CSR-I1, CSR-I2 (same-family) and CSR-I3 (different-family) parallelize. CSR-I4 closes
> on both legs; CSR-I5 + CSR-I6 follow sequentially (gates need the driver; dogfood needs
> the gates).

## 3. Foundation layer (CSR-I0–CSR-I1)

### CSR-I0 scaffold + `SKILL.md` + activation/scope-guard — M

- **Goal**: a loadable skill skeleton with the correct scope + an honest activation story.
- **Deliverables**: `cross-source-review/SKILL.md` (description declares the doc-convergence scope — same-family+different-family cross multi-round review to substantive convergence; Scope Guard routes code→`parallel-development`, spec-authoring→`blueprint-crafting`; notes Q4 explicit-invocation as the Phase-A activation mode, with the 3-way `trigger_check` partition DEFERRED to maturation).
- **Done when**: `SKILL.md` is loadable; Scope Guard emits the correct routing hints; the Q4 explicit-invocation deferral is stated honestly (not a claim of auto-routing).
- **Basis**: proposal §2 (non-goals), §6 (layering), §9 Q4.

### CSR-I1 schemas (doc-findings + convergence-record) — M

- **Goal**: the two data contracts the legs and the driver exchange.
- **Deliverables**:
  - `infra/schemas/doc-findings.schema.json` — generalized from `blueprint-crafting`'s `review-findings.schema.json` (fields `defect_id` / `severity` / `kind` / `location` / `evidence` / `suggestion`); v1 `kind` enum: `contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` / `citation-error` / `coverage-gap`; `severity` ∈ {blocker, warning, **coverage**} — the `coverage` severity is PRESERVED from bc (it is the reviewer's honest disclosure "could not verify X", required by workspace rule 3; it is DISTINCT from the `coverage-gap` KIND, which is a defect in the artifact).
  - `infra/schemas/convergence-record.schema.json` — minimal (rounds, per-round findings-count, trend, `substantive_converged`, coverage, stalemate); field NAMES aligned to `loop_state`'s run-record (iterations / verdict / findings) for Phase-B map-ability; NO code dependency on `loop_state`.
- **Done when**: both schemas pass the stdlib JSON-schema validator; the doc-findings `kind` enum is exactly the 6 Q2 kinds AND `severity` includes `coverage`; the convergence-record carries the `substantive_converged` boolean.
- **Basis**: proposal §9 Q2, Q3; plan-reviewer novel-3 (do not drop the `coverage` severity).

## 4. The two review legs (CSR-I2–CSR-I3)

### CSR-I2 same-family leg: skill-local doc-reviewer agent — M

- **Goal**: the same-family adversarial reviewer (fresh-context, no author bias).
- **Deliverables**: a skill-local agent (e.g. `agents/doc-reviewer.agent.md`) — fresh independent context; `tools: Read, Grep, Glob` (read-only at the tool layer); hunts the Q2 `kind` enum; verifies each claim against source; **barred from outcome-axis** (does not judge whether the artifact is "right"); returns a doc-findings object. It is NOT `blueprint-crafting`'s `plan-reviewer` — that agent's prompt is plan-MODEL-shaped (`item_id` / `dod_ref` / authority-chain framing), not generically doc-shaped.
- **Done when**: the agent is defined; read-only is enforced at the tool layer; on a fixture doc with a planted contradiction it returns a blocker with evidence quoting source.
- **Basis**: proposal §3 (same-family leg), §9 Q5; FX-05. The bootstrap same-family leg (this proposal's own review) already used a custom fresh-context doc reviewer — productize that.

### CSR-I3 different-family substrate: copy-pattern `hetero_review.py`, doc-adapted — L

- **Goal**: the cross-family adversarial leg, domain-decoupled from code review.
- **Deliverables**: a wrapper that copy-PATTERNS `parallel-development`'s `infra/scripts/hetero_review.py` — the FLAG-SURFACE MANIFEST, the provider-template + token-injection (`_materialize_profile`), the fence-aware JSON parse (`_extract_json_object` / `_parse_json_return`), the CC substrate-error DEGRADE handling (`DEGRADABLE_CC_SUBTYPES` / `_parse_cc_substrate_error`, ADR #41), and the multi-provider merge (the `per_provider` loop) — but with a **DOC** adversarial prompt (the Q2 enum) + the doc-findings schema, and **no `--diff`/`--blueprint` hard-requirement** (a doc has no diff/blueprint). Copy, NOT import (rule 7).
- **Done when**: the wrapper spawns DeepSeek via raw `claude -p` on a fixture doc and returns a parsed doc-findings object; the substrate-error DEGRADE path (budget/turn cap) is preserved; a `--dry-run` offline path exists for the self-gate.
- **Phase-A compatibility constraint (proposal §5, F3)**: the copy preserves the function-signature CONTRACT of its `hetero_review.py` source (interface-level, not implementation); intentional divergences are logged in a divergence note so the Phase-B B1/B3 decision stays data-driven, not invalidated by silent drift.
- **Basis**: proposal §3 (different-family substrate), §5 (Phase-A compat), §8 (bootstrap used exactly this raw-substrate pattern); `hetero_review.py` is the pattern source.

## 5. Convergence driver + self-gates + dogfood (CSR-I4–CSR-I6)

### CSR-I4 convergence loop driver (owns the §3 pluggable-seam contract) — L

- **Goal**: orchestrate same-family ↔ different-family multi-round debate to substantive convergence.
- **Deliverables**: a driver (script + the SKILL.md workflow) that, given an artifact + optional authoritative reference, alternates the same-family leg and the different-family leg (each fed the other's latest findings so it hunts the gap), with:
  - **caps by artifact size** — short cap=2, long doc cap=5–7 (pd ADR #40 (d) for the short default; long-doc cap is doc-specific).
  - **substantive convergence, BOTH prongs (proposal §3)** — (a) the core claims are coverage-verified AND (b) no new Blocker for ≥2 rounds. Advisory findings never block (rule 4).
  - **per-round reconciliation table** (proposal §3) — both-report→adopt; same-family-only→adopt; different-family-only→escalate; neither→pass; DEGRADED→adopt same-family.
  - **cap-hit → human**, never silent-pick (pd ADR #40 (e)); **adversarial-stalemate** on persistent Blocker disagreement; **do not blind-trust either source** (verify claims against source independently).
  - **pluggable-seam contract (proposal §3 "MUST get right")** — the driver exposes `findings-schema` as a parameter (default doc-shaped; a future code-shaped caller passes `violation-log`) and the same-family leg as a callback (defaulting to the CSR-I2 agent). This is OWNED by CSR-I4, not split implicitly across CSR-I3/CSR-I4.
  - emits a **convergence-record** (CSR-I1 schema).
- **Done when**: on a fixture doc with a planted blocker, the driver runs ≥1 cross-round, reconciles, and emits an honest convergence-record (`substantive_converged` reflects whether the blocker was resolved) — the no-new-Blocker prong; AND on a fixture doc with NO blocker but an uncovered core claim, the driver yields `substantive_converged=false` — the core-claims-coverage prong.
- **Basis**: proposal §3 (convergence POLICY + reconciliation table + pluggable seams); this proposal's own convergence loop is the reference behavior; plan-reviewer novel-1 (own the pluggable seam), novel-5 (operationalize both prongs).

### CSR-I5 self-gates (Q6) + standard set — L

- **Goal**: the skill's deterministic self-checks (workspace rule 1 — a skill's own self-gates are the definition of done).
- **Deliverables** — three skill-SPECIFIC gates on top of the standard set every skill inherits:
  1. **dogfood** — the skill runs its own convergence loop on its own `SKILL.md` [rule 1]. **Skips gracefully when no API tokens are present** (the different-family leg cannot run); a recorded dogfood log under `docs/` substitutes in CI / fresh-clone (workspace rule 1: tests skip when external tools are absent — the skip is honest, never a silent green).
  2. **findings shape-contract gate** — every leg/driver emit path produces a doc-findings-schema-valid object [mirror `parallel-development`'s `adapter_shape_check.py`].
  3. **offline convergence-policy gate** — caps + stalemate + reconcile round-trip on dry-run fixtures [mirror `parallel-development`'s `hetero_review_wiring.py`]; ALSO exercises the core-claims-coverage prong (a no-blocker-but-uncovered-core-claim fixture must yield `substantive_converged=false`).
  - PLUS the standard set: `disconnect_check.py` (structure + loading-chain), `plugin_layout.py` (plugin.json + hooks.json + agents well-formed), `lint_self.py` (lints own infra).
- **Done when**: all gates green (skill-specific + standard); each gate is self-contained (rule 7); gate (1)'s skip-when-no-token behavior is defined.
- **Basis**: proposal §9 Q6; workspace rule 1; plan-reviewer novel-4 (gate-1 skip path), novel-5 (core-claims fixture in gate 3).

### CSR-I6 dogfood + 质量稳定 gate (Q7) — M–L

- **Goal**: prove the skill on real artifacts before Phase B is even considered.
- **Deliverables**: run the skill on N ≥ 3 real doc artifacts — at least ONE a long doc exercising the cap=5–7 path, and ONE being the skill's own `SKILL.md` (one OF the N, not additional) — and record a measured convergence profile (caps used, substantive-converged verdicts, honest coverage notes).
- **Done when**: N ≥ 3 runs recorded; ≥ 1 long-doc reached substantive convergence; the convergence profile is persisted (e.g. a dogfood log under `docs/`).
- **Basis**: proposal §5 (质量稳定 gate), §9 Q7.

## 6. Phase-A acceptance gate (after CSR-I6)

- The skill drives a same-family+different-family cross-round to substantive convergence on a real doc (not a demo), passing BOTH prongs (no-new-Blocker AND core-claims-coverage).
- All self-gates green (skill-specific + standard); gate (1) skips gracefully when no API tokens.
- The 质量稳定 N ≥ 3 dogfood (incl. one long-doc + own `SKILL.md`) is recorded with a measured convergence profile.
- The doc-findings + convergence-record schemas validate (severity keeps `coverage`); the substrate's function-signature contract with `hetero_review.py` is documented (Phase-B viability).
- **Doc-audit pass (proposal §7 rule 5)**: `USER_GUIDE.md` (the Mine → converge → bc → pd pipeline gains a step) and bc/pd Scope Guard mutual-routing hints updated for cross-source-review.
- bc/pd CORE LOGIC is UNCHANGED (Phase A does not touch it).

## 7. Dependencies and parallelism (DAG)

```text
CSR-I0 scaffold ─▶ CSR-I1 schemas ─┬─▶ CSR-I2 same-family leg ─┐
                                    │                     │
                                    └─▶ CSR-I3 different-family substrate ─┤
                                                          ▼
                                          CSR-I4 convergence driver ◀── (CSR-I2 + CSR-I3)
                                                          ▼
                                          CSR-I5 self-gates
                                                          ▼
                                          CSR-I6 dogfood + 质量稳定
                                                          ▼
                                          Phase-A acceptance gate
```

**Parallel fan-out**: after CSR-I1, CSR-I2 and CSR-I3 run in parallel (independent legs). CSR-I4 depends on both. CSR-I5 → CSR-I6 sequential.

## 8. Risks and mitigations

| Risk | Iteration | Mitigation |
| --- | --- | --- |
| activation collision with bc/pd on "review"-type requests | CSR-I0 | Q4 explicit-invocation only in Phase A (defers the collision risk); Scope Guard ships anyway |
| doc-findings `kind` enum drifts from bc's review-findings; `coverage` severity dropped | CSR-I1 | Q2 locks the 6 kinds; severity keeps bc's {blocker,warning,coverage}; `coverage` severity ≠ `coverage-gap` kind (novel-3) |
| `plan-reviewer` wrongly reused as the same-family leg | CSR-I2 | Q5/FX-05: skill-local doc-reviewer; plan-reviewer is plan-model-shaped |
| substrate copy silently drifts from `hetero_review.py`, breaking Phase-B B1/B3 | CSR-I3 | proposal §5 Phase-A compat constraint: preserve function-signature contract + divergence log (F3) |
| pluggable-seam contract has no owner → Phase B is a rewrite | CSR-I4 | CSR-I4 OWNS the seam: findings-schema param + same-family-leg callback (novel-1) |
| convergence driver chases zero-finding, or misses the coverage prong | CSR-I4 | substantive-convergence BOTH prongs + a core-claims-coverage fixture (novel-5); caps |
| dogfood gate (1) cannot run in CI / no-token | CSR-I5 | gate (1) skips gracefully w/o tokens; recorded dogfood log substitutes (novel-4) |
| a leg's finding shape is malformed | CSR-I5 | findings shape-contract gate (mirror `adapter_shape_check`) |
| different-family substrate-error (budget/turn cap) masked as clean pass | CSR-I3/CSR-I5 | carry over `hetero_review.py`'s DEGRADE handling (ADR #41); offline convergence-policy gate exercises it |
| rule-5 doc-audit ripple forgotten | CSR-I0 / §10 | cross-cutting doc-audit task + acceptance-gate criterion (USER_GUIDE + bc/pd Scope Guard hints) (novel-2) |
| dogfood N too small to validate long-doc convergence | CSR-I6 | Q7: ≥ 1 long-doc (cap=5–7) is required, not optional |

## 9. Out of scope (Phase A)

- Phase B in any form: B1 import, B2 pattern-refresh, B3 shared-library (evidence-gated; decided after the 质量稳定 gate, with an ADR — proposal §5).
- Any change to bc/pd **CORE LOGIC**: pd's `hetero_review.py` / `loop_state.py` / `model-routing.md` / the `convergent-loop.md` different-family section; bc's convergence operators. This is NOT violated by the **doc-audit routing-hint updates** to bc/pd `SKILL.md` Scope Guards (proposal §7 rule 5 — those are doc edits, in scope, see §10).
- 3-way `trigger_check` activation partition (Q4 — deferred to maturation).
- Outcome-axis judgment (is the artifact "right") — human only (proposal §2).

## 10. Cross-cutting tasks (across iterations)

| Task | Starts at | Note | Workspace rule |
| --- | --- | --- | --- |
| dogfooding self-check | CSR-I5 | the skill runs its own convergence loop on its own `SKILL.md`; skips gracefully w/o API tokens | rule 1 |
| copy-patterns-not-code | CSR-I3 | substrate copied from `hetero_review.py`, NOT imported; signature contract preserved + divergence logged | rule 7 |
| ADR log | CSR-I1 | `design-decisions.md` for the skill; non-obvious decisions (substantive-convergence doctrine, Phase-B framing, outcome-axis bound, the `coverage`-severity preservation) get an ADR | rule 6 |
| substrate interface-compat tracking | CSR-I3 | divergence log keeps Phase-B B1/B3 data-driven | proposal §5 / F3 |
| honest-coverage discipline | CSR-I4 | never fake green; substrate-error DEGRADE + substantive-converged + `coverage` severity stated honestly | rule 3 / rule 4 |
| **doc-audit (rule-5 ripple)** | CSR-I0 | update `USER_GUIDE.md` (Mine → converge → bc → pd pipeline) + bc/pd Scope Guard mutual-routing hints for cross-source-review | proposal §7 / rule 5 |
