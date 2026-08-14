#!/usr/bin/env python3
"""Regression tests for arm.py --revert (the project-side inverse of arming).

Covers: mutual-exclusion guards, dry-run leaves the project untouched, --revert --apply removes every arming artifact (arch-configs / constitution section / blueprint templates / .gitignore entries) while keeping user hooks + user AGENTS.md content, arch-configs a user edited are preserved (not nuked), idempotency, and AGENTS.md section removal preserving surrounding content.

Coverage note (workspace rule 3): the FULL --uninstall of the old install.py (which also removed copied hook scripts, the .solidforge/loop/ dir, and skill-attributed hook entries from settings.json) is RETIRED — under the plugin model those artifacts no longer live in the project (hooks run from the plugin root; runtime state is written to $SOLIDFORGE_PROJECT_DIR on demand). Their removal is a plugin-disable, not skill-testable. Only the project-side provisioning (arch-configs / constitution / templates / gitignore) has an in-skill inverse, tested here as --revert.

Run:
    python3 infra/test/arm_revert.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(ROOT, "infra")
ARM_PY = os.path.join(INFRA, "install", "arm.py")

_spec = importlib.util.spec_from_file_location("pd_arm", ARM_PY)
assert _spec is not None and _spec.loader is not None, f"could not load {ARM_PY}"
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  {'ok' if cond else 'FAIL'}: {name}")


def run(args):
    proc = subprocess.run(
        [sys.executable, ARM_PY] + args, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout


def make_fixture():
    """A project with USER content (user-owned content) that must survive arm -> --revert. arm.py does NOT touch .solidforge/hooks or user config, so user-owned content there is never at risk."""
    tmp = tempfile.mkdtemp(prefix="pd_revert_test_")
    with open(os.path.join(tmp, "pyproject.toml"), "w") as fh:
        fh.write("")
    os.makedirs(os.path.join(tmp, ".solidforge", "hooks"))
    with open(
        os.path.join(tmp, ".solidforge", "hooks", "my_hook.py"), "w"
    ) as fh:  # user hook
        fh.write("# user-owned\n")
    with open(os.path.join(tmp, "AGENTS.md"), "w") as fh:
        fh.write("# My Project\n\nSome user notes.\n")
    return tmp


def t_mutual_exclusion():
    tmp = make_fixture()
    try:
        rc, _ = run([tmp, "--revert", "--with-tools"])
        check("--revert + --with-tools exits 2", rc == 2)
        rc, _ = run([tmp, "--apply"])
        check("--apply without --revert exits 2", rc == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_dry_run_no_mutation():
    tmp = make_fixture()
    try:
        run([tmp])  # arm
        rc, out = run([tmp, "--revert"])
        check("revert dry-run exit 0", rc == 0)
        check("revert dry-run lists would-remove", "would remove" in out)
        check(
            "dry-run keeps arch-config",
            os.path.exists(os.path.join(tmp, ".importlinter.ini")),
        )
        check(
            "dry-run keeps constitution",
            arm.CONSTITUTION_HEADING in open(os.path.join(tmp, "AGENTS.md")).read(),
        )
        check(
            "dry-run keeps blueprint template",
            os.path.exists(
                os.path.join(
                    tmp,
                    "docs",
                    "intent-blueprints",
                    "_templates",
                    "intent-blueprint.template.md",
                )
            ),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_apply_removes_arming_keeps_user():
    tmp = make_fixture()
    try:
        run([tmp])  # arm
        gi_after_arm = open(os.path.join(tmp, ".gitignore"), encoding="utf-8").read()
        check(
            "gitignore loop-state entry added on arm",
            ".solidforge/loop/loop-state.json" in gi_after_arm,
        )
        check(
            "gitignore runs/ entry added on arm",
            ".solidforge/loop/runs/" in gi_after_arm,
        )
        rc, _ = run([tmp, "--revert", "--apply"])
        check("revert apply exit 0", rc == 0)
        # arming artifacts removed
        check(
            ".importlinter.ini removed (matched template)",
            not os.path.exists(os.path.join(tmp, ".importlinter.ini")),
        )
        check(
            ".env.solidforge.example removed (matched template)",
            not os.path.exists(os.path.join(tmp, ".env.solidforge.example")),
        )
        check(
            "blueprint templates removed",
            not os.path.exists(
                os.path.join(
                    tmp,
                    "docs",
                    "intent-blueprints",
                    "_templates",
                    "intent-blueprint.template.md",
                )
            ),
        )
        # user content preserved
        check(
            "user hook file kept",
            os.path.exists(os.path.join(tmp, ".solidforge", "hooks", "my_hook.py")),
        )
        claude = open(os.path.join(tmp, "AGENTS.md"), encoding="utf-8").read()
        check("constitution section removed", arm.CONSTITUTION_HEADING not in claude)
        check(
            "user AGENTS.md content kept",
            "# My Project" in claude and "Some user notes." in claude,
        )
        gi = open(os.path.join(tmp, ".gitignore"), encoding="utf-8").read()
        check(
            "gitignore loop-state entry removed",
            ".solidforge/loop/loop-state.json" not in gi,
        )
        check("gitignore runs/ entry removed", ".solidforge/loop/runs/" not in gi)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_arch_config_user_edit_kept():
    tmp = make_fixture()
    try:
        run([tmp])  # arm -> .importlinter.ini matches template
        with open(os.path.join(tmp, ".importlinter.ini"), "a") as fh:  # user edit
            fh.write("\n# my custom contract\n")
        _, out = run([tmp, "--revert", "--apply"])
        check(
            "revert keeps user-edited arch-config",
            os.path.exists(os.path.join(tmp, ".importlinter.ini")),
        )
        check("revert warns about kept config", "KEPT .importlinter.ini" in out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_external_config_template_removed():
    tmp = make_fixture()
    try:
        run(
            [tmp, "--scaffold-configs"]
        )  # arms .vale.ini / .semgrep.yml / .spectral.yaml
        check(
            "scaffolded .vale.ini present before revert",
            os.path.exists(os.path.join(tmp, ".vale.ini")),
        )
        run([tmp, "--revert", "--apply"])
        check(
            "revert removes template-matching .vale.ini",
            not os.path.exists(os.path.join(tmp, ".vale.ini")),
        )
        check(
            "revert removes template-matching .spectral.yaml",
            not os.path.exists(os.path.join(tmp, ".spectral.yaml")),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_external_config_user_edit_kept():
    tmp = make_fixture()
    try:
        run([tmp, "--scaffold-configs"])  # .vale.ini matches template
        with open(os.path.join(tmp, ".vale.ini"), "a") as fh:  # user edit
            fh.write("\n# my house style override\n")
        _, out = run([tmp, "--revert", "--apply"])
        check(
            "revert keeps user-edited external config",
            os.path.exists(os.path.join(tmp, ".vale.ini")),
        )
        check("revert warns about kept external config", "KEPT .vale.ini" in out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_idempotent():
    tmp = make_fixture()
    try:
        run([tmp])
        run([tmp, "--revert", "--apply"])
        rc, out = run([tmp, "--revert", "--apply"])  # second time
        check("second revert apply exit 0", rc == 0)
        # action lines are indented "<area>: removed <what>"; the always-on footer "Done. ..." is NOT indented, so exclude it.
        removals = [
            ln for ln in out.splitlines() if ln.startswith("  ") and "removed " in ln
        ]
        check("second revert finds nothing to remove", not removals)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_claude_md_sections_unit():
    tmp = tempfile.mkdtemp(prefix="pd_revert_unit_")
    try:
        text = (
            "# Proj\n\n"
            + arm.CONSTITUTION_HEADING
            + "\n\nconstitution body.\n\n"
            + arm.TOOLCHAIN_HEADING
            + "\n\ntoolchain body.\n\n"
            + "## Other Section\n\nkept.\n"
        )
        with open(os.path.join(tmp, "AGENTS.md"), "w") as fh:
            fh.write(text)
        arm.uninstall_claude_md_sections(tmp, apply=True)
        result = open(os.path.join(tmp, "AGENTS.md"), encoding="utf-8").read()
        check("constitution section removed", arm.CONSTITUTION_HEADING not in result)
        check("toolchain section removed", arm.TOOLCHAIN_HEADING not in result)
        check("following section preserved", "## Other Section" in result)
        check("unrelated content preserved", "# Proj" in result and "kept." in result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    for fn in (
        t_mutual_exclusion,
        t_dry_run_no_mutation,
        t_apply_removes_arming_keeps_user,
        t_arch_config_user_edit_kept,
        t_external_config_template_removed,
        t_external_config_user_edit_kept,
        t_idempotent,
        t_claude_md_sections_unit,
    ):
        print(f"\n{fn.__name__}:")
        fn()
    failed = [n for n, ok in RESULTS if not ok]
    print(
        f"\n{'PASS' if not failed else 'FAIL'} ({len(RESULTS) - len(failed)}/{len(RESULTS)})"
    )
    if failed:
        for n in failed:
            print(f"  FAILED: {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
