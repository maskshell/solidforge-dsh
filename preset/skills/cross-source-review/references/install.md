# cross-source-review — install / provisioning

> How to arm `cross-source-review` (csr) — inside the solidforge workspace OR externally
> (e.g. fedaot wiki). DSH port: the different-family default is `claude` — the DSH
> orchestrator is DeepSeek, so DeepSeek is same-source and never a csr backend. csr's gating is SELF-contained: its self-gates run on csr's own
> infra, NOT the target project's code, so an external project installs nothing (unlike
> parallel-development, whose gates run in the target and need `arm-tools`). csr's only
> runtime dependency is the different-family leg's provider token.

## Provisioning model — env-based, NO arm command

csr is armed by ONE environment variable (the provider token). There is no `arm` command.
csr's self-gates are csr's own (they check csr's scripts/schemas in the solidforge dev
workspace), so the INVOKING project never runs them and installs nothing. The only thing
the invoking project provides at runtime is the different-family leg's token.

## The one required var + where to set it

The default provider needs NO token:

- `claude` (default) needs NO token — `_native_auth: true`, the CLI's own credentials route the call
- token-backed providers (qwen/bigmodel/minimax): set `<NAME>_ANTHROPIC_AUTH_TOKEN` in one of (setdefault; shell wins):
  1. the **preset-root** `.env.solidforge` (DSH site default — one config for every project using the preset; the preset root is the dir holding `agent.cordis.yml`)
  2. the invoking project's `.env` (a `KEY=VALUE` line)
  3. the project's `.env.solidforge` (arm-tools-provisioned; authoritative among files)

**Sole source (namespace isolation)**: the wrapper reads ONLY `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` for a provider's token. The provider's native `<FILENAME>_API_KEY` (e.g. `QWEN_API_KEY`) is NEVER read — the `_ANTHROPIC_AUTH_TOKEN` suffix namespaces the credential to this substrate's Anthropic gateway, so it cannot collide with the native var (which may be set in the same env for a different tool/SDK, possibly a different key/quota). A project carrying both `QWEN_API_KEY` (its own native-SDK use) and `QWEN_ANTHROPIC_AUTH_TOKEN` (this substrate) is the intended state, not a smell. See the namespace-isolation ADR.

## `.env` resolution (CWD-based — why csr is portable)

csr's substrate (`infra/scripts/hetero_doc_review.py`) reads the INVOKING project's env
(`SOLIDFORGE_PROJECT_DIR` or `cwd`), in order:

1. `<cwd>/.env.solidforge` — the host workspace's arm-env IF present (the solidforge arm
   convention; absent + silently skipped in external projects).
2. `<cwd>/.env` — the generic project env.

Then the shell env (always wins; between the two files, the first-loaded wins for a shared
key). So: in solidforge → reads the armed `.env.solidforge`; in an external project →
reads that project's `.env`. CWD-based = portable.

## Optional — the profile selector (`HETERO_DOC_PROFILE`)

`HETERO_DOC_PROFILE` selects the provider NAME(S), resolved against csr's OWN
`infra/scripts/profiles/`. Default `claude`. Comma-list = dual-/multi-different-family (each backend
runs independently; findings merged + tagged with `provider`):

- `HETERO_DOC_PROFILE=claude` (default)
- `HETERO_DOC_PROFILE=claude,qwen3` (dual-different-family)

csr's profile selector is SEPARATE from pd's `HETERO_PROFILE` (the two skills do not share
it). The TOKEN vars ARE shared (same provider → same credential).

## Optional — the timeout (`HETERO_DOC_TIMEOUT`)

`HETERO_DOC_TIMEOUT` sets the per-subprocess wall-clock cap (seconds) for
`hetero_doc_review.py`. Default `600`. The top tier on a cold large doc (e.g. the qwen3
profile mapping `opus`/`sonnet` → `qwen3.8-max`) can exceed 600s and return a
`hetero-subprocess-timeout` malformation. For a known-cold large review: raise
it (e.g. `1200`) to keep the pro tier, OR drop to `--model haiku` (→ the profile's flash
alias) for that call. Do NOT remap the profile alias to dodge a timeout — cold-start is
transient, and a global alias remap permanently sacrifices review depth on warm calls
(ADR #43). `HETERO_DOC_TIMEOUT` is SEPARATE from pd's
`HETERO_TIMEOUT` (mirrors the `HETERO_DOC_PROFILE` / `HETERO_PROFILE` split).

- `HETERO_DOC_TIMEOUT=1200` (example — raise for cold large docs)

## Adding a custom third-party provider (zero code change)

csr ships `infra/scripts/profiles/claude.json` + `qwen.json` (+ bigmodel/minimax). Add another provider by dropping a
`profiles/<name>.json` (ROUTING ONLY — no secret) + setting its token var. csr resolves
the profile against its OWN `profiles/` dir, INDEPENDENT from pd's (adding a csr profile
does NOT affect pd).

### Profile template (routing only)

`profiles/<name>.json` carries `ANTHROPIC_BASE_URL` (the provider's Anthropic-compatible
endpoint) + model aliases (tier → the provider's model id) + an optional `model` default.
NO `ANTHROPIC_AUTH_TOKEN` field, NO `${...}` ceremony. Example — a custom OpenAI-compatible
gateway:

```json
{
  "_provider": "my-gateway",
  "env": {
    "ANTHROPIC_BASE_URL": "https://my-gateway.example.com/anthropic",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "my-strong-model",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "my-fast-model",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "my-cheap-model"
  },
  "model": "my-strong-model"
}
```

### Token-var naming rule

The token var is derived BY CONVENTION from the profile filename:
`<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN`. Non-alphanumeric chars in the filename
collapse to `_` before uppercasing.

| profile filename | token env var |
| --- | --- |
| `claude.json` | none — `_native_auth: true` (the CLI's own credentials) |
| `qwen.json` | `QWEN_ANTHROPIC_AUTH_TOKEN` |
| `bigmodel.json` | `BIGMODEL_ANTHROPIC_AUTH_TOKEN` |
| `openai-compat.json` | `OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN` |

Override the var name via the profile's optional `_credential_env` field (rarely needed — e.g.
a profile that must read a non-conventional var).

csr reads the token from shell / `.env` / `.env.solidforge`, INJECTS it as
`ANTHROPIC_AUTH_TOKEN` into a throwaway chmod-600 temp settings file passed to
`claude -p`, and unlinks it. The real token NEVER touches the committed profile.

### Use the new provider

`HETERO_DOC_PROFILE=<name>` (or `--profile <name>` on the substrate CLI), with
`<UPPERCASE_NAME>_ANTHROPIC_AUTH_TOKEN` set. Done — no code change.

## What needs no arming

- The same-family leg (`agents/doc-reviewer.agent.md`) — a local fresh-context agent; needs nothing
  beyond the Claude Code runtime.
- The convergence engine (`converge.py`) — pure stdlib; jsonschema OPTIONAL (the engine
  graceful-skips schema validation if absent, with an honest coverage note). The solidforge
  dev workspace ships jsonschema via `uv sync` (dev deps, fix C) — the SKIP note appears
  only in environments without it.
- **Record schema version note (fix A / ADR #3)**: records produced before the retention
  fix (round `findings` + `dispositions` required) no longer validate against the current
  `convergence-record.schema.json`. Historical counts-only records (e.g. any emitted before
  2026-08) are accepted as-is — no migration (ADR #3); treat them as version-0 records.
- csr's self-gates — run on csr's own infra (the solidforge dev workspace). An external
  project invoking csr NEVER runs them.
