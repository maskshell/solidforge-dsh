---
title: spec-gaming paper — publication-readiness review + proposed fixes
status: csr-substantive-converged + psv-verified (N14/W0/R0/K0 against the paper); records in .csr/convergence-record.json + .csr/psv-coverage-record.json
authors: TBD
last_updated: 2026-08-06
source_doc: |
  Editorial/readiness assessment of docs/papers/spec-gaming-orthogonal-axis.md.
  Pending csr convergence + psv adjudication before any fix is applied.
citation_legend:
  "[paper:Lxx]": "docs/papers/spec-gaming-orthogonal-axis.md line xx"
  "[paper:§X]": "docs/papers/spec-gaming-orthogonal-axis.md section"
  "[reconv:...]": "docs/papers/spec-gaming-orthogonal-axis.loopx-reconvergence.json"
psv_scope_note: |
  psv adjudicates the review's FACTUAL/CITATION claims against the paper (the
  primary source). Normative claims (venue choice, framing advice, "should fix",
  "recommend") are outcome-axis (human) and NOT psv-admissible — tagged
  [advisory, not psv-admissible].
---

# Publication-Readiness Review: spec-gaming-orthogonal-axis.md

## Verdict (advisory, not psv-admissible)

Position-paper tier (arXiv / workshop / industry essay): publishable after 1 blocker fix + 3 warning fixes + a title/Abstract framing alignment. Top-tier research conference (ICSE/NeurIPS/FACCT main track): not yet — the paper itself states no empirical evaluation and names the §8.3 injection-set benchmark as the principal open problem.

## F1 (blocker) — §1 vs §4.4/§5 internal contradiction

- **Finding:** The unqualified universal "heterogeneous oracles forced out of process" appears in TWO places, both unqualified by oracle type: §1 contribution (iv) [paper:L39] ("any genuinely heterogeneous oracle is forced out of process") AND §3.3 [paper:L86] ("the agent harness forces heterogeneous oracles out of process precisely because in-process reviewers cannot differ in blind-spot set" — in the same sentence that cites §4.4). §4.4 [paper:L139] scopes the boundary to "**for model-based heterogeneous oracles**" with an in-process exception ("A formal or fetched-source oracle is an in-process exception... strong decoupling"); §5 [paper:L157] scopes likewise. So BOTH §1 and §3.3 contradict §4.4/§5. (The earlier `abs-contr-1` backlog named only §1/Abstract; the Abstract [paper:L20] in fact lacks the literal phrase, and §3.3 L86 is a second carrier the backlog missed — caught by this review's csr R1.)
- **Proposed fix (advisory):** qualify BOTH locations — §1 [paper:L39] and §3.3 [paper:L86] — "heterogeneous oracle" → "heterogeneous **model-based** oracle (a deterministically-adjudicated fetched-source oracle is the in-process exception, §4.4)". Patching only §1 leaves the §3.3 contradiction live.
- **Claim (psv-admissible):** the Abstract [paper:L20] contribution (iv) does NOT contain the "forced out of process" phrase; it states the softer "enforce this separation under current architecture... converting what would be a bypassable convention into an implementation-level invariant." (If true, the 2026-08-04 hetero finding over-attributed the universal to the Abstract; the contradiction is located in §1, not the Abstract.)

## F2 (warning) — §8 missing self-certification-conjecture testability item

- **Finding:** §3.1 [paper:§3.1, ~L65] stipulates the strong-form self-certification conjecture as load-bearing for the necessity framing ("logically necessary", §3.1 L65) and explicitly flags it as stipulative rather than established, including a weak-form fallback. §8 Open Problems [paper:§8, L199–207] enumerates 7 items but contains none on empirically testing or falsifying that conjecture.
- **Proposed fix (advisory):** add §8.8 — empirically testing the strong-form conjecture (e.g., same-family-fresh-context vs cross-family verdict divergence on a known latent-proxy-gap test set).

## F3 (warning) — §3.2(ii) causal-disjointness premise unsupported

- **Finding:** §3.2(ii) [paper:~L73] asserts "The three intrinsic modes are **physical manifestations of two properties** — the model's probabilistic nature and its bounded attention — over long sequences" as the load-bearing premise for the causal-disjointness step ("Because the causal mechanisms are disjoint..."), with no citation or argument. §2 [paper:~L49] explicitly declines to attribute the three-mode taxonomy to a single named source.
- **Proposed fix (advisory):** either support the two-property reduction (citation or per-mode argument) or hedge it as an analytical assumption, parallel to §3.1's conjecture flag.

## F4 (warning) — §6 "two cases" unidentified

- **Finding:** §6 [paper:L163] says SolidForge's "design choices are consistent with — and in two cases concretely instantiate — the claims of §3–§4" but never names which two. The §6 subsections each assert a distinct relation ("This is §4.2 in production"; "consistent with §4.4's platform-observed boundary"; "This defends salient specification gaming (§4.3)"; "operationalizes the two-axis frame (§3.3)").
- **Proposed fix (advisory):** name the two cases explicitly — e.g., "the Process/Outcome split (§4.2) and the cross-provider heterogeneous ring (§4.4) concretely instantiate §4.2 and §4.4 respectively."

## F5 (structural, advisory, not psv-admissible) — title/Abstract confidence vs stipulated premise

- **Observation:** the title "Specification Gaming as an **Orthogonal** Failure Axis" is silent on the stipulation, and the Abstract's OPENING "incomplete in a **precise** sense" precedes the mid-Abstract clause that does flag it ("under the self-certification conjecture of §3.1, stipulated rather than established" [paper:L20]). The stipulation is in fact foregrounded in Abstract L20, §1 L32, §3.1 L65, §4.1, §4.4 (NOT buried), with a weak-form fallback that downgrades "logically necessary" to "strongly advisable". So the concern is narrower than "buried": the TITLE doesn't flag it and the Abstract opening asserts precision before the stipulation clause appears.
- **Proposed fix (advisory):** either (a) foreground the stipulation in the Abstract (one clause: "under the self-certification conjecture of §3.1, stipulated rather than established"), or (b) soften "orthogonal" to "orthogonal under the conjecture" in title/body. (This is a framing/positioning judgment — outcome-axis, human.)

## F6 (mechanical) — provenance items for submission

- **Claim (psv-admissible):** `authors: TBD` [paper:L2].
- **Claim (psv-admissible):** SolidForge is cited as a private repo: "Repository: ws-ai/solidforge (private)" [paper:L227]. Consequence (advisory): §6's existence-proof is not independently verifiable by a reviewer.
- **Claim (psv-admissible):** the frontmatter [paper:L5–11] is a multi-paragraph internal convergence/csr/psv process log (not publication metadata).
- **Claim (psv-admissible):** the "loop engineering" primary citation (Osmani 2026) [paper:References] is a blog post.
- **Coverage note (csr R1 hetero):** the review's "citation grounding psv-verified" assertion is grounded only in the paper's frontmatter RECORD of the 2026-07-31 psv run (N=7/W=1/K=0 of M=8) — not a fresh psv re-run on the References. For submission, attach that record as evidence or re-run solidforge:primary-source-verification on the References list.

## F7 (novelty due-diligence, advisory, not psv-admissible) — no academic prior-art search run

- **Observation:** §7's peer review is mixed — an INDUSTRIAL horizontal comparison (Spec Kit / Loki / zeroshot / LoopX) PLUS informal ACADEMIC novelty positioning (CaMeL, AgentCoder/MetaGPT/ChatEval, mutation testing, Barr 2015, CodeT/AlphaCodium, LLM-as-judge are each distinguished against the paper's three novelty claims: two-axis frame, Process/Outcome split, salient/latent). What has NOT been run is a FORMAL systematic academic prior-art search (e.g., PRISMA-style) beyond §7's cited-work positioning. This is the standard pre-submission gap for a position paper.
- **Proposed next step (advisory):** run solidforge:prior-art-search before submission.

## What is publication-grade (advisory, not psv-admissible)

Citation grounding (psv-verified across prior passes); honesty discipline (COI disclosure, "consistent with" not "confirms", salient/latent care, human-only correctness, §6 honest limitations, "What this paper is not"); process-axis quality (3 csr passes + psv + reconverge). These need no change.

## Claims flagged for psv (adjudicate against the paper)

- P1. §1 contribution (iv) [paper:L39] contains the phrase "any genuinely heterogeneous oracle is forced out of process" (unqualified). [paper:L39]
- P2. §4.4 [paper:L139] contains "for model-based heterogeneous oracles" (scoping) AND an in-process fetched-source exception with "strong decoupling" under deterministic adjudication. [paper:L139]
- P3. §5 [paper:L157] contains "external to the process for model-based oracles" AND "in-process-but-decoupled for a deterministically-adjudicated fetched-source oracle". [paper:L157]
- P4. The Abstract contribution (iv) [paper:L20] does NOT contain the literal phrase "forced out of process". [paper:L20]
- P5. §3.1 [paper:§3.1] stipulates the strong-form self-certification conjecture, calls it load-bearing for the necessity framing, and flags it as stipulative with a weak-form fallback. [paper:§3.1]
- P6. §8 Open Problems [paper:§8] enumerates items and contains NONE on empirically testing/falsifying the self-certification conjecture. [paper:§8]
- P7. §3.2(ii) [paper:§3.2] asserts the "three modes = probabilistic nature + bounded attention" physical-reduction premise without a citation. [paper:§3.2]
- P8. §2 [paper:§2] declines to attribute the three-mode taxonomy to a single named source. [paper:§2]
- P9. §6 [paper:L163] says "in two cases concretely instantiate" without naming the two cases. [paper:L163]
- P10. SolidForge is cited as a private repository. [paper:L227]
- P11. `authors: TBD`. [paper:L2]
- P12. The frontmatter contains a multi-paragraph process/csr/psv log. [paper:L5–11]
- P13. The paper states it presents no benchmark evaluation and names constructing one (§8.3) as the principal open problem. [paper:L43, paper:§8.3]
- P14. §3.3 [paper:L86] contains "the agent harness forces heterogeneous oracles out of process precisely because in-process reviewers cannot differ in blind-spot set" (unqualified by oracle type). [paper:L86]
