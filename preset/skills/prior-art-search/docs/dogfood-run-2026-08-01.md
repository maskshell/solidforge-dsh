# prior-art-search — live dogfood coverage profile (2026-08-01)

> The live N≥3 dogfood (the human acceptance gate; the offline `dogfood.py` covers only the
> canonical fixture). Run by the orchestrator on 3 real artifacts via the full pipeline
> (`solidforge:novelty-claim-extractor` → `search_prior_art.py` → `solidforge:collision-verifier`
> per claim → `coverage_driver.py`). Oracle = arXiv open API (credential-free); no web-search
> key was set, so the web path was skipped — this is an arXiv-only run (a recall-limited,
> ranking-biased selection — the selection-side oracle weakness, design-decisions.md ADR #4).

## Scope + honest limits

- Each artifact ran a **focused subset** of its admissible novelty claims (the highest-stakes
  central claims + the known-collision target), NOT all extracted claims — a full per-claim run
  is the cost-bounded Phase-B path. `M` below = claims actually searched this run.
- The extractor (same-family) and collision-verifier (same-family) blind spots apply (ADR #38).
- `novel_confirmed` never appears in any record; every collision/uncited-relevant finding cites a
  fetched prior-art quote (the fetched-quote invariant held).

## Records (collisions_under_known_coverage)

| Artifact (admissible / searched) | C clear | N collision | U uncited-rel | I inconclusive | M | findings | escalate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| spec-gaming paper (43 / 5) | 4 | 0 | 1 | 0 | 5 | 1 (NC34) | 0 |
| csr proposal (8 / 3) | 1 | 0 | 0 | 2 | 3 | 2 (NC1, NC4) | 2 |
| psv proposal (6 / 2) | 1 | 0 | 1 | 0 | 2 | 1 (NC2) | 0 |
| **totals** | **6** | **0** | **2** | **2** | **10** | **4** | **2** |

## Findings surfaced (fetched prior-art quotes)

- **spec-gaming NC34** (`uncited-relevant`, warning) — SWE-ABS (arXiv:2603.00520): *"one in five
  'solved' patches from the top-30 agents are semantically incorrect, passing only because weak
  test suites fail to expose their errors."* Adjacent to the paper's Axis-B benchmark claim
  (SWE-Bench inflation); differs in threat model (weak-test slack vs spec-gaming/intent violation)
  and lacks the two-axis framing. Recommend the paper cite + distinguish it in §5/§8.3.
- **psv NC2** (`uncited-relevant`, warning) — AI-Powered Citation Auditing (arXiv:2511.04683):
  *"20% of citations contain errors... a novel AI-powered methodology for systematic, comprehensive
  reference auditing using agentic AI."* Same domain as psv (agentic citation auditing) + a
  population error stat; does NOT make psv's coverage-disclosure (N/R/W/K of M, never boolean
  correctness) claim. Recommend psv cite + distinguish it.
- **csr NC1, NC4** (`inconclusive`, coverage → escalate) — the arXiv query returned only off-domain
  keyword noise (geometry, endoscopy, financial-LLM); the search could not cover the claims' domain,
  so no collision could be adjudicated. Distinct from clear-under-search: csr NC3's search DID
  surface an in-domain candidate (Review Arcade) → clear-under-search (no collision among what was
  searched).

## Notable honest result — the known-collision target

The spec-gaming paper's **self-certification-paradox** claim (NC7) — the readiness-gate's 2026-07-31
*web* search surfaced the "Verification Paradox" / "Self-Critique Paradox" framings as uncited prior
art — came back **clear-under-search** in this arXiv-only run: the query returned LLM-as-a-Verifier
(a scaling-axis framing, not the shared-blind-spot thesis) + 2 unrelated hits. The arXiv-only oracle
did not recall those framings. This is the two-layer oracle weakness demonstrated in production: a
zero-collision result is "no collision in what was searched," NOT "novel." A web-search key
(`PRIOR_ART_SEARCH_API_KEY`) or a different-family extraction leg would broaden recall.

## Acceptance

- N≥3 real artifacts run (incl. the long spec-gaming doc). ✓
- ≥1 real finding surfaced via fetched prior art — 2 uncited-relevant (NC34, psv-NC2) + 2
  inconclusive escalations. ✓
- The fetched-quote invariant held on every collision/uncited-relevant finding; `novel_confirmed`
  never emitted. ✓
- Rightness stays `human_confirm_required`: whether these docs are genuinely novel is NOT
  adjudicated (outcome-axis — human). The findings are coverage disclosures, not novelty verdicts.

## Broader-oracle re-run (web search + paper fetch — the "kindly web/paper search" pass)

The arXiv-only oracle left the known-collision target (NC7) at clear-under-search and several
queries returned off-domain noise. Re-running the collision-verifiers with the orchestrator's
broader web/paper search (web-search-prime + web-reader MCP; the skill's `search_prior_art.py`
is arXiv-only — the orchestrator's built-in search is the broader channel per SKILL.md) **dramatically
improved recall** and is the clearest possible demonstration of the two-layer oracle weakness:
the same claims, same comparator, different (broader) oracle → materially different verdicts.

| Artifact (web oracle) | C | N (collision) | U | I | M | findings | blocker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| spec-gaming paper | 1 | **1** | 3 | 0 | 5 | 4 | **1** |
| csr proposal | 0 | 0 | 3 | 0 | 3 | 3 | 0 |
| psv proposal (arXiv run; not re-run) | 1 | 0 | 1 | 0 | 2 | 1 | 0 |
| **totals** | **2** | **1** | **7** | **0** | **10** | **8** | **1** |

Upgrades the broader oracle surfaced (all with fetched quotes):
- **NC34 → COLLISION (blocker):** SpecBench (arXiv:2605.21384) — *"whether coding agents build
  genuine working systems or merely game the test suites developers hand them"* + "reward hacking
  gap" (proxy vs spec). SpecBench already IS the Axis-B benchmark NC34 claims is required; the
  arXiv-only run had found only the weaker SWE-ABS (uncited-relevant).
- **NC7 → uncited-relevant:** the exact-term **Self-Certification Paradox** (Brilliant 2026,
  preprints 202601.0892 — Lemma 2 bounds repeated self-critique by the shared failure variable)
  + **Self-Critique Paradox** (Snorkel) + **Verification Paradox** (YAI HQ) + Self-Correction
  Blind Spot (Tsui arXiv:2507.02778). The general paradox is prior art; NC7's contribution narrows
  to the coding-loop application.
- **NC1 → uncited-relevant:** MAST taxonomy + Microsoft failure-mode taxonomy already list
  specification issues as a distinct category (the orthogonality/irreducibility thesis stays the
  paper's own).
- **NC14 → uncited-relevant:** "Towards a Science of AI Agent Reliability" (arXiv:2602.16666)
  establishes the process-vs-outcome distinction (the schema-level never-auto-satisfied invariant
  stays the paper's own).
- **csr-NC1, NC3, NC4 → uncited-relevant** (resolved the two inconclusives): ReConcile
  (arXiv:2309.13007, ACL 2024, 381 citations) — *"multi-model multi-agent framework… round table
  conference among diverse LLM agents… multiple rounds of discussion… confidence-weighted voting… a
  better consensus"* — is the multi-round-cross-family-consensus home csr's "no home" / convergence
  claims must cite+distinguish; "Cross-Model LLM Code Review" (arXiv:2607.21656) grounds csr-NC3's
  conceded "exists for code" premise.

Tooling note: the `kindly` / `kindly-papers` MCP **search** returned empty/errors in this environment
(no working Serper/Tavily key; SearXNG 302), so search used the orchestrator's native WebSearch;
`kindly-papers get_content` (full-PDF fetch, a different code path) DID work and supplied the
ReConcile + Brilliant full text (richer than abstracts). This is itself an ADR #4 finding: the
oracle's reach is bounded by whichever search channel is live.

**Honest reading:** the broader oracle turned 1 finding into 5 (incl. 1 blocker) on the spec-gaming
paper alone. This is exactly the selection-side weakness named in design-decisions.md ADR #4: the
arXiv-only oracle's recall was the bottleneck, not the comparator. Setting `PRIOR_ART_SEARCH_API_KEY`
(wiring `search_prior_art.py`'s web path) or routinely augmenting with the orchestrator's web search
is the single highest-leverage improvement. `novel_confirmed` STILL never emitted — a zero-collision
result remains "no collision in what was searched," not "novel," and the blocker is a coverage finding
(the doc overstates novelty), not a novelty verdict.

Raw records: `/tmp/nc-dogfood/records/{specgaming,csr,psv}{,_web}.json` (run artifacts; not committed).

