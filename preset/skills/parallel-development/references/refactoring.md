# Refactoring Workflow

Phase-by-phase workflow for safely refactoring code while maintaining functionality.

## Project Type Detection (ALWAYS RUN FIRST)

Before executing any phase, detect the project type to route to the correct toolchain:

| Project Type | Detected By | Test Framework | Developer Role |
| --- | --- | --- | --- |
| Web (Vue/React/Node) | `package.json`, no `.xcodeproj` | Jest/Vitest | `frontend-developer` / `backend-developer` |
| iOS (Swift/SwiftUI) | `*.xcodeproj` or `Package.swift` | XCTest | `ios-developer` (impl + unit), `ios-tester` (XCUITest E2E) |
| Rust | `Cargo.toml` | cargo test | `backend-developer` |
| Go | `go.mod` | go test | `backend-developer` |
| Python | `pyproject.toml` | pytest | `backend-developer` |

The phases below apply to all project types. The specific tools and agent assignments adapt based on the detected project type.

## Phase 0: Intent Freeze (Sequential)

Role: Planner (`requirements-manager`)

Freeze a narrow Intent Blueprint: the acceptance criteria = the existing tests that lock current behavior (Phase 2 produces them), and the NFR = "behavior unchanged, structure improved." The blueprint anchors the Phase 4 diff-to-blueprint check so a refactor cannot silently change behavior. See [intent-blueprint.md](intent-blueprint.md).

## Phase 1: Analysis (Sequential)

Role: Architect

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "code structure architecture patterns", "refactoring patterns best practices". Store: refactoring plan with current issues and target structure.

Task: Analyze current structure, plan refactoring

## Phase 2: Ensure Test Coverage (Sequential)

Role: Test Engineer → `tester` (Web/Backend) or `ios-developer` with XCTest prompt (iOS)

Memory: follow [memory-protocol.md](memory-protocol.md). Store: test coverage gaps identified.

Refactoring requires existing tests. If tests are missing, write them first (TDD) -- the tests lock in the behavior that the refactoring must preserve.

RED Phase (if needed):

- Web: Write Jest/Vitest tests for existing behavior. Ensure all tests pass.
- iOS: Write XCTest unit tests for existing behavior. Use `swift test` or `xcodebuild test` to verify they pass. Coverage can be checked via `xcrun xccov view --report coverage.xcresult`.
- Backend: Write tests using the project's framework (cargo test, go test, pytest). Ensure all tests pass.

## Phase 3: Refactoring (Parallel when safe)

Role: Developer — `frontend-developer` / `backend-developer` (Web), or `ios-developer` (iOS Swift/SwiftUI)

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "design patterns SOLID". Store: refactored module changes and improvements.

REFACTOR Phase - Refactor while keeping tests green:

For independent files/modules:

Web:

```text
Task(developer): Refactor module A (keep tests green)
Task(developer): Refactor module B (keep tests green)
Task(developer): Refactor module C (keep tests green)
```

iOS:

```text
Task(ios-developer with Swift/SwiftUI prompt): Refactor LoginViewModel (keep XCTest green)
Task(ios-developer with Swift/SwiftUI prompt): Refactor UserService actor (keep XCTest green)
```

Continuously run Phase 2 tests after each change. If tests fail → revert change, investigate, re-apply fix. For iOS, `swift test --filter TargetName` allows running only the relevant test target to validate each refactored module independently.

## Phase 4: Verification (Sequential) — Convergent Fix Loop

After Phase 3 refactoring completes, enter the dual-ring Convergent Fix Loop (see [convergent-loop.md](convergent-loop.md)):

- Inner ring — Fast Gate: type check, lint, full test suite. With the opt-in infra installed, per-file checks also run as a tools/post-execute hook. Red → revert/fix, re-run; short-circuit, do not enter the outer ring.
- Inner ring — Architecture-Contract Gate (at convergence): codable architecture contracts. This is where refactoring most often catches regressions (a refactor must not introduce a circular dependency or break layer isolation). Blocker → fix inner, re-run.
- Gate附加条件: coverage ≥ threshold, no skip/ignore, flaky stabilized, test set not shrunk (behavior must be preserved — no deleting tests).
- Outer ring: independent `code-reviewer` subagent on the final Diff against the Intent Blueprint. Dual-line check (semantic + diff-to-blueprint), structured findings with line numbers. For refactoring, the intent line verifies behavior is preserved while structure improved.
  - iOS: review for Swift Concurrency violations, missing `[weak self]`, `try!` in production code, and MainActor isolation issues. Use ast-grep Swift patterns from [ast-grep-patterns.md](ast-grep-patterns.md).
- Verdict dispatch: pass → converge; semantic issue → rewrite; intent drift (behavior changed) → hard rollback + reverse prompt; blueprint defect → revision channel.
- Circuit breaker is a state machine (Thrashing N=3 / cap M=8 / budget T,W,C → degrade/escalate/suspend/hard-terminate), not a flat iteration count.

Do not report mid-loop status to the user.
