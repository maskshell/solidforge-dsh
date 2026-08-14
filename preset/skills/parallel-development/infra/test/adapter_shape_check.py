#!/usr/bin/env python3
"""adapter_shape_check.py — adapter-family shape contract (BLOCKER; rule 4 codifiable).

A self-contained (rule 7) contract test over the 7 `*_adapter.py`. Each adapter MUST
emit a `violation-log.schema.json`-valid object from its `emit(findings, coverage)`
helper. This gate verifies that ISOLATED-DYNAMICALLY (arch-design §4 D5): it imports
each adapter, invokes `emit()` with MOCK inputs (an empty findings list + a dummy
coverage list), captures stdout (`contextlib.redirect_stdout` + catch `SystemExit` —
the adapters print + `sys.exit` rather than returning, verified against
`vale_adapter.py:49-63` / `license_adapter.py:102-116`), and validates the captured
JSON against the violation-log shape.

Severity is BLOCKER (rule 4: this is a codifiable contract — a missing/typed field is a
proven defect, not a guess). Adapter-family membership is glob-derived (`infra/scripts/
*_adapter.py`), NOT registry-enumerated (D5), so this gate does NOT read
`drift_registry.json`. It composes with `smoke_gates.py`, which validates adapter
output DYNAMICALLY with the external tool armed (or skips) — this gate runs without any
tool (static mocks), so it always runs.

Self-contained (rule 7): duplicates the schema validator + emit helper rather than
importing `violation_log_schema` / a shared lib. Pure stdlib.

Usage:
    python3 infra/test/adapter_shape_check.py        # glob + check all 7 adapters
"""

import contextlib
import glob
import importlib.util
import io
import json
import os
import sys

GATE = "adapter-shape-check"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/parallel-development
ADAPTER_GLOB = os.path.join("infra", "scripts", "*_adapter.py")
REQUIRED_TOP = ("gate", "passed", "coverage", "findings")
REQUIRED_FINDING = ("severity", "rule", "file", "line", "detail", "suggestion")


def find_adapters(root):
    """Glob the adapter family. Membership is glob-derived, NOT registry (arch-design D5)."""
    return sorted(glob.glob(os.path.join(root, ADAPTER_GLOB)))


def validate_shape(obj):
    """Validate obj against violation-log.schema.json (self-contained; rule 7).

    Returns a list of error strings (empty = valid). Checks the required top-level
    fields, `passed` boolean, `coverage`/`findings` list-ness, and each finding's
    required fields + severity enum.
    """
    errors = []
    if not isinstance(obj, dict):
        return ["emit output is not a JSON object"]
    for k in REQUIRED_TOP:
        if k not in obj:
            errors.append(f"missing top-level field '{k}'")
    if "passed" in obj and not isinstance(obj["passed"], bool):
        errors.append("'passed' must be boolean")
    if "coverage" in obj and not isinstance(obj["coverage"], list):
        errors.append("'coverage' must be a list")
    findings = obj.get("findings")
    if findings is not None:
        if not isinstance(findings, list):
            errors.append("'findings' must be a list")
        else:
            for i, f in enumerate(findings):
                if not isinstance(f, dict):
                    errors.append(f"finding[{i}] is not an object")
                    continue
                for k in REQUIRED_FINDING:
                    if k not in f:
                        errors.append(f"finding[{i}] missing '{k}'")
                sev = f.get("severity")
                if sev not in ("blocker", "warning"):
                    errors.append(
                        f"finding[{i}] severity must be blocker|warning, got {sev!r}"
                    )
    return errors


def _load(path):
    """importlib-load an adapter module. Returns the module, or an Exception on failure."""
    name = "adapter_mod_" + os.path.basename(path).replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return RuntimeError("spec_from_file_location returned None")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001 — report import failure, don't crash the gate
        return e
    return mod


def check_adapter(path):
    """Import adapter, invoke emit() with mocks, capture stdout, validate.

    Returns (errors, coverage_bit). errors non-empty -> this adapter violates the shape.
    """
    rel = os.path.relpath(path, ROOT)
    mod = _load(path)
    if isinstance(mod, Exception):
        return [f"{rel}: import failed: {mod}"], f"{rel}: import failed (skipped emit)"
    if not hasattr(mod, "emit"):
        return [f"{rel}: no emit() callable"], f"{rel}: no emit() (skipped)"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            mod.emit([], ["mock-coverage"])  # mock: empty findings + dummy coverage
        except SystemExit:
            pass  # adapters print + sys.exit (verified) — expected, not an error
        except Exception as e:  # noqa: BLE001
            return (
                [f"{rel}: emit() raised {type(e).__name__}: {e}"],
                f"{rel}: emit() raised (captured)",
            )
    out = buf.getvalue()
    try:
        obj = json.loads(out)
    except json.JSONDecodeError as e:
        return [f"{rel}: emit output not JSON ({e})"], f"{rel}: non-JSON output"
    errors = validate_shape(obj)
    bit = (
        f"{rel}: emit() -> valid shape"
        if not errors
        else f"{rel}: {len(errors)} shape error(s)"
    )
    return errors, bit


def run(root):
    """Glob the adapter family, check each. Returns (findings, coverage). Blocker on violation."""
    adapters = find_adapters(root)
    findings = []
    coverage = [
        f"adapter-shape-check (BLOCKER, rule 4 codifiable): glob {ADAPTER_GLOB} -> "
        f"{len(adapters)} adapter(s); isolated-dynamic (import + invoke emit with mocks, "
        "capture stdout, validate vs violation-log.schema.json)"
    ]
    for path in adapters:
        errors, bit = check_adapter(path)
        coverage.append(bit)
        for err in errors:
            findings.append(
                {
                    "severity": "blocker",
                    "rule": "adapter-shape-violation",
                    "file": os.path.relpath(path, ROOT),
                    "line": 0,
                    "detail": err,
                    "suggestion": (
                        "fix the adapter's emit() to produce a violation-log.schema.json-valid "
                        "object (top-level gate/passed/coverage/findings + per-finding "
                        "severity/rule/file/line/detail/suggestion)"
                    ),
                }
            )
    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4 permits Blocker)."""
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


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or ROOT
    findings, coverage = run(root)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
