#!/usr/bin/env python3
"""drift_check.py — drift-detection self-gate (ADVISORY; workspace rule 4).

A self-contained (rule 7) structural checker, data-driven by a sibling registry
`drift_registry.json`. It surfaces DIVERGENCE in the duplicated boilerplate that the
self-contained-script convention mandates (rule 7): a named sibling set — e.g. the
`emit(findings, coverage)` helper across the adapter family — whose members SHOULD
match after a normalized-text diff (ODP-2: strip comments + whitespace) but have
copy-paste-diverged.

Severity is ADVISORY (rule 4: a heuristic-surface check never Blocks). Drift findings
are `warning`, the gate always exits 0, and `passed` is always True. The registry is the
heuristic surface (which sites should match is a human curation, not a proven fact); the
diff is the deterministic comparator over it. A registry omission degrades to a coverage
note, never a silent green (rule 3).

Self-contained (rule 7): duplicates the `read` / `emit` helpers used across the skill's
other infra scripts rather than importing a shared lib, so it stays independently
deployable. Pure stdlib. `drift_check.py` itself is a one-member family for now; ODP-3
(self-dogfood drift against future siblings) activates once a second sibling exists.

Usage:
    python3 infra/test/drift_check.py            # read drift_registry.json, emit + exit 0
"""

import ast
import json
import os
import re
import sys

GATE = "drift-check"
HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "drift_registry.json")
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/parallel-development


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def normalize(text):
    """Strip comments + collapse whitespace (ODP-2).

    Naive line-level comment strip (not string-aware). The duplicated helpers are
    simple; a '#' inside a string literal is rare and only adds noise to an advisory
    gate (rule 4 bounds the cost of a false positive).
    """
    lines = [re.sub(r"#.*$", "", line) for line in text.splitlines()]
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def extract_function_body(source, fn_name):
    """AST-extract a named function's source segment. None if absent or unparseable."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == fn_name
        ):
            return ast.get_source_segment(source, node)
    return None


def diff_site(site, root):
    """Compare a site's siblings by normalized function body.

    Returns (findings, coverage_bit). Divergence -> advisory `warning`. A site marked
    variation_allowed is skipped. Missing siblings (file/function absent) become a
    coverage note, not a drift finding.
    """
    fn = site.get("function", "")
    name = site.get("name", fn)
    if site.get("variation_allowed"):
        return [], f"site '{name}': variation_allowed — skipped"
    bodies = {}
    missing = []
    for sib in site.get("siblings", []):
        src = read(os.path.join(root, sib))
        body = None if src is None else extract_function_body(src, fn)
        if body is None:
            missing.append(sib)
            continue
        bodies.setdefault(normalize(body), []).append(sib)
    present = sum(len(v) for v in bodies.values())
    if missing and not bodies:
        return (
            [],
            f"site '{name}': {fn} not found in any sibling ({', '.join(missing)})",
        )
    if len(bodies) <= 1:
        tail = f"; {fn} not found in {', '.join(missing)}" if missing else ""
        return [], f"site '{name}': {present} sibling(s) match{tail}"
    majority = max(bodies.values(), key=len)
    findings = []
    for sibs in bodies.values():
        if set(sibs) == set(majority):
            continue
        findings.append(
            {
                "severity": "warning",
                "rule": "drift-divergent-sibling",
                "file": sibs[0],
                "line": 0,
                "detail": (
                    f"{fn} in {', '.join(sibs)} diverges from the majority "
                    f"({len(majority)} sibling(s))"
                ),
                "suggestion": (
                    f"reconcile {fn} across the sibling set, or mark "
                    "variation_allowed in drift_registry.json"
                ),
            }
        )
    return (
        findings,
        f"site '{name}': drift — {len(findings)} divergent group(s) of {present}",
    )


def run(registry_path, root):
    """Read the registry, iterate sites. Returns (findings, coverage). Advisory (rule 4)."""
    raw = read(registry_path)
    if raw is None:
        return [], [
            f"drift-check: registry {registry_path} not found — gate skipped (no-op)"
        ]
    try:
        reg = json.loads(raw)
    except json.JSONDecodeError as e:
        return [], [f"drift-check: registry unparseable ({e}) — gate skipped"]
    sites = reg.get("sites", [])
    findings = []
    coverage = [
        f"drift-check (advisory, rule 4): normalized-text diff (ODP-2) over {len(sites)} "
        "site(s); warning-only, exits 0"
    ]
    for site in sites:
        site_findings, bit = diff_site(site, root)
        findings += site_findings
        coverage.append(bit)
    return findings, coverage


def emit(findings, coverage):
    """Advisory: drift is never blocker (rule 4), so passed is always True and exit is 0."""
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
    sys.exit(0)


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or ROOT
    findings, coverage = run(REGISTRY, root)
    emit(findings, coverage)


if __name__ == "__main__":
    main()
