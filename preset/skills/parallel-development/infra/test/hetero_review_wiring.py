#!/usr/bin/env python3
"""hetero_review.py ↔ loop_state wiring — the wrapper drives loop_state truthfully
around the different-family subprocess (ADR #39, ADR #40 (g)), and the P1-1 schema delta
(`adversarial-stalemate`) round-trips through run-record.schema.json.

OFFLINE + DETERMINISTIC (rule 4 — no real model call in the gate): exercises the
wrapper's --dry-run path (canned violation-log-shaped return) + drives loop_state
directly for the verdict-enum cases. The live `claude -p` substrate is exercised by
the dogfood runs (§6 Phase-3 gate), NOT here.

Cases:
  1. --dry-run → loop_state driven truthfully: run-record converged, steps.inner>=1,
     outer.iterations>=1, outer_verdicts non-empty (ADR #39/#16 invariant).
  2. --dry-run → the wrapper returns a typed JSON object (verdict/findings_count/
     findings/run_record) — the reconciliation shape P1-5 consumes.
  3. adversarial-stalemate round-trips: loop_state accepts record-outer
     --verdict adversarial-stalemate AND the emitted run-record validates against
     run-record.schema.json (P1-1 schema delta).
  4. --embedded → skips init/mark-converged/run-record (the orchestrator owns those
     when the wrapper runs as the convergence-loop outer ring).

Run: python3 infra/test/hetero_review_wiring.py
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
SCHEMAS = os.path.normpath(os.path.join(HERE, "..", "schemas"))
HETERO = os.path.join(SCRIPTS, "hetero_review.py")
LOOP_STATE = os.path.join(SCRIPTS, "loop_state.py")
RUN_RECORD_SCHEMA = os.path.join(SCHEMAS, "run-record.schema.json")

sys.path.insert(0, SCRIPTS)
import hetero_review as h  # noqa: E402  (unit-test the profile helpers directly)

def _resolved_default_profile_hint():
    import os as _os
    return _os.environ.get("HETERO_PROFILE", "")

try:
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:
    HAVE_JSONSCHEMA = False


def _run(py_script, args, cwd, env):
    return subprocess.run(
        [sys.executable, py_script] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _env(td):
    # Offline suite: arm a valid (claude-code substrate) profile so the fail-fast
    # default only fires where a test asks for it explicitly.
    return {**os.environ, "SOLIDFORGE_PROJECT_DIR": td, "HETERO_PROFILE": "qwen"}


def _runs(td, task):
    return sorted(
        glob.glob(os.path.join(td, ".solidforge", "loop", "runs", f"{task}-*.json"))
    )


def check_wrapper_drives_truthful_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het1",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"wrapper failed: {r.stderr or r.stdout}"
        recs = _runs(td, "het1")
        assert recs, f"wrapper must emit runs/het1-*.json: {td}"
        rec = json.load(open(recs[-1]))
        assert rec.get("converged") is True, f"not converged: {rec.get('converged')}"
        assert rec.get("dod_satisfied") is True, (
            f"dod_satisfied false (ADR #16 outer ring invariant): {rec.get('dod_satisfied')}"
        )
        assert rec["steps"]["inner"] >= 1, (
            f"steps.inner<1 — bookkeeping dishonest (ADR #39): {rec['steps']}"
        )
        # The run-record expresses the outer ring via outer_verdicts[] (one entry per
        # record-outer call); len >= 1 means the wrapper drove record-outer (ADR #16).
        assert len(rec["outer_verdicts"]) >= 1, (
            f"outer_verdicts empty — record-outer not driven: {rec.get('outer_verdicts')}"
        )
    print(
        "  --dry-run -> truthful run-record (converged, steps.inner>=1, outer>=1): PASS"
    )


def check_wrapper_returns_typed_findings():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het2",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        out = json.loads(r.stdout)
        for key in ("verdict", "findings_count", "findings", "run_record"):
            assert key in out, f"typed return missing {key}: {out}"
        assert out["verdict"] in ("pass", "rewrite", "adversarial-stalemate"), (
            f"bad verdict: {out['verdict']}"
        )
        assert isinstance(out["findings"], list), "findings not a list"
    print("  --dry-run -> typed JSON return (reconciliation shape): PASS")


def check_adversarial_stalemate_round_trips():
    """P1-1 schema delta: record-outer accepts adversarial-stalemate AND the emitted
    run-record validates against run-record.schema.json."""
    with tempfile.TemporaryDirectory() as td:
        env = _env(td)
        assert _run(LOOP_STATE, ["init", "--task-id", "het3"], td, env).returncode == 0
        ro = _run(
            LOOP_STATE,
            [
                "record-outer",
                "--verdict",
                "adversarial-stalemate",
                "--findings",
                "2",
                "--notes",
                "cap=2 hit without convergence; escalate to human",
            ],
            td,
            env,
        )
        assert ro.returncode == 0, (
            f"record-outer --verdict adversarial-stalemate rejected (P1-1 delta): {ro.stderr}"
        )
        assert _run(LOOP_STATE, ["mark-converged"], td, env).returncode == 0
        assert _run(LOOP_STATE, ["run-record"], td, env).returncode == 0
        recs = _runs(td, "het3")
        assert recs, "run-record not emitted"
        rec = json.load(open(recs[-1]))
        verdicts = [v["verdict"] for v in rec["outer_verdicts"]]
        assert "adversarial-stalemate" in verdicts, (
            f"adversarial-stalemate not in run-record outer_verdicts: {verdicts}"
        )
        if HAVE_JSONSCHEMA:
            schema = json.load(open(RUN_RECORD_SCHEMA))
            jsonschema.validate(rec, schema)  # type: ignore[reportPossiblyUnboundVariable]  # raises on invalid
            print("  adversarial-stalemate round-trips + jsonschema VALID: PASS")
        else:
            # Degrade honestly (rule 3): structural check only — jsonschema absent.
            assert isinstance(rec.get("outer_verdicts"), list), (
                "outer_verdicts not a list"
            )
            print(
                "  adversarial-stalemate round-trips (structural; jsonschema absent): PASS"
            )


def check_embedded_skips_terminal_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het4",
                "--dry-run",
                "--embedded",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"embedded wrapper failed: {r.stderr or r.stdout}"
        assert not _runs(td, "het4"), (
            "--embedded must NOT emit runs/ (orchestrator owns mark-converged/run-record)"
        )
    print("  --embedded -> skips init/mark-converged/run-record: PASS")


def check_malformation_gate_fail_survives_init():
    """Phase-1 dogfood blocker fix: the gate-fail fingerprint must survive
    drive_lifecycle's init (recorded POST-init, since loop_state `init` unconditionally
    re-defaults state). The fingerprint appears in the run-record's top_fingerprints."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het5",
                "--dry-run",
                "--dry-run-malform",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"malform wrapper failed: {r.stderr or r.stdout}"
        recs = _runs(td, "het5")
        assert recs, "malform run must emit runs/het5-*.json"
        rec = json.load(open(recs[-1]))
        fps = [f.get("fingerprint") for f in rec.get("top_fingerprints", [])]
        assert "dry-run-malform" in fps, (
            f"gate-fail fingerprint wiped by init (dogfood blocker regression): {fps}"
        )
        out = json.loads(r.stdout)
        assert out["malformation"] == "dry-run-malform", (
            f"malformation not surfaced in output: {out.get('malformation')}"
        )
    print("  --dry-run-malform -> gate-fail survives init + surfaces in output: PASS")


def check_budget_exhaustion_degrades():
    """ADR #41: a recoverable CC substrate error (budget cap) DEGRADES, not rewrites.

    The different-family leg contributes 0 findings + a coverage note + a persisted
    hetero-degraded-<subtype> fingerprint (so the thrashing breaker escalates persistent
    degradation); verdict stays pass (same-family primary stands — ADR #40 additive).
    Canned via --dry-run-budget (rule 4 — no real model call)."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het6",
                "--dry-run",
                "--dry-run-budget",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"budget wrapper failed: {r.stderr or r.stdout}"
        out = json.loads(r.stdout)
        # Degrade, not rewrite: a recoverable cap must not force a rewrite of the work.
        assert out["degraded"] is True, f"degraded flag not set: {out}"
        assert out["verdict"] == "pass", (
            f"budget must DEGRADE (verdict=pass), not rewrite: {out['verdict']}"
        )
        assert out["malformation"] == "", (
            f"degrade is not a malformation (return parsed cleanly): {out.get('malformation')}"
        )
        assert any("error_max_budget_usd" in c for c in out["coverage"]), (
            f"coverage missing the degrade note: {out['coverage']}"
        )
        assert out["degraded_providers"], "degraded_providers empty"
        assert out["degraded_providers"][0]["subtype"] == "error_max_budget_usd", out
        # Persistence-layer honesty (rule 3 / ADR #39): the degrade fingerprint must survive
        # to the run-record so persistent degradation escalates rather than masquerading as
        # clean convergence (converged:true, verdict:pass, findings:0).
        recs = _runs(td, "het6")
        assert recs, "budget run must emit runs/het6-*.json"
        rec = json.load(open(recs[-1]))
        fps = [f.get("fingerprint") for f in rec.get("top_fingerprints", [])]
        assert "hetero-degraded-error_max_budget_usd" in fps, (
            f"degrade fingerprint not persisted (ADR #41 honesty regression): {fps}"
        )
        # --dry-run-budget ALONE implies --dry-run (else subprocess.run(None) TypeError).
        r2 = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--dry-run-budget",
                "--embedded",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r2.returncode == 0, (
            f"--dry-run-budget alone must imply --dry-run: {r2.stderr or r2.stdout}"
        )
        out2 = json.loads(r2.stdout)
        assert out2["degraded"] is True and out2["verdict"] == "pass", out2
    # _parse_cc_substrate_error handles BOTH output modes (json + stream-json/JSONL; ADR #41).
    sub_j, _ = h._parse_cc_substrate_error(
        '{"type":"result","subtype":"error_max_budget_usd","is_error":true,'
        '"errors":["x"]}'
    )
    assert sub_j == "error_max_budget_usd", sub_j
    sub_l, _ = h._parse_cc_substrate_error(
        '{"type":"hook"}\n'
        '{"type":"result","subtype":"error_max_turns","is_error":true,"errors":[]}'
    )
    assert sub_l == "error_max_turns", sub_l
    assert h._parse_cc_substrate_error("not json") == (None, [])
    print(
        "  --dry-run-budget -> degrade (pass + flag + persisted fingerprint + modes): PASS"
    )


def check_provider_template_expansion():
    """Convention token-var derivation + materialization. The token var is DERIVED
    from the profile filename (<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN), so a
    user-authored profiles/foo.json needs NO _token_env / ${...} — zero ceremony."""
    # convention derivation (no _token_env in the template)
    assert h._resolve_token_var("qwen", {}) == "QWEN_ANTHROPIC_AUTH_TOKEN"
    assert (
        h._resolve_token_var("openai-compat", {})
        == "OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN"
    )
    # optional override via _token_env
    assert h._resolve_token_var("x", {"_token_env": "CUSTOM_VAR"}) == "CUSTOM_VAR"
    print("  _resolve_token_var (convention + _token_env override): PASS")

    # recursive ${VAR} expansion still works for NON-token fields
    os.environ["HETERO_UNIT"] = "u-val"
    expanded = h._expand_env_values(
        {"env": {"X": "${HETERO_UNIT}"}, "nested": {"y": "${HETERO_UNIT}"}}
    )
    assert expanded["env"]["X"] == "u-val" and expanded["nested"]["y"] == "u-val"
    del os.environ["HETERO_UNIT"]
    print("  _expand_env_values (recursive, non-token ${VAR}): PASS")

    # materialize qwen with the CONVENTION var → token injected, routing preserved
    os.environ["QWEN_ANTHROPIC_AUTH_TOKEN"] = "sk-conv-unit"
    tmp = h._materialize_profile("qwen")
    try:
        d = json.load(open(tmp))
        assert d["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-conv-unit", d["env"]
        assert d["env"]["ANTHROPIC_BASE_URL"] == "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic"
    finally:
        os.unlink(tmp)
    del os.environ["QWEN_ANTHROPIC_AUTH_TOKEN"]
    print("  _materialize_profile (convention var injected + routing preserved): PASS")

    # missing token -> fail fast (non-zero), naming the CONVENTION var
    r = _run(
        HETERO,
        [
            "--diff",
            "HEAD",
            "--blueprint",
            "t#b",
            "--task-id",
            "u",
            "--profile",
            "qwen",
            "--project-dir",
            tempfile.mkdtemp(),
        ],
        tempfile.mkdtemp(),
        {**os.environ, "QWEN_ANTHROPIC_AUTH_TOKEN": ""},
    )
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "QWEN_ANTHROPIC_AUTH_TOKEN" in out, (
        r.returncode,
        out,
    )
    print("  missing-token fail-fast (names the convention var): PASS")





def check_family_guards():
    """_family metadata is FUNCTIONAL: same-source refusal + dual-family honesty
    (paper §4.1). Unit-style against a temp profiles dir."""
    import tempfile as _t
    d = _t.mkdtemp(prefix="fam_")
    try:
        for n, fam in [("zai.json", "zhipu"), ("zai-coding-cn.json", "zhipu"),
                       ("deepseek-r.json", "deepseek"), ("nofam.json", None)]:
            obj = {"substrate": "dsh", "model": "m"}
            if fam:
                obj["_family"] = fam
            json.dump(obj, open(os.path.join(d, n), "w"))
        errs, notes = h._family_checks(["zai"], d)
        assert not errs and not notes, (errs, notes)
        errs, notes = h._family_checks(["deepseek-r"], d)
        assert errs and any("SAME-SOURCE" in e for e in errs) and not notes, (errs, notes)
        errs, notes = h._family_checks(["zai", "zai-coding-cn"], d)
        assert not errs and any("no blind-spot diversity" in n for n in notes), (errs, notes)
        errs, notes = h._family_checks(["nofam"], d)
        assert not errs and any("guard inactive" in n for n in notes), (errs, notes)
    finally:
        import shutil as _sh3
        _sh3.rmtree(d, ignore_errors=True)
    print("  family guards (same-source refuse / dual-family note / undeclared note): PASS")

def check_dsh_substrate_home_construction():
    """DSH-native substrate: _prepare_dsh_home builds a throwaway DSH_HOME whose
    settings.yaml pins agent-default-model to the profile's route + model, and the
    credential env resolves through the three-tier chain (setdefault). No foreign
    harness in the argv."""
    tmpl = {
        "substrate": "dsh",
        # NOTE: no "provider" field — it DERIVES from the profile filename (the
        # filename IS the route; single namespace, no drift).
        "model": "het-model",
        "reasoning_effort": "high",
        "_credential_env": "HETERO_UNIT_KEY",
    }
    os.environ["HETERO_UNIT_KEY"] = "sk-hetero"
    try:
        home, env_block = h._prepare_dsh_home("het-route", tmpl)
        assert os.path.isdir(home)
        try:
            settings = json.load(open(os.path.join(home, "settings.yaml")))
            assert settings["agent-default-model"]["provider"] == "het-route"
            assert settings["agent-default-model"]["model"] == "het-model"
            assert settings["agent-default-model"]["reasoningEffort"] == "high"
            assert settings["llm-pi-ai"]["providers"]["het-route"] == {"apiKeyEnv": "HETERO_UNIT_KEY"}  # catalog route: apiKeyEnv only
            assert env_block["HETERO_UNIT_KEY"] == "sk-hetero"
        finally:
            import shutil as _shutil
            _shutil.rmtree(home, ignore_errors=True)
    finally:
        del os.environ["HETERO_UNIT_KEY"]
    # DERIVATION default: a profile WITHOUT _credential_env derives
    # <UPPERCASE(route)>_API_KEY — pi-ai's own env convention.
    os.environ["HET_ROUTE_API_KEY"] = "sk-derived"
    try:
        home2, env2 = h._prepare_dsh_home("het-route", {k: v for k, v in tmpl.items() if k != "_credential_env"})
        assert os.path.isdir(home2)
        try:
            settings2 = json.load(open(os.path.join(home2, "settings.yaml")))
            assert settings2["llm-pi-ai"]["providers"]["het-route"]["apiKeyEnv"] == "HET_ROUTE_API_KEY"
            assert env2["HET_ROUTE_API_KEY"] == "sk-derived"
        finally:
            import shutil as _sh2
            _sh2.rmtree(home2, ignore_errors=True)
    finally:
        del os.environ["HET_ROUTE_API_KEY"]
    print("  _prepare_dsh_home (route-derived credential var): PASS")

    # missing credential -> fail-fast naming the var (mirrors the claude path);
    # the throwaway home is cleaned up on the failure branch (no temp litter)
    import contextlib
    import io as _io
    import glob as _glob
    before = set(_glob.glob(os.path.join(tempfile.gettempdir(), "sf-dsh-hetero-*")))
    with contextlib.redirect_stderr(_io.StringIO()):
        try:
            h._prepare_dsh_home("het-route", {**tmpl, "_credential_env": "UNSET_HETERO_KEY"})
        except SystemExit:
            pass
    after = set(_glob.glob(os.path.join(tempfile.gettempdir(), "sf-dsh-hetero-*")))
    assert after == before, "missing-token branch must clean up its throwaway home"
    print("  _prepare_dsh_home (throwaway DSH_HOME + credential env + fail-fast cleanup): PASS")

    # default is FAIL-FAST: no provider configured = an arming prompt, never a
    # silent fallback (the placeholder pi-ai.json default was removed).
    assert _resolved_default_profile_hint() == ""
    r = _run(
        HETERO,
        ["--diff", "HEAD", "--blueprint", "t#b", "--task-id", "u", "--project-dir", tempfile.mkdtemp()],
        tempfile.mkdtemp(),
        {**os.environ, "HETERO_PROFILE": "", "SOLIDFORGE_PROJECT_DIR": tempfile.mkdtemp()},
    )
    assert r.returncode == 2 and "no heterogeneous provider configured" in r.stderr, (r.returncode, r.stderr)
    print("  default fail-fast arming prompt (no silent fallback): PASS")

def check_dual_provider_dry_run():
    """Multi-different-family: --profile a,b runs each backend, tags findings with `provider`,
    returns the provider list. Offline via --dry-run (no real model call)."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "v",
                "--profile",
                "claude,qwen",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, r.stderr or r.stdout
        out = json.loads(r.stdout)
        assert out["providers"] == ["claude", "qwen"], out
    print("  dual-different-family dry-run (providers listed): PASS")


def check_unknown_provider_fail_fast():
    """An unknown provider NAME (no template) fails fast with a clear error."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "w",
                "--profile",
                "nonexistent",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "unknown provider profile" in out, out
    print("  unknown-provider fail-fast: PASS")


def main():
    print("hetero_review.py ↔ loop_state wiring (ADR #40 Phase 1):")
    failures = []
    for fn in (
        check_wrapper_drives_truthful_lifecycle,
        check_wrapper_returns_typed_findings,
        check_adversarial_stalemate_round_trips,
        check_embedded_skips_terminal_lifecycle,
        check_malformation_gate_fail_survives_init,
        check_budget_exhaustion_degrades,
        check_provider_template_expansion,
        check_dsh_substrate_home_construction,
        check_family_guards,
        check_dual_provider_dry_run,
        check_unknown_provider_fail_fast,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nwiring: hetero_review drives loop_state truthfully + adversarial-stalemate "
        "round-trips the schema (P1-1/P1-4/P1-5/P1-7)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
