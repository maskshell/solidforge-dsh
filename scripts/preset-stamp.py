#!/usr/bin/env python3
"""preset-stamp.py — the deterministic preset version stamp (stdlib only).

install.sh writes the stamp after syncing the preset:
.preset-stamp.json = {source_commit, installed_at, hash}
where hash = sha256 over the sorted relative paths + contents of the preset
tree (excluding __pycache__ / .git / .pyc / .DS_Store / the stamp itself).

install-global.sh runs `check` and WARNS when the installed preset's hash
differs from the repo's preset/ (stale deployment: the fix is in the repo,
the deployed preset is not) or the stamp is missing (pre-stamp install).

Usage:
  python3 preset-stamp.py write <installed-preset-dir> [repo-root]
  python3 preset-stamp.py check <installed-preset-dir> [repo-root]
    -> exit 0 + "OK" (stamp present and current)
    -> exit 3 + "STALE: ..." (stamp missing/older than repo)
    -> exit 0 + "NO-STAMP-CONTEXT: ..." (no repo root / repo not a git tree)
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

STAMP_NAME = ".preset-stamp.json"
EXCLUDED_DIRS = {"__pycache__", ".git", ".ruff_cache"}
EXCLUDED_FILES = {".DS_Store", STAMP_NAME}


def hash_dir(root):
    h = hashlib.sha256()
    entries = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDED_DIRS]
        for f in fn:
            if f in EXCLUDED_FILES or f.endswith(".pyc"):
                continue
            entries.append(os.path.relpath(os.path.join(dp, f), root))
    for rel in sorted(entries):
        h.update(rel.encode())
        with open(os.path.join(root, rel), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def repo_commit(repo_root):
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def write_stamp(dest, repo_root):
    stamp = {
        "source_commit": repo_commit(repo_root),
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hash": hash_dir(dest),
    }
    with open(os.path.join(dest, STAMP_NAME), "w", encoding="utf-8") as fh:
        json.dump(stamp, fh, indent=2)
    print(f"  wrote {STAMP_NAME} ({stamp['source_commit'][:8] or 'repo-less'})")
    return 0


def check_stamp(dest, repo_root):
    stamp_path = os.path.join(dest, STAMP_NAME)
    if not os.path.isfile(stamp_path):
        print(f"STALE: {STAMP_NAME} missing — re-run: bash scripts/install.sh")
        return 3
    try:
        with open(stamp_path, encoding="utf-8") as fh:
            stamp = json.load(fh)
    except (OSError, json.JSONDecodeError):
        print(f"STALE: {STAMP_NAME} unreadable — re-run: bash scripts/install.sh")
        return 3
    repo_preset = os.path.join(repo_root, "preset")
    repo_plugins = os.path.join(repo_root, "plugins")
    if not os.path.isdir(repo_preset):
        print(f"NO-STAMP-CONTEXT: repo preset dir absent ({repo_preset})")
        return 0
    installed_hash = stamp.get("hash", "")
    current_hash = hash_dir(dest)
    if installed_hash != current_hash:
        print(
            "STALE: installed preset drifted since install "
            f"(installed {installed_hash[:10]}… vs now {current_hash[:10]}…) — "
            "re-run: bash scripts/install.sh"
        )
        return 3
    # expected = what the CURRENT repo would install: preset/ + plugins
    # baked with the SAME destination path (the install output is not a pure
    # copy of preset/ — plugins/ is baked separately under DEST/plugins).
    with tempfile.TemporaryDirectory(prefix="preset-stamp-") as td:
        shutil.copytree(repo_preset, td, dirs_exist_ok=True)
        plugin_dir = os.path.join(td, "plugins")
        os.makedirs(plugin_dir, exist_ok=True)
        if os.path.isdir(repo_plugins):
            for name in sorted(os.listdir(repo_plugins)):
                if not name.endswith(".host.js"):
                    continue
                src = os.path.join(repo_plugins, name)
                with open(src, encoding="utf-8") as fh:
                    baked = fh.read().replace("__SOLIDFORGE_PRESET_ROOT__", dest)
                with open(os.path.join(plugin_dir, name), "w", encoding="utf-8") as fh:
                    fh.write(baked)
        expected_hash = hash_dir(td)
    if expected_hash != current_hash:
        print(
            "STALE: installed preset is OLDER than what the repo would install "
            f"(repo {expected_hash[:10]}… vs installed {current_hash[:10]}…) — "
            "re-run: bash scripts/install.sh"
        )
        return 3
    print(
        f"OK: preset in sync (commit {stamp.get('source_commit', '')[:8] or '—'}, "
        f"installed {stamp.get('installed_at', '')})"
    )
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    action, dest = sys.argv[1], sys.argv[2]
    repo_root = sys.argv[3] if len(sys.argv) > 3 else os.getcwd()
    if action == "write":
        return write_stamp(dest, repo_root)
    if action == "check":
        return check_stamp(dest, repo_root)
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
