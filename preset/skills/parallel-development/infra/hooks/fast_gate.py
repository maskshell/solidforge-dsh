#!/usr/bin/env python3
"""fast_gate.py — PostToolUse hook: the cheap "快速门".

Runs after every Edit/Write. Performs only single-file, ms~sec checks (lint / format). The heavier type-check / full-suite / architecture-contract checks belong to the arch-contract gate at the inner convergence point, NOT here.

On failure: records the error fingerprint via loop_state.py (Thrashing feed), queries the breaker state, and emits a structured `decision:block` so Claude self-corrects on the next turn and the orchestrator treats the result as "inner red — short-circuit, do not enter the outer ring."

Tool missing or not configured → silent pass (exit 0). Never hard-errors.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import detect_toolchain as dt  # noqa: E402

TIMEOUT = 20


def run_quiet(argv, timeout=TIMEOUT):
    """Run a command, capturing output. Returns (rc, combined_output_str)."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None, ""  # tool not installed
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def first_meaningful_line(output):
    for line in output.splitlines():
        s = line.strip()
        if s:
            return s
    return "unknown error"


def check_python(file_path):
    tool = dt.resolve_tool("ruff")
    if not tool:
        return True, None
    rc, out = run_quiet(
        tool + ["check", "--no-cache", "--output-format=concise", file_path]
    )
    if rc not in (0, None):
        return False, ("ruff check", out)
    rc, out = run_quiet(tool + ["format", "--check", file_path])
    if rc not in (0, None):
        return False, ("ruff format", out)
    return True, None


def check_swift(file_path):
    tool = dt.which_any("swift-format")
    if not tool:
        return True, None
    rc, out = run_quiet([tool, "lint", file_path])
    if rc not in (0, None):
        return False, ("swift-format", out)
    return True, None


def check_rust(file_path):
    # Cheap per-file check: rustfmt --check. cargo check / clippy are whole-crate and belong to the architecture-contract gate at the convergence point.
    tool = dt.resolve_tool("rustfmt")
    if not tool:
        return True, None
    rc, out = run_quiet(tool + ["--edition", "2021", "--check", file_path])
    if rc not in (0, None):
        return False, ("rustfmt", out)
    return True, None


def check_java(file_path):
    # Cheap per-file check: google-java-format --dry-run. Checkstyle / jdeps are whole-project and belong to the architecture-contract gate at convergence.
    tool = dt.resolve_tool("google-java-format")
    if not tool:
        jar = os.environ.get("GOOGLE_JAVA_FORMAT_JAR")
        if jar and os.path.exists(jar):
            tool = ["java", "-jar", jar]
    if not tool:
        return True, None
    rc, out = run_quiet(tool + ["--dry-run", "--set-exit-if-changed", file_path])
    if rc not in (0, None):
        return False, ("google-java-format", out)
    return True, None


def check_go(file_path):
    # Cheap per-file check: `gofmt -l <file>` lists files needing formatting. Unlike
    # `rustfmt --check` / `google-java-format --dry-run`, `gofmt -l` ALWAYS exits 0 — the
    # failure signal is NON-EMPTY stdout (the file's name is printed when it needs
    # formatting). `go vet` / `golangci-lint` are whole-module and belong to the
    # architecture-contract gate at convergence.
    tool = dt.resolve_tool("gofmt")
    if not tool:
        return True, None
    rc, out = run_quiet(tool + ["-l", file_path])
    # gofmt -l exits 0 even when files need formatting — gate on non-empty stdout.
    if rc not in (0, None) or (out or "").strip():
        return False, ("gofmt", out)
    return True, None


def check_web(file_path):
    # Only run if an eslint config is present in the project and eslint is reachable.
    root = dt.project_root()
    has_cfg = any(
        os.path.exists(os.path.join(root, name))
        for name in (
            "eslint.config.js",
            "eslint.config.mjs",
            "eslint.config.cjs",
            ".eslintrc.js",
            ".eslintrc.json",
            ".eslintrc",
        )
    )
    if not has_cfg:
        return True, None
    local = os.path.join(root, "node_modules", ".bin", "eslint")
    tool = local if os.path.exists(local) else dt.which_any("eslint")
    if not tool:
        return True, None
    rc, out = run_quiet([tool, "--no-error-on-unmatched-pattern", file_path])
    if rc not in (0, None):
        return False, ("eslint", out)
    return True, None


def main():
    payload = dt.read_payload()
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        sys.exit(0)

    platform = dt.classify(file_path)
    if platform is None:
        sys.exit(0)  # not a source file we gate

    if platform == "python":
        ok, detail = check_python(file_path)
    elif platform == "swift":
        ok, detail = check_swift(file_path)
    elif platform == "rust":
        ok, detail = check_rust(file_path)
    elif platform == "java":
        ok, detail = check_java(file_path)
    elif platform == "go":
        ok, detail = check_go(file_path)
    elif platform == "web":
        ok, detail = check_web(file_path)
    else:
        sys.exit(0)  # unknown platform: no fast-gate check (do not fall through to web)

    if ok:
        sys.exit(0)

    tool_name, output = detail
    rel = dt.relpath(file_path)
    msg = first_meaningful_line(output)
    fingerprint = f"{rel}:{tool_name}:{msg}"

    # Record fingerprint + query breaker (single spawn).
    ls = dt.loop_state_path()
    action = "ok"
    breaker_reason = ""
    try:
        proc = subprocess.run(
            ["python3", ls, "gate-fail", fingerprint],
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json as _json

        data = _json.loads(proc.stdout) if proc.stdout.strip() else {}
        action = data.get("action", "ok")
        breaker_reason = data.get("reason", "")
    except Exception:
        pass  # never let state accounting break the gate

    guidance = {
        "escalate": "Breaker=ESCALATE (same root cause repeated): package this context and hand to the outer Reviewer — this is the inner->outer exception channel.",
        "degrade": "Breaker=DEGRADE (iteration cap): split the task / narrow the convergence target to a sub-task and stabilize locally.",
        "suspend": "Breaker=SUSPEND (iteration cap + budget near exhaustion): pause and surface a diagnostic summary for human review; if a blueprint defect, open the revision channel.",
        "hard-terminate": "Breaker=HARD-TERMINATE (budget exhausted): output the best snapshot + failure diagnosis and stop. Do not retry.",
    }.get(
        action,
        "Breaker=OK: fix in the inner ring and re-run; do NOT proceed to the arch-contract gate while red.",
    )

    # Option C (fast-gate-format-advisory-design.md §4): lint and format are both
    # Blockers, but a FORMAT failure's remediation STRATIFIES — the reformat churn
    # is isolated into a standalone style: commit (references/commit-stratification.md,
    # C-pre) instead of being inline-rewritten into the logic diff, so the logic diff
    # stays reviewable in MR/PR. Lint failures keep the fix-in-ring remediation above.
    if tool_name in ("ruff format", "google-java-format", "gofmt", "rustfmt"):
        guidance = (
            "Format check failed — STRATIFY if the file is legacy-unformatted (the "
            "reformat churn would drown your logic diff): run the formatter on this "
            "file, commit the pure-format change as a standalone `style:` commit "
            "(references/commit-stratification.md, C-pre), then redo the logic edit "
            "on top. If your own edit introduced the drift on an already-formatted "
            "file, fix it inline instead. "
        ) + guidance

    reason = f"Fast-gate failed ({tool_name}) on {rel}: {msg}. {guidance}" + (
        f" [{breaker_reason}]" if breaker_reason and action != "ok" else ""
    )
    dt.emit_block(reason)


if __name__ == "__main__":
    main()
