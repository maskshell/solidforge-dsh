#!/usr/bin/env python3
"""iac_adapter.py — convergence-point adapter: Checkov IaC MISCONFIG → 越权日志.

A SIBLING convergence-point gate (like semgrep_adapter.py / spectral_adapter.py /
arch_contract_api.py), NOT a hand-rolled heuristic. It shells out to the ARMED Checkov CLI
(armed globally via `brew install checkov` or `pip install checkov`) and translates its
JSON findings into the loop's 越权日志 schema (`{gate, passed, coverage, findings[]}`). See
references/external-skills.md.

COMPLEMENTARY to the existing security coverage, NOT a replacement:
  - `/security-review` (skill) is an LLM review — semantic, slow, token-costly.
  - `arch_contract_deps.py` covers leaked SECRETS (gitleaks) + dependency CVEs.
  - `semgrep_adapter.py` covers SAST over SOURCE code (CVE-pattern code).
  - `iac_adapter.py` covers MISCONFIG in IaC files (Terraform/Kubernetes/Dockerfile) —
    a different axis: the bug is in the deployment manifest, not the app source.

OPT-IN for infra-bearing projects. solidforge's platform model (platforms.json) is APP
languages (iOS/Python/Rust/Web/Java); this gate is an EXTERNAL-SKILL gate, not a platform
row, and NO-OPS CLEANLY when no IaC markers are present (no Terraform/Dockerfile/K8s).

Checkov emits (with `--output json --quiet`) `{"Results":[{check_type, failed_checks:[
{check_id, check_name, file_path, file_abs_path, guideline, severity, ...}]}]}`. The adapter
maps `check_id -> rule`, `check_name + file_path -> detail`, `file_path -> file` (relpath),
and reports findings at LINE 0 (Checkov findings are file-level; line is often absent).
severity COLLAPSES to `warning` (see GAP).

ADVISORY: never emits `blocker` (rule 4 — IaC misconfig context matters and false-positives
are common), so `passed` is always True; findings surface for the run-record + outer ring.
Never silently green: always reports `coverage` (what ran + what was skipped).

GAPS (rule 3):
  - Only fires when IaC files are present — opt-in for infra-bearing projects; out of the
    app-language platform model (platforms.json). This is an external-skill gate, NOT a
    platform row; do not add a platforms.json entry for it.
  - Checkov findings are FILE-LEVEL (line often absent) — line is reported as 0.
  - Checkov's severity levels COLLAPSE to `warning` (越权日志 schema enum is blocker|warning;
    advisory never blocker). The original severity is kept in `detail` text.
  - Does NOT cover runtime/cloud misconfig (drift, live IAM) — that is an outer-ring concern.
  - IaC misconfig context matters (a `:*` port may be intentional in a sandbox); findings are
    advisory review input, not auto-Blockers.

Usage: iac_adapter.py [root]   (default: cwd / $SOLIDFORGE_PROJECT_DIR)
       No-op (coverage note) when Checkov is not armed OR no IaC markers are present.
"""

import json
import os
import subprocess
import sys

GATE = "iac-misconfig"

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

# Directory names that, if present at any depth, signal a K8s manifest tree even before
# we hand YAML files to checkov for framework auto-detection.
_K8S_DIR_NAMES = {"k8s", "kubernetes", "deploy", "deployment", "helm"}


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


def resolve_checkov():
    """The armed Checkov CLI on PATH, or None when not armed."""
    if have("checkov"):
        return ["checkov"]
    return None


def find_iac_markers(root):
    """True iff the tree (bounded depth) contains IaC markers checkov would scan.

    Markers: `*.tf` (Terraform), `Dockerfile` / `*.dockerfile` / `Containerfile`,
    any `*.yaml`/`*.yml` (let checkov decide if it's a k8s manifest), or a k8s-ish
    directory (`k8s`/`kubernetes`/`deploy`/`deployment`/`helm`). Bounded to avoid
    walking huge repos; reuses spectral_adapter's _IGNORE_DIRS.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        if any(d in _K8S_DIR_NAMES for d in dirnames):
            return True
        for n in filenames:
            low = n.lower()
            if n.endswith(".tf"):
                return True
            if (
                low == "dockerfile"
                or low.endswith(".dockerfile")
                or low == "containerfile"
            ):
                return True
            if low.endswith(".yaml") or low.endswith(".yml"):
                return True
    return False


def _suggest(check_id):
    """Best-effort: map a Checkov check id to a concrete fix pointer."""
    cid = (check_id or "").lower()
    if "iam" in cid or "privileg" in cid:
        return "Scope IAM / drop privileged flags (least-privilege finding)."
    if "port" in cid or "exposure" in cid or "public" in cid:
        return "Constrain the port/exposure (verify the wildcard is intentional)."
    if "encryp" in cid or "tls" in cid or "ssl" in cid:
        return "Enable encryption in transit / at rest."
    if "secret" in cid or "credential" in cid or "password" in cid:
        return "Move the secret to a secret store / env var (do not inline in IaC)."
    if "image" in cid or "tag" in cid:
        return "Pin the image to an immutable tag / digest."
    if "root" in cid:
        return "Avoid running as root (set runAsNonRoot)."
    return "Review the finding in the IaC file; verify it is not a false positive in context."


def translate(results, root):
    """Checkov Results[].failed_checks[] -> 越权日志 findings. severity COLLAPSES to warning."""
    out = []
    if not isinstance(results, list):
        return out
    for result in results:
        if not isinstance(result, dict):
            continue
        for fc in result.get("failed_checks") or []:
            if not isinstance(fc, dict):
                continue
            check_id = fc.get("check_id") or "checkov-finding"
            check_name = fc.get("check_name", "")
            sev = (fc.get("severity") or "").upper()
            filep = fc.get("file_path") or fc.get("file_abs_path") or "(unknown)"
            try:
                filep = os.path.relpath(filep, root)
            except ValueError:
                pass
            detail = f"{check_name} ({filep})"
            if sev:
                detail = f"[checkov:{sev.lower()}] {detail}"
            out.append(
                {
                    "severity": "warning",  # COLLAPSED — schema enum blocker|warning; advisory never blocker
                    "rule": f"checkov:{check_id}",
                    "file": filep,
                    "line": 0,  # Checkov findings are file-level (line often absent)
                    "detail": detail,
                    "suggestion": _suggest(check_id),
                }
            )
            if len(out) >= _MAX_FINDINGS:
                return out
    return out


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or (
        os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    )
    coverage = [
        "iac-misconfig (advisory, severity collapsed to warning): wraps the armed Checkov CLI "
        "scanning IaC files (Terraform / Kubernetes / Dockerfile) for CIS/OWASP-style misconfig; "
        "opt-in for infra-bearing projects, no-ops when no IaC markers present"
    ]
    checkov = resolve_checkov()
    if not checkov:
        coverage.append(
            "iac-misconfig: Checkov not armed (`checkov` not on PATH) — run `brew install checkov` "
            "(or `pip install checkov`). Gate skipped (no-op)."
        )
        emit([], coverage)
        return

    if not find_iac_markers(root):
        coverage.append(
            "iac-misconfig: no IaC files (Terraform/Dockerfile/K8s) — iac gate skipped "
            "(not an infra-bearing project)."
        )
        emit([], coverage)
        return

    coverage.append(
        "iac-misconfig: IaC markers detected (Terraform/Dockerfile/K8s); running checkov with "
        "framework auto-detection (terraform/kubernetes/dockerfile)."
    )
    proc = subprocess.run(
        [*checkov, "--directory", root, "--output", "json", "--quiet"],
        capture_output=True,
        text=True,
    )
    # Checkov: 0 = no failures; 1 = failures present (not a hard error); parse stdout JSON
    # regardless — with --output json it emits JSON on stdout for both exit codes.
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        coverage.append(
            f"iac-misconfig: output unparseable ({e}); exit {proc.returncode} — "
            f"{(proc.stderr or '').strip()[:200] or 'no stderr'}; findings skipped."
        )
        emit([], coverage)
        return

    results = raw.get("results") or []
    if isinstance(results, dict):
        # Some checkov versions return a dict keyed by framework -> list; flatten.
        flat = []
        for arr in results.values():
            if isinstance(arr, list):
                flat.extend(arr)
        results = flat
    findings = translate(results, root)
    coverage.append(
        f"iac-misconfig: {checkov[0]} --directory <root> --output json --quiet; "
        f"{len(findings)} finding(s) emitted (capped at {_MAX_FINDINGS}, severity collapsed to "
        f"warning); exit {proc.returncode}."
    )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
