#!/usr/bin/env python3
"""Spec run-record schema + stdlib validator (iteration I6).

Loads infra/schemas/run-record.schema.json and validates a record.
Reuses the generic _validate algorithm from plan_model_schema (within-skill — no duplication).
The schema enforces field isolation structurally: `rightness` is an enum with exactly ONE value ("human_confirm_required"), so it can never hold anything else regardless of process_converged.

Run directly for the validator's self-tests:

    python3 infra/test/run_record_schema.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plan_model_schema import _validate  # noqa: E402 — within-skill reuse (needs the sys.path.insert above)

SCHEMA_PATH = os.path.normpath(
    os.path.join(HERE, "..", "schemas", "run-record.schema.json")
)


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


SCHEMA = load_schema()


def validate(obj):
    return _validate(obj, SCHEMA, SCHEMA.get("$defs", {}), "$")


def _good():
    return {
        "artifact_type": "iteration-plan",
        "process_converged": True,
        "rightness": "human_confirm_required",
        "inner_ring": {
            "passed": True,
            "blockers": 0,
            "findings": 0,
            "profile": "iteration-plan",
        },
        "outer_ring": {"passed": True, "blockers": 0, "findings": 1},
        "coverage": [],
        "caveats": ["rightness is human_confirm_required by design"],
    }


def _without(d, k):
    return {kk: v for kk, v in d.items() if kk != k}


def main():
    cases = [
        ("valid converged run-record", _good(), False),
        (
            "valid non-converged (process_converged false)",
            {**_good(), "process_converged": False},
            False,
        ),
        (
            "valid research artifact_type",
            {
                **_good(),
                "artifact_type": "research",
                "inner_ring": {**_good()["inner_ring"], "profile": "research-v1"},
            },
            False,
        ),
        (
            "rightness NOT the constant (enum isolation)",
            {**_good(), "rightness": "converged"},
            True,
        ),
        ("rightness missing", _without(_good(), "rightness"), True),
        ("process_converged missing", _without(_good(), "process_converged"), True),
        ("process_converged wrong type", {**_good(), "process_converged": "yes"}, True),
        (
            "inner_ring missing 'blockers'",
            {**_good(), "inner_ring": _without(_good()["inner_ring"], "blockers")},
            True,
        ),
        ("bad artifact_type enum", {**_good(), "artifact_type": "roadmap"}, True),
        (
            "blockers below minimum",
            {**_good(), "inner_ring": {**_good()["inner_ring"], "blockers": -1}},
            True,
        ),
        ("unexpected top-level field", {**_good(), "extra": 1}, True),
        (
            "inner_ring unexpected field",
            {**_good(), "inner_ring": {**_good()["inner_ring"], "phantom": 1}},
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
