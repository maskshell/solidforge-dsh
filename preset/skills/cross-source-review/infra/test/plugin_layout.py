#!/usr/bin/env python3
"""plugin_layout.py — plugin.json + agents well-formed gate (BLOCKER; rule 4).

Mirrors parallel-development's plugin_layout.py (rule 7 — copy the helper, do NOT
import a shared lib), adapted to this skill. cross-source-review ships its OWN
plugin.json (a skill-level manifest declaring name/version/description/the skill
entry + its agent). Phase A has NO hooks of its own — the convergence loop is
orchestrator-driven, NOT hook-driven — so there is no hooks.json. The hooks check
is therefore SKIPPED GRACEFULLY (rule 3 — declared in coverage, never faked) when
no hooks.json is present, rather than failing.

Checks:
  - plugin.json parses and has: name=cross-source-review, version, description,
    author as an object (a bare string fails the CC plugin loader — mirrors pd),
    and a `skills` entry listing this skill.
  - agents/*.agent.md frontmatter is well-formed: name + description present; no
    hardcoded model/max_turns (workspace rule + Agent Definition Conventions).
  - hooks.json (OPTIONAL): if present, parses + has PreToolUse/PostToolUse. If
    absent, skip with a coverage note (Phase A has no PostToolUse hooks).

Self-contained (rule 7): pure stdlib. Line-length discipline: all lines <=88 so
the file passes format --check under BOTH per-skill (88) and repo-root (100).

Usage:
    python3 infra/test/plugin_layout.py
"""

import glob
import json
import os
import sys

GATE = "plugin-layout"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
PLUGIN_JSON = os.path.join(ROOT, "plugin.json")
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
AGENTS_DIR = os.path.join(ROOT, "agents")

EXPECTED_PLUGIN_NAME = "cross-source-review"


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
    """plugin.json parses + has name/version/description/author/skills."""
    coverage.append("plugin.json:")
    if not os.path.exists(PLUGIN_JSON):
        findings.append(
            _finding(
                "plugin-json-missing",
                f"plugin.json missing at {PLUGIN_JSON}",
                f"create {PLUGIN_JSON} (mirror pd's plugin.json structure)",
            )
        )
        return
    raw = _read(PLUGIN_JSON)
    if raw is None:
        findings.append(
            _finding(
                "plugin-json-unreadable",
                f"plugin.json unreadable at {PLUGIN_JSON}",
                "check file permissions / encoding",
            )
        )
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        findings.append(
            _finding(
                "plugin-json-parse",
                f"plugin.json is not valid JSON: {exc}",
                "fix the JSON syntax",
            )
        )
        return
    if data.get("name") != EXPECTED_PLUGIN_NAME:
        findings.append(
            _finding(
                "plugin-json-name",
                f"name={data.get('name')!r} (expected {EXPECTED_PLUGIN_NAME!r})",
                f"set name to {EXPECTED_PLUGIN_NAME!r}",
            )
        )
    if not data.get("version"):
        findings.append(
            _finding(
                "plugin-json-version",
                "version missing/empty",
                "set a version (e.g. 0.1.0)",
            )
        )
    if not data.get("description"):
        findings.append(
            _finding(
                "plugin-json-description",
                "description missing/empty",
                "set a description",
            )
        )
    # author must be an OBJECT ({"name": ...}); a bare string fails the loader.
    if not isinstance(data.get("author"), dict):
        findings.append(
            _finding(
                "plugin-json-author",
                f"author={data.get('author')!r} (must be an object)",
                'set author to {"name": ...} (a bare string fails the loader)',
            )
        )
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        findings.append(
            _finding(
                "plugin-json-skills",
                "skills entry missing/not a list",
                "add a `skills` array listing this skill",
            )
        )
    else:
        names = [s.get("name") for s in skills if isinstance(s, dict)]
        if EXPECTED_PLUGIN_NAME not in names:
            findings.append(
                _finding(
                    "plugin-json-skill-entry",
                    f"skills list missing {EXPECTED_PLUGIN_NAME}: {names}",
                    f"add {{name: {EXPECTED_PLUGIN_NAME}, path: .}} to skills",
                )
            )
    coverage.append("  plugin.json: name/version/description/author/skills ok")


def _check_hooks(findings, coverage):
    """hooks.json OPTIONAL. Skip gracefully if absent (Phase A: no hooks)."""
    if not os.path.exists(HOOKS_JSON):
        coverage.append(
            "hooks: SKIP — no hooks.json (Phase A has no PostToolUse hooks; "
            "the convergence loop is orchestrator-driven, not hook-driven)."
        )
        return
    raw = _read(HOOKS_JSON)
    if raw is None:
        findings.append(
            _finding(
                "hooks-json-unreadable",
                f"hooks.json unreadable at {HOOKS_JSON}",
                "check file permissions / encoding",
            )
        )
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        findings.append(
            _finding(
                "hooks-json-parse",
                f"hooks.json is not valid JSON: {exc}",
                "fix the JSON syntax",
            )
        )
        return
    hooks = data.get("hooks", {})
    for event in ("PreToolUse", "PostToolUse"):
        if event not in hooks:
            findings.append(
                _finding(
                    "hooks-json-event",
                    f"hooks.json missing {event}",
                    f"add a {event} entry (or remove hooks.json to skip)",
                )
            )
    coverage.append("  hooks.json checked (PreToolUse/PostToolUse)")


def _check_agents(findings, coverage):
    """Skill-internal agents/*.agent.md frontmatter (OPTIONAL — doc-reviewer is plugin-level)."""
    coverage.append("agents/:")
    if not os.path.isdir(AGENTS_DIR):
        coverage.append(
            "no skill-internal agents/ — the same-family leg (doc-reviewer) is plugin-level at "
            "<repo-root>/agents/ (solidforge:doc-reviewer), mirroring solidforge:plan-reviewer"
        )
        return
    agent_files = sorted(glob.glob(os.path.join(AGENTS_DIR, "*.agent.md")))
    if not agent_files:
        coverage.append("no *.agent.md under skill agents/ (optional in Phase A)")
        return
    for af in agent_files:
        rel = os.path.relpath(af, ROOT)
        text = _read(af) or ""
        if not text.startswith("---"):
            findings.append(
                _finding(
                    "agent-frontmatter",
                    f"{rel}: no YAML frontmatter",
                    "add a --- -delimited frontmatter block",
                )
            )
            continue
        fm = text.split("---", 2)[1]
        fm_lines = fm.splitlines()
        for field in ("name", "description"):
            if not any(ln.startswith(f"{field}:") for ln in fm_lines):
                findings.append(
                    _finding(
                        "agent-frontmatter",
                        f"{rel}: frontmatter missing {field}:",
                        f"add `{field}:` (the agent trigger surface)",
                    )
                )
        # do NOT hardcode model/max_turns (workspace rule + global conventions)
        if any(ln.startswith("model:") for ln in fm_lines) or any(
            ln.startswith("max_turns:") for ln in fm_lines
        ):
            findings.append(
                _finding(
                    "agent-frontmatter",
                    f"{rel}: hardcodes model/max_turns",
                    "omit to inherit (workspace rule)",
                )
            )
    coverage.append(f"  {len(agent_files)} agent file(s) frontmatter checked")


def run():
    coverage = [
        "plugin-layout (BLOCKER, rule 4 codifiable): plugin.json parses + "
        "required fields + agents frontmatter. hooks.json optional (Phase A "
        "skip)."
    ]
    findings = []
    _check_plugin_manifest(findings, coverage)
    _check_hooks(findings, coverage)
    _check_agents(findings, coverage)
    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4)."""
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
