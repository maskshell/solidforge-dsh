#!/usr/bin/env python3
"""plugin_layout.py -- plugin.json + agents well-formed gate (BLOCKER; rule 4).

Mirrors primary-source-verification's plugin_layout.py (rule 7 -- copy the helper, do
NOT import a shared lib), adapted to prior-art-search. prior-art-search ships its OWN
plugin.json (name/version/description/the skill entry). Phase A has NO hooks of its own
-- the pipeline is orchestrator-driven, NOT hook-driven -- so no hooks.json; the hooks
check SKIPS GRACEFULLY (rule 3) when absent.

Checks:
  - plugin.json parses + has name=prior-art-search, version, description, author as an
    object, and a `skills` entry listing this skill.
  - agents/*.agent.md frontmatter (skill-internal, OPTIONAL -- prior-art-search's
    novelty-claim-extractor / collision-verifier are plugin-level at <repo-root>/agents/).

Self-contained (rule 7): pure stdlib.

Usage:
    python3 infra/test/plugin_layout.py
"""

import glob
import json
import os
import sys

GATE = "plugin-layout"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/prior-art-search
PLUGIN_JSON = os.path.join(ROOT, "plugin.json")
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
AGENTS_DIR = os.path.join(ROOT, "agents")

EXPECTED_PLUGIN_NAME = "prior-art-search"


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _finding(rule, detail, suggestion, severity="blocker"):
    return {
        "severity": severity,
        "rule": rule,
        "file": "plugin.json",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _check_plugin_manifest(findings, coverage):
    coverage.append("plugin.json:")
    if not os.path.exists(PLUGIN_JSON):
        findings.append(
            _finding(
                "plugin-json-missing",
                f"plugin.json missing at {PLUGIN_JSON}",
                "create it",
            )
        )
        return
    raw = _read(PLUGIN_JSON)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        findings.append(
            _finding("plugin-json-parse", f"not valid JSON: {exc}", "fix syntax")
        )
        return
    if data.get("name") != EXPECTED_PLUGIN_NAME:
        findings.append(
            _finding(
                "plugin-json-name",
                f"name={data.get('name')!r}",
                f"set {EXPECTED_PLUGIN_NAME!r}",
            )
        )
    if not data.get("version"):
        findings.append(
            _finding("plugin-json-version", "version missing", "set e.g. 0.1.0")
        )
    if not data.get("description"):
        findings.append(
            _finding(
                "plugin-json-description", "description missing", "set a description"
            )
        )
    if not isinstance(data.get("author"), dict):
        findings.append(
            _finding(
                "plugin-json-author", "author must be an object", 'set {"name": ...}'
            )
        )
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        findings.append(
            _finding(
                "plugin-json-skills", "skills missing/not a list", "add a skills array"
            )
        )
    else:
        names = [s.get("name") for s in skills if isinstance(s, dict)]
        if EXPECTED_PLUGIN_NAME not in names:
            findings.append(
                _finding(
                    "plugin-json-skill-entry",
                    f"skills missing {EXPECTED_PLUGIN_NAME}",
                    "add it",
                )
            )
    coverage.append("  plugin.json: name/version/description/author/skills ok")


def _check_hooks(findings, coverage):
    if not os.path.exists(HOOKS_JSON):
        coverage.append(
            "hooks: SKIP -- no hooks.json (Phase A has no hooks; the pipeline "
            "is orchestrator-driven, not hook-driven)."
        )
        return
    raw = _read(HOOKS_JSON)
    try:
        json.loads(raw)
        coverage.append("  hooks.json parses")
    except json.JSONDecodeError as exc:
        findings.append(
            _finding("hooks-json-parse", f"not valid JSON: {exc}", "fix syntax")
        )


def _check_agents(findings, coverage):
    coverage.append("agents/:")
    if not os.path.isdir(AGENTS_DIR):
        coverage.append(
            "no skill-internal agents/ -- prior-art-search's same-family legs "
            "(novelty-claim-extractor, collision-verifier) are plugin-level at "
            "<repo-root>/agents/ (solidforge:novelty-claim-extractor / "
            "solidforge:collision-verifier), mirroring psv's claim-extractor / "
            "claim-verifier"
        )
        return
    agent_files = sorted(glob.glob(os.path.join(AGENTS_DIR, "*.agent.md")))
    for af in agent_files:
        rel = os.path.relpath(af, ROOT)
        text = _read(af) or ""
        if not text.startswith("---"):
            findings.append(
                _finding("agent-frontmatter", f"{rel}: no frontmatter", "add ---")
            )
            continue
        fm = text.split("---", 2)[1]
        for field in ("name", "description"):
            if not any(ln.startswith(f"{field}:") for ln in fm.splitlines()):
                findings.append(
                    _finding(
                        "agent-frontmatter",
                        f"{rel}: missing {field}:",
                        f"add `{field}:`",
                    )
                )
        if any(
            ln.startswith("model:") or ln.startswith("max_turns:")
            for ln in fm.splitlines()
        ):
            findings.append(
                _finding(
                    "agent-frontmatter",
                    f"{rel}: hardcodes model/max_turns",
                    "omit to inherit",
                )
            )
    coverage.append(f"  {len(agent_files)} skill-internal agent file(s) checked")


def run():
    coverage = [
        "plugin-layout (BLOCKER, rule 4): plugin.json parses + required fields + "
        "agents frontmatter. hooks.json optional (Phase A skip)."
    ]
    findings = []
    _check_plugin_manifest(findings, coverage)
    _check_hooks(findings, coverage)
    _check_agents(findings, coverage)
    return findings, coverage


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


def main():
    findings, coverage = run()
    emit(findings, coverage)


if __name__ == "__main__":
    main()
