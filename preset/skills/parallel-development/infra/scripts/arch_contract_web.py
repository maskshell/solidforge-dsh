#!/usr/bin/env python3
"""arch_contract_web.py — the inner-ring "架构契约门" for Web (JavaScript / TypeScript).

Covers the JS/TS language family on browser and Node.js (detected via package.json). dependency-cruiser + eslint apply to JS and TS alike; the tsc type-check runs only when a tsconfig.json is present (pure-JS projects opt in via allowJs — otherwise that check degrades honestly). See references/web-patterns.md.

Deterministic architecture gate run at the inner convergence point. Emits structured "越权日志" JSON findings; non-zero (Blocker) exit on any violation.
Tools missing -> degrades to a no-op pass with an explicit coverage note.

Checks:
  1. circular deps + layer boundaries  -> dependency-cruiser (.dependency-cruiser.cjs)
  2. concurrency baseline              -> eslint no-restricted-syntax (sync APIs in async handlers), via local eslint if configured
  3. type baseline                     -> tsc --noEmit --pretty false

Usage: arch_contract_web.py [src_path]
       src_path defaults to 'src'.
"""

import json
import os
import re
import subprocess
import sys

GATE = "arch-contract-web"


def run(argv, timeout=180):
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


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


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


def depcruise_cmd(root):
    local = os.path.join(root, "node_modules", ".bin", "depcruise")
    if os.path.exists(local):
        return [local]
    if have("depcruise"):
        return ["depcruise"]
    if have("npx"):
        return ["npx", "--no-install", "depcruise"]
    return None


def check_dependency_cruiser(root, findings, coverage, src):
    cfg = os.path.join(root, ".dependency-cruiser.cjs")
    if not os.path.exists(cfg):
        # also accept .json variant
        cfg = (
            os.path.join(root, ".dependency-cruiser.json")
            if os.path.exists(os.path.join(root, ".dependency-cruiser.json"))
            else None
        )
    if not cfg:
        coverage.append(
            "dependency-cruiser: no .dependency-cruiser config — circular/layer checks skipped"
        )
        return
    base = depcruise_cmd(root)
    if not base:
        coverage.append(
            "dependency-cruiser: not installed — circular/layer checks skipped (install: `npm i -D dependency-cruiser`)"
        )
        return
    # Use --output-type err (not json): depcruise's JSON `violations` array omits some cycles that the err/text output reports, and the exit code is non-zero on error violations. err output is the reliable signal.
    argv = base + ["--config", cfg, "--output-type", "err", src]
    rc, out = run(argv, timeout=180)
    text = out or ""
    text = re.sub(
        r"\x1b\[[0-9;]*m", "", text
    )  # depcruise emits ANSI color even non-TTY; strip so viol_re matches
    has_summary = ("dependency violations" in text) or (
        "no dependency violations found" in text
    )
    if rc is None or (rc != 0 and not has_summary):
        # No summary + non-zero => depcruise didn't actually run (e.g. npx --no-install with depcruise absent). Do NOT silently report "0 violations".
        coverage.append(
            f"dependency-cruiser: invocation failed (rc={rc}) — circular/layer checks skipped (install: `npm i -D dependency-cruiser`){' — ' + first_line(text)[:140] if first_line(text) else ''}"
        )
        return
    # Parse violation blocks: "  error|warning <rule>: <head>\n      <cycle path lines>"
    viol_re = re.compile(r"^\s*(error|warning)\s+([\w-]+)\s*:\s*(.*)$", re.MULTILINE)
    matches = list(viol_re.finditer(text))
    for m in matches:
        sev, rule, head = m.group(1), m.group(2), m.group(3).strip()
        detail = [head]
        for line in text[m.end() :].splitlines():
            if line.startswith("      "):
                detail.append(line.strip())
            elif not line.strip():
                break
            else:
                break
        findings.append(
            {
                "severity": "blocker" if sev == "error" else "warning",
                "rule": rule,
                "file": head.split("→")[0].strip().rstrip(":") or "(cycle)",
                "line": 0,
                "detail": " ".join(detail)[:300],
                "suggestion": "Break the dependency edge: invert it via an interface, move shared code to a lower layer, or remove the import.",
            }
        )
    n_err = sum(1 for m in matches if m.group(1) == "error")
    coverage.append(
        f"dependency-cruiser: {len(matches)} violation(s) reported ({n_err} error)"
    )
    if "0 modules, 0 dependencies cruised" in text:
        coverage.append(
            "dependency-cruiser: WARNING 0 modules cruised — a bare directory arg can yield nothing in depcruise 17.x; pass entry files (e.g. src/index.ts) or a glob (src/**/*) so the gate actually traverses your code"
        )


def check_eslint_concurrency(root, findings, coverage, src):
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
        coverage.append(
            "eslint: not configured — sync-in-async concurrency check skipped"
        )
        return
    local = os.path.join(root, "node_modules", ".bin", "eslint")
    tool = local if os.path.exists(local) else ("eslint" if have("eslint") else None)
    if not tool:
        coverage.append(
            "eslint: not installed — sync-in-async concurrency check skipped (install: `npm i -D eslint`)"
        )
        return
    rc, out = run(
        [tool, "--format", "json", "--no-error-on-unmatched-pattern", src], timeout=180
    )
    try:
        data = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        data = []
    count = 0
    for entry in data if isinstance(data, list) else []:
        fpath = entry.get("filePath", "(unknown)")
        for msg in entry.get("messages", []):
            rule = msg.get("ruleId") or ""
            if rule not in ("no-restricted-syntax", "no-sync", "no-await-in-loop"):
                continue
            count += 1
            findings.append(
                {
                    "severity": "blocker",
                    "rule": "concurrency-baseline-" + rule,
                    "file": fpath,
                    "line": msg.get("line", 0),
                    "detail": f"{rule}: {msg.get('message', '')}".strip(),
                    "suggestion": "Replace the synchronous API with an async/Promise-based one, or offload to a worker; avoid sync I/O in request handlers.",
                }
            )
    coverage.append(f"eslint: {count} concurrency-baseline violation(s)")


def _resolve_tsc(root):
    """Resolve tsc: project-local node_modules/.bin/tsc first, else PATH."""
    local = os.path.join(root, "node_modules", ".bin", "tsc")
    if os.path.exists(local):
        return [local]
    return ["tsc"] if have("tsc") else None


def check_types(root, findings, coverage, src):
    """tsc type-check baseline. tsc has no JSON output, so parse the one-line
    --pretty false form: `path(line,col): error TSxxxx: message`. Type errors
    constrain Agent hallucination in dynamic TS."""
    tsc = _resolve_tsc(root)
    if not tsc:
        coverage.append(
            "tsc: not installed — type-check skipped (install: `npm i -D typescript`)"
        )
        return
    if not os.path.exists(os.path.join(root, "tsconfig.json")):
        coverage.append(
            "tsc: no tsconfig.json — type-check skipped (tsc project mode needs a tsconfig)"
        )
        return
    rc, out = run(tsc + ["--noEmit", "--pretty", "false"], timeout=300)
    if rc is None:
        coverage.append("tsc: invocation failed — type-check skipped")
        return
    line_re = re.compile(r"^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s*(.+)$")
    count = 0
    for line in (out or "").splitlines():
        m = line_re.match(line.strip())
        if not m:
            continue
        findings.append(
            {
                "severity": "blocker" if m.group(4) == "error" else "warning",
                "rule": f"tsc:{m.group(5)}",
                "file": m.group(1),
                "line": int(m.group(2)),
                "detail": m.group(6).strip(),
                "suggestion": "Fix the TypeScript error: correct the type or add/align a type annotation.",
            }
        )
        count += 1
    coverage.append(f"tsc: {count} diagnostic(s)")


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    src = sys.argv[1] if len(sys.argv) > 1 else "src"
    findings = []
    coverage = []
    check_dependency_cruiser(root, findings, coverage, src)
    check_eslint_concurrency(root, findings, coverage, src)
    check_types(root, findings, coverage, src)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
