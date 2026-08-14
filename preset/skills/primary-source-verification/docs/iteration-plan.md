# primary-source-verification — Iteration Plan (Phase A / P1)

> Based on `docs/proposal.md` (CSR process-axis SUBSTANTIVE-CONVERGED 2026-07-31; convergence
> record: `docs/proposal.convergence.md`). This plan is the **execution blueprint** for Phase A / P1.
> Structured like `cross-source-review`'s plan (complexity tier + dependency edges + **validation
> gate** = the only "done" criterion — no calendar duration).
>
> **Authority chain**: `proposal.md` = authoritative design (master); this `iteration-plan.md` =
> execution blueprint (on conflict, **proposal.md wins**). The proposal's §9 decisions (Q1–Q5) are
> locked inputs; this plan shapes them into work-items, it does not re-debate them.

## 0. Background and scope

- Current state: proposal frozen + cross-source-reviewed (`proposal.convergence.md`); **no
  `SKILL.md`, no schemas, no agents, no fetch/verdict machinery, no self-gates**.
- Scope (Phase A / P1): zero → a read-only, source-grounded, per-claim verifier that drives a
  doc-shaped artifact's factual/citation claims against their **fetched primary sources** and emits a
  per-claim verdict packet plus an honest coverage disclosure. It is ADDITIVE to `cross-source-review`
  (csr) — csr converges the process axis; psv opens the outcome axis's *admissible* surface (claim
  vs fetched source). It does NOT converge to soundness/correctness (proposal §2 — the category error).
- Architecture note (load-bearing): psv is a **single pipeline** (extract → fetch → verdict →
  coverage), NOT a same-family+different-family multi-round debate (that is csr's regime). The oracle
  is the **fetched source text** (proposal §3 step 2 / §9 Q4), not a different-family model. psv
  therefore does NOT port csr's heterogeneous substrate; it reuses csr's *schema-field pattern* and
  the `install.md` token-isolation pattern (workspace rule 7 — copy-patterns, not code).
- P2 `prior-art-search` and P3 `argument-red-team` are **out of scope** (proposal §2 Q2, §5) — each
  earns its own proposal; neither is designed here. `significance` is a permanent human non-goal.

## 1. Estimation gauge (no day counts)

| Dimension | Meaning | Use |
| --- | --- | --- |
| **Complexity tier** S/M/L/XL | intrinsic difficulty: fetch/verdict novelty × coverage-honesty risk × integration surface | per-iteration risk + gate density |
| **Dependency edge** | "X must exist before Y" | execution order + critical path |
| **Validation gate** | an objective "done" criterion: schema validates / shape-contract gate green / dogfood catches a planted misattribution | the unit of progress — no gate, no delivery |

Tier definitions: S = single artifact, few edge cases; M = several subtleties; L = many subtleties stacked (fetch tooling + verdict semantics + honesty contract); XL = broad coverage + high integration + hard semantics. No XL iterations in Phase A.

## 2. Overview: iterations, complexity, dependencies, gates

| ID | Iteration | Complexity | Deps | Key validation gate (summary) |
| --- | --- | --- | --- | --- |
| PSV-I0 | scaffold + `SKILL.md` + activation/scope-guard | M | — | `SKILL.md` loadable; Scope Guard routes code→`parallel-development`, spec-authoring→`blueprint-crafting`, convergence→`cross-source-review`; positions psv as the outcome-axis per-claim verifier, additive to csr |
| PSV-I1 | schemas (doc-findings extension + coverage-record) | M | PSV-I0 | both schemas validate; doc-findings `kind` enum = csr's 6 kinds **+** `claim-refuted` / `claim-narrowed` / `claim-unverifiable` (strict superset — csr's 6 preserved); coverage-record carries `oracle_verified_under_known_coverage` + N/R/W/K/M counts |
| PSV-I2 | claim-extraction agent/prompt | M | PSV-I1 | agent enumerates atomic, source-admissible claims (each tied to a location + expected adjudicating source); tags interpretive claims `unverifiable`; carries the extractor blind-spot caveat |
| PSV-I3 | source-fetch tooling + per-claim verdict comparator | L | PSV-I1 | fetches a cited source and returns a parsed text blob; comparator assigns verified/refuted/narrowed/unverifiable with a **fetched-source quote** as evidence (provider-token isolation per csr `install.md`) |
| PSV-I4 | coverage driver (owns the §3 pipeline contract) | L | PSV-I2, PSV-I3 | drives extract→fetch→verdict→coverage on a fixture doc; emits the coverage-record (`oracle_verified_under_known_coverage`: N/R/W/K of M); NEVER `correctness_converged` |
| PSV-I5 | self-gates + standard set | L | PSV-I4 | 3 skill-specific gates green — (a) **fetched-quote invariant** (every emitted finding carries a fetched-source quote; a quote-less finding is downgraded to `claim-unverifiable`), (b) findings/coverage shape-contract, (c) offline coverage-policy — PLUS standard (`disconnect_check` / `plugin_layout` / `lint_self`) |
| PSV-I6 | dogfood + 质量稳定 gate | M–L | PSV-I5 | N ≥ 3 real artifacts (≥ 1 long doc) verified, including ≥ 1 doc with a **planted misattribution** that psv catches via the fetched source; measured coverage profile recorded |
| — | **Phase-A acceptance gate** | | PSV-I6 | see §6 |

> **First package**: PSV-I0 + PSV-I1 together (scaffold + schema contract are the foundation). After
> PSV-I1, PSV-I2 (extraction) and PSV-I3 (fetch+verdict) parallelize. PSV-I4 closes on both; PSV-I5
> + PSV-I6 follow sequentially (gates need the driver; dogfood needs the gates).

## 3. Foundation layer (PSV-I0–PSV-I1)

### PSV-I0 scaffold + `SKILL.md` + activation/scope-guard — M

- **Goal**: a loadable skill skeleton with the correct scope + an honest activation story.
- **Deliverables**: `primary-source-verification/SKILL.md` (description declares the per-claim, source-grounded verification scope; Scope Guard routes code→`parallel-development`, spec-authoring→`blueprint-crafting`, and doc-convergence→`cross-source-review`; states psv is additive to csr and NEVER emits `correctness_converged`).
- **Done when**: `SKILL.md` is loadable; Scope Guard emits the correct routing hints; the additive-to-csr + no-correctness-boolean positioning is stated honestly.
- **Basis**: proposal §1, §2 (non-goals), §6 (layering), §9 Q1/Q2/Q3.

### PSV-I1 schemas (doc-findings extension + coverage-record) — M

- **Goal**: the two data contracts the extractor, comparator, and driver exchange.
- **Deliverables**:
  - `infra/schemas/doc-findings.schema.json` — **copied from csr's** `doc-findings.schema.json` and extended: the `kind` enum gains `claim-refuted` / `claim-narrowed` / `claim-unverifiable` alongside csr's existing 6 (a STRICT SUPERSET — csr's 6 are preserved byte-for-byte); `severity` keeps {blocker, warning, coverage}; the `evidence` standard is raised — every `claim-refuted`/`claim-narrowed` finding MUST cite a fetched-source quote (a finding lacking one is downgraded to `claim-unverifiable`, never asserted). `claim-unverifiable` is a KIND (an artifact-adjudicable claim that no source could settle), DISTINCT from csr's `coverage-gap` kind (a missing-section defect) and from the `coverage` SEVERITY (the reviewer's own disclosure).
  - `infra/schemas/coverage-record.schema.json` — the top-line signal's home: `oracle_verified_under_known_coverage` + the counts N verified / R refuted / W narrowed / K unverifiable of M = N + R + W + K extracted claims; plus `rightness: human_confirm_required` constant. Analogous to csr's split (doc-findings for per-claim defects vs convergence-record for the top-line verdict).
- **Done when**: both schemas pass the stdlib JSON-schema validator; doc-findings `kind` enum = csr's 6 + exactly the 3 new kinds; the coverage-record carries `oracle_verified_under_known_coverage` (NOT `correctness_converged`) and the N/R/W/K/M invariant is stated.
- **Basis**: proposal §3 (schema), §9 Q3/Q4; PSV round-2 fixes (claim-unverifiable kind; coverage-record home; M = N+R+W+K).

## 4. The pipeline legs (PSV-I2–PSV-I3)

### PSV-I2 claim-extraction agent/prompt — M

- **Goal**: enumerate the admissible claim set the oracle will adjudicate.
- **Deliverables**: a skill-local agent/prompt that reads the artifact and emits atomic, source-admissible claims, each tied to a location and an expected adjudicating source (arXiv abstract / Crossref / spec section / code symbol). **Atomic** = one verifiable proposition per claim (compound split). **Source-admissible** = references a specific, fetchable source; design decisions, predictions, and interpretations are NOT admissible (escalate to human). Interpretive claims are tagged `unverifiable` at extraction, not force-fitted. Carries the **extractor blind-spot caveat** (rule 3): extraction is model-performed; claims neither author nor extractor can see are absent from M — the counts are conditional on what was extracted, not a completeness guarantee.
- **Done when**: on a fixture doc the agent returns a claim list where every claim has a location + an adjudicating-source ref; a planted interpretive claim is tagged `unverifiable`, not forced admissible.
- **Basis**: proposal §3 step 1 (+ PSV round-2 D2/D4 fixes: atomic/source-admissible defined; extractor blind-spot caveat).

### PSV-I3 source-fetch tooling + per-claim verdict comparator — L

- **Goal**: the fetched-text oracle + the claim-vs-text verdict.
- **Deliverables**:
  - a **fetch** tool/unit that retrieves a cited source (arXiv abstract page, Crossref, repo file, spec section) and returns parsed text. **Credential surface (outer-ring novel-1):** csr's `install.md` token-isolation targets csr's heterogeneous `claude -p` substrate (an Anthropic-gateway LLM token) — a precondition psv does NOT have (psv disclaims that substrate). psv's actual surface: (a) the comparator runs in the same-family Claude runtime (no isolated LLM token); (b) open sources (arXiv, Crossref, repos) are fetched with NO credential; (c) paywalled sources are NOT fetched — returned `claim-unverifiable` (escalate). A future paywalled-fetch credential would be a separately-named HTTP surface, not csr's LLM-token namespace. The fetched TEXT (not a model) is the oracle.
  - a **comparator** that, given a claim + fetched text, assigns `verified` / `refuted` / `narrowed` / `unverifiable` and emits a doc-findings entry whose `evidence` QUOTES the fetched text (for refuted/narrowed). Carries the **comparison blind-spot caveat** (rule 3): the fetched source is strongly decoupled, the comparison judgment is not — `verified` means the model found no contradiction, not that none exists; `refuted`/`narrowed` involve a bounded interpretive step.
- **Done when**: on a fixture claim + fetched fixture source, the comparator returns a schema-valid finding with a fetched quote; on a claim whose source cannot be fetched, it returns `claim-unverifiable` (escalate), never a bare assertion.
- **Basis**: proposal §3 steps 2–3 (+ PSV round-2 D1/h2 fixes: fetched prose is externally-authored not "level-3 formal"; comparison blind-spot caveat); §8 (fetch primitives + token isolation).

## 5. Coverage driver + self-gates + dogfood (PSV-I4–PSV-I6)

### PSV-I4 coverage driver (owns the §3 pipeline contract) — L

- **Goal**: orchestrate extract → fetch → verdict → coverage into one honest pass.
- **Deliverables**: a driver (script + the SKILL.md workflow) that, given an artifact, runs PSV-I2 extraction → PSV-I3 fetch+verdict per claim → emits the coverage-record (`oracle_verified_under_known_coverage`: N/R/W/K of M; K escalated to human) PLUS the doc-findings packet (refuted/narrowed/unverifiable findings only; `verified` claims are counted, not listed). Hard invariants: NEVER emits `correctness_converged` (proposal §2/§9 Q3 — the forbidden term); a finding without a fetched quote is downgraded to `claim-unverifiable`; the coverage disclosure is the ONLY top-line signal; **M=0 (no source-admissible claims extracted) escalates to human ("no admissible surface on this artifact"), DISTINCT from K>0 (claims extracted but unverifiable) — never a silent "0-of-0 perfect" green** (outer-ring novel-2).
- **Done when**: on a fixture doc with a planted refutable claim, the driver emits `claim-refuted` with a fetched quote AND a coverage-record whose counts include it; on a fixture doc with an uncovered (unverifiable) claim, K > 0 and the record escalates honestly (no silent pass).
- **Basis**: proposal §3 step 4 (+ PSV round-2 F4/F10 fixes); §9 Q3.

### PSV-I5 self-gates + standard set — L

- **Goal**: the skill's deterministic self-checks (workspace rule 1).
- **Deliverables** — three skill-SPECIFIC gates on top of the standard set:
  1. **fetched-quote invariant gate** — every emitted `claim-refuted` / `claim-narrowed` finding carries a fetched-source quote in `evidence`; a quote-less finding is downgraded to `claim-unverifiable`. This is the workspace-rule-3 + L1 enforceable invariant (proposal §3, §8) — the load-bearing honesty gate.
  2. **shape-contract gate** — every extractor/comparator/driver emit path produces a doc-findings-valid AND coverage-record-valid object [mirror csr's `findings_shape_check.py` / pd's `adapter_shape_check.py`].
  3. **offline coverage-policy gate** — on dry-run fixtures: counts sum to M = N+R+W+K; an unverifiable claim yields K>0 + escalation (never silent pass); a no-admissible-claim fixture yields M=0 + escalation (never a silent "0-of-0" pass — novel-2); the `correctness_converged` term never appears in any emitted object.
  - PLUS the standard set: `disconnect_check.py`, `plugin_layout.py`, `lint_self.py`.
- **Done when**: all gates green (skill-specific + standard); each gate is self-contained (rule 7); gate (1)'s downgrade path is exercised on a quote-less fixture.
- **Basis**: proposal §3, §8, §9; workspace rule 1; PSV round-2 h1/h2/h3 (the honesty contract).

### PSV-I6 dogfood + 质量稳定 gate — M–L

- **Goal**: prove psv on real artifacts, including catching a real misattribution via the fetched source.
- **Deliverables**: run psv on N ≥ 3 real doc artifacts (≥ 1 a long doc), including ≥ 1 doc with a **known citation misattribution** that psv must catch by fetching the source (the spec-gaming paper's own pre-fix draft — with its CaMeL-lineage / Pan / Loki misattributions — is the canonical dogfood: psv should reproduce the spot-checks recorded in that paper's front matter). Record a measured coverage profile (N/R/W/K/M per run, escalations, honest coverage notes).
- **Done when**: N ≥ 3 runs recorded; ≥ 1 long-doc verified; the misattribution dogfood catches ≥ 1 planted/real misattribution via the fetched source (the value proposition demonstrated, as it was live during psv's own proposal review).
- **Divergence note (workspace rule 7 — explained divergence from csr-I6)**: unlike csr, psv's own `SKILL.md` is NOT a dogfood target — it is skill-definition prose with no primary-source-citable claims (inadmissible under PSV-I2 → M=0). The self-referential role csr's own-SKILL.md plays is filled here by psv's own `proposal.md` (cites CaMeL arXiv:2503.18813 + GSME arXiv:2607.13683, both fetch-verified) and by the spec-gaming pre-fix draft (the canonical misattribution fixture) (outer-ring novel-3).
- **Basis**: proposal §5 (质量稳定 gate analog), §8; the proposal's own origin (the spec-gaming paper's spot-checks).

## 6. Phase-A acceptance gate (after PSV-I6)

- psv drives extract→fetch→verdict→coverage on a real doc, emitting an honest coverage-record (`oracle_verified_under_known_coverage`; K escalations stated) and a doc-findings packet whose every refuted/narrowed finding carries a fetched-source quote.
- All self-gates green (skill-specific + standard); the fetched-quote invariant gate (1) exercises the downgrade path.
- The 质量稳定 N ≥ 3 dogfood (incl. one long-doc + one misattribution-catch) is recorded with a measured coverage profile.
- The doc-findings extension is a strict superset of csr's (the 6 csr kinds preserved); the coverage-record validates and never carries `correctness_converged`.
- **Doc-audit pass (proposal §7 rule 5)**: the family's layering docs gain the outcome-axis tier (csr's docs note "psv runs for factual/citation correctness; csr does not reach psv's regime" — proposal §6).
- csr/bc/pd CORE LOGIC is UNCHANGED (Phase A does not touch it; psv is additive).

## 7. Dependencies and parallelism (DAG)

```text
PSV-I0 scaffold ─▶ PSV-I1 schemas ─┬─▶ PSV-I2 claim-extraction ─┐
                                    │                      │
                                    └─▶ PSV-I3 fetch + verdict comparator ─┤
                                                          ▼
                                          PSV-I4 coverage driver ◀── (PSV-I2 + PSV-I3)
                                                          ▼
                                          PSV-I5 self-gates
                                                          ▼
                                          PSV-I6 dogfood + 质量稳定
                                                          ▼
                                          Phase-A acceptance gate
```

**Parallel fan-out**: after PSV-I1, PSV-I2 and PSV-I3 run in parallel (extraction and fetch+verdict are independent). PSV-I4 depends on both. PSV-I5 → PSV-I6 sequential.

## 8. Risks and mitigations

| Risk | Iteration | Mitigation |
| --- | --- | --- |
| psv mistaken for a correctness/soundness oracle (the §3.3 category error) | PSV-I0 | SKILL.md + the `oracle_verified_under_known_coverage` signal (never `correctness_converged`) + the §2 non-goal stated up front |
| doc-findings extension drifts from csr's (breaks the strict-superset contract) | PSV-I1 | copy csr's schema verbatim then ADD the 3 kinds; gate asserts csr's 6 are preserved |
| a refuted/narrowed finding slips through without a fetched quote (silent assertion) | PSV-I3/PSV-I5 | fetched-quote invariant gate (1) downgrades quote-less findings to `claim-unverifiable` |
| claim-extraction blind-spot: a real claim is never extracted → absent from M | PSV-I2 | extractor blind-spot caveat disclosed per rule 3; different-family extraction leg is partial mitigation, NOT a fix (deferred) |
| comparison blind-spot: `verified` read as "no contradiction exists" | PSV-I3/PSV-I4 | comparison blind-spot caveat; `verified` counted, never asserted as proof |
| fetch tooling leaks/borrows a credential (token-isolation breach) | PSV-I3 | open sources need no credential; paywalled → `claim-unverifiable`; if an HTTP-credential surface is added it is separately named (NOT csr's LLM-token namespace) — novel-1 |
| psv and csr both triggered on a "review this doc" request | PSV-I0 | Scope Guard: convergence→csr, per-claim source verification→psv; explicit invocation in Phase A |
| rule-5 doc-audit ripple forgotten | PSV-I0 / §10 | cross-cutting doc-audit task + acceptance-gate criterion (family layering docs gain the outcome-axis tier) |
| dogfood N too small / no misattribution caught | PSV-I6 | require ≥ 1 misattribution-catch run (the spec-gaming pre-fix draft is the canonical fixture) |

## 9. Out of scope (Phase A)

- P2 `prior-art-search` and P3 `argument-red-team` in any form (proposal §5 — each earns its own proposal + convergence pass).
- Any change to csr/bc/pd **CORE LOGIC**: csr's legs/driver, bc's operators, pd's gates. psv is additive (proposal §4). NOT violated by the **doc-audit routing-hint / layering-doc updates** (doc edits, in scope, §10).
- `significance` assessment — permanent human non-goal (proposal §2, §5).
- Outcome-axis judgment (is the doc "right") — human only. psv verifies per-claim against a source; it does not certify global truth.
- A symmetric "outcome-source-review" that loops to `soundness_converged` — the §3.3 category error; explicitly rejected (proposal §2).

## 10. Cross-cutting tasks (across iterations)

| Task | Starts at | Note | Workspace rule |
| --- | --- | --- | --- |
| copy-patterns-not-code | PSV-I1/PSV-I3 | schemas copied from csr (extended, not imported); fetch token-isolation pattern copied from csr `install.md` — NOT imported | rule 7 |
| fetched-quote honesty | PSV-I3/PSV-I5 | the load-bearing invariant: every refuted/narrowed finding cites fetched text; quote-less → `claim-unverifiable` | rule 3 / L1 |
| ADR log | PSV-I1 | `design-decisions.md` for psv; non-obvious decisions get an ADR — the no-mirror/no-correctness-boolean decision (proposal §2, the §3.3 category error), the fetched-quote invariant, the coverage-record split, the extractor/comparison blind-spot disclosures | rule 6 |
| honest-coverage discipline | PSV-I4 | never fake green; `oracle_verified_under_known_coverage` + K escalations + blind-spot caveats stated honestly; `correctness_converged` never emitted | rule 3 / rule 4 |
| **doc-audit (rule-5 ripple)** | PSV-I0 | family layering docs gain the outcome-axis tier (csr's docs note psv runs the admissible per-claim surface csr cannot reach) | proposal §6 / rule 5 |
