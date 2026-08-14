# primary-source-verification — design proposal (CSR SUBSTANTIVE-CONVERGED; Phase A BUILT 2026-07-31)

> Status: Converged + built. CSR process-axis SUBSTANTIVE-CONVERGED 2026-07-07 (trail: `proposal.convergence.md`); Phase A built 2026-07-31 (PSV-I0–PSV-I6 converged via parallel-development plan-driven). Name LOCKED `primary-source-verification`. Formalizes the P1 outcome-axis skill. Origin: recommendation produced while evaluating arXiv:2607.13683 ("Self-Evolving Agent Harnesses via Gated Semantic Quality-Diversity"; the "GSME" acronym used in the outcome-axis backlog is pending verification of its declared expansion) against the position paper *Specification Gaming as an Orthogonal Failure Axis in Autonomous Coding Loops* (the "spec-gaming paper"). That paper's own review record shows citation misattributions (CaMeL lineage, Pan 2022 attribution, Loki specifics) slipping its cross-source-review pass and caught only by independent primary-source spot-checks. This skill closes that gap.

**Authority status (2026-07-31, orchestrator primary-source check).** The spec-gaming paper exists as a local fedaot-wiki draft (`docs/papers/spec-gaming-orthogonal-axis.md`; status `draft-cross-source-converged` 2026-07-08; authors TBD). Open-web and arXiv search do NOT surface it because it is a private draft, not a publication — the negative search result is a coverage artifact, not evidence of nonexistence. Orchestrator-verified against that source on 2026-07-31: every section attribution checks out — §3.3 two-axis frame + the "flatten two axes" category-error (the phrase appears in the paper's abstract/§1; §3.3 develops it); §4.1 level-3 "Formal (externally authored)" oracle with strong decoupling; §4.2 `rightness` schema ("not auto-satisfied by process success"; values `human_confirm_required` / `oracle_verified_under_known_coverage`); §3.2(iii) same-source-review ceiling — and the origin-story claim (CaMeL spec-gaming-lineage misattribution dropped; Pan 2022 "irreducible" narrowed; Loki specifics corrected) matches the paper's own review record. CaMeL arXiv:2503.18813 = "Defeating Prompt Injections by Design" and arXiv:2607.13683's title are independently fetch-verified (orchestrator-only: a local-only reviewer leg cannot re-fetch these or re-run the open-web negative search; recorded per workspace rule 3). Coverage caveat (not a blocker): the paper is a draft with authors TBD — a weaker epistemic anchor than a peer-reviewed source; the proposal's framework is accurately derived from it, but the paper's own conclusions stay human/outcome-axis.

CSR covers process-axis only; the design's soundness stays human (outcome-axis).

## 1. Problem

cross-source-review converges a doc's PROCESS-axis quality (well-formed, internally consistent, citation-accurate, coverage-complete) and is schema-barred from OUTCOME-axis judgment. The doc-findings `kind` enum has no word for "this factual claim is false" or "this citation misrepresents its primary source." `authority-chain-break` exists but, for EXTERNAL citations (arXiv, Crossref, paywalled sources), it is bounded by the reviewer leg's MODEL RECALL of the cited work, not the fetched source text. (csr's legs DO fetch and verify LOCAL repo citations — files, sections, code symbols — via Read/Grep/Glob; psv's added surface is the external fetch, not local verification, which csr already does.) A doc can reach `substantive_converged` while its factual and citation claims are wrong.

| Need | Owner today | Gap |
| --- | --- | --- |
| verify an artifact's factual/citation claims against the cited PRIMARY source | cross-source-review legs (LOCAL citations fetched via Read/Grep/Glob; EXTERNAL citations via model recall only) | external-source misattributions slip (claimed example — spec-gaming paper: CaMeL/Pan/Loki caught only by human spot-check; NOTE the spec-gaming paper is itself unfetchable, see Authority status) |
| a per-claim verdict grounded in a fetched-source quote | cross-source-review legs (LOCAL citations only — fetched); nothing for EXTERNAL citations | external-citation findings cite recalled text, not fetched text |
| an honest "verified under known coverage" signal (not a correctness-converged boolean) | nothing | no outcome-axis oracle weaker than human exists in the family |

Scope note: this skill targets CLAIMS ADMISSIBLE TO A FETCHABLE AUTHORITY — atomic factual/citation statements a fetched source can adjudicate (arXiv abstract, Crossref metadata, a spec section, a code symbol). Interpretive claims ("X and Y address disjoint surfaces") are not admissible; they escalate to human. The automatable surface is narrower than "all correctness"; see §2.

## 2. Non-goals (honesty bounds)

- NOT a global correctness verdict. The skill NEVER emits `correctness_converged` or "the doc is correct." Per the spec-gaming paper §4.2, `rightness` is not auto-satisfiable; the skill's top-line signal is `oracle_verified_under_known_coverage` (verified N of M claims against fetched sources; K unverifiable escalate to human). This is an honest coverage disclosure, workspace rule 3 (never silently green).
- NOT a symmetric "outcome-source-review" that converges to soundness. A mirror of cross-source-review that loops LLM legs to a `soundness_converged` boolean is the category error the spec-gaming paper names (abstract; §1 contributions; developed in §3.3 — flattening two axes into one). This is the load-bearing non-goal; its ADR (Context / Decision / Why / Rejected, workspace rule 6) is to be logged in the skill's `design-decisions.md` at Phase A. Rationale: the symmetric-mirror rejection IS the category-error argument in this bullet (§2); the csr–psv additive relationship is in §9 Q5.
- NOT novelty, soundness, or significance assessment. Sibling outcome-axis concerns (Phase B skills or human); see §5. Significance is a permanent human non-goal, not a deferred skill.
- NOT primary-source gathering for an open question. That is blueprint-crafting `researcher` (forward: "find sources about X"). This skill is backward: "does claim C in a finished artifact hold against its cited source?"

## 3. What the skill owns (Phase A)

Contract: a read-only, source-grounded, per-claim verifier for a doc-shaped artifact. It never edits the artifact; its sole output is a findings packet plus a coverage disclosure.

Pipeline:

1. **Claim extraction.** Read the artifact; enumerate atomic, source-admissible claims, each tied to a location and an expected adjudicating source. **Atomic** = one verifiable proposition per claim (compound claims split). **Source-admissible** = the claim references a specific, fetchable source that can adjudicate it (arXiv abstract, Crossref, spec section, code symbol); design decisions, predictions, and interpretations are NOT admissible and escalate to human. Interpretive or judgment claims are tagged `unverifiable` at extraction, not force-fitted. **Extractor blind-spot caveat (workspace rule 3):** extraction is itself model-performed and inherits the extractor's blind spots — claims neither the author nor the extractor can see are absent from the enumeration and therefore from the coverage disclosure. The N/R/W/K/M counts are conditional on what was extracted, not a completeness guarantee; a different-family extraction leg is partial mitigation, not a fix (the spec-gaming paper §3.1 self-certification paradox, applied to psv's own step 1).
2. **Source fetch.** For each claim, fetch its cited authority (arXiv abstract page, Crossref, repo file, spec section). The fetched-source TEXT is the oracle — externally authored, so by the spec-gaming paper's §4.1 decoupling criterion (the oracle's blind-spot set differs from the agent's), its blind spots are the source's, not a model's. (Precision: the paper's §4.1 level-3 "Formal (externally authored)" slot is specifically *formal* artifacts — contracts, invariants, type systems; fetched prose is externally authored but not formal, so it inherits the strong-decoupling property without occupying the level-3 formal slot.)
3. **Per-claim verdict.** Compare claim vs fetched text; assign one of:
   - `verified` — fetched source supports the claim.
   - `refuted` — fetched source contradicts the claim (e.g., CaMeL arXiv:2503.18813 is prompt-injection defense, not a "specification gaming lineage").
   - `narrowed` — source supports a weaker form (e.g., an "irreducible" reading of Pan 2022 (arXiv:2201.03544) overclaims: Pan demonstrates the proxy/true-reward gap but also proposes mitigations; the spec-gaming paper §3.2(ii) narrows its own irreducibility claim accordingly).
   - `unverifiable` — no fetchable source adjudicates it (interpretive, paywalled, judgment call); escalate to human.
   - **Comparison blind-spot caveat (workspace rule 3):** the fetched TEXT is the oracle for what the source says, but the claim-vs-text comparison is model-performed — `verified` means the model found no contradiction, not that none exists (false-negative risk). The fetched source is strongly decoupled (§4.1); the comparison judgment is not. `refuted` / `narrowed` additionally involve a bounded interpretive step (not pure string match), so a factual, source-admissible claim may still receive a model-judged verdict — distinct from step 1's rule that interpretive *claims* themselves are inadmissible.
4. **Coverage disclosure.** `oracle_verified_under_known_coverage`: N verified, R refuted, W narrowed, K unverifiable, of M = N + R + W + K extracted claims. This is the ONLY top-line signal. There is no boolean "correct."

Schema (extends doc-findings, reuses `defect_id` / `severity` / `location` / `evidence` / `suggestion`):

- `kind` gains `claim-refuted`, `claim-narrowed`, and `claim-unverifiable`.
- The findings array holds defects only: `claim-refuted` (severity `blocker`), `claim-narrowed` (severity `warning`), and `unverifiable` claims as `claim-unverifiable` kind at `coverage` severity (rule 3) — DISTINCT from csr's `coverage-gap` kind (a missing-section defect in the artifact), so a reviewer disclosure is not conflated with an artifact defect. `verified` claims are NOT findings (no defect); they are counted in the coverage disclosure.
- The `evidence` standard is raised: every finding MUST cite a fetched-source quote, not model recall. A finding lacking a fetched quote is downgraded to `unverifiable`, never asserted.
- The required `outcome_axis_respected` boolean is retained and asserted true: the skill verifies per-claim against a source; it does not certify global truth.
- The top-line signal `oracle_verified_under_known_coverage` and its N/R/W/K/M counts live in a SEPARATE `coverage-record` schema, analogous to csr's split (doc-findings for per-claim defects vs convergence-record for the top-line verdict). psv thus emits two objects: the extended doc-findings (per-claim defects) and the coverage-record (the count + signal).

## 4. What stays put (Phase A does NOT touch)

- `cross-source-review/` unchanged. psv is additive; csr remains the process-axis convergence engine. A doc still goes through csr for consistency and structure; psv runs for factual/citation correctness. The two compose; they do not merge.
- `blueprint-crafting/` unchanged, including its `researcher` agent (forward source-gathering; distinct direction, §2).
- `parallel-development/` unchanged. psv is doc-shaped, not code-shaped; code correctness routes to pd's gates.

## 5. Phase B — evidence-gated, NOT pre-committed

Two sibling outcome-axis skills are foreseeable. Each gets its own proposal and its own convergence pass; neither is designed here.

- **prior-art-search (P2).** Extract the artifact's novelty claims; multi-source search (arXiv, web, repos) per claim; surface prior-art collisions plus uncited relevant work. Output is a collision report plus coverage disclosure, NEVER `novel_confirmed` (absence of found prior art is not proof of novelty — the irreducible limit). Distinct from `researcher` (forward gather vs backward collision).
- **argument-red-team (P3).** Per load-bearing claim, emit attack vectors, with a different-family leg for partial decoupling. Red-team EVIDENCE only (weaknesses for the human), never a `soundness_converged` verdict. Ceiling for informal or philosophical arguments is salient plus partial-decoupling; latent soundness stays human — the spec-gaming paper §3.2(iii) prediction.

Permanent non-goal (not Phase B, not ever a skill): **significance.** Community judgment, human only. A skill may gather signals for the human; it does not verdict.

## 6. Layering

The family currently covers the PROCESS axis (blueprint-crafting authors and converges upstream artifacts; cross-source-review converges any doc; parallel-development converges code). psv opens the OUTCOME axis, making the family two-axis — the frame the spec-gaming paper §3.3 argues and §4.2 schemas.

Rightness-tier mapping across the family (one term per tier, workspace rule 10):

| Tier signal | Owner skill | Meaning |
| --- | --- | --- |
| `substantive_converged` | cross-source-review | doc is well-formed, internally consistent, citation-structured, core-claims coverage-reviewed. Precision: this is csr's process-axis field and it is LLM-adjudicated (a same+异源 review-loop verdict), NOT the spec-gaming paper's machine-checkable `process_converged` (§4.2 — a deterministic, gate-derived boolean the agent cannot tamper with). psv maps csr's field to the paper's process TIER, but csr's realization is a weaker structural guarantee than the paper's deterministic one; the two share the tier concept, not the tamper-resistance property. |
| `oracle_verified_under_known_coverage` | primary-source-verification (this skill) | per-claim verdicts grounded in fetched sources, with declared coverage; K claims escalated |
| `human_confirm_required` | human (significance, latent soundness, final novelty) | the residue no machine oracle adjudicates |

psv does NOT subsume csr, and csr does NOT reach psv's regime: csr's legs share the model's blind spot on cited works; psv's oracle is the fetched source text, a genuinely different blind-spot set.

## 7. Workspace-rule implications

- Rule 3 (never silently green) is load-bearing for psv. The coverage disclosure IS the rule-3 instrument: the skill states exactly what it verified and what it could not, and degrades `unverifiable` to escalation, never to a silent pass.
- Rule 6 (ADR for non-obvious decisions). The "no symmetric outcome-convergence skill" decision is non-obvious and runs counter to the instinct to mirror csr; it gets a rule-6 ADR (logged in the skill's `design-decisions.md` at Phase A; rationale — mirror-rejection = the §2 category-error argument; csr–psv additive relationship = §9 Q5) so a future maintainer does not re-derive it by building the mirror.
- Rule 10 (terminology). `oracle_verified_under_known_coverage` is the one term for the skill's top-line signal; `correctness_converged` is the forbidden term and never appears as an emitted field.

## 8. Bootstrap (Phase A implementation — out of scope for this proposal)

Listed for sizing only; this proposal does not build it. Phase-A work-items would include: a claim-extraction prompt or agent; source-fetch tooling (reuse of fetch primitives; provider-token isolation per the csr `install.md` pattern); the schema extension in §3; a self-gate asserting every emitted finding carries a fetched-source quote (the rule-3 plus L1 enforceable invariant); `plugin.json` and `SKILL.md` registration. Each is a CSR-style work-item in a future `iteration-plan.md`, not pre-committed here.

## 9. Decisions proposed this round (still reviewable; Q1 name pending LOCK)

- **Q1 — Name.** PROPOSED `primary-source-verification`. Names the method (fetched primary-source oracle) plus the activity, consistent with the family's descriptive `<domain>-<activity>` naming pattern (csr is the closest exemplar; the pattern is observed, not a codified rule — bc's `blueprint-crafting` parses as object + activity); foregrounds the differentiator from csr's recall-based `authority-chain-break`. "Primary source" is broadened here to mean any fetched authoritative origin (arXiv abstract, Crossref, spec section, code symbol), not only academic primary sources. Rejected: `outcome-correctness-review` (implies global correctness certification — the §2/§3 category error, and an L1 naming-vs-function Blocker per the repo constitution). Considered and dropped: `claim-verification` (loses the source-grounding signal; reads as csr's existing claim-checking). Pending convergence to LOCK.
- **Q2 — Scope.** P1 (correctness via primary-source fetch) ONLY in Phase A. Rejected: an umbrella outcome-axis proposal covering P2/P3 (breaks one-skill-one-proposal; pre-commits unconverged P2/P3 designs). P2/P3 get their own proposals (§5).
- **Q3 — Signal.** `oracle_verified_under_known_coverage`, never `correctness_converged`. The coverage disclosure, not a boolean, is the contract.
- **Q4 — Oracle.** The fetched primary-source text — externally authored, so it meets the spec-gaming paper's §4.1 decoupling criterion (blind-spot set differs from the agent's). (Precision: the paper's level-3 "Formal" slot is specifically formal artifacts; fetched prose is externally authored, not formal — same decoupling property, different slot.) Rejected: model-recall verification (that is csr's bounded leg; it is the gap, not the fix).
- **Q5 — Relation to csr.** Additive, non-merging. psv runs after csr (authoritative full-M record) or beside it; GATE MODE (2026-08): when rule-13 conditions hold, psv runs BEFORE csr as a load-bearing-claims subset gate — batch GO/NO-GO signal, gate record explicitly non-authoritative (not a coverage record), bounded re-gate ≤2 (not a debate loop — ADR #1 intact); the full-M run after csr remains the ONLY authoritative coverage record. Discriminator (ODP-5, 2026-08-10): the gate pays on docs with predominantly EXTERNAL load-bearing citations and on LONG-tier docs; local-citation docs — csr alone suffices; short docs never pay (p/C ratio). csr's `substantive_converged` does not imply psv's coverage, and psv's coverage does not grant csr's process convergence.
