#!/usr/bin/env python3
"""impeccable_detect_adapter.py — convergence-point adapter: Impeccable detector → 越权日志.

A SIBLING convergence-point gate (like arch_contract_api.py), NOT a hand-rolled heuristic gate. It shells out to the ARMED Impeccable skill's detector (`.solidforge/skills/impeccable/scripts/detect.mjs`, installed per-project via `npx impeccable install`) and translates its bare JSON findings array into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See references/external-skills.md.

detect --json emits a bare array of:
    {antipattern, name, description, severity, file, line, snippet}
(severity IS present, e.g. "warning"; line may be null for file-level findings; empty -> []; exit 2 = findings present, 0 = none). The adapter INHERITS severity (does not overwrite), maps antipattern -> rule, folds name into detail, line -> line ?? 0, and optionally synthesizes a suggestion.

This gate is ADVISORY: it never emits a `blocker` (the detector's findings are heuristics — rule 4), so `passed` is always True; findings are surfaced for the run-record + reviewer visual line. Never silently green: it always reports `coverage` (what ran + what was skipped).

Usage: impeccable_detect_adapter.py [target...]   (default: cwd)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when Impeccable is not armed (no detect.mjs) or there is no frontend marker.
"""

import json
import os
import subprocess
import sys

GATE = "impeccable-detect"

_FRONTEND_MARKERS = ("package.json",)
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


def find_marker_dirs(root, names, max_depth=4):
    ignore = {
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
    want = set(names)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            found.append("" if rel == "." else rel)
    return found


def detect_mjs_path(root):
    """The armed Impeccable skill's detector (project-scoped install)."""
    for cand in (
        os.path.join(root, ".solidforge", "skills", "impeccable", "scripts", "detect.mjs"),
        # user-level fallback
        os.path.expanduser("~/.solidforge/skills/impeccable/scripts/detect.mjs"),
    ):
        if os.path.isfile(cand):
            return cand
    return None


def translate(raw_findings, root):
    """detect bare-array finding -> 越权日志 finding. INHERIT severity; do not overwrite."""
    out = []
    for f in raw_findings[:_MAX_FINDINGS]:
        rule = f.get("antipattern") or f.get("name") or "impeccable-finding"
        detail = f.get("description", "")
        name = f.get("name")
        if name and name.lower() not in detail.lower():
            detail = f"{name}: {detail}"
        filep = f.get("file") or "(unknown)"
        try:
            filep = os.path.relpath(filep, root)
        except ValueError:
            pass
        out.append(
            {
                "severity": f.get("severity")
                or "warning",  # INHERIT (source carries it)
                "rule": rule,
                "file": filep,
                "line": f.get("line") or 0,  # null -> 0 for file-level findings
                "detail": detail,
                "snippet": f.get("snippet", ""),
                "suggestion": _suggest(rule, name),
            }
        )
    return out


def _suggest(rule, name):
    """Best-effort: map a detected anti-pattern to the Impeccable command that fixes it."""
    s = f"{rule or ''} {name or ''}".lower()
    if any(k in s for k in ("font", "type", "tracking", "line-length")):
        return "Run /impeccable typeset to fix typography."
    if any(k in s for k in ("color", "gradient", "contrast", "palette", "gray")):
        return "Run /impeccable colorize (or quieter for loud palettes)."
    if any(k in s for k in ("motion", "animate", "ease", "bounce")):
        return "Run /impeccable animate (or quieter to tame motion)."
    if any(k in s for k in ("spacing", "layout", "card", "grid", "rhythm")):
        return "Run /impeccable layout."
    return "Run /impeccable critique for the full review, then the matching refine command."


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "impeccable-detect (advisory, inherits severity): wraps the armed Impeccable 44-rule "
        "detector; visual fidelity / pixel-match / runtime a11y beyond the rules stay outer-ring "
        "(reviewer visual line + /impeccable critique/audit)"
    ]
    detect = detect_mjs_path(root)
    if not detect:
        coverage.append(
            "impeccable-detect: Impeccable not armed (no .solidforge/skills/impeccable/scripts/detect.mjs) "
            "— run `npx impeccable install`. Gate skipped (no-op)."
        )
        emit([], coverage)
        return
    fe_dirs = find_marker_dirs(root, list(_FRONTEND_MARKERS))
    if not fe_dirs:
        coverage.append(
            "impeccable-detect: no frontend marker (package.json) found — design gate skipped "
            "(not a frontend project)."
        )
        emit([], coverage)
        return
    targets = sys.argv[1:] or [root]
    coverage.append(
        f"impeccable-detect: {len(fe_dirs)} frontend dir(s); detector at "
        f"{os.path.relpath(detect, root)}; targets={targets}"
    )
    proc = subprocess.run(
        # NOTE: do NOT pass --no-config — it skips DESIGN.md loading, which is the whole point of a design-FIDELITY gate (detect cross-checks the implementation against the frozen DESIGN.md / design.json as context). Respect the project's .impeccable/config.json ignores too.
        ["node", detect, "--json", *targets],
        capture_output=True,
        text=True,
    )
    # exit 2 = findings present (not a hard error); exit 0 = none; anything else = detector fault.
    if proc.returncode not in (0, 2):
        coverage.append(
            f"impeccable-detect: detector exited {proc.returncode} — "
            f"{proc.stderr.strip()[:200] or 'no stderr'}; findings skipped."
        )
        emit([], coverage)
        return
    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as e:
        coverage.append(
            f"impeccable-detect: detector output unparseable ({e}); findings skipped."
        )
        emit([], coverage)
        return
    findings = translate(raw, root)
    coverage.append(
        f"impeccable-detect: detector reported {len(raw)} finding(s); "
        f"adapter emitted {len(findings)} (capped at {_MAX_FINDINGS})."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
