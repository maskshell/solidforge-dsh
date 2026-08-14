# Intent Blueprint (Read-Only Anchor)

The Intent Blueprint is the frozen, structured replacement for the ambiguous natural-language prompt. It anchors the convergence loop so the Coder cannot drift from the original intent across many inner/outer iterations.

## Format

Template: `infra/templates/intent-blueprint.template.md` (installed to `docs/intent-blueprints/_templates/`). A blueprint file is `docs/intent-blueprints/<task>-v<n>.blueprint.md` and contains:

- Frontmatter: `blueprint_version`, `frozen_at`, `task`, `status` (`frozen` | `revising`).
- Core Use Cases (UC): functional points the system MUST implement. Never deleted to satisfy a compile/test constraint.
- Acceptance Criteria (AC): BDD Given/When/Then, each mapping to an executable test.
- Non-Functional Requirements (NFR): performance, external dependencies, capacity. A coverage floor bullet (e.g. `- NFR-2: line coverage >= 80%`) is read by the per-language coverage gate (P3) — the MAX such floor becomes the warning threshold; absent → measure-only.
- Optional: a `visual_ref` pointer to a frozen **DESIGN.md** (external-skill anchor; see [external-skills.md](external-skills.md)) — its design tokens / component inventory / a11y targets flow into the NFR + visual-AC. DESIGN.md is read-only-enforced by the same `blueprint_guard.py` (anchor kind `design`), but via a **side-car sentinel** (`.solidforge/loop/design.frozen`), not frontmatter `status` — its frontmatter is an external (Impeccable) token-export with no status.
- AC → test mapping (declared at RED phase; value is a test name/nodeid, not a file path; consumed by the test-name set gate — see "Acceptance-Criteria -> Test Mapping" below).

## Acceptance-Criteria -> Test Mapping

> **Section heading is regex-matched** — `parse_ac_test_map` matches `^##\s+Acceptance[\s-]+Criteria\s*(?:->|→)\s*Test\s+Mapping`. Use the **full** `## Acceptance-Criteria -> Test Mapping` form (copied verbatim from the template); the `AC → Test Mapping` shorthand does NOT match and the gate silently no-ops.

An optional but recommended field, declared at RED phase. For each AC, name the executable test(s) that verify it.

- Value = a test name or nodeid the per-language collector emits (e.g. `test_user_registration`, `tests/test_auth.py::test_user_registration`), NOT a bare file path. The test-name set gate (`arch_contract_tests.py` → `parse_ac_test_map`) verifies each mapped test **exists** in the collected set — a missing declared name is a Blocker. One bullet per test; multiple bullets may share an AC id (each name collected). Comma-listing multiple names on one line is NOT supported (read as one name).
- Absent mapping → the gate degrades to an **inactive coverage note** (no name comparison runs — count comparison was rejected: it misses name replacement). It is optional precisely so a minimal blueprint does not block on it; declare a mapping to enable the set-diff.
- Whether the mapped test **actually verifies** the AC is semantic residue — outer-ring (the reviewer's diff-to-blueprint check), not this gate's claim. Name-presence and execution coverage are same-source signals with a hard ceiling against test-quality spec gaming (ADR #38: same-source verification cannot defend spec gaming on test quality).

Template: `infra/templates/intent-blueprint.template.md`.

## Phase 0 (freeze)

At the start of a task, the Planner (`requirements-manager` / `Plan`) converts the request into a blueprint, sets `status: frozen`, and records its path in loop-state (`loop_state.py init --blueprint-ref <path> --blueprint-version v1`).
No GREEN work begins until a frozen blueprint exists.

## Rich path — seeding from a blueprint-crafting spec

When the input is a blueprint-crafting artifact (its `.queue.md` carries the `producer: blueprint-crafting` marker — `plan_queue.detect_producer` — and the spec is reachable via the queue's `authority_chain`), the Planner **derives the Intent Blueprint from the spec rather than from the raw request** (odp1-blueprint-collapse-design D1: seed, don't alias). The spec and the Blueprint are different artifact kinds at different AC abstraction levels, so the Blueprint is a **derivative** of the spec, not an alias:

- spec `acceptance-criteria` → Blueprint AC, refined into BDD Given/When/Then (each → an executable test).
- spec `jtbd` + `scope-boundary` → Blueprint UC.
- spec `constraints-assumptions` → Blueprint NFR.
- spec `non-goals` → Blueprint scope (explicit exclusions).
- spec `desired-outcome-metrics` + `decisions` → authority context the Planner references but does not replicate (no Blueprint counterpart).

This collapses the authority (one source: the spec), not the artifacts. The Planner still does the refinement (product AC → BDD → test mapping) — the Blueprint remains parallel-development's technical/executable artifact.

Fail-safe: no spec in the chain (free path) → the Planner derives the Blueprint from the raw request, unchanged (today's behavior).

**Coverage note** — the Planner is an agent (an LLM act); this seeding is guided by this section, not enforced by a deterministic gate. Its fidelity (does the Planner actually seed from the spec rather than re-imagine?) is an outer-ring/eval concern, like `plan_reviewer` precision (ADR #10), not a deterministic self-check.

## Read-only enforcement (three layers)

1. Deterministic guard: tools/pre-execute hook `blueprint_guard.py` DENIES any Edit/Write/MultiEdit to a `**/intent-blueprints/*.blueprint.md` whose frontmatter `status` is `frozen`. The Coder cannot bypass it.
2. Revision channel: the ONLY way to change a blueprint (see below).
3. Reviewer check: the outer-ring reviewer is prompted to verify no blueprint was silently modified outside the revision channel.

## Blueprint Revision Channel (the only change path)

If implementation or review discovers the blueprint is:

- unreachable (a use case is physically impossible),
- self-contradictory (NFR conflicts with a use case), or
- has acceptance criteria that cannot be satisfied,

the Coder MUST NOT edit the blueprint. Instead:

1. Set the blueprint frontmatter `status: revising` (the guard now allows edits).
2. Raise a suspend with a blueprint-defect flag: `loop_state.py mark-suspend --blueprint-defect --reason "<what is unreachable/contradictory>"`.
3. Escalate to the Planner (`requirements-manager` / `Plan`) + a human. Revise explicitly.
4. Bump `blueprint_version`; record it: `loop_state.py set-blueprint-version v<n>`.
5. Set `status: frozen` again (the guard re-locks).
6. The loop restarts at Phase 1 with the new blueprint ref.

The blueprint changes ONLY through this channel — no silent edits. This is the rigid-constraint escape hatch required by the spec.

## Diff-to-blueprint check (outer ring)

Performed by the outer-ring reviewer (see [convergent-loop.md](convergent-loop.md) reviewer prompt). For each Core Use Case and AC, state satisfied | partially-satisfied | missing, with file:line evidence. Flag any value hardcoded to bypass a failing test. A "missing" or "hardcoded" verdict triggers the intent-drift hard-rollback path.
