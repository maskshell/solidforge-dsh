#!/usr/bin/env python3
"""converge.py — deterministic convergence-policy engine for cross-source-review (CSR-I4).

PURE POLICY ENGINE — NO LLM CALLS. The orchestrator runs the legs (the same-family doc-reviewer
agent + the different-family hetero_doc_review.py substrate) and feeds each round's findings to this
engine, which reconciles + judges substantive-convergence + emits the convergence-record.

Authority chain: docs/proposal.md §3 (convergence POLICY + per-round reconciliation table +
pluggable seams), §9 Q3 (convergence-record schema); docs/iteration-plan.md §CSR-I4 (Goal /
Deliverables / Done-when — BOTH prongs + pluggable seam); infra/schemas/
convergence-record.schema.json (the output contract — must emit a schema-valid record);
infra/schemas/doc-findings.schema.json (each leg's finding shape).

Self-contained (workspace rule 7): pure stdlib + jsonschema (when available) for
validation. No imports from pd's loop_state or any shared lib (proposal Q3 — the doc
domain does NOT drive pd's loop_state state machine; field NAMES are aligned for
Phase-B map-ability only).

Graceful-skip (workspace rules 1 + 3 — tests skip when external tools absent; never
fake a green gate): when jsonschema is NOT importable, the pluggable-seam
findings-schema validation + the convergence-record schema validation are SKIPPED
with an honest coverage note in the emitted record; the CORE reconciliation +
substantive-convergence judgment (which do NOT need jsonschema) still run. This
mirrors the HAVE_JSONSCHEMA pattern in converge_fixtures/verify.py and the
token-skip in dogfood.py. Install jsonschema (or run under
`uv run --with jsonschema ...`) for full pluggable-seam + record validation.

==============================================================================
POLICY (proposal §3, implemented EXACTLY):
  Per-round reconciliation (the §3 table):
    - combined findings = same_findings + (hetero_findings if NOT hetero_degraded else [])
      — when different-family DEGRADED, the leg contributed nothing; the same-family primary stands
      (degraded flag persisted for the coverage trail).
    - a finding is a BLOCKER iff severity == "blocker".
    - new_blockers = blockers whose defect_id did NOT appear in any PRIOR round's blocker
      set (de-dup by defect_id across the whole run).
    - round.blockers = count of new_blockers this round.
    - round.verdict = "rewrite" if new_blockers else "pass".
      (The schema's third verdict — "adversarial-stalemate" — is reserved for the
      orchestrator layer, which makes the persistent-disagreement semantic call across
      rounds; a pure policy engine cannot derive it from one round's findings alone.)
  Run-level substantive-convergence (BOTH prongs):
    - prong_b (no-new-Blocker): the last >=2 rounds each had 0 new_blockers
      (and at least 2 rounds exist).
    - prong_a (core-claims-coverage): every entry in core_claims appears in the union of
      core_claims_covered across all rounds. Empty core_claims → prong_a vacuously true
      (the doc declared no explicit core-claim set — declared honestly in coverage).
    - substantive_converged = prong_a AND prong_b.
    - stalemate = (NOT substantive_converged) AND (len(rounds) >= cap)
      — cap-hit escalates to the human, never silent-pick (pd ADR #40 (e)).
    - rightness = "human_confirm_required" (constant — outcome-axis isolation; a green
      process axis NEVER changes this constant — the skill does not judge whether the
      doc is right).
    - coverage = honest notes (rule 3 — never silent):
        * per degraded round: "round N different-family degraded[: <subtype>]"
        * "core-claims-coverage: <covered>/<total>" when core_claims non-empty
        * "cap=<cap>, rounds=<n>" always

PLUGGABLE SEAM (proposal §3 — cheap thing Phase A MUST get right):
  --findings-schema validates EACH input finding against the given schema's $defs/finding
  subshape (default doc-findings.schema.json). A future code-shaped caller passes a schema
  whose $defs/finding is the violation-log shape. A finding that fails validation is
  REJECTED with a clear error (rule 3 — never silently accept malformed input; the CSR-I5
  findings shape-contract gate builds on this).
==============================================================================

Exit codes: 0 = clean record emitted (pass OR rewrite-due-to-blocker — the engine
succeeded); 1 = policy/contract violation (malformed finding, invalid run shape,
record failed schema validation); 2 = argument/IO error.
"""

import argparse
import importlib.util
import json
import os
import sys

SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")
DEFAULT_FINDINGS_SCHEMA = os.path.join(SCHEMAS_DIR, "doc-findings.schema.json")
CONVERGENCE_RECORD_SCHEMA = os.path.join(SCHEMAS_DIR, "convergence-record.schema.json")

# Caps by artifact size (proposal §3; pd ADR #40 (d) for the short default; the long-doc
# cap=5–7 is doc-specific, measured in hetero-long-doc-review-convergence).
CAP_DEFAULT_SHORT = 2
CAP_DEFAULT_LONG = 7

RIGHTNESS = "human_confirm_required"

# jsonschema availability flag WITHOUT a top-level jsonschema import that would crash
# under bare python3 (workspace rule 1: tests skip when external tools absent; rule 3:
# never fake a green gate). The actual import is local to build_record (provably bound
# at the use site — Pyright-friendly). Mirrors converge_fixtures/verify.py.
HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None

# Coverage note emitted when the pluggable-seam schema-validation is skipped because
# jsonschema is absent (rule 1 + rule 3 — declared in the record, never faked).
SKIP_FINDINGS_VALIDATION_NOTE = (
    "findings-schema validation skipped: jsonschema absent "
    "(rule 1 — install jsonschema for full pluggable-seam validation)"
)


class ConvergeError(Exception):
    """Raised when the engine cannot produce an honest record (malformed finding,
    invalid run shape). The caller surfaces the message verbatim — never silent (rule 3)."""


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_finding_schema(schema_obj):
    """Extract the per-finding subschema from a findings schema.

    The default doc-findings.schema.json is a WRAPPER
    ({outcome_axis_respected, findings: [...]}) whose $defs/finding is the individual
    finding shape. We validate each input finding against $defs/finding. A future
    code-shaped caller passes a schema whose $defs/finding is the violation-log shape
    (proposal §3 pluggable seam). Falls back to the root schema if no $defs/finding
    (so a caller passing a bare finding-schema also works).
    """
    defs = schema_obj.get("$defs") or schema_obj.get("definitions") or {}
    if "finding" in defs:
        return defs["finding"]
    return schema_obj


def _format_validation_error(err):
    """Render a jsonschema ValidationError as a concise readable message."""
    loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{loc}: {err.message}"


def _validate_findings(findings, finding_schema, validator_cls):
    """Validate each input finding against the per-finding schema. Returns a list of
    error messages (empty if all valid). A finding that fails validation is REJECTED —
    the caller surfaces a clear error (rule 3 — never silently accept malformed input).

    Validates BOTH legs' findings uniformly, including a degraded leg's findings: the
    degraded flag means hetero CONTRIBUTED NOTHING to reconciliation, but if findings
    are present they must still be schema-valid (a degraded round returning garbage is
    still a contract violation worth surfacing, not masking).
    """
    validator = validator_cls(finding_schema)
    errors = []
    for i, f in enumerate(findings):
        errs = sorted(validator.iter_errors(f), key=lambda e: list(e.absolute_path))
        if errs:
            msg = "; ".join(_format_validation_error(e) for e in errs)
            errors.append(f"finding[{i}] ({f.get('defect_id', '?')}): {msg}")
    return errors


def _blocker_ids(findings):
    """Return the set of defect_ids of blocker-severity findings."""
    return {f.get("defect_id") for f in findings if f.get("severity") == "blocker"}


def _resolve_cap(run):
    """Resolve the cap: explicit run.cap override > tier default (short=2, long=7)."""
    cap = run.get("cap")
    if isinstance(cap, int) and cap >= 0:
        return cap
    tier = run.get("size_tier", "short")
    return CAP_DEFAULT_LONG if tier == "long" else CAP_DEFAULT_SHORT


def _combined_findings(round_obj):
    """Per-round reconciliation (proposal §3 table): combined = same_findings +
    (hetero_findings if NOT hetero_degraded else []). When different-family DEGRADED, the different-family leg
    contributed nothing; the same-family primary stands (degraded flag persisted)."""
    combined = list(round_obj.get("same_findings") or [])
    if not round_obj.get("hetero_degraded"):
        combined.extend(round_obj.get("hetero_findings") or [])
    return combined


_SEVERITY_RANK = {"blocker": 3, "warning": 2, "coverage": 1}


def _dedup_findings(findings):
    """De-dup the record's embedded findings by defect_id (fix A mechanism:
    'reconciled findings array (same-family + hetero, de-duplicated)').

    Keeps the highest-severity copy (blocker > warning > coverage); on a tie
    the first copy wins — same-family precedes hetero in the combined list, so
    the primary leg's wording is kept. The leg COUNT fields
    (same_source_findings / hetero_findings) stay raw; only the embedded array
    is de-duplicated. Dispositions are keyed by defect_id, so 1:1 holds
    against the de-duplicated set.
    """

    def _rank(f):
        return _SEVERITY_RANK.get(f.get("severity"), 0)

    best = {}
    for f in findings:
        did = f.get("defect_id")
        if did is None:
            continue  # shape-validated elsewhere (jsonschema path)
        if did not in best or _rank(f) > _rank(best[did]):
            best[did] = f
    return list(best.values())


def _structural_finding_check(findings, round_no):
    """Stdlib-only malformed-input pre-check (rule 3 — never silently accept a
    malformed finding even when the jsonschema gate is absent): every finding
    must carry the doc-findings core fields with sane types."""
    kinds = {
        "contradiction",
        "authority-chain-break",
        "scope-creep",
        "structural-gap",
        "citation-error",
        "coverage-gap",
    }
    severities = {"blocker", "warning", "coverage"}
    for f in findings:
        did = f.get("defect_id") if isinstance(f, dict) else None
        if not isinstance(did, str) or not did:
            raise ConvergeError(
                f"round {round_no}: malformed finding — missing string defect_id"
            )
        if f.get("severity") not in severities:
            raise ConvergeError(
                f"round {round_no}: malformed finding {did} — severity must be "
                "blocker/warning/coverage"
            )
        if f.get("kind") not in kinds:
            raise ConvergeError(
                f"round {round_no}: malformed finding {did} — kind must be a "
                "doc-findings kind"
            )
        if not isinstance(f.get("location"), str):
            raise ConvergeError(
                f"round {round_no}: malformed finding {did} — location must be a string"
            )
        if not isinstance(f.get("evidence"), str) or not f["evidence"]:
            raise ConvergeError(
                f"round {round_no}: malformed finding {did} — evidence must be a "
                "non-empty string"
            )


def _validate_dispositions(findings, dispositions, round_no):
    """RETENTION FIX (record-auditability) — the 1:1 disposition-coverage invariant.

    Every finding in the round's combined set must have EXACTLY ONE disposition
    with a non-empty rationale, and every disposition must name a finding in the
    set. A partial dispositions array would re-create the untraceability hole in
    softened form (findings listed, 'what was done about it' missing) — reject
    (rule 3 — never silent). Pure python; no jsonschema needed.
    """
    by_id = {}
    for d in dispositions:
        if not isinstance(d, dict):
            raise ConvergeError(f"round {round_no}: disposition must be an object")
        did = d.get("defect_id")
        if not isinstance(did, str) or not did:
            raise ConvergeError(f"round {round_no}: disposition missing defect_id")
        if d.get("action") not in ("fixed", "rejected", "escalated"):
            raise ConvergeError(
                f"round {round_no}: disposition {did} action must be "
                "fixed/rejected/escalated"
            )
        note = d.get("note")
        if not isinstance(note, str) or not note.strip():
            raise ConvergeError(
                f"round {round_no}: disposition {did} missing rationale (note)"
            )
        if did in by_id:
            raise ConvergeError(f"round {round_no}: duplicate disposition {did}")
        by_id[did] = d
    finding_ids = [f.get("defect_id") for f in findings]
    missing = [did for did in finding_ids if did not in by_id]
    if missing:
        raise ConvergeError(
            f"round {round_no}: findings without disposition: {sorted(missing)}"
        )
    stray = [did for did in by_id if did not in set(finding_ids)]
    if stray:
        raise ConvergeError(
            f"round {round_no}: dispositions without a matching finding: "
            f"{sorted(stray)}"
        )


def _degraded_subtype(round_obj):
    """Best-effort extraction of a degrade subtype from a round, for the coverage note.
    The run.json shape carries hetero_degraded as a boolean; an optional subtype may
    attach as hetero_degraded_subtype / degraded_subtype / subtype. None → bare note."""
    for key in ("hetero_degraded_subtype", "degraded_subtype", "subtype"):
        val = round_obj.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _build_coverage_notes(degraded_rounds, core_claims, covered_union, cap, n_rounds):
    """Honest coverage notes (rule 3 — never silent). Lists degraded rounds, the
    core-claims coverage ratio (when core_claims non-empty), and the cap+rounds pair."""
    notes = []
    for round_no, subtype in degraded_rounds:
        if subtype:
            notes.append(f"round {round_no} different-family degraded: {subtype}")
        else:
            notes.append(f"round {round_no} different-family degraded")
    if core_claims:
        covered_count = sum(1 for c in core_claims if c in covered_union)
        notes.append(f"core-claims-coverage: {covered_count}/{len(core_claims)}")
    notes.append(f"cap={cap}, rounds={n_rounds}")
    return notes


def _reconcile_run(run, finding_schema, validator_cls):
    """Reconcile each round + judge substantive-convergence. Returns the record dict.

    Pure: no IO, no LLM. Throws ConvergeError on a contract violation (malformed finding,
    invalid run shape) so the caller surfaces it clearly (rule 3).

    validator_cls is None when jsonschema is absent — in that case the per-finding
    schema-validation is GRACEFUL-SKIPPED (rule 1 + rule 3) and an honest coverage
    note is appended to the record; the CORE reconciliation + substantive-convergence
    judgment still run (they do not need jsonschema).
    """
    if not isinstance(run, dict):
        raise ConvergeError("run must be a JSON object")
    rounds_in = run.get("rounds") or []
    if not isinstance(rounds_in, list) or not rounds_in:
        raise ConvergeError("run.rounds must be a non-empty array")

    prior_blocker_ids = set()  # accumulates blocker defect_ids across the run (de-dup)
    reconciled_rounds = []
    degraded_rounds = []  # (round_no, subtype_or_None) for the coverage notes

    for idx, r in enumerate(rounds_in):
        round_no = idx + 1
        if not isinstance(r, dict):
            raise ConvergeError(f"round {round_no} must be a JSON object")
        same_findings = list(r.get("same_findings") or [])
        hetero_findings = list(r.get("hetero_findings") or [])
        hetero_degraded = bool(r.get("hetero_degraded"))

        # Validate EACH input finding (both legs) — reject malformed (rule 3).
        # Graceful-skip when jsonschema absent (validator_cls is None): the coverage
        # note is appended once below; CORE reconciliation still runs (rule 1).
        all_input = same_findings + hetero_findings
        if validator_cls is not None:
            errors = _validate_findings(all_input, finding_schema, validator_cls)
            if errors:
                raise ConvergeError(
                    f"round {round_no}: malformed finding(s) rejected:\n  - "
                    + "\n  - ".join(errors)
                )

        combined = _combined_findings(r)
        # RETENTION FIX (record-auditability): the record now embeds the reconciled
        # findings (de-duplicated by defect_id) + per-finding dispositions so a
        # reader can re-judge severity and 'what was done about it'. The 1:1
        # coverage invariant is enforced here — a partial dispositions array is a
        # contract violation, never silent.
        record_findings = _dedup_findings(combined)
        _structural_finding_check(record_findings, round_no)
        dispositions = list(r.get("dispositions") or [])
        _validate_dispositions(record_findings, dispositions, round_no)
        round_blocker_ids = _blocker_ids(combined)
        new_blocker_ids = round_blocker_ids - prior_blocker_ids
        new_blockers_count = len(new_blocker_ids)
        # Update the prior set with THIS round's blockers (full set, for next round de-dup).
        prior_blocker_ids |= round_blocker_ids

        verdict = "rewrite" if new_blockers_count > 0 else "pass"
        # hetero_findings count in the record is 0 when degraded (the leg contributed
        # nothing) — proposal §3 "DEGRADED → adopt same-family primary (different-family contributed nothing)".
        hetero_count = 0 if hetero_degraded else len(hetero_findings)
        reconciled_rounds.append(
            {
                "round": round_no,
                "same_source_findings": len(same_findings),
                "hetero_findings": hetero_count,
                "hetero_degraded": hetero_degraded,
                "blockers": new_blockers_count,
                "verdict": verdict,
                "findings": record_findings,
                "dispositions": dispositions,
            }
        )
        if hetero_degraded:
            degraded_rounds.append((round_no, _degraded_subtype(r)))

    core_claims = list(run.get("core_claims") or [])
    covered_union = set()
    for r in rounds_in:
        for c in r.get("core_claims_covered") or []:
            covered_union.add(c)

    # prong_b (no-new-Blocker): the last >=2 rounds each had 0 new_blockers.
    if len(reconciled_rounds) >= 2:
        last_two = reconciled_rounds[-2:]
        prong_b = all(rr["blockers"] == 0 for rr in last_two)
    else:
        prong_b = False
    # prong_a (core-claims-coverage): every core_claim appears in the covered union.
    # Empty core_claims → vacuously true (declared in coverage either way).
    prong_a = all(c in covered_union for c in core_claims)

    substantive_converged = prong_a and prong_b
    cap = _resolve_cap(run)
    stalemate = (not substantive_converged) and len(reconciled_rounds) >= cap

    coverage = _build_coverage_notes(
        degraded_rounds, core_claims, covered_union, cap, len(reconciled_rounds)
    )
    # Honest coverage note when the pluggable-seam schema-validation was skipped
    # because jsonschema was absent (rule 1 + rule 3 — declared, never faked).
    if validator_cls is None:
        coverage.append(SKIP_FINDINGS_VALIDATION_NOTE)

    record = {
        "artifact": run.get("artifact", ""),
        "rounds": reconciled_rounds,
        "substantive_converged": substantive_converged,
        "coverage": coverage,
        "stalemate": stalemate,
        "rightness": RIGHTNESS,
        "cap": cap,
        "core_claims": core_claims,
    }
    # Optional fields — emit only when the run carries them (schema is
    # additionalProperties:false, but these are all schema-allowed optionals).
    if "authority_ref" in run:
        record["authority_ref"] = run.get("authority_ref", "")
    if "size_tier" in run:
        record["size_tier"] = run["size_tier"]
    return record


def _validate_record(record, record_schema_path, validator_cls):
    """Validate the emitted record against convergence-record.schema.json (rule 3 —
    the output contract is enforced, not hoped for). Returns None on success, or a list
    of error-message strings on failure. A missing schema file is a degrade (rule 3 —
    declared in stderr, not faked); the record is still emitted."""
    try:
        schema = _load_json(record_schema_path)
    except FileNotFoundError:
        print(
            f"warn: record schema not found at {record_schema_path}; "
            "skipping record validation (rule 3 — declared, not faked).",
            file=sys.stderr,
        )
        return None
    validator = validator_cls(schema)
    errs = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    if not errs:
        return None
    return [_format_validation_error(e) for e in errs]


def build_record(args):
    """Primary mode: read run.json, reconcile, emit a convergence-record."""
    try:
        run = _load_json(args.input)
    except FileNotFoundError:
        print(f"error: input run file not found: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(
            f"error: input run file is not valid JSON: {args.input}: {e}",
            file=sys.stderr,
        )
        return 2

    try:
        finding_schema_obj = _load_json(args.findings_schema)
    except FileNotFoundError:
        print(
            f"error: findings schema not found: {args.findings_schema}",
            file=sys.stderr,
        )
        return 2
    finding_schema = _resolve_finding_schema(finding_schema_obj)

    # Graceful-skip (rule 1 + rule 3): when jsonschema is absent, the pluggable-seam
    # findings-schema validation + the record schema-validation are SKIPPED with an
    # honest coverage note in the record (appended inside _reconcile_run); the CORE
    # reconciliation + substantive-convergence judgment still run. Install jsonschema
    # (or run under `uv run --with jsonschema ...`) for full validation. Mirrors
    # converge_fixtures/verify.py's HAVE_JSONSCHEMA pattern.
    validator_cls = None
    if HAVE_JSONSCHEMA:
        import jsonschema  # local import — provably bound at the use site

        validator_cls = jsonschema.Draft202012Validator
    else:
        print(
            "warn: jsonschema absent — findings-schema + record validation "
            "skipped (rule 1 — install jsonschema for full pluggable-seam "
            "validation); CORE reconciliation still runs.",
            file=sys.stderr,
        )

    try:
        record = _reconcile_run(run, finding_schema, validator_cls)
    except ConvergeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Validate the emitted record against the convergence-record schema (rule 3 — the
    # output contract is enforced, not just hoped for). Defaults to the standard schema
    # path; --record-schema override is a testability escape hatch. SKIPPED when
    # jsonschema is absent (validator_cls is None — declared in the record, not faked).
    if validator_cls is not None:
        errs = _validate_record(record, args.record_schema, validator_cls)
        if errs:
            print(
                "error: emitted record violates convergence-record schema:",
                file=sys.stderr,
            )
            for msg in errs:
                print(f"  - {msg}", file=sys.stderr)
            return 1

    out = json.dumps(record, ensure_ascii=False, indent=2)
    print(out)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(out + "\n")
        except OSError as e:
            print(f"error: cannot write --out: {args.out}: {e}", file=sys.stderr)
            return 2
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=(
            "cross-source-review deterministic convergence-policy engine (CSR-I4). "
            "PURE policy — no LLM calls. Reconciles per-round findings + judges "
            "substantive-convergence + emits a convergence-record."
        )
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    br = sub.add_parser(
        "build-record",
        help=(
            "Read a run.json, reconcile each round, judge substantive-convergence, "
            "emit a convergence-record JSON to stdout (and --out if given)."
        ),
    )
    br.add_argument("--input", required=True, help="Path to run.json.")
    br.add_argument(
        "--findings-schema",
        default=DEFAULT_FINDINGS_SCHEMA,
        help=(
            "Schema whose $defs/finding validates each input finding. Default: "
            "doc-findings.schema.json. A future code-shaped caller passes a schema "
            "whose $defs/finding is the violation-log shape (proposal §3 pluggable seam)."
        ),
    )
    br.add_argument(
        "--record-schema",
        default=CONVERGENCE_RECORD_SCHEMA,
        help=(
            "Schema to validate the emitted record against (default: "
            "convergence-record.schema.json). Testability escape hatch."
        ),
    )
    br.add_argument(
        "--out",
        default="",
        help="Optional path to write the record JSON in addition to stdout.",
    )
    br.set_defaults(func=build_record)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
