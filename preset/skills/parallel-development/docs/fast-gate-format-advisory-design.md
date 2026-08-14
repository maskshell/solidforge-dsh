# Fast-Gate: Split Lint (Blocker) from Format (Advisory) — Design

Status: pre-convergence. Pipeline target: `psv(gate) → csr → psv(full) → bc → pd`.
Authority: self-contained design proposal. Internal claims are verified against solidforge source (file:line cited). External claims are cited inline in §8 and are the admissible surface for psv.
Owner: outcome-axis — human (whether demoting format is the right call is a human judgment; this doc converges the PROCESS axis only).

## 1. Problem

The fast-gate (`skills/parallel-development/infra/hooks/fast_gate.py`) runs after every Edit/Write and treats **lint** and **format** as a single concern: any failure in either emits `decision:block` and short-circuits the inner ring. The user-observed consequence: when the model touches an unformatted legacy file, the formatter (google-java-format / gofmt / rustfmt / ruff format) rewrites the whole file, so a one-line logical change becomes a large whitespace/brace diff. That diff inflation degrades MR/PR review — a third-party reviewer cannot separate the real change from formatting churn, so their judgment is slower and noisier.

The thesis: **formatting is a low-value Blocker.** It is deterministic (so rule 4's "heuristic → advisory" clause does not literally compel demotion), but it is not a correctness violation, and its enforcement as a hard Blocker imposes a real cost (diff noise) on the human review surface that the inner ring is not supposed to optimize for.

## 2. Current state (internal — code-verified)

- The fast-gate lumps lint and format into one block exit. `check_python` runs `ruff check` (lint) AND `ruff format --check` (format); both funnel into the same `return False, (...)` → block path (`fast_gate.py:41-53`). Java runs `google-java-format --dry-run --set-exit-if-changed` only (`fast_gate.py:77-89`); Go `gofmt -l` (`fast_gate.py:92-105`); Rust `rustfmt --check` (`fast_gate.py:66-74`); Swift `swift-format lint` (`fast_gate.py:56-63`); Web `eslint` (`fast_gate.py:108-131`).
- All failures route to `dt.emit_block(reason)` (`fast_gate.py:199`).
- The hook emit surface is `emit_block` ONLY — `infra/hooks/lib/detect_toolchain.py:113` defines `emit_block`; there is no `emit_warning` / `emit_advisory` in the hook helper module. (Claims C2/C7 below rest on this — C2 the emit_block-only surface, C7 the PostToolUse block/allow binary.)
- The convergence-point gates DO carry a severity tier: `arch_contract_*` adapters call `emit(findings, coverage)` with per-finding `"severity": "blocker" | "warning"` (e.g. `arch_contract_api.py:189`, `arch_contract_deps.py:197`, `arch_contract_python.py:340`). So a `warning`-level emission path exists at the convergence layer, just not in the PostToolUse hook layer.
- install.md and convergent-loop.md describe the fast-gate as "per-file lint/format" with a single `decision:block` outcome — they do not distinguish lint severity from format severity.

## 3. Core claims (the coverage-verified set)

Enumerated for csr's coverage-verified prong and psv's claim set. Each claim is atomic.

Internal (verified against solidforge source — not fetchable external sources; psv marks these `internal/verifiable-by-source-read`, not in psv's admissible external surface):

- C1. The fast-gate emits `decision:block` on any lint OR format failure today (`fast_gate.py:199`). The FORMAT-emitting checks are Python `ruff format` (`fast_gate.py:50-52`), Java `google-java-format --dry-run` (`fast_gate.py:77-89`), Go `gofmt -l` (`fast_gate.py:92-105`), Rust `rustfmt --check` (`fast_gate.py:66-74`). Swift `swift-format lint` (`fast_gate.py:56-63`) and Web `eslint` and Python `ruff check` are LINTS, not format checks — so Swift/Web/Python keep a real lint Blocker regardless of the format decision. (Corrected per csr same-family finding B2: Swift was misclassified as format.)
- C2. The hook helper module exposes `emit_block` only; no warning-level emit path exists at the PostToolUse layer (`infra/hooks/lib/detect_toolchain.py:113`).
- C3. A `warning` severity tier exists at the convergence-point adapter layer (`emit(findings, coverage)` defined at `arch_contract_api.py:74`; per-finding `severity` examples at `:189`, `arch_contract_deps.py:197`, `arch_contract_python.py:340`).

External (fetchable primary sources — psv's admissible surface):

- C5. google-java-format is a whole-file formatter BY DEFAULT: `--dry-run --set-exit-if-changed` — as the fast-gate invokes it, with no range flag — reports whether the WHOLE file would be reformatted. The CLI DOES support limited-line/range formatting via `--lines` / `--offset`, and `google-java-format-diff.py` reformats the changed lines in a patch. So whole-file behavior is a property of HOW the fast-gate calls g-j-f, NOT a capability gap of g-j-f itself. (Source: google-java-format repo — §8. psv-gate NARROWED this claim: the original "no range mode" wording was too strong — the fetched README lists `--lines`/`--offset`/`google-java-format-diff.py`.)
- C6. Spotless (JVM formatter orchestrator) provides `ratchetFrom` to restrict formatting to files changed since a Git ref, bounding the diff to touched files. (Source: Spotless docs — §8.)
- C7. Claude Code PostToolUse hooks gate via a block/allow decision; there is no built-in warn-level severity that continues the turn while surfacing a non-blocking advisory. (Source: Claude Code hooks docs — §8.)

Interpretive (NOT admissible — psv tags `unverifiable`, escalates to human; csr may flag as outcome-axis):

- C8. "Format-on-touch of legacy files is the dominant cause of diff inflation in real MR/PR review." This is industry folk-knowledge; no single primary source adjudicates it. Stated as motivation only, not load-bearing for the decision (the decision rests on C1–C7).
- C4. "Demoting format to advisory aligns with rule 4's spirit (a Blocker must be a real violation; an unformatted-but-correct file is not a correctness violation) even though format is deterministic, not heuristic." INTERPRETIVE at its core — the rule-4 TEXT is internal-verifiable (CLAUDE.md rule 4: "heuristics are advisory, not Blocker"), but the "aligns with spirit" application to deterministic format is a value judgment. (Reclassified Internal → Interpretive per the psv full-M extraction; moral framing only — the decision also rests on the practical C1–C3/C5–C7 claims.)

## 4. Design decision

The fast-gate's two concerns (lint, format) are split. Lint stays a Blocker in every option; the options differ in how FORMAT is handled.

- **Lint stays a Blocker** in the fast-gate (all options). Rationale: lint (ruff check, eslint) catches real defects (undefined names, unused imports, syntax) that can hide bugs, and the fix is a code change, not a whitespace rewrite — so lint is NOT a diff-noise source and retains high value as an early, cheap, per-edit Blocker.

Two options for format, in recommended order (a third, hook-helper advisory, is rejected — see §5):

- **Option C — commit-stratified format (RECOMMENDED).** Format STAYS a Blocker (no loss of convergence hygiene); its diff noise is isolated by splitting the stage's commit into a pure-format `style:` commit + the logic commit, so the reviewer skips the format churn and reads a clean logic diff. Three axes:

  - **Detection (PostToolUse, deterministic).** The fast-gate (`fast_gate.py`, a PostToolUse hook per its docstring) fires AFTER an edit. If the just-edited file still differs from formatter output (g-j-f `--dry-run --set-exit-if-changed` / `gofmt -l` / `rustfmt --check` / `ruff format --check` non-empty), the file is legacy-unformatted and the edit did not fully format it. The gate records "format drift on a legacy file" and blocks with stratification guidance — do NOT inline-rewrite the whole file into the logic diff.
  - **Isolation (orchestrator-level, at the per-stage commit — heuristic).** Two cadences must not be conflated: the inner convergence loop uses SNAPSHOTS (`convergent-loop.md` — `snapshot.py` at the inner convergence point; "commit" appears 0× there), while COMMITS are governed by the separate COMMIT POLICY (`plan-driven-mode.md §Commit policy`; `loop_state.py` `DEFAULT_COMMIT_POLICY = "auto-per-stage"`). Under the default `auto-per-stage` policy, the orchestrator makes one feature-branch commit per converged stage — a behavior that itself OVERRIDES rule 9's operative clause "commit only when asked; do not auto-commit" (plan-driven-mode.md: "authorizes autonomous commits for the skill's runs"). The Coder is a dispatched subagent returning a Diff (not a commit). So the `style:` commit is made by the ORCHESTRATOR at the per-stage commit point, not by a per-edit hook, and is policy-dependent: it exists under `auto-per-stage`; under `manual`/`none` it degrades to a manual stratify-when-committing protocol. bc/pd selects one reconciliation mechanism:
    - **C-pre**: a PreToolUse step formats the legacy file and commits `style:` BEFORE the logic edit lands, so the Coder's diff is clean logic.
    - **C-post**: at the per-stage commit point, the orchestrator splits the accumulated diff into a `style:` commit (pure-format hunks) + the logic commit (presupposes the per-stage commit `auto-per-stage` already authorizes; it extends one commit → two).
  - **Format-scope sub-variants**: **C-wholesale (robust, default)** — format touched file(s) wholesale into the `style:` commit (large but skippable; no range machinery); **C-range (small-diff)** — range-scope via g-j-f `--lines`/`google-java-format-diff.py`, Spotless `ratchetFrom` (both psv-gate-verified C5/C6).
  Honesty (rule 3/4): only DETECTION is deterministic; the stratify/split (C-pre or C-post) is MODEL/ORCHESTRATOR-executed and heuristic — it must NOT be claimed as a deterministic hard gate. The `style:` commit is NOT a new rule-9 override (`auto-per-stage` already authorizes the per-stage commit), but the two mechanisms extend that authorization differently: **C-post** splits the one per-stage commit into two at the same point; **C-pre** adds a NEW mid-stage `style:` commit point BEFORE the logic edit lands — an additional extension of the `auto-per-stage` authorization, still not a rule-9 override. Both recorded in the ADR. (csr same-family: B3 closed round 1; F1 closed round 2; F2 closed → C-wholesale/C-range; bc outer-ring novel-3: the "same point" framing scoped per-mechanism.)

- **Option A — demote format to advisory at the convergence-point adapter** (minimal-change fallback). Format leaves the blocking fast-gate; its drift is reported once at convergence as `"severity": "warning"` via the existing `emit(findings, coverage)` path (C3). Weakness vs C: advisory is reported-not-enforced, so the final code may stay unformatted OR the model's fix re-introduces churn into the logic diff — it does not cleanly solve the MR-review problem. Kept as the fallback when C's commit-cadence change is judged too heavy.

The block/allow binary of PostToolUse (C7) is why format cannot be "demoted to advisory" IN PLACE inside the current fast-gate — a PostToolUse hook either blocks or passes; there is no warn middle ground. So A is necessarily a MOVE (format to the convergence adapter's warning channel), and C keeps the block but relocates the diff noise into a separate commit. (A hook-helper `emit_advisory` sibling — former "Option B" — is precluded by C7: a helper only emits JSON the platform interprets, and the platform has no warn interpretation; see §5.)

## 5. Alternatives considered (rejected, with rationale)

- **Status quo (format stays Blocker with NO commit stratification).** Rejected: this is exactly the current behavior whose diff-inflation degrades MR/PR review. Note Option C ALSO keeps format as a Blocker — status quo is rejected specifically because it lacks the commit stratification that isolates the diff noise.
- **Auto-format-on-touch (PreToolUse runs the formatter in-place instead of blocking).** Rejected: it removes the block/fix round-trip BUT reintroduces the same whole-file rewrite on legacy files into the working diff (C5) — arguably worse diff inflation, and it silently mutates files the model did not intend to touch. Does not solve the review problem. (Option C's prep format commit is the isolated-commit version of this idea, done right.)
- **Drop format entirely (no check at all).** Rejected: loses the convergence-loop hygiene value (format drift would accumulate unchecked).
- **Hook-helper advisory emit (former "Option B" — an `emit_advisory` sibling to `emit_block`).** Rejected: precluded by C7. A hook helper only emits JSON the platform interprets; the platform's PostToolUse decision vocabulary is block/allow with no warn-level severity, so there is nothing for a helper `emit_advisory` to surface that the platform would treat as a non-blocking note. A warn tier would require a platform-level change, out of scope for this skill.

## 6. Implementation surface (for bc → pd)

Option C is the recommended path; A is the fallback. Files a pd implementation must touch (rule 5 — update EVERY enumeration; rule 8 — preserve the loading chain):

- `infra/hooks/fast_gate.py` — (Option C) KEEP the format check as the deterministic DETECTOR, but change its remediation guidance: on a format failure it tells the model to stratify (run the formatter, commit as a standalone `style:` commit on the change range, then redo the logic edit), NOT to inline-rewrite the whole file into the logic diff. (Option A) remove the format half from each `check_*` and move it to convergence. Either way, lint stays a Blocker.
- a new **commit-stratification protocol doc/step** (Option C) — a short reference (under `references/`, linked from plan-driven-mode.md §Commit policy + fail-fast.md) prescribing the **C-pre** sequence (detect → format-commit → logic-edit) as canonical, with **C-post** (logic-edit → at the per-stage commit, split the accumulated diff into `style:` + logic) as the fallback reconciliation; states honestly that the stratify discipline is model-executed/gate-nudged (heuristic, rule 4) while the detect step is deterministic. C-range adds the per-language range tooling pointers (g-j-f `--lines`/`google-java-format-diff.py`, ratchetFrom).
- `infra/scripts/arch_contract_<lang>.py` (Option A only) — add a `warning`-severity format finding at convergence, reusing `emit(findings, coverage)`.
- `references/install.md` — fast-gate row: reframe "lint/format" as "lint (Blocker) + format (Blocker, commit-stratified under C / advisory under A)".
- `references/convergent-loop.md` — fast-gate description: lint blocks; format blocks but its diff is commit-isolated (C) / advisory (A).
- `references/extending.md` — the per-language formula + strength tables: record lint-Blocker + format-stratified as the new gate decision point.
- `references/maturity.md` — the maturity caveats describe the fast-gate's per-language coverage; record the split (Java/Go/Rust = format-only; Swift/Web/Python = lint) and the Option-A coverage gap for Java/Go/Rust.
- `references/design-decisions.md` — new ADR (Context / Decision / Why / Rejected) per rule 6, including the C-vs-A choice, the `auto-per-stage` `style:`+logic commit extension (NOT a rule-9 override — auto-per-stage already authorizes the per-stage commit), and the heuristic-enforcement caveat.

Coverage note (rule 3 — state honestly): Java/Go/Rust fast-gate checks are FORMAT-ONLY (no cheap per-file lint runs in the fast-gate for those languages today; their lint-grade checks — checkstyle/golangci-lint/clippy — live at the convergence gate). Swift (`swift-format lint`), Web (`eslint`), and Python (`ruff check`) DO have a lint in the fast-gate. Consequence: under Option C, Java/Go/Rust's fast-gate Blocker IS the format detector that triggers stratification, while Swift/Web/Python keep a lint Blocker regardless; under Option A (demote format), Java/Go/Rust would lose their ONLY fast-gate check — that gap must be emitted as a coverage note, not silently greened. (Corrected per csr same-family finding B2: Swift is lint, not format-only.)

## 7. Rule implications

- Rule 4 (heuristics advisory, Blocker = real violation): the decision's justification. Format is deterministic, so rule 4 does not literally force demotion, but the spirit (a stylistic non-violation should not Block) applies.
- Rule 6 (ADR for non-obvious decisions): advisory-vs-Blocker severity for format is exactly an ADR-grade decision; record Context / Decision / Why / Rejected (this doc §4–5 is the raw material).
- Rule 3 (never silently green): the Java/Go/Rust "no fast-gate check after format demotion" gap MUST be emitted as a coverage note, not hidden (Swift/Web/Python retain a lint Blocker).
- Rule 5 (update every enumeration): install.md, convergent-loop.md, extending.md, maturity caveats all describe "lint/format" as one — all need the split.

## 8. External references (psv admissible surface)

- C5 — google-java-format: `https://github.com/google/google-java-format` (README: whole-file by default; `--dry-run`/`--set-exit-if-changed` semantics; the CLI DOES support range/changed-line formatting via `--lines`/`--offset` and the `google-java-format-diff.py` patch script — matching the narrowed §3 wording; psv-gate NARROWED the original "no range mode" claim).
- C6 — Spotless `ratchetFrom`: `https://github.com/diffplug/spotless` main README (feature: "git ratcheting ... without 'format-everything' commits") + the `plugin-gradle` README `#ratchet` section (the literal keyword — `ratchetFrom 'origin/main'` with the comment "limit format enforcement to just the files changed by this feature branch" — grounded at the deeper hop after the psv full-M flagged the main README as insufficient alone).
- C7 — Claude Code PostToolUse hooks: `https://docs.claude.com/en/docs/claude-code/hooks` (PostToolUse decision semantics: block/allow; no warn severity tier).
- Tool classifications (uncited-but-load-bearing when first drafted; grounded by psv full-M fetches — E8/E9/E10 in the extraction): swift-format `lint` = linter / `format` = formatter (`https://github.com/apple/swift-format` README: "The `lint` subcommand checks one or more Swift source files for style violations"; "The `format` subcommand formats one or more Swift source files"); `ruff check` = lint (`https://docs.astral.sh/ruff/linter/`: "the primary entrypoint to the Ruff linter") and `ruff format` = formatter (same docs, Formatter half); ESLint = linter (`https://eslint.org/`: "Find and fix problems in your JavaScript code"; "statically analyzes your code"); `gofmt` = formatter (`https://pkg.go.dev/cmd/gofmt`: "Gofmt formats Go programs"); `rustfmt` = formatter (`https://github.com/rust-lang/rustfmt`: "A tool for formatting Rust code according to style guidelines"); google-java-format = formatter (grounded via the C5 fetch: "reformats Java source code to comply with Google Java Style"). These classify the fast-gate checks used by §3 C1 and §6 (Swift/Web/Python = lint; Java/Go/Rust = format-only).
