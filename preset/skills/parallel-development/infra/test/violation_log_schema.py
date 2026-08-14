#!/usr/bin/env python3
"""Violation-log (越权日志) JSON Schema + stdlib validator.

The contract every arch_contract_<lang>.py emits and the convergence loop consumes: {gate, passed, coverage[], findings[{severity, rule, file, line, detail, suggestion}]}. `severity` drives the Blocker decision.

The schema lives at infra/schemas/violation-log.schema.json (single source of truth). This validator is stdlib-only (no `jsonschema` dependency — ADR #1) and supports only the keywords that schema uses: type, required, properties, additionalProperties, items, enum, $ref (to $defs), minLength, minimum.

Imported by smoke_gates.py to assert every gate's stdout conforms. Run directly for the validator's own self-tests:

    python3 infra/test/violation_log_schema.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.normpath(
    os.path.join(HERE, "..", "schemas", "violation-log.schema.json")
)


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


SCHEMA = load_schema()


def _type_ok(value, expected):
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    return checks.get(expected, lambda v: True)(value)


def _validate(value, schema, defs, path):
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            return _validate(value, defs.get(ref.rsplit("/", 1)[-1], {}), defs, path)
        return [f"{path}: unsupported $ref {ref}"]
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        return [f"{path}: expected {expected}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{path}: missing required property '{key}'")
        props = schema.get("properties", {})
        for key, val in value.items():
            if key in props:
                errs += _validate(val, props[key], defs, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected property '{key}'")
    if expected == "array":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                errs += _validate(item, item_schema, defs, f"{path}[{i}]")
    if (
        "minLength" in schema
        and isinstance(value, str)
        and len(value) < schema["minLength"]
    ):
        errs.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
    if (
        "minimum" in schema
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value < schema["minimum"]
    ):
        errs.append(f"{path}: {value} < minimum {schema['minimum']}")
    return errs


def validate(obj):
    """Return a list of schema-violation messages (empty list = valid)."""
    return _validate(obj, SCHEMA, SCHEMA.get("$defs", {}), "$")


# --- self-tests for the validator --------------------------------------------


def _good():
    return {
        "gate": "arch-contract-python",
        "passed": False,
        "coverage": ["concurrency-baseline: scanned 1 .py files for sync-in-async"],
        "findings": [
            {
                "severity": "blocker",
                "rule": "concurrency-baseline-sync-in-async",
                "file": "app/svc.py",
                "line": 3,
                "detail": "blocking call time.sleep() directly inside async def fetch",
                "suggestion": "Offload via asyncio.to_thread / run_in_executor.",
            }
        ],
    }


def main():
    cases = [
        ("valid log", _good(), False),
        ("missing 'passed'", {k: v for k, v in _good().items() if k != "passed"}, True),
        ("coverage not an array", {**_good(), "coverage": "x"}, True),
        (
            "bad severity enum",
            {**_good(), "findings": [{**_good()["findings"][0], "severity": "error"}]},
            True,
        ),
        (
            "finding missing 'detail'",
            {
                **_good(),
                "findings": [
                    {k: v for k, v in _good()["findings"][0].items() if k != "detail"}
                ],
            },
            True,
        ),
        ("unexpected top-level field", {**_good(), "extra": 1}, True),
        (
            "line not an integer",
            {**_good(), "findings": [{**_good()["findings"][0], "line": "3"}]},
            True,
        ),
        (
            "warning severity + passed=true ok",
            {
                **_good(),
                "passed": True,
                "findings": [{**_good()["findings"][0], "severity": "warning"}],
            },
            False,
        ),
        (
            "extra finding display field allowed",
            {**_good(), "findings": [{**_good()["findings"][0], "snippet": "x"}]},
            False,
        ),
    ]
    failed = 0
    for name, obj, expect_errs in cases:
        got = validate(obj)
        ok = bool(got) == expect_errs
        print(f"  {'ok' if ok else 'FAIL'}: {name}" + ("" if ok else f" -> {got}"))
        if not ok:
            failed += 1
    print("PASS" if not failed else "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
