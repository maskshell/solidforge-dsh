#!/usr/bin/env python3
"""Regression test: arm.copy_arch_configs copies a language's arch config IFF that language is detected in the project (Layer 2 provisioning via arm.py / /solidforge:arm-tools).

Guards the bug where a Python-only project received .swiftlint.yml / .dependency-cruiser.cjs / clippy.toml. The copy decision reuses the same per-language detectors that prepare_tools / write_toolchain_note use, so config, deps, and the AGENTS.md toolchain note never disagree.

Also covers arm.py idempotency (t_arm_idempotent) — salvaged from the retired install_upgrade.py. See the coverage note below.

Run:
    python3 infra/test/arm_copy_config.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(ROOT, "infra")
TEMPLATES = os.path.join(INFRA, "templates")
ARM_PY = os.path.join(INFRA, "install", "arm.py")

# Load arm.py as a module (its main() is __main__-guarded, so import is safe).
_spec = importlib.util.spec_from_file_location("pd_arm", ARM_PY)
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

# Coverage note (workspace rule 3): the --upgrade reconcilers that used to live in install.py (reconcile_settings, prune_arch_configs, refresh_constitution/toolchain, version-stamp/drift) are RETIRED — they are plugin-manager operations (plugin update), not deterministically testable from within the skill. Only the idempotency of the surviving arm.py provisioning is testable, asserted below as t_arm_idempotent.

# (marker file that triggers the language, config that should copy, configs that must NOT)
# Every ARCH_CONFIGS entry MUST have a case here — adding a language without a case fails the coverage assertion below, so a new config can't silently never copy.
CASES = [
    ("pyproject.toml", ".importlinter.ini"),  # python
    ("package.json", ".dependency-cruiser.cjs"),  # web/ts
    ("Package.swift", ".swiftlint.yml"),  # swift
    ("Cargo.toml", "clippy.toml"),  # rust
    ("pom.xml", "checkstyle.xml"),  # java (maven)
    ("go.mod", ".golangci.yml"),  # go
]
ALL_CONFIGS = [name for name, _ in arm.ARCH_CONFIGS]

# External-tool configs (the --scaffold-configs registry). NOT language-bound — no
# marker; selection is by tool key. Every EXTERNAL_CONFIGS entry MUST have a case here
# (the coverage guard below enforces it), mirroring the ARCH_CONFIGS guard.
EXT_CASES = [
    ("vale", ".vale.ini"),
    ("semgrep", ".semgrep.yml"),
    ("spectral", ".spectral.yaml"),
]
EXT_ALL = [name for name, _, _ in arm.EXTERNAL_CONFIGS]


def fail(msg):
    print(f"  FAIL: {msg}")
    return False


def run_case(marker, expected):
    tmp = tempfile.mkdtemp(prefix="pd_arm_test_")
    try:
        # create the ONE marker for this language; nothing else
        with open(os.path.join(tmp, marker), "w") as fh:
            fh.write("")
        arm.copy_arch_configs(tmp)
        present = {c for c in ALL_CONFIGS if os.path.exists(os.path.join(tmp, c))}
        want = {expected}
        if present != want:
            return fail(f"{marker}: expected {{{expected}}}, got {sorted(present)}")
        print(f"  ok: {marker} -> {expected} only")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_ext_case(key, expected):
    tmp = tempfile.mkdtemp(prefix="pd_arm_ext_")
    try:
        arm.copy_external_configs(tmp, {key})
        present = {c for c in EXT_ALL if os.path.exists(os.path.join(tmp, c))}
        want = {expected}
        if present != want:
            return fail(
                f"--scaffold-configs {key}: expected {{{expected}}}, got {sorted(present)}"
            )
        print(f"  ok: --scaffold-configs {key} -> {expected} only")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_arm_idempotent():
    """arm.py provisioning is exit-0, idempotent (constitution appended once), and provisions arch-config + gitignore. Salvaged honesty residue of install_upgrade.py (the upgrade reconcilers themselves are retired — see coverage note in the module docstring)."""
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'ok' if cond else 'FAIL'}: {name}")

    tmp = tempfile.mkdtemp(prefix="pd_arm_idem_")
    try:
        with open(os.path.join(tmp, "pyproject.toml"), "w") as fh:
            fh.write("")
        proc = subprocess.run(
            [sys.executable, ARM_PY, tmp], capture_output=True, text=True
        )
        check("arm exit 0", proc.returncode == 0)
        check(
            "arm appends constitution",
            arm.CONSTITUTION_HEADING in open(os.path.join(tmp, "AGENTS.md")).read(),
        )
        check(
            "arm copies arch-config",
            os.path.exists(os.path.join(tmp, ".importlinter.ini")),
        )
        check(
            "arm adds gitignore loop-state entry",
            ".solidforge/loop/loop-state.json"
            in open(os.path.join(tmp, ".gitignore")).read(),
        )
        check(
            "arm provisions .env.solidforge.example (different-family secrets placeholder)",
            os.path.exists(os.path.join(tmp, ".env.solidforge.example")),
        )
        check(
            "arm adds .env.solidforge to .gitignore (live secrets ignored; .example committed)",
            "\n.env.solidforge\n"
            in "\n" + open(os.path.join(tmp, ".gitignore")).read(),
        )
        check(
            "arm adds !.env.solidforge.example negation (placeholder committable even with .env.*)",
            "!.env.solidforge.example" in open(os.path.join(tmp, ".gitignore")).read(),
        )
        # second arm — idempotent (constitution not duplicated)
        proc2 = subprocess.run(
            [sys.executable, ARM_PY, tmp], capture_output=True, text=True
        )
        check("arm second run exit 0", proc2.returncode == 0)
        claude = open(os.path.join(tmp, "AGENTS.md")).read()
        check(
            "arm idempotent: constitution once",
            claude.count(arm.CONSTITUTION_HEADING) == 1,
        )
        check(
            "arm idempotent: reports already-present/skipped",
            "already present" in proc2.stdout or "skipped" in proc2.stdout,
        )
        # --scaffold-configs: provisions the 3 external configs; idempotent on re-run
        proc3 = subprocess.run(
            [sys.executable, ARM_PY, tmp, "--scaffold-configs"],
            capture_output=True,
            text=True,
        )
        check("arm --scaffold-configs exit 0", proc3.returncode == 0)
        check(
            "arm --scaffold-configs copies .vale.ini",
            os.path.exists(os.path.join(tmp, ".vale.ini")),
        )
        check(
            "arm --scaffold-configs copies .spectral.yaml",
            os.path.exists(os.path.join(tmp, ".spectral.yaml")),
        )
        # second scaffold run — idempotent (already present, not clobbered)
        proc4 = subprocess.run(
            [sys.executable, ARM_PY, tmp, "--scaffold-configs"],
            capture_output=True,
            text=True,
        )
        check("arm --scaffold-configs second run exit 0", proc4.returncode == 0)
        check(
            "arm --scaffold-configs idempotent: reports already-present/skipped",
            "already present" in proc4.stdout or "skipped" in proc4.stdout,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return all(ok for _, ok in results)


def main():
    ok = True
    print("copy_arch_configs gating:")

    # structural guard: ARCH_CONFIGS is well-formed (name, predicate) tuples
    for entry in arm.ARCH_CONFIGS:
        if not (isinstance(entry, tuple) and len(entry) == 2):
            ok = fail(f"ARCH_CONFIGS entry not a (name, predicate) tuple: {entry!r}")

    # coverage guard: every declared config has a template AND a test case
    for name, _ in arm.ARCH_CONFIGS:
        if not os.path.exists(os.path.join(TEMPLATES, name)):
            ok = fail(f"ARCH_CONFIGS names a config with no template: {name}")
    declared = set(ALL_CONFIGS)
    tested = {cfg for _, cfg in CASES}
    if declared != tested:
        ok = fail(
            f"ARCH_CONFIGS vs CASES mismatch: declared={sorted(declared)} tested={sorted(tested)}"
        )

    # multi-language: a python+rust project gets exactly those two configs
    tmp = tempfile.mkdtemp(prefix="pd_arm_multi_")
    try:
        for m in ("pyproject.toml", "Cargo.toml"):
            with open(os.path.join(tmp, m), "w") as fh:
                fh.write("")
        arm.copy_arch_configs(tmp)
        present = {c for c in ALL_CONFIGS if os.path.exists(os.path.join(tmp, c))}
        want = {".importlinter.ini", "clippy.toml"}
        if present != want:
            ok = fail(
                f"multi (py+rust): expected {sorted(want)}, got {sorted(present)}"
            )
        else:
            print(f"  ok: py+rust -> {sorted(want)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # no-language: nothing copies
    tmp = tempfile.mkdtemp(prefix="pd_arm_none_")
    try:
        arm.copy_arch_configs(tmp)
        present = {c for c in ALL_CONFIGS if os.path.exists(os.path.join(tmp, c))}
        if present:
            ok = fail(f"empty project: expected no configs, got {sorted(present)}")
        else:
            print("  ok: empty project -> no configs")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\ncopy_external_configs (--scaffold-configs) gating:")

    # structural guard: EXTERNAL_CONFIGS is well-formed (filename, key, note) 3-tuples
    for entry in arm.EXTERNAL_CONFIGS:
        if not (isinstance(entry, tuple) and len(entry) == 3):
            ok = fail(f"EXTERNAL_CONFIGS entry not a 3-tuple: {entry!r}")

    # coverage guard: every declared external config has a template AND a test case
    for name, _key, _note in arm.EXTERNAL_CONFIGS:
        if not os.path.exists(os.path.join(TEMPLATES, name)):
            ok = fail(f"EXTERNAL_CONFIGS names a config with no template: {name}")
    ext_keys = {key for _, key, _ in arm.EXTERNAL_CONFIGS}
    ext_tested_keys = {key for key, _ in EXT_CASES}
    if ext_keys != ext_tested_keys:
        ok = fail(
            f"EXTERNAL_CONFIGS vs EXT_CASES key mismatch: "
            f"declared={sorted(ext_keys)} tested={sorted(ext_tested_keys)}"
        )

    # multi-tool: --scaffold-configs vale,semgrep -> exactly those two
    tmp = tempfile.mkdtemp(prefix="pd_arm_ext_multi_")
    try:
        arm.copy_external_configs(tmp, {"vale", "semgrep"})
        present = {c for c in EXT_ALL if os.path.exists(os.path.join(tmp, c))}
        want = {".vale.ini", ".semgrep.yml"}
        if present != want:
            ok = fail(
                f"multi (vale+semgrep): expected {sorted(want)}, got {sorted(present)}"
            )
        else:
            print(f"  ok: --scaffold-configs vale,semgrep -> {sorted(want)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # bare flag: tools=None -> all three
    tmp = tempfile.mkdtemp(prefix="pd_arm_ext_bare_")
    try:
        arm.copy_external_configs(tmp, None)
        present = {c for c in EXT_ALL if os.path.exists(os.path.join(tmp, c))}
        if present != set(EXT_ALL):
            ok = fail(
                f"bare flag: expected all {sorted(set(EXT_ALL))}, got {sorted(present)}"
            )
        else:
            print(f"  ok: bare --scaffold-configs -> all {len(EXT_ALL)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # skip-if-exists: a pre-existing config is never clobbered
    tmp = tempfile.mkdtemp(prefix="pd_arm_ext_skip_")
    try:
        with open(os.path.join(tmp, ".vale.ini"), "w") as fh:
            fh.write("# user-authored Vale config (must not be clobbered)\n")
        arm.copy_external_configs(tmp, None)
        kept = open(os.path.join(tmp, ".vale.ini")).read()
        if "user-authored" not in kept:
            ok = fail(
                f"copy_external_configs clobbered a pre-existing .vale.ini: {kept!r}"
            )
        else:
            print("  ok: pre-existing .vale.ini not clobbered")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for key, expected in EXT_CASES:
        ok = run_ext_case(key, expected) and ok

    for marker, expected in CASES:
        ok = run_case(marker, expected) and ok

    print("\nt_arm_idempotent:")
    ok = t_arm_idempotent() and ok

    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
