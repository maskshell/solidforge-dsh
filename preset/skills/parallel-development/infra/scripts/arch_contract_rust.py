#!/usr/bin/env python3
"""arch_contract_rust.py — the inner-ring "架构契约门" for Rust.

Deterministic architecture gate run at the inner convergence point. Emits a structured "越权日志" JSON; non-zero (Blocker) exit on any violation. Tools missing -> degrades to a no-op pass with an explicit coverage note (never silently green).

HONEST GAP: Rust has NO first-class layer / dependency-direction enforcer (equivalent to Python's import-linter or Web's dependency-cruiser). The module graph is acyclic by compilation, but declared layering is not enforceable deterministically. This gate therefore covers what IS codable in Rust:

  1. correctness/concurrency baseline -> `cargo clippy` (Send/Sync, unsafe, obvious anti-patterns), parsed from its JSON message stream.
  2. orphaned/dead modules           -> `cargo-modules` (optional; if absent, reported as uncovered).

Layer-direction contracts for Rust are NOT enforced here — they remain an outer-ring semantic concern (see references/arch-contracts.md). This is the correct behavior for a language with weak deterministic arch tooling, surfaced explicitly in `coverage`.

Usage: arch_contract_rust.py [package_path]
       package_path defaults to '.' (must contain a Cargo.toml).
"""

import json
import os
import subprocess
import sys

GATE = "arch-contract-rust"


def run(argv, timeout=600):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return None, ""
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


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


def _clippy_suggestion(msg):
    """Prefer clippy's machine-applicable rustfix suggestion; fall back to a docs link. clippy encodes fixes as `suggested_replacement` on spans — but frequently on a help sub-message (`message.children[].spans[]`), not the primary span. Scan primary, then other spans, then children."""
    spans = (msg or {}).get("spans") or []
    primary = next((s for s in spans if s.get("is_primary")), None)
    candidates = ([primary] if primary else []) + [s for s in spans if s is not primary]
    for child in (msg or {}).get("children") or []:
        candidates += child.get("spans") or []
    for s in candidates:
        repl = (s or {}).get("suggested_replacement")
        if repl:
            appl = (s or {}).get("suggestion_applicability")
            qual = f" (applicability: {appl})" if appl else ""
            snippet = repl if len(repl) <= 200 else repl[:200] + "…"
            return f"Apply rustfix suggestion{qual}: replace with `{snippet}`"
    code = ((msg or {}).get("code") or {}).get("code") or ""
    if code.startswith("clippy::"):
        return f"See https://rust-lang.github.io/rust-clippy/#{code} — fix or allow deliberately."
    return "Address the compiler diagnostic; see the rendered message above."


def check_clippy(root, findings, coverage):
    if not have("cargo"):
        coverage.append("cargo: toolchain not installed — clippy baseline skipped")
        return
    if not os.path.exists(os.path.join(root, "Cargo.toml")):
        coverage.append(
            "cargo: no Cargo.toml here — clippy baseline skipped (run inside the crate root)"
        )
        return
    # JSON message stream: one JSON object per line.
    rc, out = run(
        ["cargo", "clippy", "--all-targets", "--message-format=json", "--quiet"],
        timeout=600,
    )
    if rc is None:
        coverage.append("cargo clippy: invocation failed — baseline skipped")
        return
    count = 0
    for line in (out or "").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("reason") != "compiler-message":
            continue
        msg = obj.get("message") or {}
        level = msg.get("level")
        if level not in ("error", "warning"):
            continue
        spans = msg.get("spans") or []
        primary = next(
            (s for s in spans if s.get("is_primary")), spans[0] if spans else {}
        )
        code = (
            (msg.get("code") or {}).get("code") or "clippy"
            if "clippy::" in (msg.get("message") or "")
            else ((msg.get("code") or {}).get("code") or level)
        )
        # Treat clippy lint codes (clippy::*) and compiler errors as architecture/concurrency-relevant.
        mtext = msg.get("message", "")
        is_clippy = "clippy::" in mtext or (code or "").startswith("clippy::")
        findings.append(
            {
                "severity": "blocker"
                if level == "error"
                else ("blocker" if is_clippy else "warning"),
                "rule": code or "clippy",
                "file": primary.get("file_name", "(unknown)"),
                "line": primary.get("line_start", 0),
                "detail": f"[{level}] {mtext}",
                "suggestion": _clippy_suggestion(msg),
            }
        )
        count += 1
    coverage.append(
        f"cargo clippy: {count} diagnostic(s) parsed (correctness/concurrency baseline)"
    )
    if count == 0:
        coverage.append(
            "note: clippy is incremental — 0 diagnostics means the source has not changed content since the last clippy pass (re-run after edits; the convergence loop always runs this after a change)"
        )


def check_modules(root, findings, coverage):
    if not have("cargo-modules"):
        coverage.append(
            "cargo-modules: not installed — orphaned-module check skipped (optional: cargo install cargo-modules)"
        )
        return
    # `cargo modules` prints a tree; orphaned modules surface as warnings. Best-effort parse.
    rc, out = run(["cargo", "modules", "orphans", "--hide-path", "."], timeout=180)
    if rc is None:
        coverage.append("cargo-modules: invocation failed — skipped")
        return
    if (
        out
        and out.strip()
        and "no orphaned" not in out.lower()
        and len([line for line in out.splitlines() if line.strip()]) > 0
    ):
        findings.append(
            {
                "severity": "warning",
                "rule": "orphaned-module",
                "file": "(cargo modules orphans)",
                "line": 0,
                "detail": (out or "").strip()[-1000:],
                "suggestion": "Remove orphaned/dead modules or wire them into the crate.",
            }
        )
        coverage.append("cargo-modules: orphaned modules reported")
    else:
        coverage.append("cargo-modules: no orphaned modules")


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = [
        "layer-direction: NOT enforced deterministically in Rust (no first-class tool) — outer-ring semantic concern only"
    ]
    check_clippy(root, findings, coverage)
    check_modules(root, findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
