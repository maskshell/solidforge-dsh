#!/usr/bin/env python3
"""findings_shape_check.py — doc-findings shape-contract gate (BLOCKER; rule 4).

Mirrors parallel-development's adapter_shape_check.py (rule 7 — copy the helper,
do NOT import a shared lib): validate that every leg emit path produces a
doc-findings.schema.json-VALID object. Three prongs:

  1. hetero_doc_review.py --dry-run emits a doc-findings-valid object (the different-family
     leg's emit path, isolated-dynamically — invoke the wrapper, capture stdout,
     validate vs the schema).
  2. hetero_doc_review.py --dry-run-malform IS CAUGHT — the wrapper exits 1 and
     surfaces a non-empty malformation fingerprint. The gate confirms malformation
     HANDLING, not that the malformed output is valid (rule 3 — never mask a
     regression). Mirrors adapter_shape_check's "capture SystemExit" pattern.
  3. each fixture finding in converge_fixtures/ validates against the schema's
     $defs/finding subshape (the converge.py pluggable-seam contract).

Uses jsonschema (Draft 2020-12). Graceful-skip when jsonschema is absent (rule 1 +
rule 3 — declared in coverage, never faked): the schema-validation prongs skip with
a coverage note; the malformation-handling prong (pure exit-code + string check)
still runs — it does not need jsonschema.

Self-contained (rule 7): duplicates the schema-loader + validator; pure stdlib +
jsonschema where available. Line-length discipline: all lines <=88 so the file
passes format --check under BOTH per-skill (88) and repo-root (100) configs.

Usage:
    python3 infra/test/findings_shape_check.py
"""

import glob
import importlib.util
import json
import os
import subprocess
import sys

GATE = "findings-shape-check"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
SCRIPTS = os.path.join(ROOT, "infra", "scripts")
SCHEMAS = os.path.join(ROOT, "infra", "schemas")
HETERO = os.path.join(SCRIPTS, "hetero_doc_review.py")
FINDINGS_SCHEMA = os.path.join(SCHEMAS, "doc-findings.schema.json")
FIXTURES = os.path.join(SCRIPTS, "converge_fixtures")

# jsonschema availability WITHOUT a top-level import that ruff flags as unused
# (mirrors converge_fixtures/verify.py: find_spec sets the flag; the actual
# import is local to the use site). Graceful-skip when absent (rule 3).
HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _validate(instance, schema):
    """Validate instance vs schema. Returns list of error strings (empty=valid).

    Self-contained: constructs a Draft202012Validator directly. Caller guards
    HAVE_JSONSCHEMA; on absent, returns ["SKIP (jsonschema absent)"]."""
    if not HAVE_JSONSCHEMA:
        return ["SKIP (jsonschema absent — rule 3: declared, not faked)"]
    import jsonschema  # local import — provably bound at the use site

    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errs:
        return []
    return [_render_err(e) for e in errs]


def _render_err(e):
    """Render a jsonschema ValidationError as a concise path:message string."""
    loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
    return f"{loc}: {e.message}"


def _run_wrapper(args):
    """Invoke hetero_doc_review.py, return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, HETERO] + args,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _finding(rule, detail, suggestion, severity="blocker"):
    """Build a violation-log-shaped finding (mirrors adapter_shape_check)."""
    return {
        "severity": severity,
        "rule": rule,
        "file": "infra/scripts/hetero_doc_review.py",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def run():
    """Three prongs. Returns (findings, coverage)."""
    coverage = [
        "findings-shape-check (BLOCKER, rule 4 codifiable): the doc-findings "
        "shape contract. 3 prongs — different-family --dry-run emit, --dry-run-malform "
        "caught, fixture findings vs $defs/finding."
    ]
    findings = []

    schema = _load_json(FINDINGS_SCHEMA)
    defs = schema.get("$defs") or schema.get("definitions") or {}
    finding_subshape = defs.get("finding", schema)

    # --- prong 1: --dry-run emits a well-formed typed-return envelope whose
    # findings validate against $defs/finding. The wrapper's stdout is NOT a raw
    # doc-findings object — it is a typed RESULT envelope (verdict/findings_count/
    # findings/coverage/malformation/providers), like pd's hetero_review. The
    # doc-findings schema validates the INNER model return; the envelope CARRIES
    # the unpacked findings list. So the contract is: envelope well-formed AND
    # each findings[i] is $defs/finding-valid. Mirrors pd's
    # check_wrapper_returns_typed_findings (hetero_review_wiring.py).
    dry_args = ["--dry-run", "--artifact", "SKILL.md", "--profile", "qwen"]
    rc, out, err = _run_wrapper(dry_args)
    if rc != 0:
        findings.append(
            _finding(
                "dry-run-emit",
                f"--dry-run exited {rc} (expected 0): {err.strip() or out.strip()}",
                "the --dry-run path must emit a clean typed-return envelope",
            )
        )
        coverage.append("prong-1 dry-run emit: FAIL (non-zero exit)")
    else:
        try:
            env = json.loads(out)
        except json.JSONDecodeError as e:
            findings.append(
                _finding(
                    "dry-run-emit",
                    f"--dry-run stdout not JSON: {e}",
                    "emit valid JSON from the --dry-run path",
                )
            )
            env = None
            coverage.append("prong-1 dry-run emit: FAIL (non-JSON)")
        if env is not None:
            env_ok = True
            for key in ("verdict", "findings_count", "findings", "coverage"):
                if key not in env:
                    findings.append(
                        _finding(
                            "dry-run-emit",
                            f"typed-return envelope missing '{key}': {sorted(env)}",
                            f"add the '{key}' field to the wrapper result dict",
                        )
                    )
                    env_ok = False
            if env.get("verdict") not in ("pass", "rewrite", "adversarial-stalemate"):
                findings.append(
                    _finding(
                        "dry-run-emit",
                        f"bad verdict {env.get('verdict')!r}",
                        "verdict must be pass|rewrite|adversarial-stalemate",
                    )
                )
                env_ok = False
            schema_skipped = False
            flist = env.get("findings")
            if not isinstance(flist, list):
                findings.append(
                    _finding(
                        "dry-run-emit",
                        f"envelope.findings not a list: {type(flist).__name__}",
                        "emit findings as a list",
                    )
                )
                env_ok = False
            else:
                schema_skipped = False
                for i, f in enumerate(flist):
                    errs = _validate(f, finding_subshape)
                    if errs and errs[0].startswith("SKIP"):
                        schema_skipped = True
                    elif errs:
                        findings.append(
                            _finding(
                                "dry-run-emit",
                                f"envelope.findings[{i}] invalid: {'; '.join(errs)}",
                                "fix the canned finding to satisfy $defs/finding",
                            )
                        )
                        env_ok = False
            if env_ok:
                if schema_skipped:
                    coverage.append(
                        "prong-1 dry-run emit: envelope OK; findings-schema "
                        "SKIPPED (jsonschema absent — rule 3)"
                    )
                else:
                    coverage.append("prong-1 dry-run emit: VALID (envelope + findings)")

    # --- prong 2: --dry-run-malform IS CAUGHT (exit 1 + non-empty malformation) ---
    rc, out, err = _run_wrapper(
        [
            "--dry-run",
            "--dry-run-malform",
            "--artifact",
            "SKILL.md",
            "--profile",
            "qwen",
        ]
    )
    malform_caught = False
    malform_msg = ""
    if rc != 1:
        malform_msg = f"exited {rc} (expected 1 — malformation must surface)"
    else:
        try:
            obj = json.loads(out)
            fp = obj.get("malformation", "")
            if not fp:
                malform_msg = "exit 1 but 'malformation' field is empty"
            elif fp != "dry-run-malform":
                malform_msg = f"malformation={fp!r} (expected 'dry-run-malform')"
            else:
                malform_caught = True
        except json.JSONDecodeError as e:
            malform_msg = f"exit 1 but stdout not JSON: {e}"
    if not malform_caught:
        findings.append(
            _finding(
                "dry-run-malform-caught",
                f"malformation not surfaced honestly: {malform_msg}",
                "the wrapper must exit 1 + non-empty malformation on a "
                "substrate malformation (rule 3 — never mask)",
            )
        )
        coverage.append("prong-2 malform-caught: FAIL")
    else:
        coverage.append("prong-2 malform-caught: PASS (exit 1 + fingerprint)")

    # --- prong 3: each fixture finding validates against $defs/finding ---
    fixture_files = sorted(glob.glob(os.path.join(FIXTURES, "*.json")))
    coverage.append(f"prong-3 fixtures: {len(fixture_files)} file(s)")
    for fx in fixture_files:
        data = _load_json(fx)
        all_findings = []
        for rnd in data.get("rounds", []):
            all_findings.extend(rnd.get("same_findings") or [])
            all_findings.extend(rnd.get("hetero_findings") or [])
        rel = os.path.relpath(fx, ROOT)
        if not all_findings:
            coverage.append(f"  {rel}: 0 finding(s) (vacuously valid)")
            continue
        bad = 0
        skipped = False
        for i, f in enumerate(all_findings):
            errs = _validate(f, finding_subshape)
            if errs and errs[0].startswith("SKIP"):
                skipped = True
            elif errs:
                findings.append(
                    {
                        "severity": "blocker",
                        "rule": "fixture-finding-shape",
                        "file": rel,
                        "line": 0,
                        "detail": f"finding[{i}] invalid: {'; '.join(errs)}",
                        "suggestion": (
                            "fix the fixture finding to satisfy $defs/finding "
                            "(defect_id/severity/kind/location/evidence)"
                        ),
                    }
                )
                bad += 1
        if bad == 0:
            if skipped:
                coverage.append(
                    f"  {rel}: {len(all_findings)} finding(s) SKIP "
                    "(jsonschema absent — rule 3)"
                )
            else:
                coverage.append(f"  {rel}: {len(all_findings)} finding(s) VALID")

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
