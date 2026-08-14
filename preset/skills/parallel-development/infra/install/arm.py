#!/usr/bin/env python3
"""arm.py — Layer 2 project provisioning for the SolidForge DSH port.

The preset model (see references/install.md, references/design-decisions.md ADR #19) retires the old install.py copy-and-wire installer. Its duties split:

  - Layer 1 (on preset MOUNT): skills + role agents + gate plugins activate. The gates (blueprint_guard / counters / fast_gate) run from the preset root via ${SOLIDFORGE_PRESET_ROOT} and operate on $SOLIDFORGE_PROJECT_DIR — they are NOT copied into the target project.
  - Layer 2 (THIS script, invoked by the arm-tools command): provisions the PROJECT-SIDE files the gates and loop need, because plugins do not mutate host-project build files (so this cannot collapse into enable):
      * copy per-language arch-configs to the project root (only for detected languages; never clobbers an existing edited file)
      * append the L1 Constitution + (with --with-tools) Gate-Toolchain note to the project AGENTS.md
      * copy the intent-blueprint template + cold-start patterns
      * add .gitignore entries for the loop's runtime state
      * --with-tools: add version-matched gate tools to the project's OWN dev deps (uv/poetry/pipenv/pip/npm/pnpm/yarn); system-only tools print install commands. Append `--lang <python|web|rust|swift|java|go>` to arm ONE ecosystem only (default: all detected) — for polyglot repos that want just one language's gate tools.
      * print a gate-status report + an LSP/code-intelligence advisory

Retired from install.py (now preset-manager operations, not skill-testable):
  - hook/script copy + wiring -> gate plugins + ${SOLIDFORGE_PRESET_ROOT} (Layer 1)
  - version stamp / drift / upgrade reconcilers -> preset update
  - full uninstall -> preset deselect; the --revert here is the project-side inverse of THIS script's provisioning only (keeps user edits)

Usage:
  python3 arm.py [project_dir] [--with-tools [--lang python|web|rust|swift|java|go]] [--scaffold-configs [vale,semgrep,spectral]] [--revert [--apply]]
  project_dir defaults to $SOLIDFORGE_PROJECT_DIR or the current working directory.

--revert is DRY-RUN by default; --revert --apply removes only the files arm.py provisioned (arch-configs that still match the template, the constitution / toolchain AGENTS.md sections, blueprint templates, .gitignore entries). A config or section you edited is KEPT and warned about. Exclusive of --with-tools.
"""

import glob
import os
import re
import shutil
import subprocess
import sys

INFRA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../infra
SKILL_ROOT = os.path.dirname(INFRA_ROOT)  # .../parallel-development
TEMPLATES_SRC = os.path.join(INFRA_ROOT, "templates")

CONSTITUTION_SRC = os.path.join(TEMPLATES_SRC, "claude-md-l1-constitution.md")
CONSTITUTION_HEADING = "## L1 Constitution (uncodable red lines)"
TOOLCHAIN_HEADING = "## Deterministic Gate Toolchain"

PY_GATE_PKGS = [
    "ruff",
    "import-linter",
    "pylint",
    "pyright",
    "pip-audit",
    "pytest-json-report",
    "pytest-cov",
]  # fast gate (ruff) + arch gate (import-linter, pylint, pyright) + supply-chain (pip-audit) + test gate (pytest-json-report) + coverage gate (pytest-cov, P3)
WEB_GATE_PKGS = [
    "dependency-cruiser",
    "eslint",
    "typescript",
    "vitest",
    "@vitest/coverage-v8",
]  # arch + type (typescript/tsc) + test gate (vitest) + coverage gate (@vitest/coverage-v8, P3)


def have(cmd):
    return (
        subprocess.run(
            ["sh", "-c", f"command -v {cmd}"], capture_output=True
        ).returncode
        == 0
    )


def tool_present(project_dir, name):
    """True if a tool is reachable: on PATH OR in the project's local venv bin."""
    if have(name):
        return True
    for venv in (".venv", "venv", "env"):
        if os.path.exists(os.path.join(project_dir, venv, "bin", name)):
            return True
    return False


def run_cwd(argv, cwd, timeout=600):
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return None, "command not found"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def tail1(text):
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


# --- file copy ---------------------------------------------------------------


def copy_tree_filtered(src, dst, label):
    if not os.path.isdir(src):
        return
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        rel = os.path.relpath(dirpath, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for fname in filenames:
            if fname.endswith((".pyc", ".pyo")):
                continue
            shutil.copy2(os.path.join(dirpath, fname), os.path.join(target_dir, fname))
    print(f"  + copied {label} -> {dst}")


def append_constitution(project_dir):
    cmd = os.path.join(project_dir, "AGENTS.md")
    try:
        with open(CONSTITUTION_SRC, "r", encoding="utf-8") as fh:
            section = fh.read()
    except OSError:
        return
    existing = ""
    if os.path.exists(cmd):
        with open(cmd, "r", encoding="utf-8") as fh:
            existing = fh.read()
    if CONSTITUTION_HEADING in existing:
        print("  = AGENTS.md already has the L1 Constitution section (skipped)")
        return
    with open(cmd, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(section)
        if not section.endswith("\n"):
            fh.write("\n")
    print(f"  + appended L1 Constitution to {cmd}")


def detect_root_package(project_dir):
    """Best-effort detection of the Python importable root package for .importlinter.ini.

    Tries (a) pyproject.toml [project] name / [tool.setuptools.packages]; (b) src-layout
    src/<pkg>/__init__.py; (c) flat-layout top-level dir with __init__.py. Returns the
    package name or '__REPLACE_ME__' on failure (the gate stays green — 0 active contracts).
    Pure stdlib; no new deps.
    """

    # (a) pyproject.toml [project] name
    pyproject = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            text = open(pyproject, encoding="utf-8").read()
            m = re.search(r"^\[project\]\s*$", text, re.M)
            if m:
                nm = re.search(
                    r"^name\s*=\s*[\"']([^\"']+)[\"']", text[m.start() :], re.M
                )
                if nm:
                    pkg = nm.group(1).replace("-", "_")
                    return pkg
        except (OSError, ValueError):
            pass
    # (b) src-layout: src/<pkg>/__init__.py
    src_dir = os.path.join(project_dir, "src")
    if os.path.isdir(src_dir):
        for entry in sorted(os.listdir(src_dir)):
            if os.path.isfile(os.path.join(src_dir, entry, "__init__.py")):
                return entry
    # (c) flat-layout: top-level dir with __init__.py (skip common non-package dirs)
    skip = {
        "tests",
        "test",
        "docs",
        "doc",
        "scripts",
        "venv",
        ".venv",
        "infra",
        "hooks",
    }
    for entry in sorted(os.listdir(project_dir)):
        d = os.path.join(project_dir, entry)
        if (
            os.path.isdir(d)
            and not entry.startswith(".")
            and entry.lower() not in skip
            and os.path.isfile(os.path.join(d, "__init__.py"))
        ):
            return entry
    return "__REPLACE_ME__"


def copy_arch_configs(project_dir):
    # ARCH_CONFIGS pairs each config with the per-language detector that also drives prepare_tools / write_toolchain_note. A config is copied IFF the project is recognized as that language — so config, deps, and the AGENTS.md toolchain note can never disagree (no orphan configs for a language the project doesn't use, no missing config for one it does).
    for name, relevant in ARCH_CONFIGS:
        if not relevant(project_dir):
            print(f"  - {name} skipped (language not detected in this project)")
            continue
        src = os.path.join(TEMPLATES_SRC, name)
        dst = os.path.join(project_dir, name)
        if not os.path.exists(src):
            continue
        if os.path.exists(dst):
            print(f"  = {name} already present in project root (skipped)")
            continue
        shutil.copy2(src, dst)
        # ACF-I1: substitute root_package for .importlinter.ini (the only template with a
        # project-specific token after ACF-I0 neutralized the layer examples).
        if name == ".importlinter.ini":
            detected = detect_root_package(project_dir)
            if detected != "__REPLACE_ME__":
                try:
                    with open(dst, encoding="utf-8") as fh:
                        content = fh.read()
                    content = content.replace(
                        "root_package = __REPLACE_ME__", f"root_package = {detected}", 1
                    )
                    with open(dst, "w", encoding="utf-8") as fh:
                        fh.write(content)
                except OSError:
                    pass  # best-effort; the template stays with __REPLACE_ME__
        if name in (".importlinter.ini", ".dependency-cruiser.cjs", ".swiftlint.yml"):
            print(
                f"  + copied {name} — layering is a PLACEHOLDER (commented). Uncomment + edit to enforce YOUR architecture; gate is green until then."
            )
        else:
            print(f"  + copied {name} to project root (edit to match your project)")


def copy_external_configs(project_dir, tools):
    """Copy the external-tool config templates the user opted into via --scaffold-configs.

    `tools` is the set of keys selected (None = all three). Mirrors copy_arch_configs:
    skip if not selected, skip-if-exists (never clobber). NOT language-bound — these
    tools cross-cut languages, so selection is by flag key, not a language predicate.
    """
    selected = tools if tools is not None else {key for _, key, _ in EXTERNAL_CONFIGS}
    for name, key, note in EXTERNAL_CONFIGS:
        if key not in selected:
            continue
        src = os.path.join(TEMPLATES_SRC, name)
        dst = os.path.join(project_dir, name)
        if not os.path.exists(src):
            continue
        if os.path.exists(dst):
            print(f"  = {name} already present in project root (skipped)")
            continue
        shutil.copy2(src, dst)
        print(f"  + copied {name} to project root ({note})")


def copy_blueprint_templates(project_dir):
    dst_dir = os.path.join(project_dir, "docs", "intent-blueprints", "_templates")
    os.makedirs(dst_dir, exist_ok=True)
    for name in ("intent-blueprint.template.md",):
        src = os.path.join(TEMPLATES_SRC, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst_dir, name))
    cold = os.path.join(TEMPLATES_SRC, "cold-start-patterns")
    if os.path.isdir(cold):
        copy_tree_filtered(
            cold, os.path.join(dst_dir, "cold-start-patterns"), "cold-start-patterns"
        )
    print(f"  + copied blueprint templates -> {dst_dir}")


def _toolchain_note_lines(project_dir, lang=None):
    """Build the canonical Gate Toolchain section body (starts with the heading, no leading blank). Shared by write_toolchain_note only (the upgrade refresh path is retired; this is the single writer now). `lang` (from --with-tools --lang <name>) restricts the note to the armed ecosystem; None = all detected."""
    pm = detect_python_pm(project_dir)
    node_pm = detect_node_pm(project_dir)
    py = has_python(project_dir)
    node = has_node(project_dir)
    swift = has_swift(project_dir)
    rust = has_rust(project_dir)
    java = has_java(project_dir)
    go = has_go(project_dir)

    def want(name):
        return lang is None or lang == name

    lines = [
        TOOLCHAIN_HEADING,
        "",
        "The convergence-loop gates degrade gracefully and never report a silent green when a tool is absent. To arm them on a new machine or in CI, restore/install the gate tools for the ecosystems this project uses:",
        "",
    ]
    emitted = False
    if want("python"):
        if pm == "uv":
            lines.append(
                "- Python: `uv sync` — ruff / import-linter / pylint are in dev deps (uv.lock)"
            )
            emitted = True
        elif pm == "poetry":
            lines.append(
                "- Python: `poetry install` — ruff / import-linter / pylint are in the dev group"
            )
            emitted = True
        elif pm in ("pipenv", "pip"):
            lines.append(
                "- Python: install dev requirements — ruff, import-linter, pylint"
            )
            emitted = True
        elif py:
            lines.append(
                "- Python (nested subdir, no root marker): `cd` into the Python dir and run `uv sync` / `poetry install` / `pip install -e .`"
            )
            emitted = True
    if want("web"):
        if node_pm:
            inst = {
                "npm": "npm ci",
                "pnpm": "pnpm install --frozen-lockfile",
                "yarn": "yarn install --frozen-lockfile",
            }[node_pm]
            lines.append(
                f"- Web: `{inst}` — dependency-cruiser / eslint are in devDependencies"
            )
            emitted = True
        elif node:
            lines.append(
                "- Web (nested frontend, no root marker): `cd` into the frontend dir and run `npm ci` / `pnpm install --frozen-lockfile` / `yarn install --frozen-lockfile`"
            )
            emitted = True
    if want("swift") and swift:
        lines.append(
            "- Swift (per-machine, NOT in the repo): `brew install swiftlint` (or `mint install realm/swiftlint`)"
        )
        emitted = True
    if want("rust") and rust:
        lines.append(
            "- Rust (per-machine, NOT in the repo): `rustup component add clippy rustfmt` "
            "(optional `cargo install cargo-modules`); coverage gate `cargo install cargo-tarpaulin`"
        )
        emitted = True
    if want("java") and java:
        lines.append(
            "- Java (per-machine, NOT in the repo): build via `./mvnw` / `./gradlew` (or `brew install maven gradle`); fast gate `google-java-format` (shim or $GOOGLE_JAVA_FORMAT_JAR); arch gate `checkstyle` ($CHECKSTYLE_JAR or shim); supply-chain `brew install dependency-check` (sync the NVD DB separately: `dependency-check --updateonly`)"
        )
        emitted = True
    if want("go") and go:
        lines.append(
            "- Go (per-machine, NOT in the repo): the `go` toolchain provides gofmt (fast gate) + "
            "`go vet`/`go build` (arch gate); arch gate `brew install golangci-lint` or "
            "`go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest` (depguard layer rules); "
            "supply-chain `go install golang.org/x/vuln/cmd/govulncheck@latest`; concurrency baseline "
            "`go test -race` runs in the test gate; coverage gate is built-in (`go test -coverprofile` + `go tool cover`)"
        )
        emitted = True
    if not emitted:
        if lang:
            lines.append(
                f"- (no {lang} ecosystem detected at the project root; see the "
                f"parallel-development skill's references/install.md)"
            )
        else:
            lines.append(
                "- (no recognized ecosystem detected; see the parallel-development skill's references/install.md)"
            )
    lines.append("")
    return lines


def write_toolchain_note(project_dir, lang=None):
    """Append a checked-in Gate Toolchain note to AGENTS.md so a new machine / CI contributor knows how to arm the gates. Project-portable tools restore via the lockfile; system tools need a per-machine install. Append-once (idempotent). Written only under --with-tools (documents the deps just added). `lang` restricts the note to the armed ecosystem (mirrors prepare_tools' --lang filter)."""
    cmd = os.path.join(project_dir, "AGENTS.md")
    existing = ""
    if os.path.exists(cmd):
        with open(cmd, "r", encoding="utf-8") as fh:
            existing = fh.read()
    if TOOLCHAIN_HEADING in existing:
        print("  = AGENTS.md already has the Gate Toolchain note (skipped)")
        return
    canonical = "\n".join(_toolchain_note_lines(project_dir, lang))
    prefix = existing.rstrip("\n")
    sep = "\n\n" if prefix else ""
    with open(cmd, "w", encoding="utf-8") as fh:
        fh.write(prefix + sep + canonical + "\n")
    print(
        f"  + appended Gate Toolchain note to {cmd} (travels with the repo for new machines/CI)"
    )


# Derived-state paths the loop keeps out of git. loop-state.json is the live convergence-loop state; runs/ holds per-run telemetry snapshots written by loop_state.py. Both are machine-generated transient state, never committed.
GITIGNORE_ENTRIES = [
    ".solidforge/loop/loop-state.json",
    ".solidforge/loop/runs/",
    # different-family secrets: .env (the user's app env) + .env.solidforge (the Solid Forge
    # secrets file) hold provider tokens, never committed. The negations below
    # un-ignore the committed placeholders (no real tokens) — defensive against
    # projects whose own .gitignore uses `.env.*` (which would match .env.example
    # + .env.solidforge.example).
    ".env",
    ".env.solidforge",
    "!.env.example",
    "!.env.solidforge.example",
]


def copy_env_example(project_dir):
    """Provision the Solid Forge different-family secrets-placeholder `.env.solidforge.example` to
    the project root (always-on — harmless documentation, never carries real tokens).
    The namespaced filename avoids collision with the user's own `.env.example` + makes
    ownership clear. The user copies it to `.env.solidforge` (or puts the vars in their
    shell / `.env`) + fills tokens to opt into different-family. Idempotent + never clobbers (mirrors
    copy_blueprint_templates). `.env.solidforge` is gitignored; the `.example` is
    committed."""
    name = ".env.solidforge.example"
    src = os.path.join(TEMPLATES_SRC, name)
    dst = os.path.join(project_dir, name)
    if not os.path.exists(src):
        return
    if os.path.exists(dst):
        print(f"  = {name} already present in project root (skipped)")
        return
    shutil.copy2(src, dst)
    print(
        f"  + copied {name} to project root (different-family secrets placeholder; "
        "cp to .env.solidforge + fill tokens)"
    )


def update_gitignore(project_dir):
    gi = os.path.join(project_dir, ".gitignore")
    existing = ""
    if os.path.exists(gi):
        with open(gi, "r", encoding="utf-8") as fh:
            existing = fh.read()
    pending = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if not pending:
        return
    body = existing
    if body and not body.endswith("\n"):
        body += "\n"
    body += "".join(e + "\n" for e in pending)
    with open(gi, "w", encoding="utf-8") as fh:
        fh.write(body)
    for entry in pending:
        print(f"  + added {entry} to .gitignore")


# --- --with-tools: project-local gate deps -----------------------------------


def detect_python_pm(project_dir):
    if os.path.exists(os.path.join(project_dir, "uv.lock")):
        return "uv"
    if os.path.exists(os.path.join(project_dir, "poetry.lock")):
        return "poetry"
    if os.path.exists(os.path.join(project_dir, "Pipfile")):
        return "pipenv"
    pyproject = os.path.join(project_dir, "pyproject.toml")
    has_pyproject = os.path.exists(pyproject)
    has_reqs = bool(
        glob.glob(os.path.join(project_dir, "requirements*.txt"))
    ) or os.path.exists(os.path.join(project_dir, "setup.py"))
    if has_pyproject:
        # A pyproject.toml without a lockfile: distinguish poetry-style from uv/PEP 621.
        try:
            with open(pyproject, "r", encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            body = ""
        if "[tool.poetry]" in body:
            return "poetry"
        if have(
            "uv"
        ):  # PEP 621 pyproject + uv available -> uv manages it (uv add will create uv.lock)
            return "uv"
        return "pip"
    if has_reqs:
        return "pip"
    return None


def detect_node_pm(project_dir):
    if os.path.exists(os.path.join(project_dir, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(project_dir, "yarn.lock")):
        return "yarn"
    if os.path.exists(os.path.join(project_dir, "package.json")):
        return "npm"
    return None


# Dirs never descended into when searching for language markers — build output, dependencies, vendored trees, caches. Keeps the bounded walk fast and avoids false detections (e.g. a package.json inside node_modules, a pom.xml inside target).
_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "target",
    "build",
    "dist",
    "out",
    ".venv",
    "venv",
    "env",
    ".gradle",
    ".next",
    ".nuxt",
    ".turbo",
    ".nx",
    "__pycache__",
    "Pods",
    "DerivedData",
    ".build",
    "coverage",
    ".idea",
    ".vscode",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}
_MAX_MARKER_DEPTH = 4


def find_marker_dirs(project_dir, names, max_depth=_MAX_MARKER_DEPTH):
    """Return dirs (relative to project_dir; "" == the root) that directly contain any of the marker file `names`. Bounded walk that prunes build/dep/cache dirs so a nested frontend (frontend/package.json) or backend (backend/pom.xml) is detected without descending into node_modules/target/etc. The root is depth 0, so a root-level marker and a nested one are handled by the same loop."""
    want = set(names)
    found = []
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, project_dir)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        if any(n in filenames for n in want):
            found.append("" if rel == "." else rel)
    return found


def has_node(project_dir):
    """True if a package.json exists at the root OR nested (monorepo / FE-in-subdir)."""
    return bool(find_marker_dirs(project_dir, ["package.json"]))


def has_python(project_dir):
    """True if a Python project marker exists at the root OR nested."""
    return bool(
        find_marker_dirs(project_dir, ["pyproject.toml", "setup.py", "setup.cfg"])
    )


def has_java(project_dir):
    """Maven (pom.xml) or Gradle (Groovy build.gradle / Kotlin build.gradle.kts),
    at the root OR nested."""
    return bool(
        find_marker_dirs(project_dir, ["pom.xml", "build.gradle", "build.gradle.kts"])
    )


def has_go(project_dir):
    """Go module (go.mod) at the root OR nested (workspace member in a subdir)."""
    return bool(find_marker_dirs(project_dir, ["go.mod"]))


def has_rust(project_dir):
    """Cargo.toml at the root OR nested (workspace member in a subdir)."""
    return bool(find_marker_dirs(project_dir, ["Cargo.toml"]))


def has_swift(project_dir):
    """Package.swift (SPM) OR an *.xcodeproj/*.xcworkspace, at the root OR nested."""
    if find_marker_dirs(project_dir, ["Package.swift"]):
        return True
    for dirpath, dirnames, _filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        rel = os.path.relpath(dirpath, project_dir)
        if rel != "." and rel.count(os.sep) + 1 > _MAX_MARKER_DEPTH:
            dirnames[:] = []
            continue
        if any(
            d.endswith(".xcodeproj") or d.endswith(".xcworkspace") for d in dirnames
        ):
            return True
    return False


# Each entry: (arch-config filename, predicate(project_dir) -> bool).
# The predicate reuses the per-language detector above — the SAME signal prepare_tools / write_toolchain_note key on
#  — so a config is copied iff the project is recognized as that language (root OR nested).
# Colocating name + predicate means a new language cannot add its config without also adding its detector (no silent skip).
# disconnect_check.py greps this module for the filename substring (install_token / arch_config) per platforms.json.
ARCH_CONFIGS = [
    (".importlinter.ini", has_python),
    (".dependency-cruiser.cjs", has_node),
    (".swiftlint.yml", has_swift),
    ("clippy.toml", has_rust),
    ("checkstyle.xml", has_java),
    (".golangci.yml", has_go),
]


# External-tool config templates (the --scaffold-configs registry). NOT language-bound
# (unlike ARCH_CONFIGS): Vale = any docs, Semgrep = any source, Spectral = any OpenAPI
# spec — selection is by --scaffold-configs <key,...> (bare flag = all three), not by a
# language predicate. disconnect_check.py does NOT grep these (external-skill gates are
# not platforms); arm_copy_config.py enforces a parallel coverage guard instead.
EXTERNAL_CONFIGS = [
    (
        ".vale.ini",
        "vale",
        "Vale prose-lint config (styles are OPINION — a subjective starting point; run `vale sync` after scaffolding)",
    ),
    (
        ".semgrep.yml",
        "semgrep",
        "Semgrep SAST ruleset (offline-deterministic; replaces the --config auto network fallback)",
    ),
    (
        ".spectral.yaml",
        "spectral",
        "Spectral OpenAPI ruleset (user-customizable; default equals the adapter's synthesized fallback)",
    ),
]


def _append_requirements_dev(project_dir, pkgs):
    rd = os.path.join(project_dir, "requirements-dev.txt")
    target = rd if os.path.exists(rd) else os.path.join(project_dir, "requirements.txt")
    if not os.path.exists(target):
        print(
            f"  pip: no requirements-dev.txt / requirements.txt; add these dev deps manually: {' '.join(pkgs)}"
        )
        return
    with open(target, "r", encoding="utf-8") as fh:
        existing = fh.read()
    added = []
    for pkg in pkgs:
        if not re.search(rf"^\s*{re.escape(pkg)}\b", existing, re.MULTILINE):
            added.append(pkg)
    if not added:
        print(f"  pip: {target} already has all gate deps (skipped)")
        return
    with open(target, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("# parallel-development gate tools (dev)\n")
        for pkg in added:
            fh.write(f"{pkg}\n")
    print(
        f"  pip: appended {added} to {target} (run: pip install -r {os.path.basename(target)})"
    )


def prepare_tools(project_dir, lang=None):
    """--with-tools provisioning. `lang` (from --lang <name>) restricts to ONE ecosystem (python|web|rust|swift|java|go); None = all detected ecosystems."""
    print(
        "\n--with-tools: adding gate tools to PROJECT-LOCAL deps (version-matched, reversible)"
        + (f" [--lang {lang}]" if lang else "")
    )
    saw_any = False

    def want(name):
        # lang None -> arm every detected ecosystem; else only the named one.
        return lang is None or lang == name

    if want("python"):
        pm = detect_python_pm(project_dir)
        if pm == "uv":
            saw_any = True
            if have("uv"):
                rc, out = run_cwd(
                    ["uv", "add", "--dev"] + PY_GATE_PKGS, project_dir, timeout=600
                )
                print(
                    f"  uv add --dev {PY_GATE_PKGS}: {'ok' if rc == 0 else 'FAILED'}"
                    + (f" — {tail1(out)}" if rc else "")
                )
            else:
                print(
                    f"  uv project but `uv` not on PATH. Run manually: uv add --dev {' '.join(PY_GATE_PKGS)}"
                )
        elif pm == "poetry":
            saw_any = True
            if have("poetry"):
                rc, out = run_cwd(
                    ["poetry", "add", "--group", "dev"] + PY_GATE_PKGS,
                    project_dir,
                    timeout=600,
                )
                print(
                    f"  poetry add --group dev {PY_GATE_PKGS}: {'ok' if rc == 0 else 'FAILED'}"
                    + (f" — {tail1(out)}" if rc else "")
                )
            else:
                print(
                    f"  poetry project but `poetry` not on PATH. Run manually: poetry add --group dev {' '.join(PY_GATE_PKGS)}"
                )
        elif pm == "pipenv":
            saw_any = True
            if have("pipenv"):
                rc, out = run_cwd(
                    ["pipenv", "install", "--dev"] + PY_GATE_PKGS,
                    project_dir,
                    timeout=600,
                )
                print(
                    f"  pipenv install --dev {PY_GATE_PKGS}: {'ok' if rc == 0 else 'FAILED'}"
                    + (f" — {tail1(out)}" if rc else "")
                )
            else:
                print(
                    f"  pipenv project but `pipenv` not on PATH. Run manually: pipenv install --dev {' '.join(PY_GATE_PKGS)}"
                )
        elif pm == "pip":
            saw_any = True
            _append_requirements_dev(project_dir, PY_GATE_PKGS)
        elif has_python(project_dir):
            saw_any = True
            print(
                "  Python: detected in a subdir (no root pyproject/setup). `cd` into the Python dir and re-run arm.py --with-tools there (or run uv/poetry/pip add manually)."
            )

    if want("web"):
        npm_pm = detect_node_pm(project_dir)
        if npm_pm:
            saw_any = True
            add_cmd = {
                "npm": ["npm", "install", "-D"],
                "pnpm": ["pnpm", "add", "-D"],
                "yarn": ["yarn", "add", "-D"],
            }[npm_pm]
            if have(npm_pm):
                rc, out = run_cwd(add_cmd + WEB_GATE_PKGS, project_dir, timeout=600)
                print(
                    f"  {npm_pm} add -D {WEB_GATE_PKGS}: {'ok' if rc == 0 else 'FAILED'}"
                    + (f" — {tail1(out)}" if rc else "")
                )
            else:
                print(
                    f"  {npm_pm} project but `{npm_pm}` not on PATH. Run manually: {' '.join(add_cmd + WEB_GATE_PKGS)}"
                )
        elif has_node(project_dir):
            saw_any = True
            print(
                "  Web: detected in a subdir (no root package.json). `cd` into the frontend dir and re-run arm.py --with-tools there (or run npm/pnpm/yarn add -D manually)."
            )

    if want("swift") and has_swift(project_dir):
        saw_any = True
        print(
            "  Swift: SwiftLint is a system linter (not a project dep). Install one of:"
        )
        print("    brew install swiftlint")
        print("    mint install realm/swiftlint   # project-pinned via Mintfile")

    if want("rust") and has_rust(project_dir):
        saw_any = True
        print(
            "  Rust: gate tools are system toolchain components (not project deps). Install:"
        )
        print(
            "    rustup component add clippy rustfmt      # fast gate (rustfmt) + arch gate (clippy)"
        )
        print(
            "    cargo install cargo-modules              # optional: orphaned-module check"
        )
        print(
            "    cargo install cargo-audit                # supply-chain gate (Rust dep vulns)"
        )
        print(
            "    cargo install cargo-nextest              # test gate (structured JUnit XML output)"
        )
        print(
            "    cargo install cargo-tarpaulin            # coverage gate (P3; NFR-threshold warning)"
        )

    if want("java") and has_java(project_dir):
        saw_any = True
        print(
            "  Java: gate tools are system-toolchain / standalone (not project deps). Install:"
        )
        print(
            "    brew install maven gradle                # build + test gates (or use ./mvnw / ./gradlew)"
        )
        print(
            "    # fast gate: google-java-format — install a `google-java-format` shim or set $GOOGLE_JAVA_FORMAT_JAR"
        )
        print(
            "    # arch gate: checkstyle — set $CHECKSTYLE_JAR, drop a checkstyle-*-all.jar in the repo, or install a shim"
        )
        print(
            "    # supply-chain: brew install dependency-check   # then sync the NVD DB: dependency-check --updateonly"
        )

    if want("go") and has_go(project_dir):
        saw_any = True
        print(
            "  Go: gate tools are system-toolchain (not project deps). The `go` toolchain ships"
        )
        print(
            "    gofmt (fast gate) + go vet / go build (arch gate). Install the extras:"
        )
        print(
            "    brew install go                                  # or the official installer"
        )
        print(
            "    brew install golangci-lint                       # arch gate: depguard layer rules"
        )
        print(
            "    #   alt: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
        )
        print(
            "    go install golang.org/x/vuln/cmd/govulncheck@latest  # supply-chain gate"
        )
        print(
            "    #   concurrency baseline `go test -race` runs in the test gate (no install — ships with go)"
        )

    if saw_any:
        print(
            "  Supply-chain (cross-language): gitleaks scans for leaked secrets. Install one of:"
        )
        print("    brew install gitleaks")
        print("    cargo install gitleaks")

    if not saw_any:
        if lang:
            print(
                f"  no {lang} project toolchain detected at the project root (other ecosystems may "
                f"be present but were skipped by --lang {lang})."
            )
        else:
            print(
                "  no recognized project toolchain (Python/Web/Swift/Rust/Java/Go). Install gate tools manually or rely on the runtime fallback."
            )


# --- LSP / code-intelligence advisory (recommend official plugins; do NOT install) ---

_LSP_ADVISORY = [
    # (predicate, label, plugin, lsp_binary_cmd, binary_install)
    # `lsp_binary_cmd` is what have() probes on $PATH to suppress the binary line
    # when the LSP server is already installed (avoids a redundant install hint —
    # report_gates separately checks the gate type-checkers like pyright/tsc). The
    # Claude Code plugin itself CANNOT be probed (not on $PATH) — its line always
    # shows; that limitation is coverage-noted up front (rule 3), never a silent repeat.
    (
        has_python,
        "Python",
        "pyright-lsp",
        "pyright",
        "npm install -g pyright (or pipx install pyright)",
    ),
    (
        has_rust,
        "Rust",
        "rust-analyzer-lsp",
        "rust-analyzer",
        "rustup component add rust-analyzer",
    ),
    (
        has_swift,
        "Swift",
        "swift-lsp",
        "sourcekit-lsp",
        "ships with Xcode (`xcrun sourcekit-lsp`)",
    ),
    (
        has_java,
        "Java",
        "jdtls-lsp",
        "jdtls",
        "brew install jdtls (or download Eclipse JDT.LS)",
    ),
    (
        has_go,
        "Go",
        "gopls-lsp",
        "gopls",
        "go install golang.org/x/tools/gopls@latest",
    ),
    (
        has_node,
        "Web/TS",
        "typescript-lsp",
        "typescript-language-server",
        "npm install -g typescript typescript-language-server",
    ),
]


def lsp_advisory(project_dir):
    """Print a per-detected-language LSP recommendation. Solid Forge does NOT bundle
    .lsp.json or install language servers — the official per-language LSP plugins
    (claude-plugins-official) own the Claude<->LSP wiring + auto-diagnostics. This
    is advisory text only (no mutation).

    The LSP *binary* is probed on $PATH (have()); if already installed, only the
    plugin line shows (no redundant install hint — report_gates separately checks
    the gate type-checkers like pyright/tsc). The Claude Code *plugin* (e.g.
    pyright-lsp) cannot be probed — its install state is not on $PATH — so the
    plugin line always shows; that limitation is coverage-noted up front (rule 3),
    never a silent repeat."""
    hits = [
        (lang, plugin, bin_cmd, bin_install)
        for pred, lang, plugin, bin_cmd, bin_install in _LSP_ADVISORY
        if pred(project_dir)
    ]
    if not hits:
        return
    print(
        "\nLSP / code-intelligence advisory (opt-in; the official Claude Code plugins own the wiring + auto-diagnostics):"
    )
    print(
        "  (arm cannot detect whether a Claude Code plugin is already installed — "
        "plugin state is not on $PATH — so plugin lines always show; ignore one "
        "already installed. LSP binary detection is per line.)"
    )
    for lang, plugin, bin_cmd, bin_install in hits:
        if have(bin_cmd):
            print(
                f"  {lang:<7}: plugin `{plugin}` (LSP binary `{bin_cmd}` already on $PATH)"
            )
        else:
            print(f"  {lang:<7}: plugin `{plugin}`; binary `{bin_install}`")
    print(
        "  (Solid Forge does NOT bundle .lsp.json or install language servers; opt in per language.)"
    )


# --- report ------------------------------------------------------------------


def report_gates(project_dir):
    print("\nToolchain / gate status:")
    checks = [
        ("python3 (required)", have("python3"), True),
        ("ruff (Python fast gate)", tool_present(project_dir, "ruff"), False),
        (
            "import-linter (Python arch gate)",
            tool_present(project_dir, "lint-imports"),
            False,
        ),
        ("pylint (Python cyclic)", tool_present(project_dir, "pylint"), False),
        ("swift toolchain (Swift gate)", have("swift"), False),
        ("swiftlint (Swift arch gate)", have("swiftlint"), False),
        ("cargo (Rust gate)", have("cargo"), False),
        ("rustfmt (Rust fast gate)", have("rustfmt"), False),
        ("clippy (Rust arch gate)", have("cargo-clippy"), False),
        ("node (Web gate)", have("node"), False),
        ("eslint (Web gate)", tool_present(project_dir, "eslint"), False),
        (
            "dependency-cruiser (Web arch gate)",
            tool_present(project_dir, "depcruise"),
            False,
        ),
        ("pyright (Python type gate)", tool_present(project_dir, "pyright"), False),
        ("tsc (Web type gate)", tool_present(project_dir, "tsc"), False),
        ("gitleaks (secrets gate)", have("gitleaks"), False),
        (
            "pip-audit (Python supply-chain)",
            tool_present(project_dir, "pip-audit"),
            False,
        ),
        ("npm audit (Web supply-chain)", have("npm"), False),
        ("cargo-audit (Rust supply-chain)", have("cargo-audit"), False),
        ("pytest (Python test gate)", tool_present(project_dir, "pytest"), False),
        ("vitest (Web test gate)", tool_present(project_dir, "vitest"), False),
        ("mvn / gradle (Java build + test)", have("mvn") or have("gradle"), False),
        ("javac (Java type gate)", have("javac"), False),
        ("google-java-format (Java fast gate)", have("google-java-format"), False),
        ("checkstyle (Java arch gate)", have("checkstyle"), False),
        ("dependency-check (Java supply-chain)", have("dependency-check"), False),
        ("go (Go build + test)", have("go"), False),
        ("gofmt (Go fast gate)", have("gofmt"), False),
        ("golangci-lint (Go arch gate)", have("golangci-lint"), False),
        (
            "govulncheck (Go supply-chain)",
            tool_present(project_dir, "govulncheck"),
            False,
        ),
    ]
    absent = []
    for label, present, required in checks:
        flag = (
            "OK"
            if present
            else ("MISSING (required!)" if required else "absent (gate degrades)")
        )
        print(f"  - {label}: {flag}")
        if not present and not required:
            absent.append(label)
    return absent


def absent_tool_hint(absent_labels, with_tools):
    """Surface missing gate tools (notably the type/supply-chain/test tools that may be new since an older install). Returns the hint text, or None when nothing is absent or --with-tools already provisions/prints install commands."""
    if with_tools or not absent_labels:
        return None
    return "Some gate tools are absent (see status above) — including tools that may be new since your last install (type / supply-chain / test). Re-run with --with-tools to provision project-local tools (pip-audit, pytest-json-report, vitest, ...) and to print install commands for system tools (gitleaks, cargo-audit, cargo-nextest)."


# --- --revert: inverse of THIS script's provisioning (dry-run default, --apply) ---


def _same_content(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def _remove_section(text, heading):
    """Remove the span from the line equal to `heading` through the next top-level '## ' heading or EOF. Returns (new_text, removed)."""
    lines = text.splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.strip() == heading.strip()), None)
    if idx is None:
        return text, False
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    new_lines = lines[:idx] + lines[end:]
    new_text = "\n".join(new_lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, True


def _same_content_normalized(dst, src, name):
    """Like _same_content, but for .importlinter.ini normalizes the ACF-I1 root_package
    substitution back to the template placeholder (__REPLACE_ME__) before comparing — so a
    freshly-armed, unedited config (root_package auto-detected) is still 'matches template'
    and removable by --revert. Any OTHER diff (the user edited layers, etc.) = customized."""
    if name != ".importlinter.ini":
        return _same_content(dst, src)
    try:
        with open(dst, encoding="utf-8") as fh:
            dst_text = fh.read()
        with open(src, encoding="utf-8") as fh:
            src_text = fh.read()
    except OSError:
        return False
    dst_norm = re.sub(
        r"root_package\s*=\s*.+", "root_package = __REPLACE_ME__", dst_text
    )
    return dst_norm == src_text


def uninstall_arch_configs(project_dir, apply):
    """Remove arch-configs arm.py copied, but ONLY if they still match the template (untouched). A config the user edited is the user's — leave it and warn."""
    removed = []
    customized = []
    for name, _ in ARCH_CONFIGS:
        dst = os.path.join(project_dir, name)
        src = os.path.join(TEMPLATES_SRC, name)
        if not os.path.exists(dst):
            continue
        if os.path.exists(src) and _same_content_normalized(dst, src, name):
            removed.append(name)
        else:
            customized.append(name)
    if not removed and not customized:
        print("  arch-configs: none present")
        return
    verb = "would remove" if not apply else "removed"
    for name in removed:
        print(f"  arch-configs: {verb} {name} (matches template)")
    for name in customized:
        print(
            f"  arch-configs: KEPT {name} (differs from template — looks user-edited; remove manually if wanted)"
        )
    if apply:
        for name in removed:
            try:
                os.remove(os.path.join(project_dir, name))
            except OSError as exc:
                print(f"  ! failed to remove {name}: {exc}")


def uninstall_external_configs(project_dir, apply):
    """Remove external-tool configs arm.py scaffolded, but ONLY if they still match the
    template (untouched). A config the user edited is KEPT + warned. Mirrors
    uninstall_arch_configs."""
    removed = []
    customized = []
    for name, _key, _note in EXTERNAL_CONFIGS:
        dst = os.path.join(project_dir, name)
        src = os.path.join(TEMPLATES_SRC, name)
        if not os.path.exists(dst):
            continue
        if os.path.exists(src) and _same_content(dst, src):
            removed.append(name)
        else:
            customized.append(name)
    if not removed and not customized:
        print("  external-configs: none present")
        return
    verb = "would remove" if not apply else "removed"
    for name in removed:
        print(f"  external-configs: {verb} {name} (matches template)")
    for name in customized:
        print(
            f"  external-configs: KEPT {name} (differs from template — user-edited; "
            "remove manually)"
        )
    if apply:
        for name in removed:
            try:
                os.remove(os.path.join(project_dir, name))
            except OSError as exc:
                print(f"  ! failed to remove {name}: {exc}")


def uninstall_claude_md_sections(project_dir, apply):
    cmd_path = os.path.join(project_dir, "AGENTS.md")
    if not os.path.exists(cmd_path):
        print("  AGENTS.md: not present")
        return
    with open(cmd_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    changed = False
    for heading, label in (
        (CONSTITUTION_HEADING, "L1 Constitution"),
        (TOOLCHAIN_HEADING, "Gate Toolchain note"),
    ):
        new_text, removed = _remove_section(text, heading)
        if removed:
            changed = True
            verb = "would remove" if not apply else "removed"
            print(f"  AGENTS.md: {verb} {label} section")
            text = new_text
        else:
            print(f"  AGENTS.md: {label} section not present")
    if changed and apply:
        with open(cmd_path, "w", encoding="utf-8") as fh:
            fh.write(text)


def uninstall_blueprint_templates(project_dir, apply):
    base = os.path.join(project_dir, "docs", "intent-blueprints", "_templates")
    names = ("intent-blueprint.template.md", "cold-start-patterns")
    found = False
    for name in names:
        p = os.path.join(base, name)
        if os.path.isdir(p):
            found = True
            verb = "would remove" if not apply else "removed"
            print(f"  blueprints: {verb} {name}/")
            if apply:
                shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            found = True
            verb = "would remove" if not apply else "removed"
            print(f"  blueprints: {verb} {name}")
            if apply:
                try:
                    os.remove(p)
                except OSError as exc:
                    print(f"  ! failed to remove {name}: {exc}")
    if not found:
        print("  blueprints: no arming templates found")


def uninstall_env_example(project_dir, apply):
    """Remove the provisioned `.env.solidforge.example`, but ONLY if it still matches the
    template (untouched). One the user edited is KEPT + warned (mirrors
    uninstall_arch_configs / uninstall_external_configs)."""
    name = ".env.solidforge.example"
    dst = os.path.join(project_dir, name)
    src = os.path.join(TEMPLATES_SRC, name)
    if not os.path.exists(dst):
        print("  env-example: not present")
        return
    if os.path.exists(src) and _same_content(dst, src):
        verb = "would remove" if not apply else "removed"
        print(f"  env-example: {verb} {name} (matches template)")
        if apply:
            os.remove(dst)
    else:
        print(
            f"  env-example: KEPT {name} (differs from template — looks user-edited; remove manually if wanted)"
        )


def uninstall_gitignore(project_dir, apply):
    gi = os.path.join(project_dir, ".gitignore")
    if not os.path.exists(gi):
        print("  .gitignore: not present")
        return
    with open(gi, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    pending = [e for e in GITIGNORE_ENTRIES if any(line.strip() == e for line in lines)]
    if not pending:
        print("  .gitignore: parallel-dev entries not present")
        return
    verb = "would remove" if not apply else "removed"
    print(
        f"  .gitignore: {verb} {len(pending)} parallel-dev entr"
        + ("y" if len(pending) == 1 else "ies")
    )
    if apply:
        kept = [line for line in lines if line.strip() not in GITIGNORE_ENTRIES]
        with open(gi, "w", encoding="utf-8") as fh:
            fh.writelines(kept)


def do_revert(project_dir, apply):
    print(
        "\n--revert: removing Solid Forge arming from project"
        + (" [APPLY]" if apply else " [DRY-RUN — pass --apply to remove]")
    )
    uninstall_arch_configs(project_dir, apply)
    uninstall_external_configs(project_dir, apply)
    uninstall_claude_md_sections(project_dir, apply)
    uninstall_blueprint_templates(project_dir, apply)
    uninstall_env_example(project_dir, apply)
    uninstall_gitignore(project_dir, apply)


def main():
    args = sys.argv[1:]
    with_tools = "--with-tools" in args
    revert = "--revert" in args
    apply = "--apply" in args
    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        if i + 1 >= len(args):
            print(
                "--lang requires a value (python|web|rust|swift|java|go)",
                file=sys.stderr,
            )
            sys.exit(2)
        lang = args[i + 1]
        del args[i : i + 2]
    # --scaffold-configs [vale,semgrep,spectral]: optional-value flag. Bare flag = all
    # three; a comma-list selects a subset. The next arg is the value only if it does
    # NOT start with "--" (so `--scaffold-configs --with-tools` is bare, not a value).
    # Unknown key -> exit 2. Ignored under --revert (warning, not exit — see below).
    scaffold_present = "--scaffold-configs" in args
    scaffold_tools = None  # None = bare flag (all three); set = named subset
    if scaffold_present:
        i = args.index("--scaffold-configs")
        known_ext = {key for _, key, _ in EXTERNAL_CONFIGS}
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            selected = set()
            for k in args[i + 1].split(","):
                k = k.strip()
                if k not in known_ext:
                    print(
                        f"unknown --scaffold-configs tool {k!r}; known: "
                        f"{', '.join(sorted(known_ext))}",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                selected.add(k)
            scaffold_tools = selected
            del args[i + 1]
        del args[i]
    args = [a for a in args if a not in ("--with-tools", "--revert", "--apply")]
    known_langs = ("python", "web", "rust", "swift", "java", "go")
    if lang is not None and lang not in known_langs:
        print(
            f"unknown --lang {lang!r}; known: {', '.join(known_langs)}",
            file=sys.stderr,
        )
        sys.exit(2)
    if lang is not None and not with_tools:
        print(
            "--lang only takes effect under --with-tools "
            "(it filters which ecosystems get tools).",
            file=sys.stderr,
        )
        sys.exit(2)
    if apply and not revert:
        print("--apply only takes effect under --revert.", file=sys.stderr)
        sys.exit(2)
    if revert and with_tools:
        print("--revert is exclusive of --with-tools.", file=sys.stderr)
        sys.exit(2)
    if revert and scaffold_present:
        # forward-only arming flag; revert unconditionally removes what arming added
        # (mirrors uninstall_arch_configs, which runs under --revert regardless of how
        # the config was armed). Warn, do not exit 2 — unlike --lang, this flag is
        # independent of --with-tools.
        print(
            "--scaffold-configs ignored under --revert (revert removes what arming "
            "added, regardless of which flag armed it).",
            file=sys.stderr,
        )
    project_dir = (
        args[0] if args else (os.environ.get("SOLIDFORGE_PROJECT_DIR") or os.getcwd())
    )
    project_dir = os.path.abspath(project_dir)
    if not os.path.isdir(project_dir):
        print(f"target project dir not found: {project_dir}", file=sys.stderr)
        sys.exit(1)
    if not have("python3"):
        print("python3 not found on PATH — install it first.", file=sys.stderr)
        sys.exit(1)

    if revert:
        mode = " --apply" if apply else " [dry-run]"
        print(f"Reverting Solid Forge arming from: {project_dir}{mode}\n")
        do_revert(project_dir, apply)
        print(
            "\nDone. Arming removed. Files you authored or edited (customized arch-configs, your own AGENTS.md content) were left in place. Gates are preset-level — stop the solidforge preset session to deactivate them."
        )
        return

    mode = " --with-tools" if with_tools else ""
    print(f"Arming project for Solid Forge: {project_dir}{mode}\n")

    copy_arch_configs(project_dir)
    if scaffold_present:
        copy_external_configs(project_dir, scaffold_tools)
        # M1: a scaffolded .vale.ini references style packages the adapter no-ops
        # without; auto-sync when vale is armed (mirrors --with-tools running uv add /
        # npm install). If vale is absent the gate stays a no-op until the user
        # installs vale + syncs — the adapter coverage-notes that, never silent.
        if (scaffold_tools is None or "vale" in scaffold_tools) and have("vale"):
            print(
                "  + running `vale sync` to fetch style packages into .vale/styles/ ..."
            )
            rc, out = run_cwd(["vale", "sync"], project_dir, timeout=120)
            print(
                f"  + vale sync: {'ok' if rc == 0 else 'FAILED'}"
                + (f" — {tail1(out)}" if rc else "")
            )
    copy_blueprint_templates(project_dir)
    copy_env_example(project_dir)
    update_gitignore(project_dir)
    append_constitution(project_dir)
    if with_tools:
        prepare_tools(project_dir, lang)
        write_toolchain_note(project_dir, lang)
    lsp_advisory(project_dir)
    absent = report_gates(project_dir)
    hint = absent_tool_hint(absent, with_tools)
    if hint:
        print("\n" + hint)
    print(
        "\nDone. Gate listeners are preset-level (active when the solidforge-loop-gates plugin runs). "
        "Gate tools / arch-configs / constitution are project-local here. "
        "Reversible: arm.py --revert (add --apply to execute)."
    )


if __name__ == "__main__":
    main()
