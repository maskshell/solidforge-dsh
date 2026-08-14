# Feature Development Workflow

Phase-by-phase workflow for implementing new features with TDD.

## Contents

- [Phase 0: Intent Freeze (Sequential)](#phase-0-intent-freeze-sequential)
- [Phase 1: Analysis (Sequential)](#phase-1-analysis-sequential)
- [Phase 2: Architecture (Sequential, if needed)](#phase-2-architecture-sequential-if-needed)
- [Phase 3: Planning (Sequential)](#phase-3-planning-sequential)
- [Phase 4: Test Writing — RED Phase (Sequential)](#phase-4-test-writing--red-phase-sequential)
- [Phase 5: Implementation — GREEN Phase (Parallel when independent)](#phase-5-implementation--green-phase-parallel-when-independent)
- [Phase 6: Integration & Review (Sequential) — Convergent Fix Loop](#phase-6-integration--review-sequential--convergent-fix-loop)
- [Phase 7: Documentation (Sequential)](#phase-7-documentation-sequential)

## Phase 0: Intent Freeze (Sequential)

Role: Planner → `requirements-manager` (then `Plan` for structuring)

Convert the request into a frozen Intent Blueprint: Core Use Cases (must-implement functional points), Acceptance Criteria (BDD Given/When/Then, each mapping to a Phase 4 test), and Non-Functional Requirements. Set frontmatter `status: frozen` and record the ref in loop-state. With the opt-in infra installed, the blueprint is deterministically read-only for the Coder. No Phase 5 GREEN work begins without a frozen blueprint. See [intent-blueprint.md](intent-blueprint.md).

## Phase 1: Analysis (Sequential)

Role: Requirements Analyst → `requirements-manager`

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "similar feature implementations", "technical dependencies". Store: requirements analysis, prioritization decisions.

Tasks:

- Analyze user requirements
- Check memory for similar past features
- Identify acceptance criteria
- Break down into subtasks
- Identify dependencies

Output: Task breakdown with dependencies

## Phase 2: Architecture (Sequential, if needed)

Role: Architect → `architect` (Web) or Apple Platform Architect → `architect` with iOS architecture prompts (see [role-agent-mapping.md](role-agent-mapping.md) for iOS-specific triggers)

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "project architecture patterns", "framework selection". Store: module structure, architecture decisions.

Tasks:

- Design module structure
- Define interfaces
- Make technical decisions

Output: Architecture document/design

For iOS / Apple Platform projects using Swift Concurrency: Phase 2 must also produce actor isolation boundaries, Sendable shared type definitions, protocol stubs, and dependency direction declarations. These artifacts are required by Phase 5 for safe parallel implementation. See [ios-patterns.md](ios-patterns.md) § Parallel Agent Coordination for the full list and rationale.

For Python projects: Phase 2 must produce architecture artifacts per [python-patterns.md](python-patterns.md) § Architecture Phase Artifacts — API boundary map, model ownership, migration plan, shared dependency inventory, and import direction declaration. These artifacts define the constraints that enable Phase 5 parallel agents to implement without file conflicts or circular imports.

## Phase 3: Planning (Sequential)

Role: Detailed Designer → `Plan`

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "implementation patterns", "file naming conventions". Store: implementation plan, technical decisions.

Tasks:

- Create implementation plan
- Identify files to create/modify
- Estimate complexity

Output: Step-by-step plan

## Phase 4: Test Writing — RED Phase (Sequential)

Sequential — tests define interface contracts that implementations must satisfy. All test files are written in this phase before any implementation begins in Phase 5. This ordering is important because the tests define the API contracts that parallel agents independently implement against — if tests and implementation were written simultaneously, agents would have no shared contract to converge on.

Role: Test Engineer → `tester` (Web/Backend) or `ios-developer` for Swift Testing / XCTest unit + `ios-tester` for XCUITest (iOS)

Memory: follow [memory-protocol.md](memory-protocol.md). Search: "test patterns unit integration e2e", "testing frameworks". Store: test plan, test patterns.

Tests are written before implementation. This is the TDD red phase -- the test defines the interface contract that the implementation must satisfy.

Web RED Phase:

```text
Task(tester): Write tests for AppHeader (RED phase - expect failure)
Task(tester): Write tests for AppSidebar (RED phase - expect failure)
Task(tester): Write tests for AppMain (RED phase - expect failure)
```

iOS RED Phase:

```text
Task(ios-developer with Swift Testing prompt): Write @Test for LoginViewModel (RED phase - expect failure)
Task(ios-developer with XCTest prompt): Write XCTest for UserService actor (RED phase - expect failure)
Task(ios-tester with XCUITest prompt): Write XCUITest for login flow (RED phase - expect failure)
```

Python RED Phase:

```text
Task(tester): Write pytest tests for user_service (RED phase - expect failure)
Task(tester): Write pytest tests for order_service (RED phase - expect failure)
```

Tests use the project's test framework (pytest, unittest). For FastAPI projects, use TestClient for API tests. For Django, use Django's TestCase. See [python-patterns.md](python-patterns.md) for framework-specific test patterns.

Use TaskCreate/TaskUpdate to track progress. For iOS, prefer Swift Testing (`@Test`, `#expect`) for new unit/integration tests. Use XCTest only for UI automation (XCUITest) and performance benchmarks (`measure`). The `files_touched` metadata should include both the source file and the test file.

## Phase 5: Implementation — GREEN Phase (Parallel when independent)

Parallel when implementations don't share state — each agent works on an independent component.

Role: Developer → varies by task. Web → `frontend-developer` / `backend-developer`. iOS → `ios-developer` (Swift/SwiftUI/UIKit expertise). See [role-agent-mapping.md](role-agent-mapping.md).

Memory: each developer agent handles memory operations internally per [memory-protocol.md](memory-protocol.md). The orchestrator does not issue memory calls on their behalf.

GREEN Phase - Implement code to pass tests:

Use the concurrency scheduler from [parallel-patterns.md](parallel-patterns.md) rather than launching all agents at once. Assign `files_touched` for each implementation task so the scheduler can detect conflicts and respect provider concurrency limits.

Each GREEN iteration, the agent self-runs the test(s) most relevant to its change for fast feedback before the convergence gate runs the whole suite — using the Intent Blueprint's AC → test mapping when declared, else the per-language convention. This is agent self-discipline, not a gate (the tools/post-execute fast_gate hook was infeasible). See [SKILL.md](../SKILL.md) "Self-run the relevant test each GREEN".

Web example (independent components, no shared files):

```text
Create tasks with files_touched metadata:
  Task(frontend-developer): Implement AppHeader → files: [AppHeader.ts, AppHeader.test.ts]
  Task(frontend-developer): Implement AppSidebar → files: [AppSidebar.ts, AppSidebar.test.ts]
  Task(frontend-developer): Implement AppMain → files: [AppMain.ts, AppMain.test.ts]

Scheduler dispatches up to max_concurrency (default 5) agents per turn.
As agents complete, new eligible tasks fill the freed slots.
```

iOS example (independent SwiftUI views, no shared files):

```text
Create tasks with files_touched metadata:
  Task(ios-developer): Implement LoginViewModel → files: [LoginViewModel.swift, LoginViewModelTests.swift], agent_type: "ios-developer", prompt: "iOS SwiftUI developer — implement @Observable LoginViewModel with @MainActor"
  Task(ios-developer): Implement LoginView → files: [LoginView.swift], agent_type: "ios-developer", prompt: "iOS SwiftUI developer — implement LoginView consuming @Observable ViewModel"
  Task(ios-developer): Implement UserService → files: [UserService.swift, UserServiceTests.swift], agent_type: "ios-developer", prompt: "iOS Swift developer — implement Sendable-safe UserService actor with async/await"

Scheduler detects no file conflicts → all three run in parallel.
For iOS, mark Package.swift and project.pbxproj as shared resources so the scheduler serializes any dependency or project structure changes.
```

Python example (independent service modules, no shared files):

```text
Create tasks with files_touched metadata:
  Task(backend-developer): Implement user_service + models → files: [app/services/user_service.py, app/models/user.py]
  Task(backend-developer): Implement order_service + models → files: [app/services/order_service.py, app/models/order.py]

Scheduler detects no file conflicts → both run in parallel.
Mark pyproject.toml, app/main.py, and conftest.py as shared resources.
For database migrations, serialize all migration-creating tasks per [python-patterns.md](python-patterns.md).
```

## Phase 6: Integration & Review (Sequential) — Convergent Fix Loop

After Phase 5 agents complete, merge results and resolve conflicts. Then enter the dual-ring Convergent Fix Loop (see [convergent-loop.md](convergent-loop.md)):

- Inner ring — Fast Gate: type check, lint, test suite. With the opt-in infra installed, per-file checks also run as a tools/post-execute hook. Red → fix, re-run; short-circuit, do not enter the outer ring.
  - iOS/Xcode projects: use `xcodebuild` or `swift build` per [ios-patterns.md](ios-patterns.md). Include `-strict-concurrency=complete` for Swift 6 concurrency checking. Validate `.xcodeproj/project.pbxproj` is not corrupted (`xcodebuild -list`).
  - SPM projects: if multiple agents added code to the same package, run `swift package resolve` once before building.
  - Python projects: run dependency sync + type check + lint + format + test per the Tier 1 sequence in [python-patterns.md](python-patterns.md). Regenerate the lock file once if agents added dependencies.
- Inner ring — Architecture-Contract Gate (at convergence): run the codable architecture contracts for the platform (circular deps, layer isolation, concurrency baseline). This catches the cross-module violations parallel agents most often introduce. Blocker → fix inner, re-run. See [arch-contracts.md](arch-contracts.md).
- Gate附加条件: coverage ≥ threshold, no skip/ignore, flaky stabilized, test set not shrunk vs the Intent Blueprint.
- Outer ring: independent `code-reviewer` subagent on the merged Diff against the Intent Blueprint. Dual-line check (semantic + diff-to-blueprint), structured findings with line numbers.
  - iOS: review for Swift Concurrency violations, missing `[weak self]`, `try!` in production code, and MainActor isolation issues (ast-grep Swift patterns from [ast-grep-patterns.md](ast-grep-patterns.md)); run Instruments profiling for performance-sensitive features per [ios-patterns.md](ios-patterns.md).
  - Python: review for mutable default arguments, bare except, eval/exec usage, wildcard imports, and SQL injection patterns (ast-grep Python patterns from [ast-grep-patterns.md](ast-grep-patterns.md)).
- Verdict dispatch: pass → converge; semantic issue → rewrite; intent drift → hard rollback + reverse prompt; blueprint defect → revision channel.
- Circuit breaker is a state machine (Thrashing N=3 / cap M=8 / budget T,W,C → degrade/escalate/suspend/hard-terminate), not a flat iteration count.

Do not report mid-loop status to the user. The user sees output only when the loop converges or the breaker triggers.

## Phase 7: Documentation (Sequential)

Role: Documentation Writer → `documentation-writer`

Memory: follow [memory-protocol.md](memory-protocol.md). Store: feature completion, lessons learned, technical debt.

Tasks:

- Update implementation status
- Update project tracker
- Document technical debt

REFACTOR Phase (optional): After tests pass, refactor code while keeping tests green.

Verify documentation completeness. If gaps found, return to update.
