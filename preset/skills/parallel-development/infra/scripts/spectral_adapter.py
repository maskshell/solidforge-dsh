#!/usr/bin/env python3
"""spectral_adapter.py — convergence-point adapter: Stoplight Spectral → 越权日志.

A SIBLING convergence-point gate (like arch_contract_api.py / impeccable_detect_adapter.py),
NOT a hand-rolled heuristic. It shells out to the ARMED Spectral CLI (Stoplight
`@stoplight/spectral-cli`, armed globally via `brew install spectral-cli` or
`npm i -g @stoplight/spectral-cli`) and
translates its JSON findings into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`).
See references/external-skills.md.

COMPLEMENTARY to `arch_contract_api.py`, NOT a replacement:
  - `arch_contract_api.py` checks the contract's PRESENCE / generated-client freshness / coarse
    path consistency between frontend call sites and the spec (advisory heuristic, ADR 17).
  - `spectral_adapter.py` checks the spec's OWN ruleset compliance (oas / asyncapi rules + the
    project's `.spectral.yaml`): operation-ids, naming, parameter rules, security, etc.
They cover different axes; do not delete one for the other.

Spectral emits (with `-f json`) either a JSON object keyed by file path -> [finding], or a bare
array of findings. Each finding: `{code, message, severity (0-3), path, range:{start:{line}},
source, rule}` (severity: 0=error, 1=warn, 2=info, 3=hint; range.start.line is 0-based). The
adapter maps `code|rule -> rule`, `message -> detail`, `source -> file`, `range.start.line+1 ->
line`, and COLLAPSES severity to `warning` (see GAP).

This gate is ADVISORY: it never emits `blocker` (rule 4 — a linter is a heuristic), so `passed`
is always True; findings surface for the run-record + outer ring. Never silently green: it
always reports `coverage` (what ran + what was skipped).

GAPS (rule 3):
  - Spectral's error/info/hint levels COLLAPSE to `warning` — the 越权日志 schema's severity enum
    is `blocker|warning` only, and an advisory gate never emits `blocker`. Spectral "error"
    severity is preserved in `detail` text only, not as a blocking level.
  - Spectral lints the SPEC; whether the implementation CODE matches the spec stays
    `arch-contract-api` (path-check) + outer-ring / contract tests.

Usage: spectral_adapter.py [target...]   (default: cwd)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when Spectral is not
       armed or there is no OpenAPI/Swagger artifact.
"""

import json
import os
import subprocess
import sys
import tempfile

GATE = "spectral-openapi"

_SPEC_NAMES = (
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "swagger.yml",
)
_MAX_FINDINGS = 50
_MAX_DEPTH = 4

# Spectral numeric severity -> label (0=error, 1=warn, 2=info, 3=hint).
_SEVERITY_LEVEL = {0: "error", 1: "warn", 2: "info", 3: "hint"}


def _level(sev_num):
    """Spectral numeric severity (0-3) -> label; unknown/None -> 'warn'."""
    if isinstance(sev_num, int):
        return _SEVERITY_LEVEL.get(sev_num, "warn")
    return "warn"


_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "target",
    "build",
    "dist",
    "out",
    ".venv",
    "venv",
    "env",
    ".gradle",
    ".next",
    ".nuxt",
    ".turbo",
    ".nx",
    "__pycache__",
    "Pods",
    "DerivedData",
    ".build",
    "coverage",
    ".idea",
    ".vscode",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}


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


def resolve_spectral(root):
    """The armed Spectral CLI. Local install (node_modules/.bin) first, then global on PATH.
    Returns the argv-list to invoke, or None when not armed (npx fetch-on-demand is NOT armed)."""
    local_bin = os.path.join(root, "node_modules", ".bin", "spectral")
    if os.path.isfile(local_bin):
        return [local_bin]
    if have("spectral"):
        return ["spectral"]
    return None


def resolve_ruleset(root):
    """Spectral 6.x requires an explicit ruleset — the bundled `spectral:oas` is no longer
    auto-applied when no ruleset file is found (Spectral 5.x did auto-apply it). `--ruleset
    spectral:oas` is NOT accepted as a value (Spectral reads it as a file path), so a ruleset
    FILE is required. Prefer the project's own `.spectral.{yaml,yml,json}`; when none exists,
    synthesize a default `extends: ["spectral:oas"]` in a temp file (preserves the pre-6.x
    default-oas intent). Returns `(path, is_temp)`; the caller unlinks a temp path when done."""
    for name in (".spectral.yaml", ".spectral.yml", ".spectral.json"):
        cand = os.path.join(root, name)
        if os.path.isfile(cand):
            return cand, False
    tf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="spectral-default-ruleset-"
    )
    tf.write('extends:\n  - "spectral:oas"\n')
    tf.close()
    return tf.name, True


def find_spec_files(root):
    """Dirs (relative to root; '' == root) directly containing an OpenAPI/Swagger artifact."""
    want = set(_SPEC_NAMES)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            for n in filenames:
                if n in want:
                    found.append(os.path.join("" if rel == "." else rel, n))
    return found


def _suggest(code, sev_num):
    """Best-effort: map a Spectral rule to a concrete fix pointer."""
    c = (code or "").lower()
    if "operationid" in c:
        return "Add a unique operationId to each operation."
    if "tag" in c:
        return "Group the operation under a defined tag."
    if "security" in c or "oauth" in c:
        return "Declare a security scheme / requirement on the operation."
    if "param" in c:
        return "Fix the parameter (name/description/required) per the rule."
    if "version" in c or "info" in c:
        return "Complete the info/version block."
    level = _level(sev_num)
    return f"Review rule '{code or '?'}' in .spectral.yaml (Spectral level: {level})."


def translate(raw, root, spec_path):
    """Spectral finding (dict or list shape) -> 越权日志 finding. severity COLLAPSES to warning."""
    if isinstance(raw, dict):
        items = []
        for arr in raw.values():
            if isinstance(arr, list):
                items.extend(arr)
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    out = []
    for f in items[:_MAX_FINDINGS]:
        if not isinstance(f, dict):
            continue
        code = f.get("code") or (f.get("rule") or {}).get("name") or "spectral-finding"
        sev_num = f.get("severity")
        message = f.get("message", "")
        filep = f.get("source") or spec_path
        try:
            filep = os.path.relpath(filep, root)
        except ValueError:
            pass
        rng = f.get("range") or {}
        start = (rng.get("start") or {}) if isinstance(rng, dict) else {}
        line = start.get("line")
        line = (
            (line + 1) if isinstance(line, int) else 0
        )  # Spectral lines are 0-based -> 1-based
        level = _level(sev_num)
        detail = message
        if level and level not in detail.lower():
            detail = f"[spectral:{level}] {message}"
        out.append(
            {
                "severity": "warning",  # COLLAPSED — schema enum is blocker|warning; advisory never blocker
                "rule": f"spectral:{code}",
                "file": filep,
                "line": line,
                "detail": detail,
                "suggestion": _suggest(code, sev_num),
            }
        )
    return out


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "spectral-openapi (advisory, severity collapsed to warning): wraps the armed Stoplight "
        "Spectral CLI linting the OpenAPI/Swagger spec against spectral:oas + .spectral.yaml; "
        "complementary to arch-contract-api (presence/path) — does NOT lint that code matches spec"
    ]
    spectral = resolve_spectral(root)
    if not spectral:
        coverage.append(
            "spectral-openapi: Spectral not armed (`spectral` not on PATH) — run "
            "`brew install spectral-cli` (or `npm i -g @stoplight/spectral-cli`). Gate skipped (no-op)."
        )
        emit([], coverage)
        return
    specs = find_spec_files(root)
    if not specs:
        coverage.append(
            "spectral-openapi: no OpenAPI/Swagger artifact (openapi.{json,yaml,yml} / "
            "swagger.*) found — spec-gate skipped (not an API-contract project)."
        )
        emit([], coverage)
        return

    ruleset_path, ruleset_temp = resolve_ruleset(root)
    coverage.append(
        "spectral-openapi: ruleset="
        + (
            "project .spectral.{yaml,yml,json}"
            if not ruleset_temp
            else "synthesized spectral:oas default (no project ruleset — Spectral 6.x dropped "
            "auto-application of spectral:oas)"
        )
    )
    findings = []
    ran = 0
    try:
        for spec in specs:
            spec_abs = os.path.join(root, spec)
            proc = subprocess.run(
                [*spectral, "lint", "-f", "json", "--ruleset", ruleset_path, spec_abs],
                capture_output=True,
                text=True,
            )
            # Spectral: 0 = no findings, 1 = findings present (not a hard error), >=2 = fault.
            if proc.returncode not in (0, 1):
                coverage.append(
                    f"spectral-openapi: {spec}: spectral exited {proc.returncode} — "
                    f"{(proc.stderr or '').strip()[:200] or 'no stderr'}; findings skipped for this spec."
                )
                continue
            ran += 1
            try:
                raw = json.loads(proc.stdout or "[]")
            except json.JSONDecodeError as e:
                coverage.append(
                    f"spectral-openapi: {spec}: output unparseable ({e}); findings skipped for this spec."
                )
                continue
            mapped = translate(raw, root, spec)
            findings.extend(mapped)
            n_raw = (
                len(raw)
                if isinstance(raw, list)
                else sum(len(v) for v in raw.values() if isinstance(v, list))
            )
            coverage.append(
                f"spectral-openapi: {spec}: spectral reported {n_raw} finding(s); adapter emitted "
                f"{len(mapped)} (severity collapsed to warning)."
            )
    finally:
        if ruleset_temp:
            try:
                os.unlink(ruleset_path)
            except OSError:
                pass

    findings = findings[:_MAX_FINDINGS]
    coverage.append(
        f"spectral-openapi: armed ({spectral[0]}); linted {ran}/{len(specs)} spec(s); "
        f"emitted {len(findings)} finding(s) (capped at {_MAX_FINDINGS})."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
