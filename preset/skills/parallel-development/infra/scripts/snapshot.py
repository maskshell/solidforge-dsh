#!/usr/bin/env python3
"""snapshot.py — micro-step snapshot + forced hard-rollback for the convergence loop.

Snapshot granularity = the inner convergence point (both gates green, about to enter the outer ring), NOT every edit.
Backed by git where possible, using a custom `refs/pd-snap/` namespace (NOT git tags — `tag.gpgsign=true` in user config would otherwise force signing on lightweight tags); falls back to a directory copy when the project is not a git repo.

Subcommands:
  create  <task_id>            snapshot current working tree; record ref in loop-state
  list    <task_id>            list snapshots for the task
  restore <ref|task_id>        restore working tree to a snapshot (default: latest)
  cleanup <task_id>            delete the task's snapshot refs/copies ("用完即清理")

Snapshots capture tracked working-tree changes (git stash create). restore touches tracked source files only; it never touches .solidforge/ state.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

EXCLUDE_COPY = {
    ".git",
    ".solidforge",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".build",
    "DerivedData",
    "build",
    "dist",
}
REF_PREFIX = "refs/pd-snap"


def project_root():
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def snap_dir():
    return os.path.join(project_root(), ".solidforge", "loop", "snapshots")


def run(argv, timeout=60):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", "git unavailable/timeout"


def is_git(root):
    rc, _, _ = run(["git", "-C", root, "rev-parse", "--is-inside-work-tree"])
    return rc == 0


def loop_state_set_snapshot(ref):
    # Best-effort: record into loop-state if the state script exists.
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "loop_state.py"),
        os.path.join(project_root(), ".solidforge", "loop", "scripts", "loop_state.py"),
    ]
    ls = next((c for c in candidates if os.path.exists(c)), None)
    if ls:
        subprocess.run(
            ["python3", ls, "set-snapshot", ref],
            capture_output=True,
            text=True,
            timeout=10,
        )


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --- git backend -------------------------------------------------------------


def git_create(task_id):
    root = project_root()
    refspec = f"{REF_PREFIX}/{task_id}/{stamp()}"
    # Capture working-tree changes without disturbing anything: stash create.
    rc, out, _ = run(["git", "-C", root, "stash", "create"])
    base = out if (rc == 0 and out) else "HEAD"
    if base == "HEAD":
        # Unborn repo (no commits yet) has no valid HEAD -> fall back to copy.
        rc_head, _, _ = run(["git", "-C", root, "rev-parse", "--verify", "-q", "HEAD"])
        if rc_head != 0:
            return copy_create(task_id)
    rc, _, err = run(["git", "-C", root, "update-ref", refspec, base])
    if rc != 0:
        print(json.dumps({"ok": False, "error": err or f"update-ref {refspec} failed"}))
        sys.exit(1)
    loop_state_set_snapshot(refspec)
    print(json.dumps({"ok": True, "ref": refspec, "backend": "git", "base": base}))


def git_list(task_id):
    root = project_root()
    rc, out, _ = run(
        [
            "git",
            "-C",
            root,
            "for-each-ref",
            "--format=%(refname)",
            f"{REF_PREFIX}/{task_id}",
        ]
    )
    refs = sorted([line for line in out.splitlines() if line.strip()])
    print(json.dumps({"refs": refs}))


def git_restore(target):
    root = project_root()
    rc, _, err = run(["git", "-C", root, "checkout", target, "--", ":/"])
    if rc != 0:
        print(json.dumps({"ok": False, "error": err or f"checkout {target} failed"}))
        sys.exit(1)
    print(json.dumps({"ok": True, "restored": target, "backend": "git"}))


def git_cleanup(task_id):
    root = project_root()
    rc, out, _ = run(
        [
            "git",
            "-C",
            root,
            "for-each-ref",
            "--format=%(refname)",
            f"{REF_PREFIX}/{task_id}",
        ]
    )
    removed = []
    for line in out.splitlines():
        r = line.strip()
        if r and run(["git", "-C", root, "update-ref", "-d", r])[0] == 0:
            removed.append(r)
    print(json.dumps({"ok": True, "removed": removed}))


# --- copy backend (non-git) --------------------------------------------------


def copy_create(task_id):
    root = project_root()
    dest = os.path.join(snap_dir(), task_id, stamp())
    os.makedirs(dest, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDE_COPY and not d.startswith(".")
        ]
        rel = os.path.relpath(dirpath, root)
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            dst = os.path.join(dest, rel) if rel != "." else dest
            os.makedirs(dst, exist_ok=True)
            try:
                shutil.copy2(src, os.path.join(dst, fname))
            except OSError:
                pass
    loop_state_set_snapshot(dest)
    print(json.dumps({"ok": True, "ref": dest, "backend": "copy"}))


def copy_list(task_id):
    base = os.path.join(snap_dir(), task_id)
    refs = sorted(os.listdir(base)) if os.path.isdir(base) else []
    print(json.dumps({"refs": [os.path.join(base, r) for r in refs]}))


def copy_restore(target):
    root = project_root()
    if not os.path.isdir(target):
        print(json.dumps({"ok": False, "error": f"snapshot dir not found: {target}"}))
        sys.exit(1)
    for dirpath, dirnames, filenames in os.walk(target):
        rel = os.path.relpath(dirpath, target)
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            dst = os.path.join(root, rel) if rel != "." else root
            os.makedirs(dst, exist_ok=True)
            try:
                shutil.copy2(src, os.path.join(dst, fname))
            except OSError:
                pass
    print(json.dumps({"ok": True, "restored": target, "backend": "copy"}))


def copy_cleanup(task_id):
    base = os.path.join(snap_dir(), task_id)
    if os.path.isdir(base):
        shutil.rmtree(base, ignore_errors=True)
    print(json.dumps({"ok": True, "removed": [base]}))


def main():
    if len(sys.argv) < 2:
        print(
            "usage: snapshot.py {create|list|restore|cleanup} <task_id|ref>",
            file=sys.stderr,
        )
        sys.exit(2)
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    root = project_root()
    git = is_git(root)

    if cmd == "create":
        (git_create if git else copy_create)(arg)
    elif cmd == "list":
        (git_list if git else copy_list)(arg)
    elif cmd == "restore":
        target = arg
        if git and target and "/" not in target:
            # treat as task_id -> latest snapshot
            rc, out, _ = run(
                [
                    "git",
                    "-C",
                    root,
                    "for-each-ref",
                    "--format=%(refname)",
                    f"{REF_PREFIX}/{target}",
                ]
            )
            refs = sorted([line for line in out.splitlines() if line.strip()])
            target = refs[-1] if refs else target
        elif not git and target and os.path.sep not in target:
            base = os.path.join(snap_dir(), target)
            refs = sorted(os.listdir(base)) if os.path.isdir(base) else []
            target = os.path.join(base, refs[-1]) if refs else target
        if not target:
            print(json.dumps({"ok": False, "error": "no snapshot to restore"}))
            sys.exit(1)
        (git_restore if git else copy_restore)(target)
    elif cmd == "cleanup":
        (git_cleanup if git else copy_cleanup)(arg)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
