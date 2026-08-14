# cross-source-review proposal — convergence record

Multi-round 同源 ↔ 异源 cross review of `proposal.md` (the skill reviewing its own
design — dogfood). Cap = 3 (medium doc). Substantive convergence = no new Blocker for
≥2 rounds. Cap-hit or persistent stalemate → escalate to human (never silent-pick).

## Round 1

### 同源 leg (fresh-context adversarial agent; doc-review prompt; Q2 enum)

- findings: 2 blocker, 7 warning. 9 accepted (revised), 0 rejected → no stalemate this round.
- blockers:
  - FX-01 (citation-error): "ADR #38" cited for bc outcome-axis. Verified — pd ADR #38 is the 异源/L4 re-alignment; bc's outcome-axis is bc §2 + arch-design §1. Revised to bc §2 / arch-design §1.
  - FX-02 (contradiction): §8 said "use pd's `hetero_review.py` for the 异源 leg" while §1/§3 call it code-coupled and not doc-usable. Verified — `--diff`/`--blueprint` required (`hetero_review.py:683/686`), prompt hardcoded code-shaped. Revised §8 to a raw `claude -p` call.
- warnings (all revised):
  - FX-03: Q4 "zero routing risk" softened (Scope Guard concedes residual collision).
  - FX-04: Q2 rationale corrected (borrows `contradiction`; replaces the other 3 bc kinds).
  - FX-05: Q5 — `plan-reviewer` is plan-MODEL-shaped, not doc-shaped → skill-local reviewer from Phase A.
  - FX-06: §1/§3 — code-review policy IS codified (pd ADR #40 c/d/e); only the doc-specific layer is tacit.
  - FX-07: §5/Q7 count aligned — `SKILL.md` is one OF the N≥3, not additional.
  - FX-08: §6 — added the bc-callback invocation site (site 2).
  - FX-09: §5 — added B3 (shared library); bc §6 carve-out means copy-vs-share is a judgment for a pipeline, not a fixed rule.
- independent verification: FX-01 and FX-09 grep-verified against source before accepting. FX-09 citation format corrected (bc uses `## N`, not `ADR #N`; substance confirmed at `design-decisions.md:46`). Lesson reinforced: do not blind-trust the reviewer's citations either.

### 异源 leg (raw `claude -p` DeepSeek via throwaway wrapper reusing `hetero_review.py` materialization; doc-review prompt; fed FX-01..FX-09 as prior)

- findings: 0 blocker, 4 warning. 4 accepted (revised), 0 rejected.
- DeepSeek independently confirmed all 9 同源 fixes landed + grep-confirmed its own F1 claim (cross-source agreement on the core).
- warnings (all revised):
  - F1 (citation-error): §3 "pd ADR #38 outcome-axis" miscite — verified `outcome` appears in pd design-decisions ONLY at line 300 (ADR #40's shorthand), not in ADR #38's text. Fixed → cite pd ADR #40 (e) (the direct source: cap-hit→human + outcome-axis + stalemate + never-silent-pick).
  - F2 (structural-gap): §3 had no per-round 同源/异源 reconciliation (only multi-round stalemate). Added the 5-row reconciliation table (mirrors pd ADR #40 (b)).
  - F3 (coverage-gap): Phase-A copy had no interface-compat constraint → B1/B3 would silently drift to a re-port. Added §5 Phase-A compatibility constraint (preserve function-signature contract + divergence log).
  - F4 (coverage-gap): Q6 listed 3 skill-specific gates without the standard set. Clarified Q6 — 3 skill-specific ON TOP OF the standard (`disconnect_check`/`plugin_layout`/`lint_self`); §5 "self-gates green" = full set.
- independent verification: F1 grep-verified against pd design-decisions.md before accepting.

### Reconciliation

- 13 revisions total (9 同源 + 4 异源) applied to `proposal.md`. 0 rejections across both legs.
- cost: 1 DeepSeek call, ≤ $2.0 cap (well under; single cold review).

### Verdict — SUBSTANTIVE CONVERGENCE — ACCEPTED (human, 2026-07-07)

- Human accepted substantive convergence (round 2 not requested). Bootstrap step 1 of 3 (converge) COMPLETE → next: bc formalize.
- 0 outstanding blockers. Core claims cross-verified by BOTH sources (同源 + 异源 agreement on every major citation + the 9 fixes).
- Meets the doc-domain substantive-convergence doctrine (`hetero-long-doc-review-convergence`): core coverage-verified + only advisory findings remain + do not chase zero-finding on a doc (this loop's 异源 round-1 produced exactly the advisory citation-precision tail the doctrine predicts — further rounds would loop on finer citation flaws, not core defects).
- Does NOT meet the STRICT §3 "≥2 Blocker-free rounds" criterion (1 cross-round done; a 2nd Blocker-free round would). Round 2 available if the human wants strict confirmation (~$0.3–1).
- Human is the outcome-axis arbiter (pd ADR #40 (e)): accept substantive convergence, or demand round 2.
- Dogfood yield: this loop validated §3's substantive-convergence-vs-zero-finding policy AND the per-round reconciliation table (F2) AND the substrate-needs-doc-adaptation claim (§1/§8) — the skill reviewed its own design and the design held.
