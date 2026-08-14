#!/usr/bin/env python3
"""Unit tests for arch_contract_java.check_checkstyle rc-handling (rule 3: no silent green).

Checkstyle rc semantics: 0 = no violation; 1 = violations found (normal, XML output on
stdout, human summary on stderr); >=2 = config/invocation error (non-XML output).
check_checkstyle must degrade HONESTLY on rc>=2 / non-XML (a coverage note), NOT parse []
and report "0 violation(s) parsed" — that is a silent green. These tests pin the fix.
"""

import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))  # infra/test
ACJ = os.path.join(os.path.dirname(HERE), "scripts", "arch_contract_java.py")

_spec = importlib.util.spec_from_file_location("acj", ACJ)
assert _spec is not None and _spec.loader is not None
acj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acj)

CHECKSTYLE_XML = (
    '<?xml version="1.0"?><module name="Checker"><module name="TreeWalker">'
    '<module name="UnusedImports"/></module></module>'
)


def _java_project(tmp):
    os.makedirs(
        os.path.join(tmp, "src", "main", "java", "com", "example"), exist_ok=True
    )
    with open(os.path.join(tmp, "checkstyle.xml"), "w", encoding="utf-8") as fh:
        fh.write(CHECKSTYLE_XML)
    with open(
        os.path.join(tmp, "src", "main", "java", "com", "example", "S.java"),
        "w",
        encoding="utf-8",
    ) as fh:
        fh.write("package com.example; class S {}\n")


class TestCheckCheckstyleRcHandling(unittest.TestCase):
    def _run(self, rc, out):
        tmp = tempfile.mkdtemp()
        _java_project(tmp)
        findings, coverage = [], []
        orig_run, orig_resolve = acj.run, acj._resolve_checkstyle
        acj.run = lambda argv, cwd=None, timeout=600: (rc, out)
        acj._resolve_checkstyle = lambda root: ["checkstyle"]  # bypass PATH check
        try:
            acj.check_checkstyle(tmp, findings, coverage)
        finally:
            acj.run = orig_run
            acj._resolve_checkstyle = orig_resolve
        return findings, coverage

    def test_rc2_config_error_degrades_not_silent_green(self):
        findings, coverage = self._run(2, "checkstyle config error: invalid module\n")
        self.assertEqual(findings, [])
        self.assertTrue(
            any("unexpected rc=2" in c or "non-XML" in c for c in coverage),
            f"expected degrade note, got {coverage}",
        )
        self.assertFalse(
            any("0 violation(s) parsed" in c for c in coverage),
            "rc>=2 must NOT report '0 violation(s) parsed' (silent green)",
        )

    def test_rc0_clean_xml_no_finding(self):
        xml = '<?xml version="1.0"?><checkstyle version="13.7.0"></checkstyle>'
        findings, coverage = self._run(0, xml)
        self.assertEqual(findings, [])
        self.assertTrue(any("0 violation(s) parsed" in c for c in coverage))

    def test_rc1_with_finding_parsed_despite_stderr_summary(self):
        # rc=1 (violations) + the human summary on stderr that broke the old ET.fromstring
        xml = (
            '<?xml version="1.0"?><checkstyle version="13.7.0">'
            '<file name="S.java"><error line="1" severity="error" message="x" '
            'source="com.puppycrawl.tools.checkstyle.checks.imports.UnusedImportsCheck"/></file>'
            "</checkstyle>\nCheckstyle以 1 个错误结束."
        )
        findings, coverage = self._run(1, xml)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "UnusedImportsCheck")


if __name__ == "__main__":
    unittest.main()
