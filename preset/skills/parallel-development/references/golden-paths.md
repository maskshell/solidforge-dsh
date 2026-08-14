# Golden-Path Registry + L1/L2 Hybrid Injection

Solves context pollution: the outer-ring reviewer must not retrieve historical low-quality code from the knowledge base. Only curated best practices are indexed, and they expire.

Built on the existing Graphiti memory integration (see [memory-protocol.md](memory-protocol.md)).

## Golden-path episode convention (@Agent-Golden-Ref)

A golden path is a Graphiti episode tagged `@Agent-Golden-Ref` with explicit ownership and expiry. Promote ONLY core-framework-layer code or code a senior developer explicitly marked. Never bulk-index the whole codebase.

Add a golden path:

```text
mcp__graphiti__add_memory(
  name="Golden-Ref: <pattern name>",
  episode_body="""@Agent-Golden-Ref
responsible_party: <owner>
reviewed_at: 2026-06-18
expires_at: 2026-09-18
quarterly_review: true
domain: python|swift|web|rust|java|go|visual
module: app/services/

<best-practice code slice + why it is the reference>""",
  source="text",
  source_description="golden-path"
)
```

The `domain:` enum above must stay identical to the one in [memory-protocol.md](memory-protocol.md) — same controlled vocabulary, must not drift.

Required fields: `responsible_party`, `reviewed_at`, `expires_at` (quarterly). Without `expires_at` the entry is reported as `unreviewed` by the degrade scan.

## Retrieval (L2 precedent, Warning tier)

During the outer-ring review, retrieve a few-shot slice:

```text
mcp__graphiti__search_memory_facts(query="@Agent-Golden-Ref <domain> <concept>", max_facts=3)
```

L2 precedents are WARNING tier only: they guide naming and style, they do not block. A golden path always wins over a cold-start pattern.

## Quarterly expiry (auto-degrade)

Run `golden_degrade.py` quarterly (or on demand). It takes the retrieved episodes (JSON on stdin) and computes which are past `expires_at`:

```text
mcp__graphiti__search_memory_facts(query="@Agent-Golden-Ref") \
  | python3 infra/scripts/golden_degrade.py
```

For each expired entry, re-store the body with the tag `@Golden-Ref-STALE` (Warning tier, no longer a few-shot source) and prompt the responsible party to re-review or remove. Storage is via MCP; the script only computes expiry deterministically.

This prevents stale templates from becoming a new pollution source.

## Front-end smell filter (promotion gate)

Before code is tagged `@Agent-Golden-Ref`, it must pass a static smell filter (SonarQube: high cyclomatic complexity or missing tests disqualifies). The skill does not ship SonarQube; this is a documented promotion convention.
The optional pre-tag step refuses to tag a candidate if a `sonar-project.properties`

+ passing scan is absent.

## Cold-start fallback (Warning tier)

When a golden-path search returns zero `@Agent-Golden-Ref` hits, fall back to the standardized design-pattern templates in `infra/templates/cold-start-patterns/` (service-layer decoupling, async concurrency baseline, ...). These are Warning tier, not authoritative for the project. A real golden path always overrides them.

## L1/L2 summary

+ L1 constitution (static red lines): codable ones -> inner arch-contract gate (Blocker); uncodable ones -> `AGENTS.md` L1 Constitution section -> reviewer Blocker.
+ L2 precedents (dynamic few-shot): RAG from golden paths (or cold-start) -> Warning, conditional pass.
