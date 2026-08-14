---
blueprint_version: v1
frozen_at: 2026-06-18
task: <one-line task description>
status: frozen
---

# Intent Blueprint — <task>

This blueprint is the FROZEN, read-only anchor for the convergence loop. The Coder cannot edit it. Reviewer must diff every change against it. To change intent, use the Blueprint Revision Channel (status -> revising -> Planner+human -> version bump -> re-freeze). See references/intent-blueprint.md.

## Core Use Cases

Functional points the system MUST implement. The Coder must never delete or silence a use case to satisfy a compile/test constraint.

- UC-1: <must-implement functional point>
- UC-2: <must-implement functional point>

## Acceptance Criteria (BDD)

Behavior-driven, structured verification baseline. Each should map to an executable test. "Satisfied" requires the behavior, not merely a green exit.

- AC-1: Given <context> When <action> Then <observable outcome>
- AC-2: Given <context> When <action> Then <observable outcome>

## Non-Functional Requirements (NFR)

System-level hard constraints (performance, external dependencies, capacity). Flag a Blueprint Defect if an NFR contradicts a use case or is physically unreachable.

- NFR-1: <performance target / external dependency / capacity constraint>

## Acceptance-Criteria -> Test Mapping

Declared at RED phase. Maps each AC to the executable test(s) that verify it. The value is a test name or nodeid (e.g. `test_user_registration`, `tests/test_auth.py::test_user_registration`), NOT a bare file path — the test-name set gate (arch_contract_tests) verifies each mapped test exists in the per-language collected set, so the value must be a name the collector emits. One bullet per test; multiple bullets may share an AC id (each name collected). Comma-listing multiple names on one line is NOT supported (it would be read as one name). Section is optional: when absent, the gate degrades to a count + coverage note.

- AC-1 -> tests/test_auth.py::test_user_registration
- AC-2 -> test_login_redirect
