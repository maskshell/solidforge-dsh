#!/usr/bin/env python3
"""license_adapter.py — convergence-point adapter: Trivy license scan → 越权日志.

A SIBLING convergence-point gate (like arch_contract_deps.py / semgrep_adapter.py /
spectral_adapter.py), NOT a hand-rolled heuristic. It shells out to the ARMED Trivy CLI
(armed globally via `brew install trivy`) and translates its license findings into the
loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See references/external-skills.md.

COMPLEMENTARY to `arch_contract_deps.py`, NOT a replacement:
  - `arch_contract_deps.py` covers leaked SECRETS (gitleaks) + dependency CVEs.
  - `license_adapter.py` covers dependency LICENSES (copyleft / permissive / unknown) via
    Trivy's license scanner. Different axis — a clean CVE record says nothing about whether
    the dependency's license is acceptable for this project.

Trivy's license scanner (`trivy fs --scanners license --format json`) emits `{Results[]}`, each
result having a `Licenses[]` of `{PkgName, Version, License[Name], Severity, Layer, Path}`. The
adapter walks `Results[]`, collects every license entry, and maps `License.Name -> rule`,
`PkgName -> file` (package-level, `line=0`), `License <name> on <pkg> -> detail`, and COLLAPSES
severity to `warning` (see GAP). If the shape differs from expected, the adapter coverage-notes
and skips (degrade safely — never silently green).

This is a DEPTH-1 advisory rule gate (no per-feature frozen anchor — license policy is repo-wide
config, unlike Spectral's frozen spec).

ADVISORY: never emits `blocker` (rule 4 — license policy is opinion, not a code defect), so
`passed` is always True; findings surface for the run-record + outer ring. Never silently green:
always reports `coverage` (what ran + what was skipped), and degrades to a documented no-op
when Trivy is not armed OR there are no dependency/lockfile markers.

GAPS (rule 3):
  - Trivy is security-scanner-shaped; license scanning is one MODE (`--scanners license`). It
    scans the dependency tree of detected lockfiles / manifests, not source text.
  - License findings need a project POLICY (allow/deny list — e.g. reject GPL-3.0, allow MIT)
    to be actionable. Without one, this gate emits a raw license INVENTORY — noisy and not
    itself a verdict. The policy lives in `.trivyignore` / `trivy-secret.yaml` / project config
    (outer-ring concern); this adapter does not enforce it.
  - Per-license severity is advisory: Trivy maps a default license-category severity (copyleft
    -> HIGH, etc.), but whether a license is acceptable is opinion, not a code defect. Severity
    COLLAPSES to `warning` (越权日志 enum is `blocker|warning`; advisory never `blocker`). The
    raw Trivy level is kept in `detail` text.
  - Copyleft / compatibility analysis (GPL viral spread, license compatibility between deps)
    is legal judgment and stays OUTER-RING (LLM review / human legal) — not deterministic.

Usage: license_adapter.py [target...]   (default: cwd)
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD). No-op (coverage note) when Trivy is not armed
       or no dependency/lockfile markers are present.
"""

import json
import os
import subprocess
import sys

GATE = "license-compliance"

# Dependency / lockfile markers — when none are present, there is nothing to scan.
_DEP_MARKERS = (
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "Pipfile.lock",
    "poetry.lock",
    "pyproject.toml",
    "Cargo.lock",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile.lock",
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


def resolve_trivy():
    """The armed Trivy CLI on PATH, or None when not armed."""
    if have("trivy"):
        return ["trivy"]
    return None


def has_dep_markers(root):
    """True iff a dependency/lockfile marker is reachable (bounded depth, skips vendor/)."""
    want = set(_DEP_MARKERS)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            return True
    return False


def _suggest(license_name):
    """Best-effort: point the reviewer at policy / known-redflag families."""
    name = (license_name or "").upper()
    if "GPL" in name and "LGPL" not in name and "AGPL" not in name:
        return "GPL-family copyleft — review against project policy before bundling."
    if "AGPL" in name:
        return "AGPL is strongly copyleft (network-use trigger) — almost always deny."
    if "LGPL" in name or "MPL" in name or "EPL" in name or "CDDL" in name:
        return "Weak/file-copyleft — review conditions against project policy."
    if name in {"UNLICENSE", "UNKNOWN", ""} or "UNKNOWN" in name:
        return "Unknown / unclarified license — contact upstream to clarify before use."
    if name in {"MIT", "ISC", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "APACHE-2.0", "0BSD"}:
        return "Permissive license — usually fine; verify attribution requirements."
    return (
        "Review license against the project's allow/deny list (e.g. .trivyignore / policy); "
        "copyleft / compatibility analysis stays outer-ring (legal judgment)."
    )


def translate(results, root):
    """Trivy Results[] -> 越权日志 finding. severity COLLAPSES to warning.

    Each result has `Licenses[]` of {PkgName, Version, License[Name], Severity, ...}. We walk
    defensively — if a result lacks `Licenses`, skip; if the shape differs entirely, the caller
    has already coverage-noted (this fn only translates well-formed entries).
    """
    out = []
    for r in (results or [])[: _MAX_DEPTH * 4]:  # bound input traversal
        if not isinstance(r, dict):
            continue
        licenses = r.get("Licenses") or []
        if not isinstance(licenses, list):
            continue
        for lic in licenses:
            if not isinstance(lic, dict):
                continue
            pkg = lic.get("PkgName") or lic.get("Name") or "(unknown-pkg)"
            lic_names = lic.get("License") or []
            if isinstance(lic_names, dict):
                lic_names = [lic_names]
            if not isinstance(lic_names, list) or not lic_names:
                # No structured License[] -> degrade: report package + raw text if any.
                raw = lic.get("License") or lic.get("Severity") or "unknown"
                lic_label = str(raw) if raw else "unknown"
                out.append(_finding(pkg, lic_label, lic, root))
                continue
            for entry in lic_names:
                lname = (
                    entry.get("Name") if isinstance(entry, dict) else str(entry)
                ) or "unknown"
                out.append(_finding(pkg, lname, lic, root))
            if len(out) >= _MAX_FINDINGS:
                return out
        if len(out) >= _MAX_FINDINGS:
            return out
    return out


def _finding(pkg, license_name, raw_lic, root):
    """Build one finding dict. severity always 'warning'; raw Trivy level kept in detail."""
    sev = (raw_lic.get("Severity") or "").upper() if isinstance(raw_lic, dict) else ""
    filep = pkg  # package-level finding — file is the package name (line=0)
    try:
        filep = os.path.relpath(pkg, root)
    except (ValueError, TypeError):
        pass
    detail = f"License {license_name} on {pkg}"
    if sev and sev not in detail.upper():
        detail = f"[trivy:{sev.lower()}] {detail}"
    return {
        "severity": "warning",  # COLLAPSED — schema enum blocker|warning; advisory never blocker
        "rule": f"license:{license_name or pkg}",
        "file": filep,
        "line": 0,  # package-level — no source line
        "detail": detail,
        "suggestion": _suggest(license_name),
    }


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    coverage = [
        "license-compliance (advisory, severity collapsed to warning): wraps the armed Trivy "
        "CLI in license-scan mode (`--scanners license`) over dependency / lockfile markers; "
        "complementary to arch-contract-deps (secrets + CVEs) — different axis"
    ]

    trivy = resolve_trivy()
    if not trivy:
        coverage.append(
            "license-compliance: Trivy not armed (`trivy` not on PATH) — run `brew install "
            "trivy`. Gate skipped (no-op)."
        )
        emit([], coverage)
        return

    if not has_dep_markers(root):
        coverage.append(
            "license-compliance: no dependency markers — license gate skipped "
            "(checked package.json, package-lock.json, requirements.txt, Pipfile.lock, "
            "poetry.lock, pyproject.toml, Cargo.lock, go.mod, pom.xml, build.gradle, "
            "Gemfile.lock)."
        )
        emit([], coverage)
        return

    targets = sys.argv[1:] or [root]
    # --exit-code 0 so license findings do NOT fail the run; we parse stdout JSON ourselves.
    proc = subprocess.run(
        [
            *trivy,
            "fs",
            "--scanners",
            "license",
            "--format",
            "json",
            "--exit-code",
            "0",
            "--quiet",
            *targets,
        ],
        capture_output=True,
        text=True,
    )
    # Trivy: 0 = clean run (--exit-code 0 forces this); >=1 = scanner-level fault under
    # default exit codes. With --exit-code 0, a non-zero exit indicates a fault, not findings.
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        coverage.append(
            f"license-compliance: output unparseable ({e}); exit {proc.returncode} — "
            f"{(proc.stderr or '').strip()[:200] or 'no stderr'}; findings skipped."
        )
        emit([], coverage)
        return

    results = raw.get("Results") or []
    if not isinstance(results, list):
        coverage.append(
            f"license-compliance: Trivy output shape differs from expected "
            f"(Results[] not a list); findings skipped. Top-level keys: "
            f"{sorted(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}."
        )
        emit([], coverage)
        return

    findings = translate(results, root)
    # Detect degraded shape: Results present but no Licenses[] anywhere -> coverage-note.
    has_licenses = any(
        isinstance(r, dict) and isinstance(r.get("Licenses"), list) and r["Licenses"]
        for r in results
    )
    if results and not has_licenses:
        coverage.append(
            "license-compliance: Trivy Results[] present but no Licenses[] entries found "
            "(shape may differ from documented {Results[].Licenses[]}); 0 findings emitted."
        )
    coverage.append(
        f"license-compliance: {trivy[0]} fs --scanners license; targets={targets}; "
        f"{len(results)} result(s) -> {len(findings)} finding(s) emitted "
        f"(capped at {_MAX_FINDINGS}); exit {proc.returncode}."
    )
    coverage.append(
        "license-compliance: WITHOUT a project license policy (.trivyignore / allow-deny "
        "list), these findings are a raw license INVENTORY, not a verdict — review against "
        "policy; copyleft/compatibility analysis stays outer-ring (legal judgment)."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
