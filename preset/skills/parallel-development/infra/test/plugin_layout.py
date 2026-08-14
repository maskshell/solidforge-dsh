#!/usr/bin/env python3
"""Preset-layout self-check for the SolidForge DSH port.

Loading-chain check for the PRESET BOUNDARY (the DSH analog of the upstream
plugin-layout check). Asserts the preset's structural pieces exist and are
well-formed so an agent following progressive disclosure from preset mount
never hits a dead end:

  - agent.cordis.yml exists (the composition), mentions the preset's key rows,
    and does NOT carry a process-global-provider row (tool-cordis — would
    collide with the `cordis` preset in a multi-preset process)
  - preset.yml exists with a name + description
  - skills/ contains the five SolidForge skills, each with SKILL.md frontmatter
  - agents/ contains the 22 role-agent prompt files (by frontmatter name)
  - every agent referencing a references/agent-patterns/<role>.md companion has
    that companion bundled under skills/parallel-development/references/
  - commands/arm-tools.md exists
  - plugins/*.host.js exist and carry a BAKED preset root (no
    __SOLIDFORGE_PRESET_ROOT__ placeholder left)

Structural checks only (files present + well-formed); runtime resolution is the
mount-validation probe's job.

Run:
    python3 infra/test/plugin_layout.py
"""

import glob
import os
import re
import sys


def _find_preset_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, "agent.cordis.yml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:  # filesystem root reached
            return None
        cur = parent


_HERE = os.path.dirname(os.path.abspath(__file__))
PRESET_ROOT = _find_preset_root(_HERE)
if PRESET_ROOT is None:
    sys.exit("FAIL: no agent.cordis.yml found walking up from " + _HERE)

EXPECTED_SKILLS = [
    "parallel-development",
    "blueprint-crafting",
    "cross-source-review",
    "primary-source-verification",
    "prior-art-search",
]

EXPECTED_AGENTS = [
    "architect",
    "backend-developer",
    "claim-extractor",
    "claim-verifier",
    "code-reviewer",
    "collision-verifier",
    "devops-engineer",
    "doc-reviewer",
    "documentation-writer",
    "frontend-developer",
    "graphiti-config-generator",
    "ios-developer",
    "ios-tester",
    "novelty-claim-extractor",
    "plan-reviewer",
    "playwright-test-generator",
    "playwright-test-healer",
    "playwright-test-planner",
    "requirements-manager",
    "researcher",
    "security-specialist",
    "tester",
]

FRONTMATTER_NAME_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^\s*name\s*:\s*([a-z0-9-]+)\s*$", re.MULTILINE)

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("  FAIL:", msg)
    else:
        print("  ok:", msg)


def frontmatter_name(path):
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(2048)
    except OSError:
        return None
    m = FRONTMATTER_NAME_RE.match(head)
    if not m:
        return None
    nm = NAME_RE.search(m.group(1))
    return nm.group(1) if nm else None


def main():
    print("SolidForge DSH preset layout check (root:", PRESET_ROOT, ")")

    # 1. composition + metadata
    comp = os.path.join(PRESET_ROOT, "agent.cordis.yml")
    check(os.path.exists(comp), "agent.cordis.yml exists")
    if os.path.exists(comp):
        with open(comp, encoding="utf-8") as fh:
            comp_text = fh.read()
        check("dsh-persona" in comp_text, "composition carries the persona row")
        check(
            "dsh-skill-filesystem" in comp_text, "composition carries skill-filesystem"
        )
        check("tool-subagent" in comp_text, "composition carries the delegation tools")
        check(
            "dsh-tool-cordis" not in comp_text,
            "composition carries NO tool-cordis row (process-global provider collision guard)",
        )
    meta = os.path.join(PRESET_ROOT, "preset.yml")
    check(os.path.exists(meta), "preset.yml exists")
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as fh:
            mt = fh.read()
        check(
            "name:" in mt and "description:" in mt, "preset.yml has name + description"
        )

    # 2. skills
    for skill in EXPECTED_SKILLS:
        skill_md = os.path.join(PRESET_ROOT, "skills", skill, "SKILL.md")
        check(os.path.exists(skill_md), f"skill {skill}/SKILL.md exists")
        if os.path.exists(skill_md):
            nm = frontmatter_name(skill_md)
            check(nm == skill, f"skill {skill} frontmatter name matches ({nm})")

    # 3. agents
    for agent in EXPECTED_AGENTS:
        agent_md = os.path.join(PRESET_ROOT, "agents", f"{agent}.agent.md")
        check(os.path.exists(agent_md), f"agent {agent}.agent.md exists")
        if os.path.exists(agent_md):
            nm = frontmatter_name(agent_md)
            check(nm == agent, f"agent {agent} frontmatter name matches ({nm})")

    # 4. agent -> pattern companion loading chain
    patterns_dir = os.path.join(
        PRESET_ROOT, "skills", "parallel-development", "references", "agent-patterns"
    )
    for agent_md in glob.glob(os.path.join(PRESET_ROOT, "agents", "*.agent.md")):
        with open(agent_md, encoding="utf-8") as fh:
            text = fh.read()
        for ref in re.findall(r"agent-patterns/([a-z0-9-]+)\.md", text):
            check(
                os.path.exists(os.path.join(patterns_dir, ref + ".md")),
                f"agent {os.path.basename(agent_md)} companion agent-patterns/{ref}.md bundled",
            )

    # 5. command
    check(
        os.path.exists(os.path.join(PRESET_ROOT, "commands", "arm-tools.md")),
        "commands/arm-tools.md exists",
    )

    # 6. plugin sources (installed form: baked under the preset root; workspace
    # source form: the port repo's sibling plugins/ dir carries placeholders)
    plugin_dir = os.path.join(PRESET_ROOT, "plugins")
    baked = True
    if not os.path.isdir(plugin_dir):
        plugin_dir = os.path.join(os.path.dirname(PRESET_ROOT), "plugins")
        baked = False
    plugin_files = sorted(glob.glob(os.path.join(plugin_dir, "*.host.js")))
    check(
        len(plugin_files) == 4,
        "four plugin sources bundled (" + str(len(plugin_files)) + ")",
    )
    for pf in plugin_files:
        with open(pf, encoding="utf-8") as fh:
            text = fh.read()
        if baked:
            check(
                "__SOLIDFORGE_PRESET_ROOT__" not in text,
                f"plugin {os.path.basename(pf)} has baked preset root",
            )
        m = re.search(r"const PRESET_ROOT = '([^']+)'", text)
        check(
            m is not None and (os.path.isabs(m.group(1)) or not baked),
            f"plugin {os.path.basename(pf)} preset root is absolute",
        )

    if failures:
        sys.exit(f"FAIL: {len(failures)} layout check(s) failed")
    print("PASS")


if __name__ == "__main__":
    main()
