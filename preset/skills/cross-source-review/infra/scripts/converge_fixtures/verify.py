#!/usr/bin/env python3
"""verify.py — offline verification harness for converge.py (CSR-I4 DoD).

Runs converge.py build-record on each fixture in this directory, asserts the expected
substantive_converged / stalemate / per-round verdicts, AND validates every emitted
record against convergence-record.schema.json (the output contract). Also exercises
the pluggable-seam malformation-rejection path (a finding missing `evidence` is
rejected with a clear error).

OFFLINE + DETERMINISTIC (rule 4): no LLM, no network. The CSR-I5 offline
convergence-policy gate will reuse these fixtures + assertions (mirrors pd's
infra/test/hetero_review_wiring.py pattern).

Run:  python3 infra/scripts/converge_fixtures/verify.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERGE = os.path.normpath(os.path.join(HERE, "..", "converge.py"))
SCHEMAS = os.path.normpath(os.path.join(HERE, "..", "..", "schemas"))
RECORD_SCHEMA = os.path.join(SCHEMAS, "convergence-record.schema.json")

# jsonschema availability flag WITHOUT a top-level jsonschema import (avoids ruff F401 +
# Pyright "unused"): find_spec sets the flag; the actual import is local to
# _validate_record (provably bound at the use site). Graceful-skip when absent (rule 3).
HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


# (fixture, expected_substantive_converged, expected_stalemate, [(round, verdict, blockers), ...])
CASES = [
    ("converged.json", True, False, [(1, "pass", 0), (2, "pass", 0)]),
    ("stalemate.json", False, True, [(1, "rewrite", 1), (2, "rewrite", 1)]),
    (
        "core_claims_uncovered.json",
        False,
        True,
        [(1, "pass", 0), (2, "pass", 0)],
    ),
    ("degraded.json", False, True, [(1, "rewrite", 1), (2, "pass", 0)]),
    ("warnings_dont_block.json", True, False, [(1, "pass", 0), (2, "pass", 0)]),
]

# Per-fixture invariants on the round/findings-count fields (the reconciliation shape).
# (fixture, [(round, same_count, hetero_count, hetero_degraded), ...])
COUNT_INVARIANTS = {
    "converged.json": [(1, 0, 0, False), (2, 0, 0, False)],
    "stalemate.json": [(1, 1, 0, False), (2, 1, 0, False)],
    "core_claims_uncovered.json": [(1, 0, 0, False), (2, 0, 0, False)],
    # degraded: hetero_findings count is 0 in the record (degraded wins); het_dropped
    # (a blocker in the input) must NOT inflate blockers (already asserted via 1 not 2).
    "degraded.json": [(1, 1, 0, True), (2, 0, 0, False)],
    "warnings_dont_block.json": [(1, 1, 1, False), (2, 1, 0, False)],
}

# Per-fixture coverage-note substring checks (rule 3 — honest notes never silent).
COVERAGE_CONTAINS = {
    "converged.json": ["core-claims-coverage: 2/2", "cap=2, rounds=2"],
    "stalemate.json": ["core-claims-coverage: 1/1", "cap=2, rounds=2"],
    "core_claims_uncovered.json": [
        "core-claims-coverage: 1/2",
        "cap=2, rounds=2",
    ],
    "degraded.json": [
        "round 1 different-family degraded: error_max_budget_usd",
        "cap=2, rounds=2",
    ],
    "warnings_dont_block.json": ["core-claims-coverage: 1/1", "cap=2, rounds=2"],
}


def _run_converge(fixture_path):
    r = subprocess.run(
        [sys.executable, CONVERGE, "build-record", "--input", fixture_path],
        capture_output=True,
        text=True,
    )
    return r


def _validate_record(record):
    if not HAVE_JSONSCHEMA:
        return "SKIP (jsonschema absent — rule 3: declared, not faked)"
    import jsonschema  # local import — provably bound at the use site (Pyright)

    schema = json.load(open(RECORD_SCHEMA))
    jsonschema.validate(record, schema)  # raises on invalid
    return "VALID"


def check_fixture(name, exp_conv, exp_stale, exp_rounds):
    fixture = os.path.join(HERE, name)
    r = _run_converge(fixture)
    assert r.returncode == 0, f"{name}: exit {r.returncode}; stderr={r.stderr}"
    rec = json.loads(r.stdout)

    # 1. schema-valid (the output contract).
    validity = _validate_record(rec)

    # 2. rightness constant (outcome-axis isolation — never changes).
    assert rec.get("rightness") == "human_confirm_required", (
        f"{name}: rightness={rec.get('rightness')!r} (must be constant)"
    )

    # 3. substantive_converged + stalemate.
    assert rec["substantive_converged"] == exp_conv, (
        f"{name}: substantive_converged={rec['substantive_converged']} (expected {exp_conv})"
    )
    assert rec["stalemate"] == exp_stale, (
        f"{name}: stalemate={rec['stalemate']} (expected {exp_stale})"
    )

    # 4. per-round verdict + new-blocker count.
    assert len(rec["rounds"]) == len(exp_rounds), (
        f"{name}: rounds count {len(rec['rounds'])} != {len(exp_rounds)}"
    )
    for rd, (exp_no, exp_verdict, exp_blockers) in zip(rec["rounds"], exp_rounds):
        assert rd["round"] == exp_no, f"{name}: round# {rd['round']} != {exp_no}"
        assert rd["verdict"] == exp_verdict, (
            f"{name} round {exp_no}: verdict={rd['verdict']!r} (expected {exp_verdict!r})"
        )
        assert rd["blockers"] == exp_blockers, (
            f"{name} round {exp_no}: blockers={rd['blockers']} (expected {exp_blockers})"
        )

    # 5. per-fixture findings-count + degraded-flag invariants.
    for rd, (exp_no, exp_same, exp_het, exp_deg) in zip(
        rec["rounds"], COUNT_INVARIANTS[name]
    ):
        assert rd["same_source_findings"] == exp_same, (
            f"{name} round {exp_no}: same_source_findings="
            f"{rd['same_source_findings']} (expected {exp_same})"
        )
        assert rd["hetero_findings"] == exp_het, (
            f"{name} round {exp_no}: hetero_findings={rd['hetero_findings']} "
            f"(expected {exp_het})"
        )
        assert rd["hetero_degraded"] == exp_deg, (
            f"{name} round {exp_no}: hetero_degraded={rd['hetero_degraded']} "
            f"(expected {exp_deg})"
        )

    # 6. coverage notes (rule 3 — honest, never silent).
    for substr in COVERAGE_CONTAINS[name]:
        assert any(substr in note for note in rec["coverage"]), (
            f"{name}: coverage missing '{substr}': {rec['coverage']}"
        )

    print(
        f"  {name}: substantive_converged={rec['substantive_converged']}, "
        f"stalemate={rec['stalemate']} | record {validity}: PASS"
    )


def check_malformed_finding_rejected():
    """Pluggable seam: a finding missing required `evidence` is REJECTED with a clear
    error (rule 3 — never silently accept malformed input)."""
    run = {
        "artifact": "doc.md",
        "authority_ref": "",
        "size_tier": "short",
        "core_claims": [],
        "rounds": [
            {
                "same_findings": [
                    {
                        "defect_id": "bad",
                        "severity": "blocker",
                        "kind": "contradiction",
                        "location": "s1",
                        # evidence MISSING — schema requires it (minLength 1)
                    }
                ],
                "hetero_findings": [],
                "hetero_degraded": False,
                "core_claims_covered": [],
            }
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(run, fh)
        tmp = fh.name
    try:
        r = _run_converge(tmp)
    finally:
        os.unlink(tmp)
    assert r.returncode != 0, (
        "malformed finding was silently accepted (rule 3 violation)"
    )
    combined = r.stdout + r.stderr
    assert "malformed finding" in combined and "evidence" in combined, (
        f"malformation error not surfaced clearly: {combined}"
    )
    print("  malformed-finding rejected (exit!=0, names evidence): PASS")


def main():
    print("converge.py offline verification (CSR-I4 DoD):")
    failures = []
    for name, exp_conv, exp_stale, exp_rounds in CASES:
        try:
            check_fixture(name, exp_conv, exp_stale, exp_rounds)
        except AssertionError as e:
            failures.append(f"{name}: {e}")
            print(f"  {name}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{name}: error — {e}")
            print(f"  {name}: ERROR — {e}")
    try:
        check_malformed_finding_rejected()
    except AssertionError as e:
        failures.append(f"malformed: {e}")
        print(f"  malformed-finding: FAIL — {e}")
    except Exception as e:  # noqa: BLE001
        failures.append(f"malformed: error — {e}")
        print(f"  malformed-finding: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nconverge.py: 5 fixtures pass + schema-valid + malformed rejected "
        "(CSR-I4 BOTH prongs + pluggable seam demonstrated)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
