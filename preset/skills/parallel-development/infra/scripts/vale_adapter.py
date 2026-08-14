#!/usr/bin/env python3
"""vale_adapter.py — convergence-point adapter: Vale prose linter → 越权日志.

A SIBLING convergence-point gate (like arch_contract_api.py / impeccable_detect_adapter.py /
spectral_adapter.py / semgrep_adapter.py), NOT a hand-rolled heuristic. It shells out to the
ARMED Vale CLI (armed globally via `brew install vale`, or the GitHub release) and translates
its JSON findings into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See
references/external-skills.md.

FILLS THE DOCS-QUALITY AXIS: blueprint-crafting checks upstream docs' STRUCTURE (anchors +
authority-chain); it does NOT lint PROSE quality (terminology, voice, spelling, inclusiveness).
Vale does — deterministic, against a committed `.vale.ini` + `styles/`. Different axis from the
language arch gates (which lint CODE).

This is a DEPTH-1 advisory rule gate (no per-feature frozen anchor — the style config is repo-wide,
like Semgrep's ruleset, unlike Spectral's frozen spec). Mirrors semgrep_adapter.py's shape.

Vale emits (with `--output=JSON`) a JSON object keyed by file path -> [alert]; each alert:
`{Check, Line, Span:[start,end], Message, Match, Severity, Link, Alert}` (Severity:
"suggestion"|"warning"|"error"). The adapter maps `Check -> rule`, `Message -> detail`,
`<file-key> -> file`, `Line -> line`, and COLLAPSES severity to `warning` (see GAP).

ADVISORY: never emits `blocker` (rule 4 — a prose linter is a heuristic / style opinion), so
`passed` is always True; findings surface for the run-record + outer ring. Never silently green:
always reports `coverage` (what ran + what was skipped).

GAPS (rule 3):
  - Vale's suggestion/warning/error levels COLLAPSE to `warning` (越权日志 schema enum is
    `blocker|warning`; advisory never `blocker`). The level is kept in `detail` text.
  - Vale requires a `.vale.ini` config (styles are opinion; no objective default). No config ->
    no-op with a coverage note (NOT a silent green).
  - Technical accuracy, example correctness, link validity → outer ring (Vale is prose-style only).

Usage: vale_adapter.py [target...]   (default: cwd)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when Vale is not armed or
       there is no `.vale.ini`.
"""

import json
import os
import subprocess
import sys

GATE = "vale-prose"

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


def resolve_vale():
    """The armed Vale CLI on PATH, or None when not armed."""
    if have("vale"):
        return ["vale"]
    return None


def has_config(root):
    """Vale requires a config (.vale.ini / _vale.ini); styles are opinion, no objective default."""
    return any(
        os.path.isfile(os.path.join(root, name))
        for name in (".vale.ini", "_vale.ini", ".vale")
    )


def _suggest(check, message):
    """Best-effort: map a Vale alert to a concrete fix pointer."""
    c = (check or "").lower()
    m = (message or "").lower()
    if "repeat" in c or "repetition" in c:
        return "Remove the wordy repetition."
    if "substitution" in c or "terms" in c or "vale.terms" in c:
        return "Adopt the preferred term (see styles)."
    if "gender" in c or "ableis" in c or "alex" in m:
        return "Use inclusive language."
    if "spelling" in c or "typo" in m:
        return "Fix the spelling."
    return "Adjust the prose per the Vale rule (see .vale.ini + styles/)."


def translate(raw, root):
    """Vale file->alerts object -> 越权日志 findings. severity COLLAPSES to warning."""
    out = []
    if not isinstance(raw, dict):
        return out
    for file_key, alerts in raw.items():
        if not isinstance(alerts, list):
            continue
        try:
            filep = os.path.relpath(file_key, root)
        except ValueError:
            filep = file_key
        for a in alerts:
            if len(out) >= _MAX_FINDINGS:
                break
            if not isinstance(a, dict):
                continue
            check = a.get("Check") or "vale-finding"
            message = a.get("Message", "")
            sev = (a.get("Severity") or "").lower()
            line = a.get("Line") or 0
            detail = message
            if sev and sev not in detail.lower():
                detail = f"[vale:{sev}] {message}"
            out.append(
                {
                    "severity": "warning",  # COLLAPSED — schema enum blocker|warning; advisory never blocker
                    "rule": f"vale:{check}",
                    "file": filep,
                    "line": line,
                    "detail": detail,
                    "suggestion": _suggest(check, message),
                }
            )
    return out


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "vale-prose (advisory, severity collapsed to warning): wraps the armed Vale CLI linting "
        "prose (terminology, voice, spelling, inclusiveness) against .vale.ini + styles/; fills "
        "the docs-QUALITY axis (blueprint-crafting checks doc structure, not prose quality)"
    ]
    vale = resolve_vale()
    if not vale:
        coverage.append(
            "vale-prose: Vale not armed (`vale` not on PATH) — run `brew install vale` or grab the "
            "GitHub release. Gate skipped (no-op)."
        )
        emit([], coverage)
        return
    if not has_config(root):
        coverage.append(
            "vale-prose: no .vale.ini config found — Vale styles are opinion (no objective "
            "default). Add a .vale.ini + styles/ to enable. Gate skipped (no-op)."
        )
        emit([], coverage)
        return

    targets = sys.argv[1:] or [root]
    proc = subprocess.run(
        [*vale, "--output=JSON", *targets],
        capture_output=True,
        text=True,
    )
    # Vale: 0 = no error-severity alerts; 1 = >=1 error-severity alert; other = fault.
    # It emits the JSON object on stdout with --output=JSON; parse regardless of exit.
    # NOTE: Vale 3.x renamed the flag from --format to --output (the older --format is rejected).
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        coverage.append(
            f"vale-prose: output unparseable ({e}); exit {proc.returncode} — "
            f"{(proc.stderr or '').strip()[:200] or 'no stderr'}; findings skipped."
        )
        emit([], coverage)
        return

    findings = translate(raw, root)
    n_raw = (
        sum(len(v) for v in raw.values() if isinstance(v, list))
        if isinstance(raw, dict)
        else 0
    )
    coverage.append(
        f"vale-prose: {vale[0]} --output=JSON; targets={targets}; {n_raw} alert(s) -> "
        f"{len(findings)} finding(s) emitted (capped at {_MAX_FINDINGS}); exit {proc.returncode}."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
