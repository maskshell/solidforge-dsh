#!/usr/bin/env python3
"""arch_contract_api.py — the inner-ring "API 契约门" for mixed frontend+backend repos.

A SIBLING cross-ecosystem gate (like arch_contract_deps.py / arch_contract_tests.py), NOT a per-language gate. Runs at the inner convergence point. Emits a structured 越权日志; for v1 all findings are `warning` (advisory — the checks are best-effort). The gate never silently greens: it always reports what it found in `coverage`.

WHY THIS GATE EXISTS: each per-language arch gate is language-local. Neither the Java gate nor the Web gate can answer "does the frontend match the backend's API?". For a mixed project (e.g. Java/Spring backend + React/Next frontend in one repo), that question is otherwise entirely an outer-ring concern. This gate brings the codable parts under deterministic coverage:

  1. contract presence   -> is there an OpenAPI/Swagger artifact at all?
  2. generated-client    -> if a generated client exists, is it stale vs the freshness contract (mtime)?
  3. path consistency    -> (JSON contracts only) do the frontend's fetch/axios call sites hit paths that exist in the spec?

HONEST GAP: semantic request/response SHAPE matching (field types, required-ness, response codes) is NOT statically determinable without codegen or runtime contract tests. Those stay outer-ring (or in the test gate via contract tests). This gate covers artifact presence + freshness + coarse path/method consistency only — surfaced explicitly in `coverage`.

Scope (v1): frontend = package.json (any JS/TS frontend); backend = Java (pom.xml / build.gradle). The OpenAPI toolchain is most mature for Java (springdoc-openapi). Extensible to other backend markers later.

Usage: arch_contract_api.py
       Operates on $SOLIDFORGE_PROJECT_DIR (or CWD).
"""

import json
import os
import re
import sys

GATE = "arch-contract-api"

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
_MAX_MARKER_DEPTH = 4

_JSON_CONTRACTS = ("openapi.json", "swagger.json")
_YAML_CONTRACTS = ("openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml")
_STATIC_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".css",
    ".scss",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
)
_MAX_PATH_FINDINGS = 30


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


def _at(root, rel):
    return os.path.normpath(os.path.join(root, rel))


def find_marker_dirs(root, names, max_depth=_MAX_MARKER_DEPTH):
    """Dirs (relative to root; '' == root) directly containing any marker file."""
    want = set(names)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            found.append("" if rel == "." else rel)
    return found


def _candidate_contract_dirs(root, be_dirs):
    """Where an OpenAPI/Swagger artifact commonly lives."""
    out = [root]
    for sub in ("docs", "api", "openapi", "spec"):
        out.append(os.path.join(root, sub))
    for b in be_dirs:
        bd = _at(root, b)
        out.append(bd)
        out.append(os.path.join(bd, "src", "main", "resources"))
        out.append(os.path.join(bd, "docs"))
    seen = set()
    res = []
    for d in out:
        if d not in seen:
            seen.add(d)
            res.append(d)
    return res


def find_contract(root, be_dirs):
    """Return (path, is_json) — JSON preferred over YAML — or (None, False)."""
    dirs = _candidate_contract_dirs(root, be_dirs)
    for d in dirs:
        for n in _JSON_CONTRACTS:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p, True
    for d in dirs:
        for n in _YAML_CONTRACTS:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p, False
    return None, False


_GEN_FILE_RE = re.compile(
    r"(generated|api[-_]?client|openapi.*\.(ts|tsx|js|jsx))", re.IGNORECASE
)


def find_generated_client(root, fe_dirs):
    """Best-effort: a generated-client artifact under a frontend dir (a file whose name looks generated, or a dir literally named generated/api-client)."""
    for fe in fe_dirs:
        fed = _at(root, fe)
        for dirpath, dirnames, filenames in os.walk(fed):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
            rel = os.path.relpath(dirpath, fed)
            if rel != "." and rel.count(os.sep) + 1 > 3:
                dirnames[:] = []
                continue
            for fn in filenames:
                if _GEN_FILE_RE.search(fn):
                    return os.path.join(dirpath, fn)
            for d in dirnames:
                if "generated" in d.lower() or "api-client" in d.lower():
                    return os.path.join(dirpath, d)
    return None


def check_freshness(root, contract_path, fe_dirs, findings, coverage):
    gen = find_generated_client(root, fe_dirs)
    if not gen:
        coverage.append(
            "api-contract: no generated client detected under frontend — freshness check n/a (if you generate a client, name the output/dir `generated` or `api-client` so staleness is tracked)"
        )
        return
    try:
        c_mtime = os.path.getmtime(contract_path)
        g_mtime = os.path.getmtime(gen)
    except OSError:
        coverage.append(
            "api-contract: generated-client mtime unavailable — freshness check skipped"
        )
        return
    rel = os.path.relpath(gen, root)
    if g_mtime < c_mtime:
        findings.append(
            {
                "severity": "warning",
                "rule": "stale-generated-client",
                "file": rel,
                "line": 0,
                "detail": f"generated client `{rel}` is older than the API contract — the frontend may be out of sync with the backend",
                "suggestion": "Regenerate the client from the contract (e.g. rerun the codegen step / `openapi-typescript` / `openapi-generator`).",
            }
        )
        coverage.append(f"api-contract: generated client `{rel}` STALE vs contract")
    else:
        coverage.append(
            f"api-contract: generated client `{rel}` up to date vs contract"
        )


def extract_spec_paths(spec):
    """OpenAPI/Swagger: top-level `paths` object keys (path templates)."""
    paths = (spec or {}).get("paths") or {}
    if isinstance(paths, dict):
        return list(paths.keys())
    return []


def _path_to_regex(p):
    """`/users/{id}` -> `^/users/[^/]+$`. Tolerant of `{var}` and Spring `${var}`."""
    seg = []
    for part in p.split("/"):
        if (part.startswith("{") and part.endswith("}")) or (
            part.startswith("${") and part.endswith("}")
        ):
            seg.append("[^/]+")
        else:
            seg.append(re.escape(part))
    return re.compile("^" + "/".join(seg) + "$")


def _normalize_url(url):
    """Drop scheme/host/query/fragment; turn `${x}` template vars into a placeholder segment so `/api/users/${id}` can match a spec path `/api/users/{id}`."""
    u = url.strip()
    if "://" in u:  # strip scheme://host
        u = "/" + "/".join(u.split("/")[3:])
    u = u.split("?")[0].split("#")[0]
    u = re.sub(r"\$\{[^}]+\}", "_param", u)
    if not u.startswith("/"):
        u = "/" + u
    return u


# fetch("..."), axios.get("..."), axios.post(`...`), ... — first string/template arg.
_CALL_RE = re.compile(
    r"""(?:fetch|axios\.(?:get|post|put|delete|patch|request))\(\s*['"`]([^'"`]+)['"`]"""
)


def extract_call_sites(root, fe_dirs):
    """Return [(file, line, url), ...] for fetch/axios URL literals in FE source."""
    out = []
    for fe in fe_dirs:
        fed = _at(root, fe)
        for dirpath, dirnames, filenames in os.walk(fed):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
            rel = os.path.relpath(dirpath, fed)
            if rel != "." and rel.count(os.sep) + 1 > _MAX_MARKER_DEPTH:
                dirnames[:] = []
                continue
            for fn in filenames:
                if not fn.endswith((".ts", ".tsx", ".js", ".jsx")):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8") as fh:
                        lines = fh.read().splitlines()
                except OSError:
                    continue
                for i, line in enumerate(lines, 1):
                    for m in _CALL_RE.finditer(line):
                        out.append((fp, i, m.group(1)))
    return out


def _looks_like_api_path(u):
    """Filter out obvious non-API URLs (static assets, data:, bare hosts)."""
    if not u or u.startswith(("data:", "blob:", "mailto:", "tel:", "javascript:")):
        return False
    if u.endswith(_STATIC_EXT):
        return False
    # need at least one path segment beyond root
    return len(u.strip("/").split("/")) >= 1 and u != "/"


def check_path_consistency(root, contract_path, fe_dirs, findings, coverage):
    try:
        with open(contract_path, encoding="utf-8") as fh:
            spec = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        coverage.append(
            f"api-contract: contract JSON unparseable — path-consistency skipped ({e})"
        )
        return
    spec_paths = extract_spec_paths(spec)
    patterns = [_path_to_regex(p) for p in spec_paths]
    coverage.append(f"api-contract: spec declares {len(spec_paths)} path(s)")
    sites = extract_call_sites(root, fe_dirs)
    flagged = 0
    seen = set()
    for fp, line, url in sites:
        u = _normalize_url(url)
        if not _looks_like_api_path(u):
            continue
        if any(p.match(u) for p in patterns):
            continue
        key = (os.path.relpath(fp, root), line, u)
        if key in seen:
            continue
        seen.add(key)
        if flagged >= _MAX_PATH_FINDINGS:
            continue
        flagged += 1
        findings.append(
            {
                "severity": "warning",
                "rule": "api-path-not-in-spec",
                "file": os.path.relpath(fp, root),
                "line": line,
                "detail": f"frontend calls `{url}` (normalized `{u}`) which is not in the API contract paths",
                "suggestion": "Add the path to the contract, fix the call, or (if dynamic/base-prefixed) ignore — this scan is best-effort.",
            }
        )
    extra = len(seen) - flagged
    coverage.append(
        f"api-contract: scanned {len(sites)} fetch/axios call site(s); {len(seen)} path(s) not in spec (showing {flagged}{f', {extra} more suppressed' if extra > 0 else ''}) — best-effort, dynamic/base-prefixed URLs may false-positive"
    )


def main():
    root = os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd()
    findings = []
    coverage = [
        "api-contract (advisory, warnings only): semantic request/response shape matching needs codegen or runtime contract tests — this gate checks artifact presence, generated-client freshness, and coarse path/method consistency only",
    ]
    fe_dirs = find_marker_dirs(root, ["package.json"])
    be_dirs = find_marker_dirs(root, ["pom.xml", "build.gradle", "build.gradle.kts"])
    if not (fe_dirs and be_dirs):
        coverage.append(
            f"api-contract: not a mixed frontend+backend project (frontend={len(fe_dirs)}, java-backend={len(be_dirs)}) — contract gate skipped"
        )
        emit(findings, coverage)
        return
    coverage.append(
        f"api-contract: {len(fe_dirs)} frontend dir(s), {len(be_dirs)} backend dir(s)"
    )
    contract, is_json = find_contract(root, be_dirs)
    if not contract:
        findings.append(
            {
                "severity": "warning",
                "rule": "no-shared-contract",
                "file": "(project root)",
                "line": 0,
                "detail": "mixed frontend+backend project with no OpenAPI/Swagger artifact found — frontend/backend API consistency is unverifiable deterministically",
                "suggestion": "Add springdoc-openapi (Java) or an openapi.yaml at root/docs/api (or <backend>/src/main/resources), and generate the frontend client from it.",
            }
        )
        coverage.append(
            "api-contract: no openapi/swagger artifact found (looked in root, docs/, api/, openapi/, spec/, <backend>/src/main/resources)"
        )
        emit(findings, coverage)
        return
    coverage.append(
        f"api-contract: contract at {os.path.relpath(contract, root)} ({'JSON — full parse' if is_json else 'YAML — presence/freshness only'})"
    )
    check_freshness(root, contract, fe_dirs, findings, coverage)
    if is_json:
        check_path_consistency(root, contract, fe_dirs, findings, coverage)
    else:
        coverage.append(
            "api-contract: YAML contract — path-consistency scan skipped (emit JSON too — springdoc can — for full parsing)"
        )
    emit(findings, coverage)


if __name__ == "__main__":
    main()
