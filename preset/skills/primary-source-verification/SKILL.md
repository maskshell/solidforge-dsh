---
name: primary-source-verification
description: primary-source-verification (psv) — a read-only, source-grounded, per-claim verifier that FETCHES each cited primary source and adjudicates a doc's factual/citation claims (verified / refuted / narrowed / unverifiable), emitting an honest coverage disclosure (`oracle_verified_under_known_coverage`). Use it when a doc's citations need checking against the actual sources — "verify this doc's citations", "fact-check this spec's arXiv claims". Produces a per-claim verdict packet + a coverage-record; NEVER `correctness_converged`. NOT for code review (parallel-development), spec authoring (blueprint-crafting), doc process-convergence (cross-source-review), or research gathering (blueprint-crafting researcher). Does NOT judge whether the doc is RIGHT (outcome-axis — human). Phase A activation is EXPLICIT invocation (load this skill by name). GATE MODE (2026-08): load-bearing-subset GO/NO-GO run before csr — gate record non-authoritative; the full-M run after csr is the ONLY authoritative record.
---

# Primary Source Verification

> **DeepSeek Harness.** The claim-extraction / verification role prompts live in the preset's `agents/*.agent.md` (spawn via the `subagent` tool); the deterministic adjudication stays `infra/scripts/coverage_driver.py` (stdlib-only, unchanged).

A read-only, **source-grounded**, per-claim verifier for a doc-shaped artifact. It opens the OUTCOME axis's *admissible* surface that `cross-source-review` (csr) cannot reach: csr converges a doc's PROCESS axis but its legs verify citations by MODEL RECALL (they share the model's blind spot on cited works); psv FETCHES each cited primary source and adjudicates the claim against the fetched TEXT. The fetched source — not a model — is the oracle.

## Core Positioning

### Source-grounded, not recall-based

A refuted/narrowed finding MUST cite a fetched-source quote, not model recall. A finding that cannot ground a fetched quote is downgraded to `unverifiable`, never asserted. This is the load-bearing invariant (workspace rule 3 + L1), enforced by a self-gate (PSV-I5).

### Per-claim coverage, not correctness

psv NEVER emits `correctness_converged` or "the doc is correct." Its sole top-line signal is `oracle_verified_under_known_coverage`: N verified, R refuted, W narrowed, K unverifiable of M extracted claims. K claims (and the M=0 case — no admissible surface) ESCALATE to a human. This is an honest coverage disclosure, not a correctness verdict. A symmetric "outcome-convergence" skill that loops to a `soundness_converged` boolean is the category error the spec-gaming paper §3.3 names (flattening two axes); psv is explicitly NOT that.

### Additive to cross-source-review; a single pipeline

psv is ADDITIVE to csr (csr remains the process-axis convergence engine) and does NOT merge with it. Unlike csr's same-family + different-family multi-round debate, psv is a SINGLE pipeline — extract claims → fetch sources → verdict per claim → coverage disclosure. The oracle is the fetched source TEXT, not a different-family model, so psv does NOT port csr's heterogeneous substrate.

### Two blind-spots, stated honestly (workspace rule 3)

psv's own model-performed steps carry blind spots the proposal discloses rather than hides: (1) **claim extraction** inherits the extractor's blind spots — claims neither author nor extractor can see are absent from M; (2) the **claim-vs-text comparison** is model-judged — `verified` means the model found no contradiction, not that none exists. The N/R/W/K/M counts are conditional on what was extracted and compared, not a completeness guarantee.

## Scope

- **In**: extract atomic source-admissible claims from a doc; fetch each cited primary source; emit a per-claim verdict (verified/refuted/narrowed/unverifiable) grounded in fetched text; emit a coverage-record (`oracle_verified_under_known_coverage`) + a doc-findings packet.
- **Out**: code review (`parallel-development`); spec/arch-design authoring (`blueprint-crafting`); doc process-convergence (`cross-source-review`); research gathering (`blueprint-crafting researcher`); outcome-axis judgment — whether the doc is RIGHT — (human).

### Scope Guard (entry-time detection)

- Deliverable is source/test code → route to `parallel-development`.
- Deliverable is authoring/rewriting a spec, arch-design, iteration-plan, or research → route to `blueprint-crafting`.
- The request is "drive adversarial multi-round review to convergence on this doc" → route to `cross-source-review` (process axis). psv is the narrower "do this doc's cited claims hold against their sources?" (admissible outcome surface).
- The request is "is this the right requirement / right conclusion?" → outcome-axis, human only.

The guard is soft (remind + route, not refuse). Phase A relies on **explicit invocation** (`/primary-source-verification`).

## Quick Start

You are the orchestrator. The legs are read-only; the driver runs the single pipeline (NOT a multi-round debate). Run in order.

1. **Frame** — identify the artifact + its cited authorities. **Enumerate the core claims** (the load-bearing assertions to verify). Declare scope.

2. **Claim extraction** (PSV-I2) — a claim-extraction agent reads the artifact and enumerates **atomic, source-admissible** claims, each tied to a location and an expected adjudicating source (arXiv abstract / Crossref / spec section / code symbol). **Atomic** = one verifiable proposition per claim (compound split). **Source-admissible** = references a specific, fetchable source; design decisions, predictions, and interpretations are NOT admissible (escalate to human). Interpretive claims are tagged `unverifiable` at extraction. (Extractor blind-spot caveat: claims neither party can see are absent from M.) **Source durability** (fix B): prefer a durable in-repo source when one exists (the doc should carry the durable citation). A claim whose only adjudicating source is volatile (e.g. `~/.claude/projects/` memory, `/tmp` clones — repo-external, unversioned, deletable) is still admissible, but mark it `volatile` at extraction so the registry in the coverage-record captures it.

3. **Source fetch + per-claim verdict** (PSV-I3) — for each claim, fetch its cited authority. The fetched-source TEXT is the oracle. Compare claim vs fetched text; assign one of:
   - `verified` — fetched source supports the claim (the comparison model found no contradiction; not a proof of none).
   - `refuted` — fetched source contradicts the claim (severity `blocker`; `evidence` MUST quote the fetched text).
   - `narrowed` — fetched source supports a weaker form (severity `warning`; `evidence` MUST quote the fetched text).
   - `unverifiable` — no fetchable source adjudicates it (interpretive, paywalled, judgment call); escalate to human.
   Open sources (arXiv, Crossref, repos) are fetched without credential; paywalled sources are NOT fetched — returned `unverifiable`. (Comparison blind-spot caveat.)

4. **Coverage disclosure** (PSV-I4) — emit a `coverage-record`: `oracle_verified_under_known_coverage` = N verified / R refuted / W narrowed / K unverifiable of M = N+R+W+K extracted claims; plus a doc-findings packet (refuted / narrowed / unverifiable findings; `verified` claims are counted, not listed). **M=0** (no source-admissible claims — e.g. a purely interpretive doc) and **K>0** both ESCALATE to a human ("no admissible surface" vs "claims extracted but unverifiable"). NEVER `correctness_converged`. A finding without a fetched quote is downgraded to `unverifiable`. **Persistence + volatile authorities** (fix B): the doc-findings packet is PERSISTED as a file beside the coverage-record (claim_ref / verdict / source_ref / fetched quote per finding — the audit found counts-only records with no per-claim packet; that hole is closed here). The coverage-record carries a volatile-authority registry — claim_ref → volatile source — covering ALL claims, verified ones included (their sources are counted-not-listed in the packet, so the registry is their only re-fetchability signal). A repo reader can re-fetch every non-verified finding's source, or the record tells them the source was volatile and where it lived at run time.

The honest signal is the coverage disclosure — exactly what was verified against fetched sources and what could not be. Whether the doc is RIGHT stays human.

## Authority Chain

- `docs/proposal.md` = authoritative design (master; CSR process-axis SUBSTANTIVE-CONVERGED 2026-07-31).
- `docs/iteration-plan.md` = execution blueprint (Phase A work-items PSV-I0–PSV-I6; on conflict, proposal.md wins).
- `docs/design-decisions.md` = ADR log (the non-obvious decisions: single-pipeline-not-debate, fetched-quote structural proxy, the M=0-vs-K>0 split, the credential surface).
- `docs/proposal.convergence.md` = the proposal's cross-review trail.

## Coordination with cross-source-review / blueprint-crafting / parallel-development

- `cross-source-review` stays the PROCESS-axis convergence engine. psv is ADDITIVE and non-merging: csr's `substantive_converged` does not imply psv's coverage, and psv's coverage does not grant csr's process convergence. A doc may go through csr (consistency/structure) AND psv (citation correctness); the two compose, they do not merge.
- `blueprint-crafting` stays pure (process-axis). psv reuses csr's **schema-field pattern** (doc-findings, extended) and the `install.md` credential REASONING — copy-patterns, NOT code (workspace rule 7). psv does NOT port csr's heterogeneous substrate (it has no debate loop).
- `parallel-development` owns code review. psv is doc-shaped, not code-shaped.
- `files_touched` boundary: this skill owns `primary-source-verification/`. It does not modify csr, bc, or pd core logic (psv is additive). GATE MODE: when rule-13 conditions hold (load-bearing citations, fetchable sources), psv may run FIRST as a load-bearing-claims subset gate (GO/NO-GO batch signal, gate record non-authoritative, bounded re-gate ≤2) before csr; the authoritative full-M coverage record still follows csr. Discriminator (ODP-5, 2026-08-10): the gate pays on docs with predominantly EXTERNAL load-bearing citations (arXiv/blogs/standards — the recall blind-spot zone) and on LONG-tier docs (expected csr investment ≥ 3 rounds); local-citation docs — csr alone suffices; short docs never pay (gate ≈1.5 rounds vs ≤2 rounds max saved). The gate is an insertion mode, not a pipeline stage — the additive positioning is unchanged. Terminology fork (disclosed): the spec-gaming paper §4.2 names the process tier `process_converged` (machine-checkable, deterministic); csr's emitted field is `substantive_converged` (LLM-adjudicated) — psv maps csr's field to the paper's tier but states the weaker guarantee.

## Self-Checks (Definition of Done)

> **Maturity note (Phase A built):** all six self-gates below ship and pass green (PSV-I0–PSV-I6 converged; `iteration-plan.run-record.json` carries the verdict). Two honest deferrals remain — (1) the **live N≥3 dogfood** (incl. ≥1 long doc) is a human-run acceptance criterion; the offline `dogfood.py` gate covers the canonical misattribution fixture only (rule-1 skip path when no network); (2) P2 `prior-art-search` / P3 `argument-red-team` are out of scope (each earns its own proposal). The name `primary-source-verification` is PROPOSED, pending human LOCK (proposal §9 Q1).

A skill change is not done while any self-check fails (workspace rule 1). Run before commit:

```bash
python3 skills/primary-source-verification/infra/test/disconnect_check.py        # structure + loading-chain
python3 skills/primary-source-verification/infra/test/plugin_layout.py           # plugin.json + agents well-formed
python3 skills/primary-source-verification/infra/test/findings_shape_check.py    # every emit path → doc-findings + coverage-record valid
python3 skills/primary-source-verification/infra/test/coverage_policy_check.py   # counts sum M=N+R+W+K; M=0/K>0 escalate; no correctness_converged; fetched-quote invariant
python3 skills/primary-source-verification/infra/test/fetched_quote_gate.py      # every refuted/narrowed finding cites fetched text; quote-less → claim-unverifiable (the L1/rule-3 invariant)
python3 skills/primary-source-verification/infra/test/lint_self.py               # dogfood: lints this skill's own infra (ruff)
python3 skills/primary-source-verification/infra/test/dogfood.py                 # runs the pipeline on a fixture doc with a planted misattribution (skips gracefully w/o network; recorded log substitutes)
```

## Reference Files

- [proposal.md](docs/proposal.md) — authoritative design (problem, non-goals, owned contract, layering, §9 decisions).
- [iteration-plan.md](docs/iteration-plan.md) — Phase-A execution blueprint (PSV-I0–PSV-I6, DoD, DAG, risks).
- [design-decisions.md](docs/design-decisions.md) — ADR log (the 7 non-obvious decisions).
- [install.md](references/install.md) — provisioning: psv's credential surface (open sources fetched without credential; paywalled → `unverifiable`; no LLM-token substrate) + SSRF posture. psv is env-armed (no arm command — its gates are self-gates).
