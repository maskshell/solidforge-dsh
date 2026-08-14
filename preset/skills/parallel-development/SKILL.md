---
name: parallel-development
description: |
  parallel-development (pd) orchestrator: runs multiple AI agents in parallel on independent dev tasks. Use it whenever the user wants to implement several features or components at once, work in parallel, do TDD (red-green-refactor, tests first), safely refactor code modules, coordinate backend and frontend simultaneously, or manage multi-agent tasks. Also trigger on "同时做", "并行实现", "test first", "red green refactor", or whenever multiple independent subtasks are identified. Platforms: iOS/Apple (Xcode, Swift, SwiftUI, XCTest, XCUITest, SPM, Simulator); Python (FastAPI, Django, Flask, SQLAlchemy, Pydantic, pytest, poetry, uv, pyproject.toml); Rust (Rust, cargo, Cargo.toml, clippy, rustfmt); Web/frontend (React, Vue, Svelte, TypeScript, JavaScript, Node.js, Express, Next.js, Playwright, ESLint, dependency-cruiser); Java (JDK 17+, Maven, Gradle, JUnit, Checkstyle, google-java-format); Go (Go, golang, go.mod, go vet, golangci-lint, go test). Trigger readily, even without an explicit "parallel" or "TDD" keyword.
---

# Parallel Development

> **DeepSeek Harness.** This skill is SolidForge's convergence loop running on the DeepSeek Harness. Harness-specific bindings: role agents are plain prompt files under the preset's `agents/` directory (`agents/<name>.agent.md`) — spawn them with the `subagent` tool by inlining that prompt; the deterministic gates (`fast_gate.py`, `blueprint_guard.py`, `counters.py`) are wired as `tools/pre-execute` / `tools/post-execute` listeners by the `solidforge-loop-gates` plugin and also callable directly from this skill's `infra/`; project state lives in `.solidforge/loop/` (env override `$SOLIDFORGE_PROJECT_DIR`, default cwd); the preset root is `$SOLIDFORGE_PRESET_ROOT`. See the port's `docs/port-design.md` for the paper-level re-derivation.

## Core Principles

### TDD Default

1. RED - Write tests first (expect failure)
2. GREEN - Implement minimum code (make tests pass)
3. REFACTOR - Improve while tests pass

TDD is the default for new features and bug fixes. Exploration, prototyping, and minor tweaks to already-tested code may skip the RED phase.

### Self-run the relevant test each GREEN (agent behavior, not enforced)

On each GREEN iteration, run the test(s) most relevant to the change for fast feedback BEFORE the convergence gate runs the whole suite. This closes the fast-feedback gap deterministically only an agent can — a `tools/post-execute` fast_gate listener was considered and WITHDRAWN (convention assumption `tests/test_<module>.py`, DB/network-fixture timeout risk, too-frequent per edit).

- If the Intent Blueprint declares an AC → test mapping (see [intent-blueprint.md](references/intent-blueprint.md) "AC → Test Mapping"), run the mapped test(s) for the AC(s) this change targets — the mapping is the unambiguous test→impl link.
- Otherwise use the per-language convention (`tests/test_<module>.py` / `<module>_test.go` / `tests/test_*.rs`), or run what you judge relevant to the edited file. This is weaker than a declared mapping — state that honestly.
- This is agent self-discipline, not a gate. The convergence test gate (`arch_contract_tests.py`) is the authoritative pass/fail check; the AC→test-name set gate Blocks a deleted mapped test; the outer reviewer checks test quality. Self-running the relevant test each GREEN just shortens the loop.

### Definition of Done

Work is not complete when parallel agents finish. Work is complete when the Convergent Fix Loop converges — both the automated validation tier and the code review tier pass with zero issues. Until then, keep iterating. The user should only see a final report, not mid-loop status updates. This is what "done" means in every workflow (feature-dev, bug-fix, refactoring, etc.).

## Scope

This skill is an implementation execution engine, not a thinking engine.

- **Entry condition**: the task's primary deliverable is source or test code (a feature, a bug fix, a refactor, added/changed tests, or implementation-adjacent docs).
- **Deliverable**: converged code that passes the dual ring (inner Fast Gate + Architecture-Contract Gate + 附加条件; outer AI review against the Intent Blueprint). See [Definition of Done](#definition-of-done).
- **Out of scope**: design authoring, product specs (PRD), and project roadmaps/iteration plans. These are inputs this skill consumes as authoritative references (an arch-design or iteration-plan doc, or a frozen **DESIGN.md** from an external skill like Impeccable — see [external-skills.md](references/external-skills.md)), not artifacts it produces.

The hinge is the frozen Intent Blueprint; everything upstream of code is input, not deliverable. Out-of-scope requests are short, high-clarity tasks where the convergence loop has near-zero leverage — they are better served by one strong pass from a specialist agent. On such requests the Scope Guard (step 1 below) fires: it surfaces the expected gap and routes to the right tool rather than misrouting into Phase 0. Full catalog and rationale: [scope.md](references/scope.md).

## When This Skill Is Invoked

Execute the full lifecycle for the detected task type. Do not stop after a single phase. The sequence is:

1. **Scope Guard** (before any work) — if the primary deliverable is NOT source/test code (review a design doc, author a PRD, author a project roadmap/iteration plan), this skill is out of scope. **Exception: executing a referenced plan is IN scope** — if the user @-references an existing plan AND wants code delivered, enter plan-driven mode ([plan-driven-mode.md](references/plan-driven-mode.md)), not the out-of-scope path. Otherwise (authoring a plan, not following one), do NOT enter Phase 0 — emit a misuse hint naming the gap, recommend the specialist route, and offer the choice of hand-off or proceed-with-caveat. Terse gap hints (fire without loading scope.md):
   - Review a design doc → outer-ring review is diff-to-blueprint; with no code diff it degrades to a generic critique (≈ baseline). Route: subagent with `agents/architect.agent.md`.
   - Write a PRD → Phase 0 yields an Intent Blueprint: a technical/acceptance PRD that wants to proceed to code, not a product PRD. Route: subagent with `agents/requirements-manager.agent.md`.
   - Author a roadmap/plan → Phase 3 yields a single-task implementation plan, not a project-level iteration plan. Route: subagent with `agents/architect.agent.md` / plan mode. (Following/executing a referenced plan is NOT this case — see plan-driven mode above.)
   - Full catalog + the structural reason: [scope.md](references/scope.md).
2. Detect project type and task type → select the matching workflow from [Workflows](#workflows)
3. Phase 0 (Intent Freeze) → produce and freeze an Intent Blueprint before any implementation (see [intent-blueprint.md](references/intent-blueprint.md)). With the opt-in infra installed, the blueprint is deterministically read-only-enforced.
4. Execute all phases of that workflow in order (analysis → planning → test writing → implementation → integration → documentation)
5. Enter the Convergent Fix Loop automatically after implementation completes — iterate the inner ring (deterministic) + outer ring (semantic) until both pass clean (see [convergent-loop.md](references/convergent-loop.md))
6. Report the final converged result to the user

### Plan-driven mode (executing a multi-item plan)

When the Scope Guard detects a referenced plan to execute (the execute-plan carve-out in step 1), wrap the lifecycle above in an outer loop driven by [plan-driven-mode.md](references/plan-driven-mode.md). This is the fix for "completed one iteration and stopped" — the default lifecycle is single-task; plan-driven mode chains items.

1. **Phase −1 (normalize, once)** — read the plan + its authority chain; emit a frozen `docs/plan-queues/<name>.queue.md`. Graded extraction (latch tables/Cursor `todos[]`; semantic-infer prose deps); plan-native grain; resolve `dod_ref` across references; seed status from existing progress markers (resume).
2. **Checkpoint** — surface the frozen queue (item count, grain, deps, DoD sources, resume point) for user confirmation before chaining. Plan formats are heterogeneous (iteration-grain / coder-task / work-package), so this confirmation is non-negotiable. Resolve any **resolve-now Open Decision Points** here — `claim` refuses items with unresolved resolve-now ODPs (deferred ODPs re-surface at tail re-validation).
3. **Chain** — `plan_queue.py next-item` → `claim` → run steps 2–5 for that item's sub-scope → `complete`/`block`. Re-freeze a per-item sub-scope (master-blueprint AC subset or inline DoD) as the Phase-0 anchor. Do NOT report between items — one progress line only. At each `complete`, apply the **commit policy** (`loop_state.py init --commit`, default `auto-per-stage`: feature-branch commit per converged stage, no confirmation — overrides the usual "commit only when asked").
4. **Cross-item breaker** — `plan_queue.py check-breaker` (consecutive-item failure → suspend; total-items cap → hard-terminate; pending-but-stuck → stall). Composes with `loop_state.py`'s per-item breakers.
5. **Aggregate** — on plan exhaustion or breaker trip, `plan_queue.py aggregate` → one summary report (replaces the per-task report).

This is an **L3 semantic router over the L4 per-task kernel** — the plan interpretation has no objective oracle, so the frozen queue + checkpoint + revision channel + resume audit the semantic risk rather than eliminate it. See [plan-driven-mode.md](references/plan-driven-mode.md).

If the user specifies a particular phase (e.g., "write tests" or "only implement"), execute only that phase. Otherwise, run the full pipeline end-to-end.

## Quick Start

When invoked, execute these steps in order without waiting for user input between steps:

1. Analyze request → Identify independent subtasks
2. Pre-flight checks → Detect missing configs
3. Assign roles → Use [roles.md](references/roles.md) for mapping
4. Schedule & Execute → Concurrency-aware parallel execution (see [Concurrency Scheduling](#concurrency-scheduling))
5. Aggregate results → Resolve conflicts
6. Enter Convergent Fix Loop → iterate Tier 1 (automated checks) + Tier 2 (code review) until both pass clean — do not stop and wait for user input between iterations

## Aggregation & Recovery

After all parallel agents complete:

1. Merge results
   - Check all output files exist
   - Verify no orphan files or missing imports

2. Resolve conflicts
   - If agents modified the same file: prefer the result that passes tests
   - Shared files: manual merge, then validate

3. Convergent Fix Loop — immediately enter this loop after merging. Do not report partial results or wait for user input between iterations. Loop autonomously until convergence:

   > **Drive `loop_state` every inner round — inline mode is NOT exempt (ADR #39).** Whether the inner ring runs inline (orchestrator-direct, the trivial-edit / tight-coupling / skill-self-maintenance carve-out) or in a dispatched subagent, the orchestrator calls `bump-iteration` / `gate-fail` / `snapshot` / `record-outer` each round so the run record is truthful. Inline exempts WHERE the edit happens, not WHETHER the bookkeeping happens; otherwise `steps.inner` under-reports. The DoD signal stays the outer review (ADR #16); this is telemetry discipline, not a gate.

   Tier 1: Inner Ring — Fast Gate (deterministic, per-edit)

   The Fast Gate runs lint / type-check / unit tests. If the opt-in infrastructure is armed (see [install.md](references/install.md)), the cheap per-file checks also run automatically as a `tools/post-execute` listener (`fast_gate.py`, via the `solidforge-loop-gates` plugin) that emits a block on failure so the agent self-corrects next turn. Detect the project's toolchain, then run the appropriate commands:

   Web/Backend:
   - Type check (e.g. `tsc --noEmit`, `cargo check`, `go vet`, `mypy`)
   - Lint (e.g. `eslint`, `clippy`, `ruff`, `golangci-lint`)
   - Test suite (e.g. `vitest`, `cargo test`, `go test`, `pytest`)

   Apple Platforms (iOS/macOS/watchOS):
   - Build check: `xcodebuild -project X.xcodeproj -scheme Y -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build` (or `swift build` for SPM-only projects)
   - Lint: `swiftlint lint` (if configured), or `swift build -Xswiftc -strict-concurrency=complete` for Swift Concurrency validation
   - Test suite: `xcodebuild test -project X.xcodeproj -scheme Y -destination 'platform=iOS Simulator,name=iPhone 16 Pro' -resultBundlePath test-results.xcresult` (or `swift test` for SPM-only projects)
   - See [ios-patterns.md](references/ios-patterns.md) for full toolchain commands

   Python:
   - Dependency sync: `uv sync` (uv) / `poetry install` (Poetry) / `pip install -e ".[dev]"` (pip)
   - Type check: `mypy src/` or `pyright src/` (use whichever is configured in pyproject.toml)
   - Lint: `ruff check src/`
   - Format check: `ruff format --check src/`
   - Test suite: `pytest --tb=short -q`
   - See [python-patterns.md](references/python-patterns.md) for full Tier 1 validation sequence

   Rust:
   - Type check: `cargo check`
   - Format check: `cargo fmt --check` (per-file fast gate uses `rustfmt --check`)
   - Lint / concurrency baseline: `cargo clippy --all-targets` (architecture-contract gate)
   - Test suite: `cargo test`
   - See [rust-patterns.md](references/rust-patterns.md) for toolchain and the (thin) architecture-contract gate

   Java (JDK 17+):
   - Type check: `mvn -q compile` / `gradle compileJava` (javac is the type checker)
   - Format check: `google-java-format --dry-run --set-exit-if-changed` (fast gate)
   - Lint / package cycles: `checkstyle -c checkstyle.xml` + `jdeps --cyclic` (architecture-contract gate)
   - Test suite: `mvn test` / `gradle test`
   - See [java-patterns.md](references/java-patterns.md) for toolchain, parallel conflicts, and the (thin) architecture-contract gate

   Go:
   - Type check / build: `go build ./...` (the compiler is the type checker; rejects import cycles)
   - Format check: `gofmt -l` (fast gate — gates on NON-EMPTY stdout; `gofmt -l` exits 0 even when files need formatting)
   - Lint / layer rules: `go vet` + `golangci-lint run` (architecture-contract gate; depguard layer rules + the `internal/` compiler-enforced boundary)
   - Test suite + concurrency baseline: `go test -race ./...` (`-race` is the test-time data-race detector)
   - See [go-patterns.md](references/go-patterns.md) for toolchain, parallel conflicts, and the (strong) architecture-contract gate

   Web (JavaScript / TypeScript):
   - Type check: `tsc --noEmit` (TS; pure-JS needs a `tsconfig.json` with `allowJs`)
   - Lint: `eslint .` (fast gate runs per-file)
   - Cycles / layer boundaries: `depcruise --config .dependency-cruiser.cjs src` (architecture-contract gate)
   - Test suite: `vitest run` / `playwright test`
   - See [web-patterns.md](references/web-patterns.md) for detection, framework breadth (React/Vue/Svelte/Next/Nuxt/Express), JS-vs-TS, and the architecture-contract gate

   If any check fails: fix issues in priority order (type errors > lint > test failures), then restart from Tier 1. Do not proceed to the Architecture-Contract Gate while automated checks are red.

   Architecture-Contract Gate (deterministic, at the inner convergence point) — once the Fast Gate is clean, run the codable architecture contracts: circular dependencies, layer/dependency isolation, concurrency baseline (no sync-in-async / Sendable). Heavier, needs full context, so it runs once at convergence, not per edit. Scripts: `arch_contract_python.py` / `arch_contract_swift.py` / `arch_contract_web.py` / `arch_contract_rust.py` / `arch_contract_java.py` / `arch_contract_go.py` (see [arch-contracts.md](references/arch-contracts.md) and the per-platform L4 file for commands; Rust's gate is thinner — layer-direction is not deterministically enforceable in Rust and stays an outer-ring concern). Cross-ecosystem sibling gates run alongside: `arch_contract_deps.py` (secrets + dep vulns), `arch_contract_tests.py` (failing tests), and `arch_contract_api.py` (frontend↔backend API contract for mixed FE+BE repos). When a project arms an external design skill (Impeccable), its 44-rule detector is the design-fidelity gate (per-edit advisory hook + convergence `detect` sweep → 越权日志; see [external-skills.md](references/external-skills.md)). Detection is recursive (root OR nested subdir), so a mixed-layout repo gets every side gated; for a nested frontend/backend, point the per-language arch gate at the subdir. On any Blocker finding, fix in the inner ring and re-run — never enter the outer ring on a red architecture gate.

   Gate附加条件 (a green Exit Code alone is not a pass): new-code coverage ≥ threshold; tests marked skip/ignore/xfail do not count; suspect flaky tests re-run stably (fixed seeds, stabilized fixtures); the test set must not shrink relative to the Intent Blueprint (catches "delete the failing test").

   Tier 2: Outer Ring — AI Code Review (semantic quality)

   Spawn an independent reviewer subagent (prompt: `agents/code-reviewer.agent.md`) to review the final Diff against the Intent Blueprint and the L1 Constitution. Review all changed files for:
   - Correctness and edge cases
   - Security vulnerabilities
   - Performance regressions
   - Best practice adherence (uncodable L1 red lines: abstraction level, naming, emergent coupling)

   The reviewer performs the dual-line check and outputs structured findings WITH line numbers:
   - Semantic line: the items above.
   - Intent line: diff-to-blueprint — for each Core Use Case / AC, state satisfied | partially-satisfied | missing with file:line evidence; flag any value hardcoded to bypass a failing test.

   Context folding: pass the reviewer ONLY the final Diff + blueprint ref + L2 few-shot (golden path or cold-start) + a one-sentence folded inner summary (`loop_state.py summary`). Do NOT pass the inner-ring stderr trail.

   If issues found: fix by priority (security > correctness > performance > style), then restart from Tier 1 (the Fast Gate). Verdict dispatch: pass → converge; semantic issue → rewrite with line-numbered findings; intent drift → hard rollback (`snapshot.py restore`) + reverse-prompt injection; visual drift → advisory rewrite (or hard rollback under `enforcement: strict`); blueprint defect → Blueprint Revision Channel; `adversarial-stalemate` (different-family multi-round debate cap-hit, ADR #40) → escalate to human. See [convergent-loop.md](references/convergent-loop.md).

   different-family (different-family) additive outer ring (ADR #40, opt-in): for high-stakes items (ADR-level / security-correctness-sensitive / same-family low-confidence), the orchestrator MAY spawn `hetero_review.py` as an adversarial second opinion on a different model family, ALONGSIDE the same-family `code-reviewer` (which stays primary). Default items pay zero added cost (different-family does not run). The multi-round debate + cap + reconciliation live in [convergent-loop.md](references/convergent-loop.md) § different-family adversarial review; the per-stage policy in [model-routing.md](references/model-routing.md).

   Done — inner ring (Fast Gate + Architecture-Contract Gate + 附加条件) and outer ring both pass clean. Report results to the user.

   Circuit breaker (state machine) — the loop uses a state-machine breaker, not a flat iteration count: Thrashing (same root-cause fingerprint ≥ N=3) → escalate to the outer Reviewer (the only inner→outer exception); inner iteration ≥ M=8 → degrade (split/narrow); M reached + budget near exhaustion → suspend for human review; token/time/cost budget exhausted, or total steps ≥ step_cap_S (default 200) → global hard-terminate (output best snapshot + diagnosis, stop). Note: wall-clock confounds provider throughput — time is a cost/hang guard only; the step cap is the provider-independent limit, and a resource-cap termination is `inconclusive` on capability, not a failure (see [convergent-loop.md](references/convergent-loop.md) § State Machine, ADR #6/#13). State lives in `loop-state.json`; query with `loop_state.py check-breakers`. At any terminal status, emit a normalized run record (`loop_state.py run-record` → `.solidforge/loop/runs/<task>-<stamp>.json`) whose `l4_assessment` block is the instrumented form of the [maturity.md](references/maturity.md) rubric. See [convergent-loop.md](references/convergent-loop.md) § Event log + run record.

## Pre-flight Checks

Before assigning roles, check project status:

### Graphiti Memory Config

1. Check if `.graphiti.json` exists in project root
2. If missing and project has source files (Cargo.toml, package.json, go.mod, Package.swift, pom.xml, build.gradle, *.xcodeproj, Podfile, etc.):
   - Inform user about missing config
   - Suggest invoking `graphiti-config-generator` to create it
   - Proceed only after user confirmation or if explicitly not needed
3. If `.graphiti.json` exists but Graphiti MCP is unreachable, skip memory operations silently — do not block the workflow on memory failures

### Apple Platform Projects

For iOS/macOS/watchOS projects, detect the toolchain:

| File Found | Project Type | Build Tool | Test Tool |
| --- | --- | --- | --- |
| `*.xcodeproj` / `*.xcworkspace` | Xcode project | `xcodebuild` | `xcodebuild test` |
| `Package.swift` (no `.xcodeproj`) | SPM only | `swift build` | `swift test` |
| `Package.swift` + `.xcodeproj` | SPM + Xcode (XcodeGen/Tuist) | `xcodebuild` | `xcodebuild test` |
| `Podfile` | CocoaPods | `xcodebuild -workspace` | `xcodebuild test` |
| `project.yml` / `Project.swift` | XcodeGen / Tuist | generate + `xcodebuild` | generate + `xcodebuild test` |

For Xcode projects, check for `.xcodeproj/project.pbxproj` merge strategy (see [ios-patterns.md](references/ios-patterns.md)). Prefer XcodeGen or Tuist projects for parallel development — they eliminate pbxproj merge conflicts by design.

### Python Projects

For Python projects, detect the package manager and toolchain:

| File Found | Package Manager | Install Command | Test Runner |
| --- | --- | --- | --- |
| `pyproject.toml` + `uv.lock` | uv | `uv sync` | `uv run pytest` |
| `pyproject.toml` + `poetry.lock` | Poetry | `poetry install` | `poetry run pytest` |
| `pyproject.toml` (no lock file) | pip | `pip install -e .` | `pytest` |
| `requirements.txt` | pip | `pip install -r requirements.txt` | `pytest` |
| `Pipfile` | Pipenv | `pipenv install` | `pipenv run pytest` |

Check for virtual environment: verify `VIRTUAL_ENV` env var or `.venv/` directory. For uv-managed projects, `uv run` handles environment automatically.

For full toolchain detection, conflict scenarios, and framework-specific patterns, see [python-patterns.md](references/python-patterns.md).

### Other Pre-flight Items

- Verify project dependencies are installed
- Check for existing test infrastructure
- For iOS: verify at least one simulator runtime is available (`xcrun simctl list runtimes`)

## Role Mapping

For role definitions, trigger keywords, and agent assignments, see [role-agent-mapping.md](references/role-agent-mapping.md).

## Fail-Fast Testing Integration

The parallel-dev skill integrates with `@playwright-reporter/fail-fast` for intelligent test execution with automatic halting. The orchestrator delegates fail-fast work to a subagent with the `agents/playwright-test-healer.agent.md` prompt; it does not run the reporter directly.

Thresholds by project group:

| Project | Threshold | Rationale |
| --- | --- | --- |
| auth | 20% | Authentication failures affect all tests |
| config | 30% | Configuration changes impact multiple features |
| custom | 40% | Custom actions are relatively independent |

Configuration and API details: [fail-fast.md](references/fail-fast.md)

For iOS/XCUITest projects, `@playwright-reporter/fail-fast` is not applicable. Instead, use `xcodebuild test` exit codes and `.xcresult` bundle analysis to detect failure patterns. Apply the same threshold rationale: if >30% of XCUITest cases fail, halt and address root causes before proceeding. Parse test results from the `.xcresult` bundle using `xcrun xcresulttool get --path result.xcresult --format json`.

## Parallel Execution

### Parallel Decision

- Can parallelize: independent files/modules, test + implementation (TDD), frontend + backend
- Must be sequential: shared dependencies, architectural decisions, config affecting multiple components
- Decision tree: [parallel-patterns.md](references/parallel-patterns.md)

## Concurrency Scheduling

Model service providers impose concurrency limits (e.g., max 5 simultaneous requests). Rather than launching all tasks at once and risking rate-limit errors, use a slot-based scheduler that dynamically fills available capacity.

### Parameters

- `max_concurrency`: Maximum simultaneous agent calls. Default: 5. Override when the user specifies a different limit or when prior runs hit provider throttling.
- Per-task `files_touched`: List of file paths the task will read or modify, kept in the orchestrator's task ledger (todo list). Used for conflict detection.

### Scheduling Loop

The DeepSeek Harness execution model is turn-batched: multiple `subagent` tool calls issued in one message run in parallel and return results together. The scheduling loop operates per-turn:

```markdown
1. Identify all subtasks and their `files_touched`.
2. Prepare one subagent dispatch per subtask (prompt = role file + task; status: pending).
3. While pending or running tasks remain:
   a. available_slots = max_concurrency - count(running tasks)
   b. For each pending task (in priority order):
      - If available_slots <= 0: stop.
      - If task.files_touched intersects with any running task.files_touched: skip (blocked).
      - Otherwise: launch subagent, set task status to in_progress, decrement available_slots.
   c. Wait for running subagents to return results.
   d. For each completed subagent: set task status to completed (or handle failure).
   e. Repeat from step 3a.
```

### Conflict Detection

Two tasks conflict when both touch the same file or shared resource (database migration, config file, shared module). Conflicting tasks must not run simultaneously -- schedule them sequentially in the same slot.

Sequential ≠ direct: conflict-serializable tasks are still dispatched as subagents, one at a time (dispatch Coder A, await return, dispatch Coder B) — never run concurrently, yet each keeps its inner-ring churn out of the orchestrator's context. The orchestrator executes a task directly only as an exception (trivial single edit, or tight-coupling continuity). Rationale: [parallel-patterns.md](references/parallel-patterns.md) and ADR #14 in [design-decisions.md](references/design-decisions.md).

### Error Handling

When an agent fails (error, timeout, unexpected output):

- Free its slot immediately.
- Do not auto-retry -- report the failure to the user.
- Re-evaluate pending tasks: tasks that depended on the failed task's output remain blocked; independent tasks can proceed.

### Integration Points

- Feature Development: Phase 5 (GREEN) uses this scheduler -- see [feature-dev.md](references/feature-dev.md).
- Full algorithm and decision tree: See [parallel-patterns.md](references/parallel-patterns.md).

## TDD Examples

### Multi-Component

RED phase (sequential -- tests define the interface contracts):

```text
subagent(tester)        : Write tests for AppHeader → files: [AppHeader.ts, AppHeader.test.ts]
subagent(tester)        : Write tests for AppSidebar → files: [AppSidebar.ts, AppSidebar.test.ts]
subagent(tester)        : Write tests for AppMain → files: [AppMain.ts, AppMain.test.ts]
```

GREEN phase (scheduled -- no file overlaps, all can run in parallel):

```text
subagent(frontend-developer): Implement AppHeader → files: [AppHeader.ts]
subagent(frontend-developer): Implement AppSidebar → files: [AppSidebar.ts]
subagent(frontend-developer): Implement AppMain → files: [AppMain.ts]
```

### Full-Stack

RED phase:

```text
subagent(tester)        : Write API tests → files: [auth.api.test.ts]
subagent(tester)        : Write UI tests → files: [login.ui.test.ts]
```

GREEN phase (backend and frontend are independent):

```text
subagent(backend-developer): Create API → files: [src/auth/]
subagent(frontend-developer): Create UI → files: [src/components/Login.vue]
```

### iOS SwiftUI

RED phase (sequential — tests define the protocol/interface contracts):

```text
subagent(ios-tester): Write tests for LoginViewModel → files: [LoginViewModel.swift, LoginViewModelTests.swift], prompt: "Swift Testing @Test for @Observable ViewModel"
subagent(ios-tester): Write tests for UserService → files: [UserService.swift, UserServiceTests.swift], prompt: "Swift Testing @Test for actor service"
subagent(ios-tester): Write XCUITest for login flow → files: [LoginView.swift, LoginUITests.swift], prompt: "XCUITest with accessibility identifiers"
```

GREEN phase (scheduled — independent SwiftUI views/components):

```text
subagent(ios-developer): Implement LoginViewModel → files: [LoginViewModel.swift], prompt: "iOS SwiftUI developer — implement @Observable LoginViewModel with @MainActor"
subagent(ios-developer): Implement LoginView → files: [LoginView.swift], prompt: "iOS SwiftUI developer — implement LoginView using @Observable ViewModel"
subagent(ios-developer): Implement UserService actor → files: [UserService.swift], prompt: "iOS Swift developer, Swift Concurrency expert — implement Sendable-safe UserService actor"
```

Note: For iOS, use `agents/ios-developer.agent.md` for implementation (SwiftUI/UIKit/SPM) and `agents/ios-tester.agent.md` for XCUITest UI/E2E + `.xcresult` analysis; XCTest unit tests ride with the implementer. Prefer `@Observable` over `ObservableObject` for new ViewModels. Use Swift Testing (`@Test` / `#expect`) for new unit tests unless the test is UI automation (XCUITest) or performance benchmark — those remain with XCTest. See [role-agent-mapping.md](references/role-agent-mapping.md) for iOS trigger keywords and prompt templates.

### Python (FastAPI example)

RED phase (sequential — tests define the API contracts via TestClient):

```text
subagent(tester): Write tests for user router → files: [app/api/v1/users.py, tests/test_api/test_users.py], prompt: "pytest + FastAPI TestClient, test CRUD endpoints"
subagent(tester): Write tests for order router → files: [app/api/v1/orders.py, tests/test_api/test_orders.py], prompt: "pytest + FastAPI TestClient, test CRUD endpoints"
```

GREEN phase (scheduled — independent routers, no shared files):

```text
subagent(backend-developer): Implement user router + schemas → files: [app/api/v1/users.py, app/schemas/user.py]
subagent(backend-developer): Implement order router + schemas → files: [app/api/v1/orders.py, app/schemas/order.py]
```

Note: For Python, routers/blueprints/apps are natural parallel boundaries. Shared files that require serialization: pyproject.toml (dependency changes), app/main.py (router registration), conftest.py (shared fixtures), and migration directories. See [python-patterns.md](references/python-patterns.md) for Django and Flask patterns.

## Workflows

1. Determine the task type:
   - New feature? → [Feature Development](references/feature-dev.md)
   - Bug report? → [Bug Fix](references/bug-fix.md)
   - Code cleanup? → [Refactoring](references/refactoring.md)
   - Browser testing? → [E2E Testing](references/e2e-testing.md)
   - iOS native UI testing (XCUITest)? → [ios-patterns.md](references/ios-patterns.md#apple-platform-testing)
   - Docs update? → [Documentation](references/documentation.md)

## Reference Files

- [role-agent-mapping.md](references/role-agent-mapping.md) - Role definitions, trigger keywords, and agent mapping
- [memory-protocol.md](references/memory-protocol.md) - Graphiti memory integration
- [convergent-loop.md](references/convergent-loop.md) - Dual-ring convergence loop: state machine, context folding, reviewer prompt, breaker thresholds
- [orchestration-layers.md](references/orchestration-layers.md) - Convergence loop vs `ultracode`/Dynamic Workflows vs `/loop`: differentiator, worked scenarios, when each fits (ADRs #32, #33)
- [intent-blueprint.md](references/intent-blueprint.md) - Intent Blueprint format, freeze, read-only guard, revision channel
- [scope.md](references/scope.md) - Skill scope boundary (entry condition, deliverable, out-of-scope) + misuse catalog with routing hints
- [plan-driven-mode.md](references/plan-driven-mode.md) - Multi-item plan chaining: semantic plan normalizer, frozen plan-queue, cross-item breaker, resume
- [arch-contracts.md](references/arch-contracts.md) - Architecture-contract gate (越权日志 schema, L1 codable/uncodable split, per-platform tool pointers)
- [golden-paths.md](references/golden-paths.md) - Golden-path registry (@Agent-Golden-Ref), quarterly expiry, smell filter, L1/L2 injection
- [install.md](references/install.md) - Arming the deterministic infrastructure (gate plugins, scripts, templates)
- [host-routing.md](references/host-routing.md) - Optional host-project AGENTS.md routing snippet surfaced by the arm-tools command (bc/pd/csr self-route via Scope Guards; the csr explicit-invocation gap)
- [extending.md](references/extending.md) - How to add a new language and maintain the convergence-loop infra (per-language formula, disconnect checklist)
- [external-skills.md](references/external-skills.md) - External-skill integration contract (black-box skills like Impeccable: DESIGN.md anchor, detector/hook gate, command→seam map)
- [hooks-reference.md](references/hooks-reference.md) - DSH tools/pre-execute + tools/post-execute gate listeners + per-gate contract (read before editing infra/hooks/ or the loop-gates plugin)
- [design-decisions.md](references/design-decisions.md) - ADR log: the non-obvious design choices and the alternatives rejected
- [maturity.md](references/maturity.md) - L1–L4 maturity yardstick, this skill's self-assessment (L4 architecture / L3.5 operational), and the flow-control self-review gate
- [ast-grep-patterns.md](references/ast-grep-patterns.md) - Automated code review patterns (Vue, TypeScript, Rust, Swift, Python)
- [ios-patterns.md](references/ios-patterns.md) - iOS/Apple platform toolchain, Simulator management, Code Signing, pbxproj conflicts, Swift Concurrency, Instruments profiling, and Apple platform testing
- [python-patterns.md](references/python-patterns.md) - Python project detection, toolchain commands, testing strategy, dependency management, parallel conflict scenarios, framework patterns (FastAPI/Django/Flask), error recovery
- [rust-patterns.md](references/rust-patterns.md) - Rust/Cargo project detection, toolchain commands, parallel conflict scenarios (Cargo.lock/Cargo.toml), and the (thin) architecture-contract gate
- [java-patterns.md](references/java-patterns.md) - Java/Maven/Gradle (JDK 17+) project detection, toolchain commands, parallel conflict scenarios (pom.xml/build.gradle), and the (thin) architecture-contract gate (checkstyle + jdeps)
- [go-patterns.md](references/go-patterns.md) - Go (go.mod / workspace) project detection, toolchain commands, parallel conflict scenarios (go.mod/go.sum), and the (strong) architecture-contract gate (go build + go vet + golangci-lint depguard + `internal/` compiler boundary)
- [web-patterns.md](references/web-patterns.md) - Web (JavaScript/TypeScript) on browser + Node.js: project detection, language breadth (TS first-class, JS opt-in type-check), framework/runtime patterns (React/Vue/Svelte/Next/Nuxt/Express), parallel conflicts, and the architecture-contract gate
- [e2e-patterns.md](references/e2e-patterns.md) - E2E testing best practices (Playwright/Web only — for iOS E2E see [ios-patterns.md](references/ios-patterns.md#apple-platform-testing))
- [fail-fast.md](references/fail-fast.md) - Fail-fast reporter configuration (Web/Playwright only — for iOS equivalent see [SKILL.md Fail-Fast section](#fail-fast-testing-integration))

## Structural Convention: General vs. Domain Separation

This skill serves multiple platforms (Web, iOS, Rust, Go, Python, etc.). When editing any file in this skill, follow the layer model below. Violating it causes domain-specific content to leak into general-purpose files, making the skill harder to maintain and potentially confusing for users on other platforms.

### Layer Model

| Layer | Files | Content Rule |
| --- | --- | --- |
| L1 Universal entry | `SKILL.md` | Platform-agnostic only. Platform-specific content allowed only as conditional branches (`Apple Platforms:`, `Web/Backend:`) that are brief and route to L4 files. |
| L2 General workflows | `feature-dev.md`, `bug-fix.md`, `refactoring.md`, `e2e-testing.md` | Platform-agnostic workflow definition. Platform-specific sections allowed as clearly labeled conditional blocks (`For iOS:`, `iOS RED Phase:`) that contain instructions/examples, not deep reference material. Deep detail → L4 pointer. |
| L3 General support | `parallel-patterns.md`, `role-agent-mapping.md`, `memory-protocol.md`, `ast-grep-patterns.md`, `convergent-loop.md`, `orchestration-layers.md`, `intent-blueprint.md`, `arch-contracts.md`, `golden-paths.md`, `install.md`, `extending.md`, `hooks-reference.md`, `design-decisions.md`, `maturity.md`, `scope.md`, `plan-driven-mode.md`, `external-skills.md` | Platform-agnostic algorithms and mappings. Platform-specific instances (conflict matrix entries, role triggers, AST patterns) allowed inline. Platform-specific deep content (strategy, error recovery, modularization) → brief pointer to L4. |
| L4 Domain reference | `ios-patterns.md`, `python-patterns.md`, `rust-patterns.md`, `java-patterns.md`, `go-patterns.md`, `web-patterns.md`, `e2e-patterns.md`, `fail-fast.md` | All domain-specific detail lives here. Each file covers exactly one platform domain. Other layers point here; they do not duplicate. |

### The Test

Before adding or editing platform-specific content in a file, ask: "If a user on a different platform reads this file, would this content be noise?"

- If yes → the content belongs in L4. Replace with a one- or two-line pointer to the appropriate L4 file.
- If no (it's a conditional branch the user would skip, or a comparative example) → acceptable in L2/L3 with clear labeling.

### Extension

When adding support for a new platform domain (e.g., Android, embedded Rust), the rule is: **register it, then verify the loading chain** — do not scatter edits and hope.

1. Add an entry to `infra/test/platforms.json` (the single source of truth: each language declares its marker file, extension, L4 file, arch script, arch config, install token, and the decision-point markers).
2. Create the files the entry implies: the L4 `<lang>-patterns.md`, `infra/scripts/arch_contract_<lang>.py`, the template config, the `detect_toolchain`/`fast_gate`/`arm.py` wiring.
3. Route the language at every decision-point doc the registry declares (`parallel-patterns.md`, `arch-contracts.md`, `role-agent-mapping.md`) so a model following progressive disclosure can load the language's content at the point of need — not just from some doc.
4. Run `python3 infra/test/disconnect_check.py`. It is the mandatory gate: it reads `platforms.json` and verifies every structural link AND the loading chain (no 断裂), with actionable per-file guidance. The checker never needs editing for a new language — only the registry does. A language is not correctly added/updated until this passes. Full guide: [extending.md](references/extending.md).

The same gate applies when updating an existing language (e.g., adding a tool): re-run it to confirm the loading chain still holds end to end.

## Deterministic Infrastructure (Opt-In)

The convergence loop's deterministic gates (fast-gate listener, blueprint read-only guard, breaker counters, architecture-contract scripts, snapshot/rollback) ship inside the skill at `infra/` (running from the preset root — they are NOT copied into the target project) and fire only when the `solidforge-loop-gates` plugin is running; the project-side configs are armed OPT-IN via arm-tools. Without them the loop still runs but gates are advisory. Arming and gate status: [install.md](references/install.md). Loop semantics: [convergent-loop.md](references/convergent-loop.md).

## Optional Dependencies

- @playwright-reporter/fail-fast: `npm install @playwright-reporter/fail-fast` — Required only for fail-fast test reporting
- ast-grep: `npm install @ast-grep/cli` — Required only for automated code review patterns
