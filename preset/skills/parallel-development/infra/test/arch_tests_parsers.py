#!/usr/bin/env python3
"""Offline unit tests for arch_contract_tests parsers (no tools/network needed).

Run:
    python3 infra/test/arch_tests_parsers.py
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(ROOT, "infra")

_t = importlib.util.spec_from_file_location(
    "pd_tests", os.path.join(INFRA, "scripts", "arch_contract_tests.py")
)
tests = importlib.util.module_from_spec(_t)
_t.loader.exec_module(tests)

_v = importlib.util.spec_from_file_location(
    "pd_vschema", os.path.join(INFRA, "test", "violation_log_schema.py")
)
vschema = importlib.util.module_from_spec(_v)
_v.loader.exec_module(vschema)

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  {'ok' if cond else 'FAIL'}: {name}")


def conforms(findings):
    obj = {
        "gate": tests.GATE,
        "passed": not any(f.get("severity") == "blocker" for f in findings),
        "coverage": ["test"],
        "findings": findings,
    }
    return not vschema.validate(obj)


def t_pytest():
    report = {
        "tests": [
            {
                "nodeid": "tests/test_a.py::test_fail",
                "outcome": "failed",
                "call": {
                    "longrepr": "def test_fail():\n    assert 1 == 2\nE    assert 1 == 2"
                },
            },
            {"nodeid": "tests/test_b.py::test_ok", "outcome": "passed", "call": {}},
        ]
    }
    fs = tests.parse_pytest(report)
    check("pytest: 1 failed (passed ignored)", len(fs) == 1)
    check("pytest: file from nodeid", fs[0]["file"] == "tests/test_a.py")
    check("pytest: conforms", conforms(fs))


def t_vitest():
    report = {
        "testResults": [
            {
                "name": "src/a.test.ts",
                "assertionResults": [
                    {
                        "fullName": "a test",
                        "status": "failed",
                        "location": {"line": 5},
                        "failureMessages": ["expected 1 to be 2"],
                    }
                ],
            }
        ]
    }
    fs = tests.parse_vitest(report)
    check("vitest: 1 failed", len(fs) == 1)
    check("vitest: line from location", fs[0]["line"] == 5)
    check("vitest: conforms", conforms(fs))


def t_junit():
    xml = (
        '<testsuite name="s"><testcase classname="suite" name="test_x" file="tests/x.rs" line="3">'
        '<failure message="panicked at assertion">trace</failure></testcase>'
        '<testcase classname="suite" name="test_ok"/></testsuite>'
    )
    fs = tests.parse_junit_xml(xml)
    check("junit: 1 failure (passing ignored)", len(fs) == 1)
    check("junit: file + line", fs[0]["file"] == "tests/x.rs" and fs[0]["line"] == 3)
    check("junit: conforms", conforms(fs))


def t_junit_surefire():
    # Maven Surefire / Gradle test JUnit XML: <error> for thrown exceptions (vs <failure> for assertion failures), classname is the FQ test class, no file/line attrs. Proves the Java test gate's REUSED parser handles both shapes, and reconstructs the file path from the classname.
    xml = (
        '<testsuite name="com.example.SmokerTest" tests="1">'
        '<testcase classname="com.example.SmokerTest" name="failsWithNpe" time="0.01">'
        '<error type="java.lang.NullPointerException">java.lang.NullPointerException\n'
        "\tat com.example.Smoker.smoke(Smoker.java:5)</error></testcase></testsuite>"
    )
    fs = tests.parse_junit_xml(xml)
    check("junit-surefire: 1 error (passing ignored)", len(fs) == 1)
    check(
        "junit-surefire: file from classname", fs[0]["file"] == "com/example/SmokerTest"
    )
    check("junit-surefire: conforms", conforms(fs))


def t_swift():
    text = (
        '/path/T.swift:2: error: -[stests.T testF] : XCTAssertEqual failed: ("1") is not equal to ("2")\n'
        "Test Case failed\n"
    )
    fs = tests.parse_swift_test(text)
    check("swift: 1 failure", len(fs) == 1)
    check("swift: line 2", fs[0]["line"] == 2)
    check("swift: conforms", conforms(fs))


def t_cargo_text():
    text = (
        "running 1 test\n"
        "test fails_demo ... FAILED\n"
        "thread 'fails_demo' panicked at 'assertion failed: 1 == 2', src/lib.rs:4:5\n"
    )
    fs = tests.parse_cargo_test_text(text)
    check("cargo text: 1 panic", len(fs) == 1)
    check(
        "cargo text: file+line from panic",
        fs[0]["file"] == "src/lib.rs" and fs[0]["line"] == 4,
    )
    check("cargo text: conforms", conforms(fs))


def t_go_test():
    # `go test -json` NDJSON events: Action == 'fail' (a package or test failed) -> Blocker.
    # run/output/pass events are ignored. Under -race a data race also surfaces as
    # Action == 'fail' with the race in Output.
    ndjson = (
        '{"Action":"run","Test":"TestFoo"}\n'
        '{"Action":"output","Test":"TestFoo","Output":"main_test.go:5: failing\\n"}\n'
        '{"Action":"fail","Package":"example.com/foo","Test":"TestFoo",'
        '"Output":"--- FAIL: TestFoo (0.00s)\\n"}\n'
        '{"Action":"pass","Package":"example.com/bar"}\n'
    )
    fs = tests.parse_go_test(ndjson)
    check("go test: 1 fail (run/output/pass ignored)", len(fs) == 1)
    check("go test: package as file", fs[0]["file"] == "example.com/foo")
    check("go test: test name in detail", "TestFoo" in fs[0]["detail"])
    check("go test: blocker", fs[0]["severity"] == "blocker")
    check("go test: conforms", conforms(fs))


def t_ac_test_map():
    # Intent Blueprint "Acceptance-Criteria -> Test Mapping" reader (P4 baseline).
    # Value must be a test name / nodeid (NOT a bare file path) so the test-name set
    # gate (P1) can verify each mapped test exists. Arrow accepts `->` and `→`.
    bp = (
        "# Intent Blueprint — auth\n"
        "## Acceptance Criteria (BDD)\n"
        "- AC-1: Given ... Then ...\n"
        "- AC-2: Given ... Then ...\n"
        "## Acceptance-Criteria -> Test Mapping\n"
        "- AC-1 -> tests/test_auth.py::test_user_registration\n"
        "- AC-2 → test_login_redirect\n"
        "- AC-2 → test_login_redirect_302\n"
        "- bogus line with no arrow\n"
        "## Non-Functional Requirements\n"
        "- NFR-1 -> some prose arrow that must NOT be collected\n"
    )
    m = tests.parse_ac_test_map(bp)
    check(
        "ac_map: AC-1 nodeid value",
        m.get("AC-1") == ["tests/test_auth.py::test_user_registration"],
    )
    check(
        "ac_map: AC-2 both names (multi-bullet)",
        m.get("AC-2") == ["test_login_redirect", "test_login_redirect_302"],
    )
    check("ac_map: section-scoped (NFR prose arrow ignored)", "NFR-1" not in m)
    check(
        "ac_map: malformed line ignored",
        all("bogus" not in v for vs in m.values() for v in vs),
    )
    check(
        "ac_map: absent section -> {}",
        tests.parse_ac_test_map("# no mapping here\n## AC\n- AC-1\n") == {},
    )
    check("ac_map: empty -> {}", tests.parse_ac_test_map("") == {})
    # Header must carry an arrow; a loose title with the four words but no arrow
    # is NOT the mapping section.
    check(
        "ac_map: loose header (no arrow) not matched",
        tests.parse_ac_test_map(
            "## Acceptance Criteria to Test Mapping\n- AC-X -> test_y\n"
        )
        == {},
    )
    # An H1 following the section terminates it (decoy bullet under the H1 is
    # not collected); deeper headings (H3+) inside the section are content, not
    # terminators.
    check(
        "ac_map: H1 terminates section (decoy ignored)",
        tests.parse_ac_test_map(
            "## Acceptance-Criteria -> Test Mapping\n"
            "- AC-1 -> test_a\n"
            "# Appendix\n"
            "- AC-Z -> test_decoy\n"
        )
        == {"AC-1": ["test_a"]},
    )
    check(
        "ac_map: H3 subheading does not close section",
        tests.parse_ac_test_map(
            "## Acceptance-Criteria -> Test Mapping\n"
            "- AC-1 -> test_a\n"
            "### Notes\n"
            "- AC-2 -> test_b\n"
        )
        == {"AC-1": ["test_a"], "AC-2": ["test_b"]},
    )


def t_empty():
    check("pytest empty", tests.parse_pytest({}) == [])
    check("vitest empty", tests.parse_vitest({}) == [])
    check("junit empty/garbage", tests.parse_junit_xml("not xml") == [])
    check("swift empty", tests.parse_swift_test("") == [])
    check("cargo empty", tests.parse_cargo_test_text("") == [])
    check("go test empty", tests.parse_go_test("") == [])


def t_collect_pytest_names():
    # `pytest --collect-only -q` flat nodeid output; trailing summary skipped.
    text = (
        "tests/test_a.py::test_one\n"
        "tests/test_a.py::test_two\n"
        "tests/test_a.py::TestClass::test_three\n"
        "\n"
        "3 tests collected in 0.02s\n"
    )
    n = tests.collect_pytest_names(text)
    check("collect_pytest: 3 nodeids", len(n) == 3)
    check("collect_pytest: nodeid form", n[0] == "tests/test_a.py::test_one")
    check(
        "collect_pytest: class-param case kept",
        "tests/test_a.py::TestClass::test_three" in n,
    )
    check("collect_pytest: empty -> []", tests.collect_pytest_names("") == [])


def t_collect_rust_names():
    # `cargo test -- --list` -> `<fullname>: test` lines.
    text = "running 2 tests\ncrate::tests::test_a: test\ncrate::tests::test_b: test\n\n"
    n = tests.collect_rust_names(text)
    check("collect_rust: 2 names", len(n) == 2)
    check("collect_rust: strip ': test' suffix", n[0] == "crate::tests::test_a")
    check("collect_rust: empty -> []", tests.collect_rust_names("") == [])


def t_collect_go_names():
    # `go test -list . ./...` -> Test/Benchmark/Example/Fuzz names; per-package
    # `ok`/`FAIL`/`?` summary lines skipped.
    text = "TestFoo\nTestBar\nBenchmarkBaz\nok\texample.com/pkg\t0.001s\n"
    n = tests.collect_go_names(text)
    check("collect_go: Test+Bench only", n == ["TestFoo", "TestBar", "BenchmarkBaz"])
    # multi-package output: names from several packages with per-pkg ok/FAIL lines.
    mp = "TestA\nok\tpkg/a\t0.001s\nTestB\nTestC\nFAIL\tpkg/c\t0.500s\n"
    check(
        "collect_go: multi-package names",
        tests.collect_go_names(mp) == ["TestA", "TestB", "TestC"],
    )
    check("collect_go: empty -> []", tests.collect_go_names("") == [])


def t_collect_vitest_names():
    # `vitest list` best-effort: status glyph + `file > name` lines; summary skipped.
    text = (
        "✓ src/add.test.ts > add > adds two numbers\n"
        "✓ src/sub.test.ts > subtract\n"
        "Test Files  2 passed (2)\n"
    )
    n = tests.collect_vitest_names(text)
    check("collect_vitest: 2 names (summary skipped)", len(n) == 2)
    check("collect_vitest: file > name kept", n[1] == "src/sub.test.ts > subtract")
    check("collect_vitest: empty -> []", tests.collect_vitest_names("") == [])


def t_leaf_test_name():
    check("leaf: pytest nodeid", tests.leaf_test_name("tests/t.py::test_a") == "test_a")
    check(
        "leaf: pytest class case",
        tests.leaf_test_name("tests/t.py::TestX::test_b") == "test_b",
    )
    check(
        "leaf: vitest file>name", tests.leaf_test_name("src/t.test.ts > sub") == "sub"
    )
    check("leaf: no separator", tests.leaf_test_name("TestFoo") == "TestFoo")


def t_missing_mapped_tests():
    ac_map = {
        "AC-1": ["tests/test_auth.py::test_user_registration"],
        "AC-2": ["test_login_redirect", "test_gone"],
    }
    # Collected: full nodeid for AC-1; a leaf match for test_login_redirect;
    # test_gone absent (simulates a deleted/weakened test).
    full = {
        "tests/test_auth.py::test_user_registration",
        "tests/test_login.py::test_login_redirect",
    }
    leaf = {"test_login_redirect"}
    fs = tests.missing_mapped_tests(ac_map, full, leaf)
    check("diff: 1 missing (test_gone)", len(fs) == 1)
    check("diff: missing is blocker", fs[0]["severity"] == "blocker")
    check("diff: rule test-name-missing", fs[0]["rule"] == "test-name-missing")
    check(
        "diff: detail carries AC + name",
        "test_gone" in fs[0]["detail"] and "AC-2" in fs[0]["detail"],
    )
    check("diff: conforms", conforms(fs))
    # Full-form match suffices even with empty leaf set.
    check(
        "diff: full-form match ok",
        tests.missing_mapped_tests(
            {"AC-1": ["tests/test_auth.py::test_user_registration"]},
            {"tests/test_auth.py::test_user_registration"},
            set(),
        )
        == [],
    )
    # Leaf match suffices for a bare-name mapping.
    check(
        "diff: leaf match ok",
        tests.missing_mapped_tests(
            {"AC-1": ["test_login_redirect"]}, set(), {"test_login_redirect"}
        )
        == [],
    )
    check(
        "diff: empty map -> no findings",
        tests.missing_mapped_tests({}, full, leaf) == [],
    )


def t_parse_coverage_pytest():
    # pytest-cov / `coverage report` term output: TOTAL line carries the %.
    text = (
        "Name                Stmts   Miss  Cover\n"
        "src/a.py               50     10    80%\n"
        "src/b.py               50     25    50%\n"
        "TOTAL                 100     35    65%\n"
    )
    check("cov_pytest: TOTAL % parsed", tests.parse_coverage_pytest(text) == 65.0)
    check(
        "cov_pytest: no TOTAL -> None",
        tests.parse_coverage_pytest("nothing here") is None,
    )
    check("cov_pytest: empty -> None", tests.parse_coverage_pytest("") is None)


def t_parse_coverage_go():
    text = (
        "=== RUN   TestFoo\n"
        "ok  \texample.com/pkg\t0.001s\tcoverage: 72.5% of statements\n"
    )
    check("cov_go: % of statements", tests.parse_coverage_go(text) == 72.5)
    check(
        "cov_go: absent -> None", tests.parse_coverage_go("ok\tpkg\t0.001s\n") is None
    )
    # `go tool cover -func` aggregate — REAL format: `total:\t(statements)\tNN.N%`
    # (Go source cmd/cover/cover.go: Fprintf("total:\t(statements)\t%.1f%%")). The
    # literal "(statements)" column is what the real tool emits; a fabricated
    # `total:    75.0%` fixture would hide a regex that never matches real output.
    func = (
        "/path/a.go:10:    Foo          100.0%\n"
        "/path/a.go:20:    Bar           50.0%\n"
        "total:\t(statements)\t75.0%\n"
    )
    check("cov_go: cover -func total preferred", tests.parse_coverage_go(func) == 75.0)


def t_parse_coverage_rust():
    # cargo-tarpaulin `Result:` line is the aggregate.
    text = "INFO cargo_tarpaulin: Result: 62.50% coverage\n"
    check("cov_rust: Result aggregate", tests.parse_coverage_rust(text) == 62.5)
    check("cov_rust: absent -> None", tests.parse_coverage_rust("compiling...") is None)
    # Real output prints per-file `% coverage` lines BEFORE the Result aggregate;
    # the parser must take Result (50), not the first per-file line (100).
    multi = (
        "INFO cargo_tarpaulin: src/a.rs lines: 100.00% coverage\n"
        "INFO cargo_tarpaulin: src/b.rs lines:   0.00% coverage\n"
        "INFO cargo_tarpaulin: Result: 50.00% coverage (10/20)\n"
    )
    check(
        "cov_rust: Result not first per-file line",
        tests.parse_coverage_rust(multi) == 50.0,
    )
    # No Result line -> aggregate unknown -> None (degrade, rule 3).
    check(
        "cov_rust: no Result line -> None",
        tests.parse_coverage_rust("src/a.rs lines: 100.00% coverage\n") is None,
    )


def t_parse_coverage_vitest():
    # vitest coverage text table: the `All files` row's first % is overall stmts.
    text = (
        "| File        | % Stmts | % Branch | % Funcs | % Lines |\n"
        "|-------------|---------|----------|---------|---------|\n"
        "| All files   |   68.2  |    50    |   60    |   70    |\n"
    )
    check("cov_vitest: All files first %", tests.parse_coverage_vitest(text) == 68.2)
    check(
        "cov_vitest: absent -> None",
        tests.parse_coverage_vitest("Test Files 1\n") is None,
    )


def t_parse_blueprint_coverage_min():
    bp = (
        "# bp\n"
        "## Non-Functional Requirements\n"
        "- NFR-1: latency < 200ms\n"
        "- NFR-2: line coverage >= 80%\n"
        "- NFR-3: coverage minimum 75\n"
        "## Acceptance-Criteria -> Test Mapping\n"
        "- AC-1 -> cov_99%\n"
    )
    # The MAX declared coverage floor wins (80 from NFR-2; 75 from NFR-3).
    check("nfr_cov: max floor (80)", tests.parse_blueprint_coverage_min(bp) == 80.0)
    # Scoped to NFR section: a coverage % outside it is ignored.
    only_ac = "## Acceptance-Criteria -> Test Mapping\n- AC-1 -> cov_99%\n"
    check(
        "nfr_cov: absent in NFR -> None",
        tests.parse_blueprint_coverage_min(only_ac) is None,
    )
    check("nfr_cov: empty -> None", tests.parse_blueprint_coverage_min("") is None)
    # No threshold operator near "coverage" -> NOT a floor (rule 3: don't guess).
    # - "coverage tool version 7" (no op), "coverage scope is 3" (no op),
    #   "p99 latency" (not coverage-anchored), "branch coverage >= 95"
    #   (non-line metric the gate does not measure).
    noisy = (
        "# bp\n"
        "## Non-Functional Requirements\n"
        "- NFR-1: we use a test-coverage tool version 7 in CI\n"
        "- NFR-2: latency p99 < 200ms; the API coverage scope is 3 endpoints\n"
        "- NFR-3: branch coverage >= 95%\n"
    )
    check(
        "nfr_cov: no-op / non-line -> None",
        tests.parse_blueprint_coverage_min(noisy) is None,
    )


def t_coverage_finding():
    f = tests.coverage_finding("pytest", 60.0, 80.0, "tests")
    check(
        "cov_finding: below threshold -> warning",
        f is not None and f["severity"] == "warning",
    )
    check(
        "cov_finding: rule coverage-below-threshold",
        f is not None and f["rule"] == "coverage-below-threshold",
    )
    check(
        "cov_finding: assertion-quality caveat in detail",
        f is not None and "not assertion quality" in f["detail"],
    )
    check("cov_finding: conforms (warning ok)", conforms([f]) if f else False)
    # At/above threshold -> no finding.
    check(
        "cov_finding: meets threshold -> None",
        tests.coverage_finding("pytest", 80.0, 80.0, "tests") is None,
    )
    # No threshold declared -> no finding (measure-only default; rule 3).
    check(
        "cov_finding: no threshold -> None",
        tests.coverage_finding("pytest", 10.0, None, "tests") is None,
    )
    # No measurement -> no finding.
    check(
        "cov_finding: no measurement -> None",
        tests.coverage_finding("pytest", None, 80.0, "tests") is None,
    )


def main():
    for fn in (
        t_pytest,
        t_vitest,
        t_junit,
        t_junit_surefire,
        t_swift,
        t_cargo_text,
        t_go_test,
        t_ac_test_map,
        t_collect_pytest_names,
        t_collect_rust_names,
        t_collect_go_names,
        t_collect_vitest_names,
        t_leaf_test_name,
        t_missing_mapped_tests,
        t_parse_coverage_pytest,
        t_parse_coverage_go,
        t_parse_coverage_rust,
        t_parse_coverage_vitest,
        t_parse_blueprint_coverage_min,
        t_coverage_finding,
        t_empty,
    ):
        print(f"\n{fn.__name__}:")
        fn()
    failed = [n for n, ok in RESULTS if not ok]
    print(
        f"\n{'PASS' if not failed else 'FAIL'} ({len(RESULTS) - len(failed)}/{len(RESULTS)})"
    )
    if failed:
        for n in failed:
            print(f"  FAILED: {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
