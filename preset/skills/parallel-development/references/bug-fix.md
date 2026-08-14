# Bug Fix Workflow

Phase-by-phase workflow for reproducing, fixing, and verifying bugs.

## Project Type Detection (ALWAYS RUN FIRST)

Before executing any phase, detect the project type to route to the correct toolchain:

| Project Type | Detected By | Test Framework | Developer Role |
| --- | --- | --- | --- |
| Web (Vue/React/Node) | `package.json`, no `.xcodeproj` | Jest/Vitest/Playwright | `frontend-developer` / `backend-developer` |
| iOS (Swift/SwiftUI) | `*.xcodeproj` or `Package.swift` | XCTest / XCUITest | `ios-developer` (impl + unit), `ios-tester` (XCUITest E2E) |
| Rust | `Cargo.toml` | cargo test | `backend-developer` |
| Go | `go.mod` | go test | `backend-developer` |
| Python | `pyproject.toml` | pytest | `backend-developer` |

The phases below apply to all project types. The specific tools, frameworks, and agent assignments adapt based on the detected project type.

## Phase 0: Intent Freeze (Sequential)

Role: Planner (`requirements-manager`)

Freeze a narrow Intent Blueprint capturing the expected post-fix behavior (the bug becomes a failed AC, the correct behavior becomes a passing AC), or reuse the owning feature's existing blueprint. The blueprint is the read-only anchor for Phase 4's diff-to-blueprint check. See [intent-blueprint.md](intent-blueprint.md).

## Phase 1: Analysis (Sequential)

Role: Requirements Analyst

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "similar bugs issues", "bug patterns root causes". Store: bug analysis with symptoms and root cause.

Task: Analyze bug report, identify root cause

## Phase 2: Regression Test (Sequential)

Role: Test Engineer → `tester` (Web/Backend) or `ios-developer` with XCTest prompt (iOS)

Memory: follow [memory-protocol.md](memory-protocol.md). Store: regression test case and expected result.

Write the regression test first (TDD) -- the test must reproduce the bug before the fix exists.

RED Phase - Write test that reproduces the bug:

Web: Task(tester): Write test case that reproduces the bug (expect failure) — use Jest/Vitest/Playwright per project setup.
iOS: Task(ios-developer with XCTest prompt): Write XCTest case that reproduces the bug (expect failure). Use `XCTAssert` patterns, not Jest/Vitest. If the bug is in UI behavior, write an XCUITest (route that to `ios-tester`).
Backend: Task(tester): Write test case that reproduces the bug — use the project's test framework (cargo test, go test, pytest).

## Phase 3: Fix (Sequential)

Role: Developer — `frontend-developer` / `backend-developer` (Web), or `ios-developer` (iOS)

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "fix patterns solutions". Store: fix applied, solution and impact.

GREEN Phase - Implement fix to pass test:

Each GREEN iteration, the agent self-runs the test most relevant to the fix for fast feedback BEFORE re-running the Phase 2 suite — using the Intent Blueprint's AC → test mapping when declared, else the per-language convention. This is agent self-discipline, not a gate. See [SKILL.md](../SKILL.md) "Self-run the relevant test each GREEN".

Web: Task(frontend-developer or backend-developer): Implement fix to make test pass
iOS: Task(ios-developer with Swift/SwiftUI prompt): Implement fix to make XCTest pass. If the fix touches `Package.swift` or `project.pbxproj`, those files must be serialized per [parallel-patterns.md](parallel-patterns.md).
Backend: Task(backend-developer): Implement fix to make test pass

After fix → re-run Phase 2 tests. If tests fail → debug and fix again. Only proceed when tests pass.

## Phase 4: Review (Sequential) — Convergent Fix Loop

After the fix, enter the dual-ring Convergent Fix Loop (see [convergent-loop.md](convergent-loop.md)):

- Inner ring — Fast Gate: type check, lint, test suite (including the Phase 2 regression test). With the opt-in infra installed, per-file checks also run as a tools/post-execute hook. Red → fix, re-run; short-circuit, do not enter the outer ring.
- Inner ring — Architecture-Contract Gate (at convergence): codable architecture contracts (circular deps, layer isolation, concurrency baseline). Blocker → fix inner, re-run.
- Gate附加条件: coverage ≥ threshold, no skip/ignore, flaky stabilized, test set not shrunk vs the blueprint (the regression test must remain).
- Outer ring: independent `code-reviewer` subagent on the final Diff against the Intent Blueprint. Dual-line check (semantic + diff-to-blueprint), structured findings with line numbers.
  - iOS: review for Swift Concurrency violations, missing `[weak self]`, `try!` in production code, and MainActor isolation issues. Use ast-grep Swift patterns from [ast-grep-patterns.md](ast-grep-patterns.md).
- Verdict dispatch: pass → converge; semantic issue → rewrite; intent drift → hard rollback + reverse prompt; blueprint defect → revision channel.
- Circuit breaker is a state machine (Thrashing N=3 / cap M=8 / budget T,W,C → degrade/escalate/suspend/hard-terminate), not a flat iteration count.

Do not report mid-loop status to the user.

## Phase 5: Documentation (Sequential)

Role: Documentation Writer

Memory: follow [memory-protocol.md](memory-protocol.md). Store: bug resolution with fix and verification.

Task: Update status
