#!/usr/bin/env python3
"""Offline unit tests for arch_contract_deps parsers (no network, no tools needed).

Feeds canned JSON to each pure parser and asserts the findings conform to the violation-log schema. Critically verifies gitleaks NEVER echoes the secret value.

Run:
    python3 infra/test/arch_deps_parsers.py
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(ROOT, "infra")

_dep = importlib.util.spec_from_file_location(
    "pd_deps", os.path.join(INFRA, "scripts", "arch_contract_deps.py")
)
deps = importlib.util.module_from_spec(_dep)
_dep.loader.exec_module(deps)

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
    """Wrap findings into a full gate emission and validate."""
    obj = {
        "gate": deps.GATE,
        "passed": not any(f.get("severity") == "blocker" for f in findings),
        "coverage": ["test"],
        "findings": findings,
    }
    return not vschema.validate(obj)


def t_gitleaks_redacts():
    violations = [
        {
            "RuleID": "aws-access-token",
            "File": "config/settings.py",
            "StartLine": 12,
            "Secret": "AKIAFAKESECRETKEY",
            "Match": "AKIAFAKESECRETKEY",
            "Description": "AWS Access Token",
        }
    ]
    fs = deps.parse_gitleaks(violations)
    check("gitleaks: 1 finding", len(fs) == 1)
    check("gitleaks: rule tagged", fs[0]["rule"] == "secret:aws-access-token")
    check("gitleaks: line", fs[0]["line"] == 12)
    check("gitleaks: severity blocker", fs[0]["severity"] == "blocker")
    check("gitleaks: secret NOT in detail", "AKIAFAKESECRETKEY" not in fs[0]["detail"])
    check("gitleaks: conforms", conforms(fs))


def t_pip_audit():
    report = {
        "dependencies": [
            {
                "name": "requests",
                "version": "2.20",
                "vulns": [
                    {
                        "id": "GHSA-9h6g-pr28-7cqp",
                        "fix_versions": ["2.21"],
                        "description": "RCE via crafted header",
                    }
                ],
            }
        ]
    }
    fs = deps.parse_pip_audit(report)
    check("pip-audit: 1 finding", len(fs) == 1)
    check("pip-audit: rule advisory id", fs[0]["rule"] == "vuln:GHSA-9h6g-pr28-7cqp")
    check("pip-audit: suggestion names fix", "2.21" in fs[0]["suggestion"])
    check("pip-audit: conforms", conforms(fs))


def t_npm_audit():
    report = {
        "vulnerabilities": {
            "lodash": {
                "severity": "critical",
                "range": "<4.17.12",
                "fixAvailable": True,
                "via": [{"source": 1234, "url": "https://npmjs.com/advisories/1234"}],
            }
        }
    }
    fs = deps.parse_npm_audit(report)
    check("npm audit: 1 finding", len(fs) == 1)
    check("npm audit: critical -> blocker", fs[0]["severity"] == "blocker")
    check("npm audit: rule source id", fs[0]["rule"] == "vuln:1234")
    check("npm audit: conforms", conforms(fs))


def t_npm_audit_low_severity():
    report = {
        "vulnerabilities": {
            "ansi-regex": {
                "severity": "low",
                "range": "<6",
                "fixAvailable": False,
                "via": ["GHSA-xx"],
            }
        }
    }
    fs = deps.parse_npm_audit(report)
    check("npm audit: low -> warning", fs and fs[0]["severity"] == "warning")
    check("npm audit: warning conforms", conforms(fs))


def t_cargo_audit():
    report = {
        "vulnerabilities": {
            "list": [
                {
                    "advisory": {
                        "id": "RUSTSEC-2021-0139",
                        "package": "serde",
                        "title": "Unsound transmute",
                    },
                    "versions": {"patched": ["1.0.100"]},
                }
            ]
        }
    }
    fs = deps.parse_cargo_audit(report)
    check("cargo audit: 1 finding", len(fs) == 1)
    check("cargo audit: rule RUSTSEC id", fs[0]["rule"] == "vuln:RUSTSEC-2021-0139")
    check("cargo audit: suggestion names patched", "1.0.100" in fs[0]["suggestion"])
    check("cargo audit: conforms", conforms(fs))


def t_dependency_check():
    # OWASP dependency-check JSON: Critical/High -> blocker, else warning.
    report = {
        "dependencies": [
            {
                "fileName": "commons-text-1.9.jar",
                "vulnerabilities": [
                    {
                        "name": "CVE-2022-42889",
                        "severity": "Critical",
                        "description": "Text4Shell RCE",
                    }
                ],
            }
        ]
    }
    fs = deps.parse_dependency_check(report)
    check("dependency-check: 1 finding", len(fs) == 1)
    check("dependency-check: critical -> blocker", fs[0]["severity"] == "blocker")
    check("dependency-check: rule CVE id", fs[0]["rule"] == "vuln:CVE-2022-42889")
    check("dependency-check: package in file", "commons-text" in fs[0]["file"])
    check("dependency-check: conforms", conforms(fs))


def t_dependency_check_low():
    report = {
        "dependencies": [
            {
                "fileName": "x-1.0.jar",
                "vulnerabilities": [
                    {
                        "name": "CVE-2021-1",
                        "severity": "Medium",
                        "description": "low-sev info leak",
                    }
                ],
            }
        ]
    }
    fs = deps.parse_dependency_check(report)
    check("dependency-check: medium -> warning", fs and fs[0]["severity"] == "warning")
    check("dependency-check: warning conforms", conforms(fs))


def t_govulncheck():
    # Real multi-line NDJSON: BOTH an osv line and a finding line that references it. A
    # finding carries only an OSV *id*; the parser must JOIN it to the osv entry's summary
    # (a finding-only or single-doc fixture would pass offline while real output yields
    # detail-less findings — the silent-green this test exists to catch).
    ndjson = (
        '{"osv": {"id": "GO-2023-1111", "summary": "RCE in foo via crafted input"}}\n'
        '{"finding": {"osv": "GO-2023-1111", "fixed_version": "1.2.3", '
        '"trace": [{"module": "example.com/foo", "package": "example.com/foo"}]}}\n'
    )
    fs = deps.parse_govulncheck(ndjson)
    check("govulncheck: 1 finding", len(fs) == 1)
    check("govulncheck: rule GO id", fs[0]["rule"] == "vuln:GO-2023-1111")
    check("govulncheck: reachable -> blocker", fs[0]["severity"] == "blocker")
    check("govulncheck: summary joined into detail", "RCE in foo" in fs[0]["detail"])
    check("govulncheck: fixed version in detail", "1.2.3" in fs[0]["detail"])
    check("govulncheck: conforms", conforms(fs))


def t_govulncheck_missing_osv():
    # A finding whose osv id has no preceding osv message (defensive): still a blocker,
    # detail falls back to the id (no crash).
    ndjson = '{"finding": {"osv": "GO-XXXX-YYYY", "trace": []}}\n'
    fs = deps.parse_govulncheck(ndjson)
    check("govulncheck-missing: 1 finding", len(fs) == 1)
    check("govulncheck-missing: blocker", fs[0]["severity"] == "blocker")
    check("govulncheck-missing: id in detail", "GO-XXXX-YYYY" in fs[0]["detail"])
    check("govulncheck-missing: conforms", conforms(fs))


def t_empty():
    check("gitleaks empty -> no findings", deps.parse_gitleaks([]) == [])
    check("pip-audit empty -> no findings", deps.parse_pip_audit({}) == [])
    check("npm audit empty -> no findings", deps.parse_npm_audit({}) == [])
    check("cargo audit empty -> no findings", deps.parse_cargo_audit({}) == [])
    check(
        "dependency-check empty -> no findings", deps.parse_dependency_check({}) == []
    )
    check("govulncheck empty -> no findings", deps.parse_govulncheck("") == [])


def main():
    for fn in (
        t_gitleaks_redacts,
        t_pip_audit,
        t_npm_audit,
        t_npm_audit_low_severity,
        t_cargo_audit,
        t_dependency_check,
        t_dependency_check_low,
        t_govulncheck,
        t_govulncheck_missing_osv,
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
