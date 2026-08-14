#!/usr/bin/env python3
"""adapter_shape_check_test.py — contract test for adapter_shape_check.py (rule 1).

Covers the gate's contract:
- validate_shape: violation-log.schema.json conformance (top-level + per-finding).
- check_adapter: import adapter, invoke emit() with mocks, capture stdout, validate.
- find_adapters / run: glob the 7 *_adapter.py; real adapters emit a valid shape (no blocker).
- emit: codifiable contract -> blocker exits non-zero, clean exits zero (rule 4).
"""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/parallel-development

_spec = importlib.util.spec_from_file_location(
    "adapter_shape_check", os.path.join(HERE, "adapter_shape_check.py")
)
assert _spec is not None and _spec.loader is not None
asc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asc)

VALID_ADAPTER = (
    "import json, sys\n"
    "GATE = 'test'\n"
    "def emit(findings, coverage):\n"
    "    passed = not any(f.get('severity') == 'blocker' for f in findings)\n"
    "    print(json.dumps({'gate': GATE, 'passed': passed, 'coverage': coverage, "
    "'findings': findings}))\n"
    "    sys.exit(0 if passed else 1)\n"
)
BAD_ADAPTER = "def emit(findings, coverage):\n    print('not json')\n    sys.exit(0)\n"
MISSING_EMIT = "x = 1\n"


def _write_adapter(tmp, name, src):
    sdir = os.path.join(tmp, "infra", "scripts")
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    return path


class TestValidateShape(unittest.TestCase):
    def test_valid_object_no_errors(self):
        obj = {"gate": "g", "passed": True, "coverage": [], "findings": []}
        self.assertEqual(asc.validate_shape(obj), [])

    def test_missing_top_field(self):
        obj = {"gate": "g", "passed": True, "coverage": []}
        self.assertTrue(any("findings" in e for e in asc.validate_shape(obj)))

    def test_bad_severity(self):
        obj = {
            "gate": "g",
            "passed": True,
            "coverage": [],
            "findings": [{"severity": "error"}],
        }
        errs = asc.validate_shape(obj)
        self.assertTrue(any("severity" in e for e in errs))

    def test_non_list_findings(self):
        obj = {"gate": "g", "passed": True, "coverage": [], "findings": "nope"}
        self.assertTrue(any("list" in e for e in asc.validate_shape(obj)))


class TestCheckAdapter(unittest.TestCase):
    def test_valid_adapter_no_errors(self):
        tmp = tempfile.mkdtemp()
        path = _write_adapter(tmp, "foo_adapter.py", VALID_ADAPTER)
        errors, _ = asc.check_adapter(path)
        self.assertEqual(errors, [])

    def test_bad_adapter_emits_errors(self):
        tmp = tempfile.mkdtemp()
        path = _write_adapter(tmp, "foo_adapter.py", BAD_ADAPTER)
        errors, _ = asc.check_adapter(path)
        self.assertTrue(len(errors) > 0)

    def test_missing_emit(self):
        tmp = tempfile.mkdtemp()
        path = _write_adapter(tmp, "foo_adapter.py", MISSING_EMIT)
        errors, _ = asc.check_adapter(path)
        self.assertTrue(any("emit" in e for e in errors))


class TestRunReal(unittest.TestCase):
    def test_find_adapters_returns_seven(self):
        self.assertEqual(len(asc.find_adapters(ROOT)), 7)

    def test_run_real_adapters_no_blocker(self):
        findings, coverage = asc.run(ROOT)
        self.assertFalse(any(f["severity"] == "blocker" for f in findings))
        self.assertTrue(len(coverage) > 0)


class TestEmit(unittest.TestCase):
    def _finding(self, severity):
        return {
            "severity": severity,
            "rule": "x",
            "file": "f",
            "line": 0,
            "detail": "d",
            "suggestion": "s",
        }

    def test_emit_blocker_exits_nonzero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                asc.emit([self._finding("blocker")], ["c"])
        self.assertEqual(cm.exception.code, 1)

    def test_emit_clean_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                asc.emit([], ["c"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
