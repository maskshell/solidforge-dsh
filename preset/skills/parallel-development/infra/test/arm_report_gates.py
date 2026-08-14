#!/usr/bin/env python3
"""Verify the gate tools + LSP advisory are surfaced by arm.py.

(1) report_gates lists every gate tool in the arming status report.
(2) prepare_tools prints the system install hints (gitleaks / cargo-audit / cargo-nextest) without side effects, on a Cargo-only fixture.
(3) lsp_advisory recommends the matching official LSP plugin per detected language.
(4) absent_tool_hint fires / suppresses correctly.

Run:
    python3 infra/test/arm_report_gates.py
"""

import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARM_PY = os.path.join(ROOT, "infra", "install", "arm.py")

_spec = importlib.util.spec_from_file_location("pd_arm", ARM_PY)
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  {'ok' if cond else 'FAIL'}: {name}")


def t_report_lists_new_tools():
    tmp = tempfile.mkdtemp(prefix="pd_report_")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            arm.report_gates(tmp)
        out = buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for label in [
        "pyright (Python type gate)",
        "tsc (Web type gate)",
        "gitleaks (secrets gate)",
        "pip-audit (Python supply-chain)",
        "npm audit (Web supply-chain)",
        "cargo-audit (Rust supply-chain)",
        "dependency-check (Java supply-chain)",
        "pytest (Python test gate)",
        "vitest (Web test gate)",
        "mvn / gradle (Java build + test)",
        "javac (Java type gate)",
        "google-java-format (Java fast gate)",
        "checkstyle (Java arch gate)",
        "go (Go build + test)",
        "gofmt (Go fast gate)",
        "golangci-lint (Go arch gate)",
        "govulncheck (Go supply-chain)",
    ]:
        check(f"status report lists: {label}", label in out)
    # legacy tools still reported (regression guard)
    check("status report still lists ruff (legacy)", "ruff (Python fast gate)" in out)


def t_prepare_tools_prints_system_hints():
    # Cargo-only fixture: Rust branch is print-only (no package-manager mutation), and no pyproject/package.json means no uv/npm/poetry invocation occurs.
    tmp = tempfile.mkdtemp(prefix="pd_prepare_")
    try:
        with open(os.path.join(tmp, "Cargo.toml"), "w") as fh:
            fh.write('[package]\nname = "x"\nversion = "0.1.0"\nedition = "2021"\n')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            arm.prepare_tools(tmp)
        out = buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("prepare_tools prints gitleaks hint", "brew install gitleaks" in out)
    check("prepare_tools prints cargo-audit hint", "cargo install cargo-audit" in out)
    check(
        "prepare_tools prints cargo-nextest hint", "cargo install cargo-nextest" in out
    )


def t_lsp_advisory():
    # Multi-language fixture: each detected language's official LSP plugin is recommended.
    tmp = tempfile.mkdtemp(prefix="pd_lsp_")
    try:
        for m in (
            "pyproject.toml",
            "Cargo.toml",
            "package.json",
            "pom.xml",
            "Package.swift",
            "go.mod",
        ):
            with open(os.path.join(tmp, m), "w") as fh:
                fh.write("")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            arm.lsp_advisory(tmp)
        out = buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("lsp advisory recommends pyright-lsp", "pyright-lsp" in out)
    check("lsp advisory recommends rust-analyzer-lsp", "rust-analyzer-lsp" in out)
    check("lsp advisory recommends typescript-lsp", "typescript-lsp" in out)
    check("lsp advisory recommends jdtls-lsp", "jdtls-lsp" in out)
    check("lsp advisory recommends swift-lsp", "swift-lsp" in out)
    check("lsp advisory recommends gopls-lsp", "gopls-lsp" in out)
    check(
        "lsp advisory states it does NOT install servers",
        "does NOT bundle .lsp.json" in out,
    )
    check(
        "lsp advisory notes plugin detection limit",
        "cannot detect whether a Claude Code plugin" in out,
    )

    # Empty project: no advisory printed.
    tmp2 = tempfile.mkdtemp(prefix="pd_lsp_empty_")
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            arm.lsp_advisory(tmp2)
        check("lsp advisory silent when no language detected", buf.getvalue() == "")
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)


def t_absent_tool_hint():
    h = arm.absent_tool_hint(
        ["gitleaks (secrets gate)", "pip-audit (Python supply-chain)"], False
    )
    check("hint fires when tools absent & no --with-tools", h is not None)
    check("hint points to --with-tools", h is not None and "--with-tools" in h)
    check(
        "hint names system tools",
        h is not None and "gitleaks" in h and "cargo-audit" in h,
    )
    check(
        "hint suppressed under --with-tools", arm.absent_tool_hint(["x"], True) is None
    )
    check(
        "hint suppressed when nothing absent", arm.absent_tool_hint([], False) is None
    )


def t_report_gates_returns_absent():
    tmp = tempfile.mkdtemp(prefix="pd_report_ret_")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            absent = arm.report_gates(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("report_gates returns a list", isinstance(absent, list))
    check(
        "report_gates absent entries are strings",
        all(isinstance(x, str) for x in absent),
    )


def main():
    for fn in (
        t_report_lists_new_tools,
        t_prepare_tools_prints_system_hints,
        t_lsp_advisory,
        t_absent_tool_hint,
        t_report_gates_returns_absent,
    ):
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
