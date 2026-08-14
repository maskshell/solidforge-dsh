#!/usr/bin/env python3
"""Plan-model JSON Schema + stdlib validator.

The contract this skill freezes: the normalized plan-model, whose EXECUTABLE SUBSET (item_id / seq / depends_on / dod_ref) round-trips losslessly with parallel-development's plan_queue.py frozen queue (ADR #1). Every item field is classified executable / upstream_only / downstream_only (see the schema's subset_tags and EXECUTABLE_SUBSET in plan_model.py).

The schema lives at infra/schemas/plan-model.schema.json (single source of truth). This validator is stdlib-only (no `jsonschema` dependency — mirrors parallel-development's run_record_schema.py, workspace rule 7) and supports only the keywords that schema uses: type, required, properties, additionalProperties, items, enum, $ref (to $defs), minLength, minimum.

Imported by round_trip.py to assert every golden + round-tripped model conforms. Run directly for the validator's own self-tests:

    python3 infra/test/plan_model_schema.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.normpath(
    os.path.join(HERE, "..", "schemas", "plan-model.schema.json")
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
    return checks.get(expected, lambda _v: True)(value)


def _validate(value, schema, defs, path):
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            return _validate(value, defs.get(ref.rsplit("/", 1)[-1], {}), defs, path)
        return [f"{path}: unsupported $ref {ref}"]
    expected = schema.get("type")
    # union types (e.g. ["string", "null"]) — accept if any member type matches
    if isinstance(expected, list):
        if not any(_type_ok(value, t) for t in expected):
            return [f"{path}: expected one of {expected}, got {type(value).__name__}"]
        expected = None  # already checked; don't re-check below
    if expected and not _type_ok(value, expected):
        return [f"{path}: expected {expected}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{path}: missing required property '{key}'")
        props = schema.get("properties", {})
        ap = schema.get("additionalProperties")
        for key, val in value.items():
            if key in props:
                errs += _validate(val, props[key], defs, f"{path}.{key}")
            elif ap is False:
                errs.append(f"{path}: unexpected property '{key}'")
            elif isinstance(ap, dict):
                # additionalProperties as a schema (e.g. anchors map) — validate each entry
                errs += _validate(val, ap, defs, f"{path}.{key}")
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
    if (
        "minItems" in schema
        and isinstance(value, list)
        and len(value) < schema["minItems"]
    ):
        errs.append(f"{path}: length {len(value)} < minItems {schema['minItems']}")
    return errs


def validate(obj):
    """Return a list of schema-violation messages (empty list = valid)."""
    return _validate(obj, SCHEMA, SCHEMA.get("$defs", {}), "$")


# --- self-tests for the validator --------------------------------------------


def _good():
    """A minimal valid plan-model (iteration-plan with 2 items)."""
    return {
        "plan_model_version": "v1",
        "artifact_type": "iteration-plan",
        "authority_chain": ["docs/arch-design.md", "docs/iteration-plan.md"],
        "conflict_rule": "on conflict, authority_chain[0] wins",
        "items": [
            {
                "item_id": "I0",
                "seq": 0,
                "depends_on": [],
                "dod_ref": "docs/iteration-plan.md#I0-done",
                "title": "scaffold",
                "scope": "SKILL.md + activation",
                "source_location": "iteration-plan.md §3",
                "complexity": "M",
                "risk": "activation collision",
                "odp_status": [],
                "constraints_profile": "iteration-plan",
                "parallel_group": None,
                "blueprint_subset": [],
            },
            {
                "item_id": "I1",
                "seq": 1,
                "depends_on": ["I0"],
                "dod_ref": "docs/iteration-plan.md#I1-done",
            },
        ],
        "subset_tags": {
            "executable": ["item_id", "seq", "depends_on", "dod_ref"],
            "upstream_only": [
                "title",
                "scope",
                "source_location",
                "complexity",
                "risk",
                "odp_status",
                "constraints_profile",
                "parallel_group",
            ],
            "downstream_only": ["blueprint_subset"],
        },
    }


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


def main():
    cases = [
        ("valid minimal plan-model (full + sparse items)", _good(), False),
        (
            "valid without optional conflict_rule/subset_tags",
            _without(_without(_good(), "conflict_rule"), "subset_tags"),
            False,
        ),
        (
            "valid research artifact_type",
            {**_good(), "artifact_type": "research"},
            False,
        ),
        (
            "valid with anchors map (additionalProperties-schema)",
            {
                **_good(),
                "anchors": {
                    "jtbd": {"present": True, "ref": "spec#jtbd"},
                    "scope-boundary": {"present": True},
                },
            },
            False,
        ),
        (
            "anchor entry missing required 'present'",
            {**_good(), "anchors": {"jtbd": {"ref": "spec#jtbd"}}},
            True,
        ),
        (
            "odp with resolution (additive optional field)",
            {
                **_good(),
                "items": [
                    {
                        **_good()["items"][0],
                        "odp_status": [
                            {
                                "id": "ODP-1",
                                "kind": "resolve-now",
                                "resolution": "decided: X",
                            }
                        ],
                    }
                ],
            },
            False,
        ),
        (
            "valid item with odp_status populated",
            {
                **_good(),
                "items": [
                    {
                        **_good()["items"][0],
                        "odp_status": [{"id": "ODP-1", "kind": "resolve-now"}],
                    }
                ],
            },
            False,
        ),
        ("missing required 'items'", _without(_good(), "items"), True),
        (
            "missing required 'authority_chain'",
            _without(_good(), "authority_chain"),
            True,
        ),
        (
            "empty authority_chain (minItems 1)",
            {**_good(), "authority_chain": []},
            True,
        ),
        ("bad artifact_type enum", {**_good(), "artifact_type": "roadmap"}, True),
        (
            "item missing required 'item_id'",
            {**_good(), "items": [_without(_good()["items"][0], "item_id")]},
            True,
        ),
        (
            "item missing required 'dod_ref'",
            {
                **_good(),
                "items": [
                    {
                        **_good()["items"][0],
                        "dod_ref": _good()["items"][0]["dod_ref"],
                        "item_id": "X",
                    }
                ]
                if False
                else [_without(_good()["items"][0], "dod_ref")],
            },
            True,
        ),
        (
            "item bad complexity enum",
            {**_good(), "items": [{**_good()["items"][0], "complexity": "XXL"}]},
            True,
        ),
        (
            "item seq below minimum",
            {**_good(), "items": [{**_good()["items"][0], "seq": -1}]},
            True,
        ),
        (
            "item unexpected property",
            {**_good(), "items": [{**_good()["items"][0], "phantom": 1}]},
            True,
        ),
        ("top-level unexpected property", {**_good(), "extra": 1}, True),
        (
            "odp bad kind enum",
            {
                **_good(),
                "items": [
                    {
                        **_good()["items"][0],
                        "odp_status": [{"id": "ODP-1", "kind": "maybe"}],
                    }
                ],
            },
            True,
        ),
        (
            "odp missing required 'id'",
            {
                **_good(),
                "items": [
                    {**_good()["items"][0], "odp_status": [{"kind": "resolve-now"}]}
                ],
            },
            True,
        ),
        (
            "parallel_group wrong type (integer not string/null)",
            {**_good(), "items": [{**_good()["items"][0], "parallel_group": 3}]},
            True,
        ),
        (
            "subset_tags missing required 'downstream_only'",
            {
                **_good(),
                "subset_tags": _without(_good()["subset_tags"], "downstream_only"),
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
