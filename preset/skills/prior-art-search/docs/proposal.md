# prior-art-search — design proposal (CSR SUBSTANTIVE-CONVERGED + psv-verified; Phase A BUILT 2026-08-01)

> Status: Converged + built + name LOCKED. CSR process-axis SUBSTANTIVE-CONVERGED + psv N=9/K=0 verified (2026-07-31; trail: `proposal.convergence.md`); Phase A built 2026-08-01 (NC-I0–NC-I6 converged via parallel-development plan-driven). Name LOCKED `prior-art-search` (2026-08-05; §8 Q1) — the converged working name `novelty-coverage` was retired (human-usability: `coverage` = internal jargon). Formalizes the P2 outcome-axis skill. Origin: the outcome-axis line (`docs/outcome-axis-skill-backlog.md`); P2 earned this proposal when its readiness-gate worked example (2026-07-31) cleared — a search-to-collision run on the spec-gaming paper surfaced uncited prior art (the "Verification Paradox" / "Self-Critique Paradox" framings) for its self-certification-paradox claim, a finding `blueprint-crafting`'s forward-gather `researcher` would not produce (caveat: those sources themselves need primary-source adjudication — psv's job, additive). csr covers process-axis only, psv covers citation accuracy — neither validates the design's soundness, which stays human (outcome-axis).

## 1. Problem

A doc-shaped artifact (a design paper, a research doc, a spec) makes **novelty claims** — "X is a new framing," "Y is the first to," "Z has no prior art." These are load-bearing: a wrong one (the contribution already exists, uncited) silently inflates the artifact's value, and csr's legs verify EXTERNAL citations by MODEL RECALL (LOCAL repo citations they DO fetch via Read/Grep/Glob); neither csr nor psv hunts for UN-cited prior art. Three gaps:

- `cross-source-review` (csr) converges PROCESS-axis quality; it does not search for prior art the doc FAILED to cite.
- `primary-source-verification` (psv) verifies a claim against its CITED fetched source (backward, cited) — it does NOT search for uncited prior art.
- `blueprint-crafting`'s `researcher` is FORWARD gather ("find sources about X for authoring") — the opposite direction from "does this finished artifact's novelty claim collide with existing prior art?"

P2 is the missing **backward, uncited-prior-art collision** check.

| Need | Owner today | Gap |
| --- | --- | --- |
| surface prior-art COLLISIONS against a finished artifact's novelty claims | nothing | novelty claims go unchecked; the doc may overclaim novelty |
| an honest "collisions found under known search coverage" signal (not a novelty verdict) | nothing | no oracle weaker than human exists for a novelty verdict |
| a direction-distinct complement to the forward-gather `researcher` | `researcher` (forward) | no backward-collision leg |

Scope note: P2 targets a novelty claim's COLLISION with findable prior art — atomic, search-adjudicable propositions ("this paper introduces concept C"). Interpretive novelty judgments ("this is a significant contribution") are NOT search-adjudicable; they escalate to human. The automatable surface is collisions + uncited-relevant-work, NOT a novelty verdict (§2).

## 2. Non-goals (honesty bounds)

- NOT a novelty verdict. P2 NEVER emits `novel_confirmed`. Per the irreducible absence-of-evidence limit (you cannot prove a negative — "no prior art exists"), P2's top-line signal is `collisions_under_known_coverage` (N collisions / U uncited-relevant / I inconclusive of M novelty claims searched). A doc with zero found collisions is "no collision found in the searched corpus," NOT "novel." This is the load-bearing non-goal; ADR in §8, workspace rule 6.
- NOT a soundness/correctness judgment. Whether the artifact's ARGUMENTS are sound is the P3/argument-red-team domain (reclassified to a csr mode, 2026-07-31) + human. P2 checks NOVELTY claims against PRIOR ART, not argument soundness.
- NOT forward source-gathering. That is bc's `researcher` (forward). P2 is backward.
- NOT significance assessment. Permanent human non-goal (the outcome-axis line's standing non-goal).
- NOT exhaustive prior-art search. Search has recall/coverage limits (§3 oracle strength); P2 discloses its search coverage honestly, never claims the corpus was exhaustive.

## 3. What the skill owns (Phase A)

Contract: a read-only, search-grounded, per-novelty-claim collision detector. It never edits the artifact; its sole output is a collision packet plus a coverage disclosure.

Pipeline:

1. **Novelty-claim extraction.** Read the artifact; enumerate atomic novelty claims, each tied to a location + a search target. Distinguish novelty claims ("X is new") from factual/citation claims (psv's domain) and interpretive claims (escalate). Extractor blind-spot caveat applies (rule 3): claims neither author nor extractor identifies as "novelty" are absent from M.
2. **Multi-source search.** For each novelty claim, search the prior-art corpus (arXiv, web, repos) for work that ALREADY made the claim.
3. **Per-claim collision verdict.** Compare the claim against found prior art; assign one of:
   - `collision` — found prior art already makes this claim (the doc's novelty is overstated); cite the colliding source + quote.
   - `uncited-relevant` — found relevant work the doc didn't cite (not a direct collision, but a coverage gap).
   - `clear-under-search` — no collision found IN THE SEARCHED CORPUS (NOT `novel`; just no collision surfaced).
   - `inconclusive` — search couldn't cover the claim (paywalled corpus, ambiguous query); escalate to human.
4. **Coverage disclosure.** `collisions_under_known_coverage`: N collisions, U uncited-relevant, C clear-under-search, I inconclusive of M = N+U+C+I novelty claims searched. The ONLY top-line signal. There is no `novel_confirmed`. **M=0** (no extractable novelty claims — a doc making no novelty assertion, or all novelty claims interpretive) escalates to human with a note that the doc has no automatable novelty surface (distinct from I>0 inconclusive).

**Oracle-strength caveat (load-bearing, workspace rule 3).** P2's oracle is "the corpus of prior work accessed via search," which is WEAKER than psv's fetched primary source — at TWO layers. Per the spec-gaming paper §4.1's oracle levels and the fedaot-wiki `ai-coding-agent-maturity` §正交维度 (异源/different-family oracle forms — qualification criterion: the oracle's blind-spot set differs from the agent's): a fetched authoritative source is strong-decoupling at the FETCH step but tier-2 partial under model-mediated COMPARISON (psv §3 carries this Precision — fetched prose is externally authored but not formal). A SEARCH RESULT adds a SELECTION-side weakness on top of that comparison-side weakness — ranking bias, recall limits (you cannot search the whole corpus), and the found text is itself model-extracted. So P2 is weaker at two layers, not "weak oracle vs strong oracle." P2's value is honest-coverage-disclosure (a rule-3 instrument), NOT strong decoupling — the weaker oracle is precisely why P2 NEVER emits `novel_confirmed` and why its top-line is a coverage statement, not a verdict. `clear-under-search` means "no collision in what was searched," not "novel." This is the irreducible limit of novelty-checking short of a human.

Schema (mirrors psv's split — findings + record):
- `collision-findings` (extends psv's LANDED doc-findings — a strict superset: psv's 9 kinds preserved + `claim-collision` + `claim-uncited-relevant` + `claim-inconclusive`): severity collision = `blocker`, uncited-relevant = `warning`, inconclusive = `coverage` (parity with psv's `claim-unverifiable` — 3 finding-emitting verdicts of 4, like psv; `clear-under-search` is counted only, like psv's `verified`). Each collision/uncited-relevant finding MUST include a fetched QUOTE from the found prior art (URL / arXiv / repo) + why it collides — mirroring psv's fetched-quote invariant (a format-only cite is insufficient). A collision verdict is definitive in-schema — the found prior art already makes the claim (paralleling psv's `claim-refuted`). The false-positive structural-proxy risk (a quote is supplied but may be misread / over-interpreted) is recorded as an ADR (§8 Q6), NOT folded into the severity — so the blocker stands definitively (like psv) while the proxy limit is named separately (cf. psv ADR #2).
- `collision-record` (new, analogous to psv's coverage-record): `collisions_under_known_coverage` + counts (N/U/C/I of M) + `rightness: human_confirm_required`. NEVER `novel_confirmed`.

## 4. What stays put (Phase A does NOT touch)

- `cross-source-review/` unchanged. P2 is additive; csr remains the process-axis convergence engine.
- `primary-source-verification/` unchanged. P2 and psv are complements: psv verifies CITED sources (backward, fetched); P2 hunts UNCITED prior art (backward, search). They do not merge.
- `blueprint-crafting/` unchanged, including its `researcher` (forward gather; distinct direction).
- `parallel-development/` unchanged.

## 5. Layering

The family's outcome axis now has TWO skills: psv (cited-source verification) + P2 `prior-art-search` (uncited-prior-art collision). Both are per-claim, both outcome-axis, both honest-coverage, both NEVER emit a truth/novelty boolean. They compose: a high-stakes doc may run psv (are the cited sources accurate?) AND P2 (are the novelty claims collision-free against findable prior art?). SolidForge's two-axis doc-convergence frame (process × outcome) — whose orthogonal-axis PATTERN draws from the spec-gaming paper §3.3 (flow-control completeness × verification-source decoupling) + §4.2 (the Process/Outcome schema split), and the fedaot-wiki maturity page §正交维度 — now spans the outcome axis with two specialized legs.

Novelty-tier mapping (one term per tier, workspace rule 10):

| Tier signal | Owner skill | Meaning |
| --- | --- | --- |
| `substantive_converged` | cross-source-review | doc is well-formed, internally consistent, citation-structured, core-claims coverage-reviewed |
| `oracle_verified_under_known_coverage` | primary-source-verification | per-claim verdicts grounded in fetched sources, with declared coverage |
| `collisions_under_known_coverage` | prior-art-search (this skill) | novelty claims checked against the searchable prior-art corpus; N collisions surfaced, never novel_confirmed |
| `human_confirm_required` | human | the residue no machine oracle adjudicates (incl. true novelty + significance) |

## 6. Workspace-rule implications

- Rule 3 (never silently green) is load-bearing for P2. The `collisions_under_known_coverage` disclosure IS the rule-3 instrument: P2 states exactly what it searched + found, and degrades `inconclusive` / `clear-under-search` honestly, never to a silent `novel_confirmed`.
- Rule 6 (ADR). The "never `novel_confirmed` / absence-of-evidence limit" decision is non-obvious (the instinct is to want a novelty verdict); it gets an ADR (§8).
- Rule 10 (terminology). `collisions_under_known_coverage` is the one term for P2's top-line; `novel_confirmed` is the forbidden term and never appears as an emitted field.

## 7. Bootstrap (Phase A implementation — out of scope for this proposal)

Listed for sizing only; this proposal does not build it. Phase-A work-items would include: a novelty-claim-extraction prompt/agent; multi-source search tooling (reuse fetch + web-search primitives; the search-oracle weakness is inherent, not fixable); the schema extension (collision-findings + collision-record); a self-gate asserting every collision/uncited-relevant finding carries a fetched-source QUOTE (the rule-3 fetched-quote invariant, mirroring psv's `fetched_quote_gate`); `plugin.json` + `SKILL.md`. Each is a bc-style work-item in a future `iteration-plan.md`, not pre-committed here.

## 8. Decisions proposed this round (still reviewable)

- **Q1 — Name.** LOCKED `prior-art-search` (2026-08-05, human-LOCK). The skill's working name through convergence was `novelty-coverage`, but that name failed a human-usability review: `novelty` is the right concept (the field's term), but `coverage` is INTERNAL jargon — it names the `_under_known_coverage` output signal — so `novelty-coverage` reads as opaque to a human ("novelty coverage of what?"). Renamed to `prior-art-search`: the field's standard term (USPTO/EPO — "prior art search" = any evidence the idea is already known; interchangeable with "novelty search"), instantly recognizable to the target audience (a researcher/writer asking "is my 'this is new' claim already out there?"), with NO novelty-verdict implication (search ≠ judge), and it mirrors the sibling `primary-source-verification` honestly — psv VERIFIES the doc's CITED sources (backward-cited) ↔ prior-art-search SEARCHES for UNcited prior art (backward-uncited). Rejected: `novelty-verification` (implies a novelty verdict — the §2 category error; never `novel_confirmed`); `novelty-coverage` (the converged working name — retired: `coverage` is internal jargon, not a human word); `prior-art-check` (considered; `prior-art-search` preferred as the established field term + the verify↔search, cited↔uncited symmetry). The output CONTRACT is unchanged by the rename: signal `collisions_under_known_coverage`, forbidden `novel_confirmed` (these are the skill's OUTPUT, independent of its NAME).
- **Q2 — Scope.** Backward prior-art collision ONLY. Rejected: a combined novelty+significance verdict (significance is permanent human non-goal).
- **Q3 — Signal.** `collisions_under_known_coverage`, never `novel_confirmed`. The coverage disclosure, not a verdict, is the contract.
- **Q4 — Oracle.** The searchable prior-art corpus (WEAKER than psv's fetched source — §3 oracle-strength caveat). Rejected: treating search as equivalent to a fetched authoritative source.
- **Q5 — Relation to psv / researcher.** Additive + direction-distinct. psv = backward-cited; P2 = backward-uncited; researcher = forward-gather. P2 merges with neither.
- **Q6 — Collision severity + the false-positive structural-proxy.** A collision finding carries `blocker` severity (definitive in-schema — the prior art makes the claim, paralleling psv's `claim-refuted`). The fetched-quote gate is a STRUCTURAL PROXY (a quote is supplied), NOT a semantic proof the collision is genuine — a false-positive (quote misread / collision over-interpreted) is residual risk the format gate does not catch (mirrors psv ADR #2's structural-proxy posture). The proxy limit is recorded HERE (this ADR), NOT folded into the severity, so the blocker stands definitively while the limit is named honestly (rule 3 + rule 6).
