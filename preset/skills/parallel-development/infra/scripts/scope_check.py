#!/usr/bin/env python3
"""scope_check.py — the task-boundary BELONGING gate (ADR #15).

Post-hoc check at the Coder→orchestrator handoff: a Coder subagent's ACTUAL writes must be ⊆ its declared `files_touched` ∪ an allowlist. Correctness gates (fast/arch) verify "is the code right"; this verifies "do these changes BELONG to this task". A correctness-clean but out-of-scope write — e.g. an interrupted subagent that rewrote the skill's own infra + added deps + touched the lockfile — passes every other gate; this is the only one that catches it. See ADR #15.

Verdict semantics (flag-not-block, post-hoc): scope_check cannot refuse writes that already happened; it FLAGS them for the orchestrator to handle — discard the out-of-scope paths (`git checkout HEAD -- <paths>`), keep a coherent in-scope diff, or `snapshot.py restore <task>`. Never silently merge out-of- scope changes. Exit non-zero on `flag` so the orchestrator must handle it before aggregating / building on the result. Sacred-path hard-DENY is a SEPARATE PreToolUse hook (a blueprint_guard.py generalization, ADR #15c), not this script: scope_check reports sacred-path touches at the highest severity, but being post-hoc it still flags rather than prevents.

Usage:
  scope_check.py --task-base <ref> --files-touched <path,path,...> [--allow <glob,glob,...>] [--sacred <glob,glob,...>]

  --task-base <ref>        git ref/commit the Coder was dispatched from (a snapshot ref `refs/pd-snap/...` or HEAD at dispatch). Required.
  --files-touched <csv>    the task's declared files_touched (the orchestrator knows these from TaskCreate metadata). May be empty.
  --allow <csv>            extra allowlist globs (fnmatch; `*` spans `/`, use `**` as a segment wildcard) for genuinely incidental artifacts to tolerate.
  --sacred <csv>           extra sacred-path globs (never a legitimate target).

The default allowlist is intentionally EMPTY (strict): a well-declared task lists its own regenerables (goldens, `__init__.py` exports, a declared lockfile) in `files_touched`, so they are in-scope. Use `--allow` only for incidental artifacts you consciously choose to tolerate (false-positive suppression); prefer false flags over false negatives.

Default sacred paths: `.solidforge/loop/**` — the installed skill's own infra, which an implementation subagent must never rewrite.

Glossary of the JSON output groups:
  in_scope       changed AND declared (or matching nothing — fine).
  allowlisted    changed, not declared, but matched an allow glob (tolerated; NOT a violation).
  violations     changed, not declared, not allowlisted, not sacred -> FLAG.
  sacred         changed and matched a sacred glob -> FLAG, highest severity.
"""

import fnmatch
import json
import os
import subprocess
import sys

GATE = "scope-check"

# Installed skill infra in the target project — never a legitimate write target for an implementation subagent. (When the skill runs on its own source tree, the same installed path covers it.)
DEFAULT_SACRED = [".solidforge/loop/**"]
# Strict by default — see docstring. A well-declared task lists its own regenerables in files_touched; --allow opts into tolerating incidental ones.
DEFAULT_ALLOW = []


def project_root():
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def run(argv, timeout=60):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", "git unavailable/timeout"


def parse_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _glob_match(pattern, path):
    """gitignore/shell-style globstar match: `**` matches zero or more whole path segments (so `**/goldens/**` matches both `a/b/goldens/c` AND the top-level `goldens/c`); `*` and `?` match within a single segment; other segments match literally (with fnmatch char classes).
    Splits on `/` so a single-segment pattern never crosses a directory boundary."""
    pats = pattern.split("/")
    parts = path.split("/")

    def match(pi, fi):
        while pi < len(pats):
            p = pats[pi]
            if p == "**":
                if pi == len(pats) - 1:  # trailing ** swallows the rest
                    return True
                for k in range(fi, len(parts) + 1):
                    if match(pi + 1, k):
                        return True
                return False
            if fi >= len(parts) or not fnmatch.fnmatch(parts[fi], p):
                return False
            pi += 1
            fi += 1
        return fi == len(parts)

    return match(0, 0)


def match_any(path, globs):
    return any(_glob_match(g, path) for g in globs)


def classify(actual, files_touched, allow_globs, sacred_globs):
    """Pure classifier — unit-testable offline (no git, no fs).

    actual        : iterable of changed file paths (tracked-since-base UNION new untracked).
    files_touched : declared paths (exact match).
    allow_globs   : fnmatch globs for tolerated incidental artifacts.
    sacred_globs  : fnmatch globs for never-legitimate paths.

    Order matters: declared > sacred > allowlisted > violation.
    Returns a dict with in_scope / allowlisted / violations / sacred lists + counts.
    The caller derives the verdict (flag iff violations or sacred non-empty).
    """
    declared = set(files_touched)
    in_scope, allowlisted, violations, sacred = [], [], [], []
    for f in sorted(set(actual)):
        if f in declared:
            in_scope.append(f)
        elif match_any(f, sacred_globs):
            sacred.append(f)
        elif match_any(f, allow_globs):
            allowlisted.append(f)
        else:
            violations.append(f)
    return {
        "in_scope": in_scope,
        "allowlisted": allowlisted,
        "violations": violations,
        "sacred": sacred,
        "counts": {
            "in_scope": len(in_scope),
            "allowlisted": len(allowlisted),
            "violations": len(violations),
            "sacred": len(sacred),
        },
    }


def git_changed_since(base, root):
    """Files changed since <base>: tracked changes (committed or not, between base and the working tree) UNION new untracked (non-ignored) files the agent may have created.
    Returns (list, error_or_None); (None, msg) on git failure so the caller degrades honestly instead of silently passing."""
    rc, out, err = run(["git", "-C", root, "diff", "--name-only", base])
    if rc != 0:
        return None, (err or f"git diff --name-only {base} failed (rc={rc})")
    tracked = [line for line in out.splitlines() if line.strip()]
    rc2, out2, _ = run(
        ["git", "-C", root, "ls-files", "--others", "--exclude-standard"]
    )
    untracked = (
        [line for line in (out2 or "").splitlines() if line.strip()] if rc2 == 0 else []
    )
    return sorted(set(tracked) | set(untracked)), None


def verdict_of(result):
    return "clean" if not (result["violations"] or result["sacred"]) else "flag"


def emit(result):
    verdict = verdict_of(result)
    passed = verdict == "clean"
    suggestion = (
        "all actual writes are within the declared scope"
        if passed
        else "out-of-scope writes detected — discard them "
        "(`git checkout HEAD -- <paths>`), keep a coherent in-scope diff, or "
        "`snapshot.py restore <task>`; never silently merge. Sacred-path "
        "touches are highest severity."
    )
    print(
        json.dumps(
            {
                "gate": GATE,
                "verdict": verdict,
                "passed": passed,
                "task_base": result.get("task_base"),
                "counts": result["counts"],
                "in_scope": result["in_scope"],
                "allowlisted": result["allowlisted"],
                "violations": result["violations"],
                "sacred": result["sacred"],
                "coverage": result["coverage"],
                "suggestion": suggestion,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if passed else 1)


def _empty_result(task_base, coverage):
    return {
        "task_base": task_base,
        "in_scope": [],
        "allowlisted": [],
        "violations": [],
        "sacred": [],
        "counts": {"in_scope": 0, "allowlisted": 0, "violations": 0, "sacred": 0},
        "coverage": coverage,
    }


def main():
    args = sys.argv[1:]

    def get(flag):
        if flag in args:
            i = args.index(flag)
            return args[i + 1] if i + 1 < len(args) else None
        return None

    task_base = get("--task-base")
    files_touched = parse_csv(get("--files-touched"))
    allow = DEFAULT_ALLOW + parse_csv(get("--allow"))
    sacred = list(DEFAULT_SACRED) + parse_csv(get("--sacred"))

    if not task_base:
        # misuse, not degradation -> hard error (exit 2), never an advisory pass
        print("scope_check: --task-base <ref> is required", file=sys.stderr)
        sys.exit(2)

    root = project_root()
    actual, err = git_changed_since(task_base, root)
    if actual is None:
        # honest degradation: cannot compute -> advisory pass with an explicit coverage note (never silently green; mirrors arch-gate ADR #8).
        coverage = [f"scope_check: belonging check skipped ({err})"]
        emit(_empty_result(task_base, coverage))

    coverage = [
        f"scope_check: {len(actual)} changed file(s) vs {len(files_touched)} declared; "
        f"{len(allow)} allowlist glob(s), {len(sacred)} sacred glob(s)",
        "scope_check: belonging axis (ADR #15) — correctness gates do not catch "
        "out-of-scope writes; this is the only gate that does.",
    ]
    result = classify(actual, files_touched, allow, sacred)
    result["task_base"] = task_base
    result["coverage"] = coverage
    emit(result)


if __name__ == "__main__":
    main()
