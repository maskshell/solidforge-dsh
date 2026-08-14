# Extending & Maintaining This Skill

On-demand reference (not auto-loaded). How to add a new programming language and how to keep the convergence-loop infrastructure from rotting. Platform- agnostic; concrete commands for each language live in its L4 file.

## The rule, codified (read this first)

Loading-chain breaks happen because a language's touch points are scattered across ~9 files and it is easy to forget one decision-point doc. The rule that prevents this is **data-driven and authoritative**, not prose:

- **`infra/test/platforms.json` is the single source of truth.** Each language declares its marker file, extension, L4 file, arch script/config, install token, and the markers each decision-point doc must contain. The file also declares the set of decision-point docs every language must route through.
- **`infra/test/disconnect_check.py` is the mandatory gate.** It reads the registry and verifies every structural link AND the loading chain (each language reachable at each decision point — no 断裂), with actionable per-file guidance. It never needs editing for a new language.

**To add a language:** add one entry to `platforms.json`, create the files the entry implies, route the language at each declared decision-point doc, then run the checker until green. **To update a language** (new tool, renamed file): re-run the checker — it re-verifies the full chain end to end. A change is not complete while the checker fails.

This converts "avoid loading-chain breaks" from a remembered checklist into a data file plus an automated gate: the registry says what must exist; the checker enforces it; a green run is the definition of done.

## The per-language formula

One new language = one repeated pattern. Do NOT ad-hoc each language.

> N languages = N × (L4 doc + classify entry + fast-gate check + arch-contract script + arch-config template + install branch + SKILL.md pointers)

## Touch points (every file that mentions a language)

The authoritative list is `infra/test/platforms.json` — the checker verifies every row below against it. The table is the human-readable mirror.

| # | Layer | File | What to add for `<lang>` |
| --- | --- | --- | --- |
| 0 | registry | `infra/test/platforms.json` | add a language entry (marker_file, extension, l4_file, arch_script, arch_config, install_token, desc_keywords, parallel_markers, role_markers). This single entry drives the checker — no other step is complete until the checker passes. |
| 1 | L4 (new) | `references/<lang>-patterns.md` | detection marker, toolchain commands, parallel-conflict scenarios, and an `## Architecture-Contract Gate (<lang>)` section naming `arch_contract_<lang>.py` |
| 2 | infra | `hooks/lib/detect_toolchain.py` | a `<LANG>_EXTS` set + a `classify()` branch returning `"<lang>"` |
| 3 | infra | `hooks/fast_gate.py` | `check_<lang>()` (cheap per-file check) AND an explicit `elif platform == "<lang>":` branch (see trap below); if the check is FORMAT-emitting, its `tool_name` MUST also be added to the format tuple in the guidance split (`"ruff format"`/`"google-java-format"`/`"gofmt"`/`"rustfmt"` today) so the commit-stratification guidance fires — lint-emitting checks get fix-in-ring ([commit-stratification.md](commit-stratification.md)) |
| 4 | infra | `scripts/arch_contract_<lang>.py` (new) | reuse the 越权日志 JSON schema (`infra/schemas/violation-log.schema.json`: `{gate, passed, coverage[], findings[{severity, rule, file, line, detail, suggestion}]}`) + Blocker exit; pick the language's deterministic arch tools. `infra/test/smoke_gates.py` validates the new gate's output against the schema. |
| 5 | infra | `templates/<lang-config>` + `arm.py` `ARCH_CONFIGS` | the language's arch-contract config template; append a `(filename, predicate)` tuple to `ARCH_CONFIGS`. The predicate reuses `detect_<lang>()` (same signal `prepare_tools` uses), so the config copies iff the project is detected as that language. |
| 6 | install | `install/arm.py` | `detect_<lang>()` (marker file) + a `prepare_tools` branch (dep-manager add OR system-toolchain instruction) |
| 7 | L1 | `SKILL.md` | description trigger keywords; detection-table row; fast-gate bullet; Reference Files entry; L4 row in the layer table |
| 8 | L3 | `references/arch-contracts.md` | one row in the per-platform tools table, pointing to `<lang>-patterns.md` for commands |
| 9 | L3 | `references/README.md` | index `<lang>-patterns.md` |

Optional / nice-to-have: add `<lang>` to the `domain:` enum in `golden-paths.md`, add a `cold-start-patterns/<lang>-*.md` exemplar, add an eval case in `evals/evals.json`.

> **External skills follow a DIFFERENT formula.** A black-box skill we invoke but do not own (e.g.
> Impeccable) is NOT a `platforms.json` language entry — it has no marker file, arch script, or
> fast-gate branch we control. The contract is artifact+invocation based: see
> [external-skills.md](external-skills.md) (one row per skill; DESIGN.md anchor + side-car freeze;
> leverage the skill's own detector/gate; map commands to the four seams; ADR if non-obvious; no
> checker edit).

Role mapping (`role-agent-mapping.md`) is language-agnostic: Rust/Go/Python all reuse `backend-developer`; Swift reuses `ios-developer` (impl) + `ios-tester` (XCUITest). A new backend language usually needs NO new agent — only a prompt-template addition if its idioms differ enough.

## Trap: the fast-gate dispatch is `if python / elif swift / else web`

`fast_gate.py` ends its platform switch with an implicit `else: check_web(...)`. Adding `check_<lang>()` is not enough — without an explicit `elif platform == "<lang>":`, files of the new language fall through to `check_web`, which no-ops (silently passes) because no eslint config matches. Every new language MUST add an explicit branch. (Consider later refactoring the switch to a dict dispatch so this trap disappears — see Plugin refactor below.)

## Architecture-contract strength varies by language (be honest)

The whole design rests on "deterministic inner ring". Not every language has equally strong deterministic arch tooling. State the truth in the L4 file's coverage notes; never let a weak language fake a green gate.

| Language | Layer/cycle contract tool | Concurrency baseline | Strength |
| --- | --- | --- | --- |
| Python | import-linter (layers/forbidden) + pylint cyclic | stdlib ast scan (sync-in-async) | strong |
| Web/TS | dependency-cruiser (no-circular + layers) | eslint no-restricted-syntax | strong |
| Swift | SwiftLint custom_rules | `swift build -strict-concurrency=complete` (Sendable) | strong |
| Rust | (none first-class) — clippy + cargo-modules | clippy (Send/Sync, unsafe) | thin — gate degrades honestly |
| Java | checkstyle ImportControl (declared package-layer rules) + jdeps (package cycles) | (none first-class — not statically enforced by this gate) | thin — gate degrades honestly |
| Go | `internal/` compiler-enforced boundary + golangci-lint depguard (v2 `rules:`) + compiler cycle rejection (`go build`) | `go test -race` (test-time; no static equivalent) | strong |

When a language has no first-class layering enforcer (Rust; and Java beyond what Checkstyle ImportControl declares), its arch-contract gate leans on what IS codable and explicitly reports the rest as uncovered in `coverage`. That is the correct behavior, not a bug.

## --with-tools provisioning model

`arm.py --with-tools` (invoked by `arm-tools --with-tools`) provisions gate tools per the ecosystem, never global:

- Dep-manager ecosystems (Python uv/poetry/pipenv/pip, Web npm/pnpm/yarn): add tools to the PROJECT's dev deps (version-matched, reversible). New dep-manager ecosystems add a `detect_*` + a branch that runs the add command.
- System-toolchain ecosystems (Swift, Rust): tools are not project deps. The branch only PRINTS the install command (`brew install …`, `rustup component add …`, `cargo install …`). Do not auto-run system installs.

## Disconnect verification (no 断裂 in the per-language loading chain)

Two distinct failure modes — do not confuse them:

- **Structural integrity** — a file or wiring exists and is cross-referenced somewhere. (Checks 1–12 below.)
- **Loading-chain 断裂** — the file exists and is reachable from SOME doc, but NOT from the specific decision-point doc the model reads at the point of need. Progressive disclosure means the model loads `description` → `SKILL.md` body → a `references/` doc ON DEMAND. A language's L4 content is useless if the model, at the decision point where it needs that content (parallel scheduling, arch gate, role assignment), is not routed to the L4.

Example of a loading-chain 断裂 this caught: `rust-patterns.md` documented `Cargo.lock`/`Cargo.toml` serialization, and the file was reachable from `arch-contracts.md` — but `parallel-patterns.md` (the doc the scheduler reads) had no Rust conflict section and no link to `rust-patterns.md`. So a model scheduling parallel Rust work could not load the serialization rule. Structural checks passed; the loading chain was broken at the scheduling tier.

Run both checks whenever a language is added or the infra is refactored.

### Structural (per language) — top of the skill down to the deterministic script

1. `SKILL.md` description mentions the language's trigger keywords (skill activates).
2. `SKILL.md` detection table has the language's marker file (e.g. `Cargo.toml`).
3. `SKILL.md` fast-gate bullet lists the language's cheap commands.
4. `SKILL.md` Reference Files lists `<lang>-patterns.md`.
5. `SKILL.md` layer table classifies `<lang>-patterns.md` as L4.
6. `arch-contracts.md` per-platform tools table has a row pointing to `<lang>-patterns.md`.
7. `<lang>-patterns.md` exists and has an `Architecture-Contract Gate (<lang>)` section naming `arch_contract_<lang>.py`.
8. `infra/scripts/arch_contract_<lang>.py` exists.
9. `arm.py` lists the language's arch config in `ARCH_CONFIGS` AND has a `detect_<lang>()` + `prepare_tools` branch. (Arch-contract scripts are NOT copied into projects — they run from the plugin root and operate on `$CLAUDE_PROJECT_DIR`.)
10. `detect_toolchain.classify()` maps the language's extensions to `"<lang>"`.
11. `fast_gate.py` has an EXPLICIT `elif platform == "<lang>":` branch (not the implicit else).
12. `templates/<lang-config>` exists and is referenced by `ARCH_CONFIGS`.
13. If the language's fast-gate check is FORMAT-emitting, its `tool_name` is in the guidance-split format tuple (`fast_gate.py`, next to the stratification comment) — a miss silently degrades format failures to fix-in-ring guidance (the behavioral case in `smoke_gates.py` pins only the ruff pair; the tuple is a shadow enumeration, guarded by this checklist item).

### Loading-chain (per language, per decision point)

For each language, at each tier where the model needs language-specific content, the decision-point doc must either inline it or link the L4:

1. `parallel-patterns.md` routes the language's parallel conflicts (marker present: `Cargo`/`pyproject`/`pbxproj`/`package.json`, or a link to the L4). This is the tier the scheduler reads.
2. `arch-contracts.md` routes the language's arch-gate commands (link to the L4 — covered by check 6).
3. `role-agent-mapping.md` routes the language's role (extension/keyword present: `.rs`/`.py`/`.swift`/`vue|react`).
4. `SKILL.md` fast-gate bullet routes to the L4 — every language (Python/Swift/Rust/Java/Go/Web) carries a `See <lang>-patterns.md` pointer. Web's L4 is `web-patterns.md`; `e2e-patterns.md` is a peer L4 for the Playwright/E2E sub-domain (reachable from SKILL.md), not Web's platform L4.

This checklist is automated and registry-driven: `python3 infra/test/disconnect_check.py` reads `infra/test/platforms.json` and verifies, for every declared language, the structural links (1–12) AND the loading-chain links (13–16), with actionable per-file guidance. Adding a language means editing the registry, not the checker.

It also runs a second tier of skill-level integrity checks (independent of any one language):

- Broken markdown links — every `[x](references/y.md)` target resolves to a file. (A per-language link can be present as text but point at a nonexistent file.)
- Orphaned reference docs — a `references/*.md` that no file reaches transitively from `SKILL.md`.
- Description trigger coverage — the `description` frontmatter actually contains each language's framework keywords (e.g. React/Vue/TypeScript for web), not just the marker file. Without this the skill may not ACTIVATE for that language even though every lower link is intact — the top of the chain is the real断裂 point.
- SKILL.md size guard — warn past 500 lines (progressive disclosure: detail belongs in `references/`, not the always-loaded body).
- Description length guard — the `description` frontmatter must stay ≤1024 chars (skill-creator's `quick_validate` rejects longer; it can be truncated and hurt triggering).

Run the checker after adding a language OR updating one OR refactoring the infra. A green run is the definition of done: the loading chain from the skill's top-level invocation down to each language's deterministic `arch_contract_<lang>.py` is unbroken at every decision point.

## Long-term maintenance

- External-tool version drift: the parsers (import-linter text output, SwiftLint output format, clippy JSON) can break when tools upgrade. Prefer `--output-type json` paths (dependency-cruiser, clippy already do). For tools without stable JSON (import-linter), treat the parser as a known fragile surface and re-verify after upgrades.
- Coverage audit contract: every gate emits a `coverage` array and must report what it skipped. Maintain this — a degraded check must never be silently green. This is the audit trail when a language's tooling is thin.
- Verified surfaces (status, so a maintainer knows what's proven vs. assumed): (a) hook LOGIC via stdin simulation + hook FIRING live via a headless `claude -p` in the project (see hooks-reference.md § Live verification) — both tools/pre-execute guard-deny and tools/post-execute fast-gate-block confirmed; (b) golden-path `golden_degrade.py` expiry logic verified; (c) Graphiti storage round-trip is the one async surface — `add_memory` accepts and queues `@Agent-Golden-Ref` episodes, but retrieval of a just-added episode is Graphiti's background-ingestion-latency (LLM entity extraction, can take minutes), so a tight add→search→degrade loop in a test may not close instantly. This is Graphiti's behavior, not the skill's; the skill logic is correct given indexing time.
- Test coverage: two layers. `infra/test/disconnect_check.py` verifies STRUCTURE + loading-chain; `infra/test/smoke_gates.py` verifies gate BEHAVIOR (each platform's arch gate, given a fixture with a known violation, surfaces a finding — python sync-in-async, rust clippy lint, swift force_unwrapping, web circular dep; skips platforms whose tools are absent). Run both after changing the infra. A known fragility: the web gate parses depcruise's `err` output (not JSON — depcruise's JSON `violations` omits some cycles), and depcruise cycle detection is most reliable from entry files; a bare directory arg can yield 0 modules (the gate warns when that happens).
- The "would this be noise on another platform?" test: when editing L1–L3, filter platform-specific content into L4. This keeps the docs from rotting into a platform soup.
- Plugin refactor threshold: today each language touches ~9 files via a repeated pattern. At 5+ languages, refactor `classify`/fast-gate-dispatch/arch into a per-language plugin dir + manifest so the implicit-else trap and the scattered touch points disappear. Not worth it below 5.

## Self-application (editing this skill with its own workflow)

A natural question: when evolving *this* skill, should it run its own convergence loop on itself? The honest answer is **partially — at the deterministic layer, which is mandatory — and not at the heavy L4 layer, which is ill-fitting.**

**The deterministic inner ring self-applies and MUST be green on every skill change.** These are self-validating gates that run on the skill's own source:

- `python3 infra/test/disconnect_check.py` — structure + loading-chain integrity.
- `python3 infra/test/smoke_gates.py` — arch-gate behavior (skips platforms whose tools are absent).
- `python3 infra/test/run_record.py` — run-record / L4-assessment pipeline.
- `python3 infra/test/lint_self.py` — **dogfood gate**: the skill lints its OWN infra with ruff (`ruff.toml`, E4/E7/E9/F). Skips if ruff is absent (ruff is a dev tool, not an infra runtime dependency — ADR #1). A green run is the skill passing its own Fast Gate at ruff's default rule set (E4/E7/E9/F — what `check_python` applies to a project with no ruff config; a project's own ruff config can only make the real Fast Gate stricter, so this is the lower bound).
- `python3 infra/test/drift_check.py` — rule-7 boilerplate drift across duplicated helpers (advisory warning; `docs/design-pattern-review-value.md` D3).
- `python3 infra/test/adapter_shape_check.py` — `*_adapter.py` violation-log shape contract (blocker).

A skill change is not done while any of these fail. This is the layer that genuinely bootstraps: the tests are plain stdlib Python, so they need no convergence loop to be trustworthy — the recursion bottoms out here.

**The hook-enforced outer shell does NOT self-apply.** Gates are opt-in + project-scoped: the Solid Forge plugin activates the hooks on enable (they run from the plugin root, operating on `$CLAUDE_PROJECT_DIR`), never onto the skill source. So editing the skill gets advisory gates, not hook-enforced ones. `lint_self.py` closes the lint part of that gap for the skill's own Python; the Fast Gate / blueprint_guard / counters hooks still require a target project.

**The heavy L4 mechanisms are ill-fitting and degenerate for self-edits.** The architecture-contract gate targets multi-module codebases (this repo is docs + a handful of scripts — there are no layers to enforce). ADR #38 (capacity/demand split): a self-edit run CAN produce `l4-evidenced` on **capacity** (the 3-degradation defense is demand-independent — a self-edit that converges with the defenses is capacity-evidenced); `not-a-probe` now means "non-probe + capacity-NOT-met" (narrowed semantics), not "non-probe by construction." So the skill CAN evidence its own capacity by running on itself. But it **cannot retire caveat 2** (probe-grade demand evidence) — self-edit is maximally familiar, demand-light, not a stress test. See [maturity.md](maturity.md) caveat 2.

**Recommended practice for self-edits.** Run the six deterministic gates above (required), and add one manual outer-ring pass: spawn an independent `code-reviewer` agent on the final diff with the triple-line check (semantic + intent + test-quality alignment against the doc being changed; test-quality is often vacuous for a doc-only self-edit but the line is still performed), address Blockers, then commit. The human stays the goal-anchor — so the full autonomous closed-loop is neither needed nor applicable here (ADR #38: a self-edit CAN be `l4-evidenced` on capacity, but the full closed-loop's value is stress-testing capacity under probe-grade demand, which self-edit lacks).

## Worked exemplar

Rust is the reference implementation of this pattern (the thinnest arch-contract gate, so it doubles as the "how to be honest about a weak language" example). See `references/rust-patterns.md`, `infra/scripts/arch_contract_rust.py`, `infra/templates/clippy.toml`, and the Rust rows in `SKILL.md` / `arch-contracts.md` / `arm.py`.
