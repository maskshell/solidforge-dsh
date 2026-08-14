# prior-art-search — Design Decisions (ADR log)

> Non-obvious decisions (workspace rule 6). Context / Decision / Why / Rejected.
> Master authority: `proposal.md`; execution blueprint: `iteration-plan.md`.
> Mirrors psv's ADR log where the decisions mirror psv's (single-pipeline, structural-proxy,
> separate schema, M=0-vs-X>0, repo-root agents); records prior-art-search's own where they diverge
> (never-novel, the two-layer oracle, the credential surface, direction-distinct-from-psv).

## ADR #1 — prior-art-search NEVER emits `novel_confirmed` (the absence-of-evidence limit)

- **Context:** the instinct is to want a novelty verdict ("is this novel?"). But you cannot prove a negative — "no prior art exists" cannot be established by search (you cannot search the whole corpus).
- **Decision:** prior-art-search's sole top-line signal is `collisions_under_known_coverage` (N/U/C/I of M). `novel_confirmed` is a FORBIDDEN term and never appears as an emitted field. `clear-under-search` means "no collision found in the searched corpus," NOT "novel."
- **Why:** a zero-collision result is a coverage statement, not a novelty proof. Flattening coverage into a verdict is the category error (proposal §2; the spec-gaming paper §4.2 for the broader two-axis frame). The schema makes `novel_confirmed` unrepresentable (`signal` const + `additionalProperties: false` + coverage_policy_check.py).
- **Rejected:** (a) emit a `novel_confirmed` boolean — the absence-of-evidence category error; (b) treat M=0 / zero-collision as a silent "novel" pass — silent-green anti-pattern (rule 3).

## ADR #2 — prior-art-search is a single extract→search→collision→coverage pipeline, NOT a same+异源 debate loop

- **Context:** csr (cross-source-review) converges a doc via same-family + different-family multi-round debate; psv is a single pipeline (extract→fetch→verdict→coverage) with the fetched source as oracle. prior-art-search's oracle is the searchable prior-art corpus.
- **Decision:** prior-art-search is a single pipeline (extract → search → collision verdict → coverage). It does NOT port csr's heterogeneous `claude -p` substrate and has no debate loop / cap / stalemate (mirrors psv ADR #1).
- **Why:** the oracle is a searched corpus, not a model. The decoupling comes from the prior art being externally authored, not from a different model family. A debate loop would add cost without changing the oracle.
- **Rejected:** (a) mirror csr's two-leg loop — wrong oracle type; (b) port csr's hetero substrate — would inherit an LLM-token surface prior-art-search doesn't need (ADR #5).

## ADR #3 — the collision fetched-quote invariant is a STRUCTURAL-PROXY gate, not a semantic proof

- **Context:** the load-bearing honesty rule is "a collision/uncited-relevant finding MUST cite a fetched QUOTE of the found prior-art text; a quote-less one is downgraded to `claim-inconclusive`." (proposal §8 Q6.)
- **Decision:** `fetched_quote_gate.py` / `enforce_fetched_quote` check a structural proxy (evidence non-empty AND contains a quote marker — a `"` of sufficient length, or `fetched`/`source:`/`quote:`). A model could fabricate a quote that passes the proxy, OR a found quote may be misread / the collision over-interpreted.
- **Why:** JSON/python cannot semantically prove a quote is genuine or that the collision is real. The proxy catches the "no quote at all" case (the common failure), and its limit is DISCLOSED in the collision-record's `coverage` notes (rule 3: never silently green). The blocker severity stands DEFINITIVELY in-schema (the prior art makes the claim, paralleling psv's `claim-refuted`) while the proxy limit is named separately — NOT folded into the severity (mirrors psv ADR #2's structural-proxy posture).
- **Rejected:** (a) no check (silent green — violates rule 3); (b) require a verifiable byte-range into the fetched blob — out of Phase-A scope, fragile across source formats; (c) downgrade all collisions to warnings because of the proxy — would under-state a real collision.

## ADR #4 — the searchable prior-art corpus is WEAKER than psv's fetched source at TWO layers (the load-bearing oracle caveat)

- **Context:** psv's oracle is a fetched authoritative source — strong-decoupling at the FETCH step but tier-2 partial under model-mediated COMPARISON. prior-art-search's oracle is the searchable prior-art corpus.
- **Decision:** prior-art-search is weaker at TWO layers, not "weak oracle vs strong oracle": (1) **comparison-side** (shared with psv) — the claim-vs-prior-art comparison is model-judged, `clear-under-search` ≠ "no collision exists"; (2) **selection-side** (prior-art-search's own) — a search result carries ranking bias, recall limits (you cannot search the whole corpus), and the found prior-art text is itself model-extracted from the search return, not a fetched authoritative byte-range.
- **Why:** the two-layer weakness is precisely WHY prior-art-search NEVER emits `novel_confirmed` and why its top-line is a coverage statement, not a verdict. Stating it as one layer would over-state the oracle; conflating it with psv's fetched oracle would hide the selection-side weakness.
- **Rejected:** (a) treat search as equivalent to a fetched authoritative source (proposal §8 Q4 — the false equivalence); (b) name only the comparison-side weakness and elide the selection-side one.

## ADR #5 — prior-art-search's credential surface is NOT csr's `_ANTHROPIC_AUTH_TOKEN` namespace AND NOT psv's fetched-source surface

- **Context:** csr's `install.md` token-isolation targets csr's heterogeneous `claude -p` substrate; psv disclaims it (psv's oracle is a fetched cited source). prior-art-search's oracle is a searched corpus, reached via a web-search API + open-source fetch.
- **Decision:** open prior art (arXiv abstracts, public repos) is searched/fetched credential-free (stdlib + the orchestrator's primitives); the web-search API uses a SEPARATELY-NAMED HTTP API-key surface (e.g. `<NAME>_SEARCH_API_KEY`), NOT csr's `_ANTHROPIC_AUTH_TOKEN` LLM-token namespace; the claim-vs-prior-art comparison runs in the same-family Claude runtime (no isolated LLM token). (iteration-plan NC-I3; the boundary is resolved here, not silently treated as settled.)
- **Why:** csr's `_ANTHROPIC_AUTH_TOKEN` suffix scopes a credential to csr's Anthropic-gateway substrate, which prior-art-search lacks; psv's surface targets fetched cited sources, and prior-art-search searches UNcited prior art (a different direction — ADR #8). Inheriting either namespace would imply a surface that doesn't exist.
- **Rejected:** (a) inherit csr's token namespace — wrong substrate; (b) inherit psv's fetched-source reasoning — wrong direction; (c) fold the web-search key into the LLM-token namespace — conflates an HTTP search surface with an LLM-gateway surface.

## ADR #6 — `collision-record` is a SEPARATE schema; `novel_confirmed` is forbidden

- **Context:** prior-art-search's top-line is `collisions_under_known_coverage` (N/U/C/I of M), not a boolean.
- **Decision:** a separate `collision-record.schema.json` (analogous to psv's split: collision-findings for per-claim collisions vs collision-record for the disclosure). `signal` is a `const`, `rightness` is a `const: human_confirm_required`, and `additionalProperties: false` + the policy gate make `novel_confirmed` unrepresentable (mirrors psv ADR #3).
- **Why:** the category error is flattening a coverage disclosure into a verdict; the schema must make that flattening structurally impossible, not merely discouraged.
- **Rejected:** a single combined object with a `novel_confirmed: true/false` field — exactly the category error.

## ADR #7 — M=0 escalation is DISTINCT from I>0

- **Context:** the degenerate case — a doc with zero extractable novelty claims (purely interpretive, or makes no novelty assertion) — yields N=U=C=I=0; the sum invariant holds trivially and "0 collisions of 0" can be misread as a silent green ("no collisions — novel!").
- **Decision:** `build_coverage` emits a dedicated escalation "no extractable novelty claims — prior-art-search has no novelty surface on this artifact" when M=0, distinct from the per-claim I>0 escalations. `coverage_policy_check.py` exercises both (mirrors psv ADR #5).
- **Why:** "prior-art-search had no surface" ≠ "prior-art-search found no collisions." Conflating them is a silent-green anti-pattern (rule 3).
- **Rejected:** treat M=0 as a vacuous pass.

## ADR #8 — additive + direction-distinct from psv and the `researcher`

- **Context:** three doc/skill operations touch sources in different DIRECTIONS: psv = backward-CITED (fetch each cited source); prior-art-search = backward-UNCITED (search prior art the doc did NOT cite); blueprint-crafting's `researcher` = forward-GATHER (find sources about X for authoring).
- **Decision:** prior-art-search merges with NEITHER. psv and prior-art-search COMPOSE (a high-stakes doc may run both) but do not merge; the `researcher` is the opposite direction (proposal §8 Q5).
- **Why:** a wrong direction conflation would either make prior-art-search redundant with psv (it isn't — psv can't find uncited prior art) or with the researcher (it isn't — the researcher gathers forward for authoring, not backward-collides on a finished artifact).
- **Rejected:** (a) merge prior-art-search into psv — psv has no uncited-search leg; (b) merge into the researcher — wrong direction.

## ADR #9 — the same-family legs are plugin-level agents (repo-root `agents/`), not skill-internal

- **Context:** prior-art-search needs a fresh-context same-family agent (novelty-claim-extraction) to avoid orchestrator bias.
- **Decision:** `agents/novelty-claim-extractor.agent.md` lives at the repo-root `agents/` (registered as `solidforge:novelty-claim-extractor`), mirroring psv's `solidforge:claim-extractor` (mirrors psv ADR #7).
- **Why:** that is the established solidforge plugin convention (rule 7); skill-internal `agents/` is optional and csr/psv do not use it for their legs.
- **Rejected:** skill-local `skills/prior-art-search/agents/` — diverges from the psv exemplar with no benefit.
