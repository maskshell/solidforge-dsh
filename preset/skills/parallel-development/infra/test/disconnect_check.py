#!/usr/bin/env python3
"""Disconnect + loading-chain + layer-separation checker for the parallel-development skill.

Data-driven by infra/test/platforms.json (the single source of truth). Verifies, per declared language, that:

  - structural wiring is intact (L4 file, arch script, fast-gate dispatch, detect_toolchain classification, arm provisioning, template config); and
  - the LOADING CHAIN is unbroken at every declared decision-point doc — i.e. each language's specifics are reachable at the POINT OF NEED, not just from some doc. This is what prevents a model following progressive disclosure (description -> SKILL.md -> references/) from hitting a dead end.

Plus a heuristic LAYER-SEPARATION pass (workspace rule 4: heuristics are advisory, NEVER Blocker). It flags L4-domain toolchain detail — a fenced code block that runs >=2 of one language's deep tools (ruff/mypy/pytest, cargo/clippy, mvn/checkstyle, …) — that has leaked into a GENERAL layer (L1 SKILL.md or the L2 workflow docs), where it is noise to users on other platforms. These findings are ADVISORY: they are printed but do NOT change the exit code (a Blocker must be a real violation, not a guess; distinguishing "brief routing mention" from "deep L4 dump" is a judgment call).

This checker does NOT need editing when a language is added — add an entry to platforms.json instead. Run after any language change:

    python3 infra/test/disconnect_check.py                  # all languages, terse
    python3 infra/test/disconnect_check.py --verbose        # every link, per language
    python3 infra/test/disconnect_check.py --lang python    # one language
    python3 infra/test/disconnect_check.py --lang rust -v   # one language, every link

Exits non-zero with actionable per-file guidance if any structural / loading-chain link is missing. Layer-separation findings are advisory and do not affect the exit.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REFS = os.path.join(ROOT, "references")
INFRA = os.path.join(ROOT, "infra")
SKILL = os.path.join(ROOT, "SKILL.md")
REGISTRY = os.path.join(INFRA, "test", "platforms.json")

# L2 workflow docs (general layers) — L4 detail must not leak into these or SKILL.md.
L2_DOCS = ["feature-dev.md", "bug-fix.md", "refactoring.md", "e2e-testing.md"]

# Deep toolchain vocabulary per language (L4 content). A fenced block running >=2 of these from the SAME language is a toolchain dump = L4 detail. Detection markers (pyproject.toml / Cargo.toml / package.json) are deliberately NOT here — those are L1 routing signals, allowed in general layers. This is the layer-separation heuristic vocab, separate from the platforms.json registration registry.
DEEP_TOOLS = {
    "python": ["ruff", "mypy", "pylint", "pytest", "pip-audit", "import-linter"],
    "rust": ["cargo", "rustc", "rustfmt", "clippy"],
    "java": ["mvn", "gradle", "jdeps", "checkstyle", "google-java-format"],
    "web": ["tsc", "eslint", "vitest", "depcruise"],
    "swift": ["xcodebuild", "swiftlint", "xcrun"],
    "go": ["gofmt", "golangci-lint", "govulncheck"],
}


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def exists(path):
    return os.path.exists(path)


def description_length(text):
    """Char length of the SKILL.md description (block-scalar or inline). skill-creator's quick_validate caps this at 1024 — over that, the description may be truncated / hurt triggering. Line-based parse to avoid regex newline traps in block scalars."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return 0
    fm = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm.append(line)
    i = 0
    while i < len(fm) and not fm[i].startswith("description:"):
        i += 1
    if i >= len(fm):
        return 0
    head = fm[i][len("description:") :].strip()
    if head in ("|", ">", ""):  # block scalar: collect indented continuation lines
        body = []
        for line in fm[i + 1 :]:
            if line[:1] in (" ", "\t") or line.strip() == "":
                body.append(line.strip())
            else:
                break
        return len(" ".join(b for b in body if b))
    return len(head)


def load_ctx(reg):
    """Pre-read the docs the per-language checks consult (read once, not per language)."""
    decision_points = reg["decision_points"]
    skill = read(SKILL) or ""
    return {
        "skill": skill,
        "arm": read(os.path.join(INFRA, "install", "arm.py")) or "",
        "detect": read(os.path.join(INFRA, "hooks", "lib", "detect_toolchain.py"))
        or "",
        "fastgate": read(os.path.join(INFRA, "hooks", "fast_gate.py")) or "",
        "decision_points": decision_points,
        "dp_text": {dp: (read(os.path.join(REFS, dp)) or "") for dp in decision_points},
        "desc_block": skill[
            skill.find("description") : skill.find("\n---", skill.find("description"))
        ].lower(),
    }


def check_language(lang, conf, ctx):
    """Return ALL checks for one language: [(category, label, ok, how), ...]."""
    l4 = conf["l4_file"]
    l4path = os.path.join(REFS, l4)
    l4text = read(l4path) or ""
    arm = ctx["arm"]
    detect = ctx["detect"]
    fastgate = ctx["fastgate"]
    skill = ctx["skill"]
    desc_block = ctx["desc_block"]

    checks = []
    # --- structural wiring ---
    checks += [
        (
            "structural",
            "L4 file exists",
            exists(l4path),
            f"create references/{l4}",
        ),
        (
            "structural",
            "L4 has 'Architecture-Contract Gate' section naming the script",
            "Architecture-Contract Gate" in l4text and conf["arch_script"] in l4text,
            f"in references/{l4}, add an '## Architecture-Contract Gate' section "
            f"naming {conf['arch_script']}.py",
        ),
        (
            "structural",
            "infra arch script exists",
            exists(os.path.join(INFRA, "scripts", conf["arch_script"] + ".py")),
            f"create infra/scripts/{conf['arch_script']}.py",
        ),
        (
            "structural",
            "arm provisions the tool",
            conf["install_token"] in arm,
            f"add a prepare_tools/detect branch for '{lang}' in arm.py referencing "
            f"{conf['install_token']}",
        ),
        (
            "structural",
            "arm ARCH_CONFIGS has the config",
            conf["arch_config"] in arm,
            f"add {conf['arch_config']} to ARCH_CONFIGS in arm.py",
        ),
        (
            "structural",
            "template config exists",
            exists(os.path.join(INFRA, "templates", conf["arch_config"])),
            f"create infra/templates/{conf['arch_config']}",
        ),
        (
            "structural",
            "detect_toolchain classifies the extension",
            conf["extension"] in detect,
            f"add {conf['extension']} to classify() in detect_toolchain.py",
        ),
        (
            "structural",
            "fast_gate has explicit elif branch",
            f'platform == "{lang}"' in fastgate,
            f'add `elif platform == "{lang}":` to fast_gate.py '
            f"(never rely on the implicit else)",
        ),
        (
            "structural",
            "fast_gate defines the check fn",
            f"def {conf['check_fn']}(" in fastgate,
            f"add def {conf['check_fn']}() to fast_gate.py",
        ),
    ]
    # --- SKILL.md top-level routing ---
    checks += [
        (
            "routing",
            "description has trigger keywords",
            any(k in desc_block for k in conf["desc_keywords"]),
            f"add {conf['desc_keywords']} to the SKILL.md description",
        ),
        (
            "routing",
            "detection marker present",
            conf["marker_file"] in skill,
            f"mention {conf['marker_file']} in SKILL.md detection",
        ),
        (
            "routing",
            "Reference Files lists L4",
            l4 in skill,
            f"add references/{l4} to SKILL.md Reference Files",
        ),
        (
            "routing",
            "layer table classifies L4",
            l4 in skill,
            f"add {l4} to the L4 row of SKILL.md layer table",
        ),
    ]
    # --- loading chain: each declared decision-point doc must route the language ---
    for dp, meta in ctx["decision_points"].items():
        via = meta["via"]
        text = ctx["dp_text"][dp]
        if via == "l4_link":
            ok = l4 in text
            how = f"add a pointer to references/{l4} in {dp}"
        elif via in ("parallel_markers", "role_markers"):
            markers = conf[via]
            ok = any(m in text for m in markers)
            how = (
                f"add a {lang} section/link in {dp} using one of {markers} "
                f"(why: {meta['because']})"
            )
        else:
            continue
        checks.append(("loading-chain", f"{dp} routes {lang} via {via}", ok, how))
    return checks


def check_layer_separation():
    """Heuristic (rule 4: advisory, never Blocker). Flags fenced code blocks in L1
    (SKILL.md) or L2 (workflow docs) that run >=2 of one language's deep tools — i.e.
    L4 toolchain detail leaked into a general layer. Returns [(doc, lang, preview)].
    Does NOT affect the exit code."""
    findings = []
    docs = [("SKILL.md (L1)", SKILL)] + [
        (f"{d} (L2)", os.path.join(REFS, d)) for d in L2_DOCS
    ]
    fenced_re = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
    for label, path in docs:
        text = read(path)
        if not text:
            continue
        for m in fenced_re.finditer(text):
            block = m.group(1)
            for lang, tools in DEEP_TOOLS.items():
                if sum(1 for t in tools if t in block) >= 2:
                    preview = " ".join(block.split())[:90]
                    findings.append((label, lang, preview))
                    break  # one language per block is enough to flag
    return findings


def check_skill_integrity():
    """Skill-level integrity (independent of any one language). Returns a list of
    issue strings (empty = clean)."""
    issues = []
    md_files = [SKILL] + sorted(
        os.path.join(REFS, f) for f in os.listdir(REFS) if f.endswith(".md")
    )
    link_re = re.compile(r"\]\(([^)]+\.md[^)]*)\)")
    fenced_re = re.compile(r"```.*?```", re.DOTALL)
    inline_re = re.compile(r"`[^`\n]*`")
    corpus = ""
    for md in md_files:
        text = read(md) or ""
        corpus += text + " "
        clean = fenced_re.sub("", text)
        clean = inline_re.sub("", clean)
        base = os.path.dirname(md)
        for tgt in link_re.findall(clean):
            if tgt.startswith("http"):
                continue
            path = tgt.split("#")[0]
            if path and not os.path.exists(os.path.join(base, path)):
                issues.append(f"broken link in {os.path.relpath(md, ROOT)} -> {tgt}")
    for f in sorted(os.listdir(REFS)):
        if f.endswith(".md") and f not in corpus:
            issues.append(f"orphaned reference (not reachable): references/{f}")
    n_lines = len((read(SKILL) or "").splitlines())
    if n_lines > 500:
        issues.append(
            f"SKILL.md is {n_lines} lines (>500 ideal) — extract detail to references/"
        )
    desc_len = description_length(read(SKILL) or "")
    if desc_len > 1024:
        issues.append(
            f"description is {desc_len} chars (>1024 max) — trim it "
            f"(skill-creator quick_validate rejects; hurts triggering)"
        )
    return issues


def main():
    ap = argparse.ArgumentParser(
        description="Disconnect + loading-chain + layer-separation checker "
        "(registry-driven by infra/test/platforms.json)."
    )
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="print every per-language link, not just failures",
    )
    ap.add_argument(
        "--lang", help="restrict to one language (e.g. python, rust, java, web, swift)"
    )
    args = ap.parse_args()

    with open(REGISTRY, encoding="utf-8") as fh:
        reg = json.load(fh)
    languages = reg["languages"]

    if args.lang and args.lang not in languages:
        sys.exit(f"unknown --lang {args.lang!r}; known: {', '.join(sorted(languages))}")

    ctx = load_ctx(reg)
    selected = [args.lang] if args.lang else list(languages)
    per_lang = {lang: check_language(lang, languages[lang], ctx) for lang in selected}

    failures = []
    for lang in selected:
        for cat, label, ok, how in per_lang[lang]:
            if not ok:
                failures.append(f"[{lang}] {label} -> {how}")

    if args.verbose:
        for lang in selected:
            checks = per_lang[lang]
            npass = sum(1 for _, _, ok, _ in checks if ok)
            print(f"{lang}: {npass}/{len(checks)} links")
            for cat, label, ok, how in checks:
                mark = "ok  " if ok else "FAIL"
                tail = "" if ok else f" -> {how}"
                print(f"  {mark} [{cat}] {label}{tail}")
        print()
    elif failures:
        print("DISCONNECTS / LOADING-CHAIN BREAKS:")
        for f in failures:
            print("  - " + f)

    integrity = check_skill_integrity()
    if integrity:
        print("SKILL-LEVEL INTEGRITY ISSUES:")
        for f in integrity:
            print("  - " + f)

    layer = check_layer_separation()
    if layer:
        print(
            "LAYER-SEPARATION (heuristic, advisory — rule 4; does NOT fail the gate):"
        )
        for doc, lang, preview in layer:
            print(
                f"  - {doc}: fenced {lang} toolchain block (L4 detail in a general "
                f"layer): {preview!r}"
            )

    if failures or integrity:
        sys.exit(1)

    n_links = 9 + 4 + len(ctx["decision_points"])
    if args.verbose or args.lang:
        print(
            f"OK: {len(selected)} language(s) x ~{n_links} links each; "
            f"skill integrity clean."
        )
    else:
        print(
            f"OK: {len(languages)} languages x ~{n_links} links each "
            f"(structural + loading-chain), skill-level integrity clean."
        )
        print(
            "    (registry-driven: add a language via infra/test/platforms.json, "
            "not by editing this checker.)"
        )
        print(
            "    (run with --verbose or --lang <name> to see the per-language loading chain.)"
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
