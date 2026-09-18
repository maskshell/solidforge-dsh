#!/usr/bin/env python3
"""hetero_doc_review.py — minimal wiring checks (rule-7 parity with pd's
hetero_review_wiring.py, ADR #54 SHARED-ENV ALIGNMENT).

OFFLINE + DETERMINISTIC (rule 4 — no real model call): exercises the wrapper's
--dry-run path and the token-resolution helpers. The live `claude -p` substrate
is exercised by the dogfood runs, NOT here.

Cases:
  1. `_resolve_token_var` — convention derivation + `_token_env` override
     (claude-code substrate) + empty-override fail-fast (ADR #54).
  2. `--dry-run` — the wrapper returns a typed JSON object (the reconciliation
     shape), no real provider call.
  3. missing token -> fail fast (non-zero), naming the `_token_env` var AND the
     override field (`_token_env`, never the stale `_credential_env`) — the
     diagnostic-UX invariant the ADR #54 review surfaced.

Run: python3 infra/test/hetero_doc_review_wiring.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
HETERO = os.path.join(SCRIPTS, "hetero_doc_review.py")

sys.path.insert(0, SCRIPTS)
import hetero_doc_review as h  # noqa: E402  (unit-test the profile helpers directly)


def _run(argv, cwd, env):
    return subprocess.run(
        [sys.executable, HETERO, *argv],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
        env=env,
    )


def check_token_resolution():
    # convention derivation (no override in the template)
    assert h._resolve_token_var("qwen", {}) == "QWEN_ANTHROPIC_AUTH_TOKEN"
    assert (
        h._resolve_token_var("openai-compat", {})
        == "OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN"
    )
    # optional override via _token_env (claude-code substrate)
    assert h._resolve_token_var("x", {"_token_env": "CUSTOM_VAR"}) == "CUSTOM_VAR"
    # empty _token_env -> fail-fast (ADR #54: never a silent convention fallback)
    try:
        h._resolve_token_var("qwen", {"_token_env": ""})
        raise AssertionError("empty _token_env must fail fast, not fall back")
    except SystemExit as e:
        assert "EMPTY `_token_env`" in str(e), str(e)
    # null _token_env -> treated as NOT specified -> convention fallback
    # (the regression the ADR #54 review caught: str(None)=="None" is truthy)
    assert (
        h._resolve_token_var("qwen", {"_token_env": None})
        == "QWEN_ANTHROPIC_AUTH_TOKEN"
    )
    print(
        "  _resolve_token_var (convention + override + empty/null fail/fallback): PASS"
    )


def check_dry_run_shape():
    env = dict(os.environ)
    env.pop("HETERO_DOC_PROFILE", None)  # --profile is explicit; don't let env leak
    r = _run(
        [
            "--artifact",
            "docs/README.md",
            "--authority",
            "t#b",
            "--profile",
            "qwen",
            "--dry-run",
        ],
        tempfile.mkdtemp(),
        env,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    obj = json.loads(r.stdout)
    assert obj["verdict"] == "pass" and obj["findings"] == []
    assert obj["providers"] == ["qwen"]
    print("  --dry-run (typed reconciliation shape, no provider call): PASS")


def check_missing_token_fail_fast():
    r = _run(
        [
            "--artifact",
            "docs/README.md",
            "--authority",
            "t#b",
            "--profile",
            "qwen",
        ],
        tempfile.mkdtemp(),
        {**os.environ, "QWEN_TOKEN_PLAN_CN_ANTHROPIC_AUTH_TOKEN": ""},
    )
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "QWEN_TOKEN_PLAN_CN_ANTHROPIC_AUTH_TOKEN" in out, (
        r.returncode,
        out,
    )
    # the fail-fast message must name the ACTUAL override field (_token_env on the
    # claude-code substrate) — never the stale _credential_env (ADR #54 review)
    assert "_token_env" in out and "_credential_env" not in out, out
    print("  missing-token fail-fast (names _token_env var + field): PASS")


def check_cross_substrate_warning():
    """A dsh-substrate profile carrying a stray `_token_env` must surface the
    cross-substrate honesty warning on stderr (ADR #54: never silently dropped)."""
    import shutil
    import io
    import contextlib

    d = tempfile.mkdtemp(prefix="xsub_")
    prof = os.path.join(d, "xsub.json")
    with open(prof, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "_comment": "temp",
                "substrate": "dsh",
                "model": "m",
                "_family": "glm",
                "_credential_env": "XSUB_CRED",
                "_token_env": "XSUB_STRAY",
            },
            fh,
        )
    # _leg_plan needs the credential var present (else fail-fast, which we don't
    # want here) — set it, then capture the warning on stderr
    os.environ["XSUB_CRED"] = "sk-x"
    err = io.StringIO()
    old_profiles_dir = h.PROFILES_DIR
    h.PROFILES_DIR = d
    try:
        with contextlib.redirect_stderr(err):
            plan = h._leg_plan(
                "xsub",
                "opus",
                json.dumps({"type": "object"}),
                "prompt",
                4.0,
                "",
                "",
            )
        assert "ignores" in err.getvalue() and "_token_env" in err.getvalue(), (
            err.getvalue(),
        )
        assert plan is not None and plan["substrate"] == "dsh"
        shutil.rmtree(plan["home"], ignore_errors=True)
    finally:
        h.PROFILES_DIR = old_profiles_dir
        os.environ.pop("XSUB_CRED", None)
        shutil.rmtree(d, ignore_errors=True)
    print("  cross-substrate `_token_env` on dsh profile -> stderr warning: PASS")


def main():
    print("hetero_doc_review.py wiring (rule-7 parity, ADR #54):")
    check_token_resolution()
    check_dry_run_shape()
    check_missing_token_fail_fast()
    check_cross_substrate_warning()
    print("csr hetero wiring: PASS")


if __name__ == "__main__":
    main()
