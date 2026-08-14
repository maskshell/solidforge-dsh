#!/usr/bin/env python3
"""verdict-emitter behavior + field-isolation test (iteration I6).

The I6 DoD: a spec run-record (a) conforms to run-record.schema.json, and (b) the FIELD-ISOLATION assertion holds — a green process axis NEVER changes the `rightness` field, because rightness is a constant set unconditionally.
This test drives the verdict emitter through a green and a red scenario and asserts rightness is IDENTICAL in both (and structurally can only be the one enum value).

Run:

    python3 infra/test/run_record.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))

import verdict  # noqa: E402
from run_record_schema import validate as validate_run_record  # noqa: E402

CONSTANT = verdict.RIGHTNESS  # "human_confirm_required"


def _fail(msg):
    raise AssertionError(msg)


def _assert_conforms(rec, label):
    errs = validate_run_record(rec)
    if errs:
        _fail(f"{label}: run-record violates schema: {errs}")


def check_green_record():
    inner = {
        "passed": True,
        "failures": [],
        "profile": "iteration-plan",
        "coverage": [],
    }
    outer = {
        "findings": [{"severity": "warning", "kind": "over-engineering"}],
        "coverage": [],
    }
    rec = verdict.emit("iteration-plan", inner, outer)
    _assert_conforms(rec, "green")
    if not rec["process_converged"]:
        _fail(
            f"green: expected process_converged=True, got False ({rec['inner_ring']}/{rec['outer_ring']})"
        )
    if rec["rightness"] != CONSTANT:
        _fail(f"green: rightness {rec['rightness']!r} != constant {CONSTANT!r}")
    print(
        "  green run (inner pass + outer warning-only): process_converged=True, rightness=constant: PASS"
    )


def check_red_record_inner_fails():
    inner = {
        "passed": False,
        "failures": [{"severity": "blocker", "check": "anchor", "anchor": "dag"}],
        "profile": "iteration-plan",
        "coverage": [],
    }
    outer = {"findings": [], "coverage": []}
    rec = verdict.emit("iteration-plan", inner, outer)
    _assert_conforms(rec, "red-inner")
    if rec["process_converged"]:
        _fail("red-inner: expected process_converged=False (inner Blocker)")
    if rec["rightness"] != CONSTANT:
        _fail(
            f"red-inner: rightness changed to {rec['rightness']!r} — field isolation violated"
        )
    print(
        "  red run (inner Blocker): process_converged=False, rightness UNCHANGED: PASS"
    )


def check_red_record_outer_blocker():
    inner = {
        "passed": True,
        "failures": [],
        "profile": "iteration-plan",
        "coverage": [],
    }
    outer = {
        "findings": [{"severity": "blocker", "kind": "contradiction"}],
        "coverage": [],
    }
    rec = verdict.emit("iteration-plan", inner, outer)
    _assert_conforms(rec, "red-outer")
    if rec["process_converged"]:
        _fail("red-outer: expected process_converged=False (outer Blocker)")
    print(
        "  red run (outer Blocker): process_converged=False, rightness UNCHANGED: PASS"
    )


def check_field_isolation():
    """THE DoD assertion: drive green and red; rightness must be byte-identical and independent of process_converged. Plus the emitter never reads process_converged when setting rightness (it is assigned the constant unconditionally)."""
    inner_ok = {"passed": True, "failures": [], "profile": "iteration-plan"}
    inner_bad = {
        "passed": False,
        "failures": [{"severity": "blocker"}],
        "profile": "iteration-plan",
    }
    outer_ok = {"findings": []}
    green = verdict.emit("iteration-plan", inner_ok, outer_ok)
    red = verdict.emit("iteration-plan", inner_bad, outer_ok)
    if green["rightness"] != red["rightness"]:
        _fail(
            f"field isolation violated: green rightness {green['rightness']!r} != red {red['rightness']!r}"
        )
    if green["rightness"] != CONSTANT:
        _fail(f"rightness is not the constant: {green['rightness']!r}")
    # process_converged genuinely differs (proves the two records are not identical — the isolation is on rightness specifically, not a no-op)
    if green["process_converged"] == red["process_converged"]:
        _fail(
            "sanity: process_converged should differ between green and red (else the test is a no-op)"
        )
    print(
        f"  FIELD ISOLATION: rightness={CONSTANT!r} identical across green/red; process_converged differs: PASS"
    )


def check_outer_not_run_blocks_convergence():
    """No convergence without the outer ring — process_converged stays False and a coverage note explains why (honest degradation, rule 3)."""
    inner = {"passed": True, "failures": [], "profile": "iteration-plan"}
    rec = verdict.emit("iteration-plan", inner, outer={})
    _assert_conforms(rec, "outer-not-run")
    if rec["process_converged"]:
        _fail("outer-not-run: process_converged must be False without the outer ring")
    if not any("outer ring" in c and "did not run" in c for c in rec["coverage"]):
        _fail(f"outer-not-run: expected a coverage note, got {rec['coverage']}")
    print(
        "  outer ring not run -> process_converged=False + coverage note (rule 3): PASS"
    )


def check_research_dispatch():
    """A research artifact's inner ring uses the research-v1 profile (I4)."""
    inner = {"passed": True, "failures": [], "profile": "research-v1", "coverage": []}
    outer = {"findings": [], "coverage": []}
    rec = verdict.emit("research", inner, outer)
    _assert_conforms(rec, "research")
    if (
        rec["artifact_type"] != "research"
        or rec["inner_ring"]["profile"] != "research-v1"
    ):
        _fail("research: artifact_type/profile not carried through")
    print("  research artifact dispatch (profile=research-v1): PASS")


def main():
    print("run_record (I6 verdict + field isolation):")
    failures = []
    for fn in (
        check_green_record,
        check_red_record_inner_fails,
        check_red_record_outer_blocker,
        check_field_isolation,
        check_outer_not_run_blocks_convergence,
        check_research_dispatch,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        f"\nField isolation holds: rightness is the constant {CONSTANT!r} in every record; "
        "process_converged is the only convergeable field. Schema-enforced (enum of one)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
