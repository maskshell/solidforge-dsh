#!/usr/bin/env python3
"""hetero_review.py — different-family (different-family) adversarial review wrapper.

Spawns a non-interactive Claude Code subprocess on a DIFFERENT model family (e.g.
DeepSeek) as an additive adversarial second opinion on the same-family reviewer.
The same-family reviewer (solidforge:code-reviewer, ADR #16 outer ring) stays
PRIMARY; different-family is opt-in, high-stakes items only. The orchestrator (interactive CC)
stays on its primary provider unchanged.

Decision anchor: ADR #40 (`references/design-decisions.md §40`). Operational plan:
`docs/hetero-orchestration-proposal.md`. This wrapper is Phase 1 deliverable P1-4
(single-round core) + P1-5 (multi-round debate + cap).

==============================================================================
FLAG-SURFACE MANIFEST — verified against Claude Code v2.1.201 (2026-07); re-probed
against v2.1.207 (2026-07) after a substrate regression (see NOTE below).
If a CC upgrade breaks the wrapper, update this manifest + the flag list in
`_claude_argv()`. `--bare` (minimal mode: skip hooks/LSP/plugin) is the documented
FALLBACK if a CC upgrade breaks the hook/LSP surface — it is NOT the default (the
default keeps hooks so --observe-hooks can see the deterministic gates).
NOTE (v2.1.207 regression): CC's `--json-schema` validator now bundles ONLY Draft-07
in its draft registry; it rejects schemas declaring Draft 2019-09 / 2020-12 (the
`$schema` marker is treated as an unresolvable ref). The wrapper strips `$schema`
via `_strip_schema_marker_for_cc` before the `--json-schema` arg — the committed schema
stays Draft 2020-12 (loop_state's jsonschema consumer uses an explicit validator class,
unaffected). A heterogeneous backend that then exhausts CC's structured-output retries
(`error_max_structured_output_retries`) auto-falls-back to defensive parse via
`run_claude` (`fell_back_to_unstructured` surfaced in coverage). Backward-compat:
`$schema` is optional, so a validator that accepted it (v2.1.201) accepts its absence
(v2.1.207); the fallback is strict-first, gated on the exact fingerprint. Probe matrix
in `_strip_schema_marker_for_cc`'s docstring. Ported from csr (ADR #45 — rule 7).
Flags used:
  claude -p
    --settings <temp-materialized.json>  per-process provider config — the wrapper
                                         materializes this from profiles/<name>.json +
                                         the runtime token (NOT a committed path)
    --model <alias>                    tier/model alias resolved via the profile env
    --output-format json               structured return (typed findings)
    --json-schema <schema-json>        the findings shape (violation-log.schema.json)
    --permission-mode bypassPermissions
    --no-session-persistence           stateless per invocation (ADR #40 (h))
    --max-budget-usd <cap>             hard cost breaker per subprocess (a full review
                                       of a large file can cost >$1 — set headroom)
    [--include-hook-events]            gate observability (requires stream-json output;
                                       selected by --observe-hooks)
    [--allowedTools "Read Grep Glob Bash"]
    -p "<adversarial prompt>"
`--settings` receives a THROWAWAY temp file the wrapper builds (the committed
profiles/<name>.json is a TEMPLATE; CC does NOT expand ${VAR} in --settings env,
so the wrapper expands the token itself — verified CC v2.1.201). `--json-schema`
takes the schema JSON inline (read from file + passed as one arg).
`--include-hook-events` requires `--output-format stream-json`, so --observe-hooks
switches the output to stream-json and parses the final structured result + hook
events from the stream.
==============================================================================

PROVIDER-TEMPLATE + TOKEN-INJECTION PATTERN:
  profiles/<provider>.json — committed TEMPLATES with ROUTING ONLY (BASE_URL +
                               model aliases). NO `ANTHROPIC_AUTH_TOKEN` field, NO
                               `${...}` token ceremony — drop in a template + set one
                               env var, that's it.
  token-var convention — `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` (deepseek ->
                               `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`, qwen3 ->
                               `QWEN3_ANTHROPIC_AUTH_TOKEN`). Override with the
                               template's optional `_credential_env` for a non-convention name.
  --profile <name[,name2...]> or $HETERO_PROFILE — select provider(s); comma-list
                               = dual-/multi-different-family (each backend runs independently,
                               findings merged + tagged with `provider`).
  token source — shell env (`export DEEPSEEK_ANTHROPIC_AUTH_TOKEN=...`) or
                 <project>/.env (shell wins). The wrapper reads it, INJECTS it as
                 `ANTHROPIC_AUTH_TOKEN` into a chmod-600 temp settings file, passes
                 the file to claude, unlinks it. Other `${VAR}` refs (non-token
                 fields) in the template still expand.
  namespace isolation — the `_ANTHROPIC_AUTH_TOKEN` suffix is the SOLE token
                 source; the provider's native `<FILENAME>_API_KEY` is NEVER read
                 (it may serve another tool/SDK in the same env, so reading it
                 would risk a credential meant for a different use). See the
                 namespace-isolation ADR.

Findings schema (P1-2 decision): REUSE `infra/schemas/violation-log.schema.json`.
Its finding shape carries `severity` / `rule` / `file` / `line` / `detail` /
`suggestion`, which map 1:1 to the reconciliation fields (severity / defect_kind /
location) the same-family reviewer emits — so P1-5 reconciliation compares
LIKE-SHAPED findings. A different-family "could not verify X" disclosure maps to
severity=warning with the detail naming the unchecked area (rule 3/4 — never silent).

loop_state driving (ADR #39, ADR #40 (g)): the wrapper drives loop_state around
the subprocess so the run-record is truthful from day one — `init` →
`bump-iteration` → `gate-fail <fingerprint>` on malformation → `record-outer`
→ `mark-converged` → `run-record` (full standalone cycle). `--embedded` skips
init/mark-converged/run-record (the orchestrator owns those when this wrapper runs
as the convergence-loop outer ring).

Substrate-error handling (ADR #41): a non-zero CC exit is NOT automatically a
malformation. CC puts recoverable substrate errors (budget cap, turn cap, provider
overwhelm) in STDOUT as a clean `{"is_error":true,"subtype":...,"errors":[...]}`
envelope (stderr stays empty). `run_claude` parses it; subtypes in
`DEGRADABLE_CC_SUBTYPES` DEGRADE — the different-family leg contributes 0 findings + a coverage
note + a `hetero-degraded-<subtype>` fingerprint (so the thrashing breaker escalates
persistent degradation), and the verdict stays pass/rewrite from the OTHER providers
(different-family is additive — ADR #40). Non-degradable subtypes (invalid-args, auth) and
unparseable output still malform → rewrite (never mask a regression — rule 3). The
default `--budget-usd 4.0` leaves headroom under loop_state's global 5.0 cap.

USD caveat (ADR #42): for non-Anthropic backends `--max-budget-usd` is a runaway
breaker, NOT real cost — the Anthropic-compatible API returns tokens only (no price),
so CC's USD cannot reflect provider spend. Provider-independent bounds: CC's turn limit
(`error_max_turns`) per subprocess + `step_cap_S` globally; real accounting is the
provider's own dashboard.

Timeout (ADR #43): the per-subprocess wall-clock cap is `--timeout` (default 600, or
$HETERO_TIMEOUT). A cold large-diff review on the pro tier can exceed 600s — raise the
timeout OR drop a tier (`--model haiku`), do NOT remap the profile alias (timeout ⊥ model
selection; cold-start is transient — DeepSeek auto-caches ~99% after the first call).

Self-contained (workspace rule 7): duplicates the loop_state subprocess pattern
rather than importing a shared lib, so the script stays independently deployable.
Pure stdlib. Exits 0 on success; non-zero on argument/IO/parse errors or a
malformed subprocess return.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# loop_state.py lives alongside this script (peer). Mirror plan_queue.py's pattern.
LOOP_STATE_PY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "loop_state.py"
)
SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")
FINDINGS_SCHEMA = os.path.join(SCHEMAS_DIR, "violation-log.schema.json")
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

# CC substrate errors that DEGRADE (recoverable — the different-family leg contributed nothing; the
# same-family primary stands, per ADR #40 additive). Unknown subtypes + auth/invalid-args
# errors are NOT here — they malform (surface the cause), never silently mask a regression
# (rule 3; the FLAG-SURFACE MANIFEST above is the precedent for treating CC drift as
# non-silent). ADR #41.
DEGRADABLE_CC_SUBTYPES = frozenset(
    {
        "error_max_budget_usd",
        "error_max_turns",
        "error_overwhelmed",
        "error_session_expired",
        "error_session_not_found",
    }
)

# The Morph-caveat signal (ADR #40): a heterogeneous backend exhausts CC's
# --json-schema structured-output retries (CC demands the exact schema shape; a
# non-Claude backend may not comply within the retry budget). This is NOT degradable
# (it is a backend-capability gap, not a transient cap) BUT it IS recoverable via the
# wrapper's own defensive parse — retry once WITHOUT --json-schema (the live-substrate
# path; the wrapper's _extract_json_object + _validate_findings_shape handle a fenced /
# preamble-prose JSON return). See run_claude's auto-fallback. Verified CC v2.1.207.
# Ported from csr's hetero_doc_review.py (ADR #45 — rule 7 copy-pattern).
STRUCTURED_OUTPUT_RETRY_FP = "hetero-cc-error:error_max_structured_output_retries"


def _run_loop_state(argv, project_dir):
    """subprocess `loop_state.py <argv>` rooted at project_dir. Returns (rc, output)."""
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=project_dir)
    proc = subprocess.run(
        [sys.executable, LOOP_STATE_PY] + argv,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _read_schema(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _strip_schema_marker_for_cc(schema_json):
    """Compat shim — strip the `$schema` draft marker before passing the schema to CC's
    `--json-schema` arg. CC's `--json-schema` validator registers ONLY Draft-07 in its
    bundled draft registry; it rejects schemas declaring Draft 2019-09 / 2020-12 with
    `--json-schema is not a valid JSON Schema: no schema with key or ref "<draft-uri>"`
    (the marker URI is treated as an unresolvable ref). Probe matrix (CC v2.1.207):
      Draft 2020-12 / 2019-09 / Draft-06 `$schema` -> REJECT
      Draft-07 `$schema` / no `$schema`            -> ACCEPT
    The committed schema stays Draft 2020-12 (correct; `$defs` is 2019-09+): the OTHER
    consumer, loop_state's record validation (jsonschema lib), uses an EXPLICIT
    `Draft202012Validator(schema)` class (not auto-detect from `$schema`), so stripping
    the marker does not affect it. Backward-compat: `$schema` is an OPTIONAL field; a
    validator that accepts a schema WITH it (CC v2.1.201 per the FLAG-SURFACE MANIFEST)
    accepts one WITHOUT. The shim lives at the CC boundary (this wrapper), NOT in the
    committed schema — adapt-at-the-edge, do not mutilate the source. Ported from csr's
    hetero_doc_review.py (ADR #45 — rule 7 copy-pattern)."""
    try:
        obj = json.loads(schema_json)
    except json.JSONDecodeError:
        return schema_json  # let CC surface the parse error verbatim
    if isinstance(obj, dict) and "$schema" in obj:
        obj = {k: v for k, v in obj.items() if k != "$schema"}
        return json.dumps(obj)
    return schema_json


def _load_prior(prior_arg):
    """Load prior-findings context: JSON string, `@file` path, or '' → None."""
    if not prior_arg:
        return None
    raw = prior_arg
    if prior_arg.startswith("@"):
        try:
            with open(prior_arg[1:], "r", encoding="utf-8") as fh:
                raw = fh.read()
        except FileNotFoundError:
            print(
                f"warn: prior-findings file not found: {prior_arg[1:]}; ignoring",
                file=sys.stderr,
            )
            return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Not fatal — degrade to a string hint in the prompt context.
        return [{"severity": "warning", "rule": "prior-context", "detail": raw}]


# --- provider-template + token-injection (the profiles/<provider>.json pattern) --
#
# profiles/<provider>.json files are COMMITTED TEMPLATES with ROUTING ONLY (BASE_URL
# + model aliases) — NO secret, NO `${...}` token ceremony. The auth token is read
# at runtime from the env var DERIVED BY CONVENTION from the filename:
# `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` (deepseek -> DEEPSEEK_ANTHROPIC_AUTH_TOKEN,
# qwen3 -> QWEN3_ANTHROPIC_AUTH_TOKEN). The wrapper injects it as ANTHROPIC_AUTH_TOKEN
# into a THROWAWAY temp settings file passed to `claude -p` (CC does NOT expand
# ${VAR} itself — verified CC v2.1.201). A template may override the var name via an
# optional `_credential_env` field; other `${VAR}` refs (non-token fields) still expand.
# Selection: --profile <name[,name2...]> (multi = dual-/multi-different-family) or HETERO_PROFILE.


def _project_root_for_env():
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def _load_dotenv_file(path):
    """Load KEY=VALUE pairs from one file into os.environ (setdefault — shell wins).
    Best-effort: missing file / malformed line silently skipped."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _preset_root():
    """Walk up from this script to the preset root (the directory holding
    agent.cordis.yml) — the DSH-native resolution that needs no env var: the
    wrapper knows where IT lives, and the preset root is the composition file's
    directory. Returns None when run outside a preset tree."""
    cur = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.exists(os.path.join(cur, "agent.cordis.yml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:  # filesystem root reached
            return None
        cur = parent


def _load_dotenv():
    """DSH port — three-tier env resolution (setdefault: the shell always wins;
    between files the FIRST loaded wins for a shared key, so they are loaded in
    HIGHEST-precedence-first order):

      1. <project>/.env.solidforge       — the arm-tools-provisioned Solid Forge
         secrets file; authoritative for the Solid Forge vars among files.
      2. <project>/.env                  — the project's generic app env.
      3. <preset-root>/.env.solidforge   — the DSH site default: one config covers
         every project using the solidforge preset (the preset root is the dir
         holding agent.cordis.yml).

    Any file may carry the provider tokens. Best-effort: missing files are
    silently skipped."""
    root = _project_root_for_env()
    _load_dotenv_file(os.path.join(root, ".env.solidforge"))
    _load_dotenv_file(os.path.join(root, ".env"))
    preset = _preset_root()
    if preset:
        _load_dotenv_file(os.path.join(preset, ".env.solidforge"))


_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env_values(obj):
    """Expand ${VAR} in every string value at ANY depth of `obj` from os.environ.
    Unset vars are left as-is (the token-presence check in _materialize_profile
    catches a missing _token_env value before the spawn). Recurses into nested
    dicts/lists — the profile shape is {env: {ANTHROPIC_AUTH_TOKEN: "${...}"}}."""

    def expand(node):
        if isinstance(node, str):
            return _ENV_VAR_RE.sub(
                lambda m: os.environ.get(m.group(1), m.group(0)), node
            )
        if isinstance(node, dict):
            return {k: expand(v) for k, v in node.items()}
        if isinstance(node, list):
            return [expand(x) for x in node]
        return node

    return expand(obj)


def _resolve_profile_path(name):
    p = os.path.join(PROFILES_DIR, f"{name}.json")
    if not os.path.exists(p):
        sys.exit(
            f"error: unknown provider profile '{name}' (no {p}). "
            "Committed templates live in infra/scripts/profiles/; see model-routing.md."
        )
    return p


def _resolve_token_var(name, template):
    """The env var holding the provider's auth token.

    Override: the template's optional `_credential_env` field. Default (convention):
    `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` — e.g. `deepseek` ->
    `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`, `qwen3` -> `QWEN3_ANTHROPIC_AUTH_TOKEN`,
    `openai-compat` -> `OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN`. The convention lets a user
    drop in `profiles/<name>.json` with ROUTING ONLY (no `_credential_env`, no `${...}`) and
    the wrapper resolves the token var from the filename — zero ceremony per provider.
    """
    if template.get("_token_env"):
        return template["_token_env"]
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    return f"{sanitized}_ANTHROPIC_AUTH_TOKEN"


def _materialize_profile(name):
    """Load profiles/<name>.json, resolve + read the token, expand any ${VAR} in the
    template, INJECT the token as ANTHROPIC_AUTH_TOKEN, write a throwaway chmod-600
    temp settings file. Returns the temp path (caller unlinks after the spawn).

    The template carries ONLY routing (BASE_URL + model aliases) — no `ANTHROPIC_AUTH_TOKEN`
    field, no `${...}` token ceremony. The wrapper injects the token from the
    convention var (or `_credential_env` override); other `${VAR}` refs in the template
    (e.g. a custom header) still expand. The real token never touches the committed
    profile."""
    src = _resolve_profile_path(name)
    with open(src, "r", encoding="utf-8") as fh:
        tmpl = json.load(fh)
    native_auth = bool(tmpl.get("_native_auth"))
    if not native_auth:
        token_var = _resolve_token_var(name, tmpl)
        token = os.environ.get(token_var, "")
        if not token:
            sys.exit(
                f"error: provider '{name}' needs the env var ${token_var}. The wrapper reads it "
                "from $SOLIDFORGE_PROJECT_DIR or <cwd>/.env.solidforge then <cwd>/.env (shell wins) — "
                "if you cd'd into the skill dir, re-run from the PROJECT ROOT (where .env.solidforge "
                "lives) via the ${SOLIDFORGE_PRESET_ROOT} absolute path. Convention: "
                "<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN; override via the template's `_credential_env`. "
                "See model-routing.md."
            )
    env_block = _expand_env_values(tmpl.get("env", {}))
    if not isinstance(env_block, dict):
        env_block = {}
    if not native_auth:
        env_block["ANTHROPIC_AUTH_TOKEN"] = (
            token  # convention injection (overrides any stale value)
        )
    payload = {"env": env_block}
    if tmpl.get("model"):
        payload["model"] = tmpl["model"]
    fd, tmp_path = tempfile.mkstemp(suffix=f"-hetero-{name}.json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    return tmp_path


def _prepare_dsh_home(name, tmpl):
    """DSH-NATIVE substrate: heterogeneity = a DIFFERENT LLM on the SAME harness.

    Builds a throwaway DSH_HOME whose settings.yaml (JSON — a valid YAML document)
    pins agent-default-model to the profile's provider route + model, and passes
    the profile's credential env (the DSH adapter's apiKeyEnv) to the subprocess.
    The `dsh --profile headless "<prompt>"` subprocess is a fresh, stateless DSH
    session: same harness, different model family, out of process — the paper's
    §4.4 decoupling boundary re-derived for a first-class-multi-provider harness
    (§8 open problem 6), WITHOUT dragging in a foreign harness."""
    home = tempfile.mkdtemp(prefix=f"sf-dsh-hetero-{name}-")
    provider = str(tmpl.get("provider") or name)  # filename IS the route
    am = {
        "provider": provider,
        "model": str(tmpl.get("model", "")),
    }
    # reasoningEffort is OPTIONAL: some routes (e.g. GLM via hand-declared pi-ai
    # routes) support no explicit effort level at all and refuse "high"/"off"
    # alike — omission defers to the adapter default instead of failing.
    if tmpl.get("reasoning_effort"):
        am["reasoningEffort"] = str(tmpl["reasoning_effort"])
    settings = {"agent-default-model": am}
    # Always emit the pi-ai section: a CATALOG route needs only apiKeyEnv (the
    # adapter is dormant until a settings section supplies profiles), while a
    # hand-declared route carries baseURL/api/models in `provider_profile`.
    providers_entry = dict(tmpl.get("provider_profile") or {})
    cred_env = str(
        tmpl.get("_credential_env")
        or f"{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}_API_KEY"
    )
    if cred_env:
        providers_entry.setdefault("apiKeyEnv", str(cred_env))
    if providers_entry:
        settings["llm-pi-ai"] = {"providers": {provider: providers_entry}}
    with open(os.path.join(home, "settings.yaml"), "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
    env_block = {}
    # Credential var is ROUTE-DERIVED by default: <UPPERCASE(route)>_API_KEY is
    # pi-ai's own env convention (zai-coding-cn -> ZAI_CODING_CN_API_KEY,
    # minimax-cn -> MINIMAX_CN_API_KEY). `_credential_env` is only an escape
    # hatch for routes whose convention differs.
    cred_env = str(
        tmpl.get("_credential_env")
        or f"{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}_API_KEY"
    )
    if cred_env:
        token = os.environ.get(str(cred_env), "")
        if not token:
            shutil.rmtree(home, ignore_errors=True)
            sys.exit(
                f"error: profile '{name}' (route '{provider}') needs the "
                f"credential env var ${cred_env}. Set it in your shell, "
                f"<project>/.env.solidforge, <project>/.env, or <preset-root>/.env.solidforge "
                f"(the three-tier DSH resolution). No token is stored in the committed profile."
            )
        env_block[str(cred_env)] = token
    return home, env_block


SAME_SOURCE_FAMILIES = frozenset({"deepseek"})  # the DSH orchestrator's family


def _family_checks(names, profiles_dir=None):
    """Same-source guard + dual-family honesty (paper §4.1 / §3.3), powered by the
    profiles' `_family` metadata:

      - a profile whose _family is the ORCHESTRATOR's family is REFUSED
        (fail-fast — the heterogeneous leg requires a different model family);
      - a dual run whose profiles share ONE family proceeds with an honest note
        (same-family duality adds no blind-spot diversity);
      - a profile declaring no _family is noted (the guard is inactive for it —
        never silent).

    Returns (errors: list[str], notes: list[str])."""
    errors, notes = [], []
    fams = {}
    for n in names:
        src = os.path.join(profiles_dir or PROFILES_DIR, f"{n}.json")
        if not os.path.exists(src):
            continue  # _resolve_profile_path fail-fasts separately
        with open(src, "r", encoding="utf-8") as fh:
            tmpl = json.load(fh)
        fam = tmpl.get("_family")
        if fam is None:
            notes.append(
                f"profile {n} declares no _family — same-source guard inactive for it"
            )
            continue
        fam = str(fam)
        if fam in SAME_SOURCE_FAMILIES:
            errors.append(
                f"profile {n} (family {fam}) is SAME-SOURCE as the DSH orchestrator — "
                "the heterogeneous leg requires a different model family (paper §4.1); "
                "arm a different-family route"
            )
        fams.setdefault(fam, []).append(n)
    for fam, ns in fams.items():
        if len(ns) > 1 and fam not in SAME_SOURCE_FAMILIES:
            notes.append(
                f"profiles {', '.join(sorted(ns))} share family {fam} — same-family "
                "duality adds no blind-spot diversity"
            )
    return errors, notes


def _leg_plan(
    name, model, schema_json, prompt, budget_usd, allowed_tools, observe_hooks
):
    """Substrate dispatch per provider profile.

    - `substrate: dsh` (the DSH port's DEFAULT): same harness, different LLM —
      a fresh stateless `dsh --profile headless` subprocess with its own throwaway
      DSH_HOME pinning the provider route. No foreign harness involved.
    - `substrate: claude-code` (explicit opt-in ONLY): the upstream mechanism
      (`claude -p --settings <profile>`), retained for backends that only expose
      an Anthropic-compatible endpoint. It drags in a FOREIGN harness (Claude
      Code) and is never the default."""
    src = _resolve_profile_path(name)
    with open(src, "r", encoding="utf-8") as fh:
        tmpl = json.load(fh)
    if tmpl.get("substrate", "dsh") == "dsh":
        home, env_block = _prepare_dsh_home(name, tmpl)
        return {
            "substrate": "dsh",
            "home": home,
            "env": env_block,
            "prompt": prompt,
            "tmp_path": None,
            "argv": None,
        }
    tmp_path = _materialize_profile(name)
    argv = _claude_argv(
        tmp_path, model, schema_json, prompt, budget_usd, allowed_tools, observe_hooks
    )
    return {
        "substrate": "claude-code",
        "argv": argv,
        "tmp_path": tmp_path,
        "home": None,
        "env": None,
    }


def run_dsh(plan, timeout_s, dry_run, dry_findings):
    """Spawn the DSH-native heterogeneous leg ONCE (or dry-run). Same return dict
    as run_claude: {findings, hook_count, ok, fingerprint, error_subtype, errors}.
    Parses the headless final answer defensively (_extract_json_object +
    _validate_findings_shape — no structured-output schema transport, disclosed
    honestly in the coverage trail by the caller)."""
    base = {"findings": None, "hook_count": 0, "error_subtype": None, "errors": []}
    if dry_run:
        return {**base, "findings": dry_findings, "ok": True, "fingerprint": ""}
    env = dict(os.environ)
    env["DSH_HOME"] = plan["home"]
    env.update(plan["env"])
    argv = ["dsh", "--profile", "headless", plan["prompt"]]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            cwd=_project_root_for_env(),
        )
    except FileNotFoundError:
        return {
            **base,
            "ok": False,
            "fingerprint": "dsh-binary-missing",
            "errors": ["dsh is not on PATH — install the harness launcher"],
        }
    except subprocess.TimeoutExpired:
        return {**base, "ok": False, "fingerprint": "hetero-subprocess-timeout"}
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-800:]
        return {
            **base,
            "ok": False,
            "fingerprint": "dsh-subprocess-error",
            "errors": [tail],
        }
    obj = _extract_json_object(proc.stdout)
    if obj is None:
        return {
            **base,
            "ok": False,
            "fingerprint": "dsh-unparseable-return",
            "errors": ["headless return carried no JSON object"],
        }
    fp = _validate_findings_shape(obj)
    if fp:
        return {
            **base,
            "ok": False,
            "fingerprint": "dsh-shape-invalid",
            "errors": [str(fp)],
        }
    return {**base, "findings": obj, "ok": True, "fingerprint": ""}


def adversarial_prompt(diff_ref, blueprint_ref, prior_findings=None, round_no=0):
    """Build the ADVERSARIAL prompt (ADR #40 (c)).

    "Find what the primary reviewer missed or got wrong" — NOT "validate". Without
    this the loop degenerates into rubber-stamping (proposal §4 main failure mode).
    """
    prior_block = ""
    if prior_findings:
        prior_block = (
            "\n\nThe same-family primary reviewer already found:\n"
            f"{json.dumps(prior_findings, ensure_ascii=False, indent=2)}\n"
            "Your job is NOT to confirm these. Find what they MISSED or got WRONG — "
            "a defect category or code/doc location they did not cover. Restating "
            "the same defect on the same location is NOT a new finding."
        )
    return (
        f"You are an ADVERSARIAL code reviewer on a different model family than the "
        f"primary reviewer — your value is catching what same-family review misses "
        f"(enforcement gaps, silent failure modes, diagnostic UX). "
        f"Review the diff at `{diff_ref}` against the authoritative blueprint "
        f"`{blueprint_ref}`. Hunt for: correctness bugs, security issues, "
        f"performance problems, maintainability defects, and loading-chain / "
        f"rule-5 reachability gaps the primary reviewer did not surface.{prior_block}\n\n"
        f"Return a violation-log-shaped JSON object: "
        f'{{"gate": "hetero-review", "passed": <bool>, "coverage": [<what you checked>], '
        f'"findings": [{{"severity": "blocker"|"warning", "rule": "<defect-kind>", '
        f'"file": "<path>", "line": <int>, "detail": "<concrete quote + why>", '
        f'"suggestion": "<fix direction>"}}]}}. '
        f"A blocker requires concrete evidence (a quote). A guess is a warning. An "
        f"unchecked area is disclosed as a warning with detail, NEVER silenced "
        f"(rule 3/4). Round {round_no}."
    )


def _claude_argv(
    profile, model, schema_json, prompt, budget_usd, allowed_tools, observe_hooks
):
    """Build the claude -p argv. See FLAG-SURFACE MANIFEST above (CC v2.1.201)."""
    argv = [
        "claude",
        "-p",
        "--settings",
        profile,
        "--model",
        model,
        "--permission-mode",
        "bypassPermissions",
        "--no-session-persistence",
        "--max-budget-usd",
        str(budget_usd),
    ]
    if observe_hooks:
        # --include-hook-events REQUIRES stream-json output (CC v2.1.201).
        argv += ["--output-format", "stream-json", "--include-hook-events"]
    else:
        argv += ["--output-format", "json"]
    argv += ["--json-schema", schema_json]
    if allowed_tools:
        argv += ["--allowedTools", allowed_tools]
    argv += ["-p", prompt]
    return argv


def _parse_cc_substrate_error(raw):
    """Extract (subtype, errors) from a CC substrate-error envelope.

    CC exits rc!=0 with EMPTY stderr and puts the reason in stdout as
    `{"type":"result","subtype":"error_max_budget_usd","is_error":true,"errors":[...]}`.
    Handles BOTH output modes: `--output-format json` (a single object) AND
    `--output-format stream-json` (`--observe-hooks`; JSONL — walk for the result event).
    Returns (subtype, errors) for any CC error envelope (the caller decides degrade vs
    malform via DEGRADABLE_CC_SUBTYPES), else (None, []). Defensive: any parse failure →
    (None, []). ADR #41.
    """
    if not raw:
        return None, []
    obj = _try_json(raw)
    if not (isinstance(obj, dict) and obj.get("is_error")):
        # stream-json mode (--observe-hooks): stdout is JSONL — walk for a result event
        # carrying the CC error envelope. Reuses _try_json per line.
        obj = None
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            cand = _try_json(line)
            if isinstance(cand, dict) and cand.get("is_error"):
                obj = cand
                break
    if not (isinstance(obj, dict) and obj.get("is_error")):
        return None, []
    subtype = obj.get("subtype")
    if not isinstance(subtype, str) or not subtype:
        return None, []
    raw_errors = obj.get("errors", [])

    def render(e):
        return e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)

    if isinstance(raw_errors, list):
        errors = [render(e) for e in raw_errors if e is not None]
    elif raw_errors is not None:
        errors = [render(raw_errors)]
    else:
        errors = []
    return subtype, errors


def _stdout_indicates_success(raw):
    """True iff the CC stdout envelope is a SUCCESS (subtype 'success'), regardless of the
    process exit code or the is_error flag. CC's protocol: the result event's `subtype` is
    authoritative — 'success' means a usable result was produced. Handles both
    --output-format json (a single object) and stream-json (JSONL — walk for the result
    event). Defensive: any parse failure -> False.

    Ported from csr's hetero_doc_review.py (CSR-I6 dogfood fix; copy-pattern parity —
    the two wrappers must not diverge on the same substrate event)."""
    if not raw:
        return False
    obj = _try_json(raw)
    if isinstance(obj, dict) and obj.get("subtype") == "success":
        return True
    for line in raw.splitlines():
        cand = _try_json(line.strip())
        if isinstance(cand, dict) and cand.get("subtype") == "success":
            return True
    return False


def _run_claude_once(
    argv, timeout_s, dry_run, dry_findings, dry_malform=False, dry_budget=False
):
    """Spawn the subprocess ONCE (or dry-run). Returns a dict:
    {findings, hook_count, ok, fingerprint, error_subtype, errors}.

    - findings: the parsed violation-log-shaped return (None on malformation/degrade).
    - hook_count: hook events observed (0 unless --observe-hooks).
    - ok: True iff the subprocess exited 0 AND the return parsed cleanly.
    - fingerprint: a malformation fingerprint for loop_state gate-fail ("" when ok or when
      the error DEGRADED — degraded legs are not malformations).
    - error_subtype: a CC substrate-error subtype when rc!=0 but stdout carried a clean
      `is_error` envelope (None otherwise). The caller DEGRADES on DEGRADABLE_CC_SUBTYPES,
      malforms on the rest. ADR #41.
    - errors: the envelope's `errors` strings (for the coverage/degrade note).
    """
    base = {"findings": None, "hook_count": 0, "error_subtype": None, "errors": []}
    if dry_run:
        if dry_malform:
            # Offline malformation path (gate-fail-survives-init test; dogfood blocker).
            return {**base, "ok": False, "fingerprint": "dry-run-malform"}
        if dry_budget:
            # Offline budget-exhaustion (degrade test; rule 4 — no real call). ok=False +
            # fingerprint="" + error_subtype set ⇒ main classifies DEGRADED.
            return {
                **base,
                "ok": False,
                "fingerprint": "",
                "error_subtype": "error_max_budget_usd",
                "errors": ["Reached maximum budget ($0.05)"],
            }
        # Offline path for the P1-7 wiring test (rule 4: no real model call in the gate).
        return {**base, "findings": dry_findings, "ok": True, "fingerprint": ""}

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {**base, "ok": False, "fingerprint": "hetero-subprocess-timeout"}

    if proc.returncode != 0 and not _stdout_indicates_success(proc.stdout):
        # CC substrate errors (budget/turns/overwhelmed) land in STDOUT as a clean envelope;
        # stderr is empty. Parse BEFORE malforming — a recoverable cap DEGRADES, not rewrites.
        # (A non-zero exit WITH a success envelope is a CC backend quirk: subtype is
        # authoritative, the result is usable — short-circuit to the normal parse below.
        # Ported from csr, CSR-I6 dogfood.)
        subtype, errors = _parse_cc_substrate_error(proc.stdout)
        if subtype in DEGRADABLE_CC_SUBTYPES:
            return {
                **base,
                "ok": False,
                "fingerprint": "",
                "error_subtype": subtype,
                "errors": errors,
            }
        if subtype:
            # A NON-degradable CC error (invalid-args / auth) — surface the subtype in the
            # fingerprint (richer than hetero-subprocess-rc{N}) and malform; do NOT mask it.
            fp = f"hetero-cc-error:{subtype}"
        else:
            fp = f"hetero-subprocess-rc{proc.returncode}"
        return {**base, "ok": False, "fingerprint": fp, "errors": errors}

    raw = proc.stdout
    if argv[argv.index("--output-format") + 1] == "stream-json":
        findings, hook_count, ok, fp = _parse_stream_json(raw)
    else:
        findings, hook_count, ok, fp = _parse_json_return(raw)
    return {
        **base,
        "findings": findings,
        "hook_count": hook_count,
        "ok": ok,
        "fingerprint": fp,
    }


def _argv_without_json_schema(argv):
    """Return a copy of argv with `--json-schema` and its value removed (defensive-parse
    mode). Used by run_claude's structured-output-retry fallback. `--json-schema <value>`
    is a two-token arg; drop both. Leaves `--output-format json` intact so the CC wrapper
    envelope is still parsed. Ported from csr (ADR #45 — rule 7 copy-pattern)."""
    out = []
    skip_next = False
    for a in argv:
        if skip_next:
            skip_next = False
            continue
        if a == "--json-schema":
            skip_next = True
            continue
        out.append(a)
    return out


def run_claude(
    argv, timeout_s, dry_run, dry_findings, dry_malform=False, dry_budget=False
):
    """Spawn the subprocess (or dry-run), with a ONE-SHOT auto-fallback on the Morph-caveat
    structured-output-retry failure. Signature + DEGRADE logic preserved (ADR #41).

    A heterogeneous backend that exhausts CC's `--json-schema` structured-output retries
    (STRUCTURED_OUTPUT_RETRY_FP) cannot satisfy CC's strict shape enforcement, but it CAN
    still return usable findings as fenced / preamble-prose JSON that the wrapper's
    defensive parse (_extract_json_object + _validate_findings_shape) handles (the
    live-substrate path). So: spawn once WITH `--json-schema`; on that specific
    malformation, retry once WITHOUT it and stamp `fell_back_to_unstructured=True` on the
    result (honest disclosure — rule 3; surfaced in the coverage trail by main()).

    Backward-compatible: compliant backends never hit the retry, so they see no change. The
    fallback is gated on `--json-schema in argv` (a non-schema caller is unaffected) and on
    the EXACT fingerprint (a different malformation never retries — never mask a regression).
    Ported from csr's hetero_doc_review.py (ADR #45 — rule 7 copy-pattern)."""
    rc = _run_claude_once(
        argv, timeout_s, dry_run, dry_findings, dry_malform, dry_budget
    )
    if (
        argv is not None
        and "--json-schema" in argv
        and not rc["ok"]
        and rc["fingerprint"] == STRUCTURED_OUTPUT_RETRY_FP
    ):
        rc = _run_claude_once(
            _argv_without_json_schema(argv),
            timeout_s,
            dry_run,
            dry_findings,
            dry_malform,
            dry_budget,
        )
        rc["fell_back_to_unstructured"] = True
    return rc


def _parse_json_return(raw):
    """Parse --output-format json return.

    CC v2.1.201 wraps the structured output as
    `{"type":"result", ..., "result": "<json-string>", "structured_output": <obj>, ...}`
    (verified live). Extract the violation-log-shaped object from `structured_output`
    (preferred — already parsed) or `result` (a JSON string). Fall back to the raw
    object if the subprocess returned the shape without a wrapper.
    """
    try:
        wrapper = json.loads(raw)
    except json.JSONDecodeError:
        return None, 0, False, "hetero-malformed-json"
    obj = None
    if isinstance(wrapper, dict):
        so = wrapper.get("structured_output")
        if isinstance(so, dict):
            obj = so
        elif isinstance(wrapper.get("result"), str):
            # structured_output was null — extract from `result` (the backend may have
            # wrapped the JSON in a markdown fence with preamble prose).
            obj = _extract_json_object(wrapper["result"])
    if obj is None and isinstance(wrapper, dict):
        obj = wrapper  # bare shape, no CC wrapper
    if obj is None:
        return None, 0, False, "hetero-no-structured-output"
    fp = _validate_findings_shape(obj)
    if fp:
        return None, 0, False, fp
    return obj, 0, True, ""


def _parse_stream_json(raw):
    """Parse --output-format stream-json return: walk lines for the final structured
    result + count hook events. Best-effort (the live dogfood exercises this)."""
    hook_count = 0
    last_result_obj = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "hook":
            hook_count += 1
        # Prefer the parsed structured_output on the final result event (CC v2.1.201).
        if evt.get("type") == "result" and isinstance(
            evt.get("structured_output"), dict
        ):
            last_result_obj = evt["structured_output"]
        elif evt.get("type") in ("assistant", "result") and isinstance(
            evt.get("message"), dict
        ):
            # The final assistant message may carry the structured result as text.
            content = evt["message"].get("content")
            txt = _extract_text(content)
            if txt:
                cand = _try_json(txt)
                if cand is not None:
                    last_result_obj = cand
        if (
            last_result_obj is None
            and evt.get("type") == "result"
            and isinstance(evt.get("result"), dict)
        ):
            last_result_obj = evt["result"]
    if last_result_obj is not None:
        fp = _validate_findings_shape(last_result_obj)
        if fp:
            return None, hook_count, False, fp
        return last_result_obj, hook_count, True, ""
    return None, hook_count, False, "hetero-stream-no-result"


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                return part.get("text", "")
    return None


def _try_json(txt):
    try:
        return json.loads(txt)
    except (json.JSONDecodeError, TypeError):
        return None


# Live-substrate caveat (verified in the Phase-1 dogfood): under a complex review
# prompt, the non-Claude backend often returns the JSON inside a markdown code fence
# with preamble prose, and CC's `structured_output` comes back null. The wrapper must
# extract the JSON defensively from `result` (fence-aware, then brace-balanced).
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def _extract_json_object(text):
    """Extract the first JSON object from text. Prefer a ```json fence; else the
    first brace-balanced `{...}` substring. Returns the parsed dict or None."""
    if not text:
        return None
    m = _JSON_FENCE_RE.search(text)
    candidate = m.group(1) if m else text
    obj = _try_json(candidate)
    if isinstance(obj, dict):
        return obj
    start = candidate.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj = _try_json(candidate[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                    break
        start = candidate.find("{", start + 1)
    return None


def _validate_findings_shape(obj):
    """Return a malformation fingerprint if the shape violates violation-log; else ''."""
    if not isinstance(obj, dict):
        return "hetero-not-object"
    if "findings" not in obj or not isinstance(obj["findings"], list):
        return "hetero-missing-findings"
    for f in obj["findings"]:
        if not isinstance(f, dict) or "severity" not in f:
            return "hetero-finding-malformed"
        if f["severity"] not in ("blocker", "warning"):
            return "hetero-bad-severity"
    return ""


def drive_lifecycle(
    project_dir,
    task_id,
    round_verdict,
    findings_count,
    notes,
    embedded,
    hook_count,
    gate_fail_fp="",
):
    """Drive loop_state around the different-family subprocess (ADR #39, ADR #40 (g)).

    Full standalone cycle: init -> bump-iteration -> [gate-fail if malformation] ->
    record-outer -> mark-converged -> run-record. The gate-fail runs AFTER init so the
    fresh state is not wiped (loop_state `init` unconditionally re-defaults state; a
    pre-init gate-fail would be lost — found by the Phase-1 different-family dogfood). --embedded
    skips init/mark-converged/run-record (orchestrator-owned). Returns the run-record
    path (or '' if embedded/no-emission).
    """
    if not embedded:
        rc, out = _run_loop_state(["init", "--task-id", task_id], project_dir)
        if rc != 0:
            print(f"warn: loop_state init failed (continuing): {out}", file=sys.stderr)
    # One inner round per different-family invocation (the subprocess IS the inner work for this leg).
    _run_loop_state(["bump-iteration"], project_dir)
    if gate_fail_fp:
        # Post-init so the fingerprint survives to the run-record (the dogfood blocker).
        _run_loop_state(["gate-fail", gate_fail_fp], project_dir)
    # record-outer: the different-family verdict. outer.iterations += 1 satisfies the ADR #16 DoD guard.
    rc, out = _run_loop_state(
        [
            "record-outer",
            "--verdict",
            round_verdict,
            "--findings",
            str(findings_count),
            "--notes",
            f"{notes} hooks={hook_count}",
        ],
        project_dir,
    )
    if rc != 0:
        print(f"warn: loop_state record-outer failed: {out}", file=sys.stderr)
    run_path = ""
    if not embedded:
        rc, out = _run_loop_state(["mark-converged"], project_dir)
        if rc != 0:
            print(f"warn: loop_state mark-converged refused: {out}", file=sys.stderr)
        else:
            rc2, _ = _run_loop_state(["run-record"], project_dir)
            if rc2 == 0:
                # loop_state run-record writes <state_dir>/runs/<task_id>-<stamp>.json
                # and prints the JSON content. Glob for the freshest file for this task.
                runs_dir = os.path.join(project_dir, ".solidforge", "loop", "runs")
                matches = sorted(glob.glob(os.path.join(runs_dir, f"{task_id}-*.json")))
                run_path = matches[-1] if matches else ""
    return run_path


def main():
    # Load <project>/.env.solidforge + .env BEFORE argparse captures the os.environ.get
    # defaults below (--profile/$HETERO_PROFILE, --timeout/$HETERO_TIMEOUT). Previously
    # this ran AFTER parse_args, so an env var set ONLY in .env (not the shell) was
    # invisible to args -> --profile silently fell back to the hardcoded "deepseek",
    # dropping every other configured provider. Shell still wins (setdefault).
    _load_dotenv()
    ap = argparse.ArgumentParser(
        description="different-family adversarial review wrapper (ADR #40)."
    )
    ap.add_argument("--diff", required=True, help="Path/ref to the diff under review.")
    ap.add_argument(
        "--blueprint",
        required=True,
        help="Authoritative blueprint ref (doc + section).",
    )
    ap.add_argument("--task-id", default="hetero-review", help="loop_state task id.")
    ap.add_argument(
        "--profile",
        default=os.environ.get("HETERO_PROFILE", ""),
        help="Provider NAME (or comma-list for dual-/multi-different-family), resolved against "
        "profiles/<name>.json templates. Default: unset -> fail-fast arming prompt (no silent fallback). "
        "The token is read at runtime from the convention var "
        "<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN (e.g. "
        "QWEN3_ANTHROPIC_AUTH_TOKEN) — the SOLE source (the suffix namespaces "
        "it to this substrate, NOT the provider's native <FILENAME>_API_KEY). "
        "Override via the template's _token_env. The committed profile carries no secret.",
    )
    ap.add_argument(
        "--model", default="opus", help="Tier/model alias resolved via the profile."
    )
    ap.add_argument(
        "--budget-usd",
        type=float,
        default=4.0,
        help="Hard cost breaker per subprocess. Default 4.0 leaves headroom under loop_state's "
        "global cost cap (5.0) — the CLI's total_cost_usd is structurally disconnected from provider spend "
        "(ADR #40 (h)(i)), and a cold multi-tool review can cost >$1. If a review still trips "
        "the cap it DEGRADES (ADR #41), not rewrites.",
    )
    ap.add_argument(
        "--allowed-tools",
        default="Read Grep Glob Bash",
        help="Tools the different-family subprocess may wield (read-only review surface).",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("HETERO_TIMEOUT", "600")),
        help="Subprocess wall-clock cap (seconds). Default 600, or $HETERO_TIMEOUT — "
        "raise it (or drop a tier via --model) for a cold large-diff review on the "
        "pro tier; do NOT remap the profile alias to dodge a timeout (ADR #43).",
    )
    ap.add_argument(
        "--observe-hooks",
        action="store_true",
        help="Switch to stream-json + --include-hook-events for gate observability.",
    )
    ap.add_argument(
        "--round-index",
        type=int,
        default=1,
        help="This leg's round number (label only; the debate loop is orchestrator-driven "
        "per ADR #40 (c)(d) — the orchestrator alternates same-family primary ↔ this "
        "wrapper, and `max_adversarial_rounds` = the count of wrapper invocations, "
        "queryable as loop_state `outer.iterations`).",
    )
    ap.add_argument(
        "--prior-findings",
        default="",
        help="Accumulated debate context (the same-family primary's latest findings) as "
        "JSON, or `@file` to read from a path. Fed to the adversarial prompt so the "
        "different-family leg hunts what the primary MISSED, not what it already found.",
    )
    ap.add_argument(
        "--embedded",
        action="store_true",
        help="Skip init/mark-converged/run-record (orchestrator owns those).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Offline mode: emit a canned return, no claude call (for the P1-7 test).",
    )
    ap.add_argument(
        "--dry-run-malform",
        action="store_true",
        help="Offline malformation: forces the gate-fail path (no claude call). For the "
        "gate-fail-survives-init test (locks the Phase-1 dogfood blocker fix).",
    )
    ap.add_argument(
        "--dry-run-budget",
        action="store_true",
        help="Offline budget-exhaustion: forces the DEGRADE path (no claude call). Returns a "
        "canned error_max_budget_usd envelope so the wiring test exercises degrade end-to-end "
        "(ADR #41).",
    )
    ap.add_argument(
        "--findings-schema",
        default=FINDINGS_SCHEMA,
        help="Schema JSON passed via --json-schema (default: violation-log.schema.json).",
    )
    ap.add_argument(
        "--project-dir",
        default=os.getcwd(),
        help="Project root for loop_state state (SOLIDFORGE_PROJECT_DIR).",
    )
    args = ap.parse_args()
    # The offline knobs (--dry-run-malform / --dry-run-budget) imply --dry-run — without
    # this, --dry-run-budget alone would skip run_claude's canned branch and fall through to
    # subprocess.run(None). Same footgun pre-existed for --dry-run-malform; closed here.
    if args.dry_run_malform or args.dry_run_budget:
        args.dry_run = True

    try:
        schema_json = _strip_schema_marker_for_cc(_read_schema(args.findings_schema))
    except FileNotFoundError:
        print(
            f"error: findings schema not found: {args.findings_schema}", file=sys.stderr
        )
        return 2
    project_dir = os.path.abspath(args.project_dir)

    provider_names = [p.strip() for p in args.profile.split(",") if p.strip()]
    if not provider_names:
        print(
            "error: no heterogeneous provider configured. Arm one: "
            "(1) drop profiles/<name>.json (see the shipped zhipu.json / minimax.json "
            "as worked examples, substrate dsh), (2) set HETERO_PROFILE=<name[,name2]> "
            "(or HETERO_DOC_PROFILE for the csr doc leg) in <project>/.env.solidforge, "
            "<project>/.env, or <preset-root>/.env.solidforge, or pass --profile directly. "
            "Unarmed = fail-fast, never a silent same-source fallback.",
            file=sys.stderr,
        )
        return 2
    # Validate every provider NAME up front (fail-fast on a typo / unknown template,
    # regardless of dry-run — _resolve_profile_path sys.exits with a clear error).
    for name in provider_names:
        _resolve_profile_path(name)
    fam_errors, fam_notes = _family_checks(provider_names)
    if fam_errors:
        for e in fam_errors:
            print("error: " + e, file=sys.stderr)
        return 2

    # Canned return for dry-run (offline test path).
    dry_findings = {
        "gate": "hetero-review",
        "passed": True,
        "coverage": ["dry-run"],
        "findings": [],
    }

    # ONE different-family review per provider per invocation (faithful to ADR #40 (c)(d): the
    # same-family primary ↔ different-family alternation is ORCHESTRATOR-driven — this wrapper is
    # the different-family leg only; the orchestrator alternates + caps via outer.iterations).
    # Multi-provider (dual-/multi-different-family) runs each backend independently + merges; a
    # finding is tagged with its `provider` when >1 backend runs, so reconciliation
    # (ADR #40 (b)) can attribute it.
    prior = _load_prior(args.prior_findings)
    prompt = adversarial_prompt(args.diff, args.blueprint, prior, args.round_index)
    per_provider = []  # per-provider result dicts (keys: name/findings/model_coverage/...)
    for name in provider_names:
        plan = None
        if not args.dry_run and not args.dry_run_malform and not args.dry_run_budget:
            plan = _leg_plan(
                name,
                args.model,
                schema_json,
                prompt,
                args.budget_usd,
                args.allowed_tools,
                args.observe_hooks,
            )
        try:
            if plan is not None and plan["substrate"] == "dsh":
                rc = run_dsh(plan, args.timeout, args.dry_run, dry_findings)
            else:
                rc = run_claude(
                    None if plan is None else plan["argv"],
                    args.timeout,
                    args.dry_run,
                    dry_findings,
                    args.dry_run_malform,
                    dry_budget=args.dry_run_budget,
                )
        finally:
            if plan is not None:
                tmp = plan.get("tmp_path")
                if tmp:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                home = plan.get("home")
                if home:
                    shutil.rmtree(home, ignore_errors=True)
        findings_obj = rc["findings"]
        pf = (findings_obj or {}).get("findings", []) if rc["ok"] else []
        if len(provider_names) > 1:
            for f in pf:
                f.setdefault("provider", name)
        per_provider.append(
            {
                "name": name,
                "findings": pf,
                "model_coverage": (findings_obj or {}).get("coverage", [])
                if rc["ok"]
                else [],
                "ok": rc["ok"],
                "fingerprint": rc["fingerprint"],
                "hook_count": rc["hook_count"],
                "error_subtype": rc["error_subtype"],
                "errors": rc["errors"],
                "fell_back_to_unstructured": rc.get("fell_back_to_unstructured", False),
            }
        )

    # Aggregate across providers (single = classic different-family; multi = dual-/multi-different-family).
    all_findings = [f for p in per_provider for f in p["findings"]]
    # Genuine malformation = ok=False AND no degradable subtype (unparseable, or a
    # non-degradable CC error like invalid-args/auth). These surface a fingerprint + rewrite.
    malform_fps = [
        p["fingerprint"] for p in per_provider if not p["ok"] and not p["error_subtype"]
    ]
    # Degrade = a DEGRADABLE substrate error (ok=False, error_subtype set, fingerprint "").
    # The different-family leg contributed nothing; the same-family primary stands (ADR #40 additive).
    degraded_providers = [
        {"provider": p["name"], "subtype": p["error_subtype"], "errors": p["errors"]}
        for p in per_provider
        if p["error_subtype"]
    ]
    degrade_fps = [f"hetero-degraded-{d['subtype']}" for d in degraded_providers]
    any_malform = bool(malform_fps)
    degraded = bool(degraded_providers)
    blockers = [f for f in all_findings if f.get("severity") == "blocker"]
    hook_count = sum(p["hook_count"] for p in per_provider)
    malformation = ",".join(malform_fps)

    prov_list = ",".join(p["name"] for p in per_provider)
    if any_malform:
        # Genuine malformation / non-degradable CC error. gate-fail recorded inside
        # drive_lifecycle (post-init) so the fingerprint survives to the run-record
        # (ADR #39 truthfulness; never silent).
        verdict = "rewrite"
        notes = f"round={args.round_index} providers={prov_list} malformation={malformation}"
    else:
        # passed iff NO non-degraded provider surfaced a blocker (rule 4: warnings are
        # advisory). Degraded providers contribute 0 findings and never force a rewrite.
        gate_passed = len(blockers) == 0
        verdict = "pass" if gate_passed else "rewrite"
        per_counts = ",".join(f"{p['name']}={len(p['findings'])}" for p in per_provider)
        notes = (
            f"round={args.round_index} providers={per_counts} "
            f"findings={len(all_findings)} blockers={len(blockers)}"
        )

    # Degrade honesty (ADR #41; rule 3): stamp the subtype into the persisted notes AND a
    # gate-fail fingerprint so (a) the run-record shows WHY a leg contributed nothing, and
    # (b) the thrashing breaker can escalate persistent degradation across rounds instead of
    # it masquerading as clean convergence.
    if degraded:
        subtypes = ",".join(sorted({d["subtype"] for d in degraded_providers}))
        notes += f" degraded={subtypes}"

    # Combined gate-fail fingerprint: genuine malformation + degrade (both substrate issues).
    gate_fail_fp = ",".join(fp for fp in (malform_fps + degrade_fps) if fp)

    # coverage: the degrade-honestly trail (degrade + malform notes) + the model's own coverage.
    coverage = list(fam_notes)
    for d in degraded_providers:
        detail = "; ".join(d["errors"]) if d["errors"] else "no detail"
        coverage.append(f"provider {d['provider']} degraded: {d['subtype']} ({detail})")
    for p in per_provider:
        if not p["ok"] and not p["error_subtype"] and p["fingerprint"]:
            coverage.append(f"provider {p['name']} malformation: {p['fingerprint']}")
    for p in per_provider:
        if p.get("fell_back_to_unstructured"):
            # Morph-caveat disclosure (rule 3 — never silent): this provider could NOT
            # satisfy CC's --json-schema structured-output retries, so run_claude retried
            # WITHOUT --json-schema and parsed the return defensively. Findings are still
            # shape-validated (_validate_findings_shape); the fallback is disclosed, not
            # masked. Ported from csr (ADR #45).
            coverage.append(
                f"provider {p['name']} fell_back_to_unstructured "
                "(--json-schema structured-output retries exhausted; defensive parse used)"
            )
    for p in per_provider:
        for c in p["model_coverage"]:
            if c not in coverage:
                coverage.append(c)

    run_path = drive_lifecycle(
        project_dir,
        args.task_id,
        verdict,
        len(all_findings),
        notes,
        args.embedded,
        hook_count,
        gate_fail_fp=gate_fail_fp,
    )

    result = {
        "verdict": verdict,
        "degraded": degraded,
        "degraded_providers": degraded_providers,
        "findings_count": len(all_findings),
        "findings": all_findings,
        "coverage": coverage,
        "malformation": malformation,
        "providers": [p["name"] for p in per_provider],
        "run_record": run_path,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
