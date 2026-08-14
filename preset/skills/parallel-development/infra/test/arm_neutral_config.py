#!/usr/bin/env python3
"""ACF coverage: detect_root_package + _count_active_contracts + _same_content_normalized.

Tests the arm placeholder arch-config fix (ADR #49):
  - detect_root_package: pyproject [project] name / src-layout / flat-layout / detect-failure.
  - _count_active_contracts (arch_contract_python.py): 0-active (neutral template) / N-active /
    comment-skipping (commented [importlinter:contract:] not counted).
  - _same_content_normalized: a freshly-armed .importlinter.ini (root_package substituted) is
    still 'matches template' for --revert (token normalized); any other diff = customized.

Self-contained (rule 7): loads arm.py + arch_contract_python.py via importlib. Run:
    python3 infra/test/arm_neutral_config.py
"""

import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(ROOT, "infra")
TEMPLATES = os.path.join(INFRA, "templates")
ARM_PY = os.path.join(INFRA, "install", "arm.py")
GATE_PY = os.path.join(INFRA, "scripts", "arch_contract_python.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


arm = _load(ARM_PY, "pd_arm_neutral")
gate = _load(GATE_PY, "pd_gate_neutral")


def fail(msg):
    print(f"  FAIL: {msg}")
    return False


def main():
    ok = True
    print("detect_root_package:")

    # (a) pyproject [project] name
    tmp = tempfile.mkdtemp(prefix="acf_drpp_a_")
    try:
        open(os.path.join(tmp, "pyproject.toml"), "w").write(
            '[project]\nname = "my-cool-pkg"\n'
        )
        r = arm.detect_root_package(tmp)
        if r != "my_cool_pkg":
            ok = fail(f"pyproject name: expected my_cool_pkg, got {r}")
        else:
            print(f"  ok: pyproject name -> {r}")
    finally:
        shutil.rmtree(tmp)

    # (b) src-layout
    tmp = tempfile.mkdtemp(prefix="acf_drpp_b_")
    try:
        pkg = os.path.join(tmp, "src", "myproj")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").write("")
        r = arm.detect_root_package(tmp)
        if r != "myproj":
            ok = fail(f"src-layout: expected myproj, got {r}")
        else:
            print(f"  ok: src-layout -> {r}")
    finally:
        shutil.rmtree(tmp)

    # (c) flat-layout
    tmp = tempfile.mkdtemp(prefix="acf_drpp_c_")
    try:
        pkg = os.path.join(tmp, "flatpkg")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").write("")
        r = arm.detect_root_package(tmp)
        if r != "flatpkg":
            ok = fail(f"flat-layout: expected flatpkg, got {r}")
        else:
            print(f"  ok: flat-layout -> {r}")
    finally:
        shutil.rmtree(tmp)

    # (d) detect-failure -> __REPLACE_ME__
    tmp = tempfile.mkdtemp(prefix="acf_drpp_d_")
    try:
        r = arm.detect_root_package(tmp)
        if r != "__REPLACE_ME__":
            ok = fail(f"empty: expected __REPLACE_ME__, got {r}")
        else:
            print(f"  ok: detect-failure -> {r}")
    finally:
        shutil.rmtree(tmp)

    print("\n_count_active_contracts:")

    # neutral template (.importlinter.ini with commented layers) -> 0
    tmpl = os.path.join(TEMPLATES, ".importlinter.ini")
    n = gate._count_active_contracts(tmpl, ROOT)
    if n != 0:
        ok = fail(f"neutral template: expected 0 active, got {n}")
    else:
        print(f"  ok: neutral template -> {n} active")

    # active config (uncommented contract) -> 1+
    tmp_f = tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False)
    tmp_f.write(
        "[importlinter]\nroot_package = x\n\n"
        "[importlinter:contract:layers]\nname = L\ntype = layers\nlayers = x.y\n"
    )
    tmp_f.close()
    n2 = gate._count_active_contracts(tmp_f.name, ROOT)
    if n2 < 1:
        ok = fail(f"active config: expected >=1, got {n2}")
    else:
        print(f"  ok: active config -> {n2} active")
    os.unlink(tmp_f.name)

    # comment-skipping: a config with ONLY commented [importlinter:contract:] -> 0
    tmp_f2 = tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False)
    tmp_f2.write(
        "[importlinter]\nroot_package = x\n\n"
        "# [importlinter:contract:layers]\n# name = L\n"
    )
    tmp_f2.close()
    n3 = gate._count_active_contracts(tmp_f2.name, ROOT)
    if n3 != 0:
        ok = fail(f"commented-only: expected 0, got {n3}")
    else:
        print(f"  ok: commented-only -> {n3} active")
    os.unlink(tmp_f2.name)

    print("\n_same_content_normalized:")

    # armed + substituted -> still 'matches template' (token normalized)
    tmp = tempfile.mkdtemp(prefix="acf_scn_")
    try:
        dst = os.path.join(tmp, ".importlinter.ini")
        shutil.copy2(tmpl, dst)
        # simulate ACF-I1 substitution
        with open(dst) as fh:
            c = fh.read().replace(
                "root_package = __REPLACE_ME__", "root_package = detected_pkg", 1
            )
        with open(dst, "w") as fh:
            fh.write(c)
        norm = arm._same_content_normalized(dst, tmpl, ".importlinter.ini")
        if not norm:
            ok = fail("substituted config should match template (normalized)")
        else:
            print("  ok: substituted config -> matches template (removable)")
        # a config with a REAL edit (uncommented layer) -> NOT normalized match
        with open(dst) as fh:
            c2 = fh.read()
        c2 = c2.replace(
            "# [importlinter:contract:layers]",
            "[importlinter:contract:layers]",
            1,
        )
        with open(dst, "w") as fh:
            fh.write(c2)
        norm2 = arm._same_content_normalized(dst, tmpl, ".importlinter.ini")
        if norm2:
            ok = fail("user-edited config should NOT match template")
        else:
            print("  ok: user-edited config -> customized (kept + warned)")
    finally:
        shutil.rmtree(tmp)

    print("\nPASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
