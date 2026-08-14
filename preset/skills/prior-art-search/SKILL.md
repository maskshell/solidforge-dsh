---
name: prior-art-search
description: |
  prior-art-search (pas) — a read-only, search-grounded, per-novelty-claim collision detector that
  SEARCHES the prior-art corpus for a doc's novelty claims and adjudicates prior-art collision
  (collision / uncited-relevant / clear-under-search / inconclusive), emitting an honest coverage
  disclosure (`collisions_under_known_coverage`). Use it when a doc's NOVELTY claims need checking
  for prior-art collisions — "does this paper overclaim novelty", "is this framing already in the
  literature". Produces a per-claim collision packet + a collision-record; NEVER `novel_confirmed`.
  NOT for code review (parallel-development), spec authoring (blueprint-crafting), doc
  process-convergence (cross-source-review), CITED-source verification (primary-source-verification —
  psv backward-CITED, prior-art-search backward-UNCITED), or forward research gathering
  (blueprint-crafting researcher). Does NOT judge whether the doc's novelty is REAL or significant
  (outcome-axis — human). Phase A: EXPLICIT invocation (load this skill by name).
---

# Novelty Coverage

> **DeepSeek Harness.** Role prompts live in the preset's `agents/*.agent.md`; the search adjudication stays `infra/scripts/coverage_driver.py` (stdlib-only).

A read-only, **search-grounded**, per-novelty-claim collision detector for a doc-shaped artifact (a design paper, a research doc, a spec). It opens the OUTCOME axis's *novelty* surface that neither `cross-source-review` (csr), `primary-source-verification` (psv), nor blueprint-crafting's `researcher` reach: csr converges a doc's PROCESS axis but does not search for prior art; psv FETCHES each *cited* source (backward, cited) but does not hunt *uncited* prior art; the `researcher` GATHERS sources forward for authoring (the opposite direction). prior-art-search is the missing **backward, uncited-prior-art collision** check — it SEARCHES the prior-art corpus for each novelty claim and reports collisions honestly.

## Core Positioning

### Search-grounded, not recall-based

A `collision` / `uncited-relevant` finding MUST cite a fetched QUOTE from found prior art, not model recall. A finding that cannot ground a fetched quote of the found prior-art text is downgraded to `inconclusive`, never asserted. This is the load-bearing invariant (workspace rule 3 + L1), enforced by a self-gate (NC-I5). The found text is itself model-extracted from search results — a weaker oracle than psv's fetched authoritative source (see the two-layer caveat below).

### Per-claim collision coverage, not a novelty verdict

prior-art-search NEVER emits `novel_confirmed` or "the doc is novel." Its sole top-line signal is `collisions_under_known_coverage`: C clear-under-search, N collisions, U uncited-relevant, I inconclusive of M extracted novelty claims. I claims (and the M=0 case — no novelty surface) ESCALATE to a human. This is an honest coverage disclosure, NOT a novelty verdict. The irreducible absence-of-evidence limit: you cannot prove a negative ("no prior art exists"), so a doc with zero found collisions is "no collision found in the searched corpus," NOT "novel." A symmetric "novelty-convergence" skill that loops to a `novel_confirmed` boolean is the category error — it flattens a COVERAGE disclosure ("no collision found in the searched corpus") into a VERDICT ("novel"), i.e., absence-of-evidence treated as evidence-of-absence; prior-art-search is explicitly NOT that. (The broader two-axis frame — process × outcome — is the spec-gaming paper §4.2; prior-art-search lives entirely on the outcome axis, so its error is outcome-internal, not a process/outcome conflation.)

### Additive to csr and psv; a single pipeline

prior-art-search is ADDITIVE to csr (process axis) and psv (cited-source verification); it does NOT merge with either. Unlike csr's same-family + different-family multi-round debate, prior-art-search is a SINGLE pipeline — extract novelty claims → search prior art → collision verdict per claim → coverage disclosure. The oracle is the searchable prior-art corpus, not a different-family model, so it does NOT port csr's heterogeneous substrate. psv and prior-art-search compose: a high-stakes doc may run psv (are the *cited* sources accurate?) AND prior-art-search (are the *novelty* claims collision-free against findable prior art?). They do not merge.

### Two-layer oracle weakness, stated honestly (workspace rule 3)

prior-art-search's oracle is the searchable prior-art corpus, WEAKER than psv's fetched primary source at TWO layers (the load-bearing honesty caveat, proposal §3 / ADR §8 Q4):

1. **Comparison-side weakness (shared with psv).** The claim-vs-prior-art comparison is model-judged — `clear-under-search` means the model found no collision, not that none exists. This is psv's tier-2 partial-under-comparison weakness.
2. **Selection-side weakness (prior-art-search's own).** A search result adds a selection weakness on top of the comparison weakness: ranking bias, recall limits (you cannot search the whole corpus), and the found prior-art text is itself model-extracted from the search return, not a fetched authoritative byte-range.

So prior-art-search is weaker at two layers, not "weak oracle vs strong oracle." This is precisely WHY it NEVER emits `novel_confirmed` and why its top-line is a coverage statement, not a verdict. `clear-under-search` means "no collision in what was searched," not "novel." The weaker oracle is the irreducible limit of novelty-checking short of a human.

### Two blind-spots, stated honestly (workspace rule 3)

prior-art-search's own model-performed steps carry blind spots disclosed rather than hidden: (1) **novelty-claim extraction** inherits the extractor's blind spots — claims neither author nor extractor identify as "novelty" are absent from M; (2) the **claim-vs-prior-art comparison** is model-judged — `clear-under-search` means the model found no collision, not that none exists. The C/N/U/I/M counts are conditional on what was extracted, searched, and compared, not a completeness guarantee. A different-family extraction leg is a deferred mitigation (partial).

## Scope

- **In**: extract atomic novelty claims from a doc (each: location + search target); search the prior-art corpus per claim; emit a per-claim collision verdict (collision/uncited-relevant/clear-under-search/inconclusive) grounded in a fetched quote of found prior art for collisions; emit a collision-record (`collisions_under_known_coverage`) + a collision-findings packet.
- **Out**: code review (`parallel-development`); spec/arch-design authoring (`blueprint-crafting`); doc process-convergence (`cross-source-review`); CITED-source verification (`primary-source-verification`); research gathering (`blueprint-crafting researcher`); a novelty verdict — whether the doc's novelty is REAL or significant — (human).

### Scope Guard (entry-time detection)

- Deliverable is source/test code → route to `parallel-development`.
- Deliverable is authoring/rewriting a spec, arch-design, iteration-plan, or research → route to `blueprint-crafting`.
- The request is "drive adversarial multi-round review to convergence on this doc" → route to `cross-source-review` (process axis).
- The request is "do this doc's CITED claims hold against their sources?" → route to `primary-source-verification` (psv = backward-CITED; prior-art-search = backward-UNCITED).
- The request is "does this doc OVERCLAIM novelty — collide with prior art it failed to cite?" → prior-art-search (this skill).
- The request is "is this novel / significant / the right contribution?" → outcome-axis, human only.

The guard is soft (remind + route, not refuse). Phase A relies on **explicit invocation** (`/prior-art-search`).

## Quick Start

You are the orchestrator. The legs are read-only; the driver runs the single pipeline (NOT a multi-round debate). Run in order.

1. **Frame** — identify the artifact + its novelty surface. **Enumerate the core novelty claims** (the load-bearing "X is new / first / has no prior art" assertions to collision-check). Declare scope.

2. **Novelty-claim extraction** (NC-I2) — spawn the `agents/novelty-claim-extractor.agent.md` role prompt (fresh context); it reads the artifact and enumerates **atomic novelty claims**, each tied to a location and a search target. **Atomic** = one novelty proposition per claim (compound split). A novelty claim is an assertion of newness ("X is a new framing," "Y is the first to," "Z has no prior art"). Distinguish from factual/citation claims (psv's domain — verify, don't collision-check) and interpretive claims ("this is significant" — NOT search-adjudicable; escalate to human, tagged inadmissible). (Extractor blind-spot caveat: claims neither party identifies as "novelty" are absent from M.)

3. **Multi-source search + collision verdict** (NC-I3) — for each novelty claim, search the prior-art corpus (arXiv, web, public repos) for work that ALREADY made the claim, then compare the claim against found prior art and assign one of:
   - `collision` — found prior art already makes this claim (the doc's novelty is overstated); cite the colliding source + QUOTE the found prior-art text (severity `blocker`; `evidence` MUST quote the found prior art).
   - `uncited-relevant` — found relevant work the doc didn't cite (not a direct collision, but a coverage gap); QUOTE the found prior art (severity `warning`).
   - `clear-under-search` — no collision found IN THE SEARCHED CORPUS (NOT `novel`; just no collision surfaced). Counted only, not a finding.
   - `inconclusive` — search couldn't cover the claim (paywalled corpus, ambiguous query, nothing findable); escalate to human (severity `coverage`).
   Open sources (arXiv abstracts, public repos) are searched without credential; web-search APIs use a separately-named HTTP surface (NOT csr's `_ANTHROPIC_AUTH_TOKEN` LLM-token namespace — see install.md). (Comparison blind-spot caveat + the selection-side weakness.)

4. **Coverage disclosure** (NC-I4) — emit a `collision-record`: `collisions_under_known_coverage` = C clear-under-search / N collisions / U uncited-relevant / I inconclusive of M = C+N+U+I extracted novelty claims; plus a collision-findings packet (collision / uncited-relevant / inconclusive findings; `clear-under-search` claims are counted, not listed). **M=0** (no extractable novelty claims — a doc making no novelty assertion, or all novelty claims interpretive) and **I>0** both ESCALATE to a human. NEVER `novel_confirmed`. A collision/uncited-relevant finding without a fetched quote is downgraded to `inconclusive`.

The honest signal is the coverage disclosure — exactly what was searched and what collided, and what could not be covered. Whether the doc is genuinely NOVEL stays human.

## Authority Chain

- `docs/proposal.md` = authoritative design (master; CSR process-axis SUBSTANTIVE-CONVERGED + psv N=9/K=0 verified, 2026-07-31).
- `docs/iteration-plan.md` = execution blueprint (Phase A work-items NC-I0–NC-I6; on conflict, proposal.md wins).
- `docs/design-decisions.md` = ADR log (the non-obvious decisions: never-novel_confirmed, single-pipeline-not-debate, the false-positive structural-proxy, the two-layer search-oracle weakness, the relation to psv/researcher, the credential surface).
- `docs/proposal.convergence.md` = the proposal's cross-review trail.

## Coordination with cross-source-review / primary-source-verification / blueprint-crafting / parallel-development

- `cross-source-review` stays the PROCESS-axis convergence engine. prior-art-search is ADDITIVE and non-merging: csr's `substantive_converged` does not imply prior-art-search's coverage, and vice versa.
- `primary-source-verification` is the complementary outcome-axis leg. psv = backward-CITED (fetch each cited source); prior-art-search = backward-UNCITED (search for prior art the doc did NOT cite). They compose (a doc may run both); they do not merge. prior-art-search reuses psv's schema-field pattern (collision-findings extends psv's doc-findings — a strict superset) and the `install.md` credential REASONING — copy-patterns, NOT code (workspace rule 7).
- `blueprint-crafting` stays pure (process-axis). Its `researcher` is FORWARD gather ("find sources about X for authoring") — the opposite direction from prior-art-search's backward collision. They do not merge.
- `parallel-development` owns code review. prior-art-search is doc-shaped, not code-shaped.
- `files_touched` boundary: this skill owns `prior-art-search/` + the repo-root `agents/novelty-claim-extractor.agent.md` (mirroring psv's `agents/claim-extractor.agent.md`). It does not modify csr, psv, bc, or pd core logic (prior-art-search is additive). Terminology (workspace rule 10): `collisions_under_known_coverage` is the one top-line term; `novel_confirmed` is the forbidden term and never appears as an emitted field.

## Self-Checks (Definition of Done)

> **Maturity note (Phase A build):** all self-gates below ship and pass green (NC-I0–NC-I6 converged; `docs/iteration-plan.run-record.json` carries the verdict). The **live N≥3 dogfood ran 2026-08-01** on 3 real artifacts incl. the long spec-gaming paper — coverage profile at [dogfood-run-2026-08-01.md](docs/dogfood-run-2026-08-01.md): 2 uncited-relevant findings surfaced via fetched prior art (spec-gaming NC34 ↔ SWE-ABS; psv NC2 ↔ AI-Powered Citation Auditing), and the known self-cert-paradox collision came back clear-under-search under the arXiv-only oracle — demonstrating the two-layer weakness in production (a zero-collision result is "no collision in what was searched," NOT "novel"). The offline `dogfood.py` gate covers the canonical fixture only (rule-1 skip path when no network). Remaining deferral: a different-family extraction leg (partial mitigation of the extractor blind-spot). The name `prior-art-search` is PROPOSED, pending human LOCK (proposal §8 Q1).

A skill change is not done while any self-check fails (workspace rule 1). Run before commit:

```bash
python3 skills/prior-art-search/infra/test/disconnect_check.py        # structure + loading-chain
python3 skills/prior-art-search/infra/test/plugin_layout.py           # plugin.json + agents well-formed
python3 skills/prior-art-search/infra/test/findings_shape_check.py    # every emit path → collision-findings + collision-record valid
python3 skills/prior-art-search/infra/test/coverage_policy_check.py   # counts sum M=C+N+U+I; M=0/I>0 escalate; no novel_confirmed; fetched-quote invariant
python3 skills/prior-art-search/infra/test/fetched_quote_gate.py      # every collision/uncited-relevant finding cites fetched prior-art text; quote-less → inconclusive (the L1/rule-3 invariant)
python3 skills/prior-art-search/infra/test/lint_self.py               # dogfood: lints this skill's own infra (ruff)
python3 skills/prior-art-search/infra/test/dogfood.py                 # runs the pipeline on a fixture doc with a planted collision (skips gracefully w/o network; recorded log substitutes)
```

## Reference Files

- [proposal.md](docs/proposal.md) — authoritative design (problem, non-goals, owned contract, layering, §8 decisions).
- [iteration-plan.md](docs/iteration-plan.md) — Phase-A execution blueprint (NC-I0–NC-I6, DoD, DAG, risks).
- [design-decisions.md](docs/design-decisions.md) — ADR log (the non-obvious decisions).
- [install.md](references/install.md) — provisioning: prior-art-search's credential surface (open prior art searched without credential; web-search API = separately-named HTTP surface, NOT csr's LLM-token namespace) + the two-layer oracle weakness + SSRF posture. prior-art-search is env-armed (no arm command — its gates are self-gates).
