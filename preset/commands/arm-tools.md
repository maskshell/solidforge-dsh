---
description: Arm the current project for Solid Forge — provision arch-configs, optional gate dev-deps, constitution, templates, gitignore; report gate status + toolchain advisory. Layer 2 (explicit per-project opt-in; the preset does not mutate host-project build files, so this is a command, not mounting).
argument-hint: "[--with-tools [--lang python|web|rust|swift|java]] [--scaffold-configs [vale,semgrep,spectral]] [--revert [--apply]]"
---

# arm-tools — arm a project for Solid Forge

You are arming the project at `$SOLIDFORGE_PROJECT_DIR` (or the current working directory). `$SOLIDFORGE_PRESET_ROOT` is a documentation alias for the installed preset directory — concretely `$DSH_HOME/.agent-presets/solidforge/`; if the variable is not exported, substitute the concrete path in the commands below (the gate scripts never depend on it — they resolve the preset root by walking up to `agent.cordis.yml`). for the Solid Forge convergence loop. This is **Layer 2** — the explicit, per-project provisioning step. Layer 1 (mounting the `solidforge` preset) already activated the skills + role agents + gate listeners; this command provisions the **project-side** files the gates and loop need.

## Step 1 — run the arming script

Run exactly one command. If the user passed `--with-tools` (or asked to install/add the gate tools), append `--with-tools`; otherwise omit it.

```bash
python3 "${SOLIDFORGE_PRESET_ROOT}/skills/parallel-development/infra/install/arm.py" --with-tools
```

(Without `--with-tools`: `python3 "${SOLIDFORGE_PRESET_ROOT}/skills/parallel-development/infra/install/arm.py"`.)

For a polyglot repo where the user wants only ONE language's gate tools, append `--lang <python|web|rust|swift|java>` (only valid with `--with-tools`; default = all detected ecosystems). Example — arm only Python: `python3 "${SOLIDFORGE_PRESET_ROOT}/skills/parallel-development/infra/install/arm.py" --with-tools --lang python`

If the user wants external-tool configs scaffolded (Vale prose-lint / Semgrep SAST / Spectral OpenAPI), append `--scaffold-configs [vale,semgrep,spectral]` (bare flag = all three; comma-list = subset; independent of `--with-tools`). These are NOT language-bound — opt in explicitly. When `vale` is scaffolded and `vale` is on `$PATH`, arming also runs `vale sync` to fetch the style packages (the Vale gate no-ops without them).

The script provisions, for each detected ecosystem at the project root OR nested (bounded walk, depth ≤ 4):

- arch-configs copied to the project root (`.importlinter.ini` Python, `.dependency-cruiser.cjs` Web, `.swiftlint.yml` Swift, `clippy.toml` Rust, `checkstyle.xml` Java) — only for detected languages; never clobbers an existing edited file.
- `--scaffold-configs` only: external-tool config templates copied to the project root (`.vale.ini` / `.semgrep.yml` / `.spectral.yaml`) — sensible STARTING POINTS; never clobbers an existing file. (Vale: run `vale sync` after, or let arming do it.)
- `--with-tools` only: version-matched gate tools added to the project's OWN dev deps (uv/poetry/pipenv/pip/npm/pnpm/yarn) — reversible, idempotent. System-only tools (swiftlint/clippy/cargo-audit/gitleaks/...) are printed as install commands, not mutated.
- L1 Constitution + Gate-Toolchain sections appended to the project `AGENTS.md` (once; idempotent).
- intent-blueprint template + cold-start-patterns copied to `docs/intent-blueprints/_templates/`.
- `.gitignore` entries added for the convergence-loop runtime state (`.solidforge/loop/loop-state.json`, `.solidforge/loop/runs/`).

## Step 2 — read the gate-status report the script prints

The script prints a toolchain/gate status block (present vs absent per gate tool). Summarize for the user which gates are armed and which degrade (a gate that is absent degrades gracefully — it never reports a silent green).

## Step 3 — code-intelligence advisory (do NOT install yourself)

Solid Forge does NOT bundle an LSP stack and does NOT install language servers. For each detected language, recommend the language-server **binary** install command (the binary must be on `$PATH`):

- Python: `npm install -g pyright` (or `pipx install pyright`).
- Rust: `rustup component add rust-analyzer`.
- Swift: ships with Xcode (`xcrun sourcekit-lsp`).
- Java: download Eclipse JDT.LS or `brew install jdtls`.
- TypeScript/Web: `npm install -g typescript typescript-language-server`.

State clearly that LSP wiring is optional — opt in per language this project uses.

## Step 4 — report

Tell the user concisely: what was armed (configs, deps if `--with-tools`, constitution, templates, gitignore, and the `.env.solidforge.example` secrets placeholder), which gates are still absent, and the code-intelligence recommendation(s) for this project's languages. Note that the Solid Forge gate listeners are already active when the loop-gates plugin is running (Layer 1) and that `arm.py --revert` (dry-run; add `--apply` to execute) removes only the template-matching provisioned files, preserving any user edits.

Describe each armed artifact in the report by what the tooling itself says about it. The `arm.py` print line names the artifact and the action; if a provisioned template file exists, read its opening comment (the first comment block at the top of the file) for its purpose; otherwise (no template was provisioned, or the header states no purpose) report the artifact by the `arm.py` print line alone — do not guess. (For the secrets placeholder, the `arm.py` line embeds the phrase `different-family secrets placeholder`, and the template header identifies the same artifact as the different-family (different-family) adversarial-review secrets file; the two agree on identity, not wording.) Do not relabel an artifact or substitute a concept borrowed from another file in the project; an artifact's identity comes from the tooling, not from a neighboring file.

## Step 5 — optional suggested cross-skill routing snippet (do NOT write it yourself)

Read `${SOLIDFORGE_PRESET_ROOT}/skills/parallel-development/references/host-routing.md` and print its contents verbatim. Frame it as an OPTIONAL suggested addition to the project's `AGENTS.md`: bc / pd / csr self-route via their own Scope Guards regardless, and this snippet only surfaces the csr explicit-invocation gap (csr is explicit-invocation only in Phase A; neither bc nor pd auto-routes to it). arm-tools does NOT write this snippet — unlike the L1 Constitution (which `arm.py` appends), this is print-only and opt-in; the user copies it into `AGENTS.md` only if they want the convention.
