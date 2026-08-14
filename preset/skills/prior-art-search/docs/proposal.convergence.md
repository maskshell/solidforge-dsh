# prior-art-search proposal — cross-source-review convergence record

> Process-axis convergence record for `proposal.md`. Produced by `solidforge:cross-source-review`
> (同源 same-family `doc-reviewer` + 异源 different-family DeepSeek, orchestrator-driven).
> Process-axis only. Outcome-axis (is the design sound / the right skill) stays human — `rightness: human_confirm_required`.

## Verdict

- **substantive_converged (process-axis): true**
- size_tier: short · cap: 2 · rounds run: 2 · stalemate: false
- rightness: `human_confirm_required` (constant)

The core claims are coverage-verified AND no new Blocker-class finding appeared for ≥2 rounds. Round-1 findings (12) + round-2 findings (1 adopted) were all advisory (warnings/coverage) — never a Blocker.

## Schema-conformant record

```json
{
  "artifact": "skills/prior-art-search/docs/proposal.md",
  "authority_ref": "spec-gaming paper §3.3/§4.1/§4.2 + fedaot-wiki ai-coding-agent-maturity §正交维度 + psv proposal/landed schemas + outcome-axis backlog + CLAUDE.md rule 13",
  "size_tier": "short",
  "cap": 2,
  "substantive_converged": true,
  "rightness": "human_confirm_required",
  "stalemate": false,
  "core_claims": [
    "P2 is backward uncited-prior-art collision — distinct from psv (backward cited) + researcher (forward gather)",
    "never novel_confirmed; sole top-line signal collisions_under_known_coverage (absence-of-evidence limit)",
    "P2's search oracle is weaker than psv's fetched source at TWO layers (fetch-strong/comparison-partial + selection-weakness)",
    "collision-findings extends psv's LANDED doc-findings (strict superset: psv's 9 + claim-collision/uncited-relevant/inconclusive)",
    "P2 cleared its readiness gate (worked-example surfaced Verification/Self-Critique Paradox as uncited prior art)"
  ],
  "rounds": [
    {
      "round": 1, "same_source_findings": 9, "hetero_findings": 3, "hetero_degraded": false, "blockers": 0, "verdict": "rewrite",
      "detail": "同源 9 (W1 binary-oracle, W2 yield-caveat, W3 inconclusive-not-a-finding, W4 unqualified-model-recall, C1 value-synthesis, C2 rule-13-label, C3 term-drift, C4 unglossed-异源, C5 strict-superset-unverifiable) + 异源 3 (hetero-W1 §3.3/§4.2 axis conflation, hetero-C1 collision false-positive risk, hetero-C2 M=0 edge). All 12 adopted + fixed. 0 blockers."
    },
    {
      "round": 2, "same_source_findings": 2, "hetero_findings": 0, "hetero_degraded": false, "blockers": 0, "verdict": "pass",
      "detail": "r2-severity-tension (collision=blocker vs 'never proven' undercut — adopted: moved false-positive risk to ADR §8 Q6, kept collision=blocker definitive, mirroring psv ADR #2). r2-axis-attribution (coverage, RESOLVED: P2 §5 correct per the paper — §3.3=flow-control×decoupling, §4.2=Process/Outcome split; the §3.3/§4.2 conflation lives in psv's ADR #3, a psv-side follow-up, not a P2 defect). 0 blockers."
    }
  ],
  "coverage": [
    "Round-1 异源 (DeepSeek) fell_back_to_unstructured (--json-schema retries exhausted; defensive parse recovered valid findings) — not a DEGRADE.",
    "r2-axis-attribution RESOLVED by orchestrator verification against the spec-gaming paper: P2 §5 correctly distinguishes §3.3 (two-axis frame: flow-control completeness × verification-source decoupling) from §4.2 (Process/Outcome schema split). psv's design-decisions.md ADR #3 conflates these ('§3.3 names flattening process+outcome') — a psv-side citation-precision fix for a future pass, NOT a P2 defect.",
    "The spec-gaming paper is a fedaot-wiki draft (not open-web findable); both legs accessed it via the local path / orchestrator supply. The fedaot-wiki maturity page was consulted via MCP. P2's citations to both verified.",
    "Process-axis only — does NOT validate P2's architectural soundness or whether it is the right skill (outcome-axis, human)."
  ]
}
```

## Round-by-round blocker trend

| Round | same-family | different-family | new Blockers | verdict |
| --- | --- | --- | --- | --- |
| 1 | 9 | 3 | 0 | rewrite |
| 2 | 2 | 0 | 0 | pass |

Blocker trend: R1 = 0 → R2 = 0. All findings advisory. Core claims coverage-verified.
