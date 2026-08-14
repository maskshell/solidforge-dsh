# install — primary-source-verification provisioning

> psv is **env-armed** (no arm command). Its gates are self-gates (workspace rule 1);
> it has NO tools/post-execute hooks of its own — the extract→fetch→verdict→coverage pipeline
> is orchestrator-driven, not hook-driven. This doc is the credential-surface reference.

## Credential surface (differs from cross-source-review — read this, do NOT inherit csr's)

csr's `install.md` token-isolation pattern targets csr's **heterogeneous `claude -p`
substrate** — an Anthropic-gateway LLM token (`<NAME>_ANTHROPIC_AUTH_TOKEN`). **psv
does not have that substrate** (it is a single extract→fetch→verdict→coverage pipeline;
the oracle is the fetched source TEXT, not a different-family model — proposal §3,
iteration-plan PSV-I3 / outer-ring novel-1). So csr's LLM-token namespace **does not apply**.

psv's actual credential surface:

| Source class | Credential | Behavior |
| --- | --- | --- |
| Open sources — arXiv abstracts, Crossref, public repos, docs | **none** | fetched credential-free (`fetch_source.py`, stdlib `urllib`) |
| Paywalled / auth-gated (HTTP 401/403) | **not used** | NOT fetched — the claim is returned `unverifiable` (escalate to human) |
| The claim-vs-text comparison | the same-family Claude runtime (no isolated LLM token) | model-performed; comparison blind-spot disclosed (rule 3) |

If a future need requires fetching paywalled sources, that credential must be a
**separately-named HTTP surface** — never csr's `_ANTHROPIC_AUTH_TOKEN` namespace
(that suffix scopes a credential to csr's Anthropic-gateway substrate, which psv lacks).

## SSRF posture (outer-ring W4)

`fetch_source.py` fetches **arbitrary URLs the artifact cites** — no allowlist, no
private-IP blocklist, and it follows redirects (urllib default). The threat model
bounds the blast radius: artifacts are **operator-supplied** (not untrusted
external input), results return to the **same operator**, fetches are capped at
200 KB, and the primitive is **read-only**. Under that model, SSRF is an accepted,
**documented** Phase-A risk (rule 3 — never silent), not a hidden one. Phase-B
hardening options: an arXiv / Crossref / known-repo **allowlist** + a private-IP /
link-local **blocklist** + a redirect cap. An operator who runs psv on
untrusted-authored artifacts MUST add that hardening first.

## Running the pipeline

The orchestrator drives it (see `SKILL.md` Quick Start):

1. spawn the `agents/claim-extractor.agent.md` role prompt (fresh context) → claim list.
2. per admissible claim: fetch its cited source — the orchestrator's built-in fetch tool,
   OR `python3 infra/scripts/fetch_source.py <url>` (the testable stdlib primitive).
3. spawn the `agents/claim-verifier.agent.md` role prompt per claim (given the claim + fetched text) → verdict.
4. `python3 infra/scripts/coverage_driver.py <verdicts.json> --artifact <ref>` →
   the coverage-record + doc-findings packet (enforces the fetched-quote invariant,
   the M=N+R+W+K sum, M=0/K>0 escalation, and forbids `correctness_converged`).

No provider token is required to run psv (open sources are credential-free). The
different-family LLM tokens (`DEEPSEEK_ANTHROPIC_AUTH_TOKEN` etc.) belong to
`cross-source-review` / `parallel-development`, NOT to psv.

## Self-gates (definition of done)

```bash
python3 skills/primary-source-verification/infra/test/disconnect_check.py
python3 skills/primary-source-verification/infra/test/plugin_layout.py
python3 skills/primary-source-verification/infra/test/findings_shape_check.py
python3 skills/primary-source-verification/infra/test/coverage_policy_check.py
python3 skills/primary-source-verification/infra/test/fetched_quote_gate.py
python3 skills/primary-source-verification/infra/test/lint_self.py
python3 skills/primary-source-verification/infra/test/dogfood.py   # skips gracefully w/o network
```
