#!/usr/bin/env python3
"""normalizer goldens self-check (iteration I2).

The 3 source-format goldens live in infra/test/golden/normalizer/<format>/source*.
This check asserts the normalizer's GRADED EXTRACTION meets the I2 DoD on each:

  - all 3 format goldens have complete executable-subset fields (item_id/seq/ depends_on/dod_ref) and a schema-valid plan-model;
  - frontmatter todos[] -> tagged latch (high-confidence)  (cursor-plan);
  - prose dependency inference -> tagged semantic-infer (low-confidence)  (rich-md, work-package), and the inferred dep is merged into depends_on;
  - coverage discloses rule4_note (semantic-infer is advisory, never a Blocker) and the not_extracted fields (honest degradation — workspace rule 3).

Per rule 4, the normalizer NEVER emits a Blocker; it tags confidence. The constraints-checker (I3) is what Blocks. Run:

    python3 infra/test/normalizer_goldens.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # plan_model_schema
sys.path.insert(
    0, os.path.normpath(os.path.join(HERE, "..", "scripts"))
)  # normalizer, plan_model

import normalizer  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402

GOLDEN = os.path.join(HERE, "golden", "normalizer")
LATCH = normalizer.LATCH
SEMANTIC = normalizer.SEMANTIC_INFER


def _read(fmt):
    d = os.path.join(GOLDEN, fmt)
    src = [f for f in os.listdir(d) if f.startswith("source")][0]
    with open(os.path.join(d, src), encoding="utf-8") as fh:
        return fh.read()


def _exec_subset(items):
    return {
        it["item_id"]: (it["seq"], sorted(it["depends_on"]), it["dod_ref"])
        for it in items
    }


def _notes(coverage, field=None, confidence=None):
    return [
        n
        for n in coverage["extraction"]
        if (field is None or n["field"] == field)
        and (confidence is None or n["confidence"] == confidence)
    ]


def _fail(msg):
    raise AssertionError(msg)


def check_cursor_plan():
    out = normalizer.normalize(_read("cursor-plan"), format="cursor-plan")
    pm, cov = out["plan_model"], out["coverage"]
    errs = validate_plan_model(pm)
    if errs:
        _fail(f"cursor-plan: plan-model violates schema: {errs}")
    expected = {
        "c-1": (0, [], "spec#schema"),
        "c-2": (1, ["c-1"], "spec#validator"),
        "c-3": (2, ["c-2"], "spec#cli"),
    }
    if _exec_subset(pm["items"]) != expected:
        _fail(f"cursor-plan: executable subset mismatch -> {_exec_subset(pm['items'])}")
    # DoD: frontmatter todos[] -> ALL latch; no semantic-infer in this fixture
    if any(n["confidence"] != LATCH for n in cov["extraction"]):
        _fail("cursor-plan: expected all-latch, got non-latch notes")
    if not all("todos[]" in n["source"] for n in cov["extraction"]):
        _fail("cursor-plan: extraction source must be 'frontmatter todos[]'")
    if _notes(cov, confidence=SEMANTIC):
        _fail("cursor-plan: pure-latch fixture must have NO semantic-infer notes")
    print("  cursor-plan (todos[] -> latch, pure): PASS")


def check_rich_md():
    out = normalizer.normalize(_read("rich-md"), format="rich-md")
    pm, cov = out["plan_model"], out["coverage"]
    if validate_plan_model(pm):
        _fail(f"rich-md: plan-model violates schema: {validate_plan_model(pm)}")
    # r-3 carries the prose-inferred r-1 dep merged with the table's r-2
    expected = {
        "r-1": (0, [], "spec#r1"),
        "r-2": (1, ["r-1"], "spec#r2"),
        "r-3": (2, ["r-1", "r-2"], "spec#r3"),
    }
    if _exec_subset(pm["items"]) != expected:
        _fail(f"rich-md: executable subset mismatch -> {_exec_subset(pm['items'])}")
    sem = _notes(cov, field="depends_on", confidence=SEMANTIC)
    if len(sem) != 1 or sem[0]["item_id"] != "r-3":
        _fail(
            f"rich-md: expected exactly one semantic-infer depends_on note on r-3, got {sem}"
        )
    # complexity came from the table (latch upstream_only field)
    r3 = next(it for it in pm["items"] if it["item_id"] == "r-3")
    if r3.get("complexity") != "M":
        _fail(
            f"rich-md: r-3 complexity not extracted from table (got {r3.get('complexity')})"
        )
    print("  rich-md (table latch + prose dep semantic-infer): PASS")


def check_work_package():
    out = normalizer.normalize(_read("work-package"), format="work-package")
    pm, cov = out["plan_model"], out["coverage"]
    if validate_plan_model(pm):
        _fail(f"work-package: plan-model violates schema: {validate_plan_model(pm)}")
    expected = {
        "w-1": (0, [], "wp#w1"),
        "w-2": (1, ["w-1"], "wp#w2"),
        "w-3": (2, ["w-1", "w-2"], "wp#w3"),
    }
    if _exec_subset(pm["items"]) != expected:
        _fail(
            f"work-package: executable subset mismatch -> {_exec_subset(pm['items'])}"
        )
    sem = _notes(cov, field="depends_on", confidence=SEMANTIC)
    if len(sem) != 1 or sem[0]["item_id"] != "w-3":
        _fail(
            f"work-package: expected exactly one semantic-infer depends_on note on w-3, got {sem}"
        )
    print("  work-package (json latch + prose dep semantic-infer): PASS")


def check_coverage_honesty():
    """Every format's coverage carries the rule-4 note + discloses unextracted fields."""
    for fmt in ("cursor-plan", "rich-md", "work-package"):
        cov = normalizer.normalize(_read(fmt), format=fmt)["coverage"]
        if "rule4_note" not in cov or "advisory" not in cov["rule4_note"]:
            _fail(f"{fmt}: coverage missing rule4_note (semantic-infer advisory)")
        if "not_extracted" not in cov:
            _fail(f"{fmt}: coverage missing not_extracted disclosure (rule 3)")
        # the normalizer is NOT a checker: it documents extraction, never emits findings/severities. (A 'blocker' would come from the constraints-checker I3, not here.) Assert no severity vocabulary leaks into the normalizer output.
        if "severity" in cov or any("severity" in n for n in cov["extraction"]):
            _fail(
                f"{fmt}: normalizer coverage must not carry severity (it is advisory, not a checker)"
            )
    print("  coverage honesty (rule4_note + not_extracted, no blocker): PASS")


def check_format_autodetection():
    """detect_format identifies each golden without an explicit hint."""
    cases = {
        "cursor-plan": "cursor-plan",
        "rich-md": "rich-md",
        "work-package": "work-package",
    }
    for fmt, expected in cases.items():
        got = normalizer.detect_format(_read(fmt))
        if got != expected:
            _fail(f"detect_format({fmt}) -> {got}, expected {expected}")
    print("  format auto-detection: PASS")


def main():
    print("normalizer_goldens (I2):")
    failures = []
    for fn in (
        check_cursor_plan,
        check_rich_md,
        check_work_package,
        check_coverage_honesty,
        check_format_autodetection,
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
        "\n3 format goldens: complete fields, todos[]->latch, prose->semantic-infer, coverage honest. Heuristics advisory (rule 4), never Blocker."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
