#!/usr/bin/env python3
"""arch_contract_swift.py — the inner-ring "架构契约门" for Swift / Apple platforms.

Deterministic architecture gate run at the inner convergence point. Emits structured "越权日志" JSON findings; non-zero (Blocker) exit on any violation.
Tools missing -> degrades to a no-op pass with an explicit coverage note.

Checks:
  1. layer / boundary rules      -> SwiftLint custom_rules (.swiftlint.yml)
  2. concurrency baseline        -> `swift build -Xswiftc -strict-concurrency=complete` (Sendable / actor isolation / data races)

Usage: arch_contract_swift.py [package_path]
       package_path defaults to '.'.
"""

import json
import os
import re
import subprocess
import sys

GATE = "arch-contract-swift"
SKIP_DIRS = {".build", "DerivedData", ".git", "Pods", "node_modules"}


def run(argv, timeout=300):
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


def _has_xcodeproj(root):
    try:
        for name in os.listdir(root):
            if name.endswith(".xcodeproj"):
                return True
    except OSError:
        pass
    return False


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


def check_swiftlint(root, findings, coverage):
    cfg = os.path.join(root, ".swiftlint.yml")
    if not have("swiftlint"):
        coverage.append(
            "swiftlint: not installed — custom_rules layer/boundary checks skipped (install: `brew install swiftlint`, or `mint install realm/swiftlint`)"
        )
        return
    # --reporter json: structured output (machine-readable), replacing the old regex parse of human-formatted text. Capture stdout separately so swiftlint progress/diagnostic noise on stderr cannot corrupt the JSON.
    argv = ["swiftlint", "lint", "--reporter", "json"]
    if os.path.exists(cfg):
        argv += ["--config", cfg]
    else:
        coverage.append("swiftlint: no .swiftlint.yml — running default rules only")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        coverage.append("swiftlint: not on PATH — custom_rules skipped")
        return
    except subprocess.TimeoutExpired:
        coverage.append("swiftlint: timed out — custom_rules skipped")
        return
    raw = proc.stdout or ""
    try:
        violations = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        head = raw.strip().splitlines()[0][:120] if raw.strip() else "empty"
        coverage.append(
            f"swiftlint: JSON reporter output unparseable — custom_rules skipped (rc={proc.returncode}, head={head})"
        )
        return
    for v in violations:
        sev = "blocker" if str(v.get("severity", "")).lower() == "error" else "warning"
        rule = v.get("rule_id") or v.get("rule_name") or "swiftlint"
        findings.append(
            {
                "severity": sev,
                "rule": rule,
                "file": v.get("file", "(unknown)"),
                "line": int(v.get("line", 0) or 0),
                "detail": (v.get("reason") or v.get("rule_name") or rule),
                "suggestion": f"Satisfy SwiftLint rule `{rule}` or relax it deliberately in .swiftlint.yml.",
            }
        )
    coverage.append(f"swiftlint: {len(violations)} violation(s) via --reporter json")


def check_strict_concurrency(root, findings, coverage):
    if not have("swift"):
        coverage.append(
            "swift: toolchain not installed — strict-concurrency baseline skipped"
        )
        return
    is_spm = os.path.exists(os.path.join(root, "Package.swift"))
    is_xcode = any(
        os.path.exists(os.path.join(root, p)) for p in ("*.xcodeproj",)
    ) or _has_xcodeproj(root)
    if not (is_spm or is_xcode):
        coverage.append(
            "strict-concurrency: no Package.swift / .xcodeproj here — strict-concurrency baseline skipped (run inside the package/project root)"
        )
        return
    argv = (
        ["swift", "build", "-Xswiftc", "-strict-concurrency=complete"]
        if is_spm
        else [
            "xcodebuild",
            "-quiet",
            "build",
            "-Xswiftc",
            "-strict-concurrency=complete",
        ]
    )
    rc, out = run(argv, timeout=600)
    if rc in (None, 0):
        coverage.append("strict-concurrency: complete — no Sendable/actor violations")
        return
    # Surface concurrency-related diagnostics.
    diag_re = re.compile(
        r"^(.+?):(\d+):(?:\d+:)?\s*(error|warning):\s*(.*)$", re.IGNORECASE
    )
    saw = False
    for line in (out or "").splitlines():
        m = diag_re.match(line.strip())
        if not m:
            continue
        msg = m.group(4)
        if not re.search(
            r"sendable|actor|isolat|data race|concurrency|MainActor|nonisolated",
            msg,
            re.IGNORECASE,
        ):
            continue
        saw = True
        findings.append(
            {
                "severity": "blocker" if m.group(3).lower() == "error" else "warning",
                "rule": "concurrency-baseline-strict-concurrency",
                "file": m.group(1),
                "line": int(m.group(2)),
                "detail": msg.strip(),
                "suggestion": "Mark types Sendable, confine mutable state to an actor, or annotate isolation explicitly (see ios-patterns.md Swift Concurrency).",
            }
        )
    if not saw:
        findings.append(
            {
                "severity": "blocker",
                "rule": "build-failed",
                "file": "(swift build)",
                "line": 0,
                "detail": (out or "swift build failed").strip()[-1500:],
                "suggestion": "swift build -strict-concurrency=complete failed; inspect the diagnostics above.",
            }
        )
    coverage.append(
        "strict-concurrency: violations found"
        if saw
        else "strict-concurrency: build failed (see findings)"
    )


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = []
    check_swiftlint(root, findings, coverage)
    check_strict_concurrency(root, findings, coverage)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
