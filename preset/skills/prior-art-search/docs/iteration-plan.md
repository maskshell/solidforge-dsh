# prior-art-search — Iteration Plan (Phase A)

> Based on `docs/proposal.md` (CSR SUBSTANTIVE-CONVERGED + psv N=9/K=0 verified, 2026-07-31;
> convergence records: `docs/proposal.convergence.md`). This plan is the **execution blueprint**.
> Structured like `primary-source-verification`'s plan (complexity tier + dependency edges +
> **validation gate** = the only "done" criterion — no calendar duration).
>
> **Authority chain**: `proposal.md` = authoritative design (master); this `iteration-plan.md` =
> execution blueprint (on conflict, **proposal.md wins**). The proposal's §8 decisions (Q1–Q6) are
> locked inputs; this plan shapes them into work-items, it does not re-debate them.

## 0. Background and scope

- Current state: proposal CSR-converged + psv-verified; **no `SKILL.md`, no schemas, no agents, no
  search/collision machinery, no self-gates**.
- Scope (Phase A): zero → a read-only, search-grounded, per-novelty-claim collision detector that
  drives a doc-shaped artifact's novelty claims against the **searchable prior-art corpus** and emits
  a per-claim collision packet plus an honest coverage disclosure. Additive to psv (cited-source
  verification); NEVER `novel_confirmed`.
- Architecture note (load-bearing): like psv, prior-art-search is a **single pipeline** (extract
  novelty claims → search → collision verdict → coverage disclosure), NOT a debate loop. The oracle
  is the **searchable prior-art corpus** — WEAKER than psv's fetched source at TWO layers
  (fetch-strong/comparison-partial + selection-weakness); this is the load-bearing honesty caveat
  (proposal §3, ADR §8 Q6).

## 1. Estimation gauge (no day counts)

| Dimension | Meaning | Use |
| --- | --- | --- |
| **Complexity tier** S/M/L/XL | search-tooling novelty × false-positive-risk × integration surface | per-iteration risk + gate density |
| **Dependency edge** | "X must exist before Y" | execution order + critical path |
| **Validation gate** | an objective "done" criterion: schema validates / shape-contract green / dogfood surfaces a real collision | the unit of progress |

## 2. Overview: iterations, complexity, dependencies, gates

| ID | Iteration | Complexity | Deps | Key validation gate |
| --- | --- | --- | --- | --- |
| NC-I0 | scaffold + `SKILL.md` + activation/scope-guard | M | — | `SKILL.md` loadable; Scope Guard routes code→pd, spec→bc, convergence→csr, citation-verify→psv, novelty-collision→this skill |
| NC-I1 | schemas (collision-findings extends psv's LANDED doc-findings + collision-record) | M | NC-I0 | both schemas validate; collision-findings = psv's 9 kinds + `claim-collision`/`claim-uncited-relevant`/`claim-inconclusive` (strict superset); collision-record carries `collisions_under_known_coverage`, NEVER `novel_confirmed` |
| NC-I2 | novelty-claim-extraction agent | M | NC-I1 | agent enumerates atomic novelty claims (location + search target); distinguishes novelty from factual/citation (psv) + interpretive (escalate) |
| NC-I3 | multi-source search + collision verdict comparator | L | NC-I1 | searches a claim's prior art; comparator assigns collision/uncited-relevant/clear-under-search/inconclusive with a fetched-source QUOTE for collisions (mirrors psv's fetched-quote invariant) |
| NC-I4 | coverage driver | L | NC-I2, NC-I3 | drives extract→search→verdict→coverage; emits collision-record (N/U/C/I of M); M=0 escalates; NEVER `novel_confirmed` |
| NC-I5 | self-gates + standard set | L | NC-I4 | (a) collision fetched-quote invariant gate; (b) shape-contract; (c) coverage-policy (counts sum; no `novel_confirmed`; M=0/K>0 escalate) + standard |
| NC-I6 | dogfood + 质量稳定 gate | M–L | NC-I5 | N≥3 real artifacts (≥1 with a known prior-art collision the skill catches); record coverage profile |

## 3. Foundation layer (NC-I0–NC-I1)

### NC-I0 scaffold + `SKILL.md` + scope-guard — M
- **Goal**: a loadable skill skeleton with the correct scope + honest activation.
- **Deliverables**: `prior-art-search/SKILL.md` (description declares the per-novelty-claim collision scope; Scope Guard routes code→pd, spec→bc, convergence→csr, cited-source→psv, novelty-collision→this skill; states NEVER `novel_confirmed`).
- **Done when**: `SKILL.md` loadable; Scope Guard emits correct routing; the never-novel_confirmed + weaker-oracle positioning stated honestly.
- **Basis**: proposal §1, §2, §3, §8 Q1/Q2/Q3.

### NC-I1 schemas — M
- **Goal**: the two data contracts.
- **Deliverables**:
  - `infra/schemas/collision-findings.schema.json` — copy psv's LANDED `doc-findings.schema.json`, extend `kind` with `claim-collision`/`claim-uncited-relevant`/`claim-inconclusive` (strict superset — psv's 9 preserved byte-for-byte); severity collision=`blocker`, uncited-relevant=`warning`, inconclusive=`coverage`.
  - `infra/schemas/collision-record.schema.json` — `collisions_under_known_coverage` (the sole top-line, `const`) + N/U/C/I of M=N+U+C+I counts; `rightness: human_confirm_required`; `novel_confirmed` forbidden.
- **Done when**: both schemas validate; collision-findings kind = psv's 9 + 3; collision-record never carries `novel_confirmed`; M=N+U+C+I invariant stated.
- **Basis**: proposal §3 schema, §8 Q6.

## 4. The pipeline legs (NC-I2–NC-I3)

### NC-I2 novelty-claim-extraction agent — M
- **Goal**: enumerate the novelty-claim set.
- **Deliverables**: an agent that reads the artifact + emits atomic novelty claims (each: location + search target). Distinguishes novelty claims ("X is new") from factual/citation claims (psv's domain) + interpretive (escalate). Extractor blind-spot caveat (rule 3).
- **Done when**: on a fixture doc, returns novelty claims each with a search target; a planted interpretive claim is tagged inadmissible.
- **Basis**: proposal §3 step 1.

### NC-I3 multi-source search + collision comparator — L
- **Goal**: the search oracle + per-claim collision verdict.
- **Deliverables**: a search unit (web/arXiv/repo search per claim → candidate prior art) + a comparator that assigns collision/uncited-relevant/clear-under-search/inconclusive, emitting a collision-finding whose `evidence` QUOTES the found prior art (mirrors psv's fetched-quote invariant). Comparison blind-spot caveat (rule 3). **Credential surface (cf. psv PSV-I3 novel-1):** open search (arXiv abstracts, public repos) needs no credential; web-search APIs use a separately-named API-key surface (NOT csr's `_ANTHROPIC_AUTH_TOKEN` LLM-token namespace); the isolation boundary is resolved at implementation (NC-I3), not silently treated as settled.
- **Done when**: on a fixture novelty claim + a known colliding prior art, returns `claim-collision` with a fetched quote; on a claim with no findable prior art, returns `clear-under-search` (NOT `novel`).
- **Basis**: proposal §3 steps 2–3, §8 Q6 (false-positive structural-proxy ADR).

## 5. Coverage driver + self-gates + dogfood (NC-I4–NC-I6)

### NC-I4 coverage driver — L
- **Goal**: orchestrate extract → search → verdict → coverage.
- **Deliverables**: a driver emitting the collision-record (`collisions_under_known_coverage`: N/U/C/I of M) + the collision-findings packet; NEVER `novel_confirmed`; M=0 escalates ("no novelty surface"); a collision finding without a fetched quote is rejected (downgrade path).
- **Done when**: on a fixture doc with a planted collision, emits `claim-collision` + a record whose counts include it; on M=0, escalates honestly.
- **Basis**: proposal §3 step 4.

### NC-I5 self-gates — L
- **Deliverables**: (a) collision fetched-quote invariant gate (every collision/uncited-relevant finding carries a fetched-source quote; quote-less → inconclusive); (b) shape-contract; (c) coverage-policy (M=N+U+C+I; no `novel_confirmed`; M=0/I>0 escalate) + standard (`disconnect_check`/`plugin_layout`/`lint_self`).
- **Done when**: all gates green; (a)'s downgrade path exercised.

### NC-I6 dogfood — M–L
- **Deliverables**: run on N≥3 real artifacts (≥1 a **long doc** — mirroring psv PSV-I6; the spec-gaming paper collision-catch run satisfies this, being long + the known-collision target), incl. ≥1 with a KNOWN prior-art collision (the spec-gaming paper — re-run the worked example as a real collision report); record a coverage profile.
- **Done when**: ≥1 real collision surfaced via fetched prior art; profile recorded.

## 6. Phase-A acceptance gate
- prior-art-search drives extract→search→collision→coverage on a real doc, emitting an honest collision-record + findings whose every collision carries a fetched-quote.
- All self-gates green; the collision fetched-quote invariant exercised.
- N≥3 dogfood (incl. ≥1 collision-catch) recorded.
- collision-findings is a strict superset of psv's (9 psv kinds preserved); collision-record never carries `novel_confirmed`.
- Doc-audit (rule 5): family layering docs gain the collision-coverage tier.

## 7. Dependencies and parallelism (DAG)
```text
NC-I0 scaffold ─▶ NC-I1 schemas ─┬─▶ NC-I2 novelty-claim-extraction ─┐
                                  └─▶ NC-I3 search + comparator ──────┤
                                                       ▼
                                          NC-I4 coverage driver ◀── (NC-I2 + NC-I3)
                                                       ▼
                                          NC-I5 self-gates
                                                       ▼
                                          NC-I6 dogfood + 质量稳定
                                                       ▼
                                          Phase-A acceptance gate
```

## 8. Risks and mitigations
| Risk | Iteration | Mitigation |
| --- | --- | --- |
| mistaken for a novelty-verdict skill (the category error) | NC-I0 | SKILL.md + `collisions_under_known_coverage` signal (never `novel_confirmed`) + §2 non-goal up front |
| collision-findings drifts from psv's (breaks strict-superset) | NC-I1 | copy psv's LANDED schema verbatim then ADD 3 kinds; gate asserts psv's 9 preserved |
| false-positive collision (misread/over-interpreted quote) slips as a blocker | NC-I3/NC-I5 | collision fetched-quote invariant gate + the §8 Q6 structural-proxy ADR (limit named, not folded into severity) |
| novelty-extraction blind-spot: a real novelty claim never extracted → absent from M | NC-I2 | extractor blind-spot caveat (rule 3); different-family extraction deferred (partial mitigation) |
| search-oracle weakness conflated with psv's fetched oracle | NC-I0/§3 | the two-layer oracle caveat (fetch-strong/comparison-partial + selection-weakness) stated in SKILL.md + proposal §3 |
| search result is model-extracted, not fetched authoritative | NC-I3 | disclose (rule 3); collision findings require a fetched QUOTE of the found text, not just a search-snippet |

## 9. Out of scope (Phase A)
- A `novel_confirmed` verdict (the absence-of-evidence limit — permanent).
- Argument soundness / correctness (P3-reclassified-to-csr-mode / psv / human).
- Significance assessment (permanent human non-goal).
- Exhaustive prior-art search (search has recall limits — disclosed).
- Any change to csr/psv/bc/pd core logic (additive).

## 10. Cross-cutting tasks
| Task | Starts at | Note | Rule |
| --- | --- | --- | --- |
| copy-patterns-not-code | NC-I1 | collision-findings copied from psv's LANDED schema (extended, not imported) | rule 7 |
| collision fetched-quote honesty | NC-I3/NC-I5 | every collision finding cites fetched prior-art text; quote-less → inconclusive | rule 3 / L1 |
| ADR log | NC-I1 | `design-decisions.md`; non-obvious decisions get an ADR (never-novel_confirmed, the false-positive structural-proxy, the two-layer search-oracle weakness, the relation to psv/researcher) | rule 6 |
| doc-audit (rule 5) | NC-I0 | family layering docs gain the collision-coverage tier | rule 5 |
