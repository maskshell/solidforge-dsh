#!/usr/bin/env python3
"""disconnect_check.py — structure + loading-chain gate for cross-source-review.

Adapts blueprint-crafting's disconnect_check.py (rule 7 — copy the helper, do NOT
import a shared lib) to this skill's doc-centric layout. Verifies the skill is
structurally wired and the LOADING CHAIN is unbroken at every authority doc — i.e.
each capability is reachable at the POINT OF NEED, not just from some doc. This is
what prevents a model following progressive disclosure (description -> SKILL.md ->
docs/) from hitting a dead end.

Checks (additive; grows as CSR-I6 lands):
  - SKILL.md frontmatter: name + description present; Scope Guard section present.
  - Loading chain: SKILL.md routes to each authority doc (proposal.md /
    iteration-plan.md / proposal.convergence.md), and each exists.
  - Required infra files present (schemas, scripts, fixtures, profiles, the 6
    self-gates, plugin.json, ruff.toml).
  - solidforge:doc-reviewer (the same-family leg) is plugin-level at <repo-root>/agents/
    (mirrors solidforge:plan-reviewer); its backing file frontmatter is checked:
    name + description + tools + disallowedTools; no hardcoded model/max_turns.
  - Link integrity: no broken markdown links across SKILL.md + docs/.

Self-contained (rule 7): pure stdlib. Line-length discipline: all lines <=88 so
the file passes format --check under BOTH per-skill (88) and repo-root (100)
configs.

Usage:
    python3 infra/test/disconnect_check.py
"""

import json
import os
import re
import sys

GATE = "disconnect-check"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
DOCS = os.path.join(ROOT, "docs")
INFRA = os.path.join(ROOT, "infra")
SKILL = os.path.join(ROOT, "SKILL.md")

# Authority docs SKILL.md MUST reference + that MUST exist (loading chain).
AUTHORITY_DOCS = ["proposal.md", "iteration-plan.md", "proposal.convergence.md"]

# Structural pieces (rule 8 — the FULL loading chain). Each must exist.
REQUIRED_FILES = {
    "plugin.json": "the skill plugin manifest (name/version/description)",
    "ruff.toml": "the per-skill dev lint config (skill root, mirrors pd)",
    "references/install.md": "the provisioning + custom-provider guide (portable arming)",
    "infra/schemas/doc-findings.schema.json": "the findings output contract",
    "infra/schemas/convergence-record.schema.json": "the convergence-record contract",
    "infra/scripts/hetero_doc_review.py": "the different-family leg substrate (CSR-I3)",
    "infra/scripts/hetero_doc_review.divergence.md": (
        "the substrate divergence log (rule 7 copy-pattern trail)"
    ),
    "infra/scripts/converge.py": "the deterministic convergence-policy engine",
    "infra/scripts/profiles/zai-coding-cn.json": "worked dsh-substrate profile (catalog route; the default is FAIL-FAST, not a template)",
    "infra/scripts/profiles/minimax-cn.json": "worked dsh-substrate profile (catalog route)",
    "infra/scripts/profiles/qwen-token-plan-cn.json": "dsh-substrate placeholder (multi-family gateway route)",
    "infra/scripts/profiles/claude.json": "external-harness opt-in (native auth)",
    "infra/scripts/profiles/qwen.json": "external-harness opt-in (Anthropic-compatible repointing)",
    "infra/scripts/converge_fixtures/converged.json": "fixture: BOTH prongs pass",
    "infra/scripts/converge_fixtures/stalemate.json": "fixture: prong_b fails",
    "infra/scripts/converge_fixtures/core_claims_uncovered.json": (
        "fixture: prong_a fails (load-bearing)"
    ),
    "infra/scripts/converge_fixtures/degraded.json": "fixture: hetero-degraded reconcile",
    "infra/scripts/converge_fixtures/warnings_dont_block.json": (
        "fixture: rule 4 warnings never block"
    ),
    "infra/scripts/converge_fixtures/verify.py": "the CSR-I4 offline verify harness",
    "infra/scripts/converge_fixtures/README.md": "the fixtures documentation",
    "infra/test/disconnect_check.py": "this gate (self)",
    "infra/test/findings_shape_check.py": "the findings shape-contract gate",
    "infra/test/convergence_policy_check.py": "the offline convergence-policy gate",
    "infra/test/lint_self.py": "the dogfood lint gate",
    "infra/test/plugin_layout.py": "the plugin-layout gate",
    "infra/test/dogfood.py": "the dogfood convergence-loop gate (skip path)",
}

MAX_DESC_LEN = 1024
MAX_SKILL_LINES = 500


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _exists(path):
    return os.path.exists(path)


def _description_text(text):
    """Lowercased description value from YAML frontmatter (block + inline).

    Line-based parse to avoid regex newline traps (mirrors bc / pd)."""
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


def run():
    coverage = [
        "disconnect-check (BLOCKER, rule 4 codifiable): structure + loading "
        "chain. SKILL.md frontmatter + Scope Guard, authority docs, required "
        "infra, agent frontmatter, link integrity."
    ]
    findings = []
    skill = _read(SKILL) or ""

    # --- different-family profile-hardcode guard (external-app regression) ---
    # SKILL.md's step-2 command MUST NOT hardcode `--profile <name>`: a CLI arg
    # silently drops every other provider configured via HETERO_DOC_PROFILE
    # (e.g. a dual-different-family .env.solidforge — regression 2026-08-11).
    # The wrapper resolves the provider(s) itself; the instruction text may only
    # reference the selector and defaults, never pass a concrete profile.
    hardcoded_profile = re.findall(r"--profile [A-Za-z][A-Za-z0-9_,]*", skill)
    if hardcoded_profile:
        findings.append(
            _finding(
                "profile-hardcode",
                f"SKILL.md hardcodes {hardcoded_profile[0]} — a CLI --profile "
                "silently drops other providers configured via "
                "HETERO_DOC_PROFILE (external-app regression, 2026-08-11)",
                "remove --profile from the step-2 command; the wrapper resolves "
                "the provider(s) from HETERO_DOC_PROFILE (default deepseek)",
            )
        )
    else:
        coverage.append(
            "  profile-selector: no hardcoded --profile in SKILL.md (wrapper "
            "resolves HETERO_DOC_PROFILE, default deepseek)"
        )

    # --- SKILL.md frontmatter ---
    lines = skill.splitlines()
    if not lines or lines[0].strip() != "---":
        findings.append(
            _finding(
                "frontmatter",
                "SKILL.md has no YAML frontmatter",
                "add a --- -delimited frontmatter block",
            )
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
                    "SKILL.md frontmatter missing name:",
                    "add `name: cross-source-review`",
                )
            )
        desc = _description_text(skill)
        if not desc:
            findings.append(
                _finding(
                    "frontmatter",
                    "SKILL.md frontmatter missing description:",
                    "add a description (the routing surface)",
                )
            )
        elif len(desc) > MAX_DESC_LEN:
            findings.append(
                _finding(
                    "frontmatter",
                    f"SKILL.md description is {len(desc)} chars (>{MAX_DESC_LEN})",
                    "trim it (skill-creator quick_validate rejects)",
                )
            )
    if len(lines) > MAX_SKILL_LINES:
        findings.append(
            _finding(
                "skill-length",
                f"SKILL.md is {len(lines)} lines (>{MAX_SKILL_LINES} ideal)",
                "extract detail to docs/",
            )
        )

    # --- Scope Guard section (the entry-time routing guard) ---
    if "Scope Guard" not in skill:
        findings.append(
            _finding(
                "scope-guard",
                "SKILL.md has no Scope Guard section",
                "add a `### Scope Guard` section (entry-time route to pd/bc)",
            )
        )

    # --- loading chain: SKILL.md references each authority doc + each exists ---
    for doc in AUTHORITY_DOCS:
        doc_path = os.path.join(DOCS, doc)
        ref_inline = f"docs/{doc}"
        if not _exists(doc_path):
            findings.append(
                _finding(
                    "loading-chain",
                    f"authority doc missing: docs/{doc}",
                    f"create docs/{doc}",
                )
            )
        elif ref_inline not in skill:
            findings.append(
                _finding(
                    "loading-chain",
                    f"LOADING-CHAIN BREAK: SKILL.md does not reference docs/{doc}",
                    f"add a link to docs/{doc} (a model must reach it from SKILL.md)",
                )
            )

    # --- required infra files ---
    missing = []
    for rel in REQUIRED_FILES:
        if not _exists(os.path.join(ROOT, rel)):
            missing.append(rel)
    for rel in missing:
        findings.append(
            _finding(
                "required-file",
                f"missing {rel}",
                f"create it ({REQUIRED_FILES[rel]})",
            )
        )
    present = len(REQUIRED_FILES) - len(missing)
    total = len(REQUIRED_FILES)
    coverage.append(f"required files: {present}/{total} present")

    # --- same-family leg agent: solidforge:doc-reviewer is PLUGIN-LEVEL (repo-root agents/) ---
    # doc-reviewer was moved from skill-internal to plugin-level (Q1) — mirrors how bc
    # registers solidforge:plan-reviewer. Verify the backing file exists + well-formed.
    repo_root = os.path.dirname(os.path.dirname(ROOT))  # skills/<skill> -> repo root
    doc_reviewer = os.path.join(repo_root, "agents", "doc-reviewer.agent.md")
    if not _exists(doc_reviewer):
        findings.append(
            _finding(
                "agent-missing",
                "solidforge:doc-reviewer backing file missing at "
                "agents/doc-reviewer.agent.md (repo root)",
                "register the same-family leg agent at plugin level (repo-root agents/), "
                "mirroring solidforge:plan-reviewer",
            )
        )
    else:
        atext = _read(doc_reviewer) or ""
        if not atext.startswith("---"):
            findings.append(
                _finding(
                    "agent-frontmatter",
                    "doc-reviewer.agent.md has no YAML frontmatter",
                    "add a --- -delimited frontmatter block",
                )
            )
        else:
            fm = atext.split("---", 2)[1]
            fm_lines = fm.splitlines()
            for field in ("name", "description", "tools", "disallowedTools"):
                if not any(ln.startswith(f"{field}:") for ln in fm_lines):
                    findings.append(
                        _finding(
                            "agent-frontmatter",
                            f"doc-reviewer.agent.md frontmatter missing {field}:",
                            f"add `{field}:` (the agent contract)",
                        )
                    )
            # do NOT hardcode model/max_turns (workspace rule + global conventions)
            if any(ln.startswith("model:") for ln in fm_lines) or any(
                ln.startswith("max_turns:") for ln in fm_lines
            ):
                findings.append(
                    _finding(
                        "agent-frontmatter",
                        "doc-reviewer.agent.md hardcodes model/max_turns",
                        "omit to inherit (workspace rule)",
                    )
                )

    # --- link integrity across SKILL.md + docs/ ---
    md_files = [SKILL]
    if _exists(DOCS):
        doc_mds = [f for f in os.listdir(DOCS) if f.endswith(".md")]
        md_files += [os.path.join(DOCS, f) for f in doc_mds]
    link_re = re.compile(r"\]\(([^)]+\.md[^)]*)\)")
    fenced_re = re.compile(r"```.*?```", re.DOTALL)
    inline_re = re.compile(r"`[^`\n]*`")
    for md in md_files:
        text = _read(md) or ""
        clean = fenced_re.sub("", text)
        clean = inline_re.sub("", clean)
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
                        "create the target or fix the link",
                    )
                )

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
