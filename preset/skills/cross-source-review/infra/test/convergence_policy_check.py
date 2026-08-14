#!/usr/bin/env python3
"""convergence_policy_check.py — offline convergence-policy gate (BLOCKER; rule 4).

Mirrors parallel-development's hetero_review_wiring.py (rule 7 — copy the helper,
do NOT import a shared lib): the offline convergence-policy contract over
converge.py. Runs converge.py build-record on the 5 fixtures in converge_fixtures/
and asserts substantive_converged/stalemate/per-round verdicts match expected.

OFFLINE + DETERMINISTIC (rule 4 — no real model call in the gate): exercises
converge.py's PURE policy engine with committed fixtures. The live same-family+different-family legs
are exercised by the dogfood gate (CSR-I6 does the full live run), NOT here.

Load-bearing prong (CSR-I4 DoD — BOTH prongs, not just no-new-Blocker):
  - core_claims_uncovered.json MUST yield substantive_converged=false — this proves
    the core-claims-coverage prong is real, not decorative. Without it a
    no-new-Blocker-only implementation would silently pass.

Also exercises the pluggable-seam malformation-rejection (a finding missing
`evidence` is rejected with a clear error) and validates every emitted record
against convergence-record.schema.json (jsonschema).

The CASES / COUNT_INVARANTS / COVERAGE_CONTAINS tables are DUPLICATED from
converge_fixtures/verify.py (rule 7 — duplicate, do NOT import the sibling). If
verify.py's tables change, update both.

Self-contained (rule 7): pure stdlib + jsonschema where available. Line-length
discipline: all lines <=88 so the file passes format --check under BOTH per-skill
(88) and repo-root (100) configs.

Usage:
    python3 infra/test/convergence_policy_check.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

GATE = "convergence-policy-check"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
SCRIPTS = os.path.join(ROOT, "infra", "scripts")
SCHEMAS = os.path.join(ROOT, "infra", "schemas")
CONVERGE = os.path.join(SCRIPTS, "converge.py")
FIXTURES = os.path.join(SCRIPTS, "converge_fixtures")
RECORD_SCHEMA = os.path.join(SCHEMAS, "convergence-record.schema.json")

HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None

# (fixture, expected_substantive_converged, expected_stalemate,
#  [(round, verdict, blockers), ...]) — DUPLICATED from verify.py (rule 7).
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


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _validate_record(record):
    """Validate record vs convergence-record.schema.json. Returns list of errs."""
    if not HAVE_JSONSCHEMA:
        return ["SKIP (jsonschema absent — rule 3: declared, not faked)"]
    import jsonschema  # local import — provably bound at the use site

    schema = _load_json(RECORD_SCHEMA)
    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    if not errs:
        return []
    out = []
    for e in errs:
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def _run_converge(fixture_path):
    """Run converge.py build-record --input <fixture>; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, CONVERGE, "build-record", "--input", fixture_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _finding(rule, detail, suggestion, severity="blocker"):
    return {
        "severity": severity,
        "rule": rule,
        "file": "infra/scripts/converge.py",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def run():
    coverage = [
        "convergence-policy-check (BLOCKER, rule 4 codifiable): offline policy "
        "contract over converge.py. 5 fixtures + malformed-rejection + "
        "schema-validity. Mirrors pd's hetero_review_wiring."
    ]
    findings = []

    # --- per-fixture: substantive_converged / stalemate / per-round verdict ---
    for name, exp_conv, exp_stale, exp_rounds in CASES:
        fx = os.path.join(FIXTURES, name)
        r = _run_converge(fx)
        if r.returncode != 0:
            findings.append(
                _finding(
                    "fixture-run",
                    f"{name}: converge.py exited {r.returncode}: "
                    f"{r.stderr.strip() or r.stdout.strip()}",
                    "fix converge.py or the fixture",
                )
            )
            coverage.append(f"  {name}: FAIL (exit {r.returncode})")
            continue
        rec = json.loads(r.stdout)

        # schema-validity (the output contract).
        errs = _validate_record(rec)
        if errs and errs[0].startswith("SKIP"):
            schema_note = errs[0]
            schema_ok = True
        elif errs:
            joined = "; ".join(errs)
            findings.append(
                _finding(
                    "record-schema",
                    f"{name}: convergence-record schema-violation: {joined}",
                    "fix converge.py to emit a schema-valid record",
                )
            )
            schema_note = "FAIL (schema-invalid)"
            schema_ok = False
        else:
            schema_note = "schema-ok"
            schema_ok = True

        # RETENTION FIX (record-auditability): every round must carry the embedded
        # findings + dispositions (the audit's counts-only hole is closed). A record
        # round missing either is a contract violation — never silent.
        for rd in rec["rounds"]:
            if "findings" not in rd or "dispositions" not in rd:
                findings.append(
                    _finding(
                        "retention-fix",
                        f"{name} round {rd['round']}: record round lacks "
                        "'findings'/'dispositions' (counts-only hole re-opened)",
                        "converge.py must emit the reconciled findings + "
                        "per-finding dispositions per round",
                    )
                )

        # rightness constant (outcome-axis isolation).
        if rec.get("rightness") != "human_confirm_required":
            findings.append(
                _finding(
                    "rightness-constant",
                    f"{name}: rightness={rec.get('rightness')!r} "
                    f"(must stay human_confirm_required)",
                    "rightness is a constant — a green process axis never "
                    "changes it (outcome-axis isolation)",
                )
            )

        # substantive_converged + stalemate.
        if rec["substantive_converged"] != exp_conv:
            findings.append(
                _finding(
                    "substantive-converged",
                    f"{name}: substantive_converged="
                    f"{rec['substantive_converged']} (expected {exp_conv})",
                    "fix the convergence-policy prong logic",
                )
            )
        if rec["stalemate"] != exp_stale:
            findings.append(
                _finding(
                    "stalemate",
                    f"{name}: stalemate={rec['stalemate']} (expected {exp_stale})",
                    "fix the cap-hit stalemate escalation",
                )
            )

        # per-round verdict + new-blocker count.
        if len(rec["rounds"]) != len(exp_rounds):
            findings.append(
                _finding(
                    "rounds-count",
                    f"{name}: {len(rec['rounds'])} rounds (expected {len(exp_rounds)})",
                    "check the fixture's rounds array",
                )
            )
        else:
            pairs = zip(rec["rounds"], exp_rounds, strict=False)
            for rd, (exp_no, exp_v, exp_b) in pairs:
                got = rd["blockers"]
                rb_detail = f"{name} round {exp_no}: blockers={got}, expected {exp_b}"
                if rd["round"] != exp_no:
                    findings.append(
                        _finding(
                            "round-number",
                            f"{name}: round#{rd['round']}!={exp_no}",
                            "rounds must be 1-indexed",
                        )
                    )
                if rd["verdict"] != exp_v:
                    findings.append(
                        _finding(
                            "round-verdict",
                            f"{name} round {exp_no}: verdict={rd['verdict']!r} "
                            f"(expected {exp_v!r})",
                            "fix the per-round reconciliation",
                        )
                    )
                if rd["blockers"] != exp_b:
                    findings.append(
                        _finding(
                            "round-blockers",
                            rb_detail,
                            "fix the new-blocker de-dup logic",
                        )
                    )

        coverage.append(
            f"  {name}: conv={rec['substantive_converged']}, "
            f"stalemate={rec['stalemate']} | {schema_note}"
        )
        # Suppress the unused-warning lint while keeping schema_ok meaningful for
        # future assertions (the schema-validity finding already records failures).
        _ = schema_ok

    # --- load-bearing prong: core_claims_uncovered MUST yield conv=false ---
    # (proves the coverage prong is real, not decorative — CSR-I4 DoD BOTH prongs).
    fx = os.path.join(FIXTURES, "core_claims_uncovered.json")
    r = _run_converge(fx)
    rec = json.loads(r.stdout) if r.returncode == 0 else {}
    if rec.get("substantive_converged") is False:
        coverage.append(
            "  LOAD-BEARING: core_claims_uncovered -> conv=false "
            "(coverage prong is real, not decorative): PASS"
        )
    else:
        findings.append(
            _finding(
                "core-claims-prong",
                "core_claims_uncovered.json did NOT yield conv=false "
                "(a no-new-Blocker-only impl would silently pass)",
                "the coverage prong must FAIL the run when a core_claim "
                "is uncovered, even with zero blockers",
            )
        )
        coverage.append("  LOAD-BEARING: core_claims prong: FAIL")

    # --- retention-fix: partial dispositions REJECTED (rule 3 — never silent) ---
    # A round whose findings lack a disposition would re-create the
    # untraceability hole in softened form; converge.py must reject it. Pure
    # python invariant — runs even without jsonschema.
    partial_run = {
        "artifact": "doc.md",
        "core_claims": [],
        "rounds": [
            {
                "same_findings": [
                    {
                        "defect_id": "f1",
                        "severity": "warning",
                        "kind": "citation-error",
                        "location": "s1",
                        "evidence": "advisory",
                    }
                ],
                "hetero_findings": [],
                "hetero_degraded": False,
                "core_claims_covered": [],
                "dispositions": [
                    # f1 has NO disposition — partial coverage
                ],
            }
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(partial_run, fh)
        tmp = fh.name
    try:
        r = _run_converge(tmp)
    finally:
        os.unlink(tmp)
    combined = r.stdout + r.stderr
    if r.returncode != 0 and "without disposition" in combined:
        coverage.append(
            "  retention-fix: partial dispositions rejected (names the finding): PASS"
        )
    else:
        snippet = combined[:160]
        findings.append(
            _finding(
                "retention-fix-partial-dispositions",
                f"partial dispositions not rejected: rc={r.returncode}, out={snippet}",
                "converge.py must reject a round whose findings lack a "
                "disposition (rule 3 — never silent)",
            )
        )
        coverage.append("  retention-fix: FAIL")

    # --- retention-fix: stray disposition REJECTED (rule 3 — never silent) ---
    # A disposition naming a defect_id absent from the round's findings is a
    # contract violation — reject, never silently drop.
    stray_run = {
        "artifact": "doc.md",
        "core_claims": [],
        "rounds": [
            {
                "same_findings": [
                    {
                        "defect_id": "f1",
                        "severity": "warning",
                        "kind": "citation-error",
                        "location": "s1",
                        "evidence": "advisory",
                    }
                ],
                "hetero_findings": [],
                "hetero_degraded": False,
                "core_claims_covered": [],
                "dispositions": [
                    {
                        "defect_id": "f1",
                        "action": "fixed",
                        "note": "accepted",
                    },
                    {
                        "defect_id": "ghost",
                        "action": "fixed",
                        "note": "no such finding",
                    },
                ],
            }
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(stray_run, fh)
        tmp = fh.name
    try:
        r = _run_converge(tmp)
    finally:
        os.unlink(tmp)
    combined = r.stdout + r.stderr
    if r.returncode != 0 and "without a matching finding" in combined:
        coverage.append(
            "  retention-fix: stray disposition rejected (names the defect_id): PASS"
        )
    else:
        snippet = combined[:160]
        findings.append(
            _finding(
                "retention-fix-stray-disposition",
                f"stray disposition not rejected: rc={r.returncode}, out={snippet}",
                "converge.py must reject a disposition naming a defect_id "
                "absent from the round's findings (rule 3 — never silent)",
            )
        )
        coverage.append("  retention-fix-stray: FAIL")

    # --- retention-fix: duplicate defect_ids across legs are DE-DUPLICATED ---
    # Both legs reporting the same defect_id must yield ONE record entry (the
    # fix-plan's '(same-family + hetero, de-duplicated)') with the highest
    # severity, and the disposition stays 1:1 against the de-duplicated set.
    dup_run = {
        "artifact": "doc.md",
        "core_claims": [],
        "rounds": [
            {
                "same_findings": [
                    {
                        "defect_id": "X",
                        "severity": "warning",
                        "kind": "citation-error",
                        "location": "s1",
                        "evidence": "same-family sees X as advisory",
                    }
                ],
                "hetero_findings": [
                    {
                        "defect_id": "X",
                        "severity": "blocker",
                        "kind": "contradiction",
                        "location": "s1",
                        "evidence": "hetero sees X as blocking",
                    }
                ],
                "hetero_degraded": False,
                "core_claims_covered": [],
                "dispositions": [
                    {
                        "defect_id": "X",
                        "action": "fixed",
                        "note": "accepted on the blocker reading",
                    }
                ],
            }
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(dup_run, fh)
        tmp = fh.name
    try:
        r = _run_converge(tmp)
    finally:
        os.unlink(tmp)
    dup_ok = False
    if r.returncode == 0:
        rec = json.loads(r.stdout)
        rd = rec["rounds"][0]
        dup_ok = (
            len(rd["findings"]) == 1
            and rd["findings"][0]["defect_id"] == "X"
            and rd["findings"][0]["severity"] == "blocker"
            and len(rd["dispositions"]) == 1
        )
    if dup_ok:
        coverage.append(
            "  retention-fix: duplicate defect_ids de-duplicated (keeps the "
            "blocker reading, 1:1 dispositions): PASS"
        )
    else:
        snippet = (r.stdout + r.stderr)[:160]
        findings.append(
            _finding(
                "retention-fix-dedup",
                f"duplicate defect_ids not de-duplicated: rc={r.returncode}, out={snippet}",
                "converge.py must emit ONE record entry per defect_id (the "
                "fix-plan's 'de-duplicated'), keeping the highest severity, "
                "with dispositions 1:1 against the de-duplicated set",
            )
        )
        coverage.append("  retention-fix-dedup: FAIL")

    # --- pluggable-seam: malformed finding REJECTED (rule 3 — never silent) ---
    # This prong depends on converge.py's jsonschema-based findings-schema
    # validation: graceful-skip when jsonschema is absent (rule 1 + rule 3 —
    # declared in coverage, never faked). The substantive-converged/stalemate/
    # per-round-verdict assertions above do NOT need jsonschema and ran already.
    if not HAVE_JSONSCHEMA:
        coverage.append(
            "  pluggable-seam: SKIP — jsonschema absent; converge.py cannot "
            "schema-validate findings (rule 1 — install jsonschema for full "
            "pluggable-seam validation)"
        )
    else:
        bad_run = {
            "artifact": "doc.md",
            "core_claims": [],
            "rounds": [
                {
                    "same_findings": [
                        {
                            "defect_id": "bad",
                            "severity": "blocker",
                            "kind": "contradiction",
                            "location": "s1",
                            # evidence MISSING — schema requires it
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
            json.dump(bad_run, fh)
            tmp = fh.name
        try:
            r = _run_converge(tmp)
        finally:
            os.unlink(tmp)
        combined = r.stdout + r.stderr
        if (
            r.returncode != 0
            and "malformed finding" in combined
            and "evidence" in combined
        ):
            coverage.append(
                "  pluggable-seam: malformed rejected (names evidence): PASS"
            )
        else:
            snippet = combined[:160]
            ps_detail = f"malformed not rejected: rc={r.returncode}, out={snippet}"
            findings.append(
                _finding(
                    "pluggable-seam",
                    ps_detail,
                    "converge.py must reject a schema-invalid finding with a "
                    "clear error naming the failing field (rule 3)",
                )
            )
            coverage.append("  pluggable-seam: FAIL")

    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4)."""
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
    findings, coverage = run()
    emit(findings, coverage)


if __name__ == "__main__":
    main()
