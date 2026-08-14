#!/usr/bin/env python3
"""disconnect_check.py -- structure + loading-chain gate for prior-art-search.

Adapts primary-source-verification's disconnect_check.py (rule 7 -- copy the helper,
do NOT import a shared lib) to prior-art-search's layout. Verifies the skill is
structurally wired and the LOADING CHAIN is unbroken: each capability reachable at the
POINT OF NEED.

Checks:
  - SKILL.md frontmatter: name + description; Scope Guard section present.
  - Loading chain: SKILL.md routes to each authority doc, and each exists.
  - Required infra files present (2 schemas, 2 scripts, 6 self-gates, plugin.json,
    ruff.toml, references/install.md).
  - solidforge:novelty-claim-extractor + solidforge:collision-verifier are plugin-level
    at <repo-root>/agents/; their backing files' frontmatter checked.
  - Link integrity across SKILL.md + docs/.

dogfood.py (NC-I6) is in the required set -- the offline fixture gate ships with
the skill; the live N>=3 run is the human acceptance criterion. Self-contained
(rule 7): pure stdlib.

Usage:
    python3 infra/test/disconnect_check.py
"""

import json
import os
import re
import sys

GATE = "disconnect-check"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/prior-art-search
DOCS = os.path.join(ROOT, "docs")
SKILL = os.path.join(ROOT, "SKILL.md")

AUTHORITY_DOCS = ["proposal.md", "iteration-plan.md", "proposal.convergence.md"]

REQUIRED_FILES = {
    "plugin.json": "the skill plugin manifest",
    "ruff.toml": "the per-skill dev lint config (mirrors psv/csr/pd)",
    "references/install.md": "the credential-surface + provisioning guide",
    "infra/schemas/collision-findings.schema.json": (
        "the per-claim collision-findings contract (extends psv)"
    ),
    "infra/schemas/collision-record.schema.json": (
        "the top-line collision-coverage disclosure contract"
    ),
    "infra/scripts/search_prior_art.py": "the prior-art search primitive (NC-I3)",
    "infra/scripts/coverage_driver.py": "the deterministic coverage core (NC-I4)",
    "infra/test/disconnect_check.py": "this gate (self)",
    "infra/test/plugin_layout.py": "the plugin-layout gate",
    "infra/test/findings_shape_check.py": "the shape-contract gate (NC-I5b)",
    "infra/test/coverage_policy_check.py": "the coverage-policy gate (NC-I5c)",
    "infra/test/fetched_quote_gate.py": (
        "the collision fetched-quote invariant gate (NC-I5a)"
    ),
    "infra/test/lint_self.py": "the dogfood lint gate",
    "infra/test/dogfood.py": "the dogfood gate (NC-I6)",
}

# prior-art-search's same-family legs are PLUGIN-LEVEL (repo-root agents/), like psv's.
PLUGIN_AGENTS = ["novelty-claim-extractor", "collision-verifier"]

MAX_DESC_LEN = 1024


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _exists(path):
    return os.path.exists(path)


def _finding(rule, detail, suggestion, severity="blocker"):
    file_ = detail.split(" -> ")[0].split(":")[0] if " -> " in detail else "SKILL.md"
    return {
        "severity": severity,
        "rule": rule,
        "file": file_,
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _description_text(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    fm = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm.append(line)
    i = 0
    while i < len(fm) and not fm[i].startswith("description:"):
        i += 1
    if i >= len(fm):
        return ""
    head = fm[i][len("description:") :].strip()
    if head in ("|", ">", ""):
        body = []
        for line in fm[i + 1 :]:
            if line[:1] in (" ", "\t") or line.strip() == "":
                body.append(line.strip())
            else:
                break
        return " ".join(b for b in body if b)
    return head


def _check_agent(repo_root, name, findings, coverage):
    af = os.path.join(repo_root, "agents", f"{name}.agent.md")
    if not _exists(af):
        findings.append(
            _finding(
                "agent-missing",
                f"solidforge:{name} backing file missing at agents/{name}.agent.md",
                "register at plugin level",
            )
        )
        return
    atext = _read(af) or ""
    if not atext.startswith("---"):
        findings.append(
            _finding("agent-frontmatter", f"{name}.agent.md: no frontmatter", "add ---")
        )
        return
    fm = atext.split("---", 2)[1]
    fm_lines = fm.splitlines()
    for field in ("name", "description", "tools", "disallowedTools"):
        if not any(ln.startswith(f"{field}:") for ln in fm_lines):
            findings.append(
                _finding(
                    "agent-frontmatter",
                    f"{name}.agent.md missing {field}:",
                    f"add `{field}:`",
                )
            )
    if any(ln.startswith("model:") or ln.startswith("max_turns:") for ln in fm_lines):
        findings.append(
            _finding(
                "agent-frontmatter",
                f"{name}.agent.md hardcodes model/max_turns",
                "omit to inherit",
            )
        )
    coverage.append(f"  solidforge:{name} frontmatter ok")


def run():
    coverage = [
        "disconnect-check (BLOCKER, rule 4): structure + loading chain. SKILL.md "
        "frontmatter + Scope Guard, authority docs, required infra, both agent "
        "frontmatters, link integrity."
    ]
    findings = []
    skill = _read(SKILL) or ""
    lines = skill.splitlines()

    if not lines or lines[0].strip() != "---":
        findings.append(
            _finding("frontmatter", "SKILL.md has no YAML frontmatter", "add ---")
        )
    else:
        fm = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            fm.append(line)
        if not any(ln.startswith("name:") for ln in fm):
            findings.append(
                _finding(
                    "frontmatter",
                    "frontmatter missing name:",
                    "add `name: prior-art-search`",
                )
            )
        desc = _description_text(skill)
        if not desc:
            findings.append(
                _finding(
                    "frontmatter",
                    "frontmatter missing description:",
                    "add a description",
                )
            )
        elif len(desc) > MAX_DESC_LEN:
            findings.append(
                _finding(
                    "frontmatter",
                    f"description {len(desc)} chars (>{MAX_DESC_LEN})",
                    "trim",
                )
            )

    if "Scope Guard" not in skill:
        findings.append(
            _finding(
                "scope-guard",
                "no Scope Guard section",
                "add one (route to pd/bc/csr/psv/this)",
            )
        )

    for doc in AUTHORITY_DOCS:
        doc_path = os.path.join(DOCS, doc)
        if not _exists(doc_path):
            findings.append(
                _finding(
                    "loading-chain",
                    f"authority doc missing: docs/{doc}",
                    f"create docs/{doc}",
                )
            )
        elif f"docs/{doc}" not in skill:
            findings.append(
                _finding(
                    "loading-chain",
                    f"LOADING-CHAIN BREAK: SKILL.md does not reference docs/{doc}",
                    f"link docs/{doc}",
                )
            )

    missing = [rel for rel in REQUIRED_FILES if not _exists(os.path.join(ROOT, rel))]
    for rel in missing:
        findings.append(
            _finding(
                "required-file", f"missing {rel}", f"create it ({REQUIRED_FILES[rel]})"
            )
        )
    coverage.append(
        f"required files: {len(REQUIRED_FILES) - len(missing)}/{len(REQUIRED_FILES)} present"
    )

    repo_root = os.path.dirname(os.path.dirname(ROOT))
    coverage.append("plugin-level agents:")
    for name in PLUGIN_AGENTS:
        _check_agent(repo_root, name, findings, coverage)

    md_files = [SKILL]
    if _exists(DOCS):
        md_files += [
            os.path.join(DOCS, f) for f in os.listdir(DOCS) if f.endswith(".md")
        ]
    link_re = re.compile(r"\]\(([^)]+\.md[^)]*)\)")
    fenced_re = re.compile(r"```.*?```", re.DOTALL)
    inline_re = re.compile(r"`[^`\n]*`")
    for md in md_files:
        text = _read(md) or ""
        clean = inline_re.sub("", fenced_re.sub("", text))
        base = os.path.dirname(md)
        for tgt in link_re.findall(clean):
            if tgt.startswith("http"):
                continue
            path = tgt.split("#")[0]
            if path and not _exists(os.path.join(base, path)):
                findings.append(
                    _finding(
                        "link-integrity",
                        f"broken link in {os.path.relpath(md, ROOT)} -> {tgt}",
                        "fix the link",
                    )
                )

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
