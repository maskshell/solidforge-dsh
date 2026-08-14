#!/usr/bin/env python3
"""arch_contract_python.py — the inner-ring "架构契约门" for Python.

Deterministic architecture gate run at the inner convergence point (NOT per edit). Emits structured "越权日志" JSON findings; exits non-zero (Blocker) on any violation. Tools missing -> degrades to a no-op pass with an explicit `coverage` note (never silently green).

Checks (best-effort, stdlib for parsing; external tools when configured):
  1. layer / forbidden import contracts  -> import-linter (.importlinter.ini)
  2. cyclic imports                       -> pylint --enable=cyclic-import
  3. concurrency baseline                -> stdlib ast scan for blocking calls inside async def (no external dep)
  4. type baseline                        -> pyright (--outputjson)

Usage: arch_contract_python.py [package_path]
       package_path defaults to '.' (walks .py files, skipping venvs/build dirs).
"""

import ast
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {
    ".venv",
    "venv",
    "env",
    ".git",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".tox",
}
# Names treated as blocking when called directly inside an `async def`.
BLOCKING_CALLS = {
    "time.sleep",
    "sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.request",
    "requests.head",
    "requests.patch",
    "urlopen",
    "urllib.request.urlopen",
}
BLOCKING_METHODS = {"read", "readlines", "readline"}  # only flagged on open() result

GATE = "arch-contract-python"


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


def run(argv, timeout=120):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return None, ""
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def resolve_tool(name):
    """Return an argv prefix [<path>] for a tool, searching PATH then the
    project's local venv bins (.venv/venv/env); None if not found. Finds tools
    installed as project dev deps even when the venv is not active on PATH."""
    from shutil import which

    p = which(name)
    if p:
        return [p]
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    for venv in (".venv", "venv", "env"):
        cand = os.path.join(root, venv, "bin", name)
        if os.path.exists(cand):
            return [cand]
    return None


def find_importlinter_config(root):
    """import-linter auto-discovers setup.cfg/pyproject.toml, but NOT .importlinter.ini;
    return the config path to pass via --config (or a sentinel for auto-discovery, or None)."""
    for name in (".importlinter", ".importlinter.ini", "importlinter.ini"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            return p
    for name in ("setup.cfg", "pyproject.toml"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            return "__auto__"
    return None


def _count_active_contracts(cfg, root):
    """Count active import-linter contracts, format-aware (ACF-I4).

    cfg: find_importlinter_config's return (a file path or "__auto__").
    Returns the number of active contracts: INI [importlinter:contract:...] sections
    or TOML [[tool.importlinter.contracts]] entries. 0 = neutral-by-default template
    (gate skips lint-imports + emits a distinct note, not a misleading "checked").
    """
    count = 0
    files = []
    if cfg and cfg != "__auto__":
        files.append(cfg)
    else:
        for name in ("setup.cfg", "pyproject.toml"):
            candidate = os.path.join(root, name)
            if os.path.exists(candidate):
                files.append(candidate)
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith(";"):
                continue  # commented out — not an active contract
            if fpath.endswith(".toml"):
                if "[[tool.importlinter.contracts" in stripped:
                    count += 1
            elif "[importlinter:contract:" in stripped:
                count += 1
    return count


def check_import_linter(root, findings, coverage):
    cfg = find_importlinter_config(root)
    if not cfg:
        coverage.append(
            "import-linter: not configured (.importlinter.ini / setup.cfg / pyproject.toml absent) — layer/forbidden contracts skipped"
        )
        return
    lint_imports = resolve_tool("lint-imports")
    if not lint_imports:
        coverage.append(
            "import-linter: lint-imports not installed — layer/forbidden contracts skipped (install: `uv add --dev import-linter`, or run `uvx --from import-linter lint-imports`)"
        )
        return
    # ACF-I4: if 0 active contracts (neutral-by-default template), skip lint-imports
    # (nothing to evaluate) + emit a DISTINCT coverage note — NOT the blanket "checked"
    # (which would be a silent-green misrepresentation: rule 3).
    active = _count_active_contracts(cfg, root)
    if active == 0:
        coverage.append(
            "import-linter: 0 active contracts — layering NOT enforced; uncomment + edit "
            "[importlinter:contract:*] in the config to opt in"
        )
        return
    argv = lint_imports
    if cfg != "__auto__":
        argv += ["--config", cfg]
    rc, out = run(argv, timeout=180)
    if rc not in (0, None) and rc != 0:
        detail = out.strip() or "import-linter reported contract violations"
        findings.append(
            {
                "severity": "blocker",
                "rule": "layer-violation",
                "file": cfg if cfg != "__auto__" else "setup.cfg/pyproject.toml",
                "line": 0,
                "detail": detail[-2000:],
                "suggestion": "Fix the import direction to match the declared layers/forbidden contracts; route cross-layer calls through the service layer / interfaces.",
            }
        )
    coverage.append("import-linter: layer/forbidden contracts checked")


def check_cyclic(root, findings, coverage, package):
    pylint = resolve_tool("pylint")
    if not pylint:
        coverage.append(
            "pylint: not installed — cyclic-import check skipped (install: `uv add --dev pylint`)"
        )
        return
    rc, out = run(
        pylint + ["--disable=all", "--enable=cyclic-import", package], timeout=180
    )
    line_re = re.compile(
        r"^(.+?):(\d+):\s*\S*?:?\s*(R0401.*|.*cyclic import.*)$", re.IGNORECASE
    )
    found = False
    for line in (out or "").splitlines():
        m = line_re.match(line.strip())
        if m:
            found = True
            findings.append(
                {
                    "severity": "blocker",
                    "rule": "circular-dependency",
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "detail": m.group(3).strip(),
                    "suggestion": "Break the cycle: extract a shared interface/protocol, invert the dependency, or move the shared code down a layer.",
                }
            )
    coverage.append(
        "pylint cyclic-import: " + ("found cycles" if found else "no cycles")
    )


def _dotted_call(node):
    """Return dotted name of a Call node if resolvable, else None."""
    fn = node.func
    parts = []
    while isinstance(fn, ast.Attribute):
        parts.append(fn.attr)
        fn = fn.value
    if isinstance(fn, ast.Name):
        parts.append(fn.id)
        return ".".join(reversed(parts))
    return None


def _is_open_result_call(node):
    # Detect (<open(...)).read|readlines|readline)(...)
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if not isinstance(fn, ast.Attribute):
        return False
    if fn.attr not in BLOCKING_METHODS:
        return False
    val = fn.value
    return (
        isinstance(val, ast.Call)
        and isinstance(val.func, ast.Name)
        and val.func.id == "open"
    )


def check_concurrency(root, findings, coverage, package):
    """stdlib ast scan: flag blocking calls executed directly inside async def."""
    checked = 0
    for dirpath, dirnames, filenames in os.walk(package or root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            checked += 1
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=fpath)
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.AsyncFunctionDef,)):
                    continue
                for sub in ast.walk(node):
                    if not isinstance(sub, ast.Call):
                        continue
                    dotted = _dotted_call(sub)
                    if dotted and dotted in BLOCKING_CALLS:
                        findings.append(
                            {
                                "severity": "blocker",
                                "rule": "concurrency-baseline-sync-in-async",
                                "file": fpath,
                                "line": sub.lineno,
                                "detail": f"blocking call `{dotted}()` directly inside async def `{node.name}`",
                                "suggestion": "Offload to a thread/process executor (asyncio.to_thread / run_in_executor) or use an async-native API.",
                            }
                        )
                    elif _is_open_result_call(sub):
                        findings.append(
                            {
                                "severity": "blocker",
                                "rule": "concurrency-baseline-blocking-io-in-async",
                                "file": fpath,
                                "line": sub.lineno,
                                "detail": f"synchronous file read inside async def `{node.name}`",
                                "suggestion": "Use aiofiles or asyncio.to_thread for file I/O off the event loop.",
                            }
                        )
    coverage.append(
        f"concurrency-baseline: scanned {checked} .py files for sync-in-async"
    )


def check_types(root, findings, coverage, package):
    """Pyright type-check baseline. Types are the strongest deterministic constraint on Agent hallucination for dynamic Python. --outputjson emits a machine-readable report; stdout is captured alone so config chatter on stderr can't corrupt the JSON. pyright JSON lines are 0-based -> +1 for display."""
    pyright = resolve_tool("pyright")
    if not pyright:
        coverage.append(
            "pyright: not installed — type-check skipped (install: `uv add --dev pyright` or `pip install pyright`)"
        )
        return
    try:
        proc = subprocess.run(
            pyright + ["--outputjson", package or "."],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        coverage.append("pyright: not on PATH — type-check skipped")
        return
    except subprocess.TimeoutExpired:
        coverage.append("pyright: timed out — type-check skipped")
        return
    try:
        report = json.loads(proc.stdout or "{}") if (proc.stdout or "").strip() else {}
    except json.JSONDecodeError:
        coverage.append("pyright: --outputjson unparseable — type-check skipped")
        return
    diags = report.get("generalDiagnostics") or []
    for d in diags:
        sev_raw = str(d.get("severity", "")).lower()
        if sev_raw not in ("error", "warning", "information", "advice"):
            continue
        start = (d.get("range") or {}).get("start") or {}
        rule = d.get("rule") or d.get("code") or "pyright"
        findings.append(
            {
                "severity": "blocker" if sev_raw == "error" else "warning",
                "rule": f"pyright:{rule}",
                "file": d.get("file", "(unknown)"),
                "line": int(start.get("line", -1)) + 1,
                "detail": (d.get("message") or "").strip(),
                "suggestion": "Fix the type error so pyright is clean: correct the call, add a type annotation, or install missing stubs.",
            }
        )
    n_err = sum(1 for d in diags if str(d.get("severity", "")).lower() == "error")
    coverage.append(f"pyright: {len(diags)} diagnostic(s) ({n_err} error-level)")


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    package = sys.argv[1] if len(sys.argv) > 1 else "."
    findings = []
    coverage = []
    check_import_linter(root, findings, coverage)
    check_cyclic(root, findings, coverage, package)
    check_concurrency(root, findings, coverage, package)
    check_types(root, findings, coverage, package)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
