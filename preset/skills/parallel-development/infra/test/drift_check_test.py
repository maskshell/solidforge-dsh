#!/usr/bin/env python3
"""drift_check_test.py — contract test for drift_check.py (workspace rule 1).

Covers the gate's contract:
- normalize: strip comments + collapse whitespace (ODP-2).
- extract_function_body: AST-extract a named function's source (None if absent).
- diff_site: matching sibling set -> no finding; divergent -> warning; variation_allowed -> skipped.
- run: reads the real registry, never emits blocker (rule 4 advisory), coverage non-empty.
- emit: advisory -> always exit 0 (rule 4; drift is never blocker).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/parallel-development

_spec = importlib.util.spec_from_file_location(
    "drift_check", os.path.join(HERE, "drift_check.py")
)
assert _spec is not None and _spec.loader is not None
drift_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift_check)


def _write(tmp, rel, text):
    path = os.path.join(tmp, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return rel


class TestNormalize(unittest.TestCase):
    def test_strips_comments(self):
        n = drift_check.normalize("def f():\n    # a comment\n    return 1  # inline")
        self.assertNotIn("#", n)
        self.assertIn("return 1", n)

    def test_collapses_whitespace(self):
        # collapse \s+ -> single space: blank lines + extra indent become insignificant
        a = drift_check.normalize("def f():\n\n    return 1")
        b = drift_check.normalize("def f():\n return 1")
        self.assertEqual(a, b)


class TestExtractFunctionBody(unittest.TestCase):
    def test_gets_named_function(self):
        src = "def emit(f, c):\n    print('x')\n    sys.exit(0)\n"
        body = drift_check.extract_function_body(src, "emit")
        self.assertIsNotNone(body)
        self.assertIn("print", body)

    def test_missing_returns_none(self):
        self.assertIsNone(drift_check.extract_function_body("x = 1\n", "emit"))

    def test_syntax_error_returns_none(self):
        self.assertIsNone(drift_check.extract_function_body("def (\n", "emit"))


class TestDiffSite(unittest.TestCase):
    def _site(self, bodies, variation_allowed=False):
        tmp = tempfile.mkdtemp()
        siblings = [_write(tmp, f"sib{i}.py", src) for i, src in enumerate(bodies)]
        return {
            "name": "t",
            "kind": "function",
            "function": "emit",
            "siblings": siblings,
            "variation_allowed": variation_allowed,
        }, tmp

    def test_matching_siblings_no_finding(self):
        body = "def emit(f, c):\n    print(1)\n"
        site, tmp = self._site([body, body, body])
        findings, _ = drift_check.diff_site(site, tmp)
        self.assertEqual(findings, [])

    def test_divergent_sibling_warning(self):
        body_a = "def emit(f, c):\n    print(1)\n"
        body_b = "def emit(f, c):\n    print(2)\n"
        site, tmp = self._site([body_a, body_a, body_b])
        findings, _ = drift_check.diff_site(site, tmp)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "warning")
        self.assertIn("diverge", findings[0]["rule"])

    def test_variation_allowed_skipped(self):
        site, tmp = self._site(
            ["def emit(f, c):\n    print(1)\n", "def emit(f, c):\n    print(2)\n"],
            variation_allowed=True,
        )
        findings, _ = drift_check.diff_site(site, tmp)
        self.assertEqual(findings, [])

    def test_missing_sibling_no_crash(self):
        site, tmp = self._site(["def emit(f, c):\n    print(1)\n"])
        site["siblings"].append("does/not/exist.py")
        findings, bit = drift_check.diff_site(site, tmp)
        # 1 present + 1 missing -> no drift, no finding (the contract)
        self.assertEqual(findings, [])
        # the missing sibling surfaces in coverage, not silently dropped
        self.assertIn("not found", bit)


class TestRunRealRegistry(unittest.TestCase):
    """Integration: real drift_registry.json + real adapter sources."""

    def test_run_no_blocker_and_coverage(self):
        reg = os.path.join(HERE, "drift_registry.json")
        findings, coverage = drift_check.run(reg, ROOT)
        self.assertFalse(any(f["severity"] == "blocker" for f in findings))
        self.assertTrue(len(coverage) > 0)

    def test_run_missing_registry_no_op(self):
        findings, coverage = drift_check.run(os.path.join(HERE, "nope_dne.json"), ROOT)
        self.assertEqual(findings, [])
        self.assertTrue(any("not found" in c or "skipped" in c for c in coverage))


class TestEmit(unittest.TestCase):
    def test_cli_exits_zero_advisory(self):
        script = os.path.join(HERE, "drift_check.py")
        proc = subprocess.run([sys.executable, script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        obj = json.loads(proc.stdout)
        self.assertEqual(obj["gate"], "drift-check")
        self.assertIn("coverage", obj)
        self.assertIn("findings", obj)


if __name__ == "__main__":
    unittest.main()
