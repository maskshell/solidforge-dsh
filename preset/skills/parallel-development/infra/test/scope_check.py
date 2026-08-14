#!/usr/bin/env python3
"""Offline + integration tests for scope_check.py (ADR #15).

Part 1 (offline, always runs): exercises the pure `classify`/`verdict_of` classifiers with canned file sets — no git, no fs.

Part 2 (integration, runs when git is available): builds a throwaway git repo, simulates a Coder's writes, runs scope_check.py as a subprocess, and asserts the verdict JSON + exit code end-to-end (covers the tracked ∪ untracked union and the exit-code / flag semantics the pure classifier cannot).

Run:
    python3 infra/test/scope_check.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "infra", "scripts", "scope_check.py")

_spec = importlib.util.spec_from_file_location("pd_scope", SCRIPT)
scope = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scope)

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  {'ok' if cond else 'FAIL'}: {name}")


# --- Part 1: pure classifier (offline) ---------------------------------------


def t_all_in_scope_is_clean():
    r = scope.classify(["a.py", "b.py"], ["a.py", "b.py"], [], [])
    check("all in scope -> clean", scope.verdict_of(r) == "clean")
    check("counts in_scope=2", r["counts"]["in_scope"] == 2)
    check("no violations", r["violations"] == [])
    check("no sacred", r["sacred"] == [])


def t_out_of_scope_is_flag():
    r = scope.classify(["a.py", "rogue.py"], ["a.py"], [], [])
    check("out-of-scope -> flag", scope.verdict_of(r) == "flag")
    check("rogue.py is a violation", r["violations"] == ["rogue.py"])
    check("a.py in scope", r["in_scope"] == ["a.py"])


def t_allowlisted_not_a_violation():
    r = scope.classify(["a.py", "goldens/x.svg"], ["a.py"], ["**/goldens/**"], [])
    check("allowlisted -> clean", scope.verdict_of(r) == "clean")
    check("goldens listed under allowlisted", r["allowlisted"] == ["goldens/x.svg"])
    check("not counted as violation", r["violations"] == [])


def t_sacred_is_flag_and_highest_severity():
    r = scope.classify(
        ["a.py", ".solidforge/loop/scripts/loop_state.py"],
        ["a.py"],
        [],
        scope.DEFAULT_SACRED,
    )
    check("sacred -> flag", scope.verdict_of(r) == "flag")
    check(
        "sacred file in sacred list",
        r["sacred"] == [".solidforge/loop/scripts/loop_state.py"],
    )
    check("sacred NOT also in violations", r["violations"] == [])


def t_empty_actual_is_clean():
    r = scope.classify([], ["a.py"], [], [])
    check("empty actual -> clean", scope.verdict_of(r) == "clean")
    check(
        "all counts zero",
        r["counts"] == {"in_scope": 0, "allowlisted": 0, "violations": 0, "sacred": 0},
    )


def t_mix_categorizes_correctly():
    actual = ["a.py", "b.py", "rogue.py", "goldens/g.svg", ".solidforge/loop/x.py"]
    r = scope.classify(
        actual, ["a.py", "b.py"], ["**/goldens/**"], scope.DEFAULT_SACRED
    )
    check("mix -> flag (violations+sacred)", scope.verdict_of(r) == "flag")
    check("in_scope = a.py,b.py", r["in_scope"] == ["a.py", "b.py"])
    check("allowlisted = goldens/g.svg", r["allowlisted"] == ["goldens/g.svg"])
    check("violations = rogue.py", r["violations"] == ["rogue.py"])
    check(
        "sacred = .solidforge/loop/x.py",
        r["sacred"] == [".solidforge/loop/x.py"],
    )


def t_declared_takes_precedence_over_sacred():
    # a path that is BOTH declared and matches a sacred glob -> in_scope (declared wins)
    r = scope.classify(
        [".solidforge/loop/x.py"],
        [".solidforge/loop/x.py"],
        [],
        scope.DEFAULT_SACRED,
    )
    check("declared beats sacred -> clean", scope.verdict_of(r) == "clean")
    check("categorized in_scope", r["in_scope"] == [".solidforge/loop/x.py"])
    check("not in sacred", r["sacred"] == [])


def t_parse_csv_and_match_any():
    check(
        "parse_csv splits+trims+drops empty",
        scope.parse_csv(" a.py , b.py , ") == ["a.py", "b.py"],
    )
    check("parse_csv None -> []", scope.parse_csv(None) == [])
    check("match_any hits", scope.match_any("goldens/a", ["**/goldens/**", "*.py"]))
    check("match_any misses", not scope.match_any("src/main.py", ["**/goldens/**"]))


def t_default_sacred_targets_skill_infra():
    check("DEFAULT_SACRED non-empty", len(scope.DEFAULT_SACRED) > 0)
    check("DEFAULT_ALLOW strict empty", scope.DEFAULT_ALLOW == [])
    check(
        "skill scripts dir is sacred",
        scope.match_any(
            ".solidforge/loop/scripts/scope_check.py", scope.DEFAULT_SACRED
        ),
    )


# --- Part 2: end-to-end via a throwaway git repo -----------------------------


def _git(repo, *argv, **kw):
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", "-C", repo, *argv], capture_output=True, text=True, env=env, **kw
    )


def _run_scope_check(repo, task_base, files_touched_csv, extra=None):
    cmd = [
        sys.executable,
        SCRIPT,
        "--task-base",
        task_base,
        "--files-touched",
        files_touched_csv,
    ]
    if extra:
        cmd += extra
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=repo)
    try:
        obj = json.loads(proc.stdout)
    except json.JSONDecodeError:
        obj = None
    return proc.returncode, obj


def t_integration_clean():
    if not shutil.which("git"):
        print("  skip: git unavailable")
        return
    repo = tempfile.mkdtemp(prefix="scope_")
    try:
        _git(repo, "init", "-q")
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 1\n")
        _git(repo, "add", "declared.py")
        _git(repo, "commit", "-q", "-m", "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()
        # Coder modifies ONLY the declared file
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 2\n")
        rc, obj = _run_scope_check(repo, base, "declared.py")
        check("integration clean: exit 0", rc == 0)
        check("integration clean: verdict clean", obj and obj.get("verdict") == "clean")
        check(
            "integration clean: declared.py in_scope",
            obj and "declared.py" in obj.get("in_scope", []),
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def t_integration_flag_rogue_and_sacred():
    if not shutil.which("git"):
        print("  skip: git unavailable")
        return
    repo = tempfile.mkdtemp(prefix="scope_")
    try:
        _git(repo, "init", "-q")
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 1\n")
        _git(repo, "add", "declared.py")
        _git(repo, "commit", "-q", "-m", "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()
        # Coder: edits declared, creates an UNDECLARED new file (untracked), and rewrites skill infra (sacred).
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 2\n")
        with open(os.path.join(repo, "rogue_new.py"), "w") as fh:
            fh.write("# not mine\n")
        os.makedirs(os.path.join(repo, ".solidforge", "loop", "scripts"), exist_ok=True)
        with open(
            os.path.join(repo, ".solidforge", "loop", "scripts", "loop_state.py"),
            "w",
        ) as fh:
            fh.write("# tampered\n")
        rc, obj = _run_scope_check(repo, base, "declared.py")
        check("integration flag: exit non-zero", rc != 0)
        check("integration flag: verdict flag", obj and obj.get("verdict") == "flag")
        check(
            "integration flag: declared.py in_scope",
            obj and "declared.py" in obj.get("in_scope", []),
        )
        check(
            "integration flag: rogue_new.py is a violation",
            obj and "rogue_new.py" in obj.get("violations", []),
        )
        check(
            "integration flag: skill infra in sacred",
            obj and any("loop_state.py" in s for s in obj.get("sacred", [])),
        )
        check(
            "integration flag: coverage mentions belonging axis",
            obj and any("belonging axis" in c for c in obj.get("coverage", [])),
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def t_integration_allow_suppresses_incidental():
    if not shutil.which("git"):
        print("  skip: git unavailable")
        return
    repo = tempfile.mkdtemp(prefix="scope_")
    try:
        _git(repo, "init", "-q")
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 1\n")
        _git(repo, "add", "declared.py")
        _git(repo, "commit", "-q", "-m", "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()
        with open(os.path.join(repo, "declared.py"), "w") as fh:
            fh.write("x = 2\n")
        os.makedirs(os.path.join(repo, "goldens"), exist_ok=True)
        with open(os.path.join(repo, "goldens", "a.svg"), "w") as fh:
            fh.write("<svg/>\n")
        # without --allow: goldens/a.svg is a violation
        rc1, obj1 = _run_scope_check(repo, base, "declared.py")
        check(
            "integration: goldens flagged without --allow",
            obj1 and "goldens/a.svg" in obj1.get("violations", []),
        )
        # with --allow: tolerated (clean, since declared edit + allowlisted golden only)
        rc2, obj2 = _run_scope_check(
            repo, base, "declared.py", extra=["--allow", "**/goldens/**"]
        )
        check("integration: --allow -> exit 0", rc2 == 0)
        check("integration: --allow -> clean", obj2 and obj2.get("verdict") == "clean")
        check(
            "integration: --allow -> golden in allowlisted",
            obj2 and "goldens/a.svg" in obj2.get("allowlisted", []),
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def main():
    offline = [
        t_all_in_scope_is_clean,
        t_out_of_scope_is_flag,
        t_allowlisted_not_a_violation,
        t_sacred_is_flag_and_highest_severity,
        t_empty_actual_is_clean,
        t_mix_categorizes_correctly,
        t_declared_takes_precedence_over_sacred,
        t_parse_csv_and_match_any,
        t_default_sacred_targets_skill_infra,
    ]
    integration = [
        t_integration_clean,
        t_integration_flag_rogue_and_sacred,
        t_integration_allow_suppresses_incidental,
    ]
    for fn in offline + integration:
        print(f"\n{fn.__name__}:")
        fn()
    failed = [n for n, ok in RESULTS if not ok]
    print(
        f"\n{'PASS' if not failed else 'FAIL'} ({len(RESULTS) - len(failed)}/{len(RESULTS)})"
    )
    if failed:
        for n in failed:
            print(f"  FAILED: {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
