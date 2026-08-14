# E2E Testing Workflow (TDD)

TDD requirement: E2E tests are written before feature implementation.

## Project Type Detection (ALWAYS RUN FIRST)

Before executing any phase, detect the project type to route to the correct testing framework:

| Project Type | Detected By | Testing Framework | Go To |
| --- | --- | --- | --- |
| Web (Vue/React) | `package.json` with Playwright, no `.xcodeproj` | Playwright | Continue below |
| iOS (Swift/SwiftUI) | `*.xcodeproj` or `Package.swift` | XCUITest + XCTest | See [ios-patterns.md § Apple Platform Testing](ios-patterns.md#apple-platform-testing) for the complete XCUITest workflow, Simulator management, and lifecycle testing checklist |
| Hybrid (Web + iOS) | Both present | Playwright + XCUITest | Treat as two separate E2E test runs — route each to its respective workflow |

When the project is iOS, skip the rest of this file and use `ios-patterns.md` directly. This file describes the Web Playwright workflow only.

## Web E2E Testing (Playwright)

MCP Requirement: This workflow uses Playwright MCP tools.

Fallback: If Playwright MCP is not available, fall back to `tester` agent.

## Contents

- [Phase 1: Environment Verification (Sequential)](#phase-1-environment-verification-sequential)
- [Phase 2: Seed Test Setup (Sequential)](#phase-2-seed-test-setup-sequential)
- [Phase 3: Planning with Real Browser (Sequential)](#phase-3-planning-with-real-browser-sequential)
- [Phase 4: Test Generation (Sequential)](#phase-4-test-generation-sequential)
- [Phase 5: Feature Implementation (Parallel when possible)](#phase-5-feature-implementation-parallel-when-possible)
- [Phase 6: Test Execution & Healing (Sequential)](#phase-6-test-execution--healing-sequential)
  - [Debugging (When Tests Fail)](#debugging-when-tests-fail)
- [Example: E2E Test for Login Feature](#example-e2e-test-for-login-feature)
- [Test Coverage Checklist](#test-coverage-checklist)

## Phase 1: Environment Verification (Sequential)

Tasks:

- Verify Docker environment is running (`make dev-start`)
- Verify backend API is accessible
- Verify test URL is correct

Validation:

```bash
curl -I http://localhost/dianginx/
```

## Phase 2: Seed Test Setup (Sequential)

Prerequisite:

- Ensure `tests/seed.spec.ts` exists with proper setup

Seed test requirements:

- Provide `page` context for all tests
- Global setup, project dependencies, fixtures
- Used as template for generated tests

## Phase 3: Planning with Real Browser (Sequential)

Role: E2E Test Engineer → `playwright-test-planner`

Tasks:

- Launch browser and explore application UI
- Identify interactive elements and user flows
- Create comprehensive test plan including:
  - Happy path scenarios
  - Error scenarios
  - Persistence verification scenarios

```text
Task(playwright-test-planner): Create test plan for [feature]
```

Output: Test plan markdown file

## Phase 4: Test Generation (Sequential)

Role: E2E Test Engineer → `playwright-test-generator`

Tasks:

- Execute each test step in real browser
- Generate Playwright test code
- Save tests to appropriate files

```text
Task(playwright-test-generator): Generate tests from [test-plan-file]
```

Requirements for generated tests:

1. Real backend only -- use the Docker environment, never mock data.
2. Persistence verification -- test that saved data survives a page reload.
3. Error scenarios -- cover invalid input, permission denied, network errors.
4. No `sleep()` or `waitForTimeout()` -- Playwright has auto-waiting; explicit sleeps indicate a bug in the test or the app.
5. Timeout limit: 30 seconds maximum per test.

Output: Playwright test files

## Phase 5: Feature Implementation (Parallel when possible)

Role: Developer → `frontend-developer` or `backend-developer`

GREEN Phase: Implement feature to pass E2E tests

## Phase 6: Test Execution & Healing (Sequential)

Role: E2E Test Engineer → `playwright-test-healer`

Tasks:

- Check for fail-fast configuration
- Run all E2E tests with fail-fast monitoring
- Debug and fix failing tests
- Verify fixes

```text
Task(playwright-test-healer): Run and fix tests for [test-file]
```

### Fail-Fast Integration

When using `@playwright-reporter/fail-fast`:

1. Load fail-fast configuration from `fail-fast.config.json` or `fail-fast.config.yaml`
2. Initialize FailFastAgent with project config
3. Run tests with real-time monitoring
4. If halted (>threshold% failures), stop and address root causes first

```typescript
import { FailFastAgent } from '@playwright-reporter/fail-fast/agent'

const agent = new FailFastAgent({
  config: './fail-fast.config.json',
  onHalt: async (event) => {
    // Switch to fixing common failures across multiple tests
    console.log(`Halted: ${event.failureRate}% > ${event.threshold}%`)
  }
})

const result = await agent.runTests({ testDir: './tests/e2e' })
if (result.halted) {
  // Address root causes before individual test healing
  return
}
```

### Project-Specific Thresholds

- auth: 20% threshold (authentication failures affect all tests)
- config: 30% threshold (configuration changes impact multiple features)
- custom: 40% threshold (custom actions are relatively independent)

## Failure Interruption Principle

When test failure rate exceeds threshold:

1. Stop running additional tests.
2. Identify root causes (common failures across multiple tests).
3. Fix root causes first.
4. Resume testing after fixes.

Continuing to run tests when a systemic issue is present wastes time and produces uninformative failures.

Output: Working test suite

### Debugging (When Tests Fail)

Reference: [e2e-patterns.md](e2e-patterns.md) for detailed patterns.

### Root Cause Checklist

- [ ] API returns data? (verify with curl)
- [ ] API response format correct?
- [ ] Frontend calls data loader?
- [ ] Frontend parses response correctly?
- [ ] Is it test issue or app bug?

A slow test usually indicates an app bug, not a test issue.

If debug reveals test issue → return to Phase 4, fix test, re-run. If debug reveals app issue → document and loop.

## Example: E2E Test for Login Feature

Request: "Create E2E tests for login feature"

Sequential Execution:

```text
Step 1: Environment Verification
- Verify Docker environment is running

Step 2: Seed Test Setup
- Ensure tests/seed.spec.ts exists

Step 3: Planning (RED phase)
Task(playwright-test-planner): Create test plan for login feature

Step 4: Test Generation (RED phase)
Task(playwright-test-generator): Generate login tests from plan

Step 5: Implementation (GREEN phase)
Task(frontend-developer): Implement login page to pass tests

Step 6: Test Execution & Healing
Task(playwright-test-healer): Run and fix failing login tests
```

Output:

- `tests/e2e/login.spec.ts` - Playwright test file
- Test plan documentation
- Implemented login feature

## Test Coverage Checklist

Every E2E test must include:

- [ ] Happy path (normal flow)
- [ ] Error scenarios (invalid input, etc.)
- [ ] Persistence verification (save, reload, verify)
- [ ] Real backend (no mocks)
- [ ] No `sleep()` calls
- [ ] Timeout ≤ 30 seconds
