#!/usr/bin/env python3
"""Behavioral smoke tests for the architecture-contract gates.

Companion to disconnect_check.py (which verifies STRUCTURE). This verifies BEHAVIOR: each gate, given a fixture with a known violation, surfaces a finding. Skips platforms whose tools are not installed (with a clear message). Run:

    python3 infra/test/smoke_gates.py
"""

import json
import os
import subprocess
import sys
import tempfile

from violation_log_schema import validate as validate_violation_log

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "infra", "scripts")


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def run_gate(lang, fixture, src_arg):
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=fixture)
    proc = subprocess.run(
        ["python3", os.path.join(SCRIPTS, f"arch_contract_{lang}.py"), src_arg],
        capture_output=True,
        text=True,
        cwd=fixture,
        env=env,
        timeout=600,
    )
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"_raw": proc.stdout, "_stderr": proc.stderr, "_rc": proc.returncode}


def run_script(name, fixture, src_arg="."):
    """Run a cross-ecosystem gate script (deps/tests) the same way run_gate runs a per-language one, returning its parsed JSON."""
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=fixture)
    proc = subprocess.run(
        ["python3", os.path.join(SCRIPTS, name), src_arg],
        capture_output=True,
        text=True,
        cwd=fixture,
        env=env,
        timeout=600,
    )
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"_raw": proc.stdout, "_stderr": proc.stderr, "_rc": proc.returncode}


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)


def assert_conforms(data, lang):
    """Every gate's 越权日志 output must conform to the violation-log schema (infra/schemas/violation-log.schema.json). Catches drift when a 5th language is added or emit() is refactored."""
    errs = validate_violation_log(data)
    assert not errs, f"{lang}: gate output violates violation-log schema: {errs}"


def smoke_python():
    d = tempfile.mkdtemp(prefix="pdsmoke_py_")
    write(
        f"{d}/app/svc.py",
        "import time\nasync def fetch():\n    time.sleep(1)\n    return 1\n",
    )
    data = run_gate("python", d, "app")
    assert_conforms(data, "python")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("concurrency-baseline-sync-in-async" in r for r in rules), (
        f"python: expected sync-in-async finding, got {rules}"
    )
    print("  python: PASS (sync-in-async detected)")


def smoke_rust():
    if not (have("cargo") and have("cargo-clippy")):
        print("  rust: SKIP (cargo / clippy not installed)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_rs_")
    write(
        f"{d}/Cargo.toml",
        '[package]\nname = "smoke"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n',
    )
    # unnecessary_literal_unwrap is a reliable clippy lint
    write(f"{d}/src/main.rs", "fn main() { let v = Some(1); v.unwrap(); }\n")
    data = run_gate("rust", d, ".")
    assert_conforms(data, "rust")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("clippy" in r for r in rules), (
        f"rust: expected a clippy finding, got {rules}"
    )
    print("  rust: PASS (clippy lint detected)")


def smoke_swift():
    if not (have("swiftlint") and have("swift")):
        print("  swift: SKIP (swiftlint / swift not installed)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_sw_")
    write(
        f"{d}/Package.swift",
        '// swift-tools-version:5.9\nimport PackageDescription\nlet p = Package(name: "smoke", targets: [.executableTarget(name: "Main", path: "Sources/Main")])\n',
    )
    write(
        f"{d}/Sources/Main/main.swift",
        "import Foundation\nfunc f() -> Int { let v: Int? = 5; return v! }\n",
    )
    write(
        f"{d}/.swiftlint.yml",
        "included:\n  - Sources\nopt_in_rules:\n  - force_unwrapping\n",
    )
    data = run_gate("swift", d, ".")
    assert_conforms(data, "swift")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("force_unwrapping" in r for r in rules), (
        f"swift: expected force_unwrapping finding, got {rules}"
    )
    print("  swift: PASS (force_unwrapping detected)")


def smoke_web():
    # Web needs depcruise reachable in the fixture (node_modules/.bin/depcruise).
    # Gate falls back to npx --no-install, which fails if depcruise isn't installed.
    d = tempfile.mkdtemp(prefix="pdsmoke_web_")
    write(
        f"{d}/package.json",
        '{ "name": "smoke", "version": "1.0.0", "private": true }\n',
    )
    write(f"{d}/src/a.ts", "import './b'\nexport const A = 1\n")
    write(f"{d}/src/b.ts", "import './a'\nexport const B = 2\n")
    write(
        f"{d}/.dependency-cruiser.cjs",
        "module.exports = { forbidden: [{ name: 'no-circular', severity: 'error', from: {}, to: { circular: true } }], "
        "options: { tsPreCompilationDeps: true, doNotFollow: { path: 'node_modules' }, "
        "enhancedResolveOptions: { extensions: ['.ts','.tsx','.js','.jsx','.json'] } } };\n",
    )
    if not os.path.exists(f"{d}/node_modules/.bin/depcruise"):
        subprocess.run(
            ["npm", "install", "--no-save", "dependency-cruiser"],
            cwd=d,
            capture_output=True,
            timeout=180,
        )
    if not os.path.exists(f"{d}/node_modules/.bin/depcruise"):
        print(
            "  web: SKIP (depcruise not installed; run `npm i -D dependency-cruiser` to enable)"
        )
        return
    # Cruise from an ENTRY file — depcruise's cycle detection is most reliable from entries.
    data = run_gate("web", d, "src/a.ts")
    assert_conforms(data, "web")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("circular" in r for r in rules), (
        f"web: expected no-circular finding, got {rules} coverage={data.get('coverage')}"
    )
    print("  web: PASS (circular dependency detected)")


def smoke_java():
    # Schema-conformance always runs; a checkstyle finding is asserted only when Checkstyle is actually available.
    # Otherwise the gate must degrade honestly (a coverage note — never silently green), which we also assert.
    d = tempfile.mkdtemp(prefix="pdsmoke_jv_")
    write(
        f"{d}/pom.xml",
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<modelVersion>4.0.0</modelVersion>"
        "<groupId>com.example</groupId><artifactId>smoke</artifactId><version>0.0.1</version>"
        "</project>\n",
    )
    write(
        f"{d}/checkstyle.xml",
        '<?xml version="1.0"?><!DOCTYPE module PUBLIC "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN" '
        '"https://checkstyle.org/dtds/configuration_1_3.dtd">'
        '<module name="Checker"><module name="TreeWalker">'
        '<module name="UnusedImports"><property name="severity" value="error"/></module>'
        "</module></module>\n",
    )
    write(
        f"{d}/src/main/java/com/example/Smoker.java",
        "package com.example;\nimport java.util.ArrayList;  // unused\npublic class Smoker {}\n",
    )
    data = run_gate("java", d, ".")
    assert_conforms(data, "java")
    checkstyle_on = have("checkstyle") or bool(os.environ.get("CHECKSTYLE_JAR"))
    if checkstyle_on:
        rules = [f.get("rule", "") for f in data.get("findings", [])]
        assert any("UnusedImports" in r or "unused" in r.lower() for r in rules), (
            f"java: expected an UnusedImports finding, got {rules} coverage={data.get('coverage')}"
        )
        print("  java: PASS (checkstyle UnusedImports detected)")
    else:
        cov = " ".join(data.get("coverage", [])).lower()
        assert "checkstyle" in cov, (
            f"java: checkstyle absent but no honest-degrade note in coverage: {data.get('coverage')}"
        )
        print("  java: PASS (schema-valid; checkstyle absent -> honest degrade)")


def smoke_go():
    # Schema-conformance always runs; a go-vet finding is asserted only when `go` is available.
    # Otherwise the gate must degrade honestly (a coverage note — never silently green).
    d = tempfile.mkdtemp(prefix="pdsmoke_go_")
    write(f"{d}/go.mod", "module smoke\n\ngo 1.21\n")
    write(
        f"{d}/.golangci.yml",
        "linters:\n  disable-all: true\n  enable:\n    - govet\n    - gofmt\n",
    )
    # fmt.Printf with a wrong verb is the canonical `go vet` finding (printf-format) — it
    # COMPILES, so vet reaches it (build passes, vet runs). stdlib-only imports -> no
    # module-graph / network resolution needed.
    write(
        f"{d}/main.go",
        'package main\n\nimport "fmt"\n\nfunc main() { fmt.Printf("%d\\n", "x") }\n',
    )
    # GOTOOLCHAIN=local: prevent the Go 1.21+ toolchain directive from auto-downloading a
    # newer toolchain over the network if the installed Go doesn't satisfy go.mod's `go` line.
    saved = os.environ.get("GOTOOLCHAIN")
    os.environ["GOTOOLCHAIN"] = "local"
    try:
        data = run_gate("go", d, ".")
    finally:
        if saved is None:
            os.environ.pop("GOTOOLCHAIN", None)
        else:
            os.environ["GOTOOLCHAIN"] = saved
    assert_conforms(data, "go")
    if have("go"):
        rules = [f.get("rule", "") for f in data.get("findings", [])]
        details = [f.get("detail", "") for f in data.get("findings", [])]
        # `go vet` -> rule=go-vet; golangci-lint's govet -> rule=govet. Accept either, or a
        # printf/format detail.
        assert any("vet" in r for r in rules) or any(
            "format" in det.lower() or "printf" in det.lower() for det in details
        ), (
            f"go: expected a vet/printf finding, got {rules} coverage={data.get('coverage')}"
        )
        print("  go: PASS (go vet printf-format detected)")
    else:
        cov = " ".join(data.get("coverage", [])).lower()
        assert "go" in cov and "skip" in cov, (
            f"go: toolchain absent but no honest-degrade note in coverage: {data.get('coverage')}"
        )
        print("  go: PASS (schema-valid; go absent -> honest degrade)")


def smoke_deps_gitleaks():
    if not have("gitleaks"):
        print("  deps(gitleaks): SKIP (gitleaks not installed)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_dep_")
    with open(os.path.join(d, "secrets.py"), "w") as fh:
        fh.write(
            "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcFAKEBASE64CONTENTHERE\n-----END PRIVATE KEY-----\n"
        )
    data = run_script("arch_contract_deps.py", d, ".")
    assert_conforms(data, "deps")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("secret" in r for r in rules), (
        f"deps: expected a secret finding, got {rules}"
    )
    assert all(
        "FAKEBASE64CONTENTHERE" not in f.get("detail", "")
        for f in data.get("findings", [])
    ), "deps: secret leaked into detail"
    print("  deps(gitleaks): PASS (secret leak detected, redacted)")


def smoke_tests_cargo():
    if not (have("cargo") and have("cargo-clippy")):
        print("  tests(cargo): SKIP (cargo not installed)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_tst_")
    with open(os.path.join(d, "Cargo.toml"), "w") as fh:
        fh.write(
            '[package]\nname = "smoke"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n'
        )
    os.makedirs(os.path.join(d, "src"), exist_ok=True)
    with open(os.path.join(d, "src", "lib.rs"), "w") as fh:
        fh.write("pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
    os.makedirs(os.path.join(d, "tests"), exist_ok=True)
    with open(os.path.join(d, "tests", "t.rs"), "w") as fh:
        fh.write("#[test]\nfn fails_demo() { assert_eq!(1, 2); }\n")
    data = run_script("arch_contract_tests.py", d, ".")
    assert_conforms(data, "tests")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any(r == "test-failure" for r in rules), (
        f"tests: expected a test-failure finding, got {rules}"
    )
    print("  tests(cargo): PASS (failing test detected)")


def smoke_nested():
    # Root Java backend + nested frontend: recursive detection must dispatch BOTH ecosystems in the cross-language gates (root-level-only detection would miss the nested frontend).
    # Asserts the DISPATCH (coverage notes), not tool output, so it's robust whether or not npm/mvn/vitest are installed.
    d = tempfile.mkdtemp(prefix="pdsmoke_nest_")
    write(
        f"{d}/pom.xml",
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
        "<groupId>com.example</groupId><artifactId>be</artifactId><version>0.0.1</version></project>\n",
    )
    write(
        f"{d}/frontend/package.json",
        '{ "name": "fe", "version": "1.0.0", "private": true }\n',
    )
    deps_data = run_script("arch_contract_deps.py", d, ".")
    assert_conforms(deps_data, "nested-deps")
    deps_cov = " ".join(deps_data.get("coverage", []))
    assert "npm audit" in deps_cov, (
        f"nested-deps: expected npm audit dispatch (nested frontend), got {deps_data.get('coverage')}"
    )
    assert "dependency-check" in deps_cov, (
        f"nested-deps: expected dependency-check dispatch (root pom.xml), got {deps_data.get('coverage')}"
    )
    tests_data = run_script("arch_contract_tests.py", d, ".")
    assert_conforms(tests_data, "nested-tests")
    tests_cov = " ".join(tests_data.get("coverage", []))
    assert "vitest" in tests_cov, (
        f"nested-tests: expected vitest dispatch (nested frontend), got {tests_data.get('coverage')}"
    )
    assert "maven" in tests_cov or "gradle" in tests_cov, (
        f"nested-tests: expected java dispatch (root pom.xml), got {tests_data.get('coverage')}"
    )
    print(
        "  nested: PASS (recursive detection dispatched both FE and BE in deps + tests gates)"
    )


def smoke_api():
    # Mixed FE+BE with an OpenAPI contract; a frontend call to a path NOT in the spec must surface as a warning. Plus a no-contract variant -> no-shared-contract.
    d = tempfile.mkdtemp(prefix="pdsmoke_api_")
    write(
        f"{d}/pom.xml",
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
        "<groupId>com.example</groupId><artifactId>be</artifactId><version>0.0.1</version></project>\n",
    )
    write(
        f"{d}/package.json", '{ "name": "fe", "version": "1.0.0", "private": true }\n'
    )
    write(
        f"{d}/openapi.json",
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "x", "version": "1"},
                "paths": {"/users/{id}": {"get": {}}, "/health": {"get": {}}},
            }
        )
        + "\n",
    )
    # `/users/${id}` is in the spec; `/api/v1/orders` is NOT.
    write(
        f"{d}/src/api.ts",
        "export const getUser = (id: string) => fetch(`/users/${id}`);\n"
        'export const orders = () => fetch("/api/v1/orders");\n',
    )
    data = run_script("arch_contract_api.py", d, ".")
    assert_conforms(data, "api")
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert "api-path-not-in-spec" in rules, (
        f"api: expected api-path-not-in-spec for /api/v1/orders, got {rules} coverage={data.get('coverage')}"
    )
    # No-contract variant.
    d2 = tempfile.mkdtemp(prefix="pdsmoke_api2_")
    write(
        f"{d2}/pom.xml",
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
        "<groupId>com.example</groupId><artifactId>be</artifactId><version>0.0.1</version></project>\n",
    )
    write(
        f"{d2}/package.json", '{ "name": "fe", "version": "1.0.0", "private": true }\n'
    )
    data2 = run_script("arch_contract_api.py", d2, ".")
    assert_conforms(data2, "api-nocontract")
    rules2 = [f.get("rule", "") for f in data2.get("findings", [])]
    assert "no-shared-contract" in rules2, (
        f"api-nocontract: expected no-shared-contract, got {rules2}"
    )
    print("  api: PASS (api-path-not-in-spec + no-shared-contract detected)")


def _armed_detect_mjs(fixture):
    """The armed Impeccable detector path for a fixture, or None if not armed."""
    for cand in (
        os.path.join(
            fixture, ".solidforge", "skills", "impeccable", "scripts", "detect.mjs"
        ),
        os.path.expanduser("~/.solidforge/skills/impeccable/scripts/detect.mjs"),
    ):
        if os.path.isfile(cand):
            return cand
    return None


def _armed_spectral(fixture=None):
    """True if the Stoplight Spectral CLI is armed (local node_modules/.bin or global on PATH)."""
    for base in (fixture, os.getcwd()):
        if base and os.path.isfile(
            os.path.join(base, "node_modules", ".bin", "spectral")
        ):
            return True
    return have("spectral")


def smoke_impeccable():
    # The detect adapter wraps the ARMED Impeccable detector (an external skill, armed per-project).
    # Skip (like rust/swift) when Impeccable is not armed in the fixture / user-global.
    probe = tempfile.mkdtemp(prefix="pdsmoke_imp_probe_")
    detect = _armed_detect_mjs(os.getcwd()) or _armed_detect_mjs(probe)
    if not detect:
        print(
            "  impeccable: SKIP (Impeccable not armed — run `npx impeccable install` in a fixture)"
        )
        return
    # A fixture with a known anti-pattern (side-tab border + overused font).
    d = tempfile.mkdtemp(prefix="pdsmoke_imp_")
    # The adapter resolves detect.mjs from its OWN root (SOLIDFORGE_PROJECT_DIR / cwd), which the
    # smoke harness sets to THIS tempdir — so a project-cwd arm (or a ~/.solidforge global arm) is
    # NOT visible to the adapter. Mirror the armed skill dir into the tempdir's .solidforge/skills/
    # so detect_mjs_path(root=d) resolves it. (Impeccable is armed per-project via
    # `npx impeccable install`; the detector resolves its engine relative to __dirname, so a
    # symlink to the armed skill dir is sufficient — no copy needed.)
    skill_dir = os.path.dirname(os.path.dirname(detect))  # .../skills/impeccable
    link = os.path.join(d, ".solidforge", "skills", "impeccable")
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if not os.path.exists(link):
        os.symlink(skill_dir, link)
    write(
        f"{d}/package.json", '{ "name": "fe", "version": "1.0.0", "private": true }\n'
    )
    write(
        f"{d}/index.html",
        "<!DOCTYPE html><html><body><style>\n"
        ".hero{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#9ca3af;"
        "font-family:Inter,Arial,sans-serif;}\n"
        ".card{border-left:4px solid #6366f1;border-radius:32px;}\n"
        '</style><div class="hero"><h1>x</h1></div><div class="card">y</div></body></html>\n',
    )
    data = run_script("impeccable_detect_adapter.py", d, "index.html")
    assert_conforms(data, "impeccable")
    assert data["gate"] == "impeccable-detect", data["gate"]
    assert data["passed"] is True, (
        "impeccable: advisory gate must not block (passed=True)"
    )
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert "side-tab" in rules or "overused-font" in rules, (
        f"impeccable: expected side-tab/overused-font finding, got {rules} coverage={data.get('coverage')}"
    )
    # severity is INHERITED from detect (not assigned) — present on each finding.
    assert all(f.get("severity") for f in data["findings"]), (
        "impeccable: each finding must carry an inherited severity"
    )
    print(
        f"  impeccable: PASS ({len(rules)} finding(s) wrapped; side-tab/overused-font; severity inherited; advisory)"
    )


def smoke_spectral():
    # The Spectral adapter wraps the ARMED Stoplight Spectral CLI (external skill, armed per-project).
    # Skip (like impeccable) when Spectral is not armed.
    if not _armed_spectral():
        print(
            "  spectral: SKIP (Spectral not armed — run `npm i -D @stoplight/spectral-cli` in a fixture)"
        )
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_spec_")
    # An OpenAPI spec with a deliberate violation: an operation without a description
    # (`operation-description` is a default spectral:oas rule).
    write(
        f"{d}/openapi.json",
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "x", "version": "1"},
                "paths": {
                    "/users": {"get": {"responses": {"200": {"description": "ok"}}}}
                },
            }
        )
        + "\n",
    )
    data = run_script("spectral_adapter.py", d, ".")
    assert_conforms(data, "spectral")
    assert data["gate"] == "spectral-openapi", data["gate"]
    assert data["passed"] is True, (
        "spectral: advisory gate must not block (passed=True)"
    )
    assert data["findings"], (
        f"spectral: expected >=1 finding (operation-description), got none coverage={data.get('coverage')}"
    )
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "spectral: severity must collapse to warning (advisory)"
    )
    print(
        f"  spectral: PASS ({len(data['findings'])} finding(s); advisory; severity collapsed to warning)"
    )


def _armed_semgrep():
    return have("semgrep")


def smoke_semgrep():
    # The Semgrep adapter wraps the ARMED Semgrep CLI (external skill, armed per-project).
    # Skip (like spectral) when Semgrep is not armed. Uses a LOCAL fixture ruleset (offline).
    if not _armed_semgrep():
        print(
            "  semgrep: SKIP (Semgrep not armed — run `pip install semgrep` or `brew install semgrep`)"
        )
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_sg_")
    # A local ruleset (offline-deterministic) flagging eval(); a source file that trips it.
    write(
        f"{d}/.semgrep.yml",
        "rules:\n"
        "  - id: smoke-eval\n"
        "    pattern: eval(...)\n"
        "    message: eval is dangerous\n"
        "    languages: [python]\n"
        "    severity: WARNING\n",
    )
    write(f"{d}/app.py", 'def f():\n    return eval("1+1")\n')
    data = run_script("semgrep_adapter.py", d, ".")
    assert_conforms(data, "semgrep")
    assert data["gate"] == "semgrep-sast", data["gate"]
    assert data["passed"] is True, "semgrep: advisory gate must not block (passed=True)"
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("smoke-eval" in r for r in rules), (
        f"semgrep: expected smoke-eval finding, got {rules} coverage={data.get('coverage')}"
    )
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "semgrep: severity must collapse to warning (advisory)"
    )
    print(
        f"  semgrep: PASS ({len(rules)} finding(s); smoke-eval; advisory; severity collapsed to warning)"
    )


def _armed_vale():
    return have("vale")


def smoke_vale():
    # The Vale adapter wraps the ARMED Vale CLI (external skill, armed per-project).
    # Skip (like semgrep) when Vale is not armed. Uses a LOCAL fixture style (offline).
    if not _armed_vale():
        print(
            "  vale: SKIP (Vale not armed — run `brew install vale` or grab the GitHub release)"
        )
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_vale_")
    # A local .vale.ini + style flagging 'utilise'; a doc that trips it.
    # NOTE: Vale requires uppercase YES/NO booleans in .vale.ini — a lowercase `yes`
    # is treated as an unknown value and SILENTLY disables the rule (emits no alert).
    write(f"{d}/.vale.ini", "StylesPath = styles\n[*]\nTest.Substitution = YES\n")
    write(
        f"{d}/styles/Test/Substitution.yml",
        "extends: substitution\n"
        "message: \"Prefer '%s' over '%s'\"\n"
        "level: warning\n"
        "swap:\n"
        "  utilise: utilize\n",
    )
    write(f"{d}/doc.md", "We utilise this API.\n")
    data = run_script("vale_adapter.py", d, "doc.md")
    assert_conforms(data, "vale")
    assert data["gate"] == "vale-prose", data["gate"]
    assert data["passed"] is True, "vale: advisory gate must not block (passed=True)"
    rules = [f.get("rule", "") for f in data.get("findings", [])]
    assert any("test.substitution" in r.lower() for r in rules), (
        f"vale: expected Test.Substitution finding, got {rules} coverage={data.get('coverage')}"
    )
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "vale: severity must collapse to warning (advisory)"
    )
    print(
        f"  vale: PASS ({len(rules)} finding(s); Test.Substitution; advisory; severity collapsed to warning)"
    )


def smoke_oasdiff():
    # The oasdiff adapter diffs the working spec vs git HEAD. Skip when oasdiff is not armed.
    # Needs a real git repo with a tracked base spec + a breaking working-tree revision.
    if not have("oasdiff"):
        print("  oasdiff: SKIP (oasdiff not armed — run `brew install oasdiff`)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_oas_")
    for args in (
        ["git", "init", "-q"],
        ["git", "-C", d, "config", "user.email", "x@x.example"],
        ["git", "-C", d, "config", "user.name", "smoke"],
    ):
        subprocess.run(args, cwd=d, capture_output=True)
    base = {
        "openapi": "3.0.0",
        "info": {"title": "x", "version": "1"},
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["email", "name"],
                    "properties": {
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                    },
                }
            }
        },
    }
    write(f"{d}/openapi.json", json.dumps(base) + "\n")
    subprocess.run(["git", "-C", d, "add", "openapi.json"], capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "base"], capture_output=True)
    # Breaking revision: remove a previously-required response property.
    rev = json.loads(json.dumps(base))
    del rev["components"]["schemas"]["User"]["properties"]["name"]
    rev["components"]["schemas"]["User"]["required"] = ["email"]
    write(f"{d}/openapi.json", json.dumps(rev) + "\n")
    data = run_script("oasdiff_adapter.py", d, ".")
    assert_conforms(data, "oasdiff")
    assert data["gate"] == "openapi-breaking", data["gate"]
    assert data["passed"] is True, "oasdiff: advisory gate must not block (passed=True)"
    assert data["findings"], (
        f"oasdiff: expected a breaking-change finding, got none coverage={data.get('coverage')}"
    )
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "oasdiff: severity must collapse to warning (advisory)"
    )
    print(f"  oasdiff: PASS ({len(data['findings'])} breaking-change(s); advisory)")


def smoke_license():
    # The license adapter wraps Trivy's license scanner. Skip when Trivy is not armed.
    # License findings on a synthetic lockfile are Trivy-version-dependent, so we assert
    # structure (schema-valid + advisory) rather than a specific finding.
    if not have("trvy") and not have("trivy"):
        print("  license: SKIP (Trivy not armed — run `brew install trivy`)")
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_lic_")
    write(
        f"{d}/package.json",
        json.dumps(
            {"name": "smoke", "version": "1.0.0", "dependencies": {"left-pad": "1.3.0"}}
        )
        + "\n",
    )
    write(
        f"{d}/package-lock.json",
        json.dumps(
            {
                "lockfileVersion": 1,
                "dependencies": {"left-pad": {"version": "1.3.0", "license": "WTFPL"}},
            }
        )
        + "\n",
    )
    data = run_script("license_adapter.py", d, ".")
    assert_conforms(data, "license")
    assert data["gate"] == "license-compliance", data["gate"]
    assert data["passed"] is True, "license: advisory gate must not block (passed=True)"
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "license: severity must collapse to warning (advisory)"
    )
    print(f"  license: PASS ({len(data['findings'])} license finding(s); advisory)")


def smoke_iac():
    # The iac adapter wraps Checkov (Terraform/K8s/Dockerfile). Skip when not armed.
    # No-op when no IaC files; checkov findings on a synthetic .tf are version-dependent,
    # so we assert structure (schema-valid + advisory), not a specific check.
    if not have("checkov"):
        print(
            "  iac: SKIP (Checkov not armed — run `brew install checkov` or `pip install checkov`)"
        )
        return
    d = tempfile.mkdtemp(prefix="pdsmoke_iac_")
    # A bare S3 bucket trips several default checkov AWS checks (versioning/logging/acl).
    write(f"{d}/main.tf", 'resource "aws_s3_bucket" "b" {\n  bucket = "x"\n}\n')
    data = run_script("iac_adapter.py", d, ".")
    assert_conforms(data, "iac")
    assert data["gate"] == "iac-misconfig", data["gate"]
    assert data["passed"] is True, "iac: advisory gate must not block (passed=True)"
    assert all(f["severity"] == "warning" for f in data["findings"]), (
        "iac: severity must collapse to warning (advisory)"
    )
    print(f"  iac: PASS ({len(data['findings'])} misconfig finding(s); advisory)")


def smoke_fast_gate_guidance():
    # Option C behavioral coverage (fast-gate-format-advisory.plan.md fg-1; bc
    # outer-ring novel-2: no other test invokes fast_gate.py). A FORMAT failure's
    # block reason must carry the commit-stratification remediation (standalone
    # `style:` commit, C-pre); a LINT failure must keep the fix-in-ring wording.
    # SOLIDFORGE_PROJECT_DIR isolates the loop-state side effect (both fast_gate.py and
    # loop_state.py resolve state via SOLIDFORGE_PROJECT_DIR-or-cwd).
    if not have("ruff"):
        print("  fast-gate guidance: SKIP (ruff not installed)")
        return
    hook = os.path.join(ROOT, "infra", "hooks", "fast_gate.py")
    d = tempfile.mkdtemp(prefix="pdsmoke_fg_")
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=d)
    lint_fail = os.path.join(d, "lint_fail.py")  # F401 unused import, format-clean
    fmt_fail = os.path.join(d, "fmt_fail.py")  # lint-clean, format-dirty
    write(lint_fail, "import os\n")
    write(fmt_fail, "x=1\n")

    def run_hook(path):
        proc = subprocess.run(
            ["python3", hook],
            input=json.dumps({"tool_input": {"file_path": path}}),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert proc.stdout.strip(), (
            f"fast-gate emitted nothing for {path}: rc={proc.returncode} {proc.stderr}"
        )
        return json.loads(proc.stdout)

    lint_out = run_hook(lint_fail)
    assert lint_out.get("decision") == "block", lint_out
    lint_reason = lint_out.get("reason", "")
    assert "ruff check" in lint_reason, lint_reason
    assert "fix in the inner ring" in lint_reason, (
        "lint failure must positively carry the fix-in-ring guidance "
        "(guards against a vacuous absence-only assertion)"
    )
    assert "stratify" not in lint_reason.lower() and "style:" not in lint_reason, (
        "lint failure must keep fix-in-ring guidance, not format stratification"
    )

    fmt_out = run_hook(fmt_fail)
    assert fmt_out.get("decision") == "block", fmt_out
    fmt_reason = fmt_out.get("reason", "")
    assert "ruff format" in fmt_reason, fmt_reason
    assert "stratify" in fmt_reason.lower() and "style:" in fmt_reason, (
        "format failure must carry the commit-stratification remediation"
    )
    print("  fast-gate guidance: PASS (lint→fix-in-ring; format→stratify)")


def smoke_rust_edition():
    # tianwang-waf handoff (ported from upstream ADR #54, 2026-08-22): the hook
    # hardcoded `--edition 2021` and false-positived EVERY edit on edition-2024
    # projects (gate red while `cargo fmt --check` green — let-chains only valid
    # in 2024 — repeatedly tripping the thrashing breaker on phantom
    # violations). _rust_edition derives the edition from the file's nearest
    # manifest. A false-positive Blocker breaks gate truthfulness exactly like
    # a fake green (rule 3, both directions).
    hook = os.path.join(ROOT, "infra", "hooks", "fast_gate.py")
    sys.path.insert(0, os.path.dirname(hook))
    import fast_gate as fg  # __main__-guarded hook module; in-process for the unit layer

    def edition_of(tree, file_rel):
        d = tempfile.mkdtemp(prefix="pdsmoke_ed_")
        for rel, content in tree.items():
            write(os.path.join(d, rel), content)
        return fg._rust_edition(os.path.join(d, file_rel))

    assert (
        edition_of({"Cargo.toml": '[package]\nname="a"\nedition="2024"\n'}, "src/x.rs")
        == "2024"
    ), "direct [package].edition must win"
    assert (
        edition_of({"Cargo.toml": '[package]\nname="a"\nedition="2021"\n'}, "src/x.rs")
        == "2021"
    ), "direct 2021 must be honored (not upgraded)"
    assert (
        edition_of(
            {
                "Cargo.toml": '[workspace.package]\nedition="2024"\n[workspace]\nmembers=["m"]\n',
                "m/Cargo.toml": '[package]\nname="m"\nedition.workspace=true\n',
            },
            "m/src/x.rs",
        )
        == "2024"
    ), "edition.workspace=true must resolve via the ancestor [workspace.package]"
    assert (
        edition_of(
            {
                "Cargo.toml": '[workspace.package]\nedition="2024"\n',
                "m/Cargo.toml": '[package]\nname="m"\nedition={workspace=true}\n',
            },
            "m/src/x.rs",
        )
        == "2024"
    ), "the table-form inheritance spelling must resolve too"
    assert edition_of({}, "src/x.rs") == "2021", (
        "no manifest at all must keep the historical 2021 default"
    )
    assert (
        edition_of(
            {
                "Cargo.toml": '[package]\nname="root"\nedition="2024"\n',
                "m/Cargo.toml": '[package]\nname="m"\n',
            },
            "m/src/x.rs",
        )
        == "2021"
    ), "a silent member manifest must NOT poach an ancestor's edition"
    unit_note = "edition resolution PASS (6 cases)"

    if not have("rustfmt"):
        print(f"  rust edition: {unit_note}; e2e SKIP (rustfmt not installed)")
        return

    # e2e: an edition-2024 let-chains file must PASS the hook (the exact
    # historical false positive), while bare rustfmt --edition 2021 still
    # reproduces the incident error (pins the toolchain behavior the fix rests on).
    d = tempfile.mkdtemp(prefix="pdsmoke_ede2e_")
    write(
        os.path.join(d, "Cargo.toml"),
        '[package]\nname = "e2e"\nedition = "2024"\n',
    )
    write(
        os.path.join(d, "src", "x.rs"),
        "pub fn chk(x: Option<i32>, y: bool) -> i32 {\n"
        "    if let Some(v) = x\n"
        "        && y\n"
        "    {\n"
        "        v\n"
        "    } else {\n"
        "        0\n"
        "    }\n"
        "}\n",
    )
    src = os.path.join(d, "src", "x.rs")
    env = dict(os.environ, SOLIDFORGE_PROJECT_DIR=d)
    proc = subprocess.run(
        ["python3", hook],
        input=json.dumps({"tool_input": {"file_path": src}}),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    blocked = False
    if proc.stdout.strip():
        try:
            blocked = json.loads(proc.stdout).get("decision") == "block"
        except json.JSONDecodeError:
            blocked = True  # unparseable hook output is a failure, not a pass
    assert not blocked, (
        "edition-2024 let-chains file blocked by the fast gate (the historical "
        f"false positive): rc={proc.returncode} out={proc.stdout} err={proc.stderr}"
    )
    ctrl = subprocess.run(
        ["rustfmt", "--edition", "2021", "--check", src],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ctrl.returncode != 0 and "2024" in (ctrl.stdout + ctrl.stderr), (
        "the --edition 2021 control no longer reproduces the let-chains error — the toolchain changed; re-derive the fix's basis"
    )
    print(f"  rust edition: {unit_note}; e2e PASS (2024 file green, 2021 control red)")


def main():
    print("smoke_gates:")
    failures = []
    for fn in (
        smoke_python,
        smoke_rust,
        smoke_swift,
        smoke_web,
        smoke_java,
        smoke_go,
        smoke_deps_gitleaks,
        smoke_tests_cargo,
        smoke_nested,
        smoke_api,
        smoke_impeccable,
        smoke_spectral,
        smoke_semgrep,
        smoke_vale,
        smoke_oasdiff,
        smoke_license,
        smoke_iac,
        smoke_fast_gate_guidance,
        smoke_rust_edition,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__.replace('smoke_', '')}: FAIL — {e}")
        except Exception as e:
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__.replace('smoke_', '')}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print("\nAll available platform gates behave correctly.")


if __name__ == "__main__":
    main()
