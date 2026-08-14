#!/usr/bin/env python3
"""semgrep_adapter.py — convergence-point adapter: Semgrep SAST → 越权日志.

A SIBLING convergence-point gate (like arch_contract_api.py / impeccable_detect_adapter.py /
spectral_adapter.py), NOT a hand-rolled heuristic. It shells out to the ARMED Semgrep CLI
(armed globally via `brew install semgrep` or `pip install semgrep`) and translates its
JSON findings into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See
references/external-skills.md.

COMPLEMENTARY to the existing security coverage, NOT a replacement:
  - `/security-review` (skill) is an LLM review — semantic, slow, token-costly.
  - `arch_contract_deps.py` covers leaked SECRETS (gitleaks) + dependency CVEs.
  - `semgrep_adapter.py` adds deterministic SAST over SOURCE (CVE-pattern code: OWASP top-ten,
    injection, path-traversal, hardcoded creds patterns, etc.) via a ruleset. Different axis.

This is a DEPTH-1 advisory rule gate (no per-feature frozen anchor — the ruleset is repo-wide
config, unlike Spectral's frozen spec). Mirrors spectral_adapter.py's shape, minus the freeze.

Semgrep emits (with `--json`) `{"results":[{check_id, path, start:{line,col}, end, extra:{message,
severity, metadata, lines}}], "errors":[...]}` (severity: "ERROR"|"WARNING"|"INFO"). The adapter
maps `check_id -> rule`, `extra.message -> detail`, `path -> file`, `start.line -> line`, and
COLLAPSES severity to `warning` (see GAP).

ADVISORY: never emits `blocker` (rule 4 — SAST is heuristic, false-positive-prone), so `passed`
is always True; findings surface for the run-record + outer ring. Never silently green: always
reports `coverage` (what ran + what was skipped).

GAPS (rule 3):
  - Semgrep's ERROR/WARNING/INFO levels COLLAPSE to `warning` (越权日志 schema enum is
    `blocker|warning`; advisory never `blocker`). The level is kept in `detail` text.
  - SAST is false-positive-prone; findings are advisory review input, not auto-Blockers.
  - Secrets-in-history + dependency CVEs stay `arch-contract-deps`; runtime vulns → outer ring.
  - With `--config auto` (no committed ruleset) Semgrep fetches its registry (network, cached) —
    commit a `.semgrep/` ruleset for offline determinism.

Usage: semgrep_adapter.py [target...]   (default: cwd)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when Semgrep is not armed.
"""

import json
import os
import subprocess
import sys

GATE = "semgrep-sast"

_MAX_FINDINGS = 50


def emit(findings, coverage):
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


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def resolve_semgrep():
    """The armed Semgrep CLI on PATH, or None when not armed."""
    if have("semgrep"):
        return ["semgrep"]
    return None


def resolve_ruleset(root):
    """A committed local ruleset (preferred — offline deterministic), else 'auto' (registry)."""
    for cand in (".semgrep.yml", "semgrep.yml", ".semgrep/config.yml"):
        if os.path.isfile(os.path.join(root, cand)):
            return cand
    if os.path.isdir(os.path.join(root, ".semgrep")):
        return ".semgrep"
    return "auto"


def _suggest(check_id):
    """Best-effort: map a Semgrep rule id to a concrete fix pointer."""
    cid = (check_id or "").lower()
    if "injection" in cid or "sqli" in cid or "xss" in cid:
        return "Sanitize/parameterize the input (injection-class finding)."
    if "traversal" in cid or "path-traversal" in cid:
        return "Constrain the path (allowlist / basename) — path-traversal finding."
    if "hardcoded" in cid or "secret" in cid or "credential" in cid:
        return "Move the secret to an env var / secret store."
    if "crypto" in cid or "random" in cid:
        return "Use a strong, modern primitive (weak-crypto finding)."
    if "deserializ" in cid:
        return "Avoid untrusted deserialization."
    return "Review the rule in .semgrep/ (or semgrep.yml); verify it is not a false positive."


def translate(results, root):
    """Semgrep result -> 越权日志 finding. severity COLLAPSES to warning."""
    out = []
    for r in (results or [])[:_MAX_FINDINGS]:
        if not isinstance(r, dict):
            continue
        check_id = r.get("check_id") or "semgrep-finding"
        extra = r.get("extra") or {}
        message = extra.get("message", "")
        sev = (extra.get("severity") or "").upper()
        filep = r.get("path") or "(unknown)"
        try:
            filep = os.path.relpath(filep, root)
        except ValueError:
            pass
        start = r.get("start") or {}
        line = start.get("line") or 0
        detail = message
        if sev and sev not in detail.upper():
            detail = f"[semgrep:{sev.lower()}] {message}"
        out.append(
            {
                "severity": "warning",  # COLLAPSED — schema enum blocker|warning; advisory never blocker
                "rule": f"semgrep:{check_id}",
                "file": filep,
                "line": line,
                "detail": detail,
                "suggestion": _suggest(check_id),
            }
        )
    return out


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "semgrep-sast (advisory, severity collapsed to warning): wraps the armed Semgrep CLI "
        "scanning SOURCE for CVE-pattern code (OWASP top-ten, injection, traversal, weak-crypto, "
        "...); complementary to /security-review (LLM) and arch-contract-deps (secrets/CVEs)"
    ]
    semgrep = resolve_semgrep()
    if not semgrep:
        coverage.append(
            "semgrep-sast: Semgrep not armed (`semgrep` not on PATH) — run `brew install semgrep` "
            "(or `pip install semgrep`). Gate skipped (no-op)."
        )
        emit([], coverage)
        return

    ruleset = resolve_ruleset(root)
    targets = sys.argv[1:] or [root]
    if ruleset == "auto":
        coverage.append(
            "semgrep-sast: no committed ruleset (.semgrep.yml / .semgrep/) — using `--config auto` "
            "(Semgrep registry fetch; network, cached). Commit a ruleset for offline determinism."
        )
    else:
        coverage.append(
            f"semgrep-sast: ruleset = {ruleset} (local, offline-deterministic)."
        )

    proc = subprocess.run(
        [*semgrep, "--json", "--config", ruleset, *targets],
        capture_output=True,
        text=True,
    )
    # Semgrep: 0 = clean run (findings or not, by default); 1 = errors during run; >=2 = fault.
    # It always emits JSON on stdout with --json; parse regardless of exit, then note non-zero.
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        coverage.append(
            f"semgrep-sast: output unparseable ({e}); exit {proc.returncode} — "
            f"{(proc.stderr or '').strip()[:200] or 'no stderr'}; findings skipped."
        )
        emit([], coverage)
        return

    results = raw.get("results") or []
    errors = raw.get("errors") or []
    findings = translate(results, root)
    coverage.append(
        f"semgrep-sast: {semgrep[0]} --config {ruleset}; targets={targets}; "
        f"{len(results)} result(s) -> {len(findings)} finding(s) emitted "
        f"(capped at {_MAX_FINDINGS}); {len(errors)} semgrep error(s); exit {proc.returncode}."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
