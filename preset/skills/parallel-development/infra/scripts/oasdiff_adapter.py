#!/usr/bin/env python3
"""oasdiff_adapter.py — convergence-point adapter: oasdiff breaking-change → 越权日志.

A SIBLING convergence-point gate (like arch_contract_api.py / spectral_adapter.py /
semgrep_adapter.py), NOT a hand-rolled heuristic. It shells out to the ARMED oasdiff CLI
(armed globally via `brew install oasdiff`) and translates its JSON breaking-change
report into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See
references/external-skills.md.

COMPLEMENTARY to `spectral_adapter.py`, NOT a replacement — they check DIFFERENT axes:
  - `spectral_adapter.py` lints ONE spec's STYLE/RULESET (operation-ids, naming, security,
    parameter rules) against spectral:oas + .spectral.yaml. Static, single-spec.
  - `oasdiff_adapter.py` DIFFS two versions of a spec (working vs git HEAD) and reports
    BREAKING changes against existing clients (removed/required fields, narrowed types,
    changed enum, removed paths/operations, ...). Diffs a pair; needs a base.
Do not delete one for the other.

Base spec = git HEAD version of the tracked spec, materialized via `git show HEAD:<relpath>`
to a temp file. oasdiff is invoked per spec: `oasdiff breaking --format json <base> <working>`.
Exit code: 0 = no breaking changes, non-zero = breaking changes present (the JSON report is
emitted on stdout regardless with --format json; the adapter parses stdout independent of
exit). Each entry in the report carries a change id/type + description; the adapter maps
`id/type -> rule`, `description -> detail`, and synthesizes a `suggestion`.

This gate is ADVISORY: it never emits `blocker` (rule 4 — a breaking change may be intentional,
e.g. a major-version bump on a new minor release), so `passed` is always True; findings surface
for the run-record + outer ring. Never silently green: it always reports `coverage` (what ran
+ what was skipped).

GAPS (rule 3):
  - Only DIFFS specs TRACKED in git (the base is `HEAD:<relpath>`). A brand-new spec not yet in
    HEAD has no base to diff → SKIPPED with an explicit coverage note ("no base to diff (spec
    not in git HEAD) — skipped"). It is NOT silently green.
  - Breaking changes are ADVISORY, never `blocker` by default — a breaking change may be
    intentional (major-version bump, deprecation). Review at the outer ring if unsure.
  - Complements `spectral_adapter.py` (style) + `arch-contract-api` (presence/path) — does
    NOT replace either, and does NOT check that the implementation CODE matches the spec
    (that stays arch-contract-api path-check + outer-ring / contract tests).
  - When `git` is absent on PATH, ALL specs are skipped (no base can be materialized) and the
    gate no-ops with a coverage note.

Usage: oasdiff_adapter.py   (no args; walks $SOLIDFORGE_PROJECT_DIR or CWD)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when oasdiff is not
       armed, when no OpenAPI/Swagger artifact exists, or when no spec is tracked in git HEAD.
"""

import json
import os
import subprocess
import sys
import tempfile

GATE = "openapi-breaking"

_SPEC_NAMES = (
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "swagger.yml",
)
_MAX_FINDINGS = 50
_MAX_DEPTH = 4

_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "target",
    "build",
    "dist",
    "out",
    ".venv",
    "venv",
    "env",
    ".gradle",
    ".next",
    ".nuxt",
    ".turbo",
    ".nx",
    "__pycache__",
    "Pods",
    "DerivedData",
    ".build",
    "coverage",
    ".idea",
    ".vscode",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}


def emit(findings, coverage):
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


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def resolve_oasdiff():
    """The armed oasdiff CLI on PATH, or None when not armed."""
    if have("oasdiff"):
        return ["oasdiff"]
    return None


def find_spec_files(root):
    """Dirs (relative to root; '' == root) directly containing an OpenAPI/Swagger artifact."""
    want = set(_SPEC_NAMES)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            for n in filenames:
                if n in want:
                    found.append(os.path.join("" if rel == "." else rel, n))
    return found


def materialize_base(root, spec):
    """Run `git show HEAD:<relpath>` from root -> temp file. Returns (tmpfile, stderr_note).
    Returns (None, note) when git is absent OR the spec is not tracked in HEAD (untracked/new).
    The temp file is caller-managed (caller unlinks)."""
    if not have("git"):
        return None, "git not on PATH — base cannot be materialized"
    proc = subprocess.run(
        ["git", "-C", root, "show", f"HEAD:{spec}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        return (
            None,
            f"no base to diff (spec not in git HEAD) — skipped ({err[:120] or 'absent in HEAD'})",
        )
    fd, tmp = tempfile.mkstemp(prefix="oasdiff_base_", suffix=os.path.splitext(spec)[1])
    with os.fdopen(fd, "wb") as fh:
        fh.write(proc.stdout)
    return tmp, None


def _entry_id(entry):
    """oasdiff change id / type — varies by schema; prefer id, then type, then a stable label."""
    if not isinstance(entry, dict):
        return "breaking-change"
    return (
        entry.get("id") or entry.get("type") or entry.get("change") or "breaking-change"
    )


def _entry_description(entry):
    """Description text from an oasdiff change entry. Falls back to a JSON snippet if absent."""
    if not isinstance(entry, dict):
        return "breaking change detected by oasdiff"
    return (
        entry.get("description")
        or entry.get("msg")
        or entry.get("text")
        or json.dumps(entry, ensure_ascii=False)[:200]
    )


def _suggest(change_type):
    """Best-effort: map an oasdiff change type to a concrete remediation pointer."""
    ct = (change_type or "").lower()
    if "removed" in ct or "delete" in ct:
        return "Reintroduce the removed element, or stage a major-version bump + migration note."
    if "required" in ct or "added-required" in ct or "became-required" in ct:
        return "Make the field optional, or document it as a required input from a stated version."
    if "type" in ct or "narrowed" in ct:
        return "Widen the type back, or version the schema + migrate existing clients."
    if "enum" in ct:
        return "Restore the dropped enum value, or coordinate the breaking enum change downstream."
    if "response" in ct or "media-type" in ct:
        return "Keep the response shape/media-type stable, or version the API contract."
    return (
        "Review whether this breaking change is intentional (major-version bump?) — if so, "
        "note it in the changelog; otherwise restore backward compatibility."
    )


def translate(raw, root, spec):
    """oasdiff breaking-change report -> 越权日志 finding. severity COLLAPSES to warning.
    oasdiff emits either a list of change entries, or a dict keyed by change type ->
    [entries] (schema varies across versions); both are flattened here."""
    if isinstance(raw, dict):
        items = []
        for v in raw.values():
            if isinstance(v, list):
                items.extend(e for e in v if isinstance(e, dict))
            elif isinstance(v, dict):
                items.append(v)
    elif isinstance(raw, list):
        items = [e for e in raw if isinstance(e, dict)]
    else:
        items = []

    try:
        spec_rel = os.path.relpath(spec, root)
    except ValueError:
        spec_rel = spec

    out = []
    for entry in items[:_MAX_FINDINGS]:
        change_type = _entry_id(entry)
        description = _entry_description(entry)
        out.append(
            {
                "severity": "warning",  # COLLAPSED — schema enum is blocker|warning; advisory never blocker
                "rule": f"oasdiff:{change_type}",
                "file": spec_rel,
                "line": 0,  # oasdiff does not report line numbers; spec path identifies the change
                "detail": description,
                "suggestion": _suggest(change_type),
            }
        )
    return out


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "openapi-breaking (advisory, severity collapsed to warning): wraps the armed oasdiff "
        "CLI DIFFING each tracked OpenAPI/Swagger spec against its git HEAD version and reporting "
        "breaking changes against existing clients; complementary to spectral-openapi (style) "
        "and arch-contract-api (presence/path) — does NOT lint style or check code/spec match"
    ]

    oasdiff = resolve_oasdiff()
    if not oasdiff:
        coverage.append(
            "openapi-breaking: oasdiff not armed (`oasdiff` not on PATH) — run "
            "`brew install oasdiff`. Gate skipped (no-op)."
        )
        emit([], coverage)
        return

    specs = find_spec_files(root)
    if not specs:
        coverage.append(
            "openapi-breaking: no OpenAPI/Swagger artifact (openapi.{json,yaml,yml} / "
            "swagger.*) found — spec-gate skipped (not an API-contract project)."
        )
        emit([], coverage)
        return

    if not have("git"):
        coverage.append(
            "openapi-breaking: git not on PATH — no base can be materialized for any spec; "
            f"all {len(specs)} spec(s) skipped."
        )
        emit([], coverage)
        return

    findings = []
    diffed = 0
    skipped_untracked = 0
    for spec in specs:
        base_tmp, err = materialize_base(root, spec)
        if base_tmp is None:
            skipped_untracked += 1
            coverage.append(f"openapi-breaking: {spec}: {err}")
            continue
        try:
            working_abs = os.path.join(root, spec)
            proc = subprocess.run(
                [*oasdiff, "breaking", "--format", "json", base_tmp, working_abs],
                capture_output=True,
                text=True,
            )
            # oasdiff: exit 0 = no breaking changes, non-zero = breaking changes present.
            # JSON is emitted on stdout regardless with --format json; parse independent of exit.
            try:
                raw = json.loads(proc.stdout) if proc.stdout.strip() else []
            except json.JSONDecodeError as e:
                coverage.append(
                    f"openapi-breaking: {spec}: oasdiff output unparseable ({e}); exit "
                    f"{proc.returncode} — {(proc.stderr or '').strip()[:200] or 'no stderr'}; "
                    "findings skipped for this spec."
                )
                continue
            mapped = translate(raw, root, spec)
            findings.extend(mapped)
            diffed += 1
            n_raw = (
                len(raw)
                if isinstance(raw, list)
                else sum(len(v) for v in raw.values() if isinstance(v, list))
            )
            coverage.append(
                f"openapi-breaking: {spec}: diffed HEAD -> working; oasdiff reported {n_raw} "
                f"breaking change(s) (exit {proc.returncode}); adapter emitted {len(mapped)} "
                "finding(s) (severity collapsed to warning)."
            )
        finally:
            try:
                os.unlink(base_tmp)
            except OSError:
                pass

    findings = findings[:_MAX_FINDINGS]
    coverage.append(
        f"openapi-breaking: armed ({oasdiff[0]}); diffed {diffed}/{len(specs)} spec(s) "
        f"against git HEAD; {skipped_untracked} skipped (untracked / not in HEAD); emitted "
        f"{len(findings)} finding(s) (capped at {_MAX_FINDINGS})."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
