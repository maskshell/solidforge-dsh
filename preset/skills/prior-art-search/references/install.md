# install — prior-art-search provisioning

> prior-art-search is **env-armed** (no arm command). Its gates are self-gates (workspace rule 1);
> it has NO tools/post-execute hooks of its own — the extract→search→collision→coverage pipeline
> is orchestrator-driven, not hook-driven. This doc is the credential-surface + oracle-strength
> reference.

## Credential surface (differs from cross-source-review AND primary-source-verification — read this)

csr's `install.md` token-isolation pattern targets csr's **heterogeneous `claude -p` substrate**
— an Anthropic-gateway LLM token (`<NAME>_ANTHROPIC_AUTH_TOKEN`). psv inherits NONE of it (psv's
oracle is a fetched document, not a different-family model — psv install.md). **prior-art-search
inherits NEITHER**: its oracle is the **searchable prior-art corpus**, searched via a web-search
API + open-source fetch, not a fetched cited source and not an LLM gateway (proposal §3,
iteration-plan NC-I3). So csr's LLM-token namespace **does not apply**, and psv's "fetched cited
source" credential reasoning does not apply either.

prior-art-search's actual credential surface:

| Surface | Credential | Behavior |
| --- | --- | --- |
| Open prior-art search — arXiv abstracts, public repos, docs | **none** | searched / fetched credential-free (`search_prior_art.py`, stdlib + the orchestrator's search/fetch primitives) |
| Web-search API (the prior-art corpus's main entry) | a **separately-named HTTP API-key** (e.g. `<NAME>_SEARCH_API_KEY`), NOT csr's `_ANTHROPIC_AUTH_TOKEN` | the search query runs through a web-search provider; the key scopes ONLY that HTTP surface |
| The claim-vs-prior-art collision comparison | the same-family Claude runtime (no isolated LLM token) | model-performed; comparison blind-spot + selection-side weakness disclosed (rule 3) |

If a future need requires a different prior-art source class, its credential must be a
**separately-named HTTP surface** — never csr's `_ANTHROPIC_AUTH_TOKEN` namespace (that suffix
scopes a credential to csr's Anthropic-gateway substrate, which prior-art-search lacks) and never
psv's "fetched cited source" surface (prior-art-search searches UNcited prior art — a different
direction, proposal §1 / §8 Q5).

## Oracle strength: TWO layers weaker than psv (load-bearing)

psv's oracle is a **fetched authoritative source** — strong-decoupling at the FETCH step but
tier-2 partial under model-mediated COMPARISON (psv §3). prior-art-search's oracle is the
**searchable prior-art corpus**, which adds a SELECTION-side weakness on top of that
comparison-side weakness:

1. **Comparison-side** (shared with psv): the claim-vs-prior-art comparison is model-judged — `clear-under-search` means the model found no collision, not that none exists.
2. **Selection-side** (prior-art-search's own): a search result carries ranking bias, recall limits (you cannot search the whole corpus), and the found prior-art text is itself model-extracted from the search return — not a fetched authoritative byte-range.

So prior-art-search is weaker at two layers, not "weak oracle vs strong oracle." This is precisely
why it NEVER emits `novel_confirmed` and why its top-line is a coverage statement
(`collisions_under_known_coverage`), not a verdict. `clear-under-search` = "no collision in what was
searched," NOT "novel." This is the irreducible limit of novelty-checking short of a human
(proposal §3 oracle-strength caveat / ADR §8 Q4).

## SSRF posture

`search_prior_art.py` fetches the URLs a prior-art search returns to QUOTE the found text — no
allowlist, no private-IP blocklist, and it follows redirects (urllib default). The threat model
bounds the blast radius: the artifact + search queries are **operator-supplied** (not untrusted
external input), results return to the **same operator**, fetches are capped, and the primitive is
**read-only**. Under that model, SSRF is an accepted, **documented** Phase-A risk (rule 3 — never
silent), not a hidden one. Phase-B hardening options: a web-search-provider / arXiv / known-repo
**allowlist** + a private-IP / link-local **blocklist** + a redirect cap. An operator who runs
prior-art-search on untrusted-authored artifacts MUST add that hardening first.

## Running the pipeline

The orchestrator drives it (see `SKILL.md` Quick Start):

1. spawn the `agents/novelty-claim-extractor.agent.md` role prompt (fresh context) → the novelty-claim list.
2. per novelty claim: search its prior art — the orchestrator's built-in search/fetch tools,
   OR `python3 infra/scripts/search_prior_art.py <query>` (the testable stdlib primitive).
3. compare each claim against found prior art → collision verdict (a collision-verifier step;
   `clear-under-search` is counted only).
4. `python3 infra/scripts/coverage_driver.py <collision-verdicts.json> --artifact <ref>` →
   the collision-record + collision-findings packet (enforces the fetched-quote invariant,
   the M=C+N+U+I sum, M=0/I>0 escalation, and forbids `novel_confirmed`).

No provider token is required to run prior-art-search on OPEN prior art (arXiv abstracts, public
repos are credential-free). The web-search API key (`<NAME>_SEARCH_API_KEY`) is an OPTIONAL HTTP
surface — when absent, the offline `dogfood.py` gate runs on a recorded fixture (rule-1 skip path).
The different-family LLM tokens (`DEEPSEEK_ANTHROPIC_AUTH_TOKEN` etc.) belong to
`cross-source-review` / `parallel-development`, NOT to prior-art-search.

## Self-gates (definition of done)

```bash
python3 skills/prior-art-search/infra/test/disconnect_check.py
python3 skills/prior-art-search/infra/test/plugin_layout.py
python3 skills/prior-art-search/infra/test/findings_shape_check.py
python3 skills/prior-art-search/infra/test/coverage_policy_check.py
python3 skills/prior-art-search/infra/test/fetched_quote_gate.py
python3 skills/prior-art-search/infra/test/lint_self.py
python3 skills/prior-art-search/infra/test/dogfood.py   # skips gracefully w/o network
```
