# cross-source-review — design proposal (SUBSTANTIVE-CONVERGED — ACCEPTED 2026-07-07)

> Status: Round 1 cross-loop complete. same-family (9 findings) + different-family (4 findings), ALL revised,
> 0 rejected, 0 outstanding blockers. Core claims cross-verified by BOTH sources.
> Substantive convergence reached per the doc-domain doctrine (this very loop validated
> it: different-family round 1 surfaced only advisory citation-precision findings — chasing
> zero-finding on a doc is the infinite loop the policy warns against). Does NOT meet the
> strict "≥2 Blocker-free rounds" criterion in §3 — round 2 is available if the human
> wants strict confirmation. Not a live skill yet (no `SKILL.md`). Name LOCKED (Q1).
> Convergence trail: `proposal.convergence.md`.

## 1. Problem

Producing a high-quality artifact (a requirements input, a design doc, a wiki page)
needs same-family + different-family LLM cross review over multiple rounds, driven
to SUBSTANTIVE convergence. Today this has no home.

| Need | Owner today | Gap |
| --- | --- | --- |
| high-quality requirements input BEFORE blueprint-crafting | human, ad hoc — `USER_GUIDE.md:30` says "yours to mine" but provides no tool | none |
| different-family (cross-family model) review of a DOC | `parallel-development`'s `hetero_review.py` — coupled to code shape (`violation-log` schema, `loop_state`, `--diff`/`--blueprint` framing, code-shaped adversarial prompt) | not doc-usable |
| DOC-specific convergence POLICY (long-doc cap, doc substantive-convergence judgment) | tacit — in the operator's head; memory `hetero-long-doc-review-convergence` records a 7-round manual run | not codified |
| external doc review (e.g. fedaot wiki) | nothing | none |

Scope note on "not codified": the CODE-review convergence policy IS codified — pd
ADR #40 (c) multi-round debate, (d) cap default, (e) cap-hit-escalates-to-human +
adversarial-stalemate + never-silent-pick. What is NOT codified is the DOC-specific
layer: the long-doc cap=5–7 and the doc substantive-convergence judgment. This skill
codifies that doc-specific layer; it does not re-derive what pd already has.

`blueprint-crafting` (bc) and `parallel-development` (pd) do NOT fill this:

- bc converges an artifact on its PROCESS-AXIS (well-formed: anchors / authority-chain / open-decision-points) using a same-family (same-family, fresh-context) `plan-reviewer` plus a deterministic inner ring. bc is COMPLETE on its own terms. It does not own content truth — OUTCOME-AXIS is human-only (bc §2; bc arch-design §1). bc has NO different-family leg and does not need one to converge.
- pd owns the different-family substrate, but it is code-review-shaped and drives its convergence-loop state machine (`loop_state`). pd is the proven PATTERN source, not a doc-review engine.

## 2. Non-goals (honesty bounds)

- NOT outcome-axis truth. The skill converges PROCESS-AXIS quality of a doc (well-formed, internally consistent, citation-accurate, coverage-complete). Whether the doc captures the RIGHT requirement stays human (bc §2; `USER_GUIDE.md:30`).
- NOT code review. Code-shaped review stays in pd. This skill is doc/content-shaped.
- NOT research gathering. Multi-source web gathering stays in bc's `researcher` + `research_constraints` oracle. This skill REVIEWS; it does not gather.
- NOT a hot-loop gate. Opt-in, manually invoked, outer-ring only (memory `loop-integration-cost`: heavyweight LLM harnesses must not fire per-convergence).

## 3. What the skill owns (Phase A)

A doc-domain-native convergence engine. Owns:

- doc-shaped findings schema — generalized from bc's `infra/schemas/review-findings.schema.json` (fields: `defect_id` / `severity` / `kind` / `location` / `evidence` / `suggestion`); v1 `kind` enum: `contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` / `citation-error` / `coverage-gap`. NOT pd's code-shaped `violation-log` (`file`/`line`/`rule`).
- convergence POLICY, codified (the doc-specific layer; the code layer is pd ADR #40):
  - caps by artifact size. Short artifact cap = 2 (pd ADR #40 (d)); long doc cap = 5–7 (measured in `hetero-long-doc-review-convergence`; doc-specific, not in ADR #40).
  - SUBSTANTIVE convergence, not zero-finding. A persistent adversarial reviewer always finds finer citation flaws; demanding zero findings loops forever (validated by this proposal's own loop — different-family round 1 found only advisory citation-precision findings). Convergence = the core claims are coverage-verified AND no new BLOCKER-class finding appears for ≥2 rounds. Advisory findings never block (rule 4: heuristics are advisory, never Blocker).
  - cap-hit escalates to human, never silent-pick (pd ADR #40 (e) — escalates to human, outcome-axis, adversarial-stalemate, never silent-pick).
  - `adversarial-stalemate` verdict when same-family and different-family persistently disagree on a Blocker (pd ADR #40 (e)).
  - do not blind-trust EITHER source. Verify each round's factual/citation claims against source independently (the Morph caveat cuts both ways).
Per-round reconciliation (when same-family and different-family disagree WITHIN a single round) — mirrors pd ADR #40 (b):

| Findings | Action |
| --- | --- |
| both same-family + different-family report | high-confidence; adopt |
| same-family only | adopt (primary status) |
| different-family only | strong signal (cross-family independent find); escalate for adjudication |
| neither | pass |
| different-family DEGRADED (substrate error) | adopt same-family primary (different-family contributed nothing); degraded flag persisted |

- different-family substrate — copy-PATTERNED from pd's `hetero_review.py`: the FLAG-SURFACE MANIFEST, provider-template + token-injection, fence-aware JSON parse, CC substrate-error DEGRADE handling, multi-provider merge. Copy, NOT import (rule 7; see §5 for why copy-vs-share is a Phase-B judgment, not a fixed rule).

Pluggable seams — the cheap thing Phase A MUST get right so Phase B is not a rewrite:

- substrate is a clean function boundary. Input: artifact + authoritative-reference + findings-schema + same-family-leg-callback. Output: merged findings + a convergence record.
- findings-schema is a parameter (default doc-shaped; a future code-shaped caller passes `violation-log`).
- same-family leg is a callback; DEFAULT is a skill-local same-family doc-reviewer (fresh-context, read-only, barred from outcome-axis). bc's `plan-reviewer` informs the PATTERN but is NOT the default leg — its prompt is plan-MODEL-shaped (`frozen plan-model`, `item_id`/`dod_ref`/authority-chain framing), not generically doc-shaped (Q5, FX-05).
- convergence record is abstract enough to MAP to pd's `loop_state` later (iterations / fingerprints / verdict), without depending on it now.

## 4. What stays put (Phase A does NOT touch)

- bc: unchanged core (process-axis, same-family `plan-reviewer`, deterministic inner ring). bc MAY later CALL this skill for a different-family outer pass on its draft — calling a skill, not importing code. bc's independence is preserved.
- pd: `hetero_review.py`, `loop_state.py`, `model-routing.md`, the `convergent-loop.md` different-family section — all UNCHANGED in Phase A. pd is the pattern source, not a caller yet.

## 5. Phase B — evidence-gated, NOT pre-committed

After Phase A reaches "质量稳定" (operationalized below), decide pd's relationship. THREE
landing points; the Phase-A evidence picks. Note: bc §6 (`design-decisions.md:46`)
states rule 7's copy-not-import "is for small self-contained gates, not for an entire
convergence pipeline" — so for a 400+ line engine, copy-vs-share is a real judgment,
NOT a fixed rule. None of the three is rule-violating by default.

Phase-A compatibility constraint (keeps B1/B3 viable): the substrate copy preserves the
function-signature CONTRACT of its pd source (interface-level, not implementation), and
intentional divergences are logged. Without this, the copy silently drifts from pd's
`hetero_review.py` and B1/B3 become a full re-port rather than a data-driven decision.

| Landing point | What it means | Workspace-rule cost |
| --- | --- | --- |
| B1 import | pd imports the new skill's substrate; pd's `hetero_review.py` becomes a thin code-shaped caller | first cross-skill code dependency; needs an ADR (rule 6) + a version-drift story |
| B2 copy | pd keeps its code-shaped substrate; copies the new skill's proven improvements; diverges by domain | the rule-7 default for small gates; bc §6 flags pipelines as the carve-out |
| B3 shared library | the substrate is extracted to a shared lib both skills import | bc §6's carve-out makes this ARGUABLE for a pipeline-scale engine (not foreclosed); needs an ADR + a shared-dep provisioning story (cf. the rejected "shared detection lib" in pd ADR on nested platforms) |

B2 is the conservative default. B1 and B3 each need a strong, ADR-documented reason
and are decided on Phase-A evidence — NOT pre-committed now.

"质量稳定" gate (operationalized, not vague): the skill dogfoods its own convergence
loop on N ≥ 3 real doc artifacts — at least ONE being a long doc that exercises the
cap=5–7 path (validates substantive-convergence where it is hardest) and ONE being its
own `SKILL.md` (which is one OF the N, not additional to it) — AND its self-gates are
green (the skill-specific set in Q6 PLUS the standard set every skill inherits) AND a
measured convergence profile is recorded (caps used, substantive-converged verdicts,
honest coverage notes). Phase B does not start until this holds.

## 6. Layering

Two invocation sites:

```text
SITE 1 — upstream (primary):
  [raw requirements / doc / wiki page]
          ↓  cross-source-review (same-family + different-family → substantive convergence)
  [converged, cross-source-reviewed artifact + coverage record]
          ↓  feeds
  [blueprint-crafting]  →  [parallel-development]  (implement code; same-family + different-family, code-shaped)

SITE 2 — bc callback (optional outer pass on a bc draft):
  [blueprint-crafting draft]  →  cross-source-review (different-family pass)  →  back to bc
```

External: fedaot wiki review calls cross-source-review DIRECTLY (site 1, no bc/pd
dependency). The external-portability requirement FORCES the Phase-A decoupling from pd
internals — "externally portable" and "not coupled to pd" are the same constraint.

## 7. Workspace-rule implications

- rule 1 (a skill's self-gates are done). The skill's self-test IS running its own convergence loop on its own `SKILL.md`. Mirrors pd dogfooding `hetero_review.py`.
- rule 5 (a capability ripples through ~9+ files). A 3rd skill ripples to `USER_GUIDE.md` (the Mine → converge → bc → pd pipeline gains a step) and both skills' Scope Guards (mutual routing hints). The 3-way activation-boundary partition (extending bc's `trigger_check.py` to cross-source-review) is DEFERRED — Phase A is explicit-invocation only (Q4); it returns when the skill seeks auto-routing. Doc-audit pass required, not optional.
- rule 7 (copy-patterns-not-code). Substrate copied from pd in Phase A; the skill stays independently deployable. bc §6 flags copy-not-import as a small-gate convention, so the Phase-B copy-vs-share choice for a pipeline-scale engine is a judgment, not a rule (§5).
- rule 6 (ADR for non-obvious decisions). The §5 B1/B2/B3 choice, the substantive-convergence-vs-zero-finding policy, and the outcome-axis honesty bound all warrant ADRs.
- `loop-integration-cost`. Opt-in outer-ring; never a per-convergence gate.

## 8. Bootstrap

This proposal is the skill's first real review target — but the skill does not exist yet.
So the FIRST convergence of this doc uses EXISTING tools: same-family fresh-context
reasoning plus a RAW `claude -p` DeepSeek call for the different-family leg.

It does NOT use `hetero_review.py`: that wrapper requires `--diff` + `--blueprint`
(`hetero_review.py:683/686`) and its `adversarial_prompt` is hardcoded code-shaped
("ADVERSARIAL code reviewer … correctness bugs, security issues … Review the diff …
against the authoritative blueprint"). This proposal has no diff and no blueprint ref,
so the wrapper cannot review it faithfully — which is itself the §1 evidence that
doc-review needs a different substrate. The raw `claude -p` call reuses the wrapper's
MATERIALIZATION (profile + `.env` token) with a hand-written doc-review prompt (the Q2
enum) + the doc-findings shape, mirroring the manual 7-round pattern in
`hetero-long-doc-review-convergence`.

Only AFTER this doc converges does bc formalize it into a frozen spec; only then does
pd implement. We are at step 1 of 3 (converge → bc formalize → pd implement).

## 9. Decisions locked this round (still reviewable)

Each row is the proposed lock; the review loop may overturn any of them.

| ID | Question | Decision | Rationale |
| --- | --- | --- | --- |
| Q1 | name | `cross-source-review` (final) | user-locked |
| Q2 | doc-findings schema | generalize bc's `review-findings.schema.json`; v1 `kind` enum = `contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` / `citation-error` / `coverage-gap` | borrows `contradiction` from bc; replaces bc's `gap`/`over-engineering`/`blind-spot` with doc-domain kinds (`structural-gap` ≈ gap; `scope-creep` ≈ over-engineering; `coverage-gap` ≈ blind-spot) plus `authority-chain-break` + `citation-error` |
| Q3 | convergence-record schema | minimal record now (rounds, per-round findings-count, trend, `substantive_converged`, coverage, stalemate); field NAMES aligned to `loop_state`'s run-record (iterations / verdict / findings) for Phase-B map-ability; NO code dependency on `loop_state` | cheap now, expensive to retrofit (the Phase-A pluggability principle) |
| Q4 | activation boundary | Phase A = EXPLICIT invocation only (`/cross-source-review`); defer the 3-way `trigger_check` partition to when the skill seeks auto-routing; ship a Scope Guard anyway (cheap, mirrors bc/pd) | explicit invocation MINIMIZES routing risk (does not zero it — bare-phrasing collision remains, which is why a Scope Guard still ships; bc §8 bounds but does not eliminate collision); auto-routing is a maturation decision, not a Phase-A blocker |
| Q5 | same-family leg | define a skill-local same-family doc-reviewer from Phase A (fresh-context, read-only, barred from outcome-axis); bc's `plan-reviewer` informs the pattern, NOT the default leg | `plan-reviewer`'s prompt is plan-MODEL-shaped (item_id/dod_ref/authority-chain), not generically doc-shaped; the bootstrap same-family leg already used a custom fresh-context doc reviewer (FX-05) |
| Q6 | self-gate list | THREE skill-SPECIFIC gates on top of the standard set every skill inherits (`disconnect_check` / `plugin_layout` / `lint_self` — structural / loading-chain / layout / lint): (1) dogfood the skill's own convergence loop on its own `SKILL.md` [rule 1]; (2) a findings shape-contract gate [mirror pd's `adapter_shape_check.py`]; (3) an offline convergence-policy gate for caps + stalemate round-trip [mirror pd's `hetero_review_wiring.py`] | the three extend pd's proven gate trio; "self-gates green" in §5 means the full set (standard + skill-specific) |
| Q7 | N for "质量稳定" | N ≥ 3 real docs, ONE of which is the `SKILL.md` (not additional to the N), and ≥ 1 of which is a LONG doc exercising the cap=5–7 path | 3 short docs alone would not validate the long-doc substantive-convergence judgment — the skill's riskiest claim; aligned with §5 |
