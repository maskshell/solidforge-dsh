# Commit Stratification — Format-Drift Isolation Protocol

How the fast-gate's FORMAT Blocker isolates its diff churn so the logic diff stays reviewable in MR/PR. Implements Option C of `docs/fast-gate-format-advisory-design.md` (csr-converged; ADR in `references/design-decisions.md`).

## The problem this solves

When a change touches a legacy-unformatted file, reformatting rewrites the whole file, so a one-line logical change becomes a large whitespace diff. A reviewer cannot separate real change from format churn. Stratification isolates the churn: the pure-format change lands as its own `style:` commit, and the logic change lands cleanly on top.

## Mechanism

Two axes, different determinism:

- **Detection — deterministic.** The fast-gate (`infra/hooks/fast_gate.py`, tools/post-execute) fires after every edit. If the just-edited file still differs from formatter output (`ruff format --check` / `google-java-format --dry-run --set-exit-if-changed` / `gofmt -l` / `rustfmt --check` non-empty), the gate blocks with stratification guidance. Lint failures (`ruff check`, `eslint`, `swift-format lint`) keep the fix-in-ring guidance — they are code fixes, not whitespace rewrites.
- **Isolation — heuristic (model/orchestrator-executed).** The stratify step is NOT a deterministic gate (workspace rule 4); the fast-gate can detect and nudge, it cannot commit. Never claim stratification as enforced.

## C-pre (canonical): format-commit BEFORE the logic edit

Sequence: detect → format-commit → logic-edit.

1. Before editing a legacy-unformatted file, run the formatter on it.
2. Commit the pure-format result as a standalone `style:` commit.
3. Make the logic edit on top. Its diff is clean logic.

## C-post (fallback): split at the per-stage commit

Sequence: logic-edit → at the per-stage commit point, split.

After the Coder returns its diff, the orchestrator separates the accumulated diff into a `style:` commit (pure-format hunks) plus the logic commit. Requires hunk-separation — heuristic; use when C-pre was not applied in time.

## Commit authorization (per mechanism — NOT a rule-9 override)

Commits are governed by the COMMIT POLICY (`references/plan-driven-mode.md` §Commit policy; `loop_state.py` `DEFAULT_COMMIT_POLICY = "auto-per-stage"`), which already overrides workspace rule 9's "commit only when asked; do not auto-commit" for the skill's runs. The two mechanisms extend that authorization differently:

- **C-post** splits the one per-stage commit into two at the same point (`style:` + logic).
- **C-pre** adds a NEW mid-stage `style:` commit point BEFORE the logic edit lands — an additional extension of the `auto-per-stage` authorization, still not a rule-9 override.

Under `--commit manual` / `none`, stratification degrades to a manual protocol: whoever commits stratifies.

## Inline mode (ADR #39)

When the orchestrator itself made the blocked edit (inline mode — legitimate and default for sequential / tight-coupling / skill-self-maintenance work), the orchestrator executes C-pre mid-loop: format, `style:` commit, redo the edit. ADR #39 bookkeeping (`bump-iteration` / `gate-fail` / `snapshot`) is driven regardless — inline exempts WHERE the edit happens, not WHETHER the bookkeeping happens.

## Format scope

- **C-wholesale (default)**: format the touched file(s) wholesale into the `style:` commit. Large but skippable; no range machinery.
- **C-range (deferred)**: range-scope to the change lines only — `google-java-format --lines` / `--offset` / `google-java-format-diff.py` (patch-changed lines); Spotless `ratchetFrom 'origin/main'` (file-granular, JVM builds). Smaller `style:` commit at the cost of per-language range tooling. Wire only if C-wholesale proves insufficient.

## Out of scope

- Demoting format from Blocker (Option A — documented fallback, not implemented).
- A hook-helper advisory emit (Option B — precluded: tools/post-execute has no platform warn-level severity).
- The known fast-gate /tmp lint gap (dogfood gap #4) — open, orthogonal, not bundled here.
