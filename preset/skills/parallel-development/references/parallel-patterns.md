# Parallel Execution Patterns

Guidelines for determining when tasks can be executed in parallel.

## Contents

- [Parallelizable Scenarios](#parallelizable-scenarios)
  - [1. Multi-File Implementation](#1-multi-file-implementation)
  - [2. Independent Module Development](#2-independent-module-development)
  - [3. Test + Implementation Parallel (TDD)](#3-test--implementation-parallel-tdd)
- [Non-Parallelizable Scenarios](#non-parallelizable-scenarios)
  - [1. Sequential Dependencies](#1-sequential-dependencies)
  - [2. Shared Resource Conflicts](#2-shared-resource-conflicts)
  - [3. Architectural Decisions](#3-architectural-decisions)
- [Parallel Execution Workflow](#parallel-execution-workflow)
- [Concurrency Scheduling Algorithm](#concurrency-scheduling-algorithm)
- [Python Conflict Scenarios](#python-conflict-scenarios)
- [Decision Tree](#decision-tree)

## Parallelizable Scenarios

### 1. Multi-File Implementation

Different files of the same task type can be implemented in parallel.

Example: Writing multiple test files

```text
Parallel execution:
- Agent 1: Write tests for authService
- Agent 2: Write tests for authStore
- Agent 3: Write tests for router guards
```

Example: Implementing independent components

```text
Parallel execution:
- Agent 1: Implement AppHeader component
- Agent 2: Implement AppSidebar component
- Agent 3: Implement AppMain component
```

Conditions:
Files are independent (no shared imports/dependencies)
No shared state mutations
Can be tested independently
No shared configuration files

### 2. Independent Module Development

Modules without dependencies can be developed in parallel.

Example: Config service modules

```text
Parallel execution:
- Agent 1: Implement matcher config module
- Agent 2: Implement response config module
- Agent 3: Implement proxy config module
```

Conditions:
Clear module boundaries
No circular dependencies
Independent API contracts
Separate test files

### 3. Test + Implementation Parallel (TDD)

In TDD, tests drive implementation. Tests are written FIRST.

Correct Pattern:

Phase 1 (RED) - Sequential:

- Agent (tester): Write test cases for feature (expect failure)

Phase 2 (GREEN) - Parallel:

- Agent 1 (developer): Implement feature A to pass tests
- Agent 2 (developer): Implement feature B to pass tests
- Agent 3 (tester): Write additional tests if needed

Prohibited Pattern:
Tester: Write tests (depends on implementation) - This is NOT TDD

Conditions:
Test API contract defined first
Implementation matches test expectations
Tests use mocks/stubs for incomplete dependencies

## Non-Parallelizable Scenarios

### 1. Sequential Dependencies

Tasks with dependencies must execute sequentially.

Example:

```text
Sequential:
1. Architect: Design module structure
2. Tester: Write tests based on design contract
3. Developer: Implement modules (to pass tests)
```

Note: In TDD, tests are written AFTER design but BEFORE implementation.

### 2. Shared Resource Conflicts

Tasks modifying the same file cannot run in parallel.

Example:

```text
Must be sequential:
- Multiple developers updating router/index.ts
- Multiple updates to the same store
- Changes to shared configuration
```

"Sequential" here means **serialized subagent dispatch**, NOT the orchestrator executing the tasks itself: dispatch the first task's Coder subagent, await its return, then dispatch the next. Conflict-serializable tasks never run concurrently (no write conflict), yet each still runs in its own subagent so the inner-ring churn stays out of the orchestrator's context. The orchestrator executes a task directly only as an exception (trivial single edit, or tight-coupling continuity a Diff + summary cannot bridge). Rationale and the three-role model: ADR #14 in [design-decisions.md](design-decisions.md) and [convergent-loop.md](convergent-loop.md) § Roles & contexts.

**Dispatch is an escalation, not the blanket default (ADR #39).** The orchestrator-worker upside is reachable ONLY when (a) parallelism is available (independent items / `parallel_group`) or (b) horizon is long enough to bind (projected >~50% of context). A sequential dependency chain gets zero parallelism upside from dispatch and only partial context-isolation (the orchestrator still reads every diff for the outer ring), so inline remains the default for sequential / short-horizon / tight-coupling work. **Skill-self-maintenance is a first-class inline carve-out**: edits to the skill's own infra (gate scripts, hooks, agent defs, registry, `platforms.json`) stay inline even under dispatch escalation, because the orchestrator's accumulated idiom (rules 5/7/8/10, exemplar, `disconnect_check`) is the quality guarantee a fresh Coder subagent would regress on. **Either way, drive `loop_state`** (`bump-iteration` / `gate-fail` / `snapshot` / `record-outer`) every round — inline does not exempt bookkeeping.

### 3. Architectural Decisions

Decisions affecting implementation must come first.

Example:

```text
Sequential:
1. Choose state management solution
2. Implement stores using chosen solution
```

## Parallel Execution Workflow

1. Analyze Request - Identify independent subtasks
2. Check Dependencies - Verify no conflicts, determine `files_touched` per task
3. Assign Roles - Map subtasks to roles/agents
4. Schedule & Execute - Concurrency-aware dispatch (see [Concurrency Scheduling Algorithm](#concurrency-scheduling-algorithm))
5. Aggregate Results - Combine outputs, resolve conflicts
6. Verify Integration - Run tests, check for issues

## Concurrency Scheduling Algorithm

### Slot Model

The orchestrator maintains a fixed pool of execution slots. Each slot holds at most one running agent. When an agent completes (success or failure), its slot becomes available for a pending task.

- `max_concurrency`: Total slot count. Default 5.
- `running`: Set of currently executing tasks.
- `pending`: Queue of tasks not yet started, ordered by priority (earlier subtasks first, or user-specified order).

### Task Metadata Convention

Each task created via TaskCreate includes:

Web example:

```json
{
  "files_touched": ["src/auth/login.ts", "src/auth/login.test.ts"],
  "depends_on": ["task-42"],
  "agent_type": "frontend-developer"
}
```

iOS example:

```json
{
  "files_touched": ["Sources/Features/LoginView.swift", "Tests/LoginViewTests.swift"],
  "depends_on": [],
  "agent_type": "ios-developer",
  "metadata": {
    "prompt": "iOS SwiftUI developer, implement LoginView with @MainActor ViewModel"
  }
}
```

Fields:

- `files_touched`: File paths this task will read or modify. Required for conflict detection.
- `depends_on`: Task IDs that must complete before this task can start. For explicit dependency chains beyond file-level conflicts.
- `agent_type`: The subagent_type to use when launching the Agent tool.

### Conflict Detection Matrix

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same file in both `files_touched` | Yes | Schedule sequentially |
| Different files, no shared imports | No | Parallel |
| Different files, but one imports the other | Yes | Schedule sequentially (the importer runs after) |
| Same database migration file | Yes | Schedule sequentially |
| Same config file (e.g., `tsconfig.json`) | Yes | Schedule sequentially |
| Same `.xcodeproj/project.pbxproj` | Yes | Schedule sequentially — pbxproj is a merge-conflict minefield. Prefer XcodeGen/Tuist (see [ios-patterns.md](ios-patterns.md)) |
| Same `Package.swift` | Yes | Schedule sequentially — SPM dependency resolution is not concurrency-safe |
| Same `Package.resolved` | Yes | Schedule sequentially — JSON file that pins exact versions |
| Different SPM targets, no shared dependencies | No | Parallel — each agent works within its own target |
| Same SPM `.build/` directory | Yes | Use separate scratch paths or serialize builds. See [ios-patterns.md](ios-patterns.md) |
| One task's output is another's input (`depends_on`) | Yes | Schedule sequentially |

### Apple Platform Conflict Scenarios

iOS/macOS projects introduce unique conflict patterns not present in web projects:

pbxproj Merge Conflicts: The `.xcodeproj/project.pbxproj` file is a flat UUID-keyed plist that git handles poorly. Every agent that adds a file to the project modifies pbxproj. Mitigation:

1. Prefer XcodeGen/Tuist — agents edit `project.yml` or `Project.swift` instead, eliminating pbxproj conflicts entirely.
2. If XcodeGen/Tuist is not feasible, mark pbxproj as a shared resource and schedule all Xcode project modifications sequentially.
3. Use `.gitattributes` with `*.pbxproj merge=union` as a safety net.

Swift Concurrency Boundaries: When agents work on features that communicate via actors:

- Agents on different actors can run in parallel (no file overlap, different actor isolation domains).
- BUT they share the protocol/interface boundary — define the protocol first (serial phase), then implement both sides in parallel.
- Cross-agent actor communication must agree on `Sendable` types — the architect phase should define shared types before parallel implementation.

App Bundle Resources: Multiple agents adding resources (images, asset catalogs, localized strings) to the same target:

- `Assets.xcassets/` — parallel additions to different subdirectories are safe (each image set is an independent directory).
- `Localizable.strings` — serial access only (flat key-value file).
- `Info.plist` — serial access only (flat plist).
- `*.entitlements` — serial access only (shared entitlement declarations).
- `PrivacyInfo.xcprivacy` — serial access only (required by Apple since May 2024 for App Store submissions). Agents adding third-party SDK dependencies must update this manifest with the required reason APIs used by those dependencies.

### iOS Modularization & Parallel Strategy

How the project's module structure affects parallel execution opportunities. Feature-based modularization (recommended) gives each agent its own SPM target with zero file overlap. Layer-based modularization requires more sequential scheduling. For the full strategy including conflict detection at target granularity, hybrid scheduling, and build time optimization, see [ios-patterns.md](ios-patterns.md) § Modularization & Parallel Strategy.

### Python Conflict Scenarios

Python projects introduce conflict patterns specific to the package management, migration, and testing ecosystem. Full detail is in [python-patterns.md](python-patterns.md); the summary below covers the cases the scheduler must handle.

pyproject.toml Merge Conflicts: The `[project.dependencies]` array and `[project.optional-dependencies]` tables are append targets — multiple agents adding dependencies produce merge conflicts. Mitigation:

1. Mark `pyproject.toml` in `files_touched` for any task that adds or modifies dependencies.
2. Schedule all dependency-modifying tasks sequentially.
3. After all dependency additions converge, regenerate the lock file once (`uv lock` or `poetry lock`).
4. Run `uv sync` or `poetry install` to synchronize the environment.

Lock File Conflicts: `uv.lock` and `poetry.lock` are generated files that must reflect the resolved state of pyproject.toml. They must not be modified by parallel agents. Regenerate once after all dependency changes are complete.

Database Migration Chain Conflicts: Alembic migration files contain `revision` and `down_revision` fields forming a linked list. Two agents creating migrations simultaneously produce conflicting chain links.

1. Alembic: Serialize all migration-creating tasks. After convergence, run `alembic upgrade head` to verify chain integrity. If broken, merge: `alembic merge heads -m "merge"`.
2. Django: Migrations within the same app must be serialized. Cross-app migrations are parallel-safe — Django handles ordering.

conftest.py Conflicts: pytest fixtures defined in conftest.py are auto-discovered by directory hierarchy. Two agents modifying the same conftest.py must be serialized. Agents should prefer adding fixtures to their own test subdirectory's conftest.py. Top-level conftest.py modifications always require serialization.

**init**.py Conflicts: Package **init**.py files serve dual roles (package markers and public API exports). Multiple agents adding exports to the same **init**.py must be serialized. Mitigation: agents use explicit imports (`from package.module import X`) during development; reconcile exports in integration phase.

Python-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `pyproject.toml` | Yes | Schedule sequentially |
| Same `uv.lock` / `poetry.lock` | Yes | Schedule sequentially |
| Same `conftest.py` | Yes | Schedule sequentially |
| Different `conftest.py` in different directories | No | Parallel |
| Same Alembic `versions/` directory | Yes | Schedule sequentially (chain ordering) |
| Same Django app's `migrations/` | Yes | Schedule sequentially |
| Different Django apps' `migrations/` | No | Parallel |
| Same `__init__.py` | Yes | Schedule sequentially |
| Same `requirements.txt` | Yes | Schedule sequentially (flat file) |
| Different `.py` files, no cross-imports | No | Parallel |
| Different `.py` files, one imports the other | Yes | Schedule sequentially |

### Rust Conflict Scenarios

Rust projects introduce conflict patterns around the cargo manifest, the lock file, and the build script. Full detail is in [rust-patterns.md](rust-patterns.md); the summary below covers the cases the scheduler must handle.

Cargo.toml Merge Conflicts: `[dependencies]`, `[dev-dependencies]`, and `[features]` are append targets — multiple agents adding crates produce merge conflicts. Mitigation:

1. Mark `Cargo.toml` in `files_touched` for any task that adds or modifies dependencies/features.
2. Schedule all manifest-modifying tasks sequentially.
3. After all additions converge, regenerate the lock file once (`cargo update`/`cargo check`).

Cargo.lock Conflicts: `Cargo.lock` is a generated file pinning exact versions. It must not be edited by hand or by parallel agents. Regenerate once after `Cargo.toml` converges.

build.rs Conflicts: a `build.rs` build script runs before every crate compile and affects the whole build. Serialize any task that modifies `build.rs`.

Workspace Conflicts: in a `[workspace]`, the root `Cargo.toml`'s `[workspace.dependencies]` and `[workspace.members]` are shared — serialize edits to the workspace manifest.

Rust-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `Cargo.toml` | Yes | Schedule sequentially |
| Same `Cargo.lock` | Yes | Schedule sequentially (regenerate once after convergence) |
| Same `build.rs` | Yes | Schedule sequentially |
| Same workspace `Cargo.toml` | Yes | Schedule sequentially |
| Different workspace members (`-p <member>`) | No | Parallel |
| Different `.rs` files, no `use` coupling | No | Parallel |
| Different `.rs` files, one `use`s the other | Yes | Schedule sequentially |

### Java Conflict Scenarios

Java projects introduce conflict patterns around the build manifest (Maven `pom.xml` or Gradle `build.gradle` / `build.gradle.kts`) and the dependency lock. Full detail is in [java-patterns.md](java-patterns.md); the summary below covers the cases the scheduler must handle.

pom.xml / build.gradle Merge Conflicts: `<dependencies>` / `<plugins>` (Maven) and the `dependencies {}` / `plugins {}` blocks (Gradle) are append targets — multiple agents adding deps produce merge conflicts. Mitigation:

1. Mark `pom.xml` / `build.gradle` in `files_touched` for any task that adds or modifies dependencies/plugins.
2. Schedule all manifest-modifying tasks sequentially.
3. After additions converge, regenerate the lockfile once (Maven: re-resolve; Gradle: `gradle dependencies --write-locks`).

Lock File Conflicts: Gradle's `gradle.lockfile` (dependency locking) and Maven's pinned versions are derived state — never edit by hand or by parallel agents. Regenerate once after the build file converges.

Multi-module / Multi-project Boundaries: Maven modules (`-pl :module`) and Gradle subprojects (`:subproject`) are the natural parallel boundary — each agent works within its own module/subproject with zero file overlap. Shared annotation-processor configuration or a root parent POM / `settings.gradle` common config must be serialized.

Java-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `pom.xml` | Yes | Schedule sequentially |
| Same `build.gradle` / `build.gradle.kts` | Yes | Schedule sequentially |
| Same `gradle.lockfile` / pinned versions | Yes | Schedule sequentially (regenerate once after convergence) |
| Same parent POM / `settings.gradle` shared config | Yes | Schedule sequentially |
| Different Maven modules (`-pl :a` vs `-pl :b`) | No | Parallel |
| Different Gradle subprojects (`:a` vs `:b`) | No | Parallel |
| Different `.java` files, no import coupling | No | Parallel |
| Different `.java` files, one imports the other | Yes | Schedule sequentially |

### Go Conflict Scenarios

Go projects introduce conflict patterns around the module manifest (`go.mod`) and the checksum lock (`go.sum`). Full detail is in [go-patterns.md](go-patterns.md); the summary below covers the cases the scheduler must handle.

go.mod Merge Conflicts: `require` / `replace` / `exclude` are append/override targets — multiple agents editing them produce merge conflicts. Mitigation:

1. Mark `go.mod` in `files_touched` for any task that adds or modifies dependencies.
2. Schedule all module-manifest-modifying tasks sequentially.
3. After additions converge, regenerate `go.sum` once (`go mod tidy`).

go.sum Conflicts: `go.sum` is a generated checksum file. It must not be edited by parallel agents. Regenerate once after `go.mod` converges.

Workspace (`go.work`) Conflicts: a `go.work` file's local module overrides affect every build — serialize edits to it.

Go-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `go.mod` | Yes | Schedule sequentially |
| Same `go.sum` | Yes | Schedule sequentially (regenerate once after convergence) |
| Same `go.work` | Yes | Schedule sequentially |
| Different workspace member modules | No | Parallel |
| Different `.go` files, no import coupling | No | Parallel |
| Different `.go` files, one imports the other | Yes | Schedule sequentially |

### Web Conflict Scenarios

Web (Node) projects introduce conflict patterns around the manifest, the lock file, and shared config. Full detail is in [web-patterns.md](web-patterns.md); the summary below covers the cases the scheduler must handle.

package.json Merge Conflicts: `dependencies` / `devDependencies` are append targets — multiple agents adding packages produce merge conflicts. Mitigation:

1. Mark `package.json` in `files_touched` for any task that adds or modifies dependencies.
2. Schedule all dependency-modifying tasks sequentially.
3. After convergence, run the install once (`npm install` / `pnpm install` / `yarn`) to regenerate the lock file.

Lock File Conflicts: `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` are generated. They must not be edited by parallel agents. Regenerate once after `package.json` converges.

Shared Config Conflicts: `tsconfig.json`, `vite.config.*`, `eslint.config.*`, and the root `index.html` are shared — serialize edits.

Web-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `package.json` | Yes | Schedule sequentially |
| Same lock file | Yes | Schedule sequentially (regenerate once) |
| Same `tsconfig.json` / build config | Yes | Schedule sequentially |
| Different component files, no imports shared | No | Parallel |
| Different component files, one imports the other | Yes | Schedule sequentially (or extract a shared interface first) |

### Scheduling Loop (Per-Turn)

Claude's execution is turn-based. Each turn:

1. Evaluate completed tasks from the previous turn. Update their TaskCreate status.
2. Calculate `available_slots = max_concurrency - len(running)`.
3. Iterate through `pending` in priority order:
   - If `available_slots <= 0`: stop scheduling this turn.
   - If the task's `depends_on` list contains any non-completed task: skip.
   - If the task's `files_touched` intersects with any running task's `files_touched`: skip.
   - Otherwise: launch Agent tool call, update task to `in_progress`, decrement `available_slots`.
4. Issue all Agent calls for this turn in a single message (parallel dispatch).
5. When results return: process completions, loop back to step 1.

Note on step 3's "skip": a task skipped because its `files_touched` intersects a running task is simply deferred to a later turn, then launched as its own Agent once the conflicting task frees the slot — i.e. serialized subagent dispatch. On each completion, the orchestrator keeps only the folded result (task status, files changed, one-line inner summary), not the subagent's inner trail — see [convergent-loop.md](convergent-loop.md) § Cross-task orchestrator context folding.

### Backpressure

When all pending tasks are blocked by running tasks (no eligible task fits any slot), the scheduler waits for the next completion event rather than busy-looping. This happens naturally in Claude's turn model -- the orchestrator simply dispatches zero new agents and waits for running ones to return.

### Error Recovery

- Failed agent: Free its slot. Set task status to a descriptive failure state. Report to user.
- Succeeded-but-out-of-scope agent: a Coder that returns clean but wrote outside its declared `files_touched` (e.g. rogue skill-infra / dependency churn from an interrupted run) passes every correctness gate — correctness ≠ belonging. At the task boundary run `scope_check.py --task-base <dispatch-ref> --files-touched <csv>`; on `flag`, discard the out-of-scope paths (`git checkout HEAD -- <paths>`), keep a coherent in-scope diff, or `snapshot.py restore`. See ADR #15 in [design-decisions.md](design-decisions.md).
- Tasks depending on the failed task: Remain blocked. Do not auto-retry.
- Independent pending tasks: Proceed normally into freed slots.
- Platform-specific recovery: Some failure modes (derived data corruption, dependency resolution conflicts, simulator unavailability) are transient and may warrant one auto-retry before reporting. See platform-specific reference files for details: [ios-patterns.md](ios-patterns.md) § iOS Error Recovery for Parallel Agents, [python-patterns.md](python-patterns.md) § Error Recovery.

### Worked Example

8 subtasks, `max_concurrency = 5`, tasks A-H. File extensions in the examples below are placeholders — the same algorithm applies regardless of language (`.ts`, `.swift`, `.rs`, `.go`, etc.). The conflict detection logic is identical.

Web example:

```text
Task files_touched:
  A: [a.ts], B: [b.ts], C: [c.ts, shared.ts], D: [d.ts],
  E: [e.ts, shared.ts], F: [f.ts], G: [g.ts], H: [h.ts]

Turn 1:
  pending: [A, B, C, D, E, F, G, H]
  available_slots = 5

  Evaluate in order:
    A: no conflict, slots available → launch. slots=4
    B: no conflict → launch. slots=3
    C: no conflict → launch. slots=2
    D: no conflict → launch. slots=1
    E: shared.ts conflicts with running task C → skip
    F: no conflict → launch. slots=0
    G: no conflict, but slots=0 → wait
    H: no conflict, but slots=0 → wait

  Running: A, B, C, D, F

Turn 2:
  A, B, C, D, F complete.
  available_slots = 5
  pending: [E, G, H]

  Evaluate:
    E: shared.ts not touched by any running task → eligible. launch. slots=4
    G: no conflict → launch. slots=3
    H: no conflict → launch. slots=2

  Running: E, G, H

Turn 3:
  E, G, H complete. All done.
```

## Decision Tree

```text
User Request
    |
    v
Can task be broken into subtasks?
    |
    +-- No --> Execute sequentially
    |
    +-- Yes --> Identify subtasks + files_touched
                   |
                   v
               Any dependencies?
                   |
                   +-- Yes --> Execute sequentially
                   |
                   +-- No --> Check for shared resources
                                     |
                                     +-- Yes --> Execute sequentially
                                     |
                                     +-- No --> CONCURRENCY SCHEDULING
                                                      |
                                                      v
                                              Initialize scheduler
                                              (max_concurrency slots)
                                                      |
                                                      v
                                              Fill slots with eligible
                                              pending tasks (no conflicts)
                                                      |
                                                      v
                                              Dispatch agents in parallel
                                                      |
                                                      v
                                              Process completions,
                                              free slots, repeat
                                                      |
                                                      v
                                              All done? --> Aggregate + Verify
```

"Execute sequentially" leaves mean **serialized subagent dispatch** (one Coder subagent at a time), not orchestrator-internal execution — see the note under [Shared Resource Conflicts](#2-shared-resource-conflicts) and ADR #14 in [design-decisions.md](design-decisions.md).
