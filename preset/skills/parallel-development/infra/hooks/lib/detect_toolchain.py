#!/usr/bin/env python3
"""Shared toolchain classification for parallel-development hooks.

Pure stdlib. Imported by fast_gate.py and counters.py to classify a single
edited file by extension into a platform bucket (python / swift / web /
rust / java / go), and to locate the project root / state directory regardless of CWD.

Run from inside the hooks dir; callers add this file's parent to sys.path.
"""

import json
import os
import sys

PY_EXTS = {".py"}
SWIFT_EXTS = {".swift"}
WEB_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
RUST_EXTS = {".rs"}
JAVA_EXTS = {".java"}
GO_EXTS = {".go"}


def classify(file_path):
    """Return 'python' | 'swift' | 'web' | 'rust' | 'java' | 'go' | None for a file path by extension."""
    if not file_path:
        return None
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in PY_EXTS:
        return "python"
    if ext in SWIFT_EXTS:
        return "swift"
    if ext in RUST_EXTS:
        return "rust"
    if ext in JAVA_EXTS:
        return "java"
    if ext in GO_EXTS:
        return "go"
    if ext in WEB_EXTS:
        return "web"
    return None


def project_root():
    """Project root: SOLIDFORGE_PROJECT_DIR env (set in hook context) else CWD."""
    return os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()


def state_dir():
    return os.path.join(project_root(), ".solidforge", "loop")


def state_file():
    return os.path.join(state_dir(), "loop-state.json")


def relpath(file_path):
    """Project-relative path for fingerprint stability across runs."""
    try:
        return os.path.relpath(file_path, project_root())
    except ValueError:
        return file_path


def which_any(*candidates):
    """Return the first candidate command found on PATH, else None."""
    for c in candidates:
        if _shutil_which(c):
            return c
    return None


def resolve_tool(name):
    """Return an argv prefix to run a tool: [<resolved-path>] or None.
    Checks PATH first, then the project's local virtualenv bins (.venv/venv/env).
    Lets gates find tools installed as project dev deps even when the venv is not
    'active' on PATH."""
    p = _shutil_which(name)
    if p:
        return [p]
    root = project_root()
    for venv in (".venv", "venv", "env"):
        cand = os.path.join(root, venv, "bin", name)
        if os.path.exists(cand):
            return [cand]
    return None


def _shutil_which(cmd):
    # Inlined to keep import surface minimal / predictable.
    from shutil import which

    return which(cmd)


# --- shared hook I/O helpers -------------------------------------------------


def read_payload():
    """Read the Claude Code hook JSON payload from stdin. Returns {} on failure."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def emit_block(reason):
    """PostToolUse feedback: structured decision:block, conversation continues.
    The edit already happened; this feeds the failure back so Claude self-corrects
    next turn and the orchestrator treats it as 'inner red, short-circuit'."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def deny_block(reason):
    """PreToolUse: true pre-call deny. The tool call does not execute."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def loop_state_path():
    """Locate loop_state.py: dev location first (sibling scripts/ dir), then the
    installed project location."""
    here = os.path.dirname(os.path.abspath(__file__))  # .../hooks/lib
    dev = os.path.normpath(os.path.join(here, "..", "..", "scripts", "loop_state.py"))
    if os.path.exists(dev):
        return dev
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    return os.path.join(root, ".solidforge", "loop", "scripts", "loop_state.py")
