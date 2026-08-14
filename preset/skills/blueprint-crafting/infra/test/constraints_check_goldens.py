#!/usr/bin/env python3
"""constraints-checker goldens self-check (iteration I3).

Asserts the I3 DoD (iteration-plan §4):
  - the 6 exemplar plan-models (non-research types) each PASS their profile;
  - a fixture with one anchor removed -> FAIL and the failure NAMES the missing anchor;
  - an authority-chain contradiction (dod_ref -> undeclared doc) -> FAIL.

Plus the registry/checker split (workspace rule 2): profiles live in constraints.json and the checker reads them — adding a profile must not require editing the checker. All fixtures are also schema-valid (plan-model.schema.json). Run:

    python3 infra/test/constraints_check_goldens.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))

import constraints_check  # noqa: E402
from plan_model_schema import validate as validate_plan_model  # noqa: E402

GOLDEN = os.path.join(HERE, "golden", "constraints")
EXEMPLARS = [f for f in os.listdir(GOLDEN) if f.startswith("exemplar-")]


def _load(name):
    with open(os.path.join(GOLDEN, name), encoding="utf-8") as fh:
        return json.load(fh)


def _fail(msg):
    raise AssertionError(msg)


def check_exemplars_pass():
    for name in EXEMPLARS:
        pm = _load(name)
        errs = validate_plan_model(pm)
        if errs:
            _fail(f"{name}: not schema-valid: {errs}")
        res = constraints_check.check(pm)
        if not res["passed"]:
            _fail(f"{name}: expected PASS, got failures {res['failures']}")
        if res["failures"] != []:
            _fail(f"{name}: expected no failures, got {res['failures']}")
    print(
        f"  {len(EXEMPLARS)} exemplars pass their profile (schema-valid + anchors + authority + odp): PASS"
    )


def check_missing_anchor_fails_and_named():
    pm = _load("negative-missing-anchor.json")
    res = constraints_check.check(pm)
    if res["passed"]:
        _fail("negative-missing-anchor: expected FAIL, got PASS")
    anchor_fails = [f for f in res["failures"] if f.get("check") == "anchor"]
    if not anchor_fails:
        _fail(
            f"negative-missing-anchor: expected an anchor failure, got {res['failures']}"
        )
    if not any(f.get("anchor") == "dag" for f in anchor_fails):
        _fail(
            f"negative-missing-anchor: failure must NAME the missing anchor 'dag', got {anchor_fails}"
        )
    print("  missing-anchor -> FAIL, names 'dag': PASS")


def check_authority_contradiction_fails():
    pm = _load("negative-authority-contradiction.json")
    res = constraints_check.check(pm)
    if res["passed"]:
        _fail("negative-authority-contradiction: expected FAIL, got PASS")
    auth_fails = [f for f in res["failures"] if f.get("check") == "authority"]
    if not auth_fails:
        _fail(
            f"negative-authority-contradiction: expected an authority failure, got {res['failures']}"
        )
    print("  authority contradiction (dod_ref -> undeclared doc) -> FAIL: PASS")


def check_registry_driven():
    """rule 2: profiles live in the registry; the checker reads it. The 4 non-research profiles are present, and the checker's behavior follows the registry (a profile not in the registry degrades to a coverage note, not a hardcoded rejection)."""
    reg = constraints_check.load_registry()
    profiles = reg["profiles"]
    expected = {"product-spec", "arch-design", "iteration-plan", "executable-summary"}
    if set(profiles) != expected:
        _fail(f"registry profiles {set(profiles)} != expected {expected}")
    # an unknown artifact_type degrades (coverage note), not a hardcoded crash/fail
    unknown = {
        "plan_model_version": "v1",
        "artifact_type": "mystery-type",
        "authority_chain": ["docs/x.md"],
        "items": [
            {"item_id": "x", "seq": 0, "depends_on": [], "dod_ref": "docs/x.md#x"}
        ],
    }
    res = constraints_check.check(unknown, registry=reg)
    if not res["passed"] or not res["coverage"]:
        _fail(f"unknown type should degrade (pass + coverage note), got {res}")
    print("  registry-driven (4 profiles; unknown type degrades to coverage): PASS")


def check_dogfood_self_docs():
    """rule 1 dogfood: blueprint-crafting's own iteration-plan plan-queue, lifted to a plan-model, passes the iteration-plan profile. (Anchors map must be supplied — the queue is item-rich but does not carry artifact anchors, so we assert the honest degradation: without an anchors map the checker emits a coverage note, not a fail, and authority/items are clean.)"""
    # synthesize a minimal iteration-plan plan-model without an anchors map
    pm = {
        "plan_model_version": "v1",
        "artifact_type": "iteration-plan",
        "authority_chain": ["docs/arch-design.md", "docs/iteration-plan.md"],
        "items": [
            {
                "item_id": "I2",
                "seq": 0,
                "depends_on": [],
                "dod_ref": "docs/iteration-plan.md#I2",
            }
        ],
    }
    res = constraints_check.check(pm)
    if not res["passed"]:
        _fail(f"dogfood: clean plan-model should pass, got {res['failures']}")
    if not any("anchors map absent" in c for c in res["coverage"]):
        _fail(f"dogfood: expected anchors-absent coverage note, got {res['coverage']}")
    print("  dogfood (own plan-model: clean + anchors-absent coverage note): PASS")


def check_real_docs_dogfood():
    """iteration-plan §10 dogfood: the skill's OWN docs, normalized, pass the checker. iteration-plan.md is item-structured -> full pipeline (normalize -> schema-valid -> checker passes, all anchors detected). arch-design.md is anchor-rich but not item-grain -> assert its anchors all extract (present), since the item-centric checker requires >=1 item an arch-design doc does not carry."""
    docs = os.path.normpath(os.path.join(HERE, "..", "..", "docs"))
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))
    import normalizer  # noqa: E402

    # iteration-plan.md: full pipeline
    with open(os.path.join(docs, "iteration-plan.md"), encoding="utf-8") as fh:
        pm = normalizer.normalize(fh.read())["plan_model"]
    if pm["artifact_type"] != "iteration-plan":
        _fail(f"dogfood iteration-plan.md: artifact_type={pm['artifact_type']!r}")
    errs = validate_plan_model(pm)
    if errs:
        _fail(f"dogfood iteration-plan.md: not schema-valid: {errs}")
    res = constraints_check.check(pm)
    if not res["passed"]:
        _fail(f"dogfood iteration-plan.md: checker failed: {res['failures']}")
    undetected = [c for c in res["coverage"] if "not detected" in c]
    if undetected:
        _fail(f"dogfood iteration-plan.md: anchors not detected: {undetected}")
    # arch-design.md: anchor extraction (not item-grain)
    with open(os.path.join(docs, "arch-design.md"), encoding="utf-8") as fh:
        arch_anchors = normalizer.extract_anchors(fh.read(), "arch-design")
    if arch_anchors is None:
        _fail("dogfood arch-design.md: no profile/anchors extracted")
    missing = [a for a, v in arch_anchors.items() if not v.get("present")]
    if missing:
        _fail(f"dogfood arch-design.md: anchors not detected: {missing}")
    print(
        "  dogfood: iteration-plan.md full-pipeline pass + arch-design.md anchors detected: PASS"
    )


def check_chinese_anchor_detection():
    """ADR #15 dogfood: the bilingual (English + Chinese) keyword registry detects
    anchors in Chinese-language source, so the inner ring's completeness check is not
    vacuous for Chinese artifacts (the gap ADR #15 closes). Exercises BOTH detection
    paths on Chinese text: a heading match -> latch (high-confidence), a prose-only
    match -> semantic-infer (low-confidence); and confirms an absent anchor is still
    honestly reported present=False (not vacuously all-True). Detection stays heuristic
    -> the source would be tagged normalizer-extracted, so a miss degrades to coverage
    (ADR #12, rule 4) — this test asserts DETECTION, not Blocker semantics."""
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))
    import normalizer  # noqa: E402

    snippet = """# 迭代计划

## 复杂度分级
工作项按 S/M/L/XL 四档划分复杂度。

## 风险与缓解
识别主要风险并给出缓解对策。

每个工作包都必须给出明确的完成标准（Definition of Done）。
工作项之间的依赖与并行关系构成一张依赖图（DAG），驱动并行展开。
"""
    anchors = normalizer.extract_anchors(snippet, "iteration-plan")
    if anchors is None:
        _fail("chinese detection: iteration-plan profile returned no anchors map")
    # heading match -> latch (high-confidence)
    for latch_anchor in ("complexity-tiers", "risks-mitigations"):
        e = anchors.get(latch_anchor, {})
        if not e.get("present") or e.get("ref") != "heading":
            _fail(
                f"chinese detection: '{latch_anchor}' must match a Chinese heading as "
                f"latch, got {e}"
            )
        if e.get("confidence") != normalizer.LATCH:
            _fail(
                f"chinese detection: '{latch_anchor}' heading must be {normalizer.LATCH}, "
                f"got {e.get('confidence')}"
            )
    # prose-only match -> semantic-infer (low-confidence)
    for prose_anchor in ("per-iteration-dod", "dag"):
        e = anchors.get(prose_anchor, {})
        if not e.get("present") or e.get("ref") != "prose":
            _fail(
                f"chinese detection: '{prose_anchor}' must match Chinese prose, got {e}"
            )
        if e.get("confidence") != normalizer.SEMANTIC_INFER:
            _fail(
                f"chinese detection: '{prose_anchor}' prose must be "
                f"{normalizer.SEMANTIC_INFER}, got {e.get('confidence')}"
            )
    # an anchor absent from the snippet is still honestly reported (not vacuously True)
    absent = [a for a, v in anchors.items() if not v.get("present")]
    if "out-of-scope" not in absent:
        _fail(
            f"chinese detection: 'out-of-scope' is absent from the snippet and must be "
            f"reported present=False; absent set was {absent}"
        )
    print(
        "  chinese anchor detection (heading latch + prose semantic-infer + honest absence): PASS"
    )


def main():
    print("constraints_check_goldens (I3):")
    failures = []
    for fn in (
        check_exemplars_pass,
        check_missing_anchor_fails_and_named,
        check_authority_contradiction_fails,
        check_registry_driven,
        check_dogfood_self_docs,
        check_real_docs_dogfood,
        check_chinese_anchor_detection,
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
        f"\n{len(EXEMPLARS)} exemplars pass; missing anchor + authority contradiction fail (named). "
        "Registry-driven (rule 2); deterministic over the model (ADR #2)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
