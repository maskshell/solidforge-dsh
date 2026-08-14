#!/usr/bin/env python3
"""Run-record JSON Schema + stdlib validator.

The contract `loop_state.py run-record` emits: the normalized convergence-loop run record with the computed `l4_assessment` block (the instrumented form of references/maturity.md's rubric).

The schema lives at infra/schemas/run-record.schema.json (single source of truth). This validator is stdlib-only (no `jsonschema` dependency — ADR #1) and supports only the keywords that schema uses: type, required, properties, additionalProperties, items, enum, $ref (to $defs), minLength, minimum.

Imported by run_record.py to assert every emitted record conforms. Run directly for the validator's own self-tests:

    python3 infra/test/run_record_schema.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.normpath(
    os.path.join(HERE, "..", "schemas", "run-record.schema.json")
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
        "task_id": "probe1",
        "rightness": "human_confirm_required",
        "blueprint_ref": "docs/intent-blueprints/x.blueprint.md",
        "blueprint_version": "v1",
        "started_at": "2026-06-19T14:00:00+00:00",
        "ended_at": "2026-06-19T14:41:03+00:00",
        "outcome": "converged",
        "final_status": "converged",
        "converged": True,
        "dod_satisfied": True,
        "steps": {"inner": 65, "outer": 2, "total": 67},
        "budget": {
            "token_used": 1200000,
            "token_cap": 2000000,
            "time_used": 2463,
            "time_cap": 1800,
            "cost_used": 3.1,
            "cost_cap": 5.0,
        },
        "breakers_fired": [
            {
                "action": "escalate",
                "reason": "app/svc.py:ruff:undefined name",
                "at_iteration": 65,
                "at": "2026-06-19T14:30:00+00:00",
            },
        ],
        "top_fingerprints": [
            {"fingerprint": "app/svc.py:ruff:undefined name", "count": 3},
        ],
        "outer_verdicts": [
            {
                "verdict": "rewrite",
                "findings_count": 3,
                "at": "2026-06-19T14:35:00+00:00",
            },
            {"verdict": "pass", "findings_count": 0, "at": "2026-06-19T14:40:00+00:00"},
        ],
        "rollbacks": [],
        "task": {
            "codebase_novelty": "novel",
            "requirement_clarity": "fuzzy",
            "difficulty": "high",
            "attended": False,
            "declared_at": "2026-06-19T14:00:00+00:00",
            "target_horizon_steps": 60,
        },
        "l4_assessment": {
            "is_l4_probe": True,
            "provisional_verdict": "l4-evidenced",
            "terminal_cause": "converged",
            "horizon_met": True,
            "outcome_met": True,
            "error_compounding_defended": True,
            "goal_drift_defended": True,
            "context_rot_defended": True,
            "steps_total": 67,
            "target_horizon_steps": 60,
            "breakers_fired_count": 1,
            "rollbacks_count": 0,
            "outer_reviews": 2,
            "caveats_addressed": ["caveat-2-unproven-at-scale"],
            "human_confirm_required": True,
        },
    }


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


def main():
    cases = [
        ("valid l4-evidenced record (with task)", _good(), False),
        (
            "valid not-a-probe record (task omitted)",
            _without(_good(), "task")
            | {
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "is_l4_probe": False,
                    "provisional_verdict": "not-a-probe",
                    "caveats_addressed": [],
                }
            },
            False,
        ),
        (
            "valid with rollbacks populated",
            {
                **_good(),
                "rollbacks": [
                    {"lost_uc": "UC-login", "at": "2026-06-19T14:20:00+00:00"}
                ],
            },
            False,
        ),
        (
            "valid with upstream provenance (rich path)",
            {
                **_good(),
                "upstream": {
                    "producer": "blueprint-crafting",
                    "process_converged": False,
                    "profile": "iteration-plan",
                },
            },
            False,
        ),
        (
            "upstream rejects unknown subfields (additionalProperties:false)",
            {**_good(), "upstream": {"producer": "blueprint-crafting", "bogus": 1}},
            True,
        ),
        (
            "valid inconclusive (resource-capped)",
            {
                **_good(),
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "provisional_verdict": "inconclusive",
                    "terminal_cause": "resource-capped",
                    "caveats_addressed": [],
                },
            },
            False,
        ),
        ("missing 'l4_assessment'", _without(_good(), "l4_assessment"), True),
        (
            "missing terminal_cause in l4_assessment",
            {
                **_good(),
                "l4_assessment": _without(_good()["l4_assessment"], "terminal_cause"),
            },
            True,
        ),
        (
            "bad terminal_cause enum",
            {
                **_good(),
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "terminal_cause": "timeout",
                },
            },
            True,
        ),
        ("missing required 'outcome'", _without(_good(), "outcome"), True),
        ("missing required 'dod_satisfied'", _without(_good(), "dod_satisfied"), True),
        ("bad outcome enum", {**_good(), "outcome": "done"}, True),
        (
            "bad provisional_verdict enum",
            {
                **_good(),
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "provisional_verdict": "maybe",
                },
            },
            True,
        ),
        (
            "steps.total not an integer",
            {**_good(), "steps": {**_good()["steps"], "total": "67"}},
            True,
        ),
        (
            "human_confirm_required not a boolean",
            {
                **_good(),
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "human_confirm_required": "yes",
                },
            },
            True,
        ),
        ("unexpected top-level field", {**_good(), "extra": 1}, True),
        (
            "task.bad difficulty enum",
            {**_good(), "task": {**_good()["task"], "difficulty": "extreme"}},
            True,
        ),
        (
            "breaker_firing missing 'reason'",
            {
                **_good(),
                "breakers_fired": [_without(_good()["breakers_fired"][0], "reason")],
            },
            True,
        ),
        (
            "caveats_addressed not an array",
            {
                **_good(),
                "l4_assessment": {
                    **_good()["l4_assessment"],
                    "caveats_addressed": "caveat-2",
                },
            },
            True,
        ),
        (
            "outer_verdict bad enum",
            {
                **_good(),
                "outer_verdicts": [
                    {**_good()["outer_verdicts"][0], "verdict": "maybe"}
                ],
            },
            True,
        ),
        (
            "fingerprint count below minimum",
            {
                **_good(),
                "top_fingerprints": [{**_good()["top_fingerprints"][0], "count": 0}],
            },
            True,
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
