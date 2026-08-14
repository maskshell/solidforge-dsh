# primary-source-verification proposal — cross-source-review convergence record

> Process-axis convergence record for `proposal.md`. Produced by `solidforge:cross-source-review`
> (同源 same-family `doc-reviewer` + 异源 different-family DeepSeek, orchestrator-driven).
> Process-axis only. Outcome-axis (is the design sound / the right skill) stays human — `rightness: human_confirm_required`.

## Verdict

- **substantive_converged (process-axis): true**
- size_tier: short · cap: 2 · rounds run: 2 · stalemate: false
- rightness: `human_confirm_required` (constant — a green process axis never changes this)

The core claims are coverage-verified AND no new Blocker-class finding appeared in the cap round
(round 2, both legs). Round-1 blockers (F1, F2) were fixed and re-verified in round 2.

Coverage caveat on the convergence criterion (workspace rule 3): the long-tier "≥2 clean rounds"
standard is unsatisfiable within cap=2 when round 1 carries blockers (it would require a 3rd round
over cap). The short-tier criterion applied here = the cap round is clean (0 new blockers across both
legs) AND all prior blockers fixed + re-verified. A human may opt for one extra confirmatory round to
meet the strict 2-clean-rounds standard; absent that, process-axis convergence is declared.

## Schema-conformant record

```json
{
  "artifact": "skills/primary-source-verification/docs/proposal.md",
  "authority_ref": "spec-gaming paper (local fedaot-wiki draft; verified 2026-07-31); + csr infra/schemas + repo CLAUDE.md",
  "size_tier": "short",
  "cap": 2,
  "substantive_converged": true,
  "rightness": "human_confirm_required",
  "stalemate": false,
  "core_claims": [
    "Q1 name consistent with family <domain>-<activity> pattern (descriptive, not codified)",
    "CaMeL arXiv:2503.18813 = prompt-injection defense; spec-gaming paper's CaMeL-lineage misattribution dropped",
    "Pan 2022: an 'irreducible' reading overclaims; paper §3.2(ii) narrows it; Pan proposes mitigations",
    "spec-gaming paper §3.3 two-axis frame + 'flatten two axes' category-error (phrase in abstract/§1)",
    "spec-gaming paper §4.1 decoupling criterion + level-3 'Formal (externally authored)' (formal artifacts, not fetched prose)",
    "spec-gaming paper §4.2 rightness schema: human_confirm_required / oracle_verified_under_known_coverage",
    "spec-gaming paper §3.2(iii) same-source-review ceiling",
    "GSME = arXiv:2607.13683 title (Self-Evolving Agent Harnesses via Gated Semantic Quality-Diversity)",
    "psv additive to csr; symmetric outcome-convergence mirror rejected (§3.3 category-error); significance permanent human non-goal",
    "workspace rules 3/6/10 + L1 naming red line exist as cited",
    "doc-findings extension: claim-refuted/claim-narrowed/claim-unverifiable kinds + separate coverage-record for top-line signal",
    "rightness-tier mapping: substantive_converged (csr) / oracle_verified_under_known_coverage (psv) / human_confirm_required (human)"
  ],
  "rounds": [
    {
      "round": 1,
      "same_source_findings": 10,
      "hetero_findings": 4,
      "hetero_degraded": false,
      "blockers": 2,
      "verdict": "rewrite",
      "detail": "同源 F1 (process_converged vs substantive_converged), F2 (§9 locked vs pending) = blockers, fixed. 同源 F3–F10 (warnings/coverage) + 异源 D1–D4 (level-3 formal-slot miscitation; extractor blind-spot; 'category error' section; undefined atomic/source-admissible) adopted. All fixed."
    },
    {
      "round": 2,
      "same_source_findings": 3,
      "hetero_findings": 3,
      "hetero_degraded": false,
      "blockers": 0,
      "verdict": "pass",
      "detail": "同源 confirmed all round-1 fixes sound; new r2-1 (§1 table not aligned to F6 prose), r2-2 (ADR cross-ref → §9 Q5 vs §2), r2-3 (orchestrator-only authority claims) — all advisory, fixed. 异源 h1 (paper process_converged machine-checkable vs csr substantive_converged LLM-judged), h2 (step-3 comparison blind-spot), h3 (narrowed is bounded-interpretive) — all advisory, fixed post-cap-round."
    }
  ],
  "coverage": [
    "Orchestrator primary-source verification (CSR Quick Start step 3): spec-gaming paper supplied by the user mid-round-1 (local fedaot-wiki draft, draft-cross-source-converged 2026-07-08); all 12 core claims verified against it. CaMeL arXiv:2503.18813 and arXiv:2607.13683 independently fetch-verified. Workspace rules 3/6/10 + L1 + csr schemas verified in-repo.",
    "HEADLINE FLIP — the psv thesis demonstrated live: the spec-gaming paper was 'unverifiable → human escalation' to every recall-based reviewer (same-family leg flagged it coverage; 5 open-web/arXiv search methods returned zero trace) and became adjudicable the MOMENT a primary source was fetched, with all attributions verifying. This validates the proposal's premise using the proposal's own review.",
    "A genuine terminology fork was surfaced and disclosed, not papered over: the spec-gaming paper §4.2 names the process tier 'process_converged' (machine-checkable, deterministic, tamper-proof) while csr's emitted field is 'substantive_converged' (LLM-adjudicated). The proposal now maps csr's field to the paper's tier and states the weaker structural guarantee explicitly (round-2 异源 h1).",
    "DeepSeek fell_back_to_unstructured both rounds (--json-schema structured-output retries exhausted; defensive parse used). Findings were valid and adopted; this is NOT a DEGRADE (degraded=false) — the wrapper's defensive parse recovered the findings.",
    "Round-2 异源 advisory findings (h1/h2/h3) were applied after the cap round as non-blocking improvements; no round 3 was run (cap=2 reached; no new Blocker). h1/h2/h3 strengthen psv's honesty contract (comparison-step blind-spot; tamper-resistance nuance) but do not affect the process-axis verdict.",
    "The spec-gaming paper is a DRAFT (authors TBD) — a weaker epistemic anchor than a peer-reviewed source. The proposal's framework is accurately derived from it, but the paper's own conclusions remain outcome-axis / human. This record does NOT validate the proposal's architectural soundness — process-axis only.",
    "Name (Q1) remains PROPOSED, not LOCKED — pending human lock per the proposal's own §9 Q1."
  ]
}
```

## Round-by-round finding trend

| Round | same-family | different-family | new Blockers | verdict |
| --- | --- | --- | --- | --- |
| 1 | 10 (F1–F10) | 4 (D1–D4) | 2 (F1, F2) | rewrite |
| 2 | 3 (r2-1..3) | 3 (h1–h3) | 0 | pass |

Blocker trend: R1 = 2 → R2 = 0. All round-1 blockers fixed and re-verified in round 2. Round 2
introduced no new blocker; its 6 findings were all advisory (warnings/coverage) and were adopted.

## Origin note

The spec-gaming paper was not findable on the open web or arXiv (it is a private fedaot-wiki draft).
The orchestrator's initial, honest verdict on the load-bearing citation was therefore `unverifiable →
escalate to human`. The user supplied the source mid-review; per-claim verification against it
confirmed every attribution. This is the exact `unverifiable → source fetched → verified` transition
the proposed skill exists to operationalize.
