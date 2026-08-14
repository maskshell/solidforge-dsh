#!/usr/bin/env python3
"""dogfood.py — runs the skill's own different-family leg on its own SKILL.md (rule 1).

A skill that dogfoods a deterministic inner ring must pass its own inner ring
(workspace rule 1). This gate runs the skill's own different-family substrate ONCE on its own
SKILL.md — a single adversarial leg pass, NOT the full multi-round convergence
loop (the full loop is CSR-I6's live run). The convergence POLICY engine
(converge.py) is exercised offline by convergence_policy_check.py; THIS gate
exercises the LIVE different-family substrate end-to-end when tokens are available.

SKIP PATH (the default in offline / CI build envs): if DEEPSEEK_ANTHROPIC_AUTH_TOKEN
is absent from the SHELL ENV, emit passed:true with a coverage note. The token
check is SHELL-ENV ONLY — this gate does NOT load .env.solidforge (doing so would
trigger a real API call; .env.solidforge loading is the wrapper's job). A recorded
dogfood log substitutes in CI (CSR-I6 does the authoritative live run).

FAIL POLICY (when tokens ARE present and the leg runs): do NOT fail the gate on
findings — a doc having review findings is NORMAL (this is an adversarial review,
not a validation). FAIL ONLY on substrate malformation: the wrapper's
result.malformation is a non-empty string (the wrapper could not produce a usable
return). A DEGRADE (result.degraded=true) is NOT a failure — the same-family primary
stands (proposal §3; ADR #40 additive).

Self-contained (rule 7): pure stdlib. Line-length discipline: all lines <=88 so
the file passes format --check under BOTH per-skill (88) and repo-root (100).

Usage:
    python3 infra/test/dogfood.py
"""

import json
import os
import subprocess
import sys

GATE = "dogfood"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
HETERO = os.path.join(ROOT, "infra", "scripts", "hetero_doc_review.py")
SKILL = os.path.join(ROOT, "SKILL.md")
TOKEN_VAR = "DEEPSEEK_ANTHROPIC_AUTH_TOKEN"


def _finding(rule, detail, suggestion, severity="blocker"):
    return {
        "severity": severity,
        "rule": rule,
        "file": "infra/scripts/hetero_doc_review.py",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _token_present():
    """True iff the DeepSeek token is in the SHELL ENV.

    Deliberately does NOT load .env.solidforge — the gate must decide SKIP vs RUN
    before invoking the wrapper, and the wrapper itself loads .env.solidforge. If
    the gate loaded it too, the skip path could never trigger in a project that
    has the token committed there (forcing a real call in offline build envs)."""
    val = os.environ.get(TOKEN_VAR, "")
    return bool(val)


def _run_live(findings, coverage):
    """Invoke hetero_doc_review.py ONCE on SKILL.md; fail only on malformation.

    A single different-family leg pass (NOT the full multi-round loop; the full loop is
    CSR-I6). Findings on the doc are NORMAL — do not fail the gate on them. Fail
    ONLY on substrate malformation (result.malformation != "")."""
    argv = [
        sys.executable,
        HETERO,
        "--artifact",
        "SKILL.md",
        "--profile",
        "deepseek",
    ]
    try:
        proc = subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        findings.append(
            _finding(
                "substrate-timeout",
                "hetero_doc_review.py timed out (>900s) reviewing SKILL.md",
                "investigate the substrate hang; a single review should finish "
                "in minutes (raise --budget-usd headroom if the doc is large)",
            )
        )
        coverage.append("live: TIMEOUT (>900s)")
        return
    combined = proc.stdout + proc.stderr
    # The wrapper exits 1 on malformation, 0 on a usable result (pass OR rewrite
    # OR degrade). Exit 2 = arg/IO error. Parse the JSON verdict either way.
    result = None
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Non-JSON stdout + non-zero exit = the wrapper could not even surface a
        # typed result — treat as substrate malformation.
        if proc.returncode != 0:
            findings.append(
                _finding(
                    "substrate-malformation",
                    f"non-JSON stdout + exit {proc.returncode}: {combined[:240]}",
                    "the wrapper must emit a typed JSON result or a clean "
                    "malformation fingerprint (rule 3 — never silent)",
                )
            )
            coverage.append(f"live: MALFORMATION (exit {proc.returncode}, non-JSON)")
            return
    if result is not None:
        malformation = result.get("malformation", "")
        degraded = bool(result.get("degraded"))
        verdict = result.get("verdict", "?")
        n_findings = result.get("findings_count", len(result.get("findings", [])))
        if malformation:
            malf_detail = f"malformation: {malformation} (exit {proc.returncode})"
            findings.append(
                _finding(
                    "substrate-malformation",
                    malf_detail,
                    "the different-family substrate could not produce a usable return — "
                    "investigate the malformation fingerprint",
                )
            )
            coverage.append(f"live: MALFORMATION ({malformation}); gate fails")
            return
        if degraded:
            coverage.append(
                f"live: DEGRADED (verdict={verdict}, findings={n_findings}) "
                "— not a failure (same-family primary stands; ADR #40)"
            )
            return
        coverage.append(
            f"live: OK (verdict={verdict}, findings={n_findings}) — doc "
            "findings are normal for an adversarial review; gate passes"
        )
        return
    # Exit 2 (arg/IO) without JSON — a substrate problem worth surfacing.
    findings.append(
        _finding(
            "substrate-error",
            f"wrapper exited {proc.returncode} with no JSON: {combined[:240]}",
            "investigate the wrapper argument/IO error",
        )
    )
    coverage.append(f"live: ERROR (exit {proc.returncode}, no JSON)")


def run():
    coverage = [
        "dogfood (rule 1): runs the skill's own different-family leg ONCE on SKILL.md. "
        "SKIP when no DEEPSEEK_ANTHROPIC_AUTH_TOKEN in shell env (the default "
        "offline); FAIL only on substrate malformation, never on doc findings."
    ]
    findings = []
    if not _token_present():
        coverage.append(
            f"skipped: no API tokens ({TOKEN_VAR} absent from shell env; "
            "CSR-I5 gate-1 skip path; a recorded dogfood log substitutes in CI "
            "— CSR-I6 does the live run)."
        )
        return findings, coverage
    coverage.append(f"token present ({TOKEN_VAR} in shell env) — running live leg")
    _run_live(findings, coverage)
    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4)."""
    passed = not any(f.get("severity") == "blocker" for f in findings)
    print(
        json.dumps(
            {
                "gate": GATE,
                "passed": passed,
                "coverage": coverage,
                "findings": findings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if passed else 1)


def main():
    findings, coverage = run()
    emit(findings, coverage)


if __name__ == "__main__":
    main()
