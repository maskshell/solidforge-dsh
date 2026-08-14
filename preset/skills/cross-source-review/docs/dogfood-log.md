# cross-source-review — CSR-I6 dogfood log (质量稳定 gate)

> The skill ran its own convergence engine on N=3 real docs (own SKILL.md + a medium doc +
> a long doc) with REAL DeepSeek 异源 calls. This is the live proof the offline gates
> (CSR-I5) cannot give: the wrapped substrate against a real backend on real artifacts.
> Date: 2026-07-07. Caps: SKILL.md short=2, proposal.md short=2, bc arch-design.md long=7.

## Measured convergence profile

| Doc | Size tier | Legs run | 同源 findings | 异源 findings | Round-1 blockers | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| `SKILL.md` (own) | short | 同源 + 异源 (full cross) | 4 (2 warning, 2 coverage) | 4 (3 warning, 1 coverage) | 0 | substantively converging — 8 advisory findings, revisions applied (see below) |
| `proposal.md` | short/medium | 异源 | (not run) | 6 (5 warning, 1 coverage) | 0 | substrate PROVEN on a real doc; findings are post-hoc proposal improvements (proposal is accepted/converged — noted, not re-opened) |
| `blueprint-crafting/docs/arch-design.md` | long | 异源 | (not run) | 2 (1 blocker, 1 coverage) — re-run after the fix | 1 | substrate gap RESOLVED — initial run MALFORMED (`hetero-cc-error:success`); after the `_stdout_indicates_success` fix, the re-run recovered the result (a real blocker contradiction + a coverage gap in bc's arch-design.md) |

Totals: 4 real DeepSeek calls (3 + 1 fix-verification re-run) + 1 同源 agent. 16 findings across the 3 docs (the long-doc re-run added 1 blocker + 1 coverage). Cost ≈ $1.5–2.5.

## What the dogfood PROVED

- **The live 异源 substrate works on real docs.** Real DeepSeek, real adversarial doc-review findings, well-evidenced (each finding quotes source). The wrapped substrate (`hetero_doc_review.py`) — not just the raw `claude -p` proven during the proposal bootstrap — produces typed doc-findings end-to-end.
- **The 同源 leg works** (skill-local doc-reviewer agent, fresh context) — verified the copy-pattern signatures are byte-identical, the gate files exist, the Q4 rationale matches, and surfaced its own distinct findings (divergence-log line-count drift; one-sided coordination claims).
- **Cross-source complementarity is real:** 同源 and 异源 found DIFFERENT things on SKILL.md (同源: divergence-log drift, coordination one-sidedness; 异源: Quick Start gaps, schema/impl stalemate drift). Neither restated the other — the "hunt the gap" framing held.
- **The convergence engine is sound** (offline, CSR-I4 fixtures already proved both prongs; the live run produced 0 blockers, consistent with substantive convergence).

## SKILL.md round-1 revisions APPLIED (the convergence loop did its job)

8 advisory findings (0 blockers) → these revisions:
- Quick Start step 1: enumerate **core claims** + a **size-tier heuristic** (was: declare tier with no criterion; core-claims undefined). [异源 csr-sk-md-structural-1 + 同源 csr-doc-2]
- Quick Start step 2: added the **同源 + 异源 invocation commands** (was: "run this script" with no flags). [异源 csr-sk-md-structural-2]
- Coordination §: cited **proposal §5** alongside rule 7 for the copy-pattern + a **Phase-A note** that the bc/pd routing claims are CSR-side intent (reciprocal hints deferred per Q4). [异源 csr-sk-md-citation-1 + 同源 csr-doc-4]
- `convergence-record.schema.json`: aligned the **stalemate** description with `converge.py` + ADR #40 (e) (removed the "persistently disagreed" narrowing). [异源 csr-sk-md-coverage-1]

## Findings NOTED for follow-up (advisory; not applied to keep scope bounded)

- 同源 csr-doc-1: `hetero_doc_review.divergence.md` line-count metadata drifted (pd 954 / csr 926 vs logged 955/930) — the copy was reformatted after the log. Load-bearing signatures are INTACT; only the stale counts drifted. Fix: drop the hard-coded counts in favor of a git-ref baseline (they re-drift on any reformat).
- 同源 csr-doc-3: SKILL.md routes "a code diff under review → parallel-development", but pd's Scope Guard frames pd as code DELIVERY, not standalone review (a `/code-review` skill also exists). Narrow or confirm.
- proposal.md 异源 findings (6): the proposal under-defines "Morph caveat" (no gloss), "core claims", the "medium" tier, "escalate for adjudication", the DEGRADE boundary (vs ADR #41's DEGRADABLE_CC_SUBTYPES), and the "function-signature CONTRACT" term. The proposal is SUBSTANTIVE-CONVERGED + accepted; these are post-hoc improvements for a future re-open.

## Substrate robustness gap — RESOLVED (the dogfood's highest-value catch, now fixed)

**`blueprint-crafting/docs/arch-design.md` (long) → initial 异源 run MALFORMED (`hetero-cc-error:success`); FIXED + verified live.**

- Symptom (initial run): CC exited non-zero; stdout envelope had `subtype:"success"` but the wrapper treated it as a non-degradable error (`_parse_cc_substrate_error` trusts `is_error` over `subtype`) → `hetero-cc-error:success` malformation, 0 findings (result discarded).
- Root cause: a DeepSeek/CC backend quirk on a long-doc review — the result was actually a success (`subtype:"success"`) but CC exited non-zero with a contradictory `is_error` flag. pd's `_parse_cc_substrate_error` (preserved EXACTLY, ADR #41) had no case for "subtype=success but is_error=true + rc!=0" — pd's reviews are diffs, not long docs.
- Fix APPLIED: `_stdout_indicates_success(raw)` guard in `run_claude` — a non-zero exit WITH a `subtype:"success"` envelope short-circuits to the normal parse (subtype is authoritative; the result is usable). ADR #41 DEGRADE handling unchanged. Unit-verified (5 cases) + divergence-logged.
- Fix VERIFIED LIVE: the long-doc re-run (same `--artifact`) returned `malformation:""`, **2 findings** (1 blocker contradiction + 1 coverage gap in bc's arch-design.md) — the previously-discarded result recovered. This is the live verification the original gap note deferred.
- Why this was valuable: the live dogfood found a real robustness gap the offline gates (dry-run only) structurally cannot — and the fix closed it. pd's copy does NOT yet have this guard (candidate B2 pattern-refresh if pd hits the quirk).

## Verdict (CSR-I6 质量稳定 gate)

- N ≥ 3 real docs: YES (SKILL.md + proposal.md + bc arch-design.md).
- Own SKILL.md reviewed: YES.
- ≥ 1 long doc: YES (bc arch-design.md) — exercised the long-doc path; surfaced + RESOLVED the substrate gap (the `subtype:"success"` fix, verified live).
- Measured convergence profile recorded: YES (this file).
- The skill's self-gates (CSR-I5) remain green after the round-1 revisions (the SKILL.md + schema edits did not break any gate).
- **Substantive convergence demonstrated live** on SKILL.md (0 blockers round 1, both legs) — the doc-convergence engine works end-to-end on a real artifact.

The skill is built (CSR-I0–I5); the live dogfood proved it + found + RESOLVED one substrate gap (the long-doc `subtype:"success"` malformation — fixed + verified live). Phase A is functionally complete. The other noted advisory (divergence-log line-count drift, csr-doc-1) is addressed in the same follow-up commit (a git-ref baseline replaces the hard-coded counts; line counts no longer tracked — they drift).
