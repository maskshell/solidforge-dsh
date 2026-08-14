# converge.py fixtures (CSR-I4)

Offline inputs for `converge.py build-record` (CSR-I4). Reused by the CSR-I5 offline
convergence-policy gate (mirrors `parallel-development`'s
`infra/test/hetero_review_wiring.py` pattern — fixtures first, then assert the
emitted record's verdict fields). Pure data — no LLM, no network.

## Run

```bash
python3 infra/scripts/converge.py build-record --input infra/scripts/converge_fixtures/<case>.json
```

Each fixture is a `run.json` (shape: `proposal.md` §3 + `iteration-plan.md` §CSR-I4).
The emitted record validates against `infra/schemas/convergence-record.schema.json`.

## Cases + expected outcomes

| Fixture | Tier / cap | Rounds | new-blockers/round | core_claims | Expected `substantive_converged` | Expected `stalemate` | Prong exercised |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `converged.json` | short / 2 | 2 | 0, 0 | a, b (both covered) | `true` | `false` | BOTH prongs pass |
| `stalemate.json` | short / 2 | 2 | 1, 1 | a (covered) | `false` | `true` | prong_b fails (last ≥2 rounds not both 0) |
| `core_claims_uncovered.json` | short / 2 | 2 | 0, 0 | a, b (only a covered) | `false` | `true` | prong_a fails (coverage prong is real, not cosmetic) |
| `degraded.json` | short / 2 | 2 | 1, 0 | (none) | `false` | `true` | reconciliation: hetero blocker dropped on `hetero_degraded=true`; coverage notes the degrade |
| `warnings_dont_block.json` | short / 2 | 2 | 0, 0 | a (covered) | `true` | `false` | rule 4 — warnings never block |

Per-round verdict assertions (`round.blockers` = count of NEW blockers that round):

| Fixture | Round 1 verdict / blockers | Round 2 verdict / blockers |
| --- | --- | --- |
| `converged.json` | pass / 0 | pass / 0 |
| `stalemate.json` | rewrite / 1 | rewrite / 1 |
| `core_claims_uncovered.json` | pass / 0 | pass / 0 |
| `degraded.json` | rewrite / 1 (same_only; het_dropped NOT counted) | pass / 0 |
| `warnings_dont_block.json` | pass / 0 (warnings never block) | pass / 0 |

## BOTH-prongs demonstration (CSR-I4 DoD)

- `converged.json` proves prong_a is satisfied when all core_claims are covered.
- `core_claims_uncovered.json` proves prong_a FAILS the run when a core_claim is
  uncovered — even with zero blockers in both rounds. Without this fixture, a
  no-new-Blocker-only implementation would silently pass (`prong_b` alone is
  insufficient). This makes the coverage prong load-bearing, not decorative.

## Pluggable-seam test (CSR-I4 DoD)

A finding that violates the schema's `$defs/finding` is REJECTED with a clear error
(rule 3 — never silently accept malformed input). Verified out-of-band by feeding a
finding missing the required `evidence` field and asserting a non-zero exit + a
`malformed finding(s) rejected` message naming the failing finding.

## Coverage-notes discipline (rule 3)

Every emitted record carries honest `coverage` notes:

- per degraded round: `round N 异源 degraded[: <subtype>]`
- `core-claims-coverage: <covered>/<total>` when core_claims is non-empty
- `cap=<cap>, rounds=<n>` always
