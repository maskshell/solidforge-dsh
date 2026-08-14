# E2E Testing Patterns

Practical patterns for Playwright E2E tests (Web only). Complements [e2e-testing.md](e2e-testing.md).

iOS projects: Skip this file. For XCUITest patterns, simulator management, lifecycle testing, and the Apple platform test checklist, see [ios-patterns.md § Apple Platform Testing](ios-patterns.md#apple-platform-testing).

## Contents

- [Core Rules](#core-rules)
  - [Authentication: API First](#authentication-api-first)
  - [Credentials: Environment Variables](#credentials-environment-variables)
  - [State Restoration](#state-restoration)
- [Timeout Strategy](#timeout-strategy)
- [Anti-Patterns](#anti-patterns)
- [Debug Flow](#debug-flow)
- [Selector Priority](#selector-priority)
- [Test Execution Strategy](#test-execution-strategy)
  - [Failure Interruption Principle](#failure-interruption-principle)
- [Wait Strategy](#wait-strategy)

## Core Rules

### Authentication: API First

```typescript
// ✅ Fast: 3-5s saved per test
test.beforeEach(async ({ page, context }) => {
  await authenticateViaAPI(context)
  await page.goto(baseURL)
})

// ❌ Never use UI login in tests
```

### Credentials: Environment Variables

```typescript
const { username, password } = getTestCredentials()  // ✅
// ❌ Never hardcode: 'admin', 'password123'
```

### State Restoration

```typescript
let changedData: string | null = null

test.afterEach(async ({ page }) => {
  if (changedData) {
    await restoreState(page, changedData)
    changedData = null
  }
  // ❌ Never: catch (e) { console.log(e) }  // Silent failure pollutes tests
})
```

## Timeout Strategy

| Operation | Timeout | Rationale |
| --- | --- | --- |
| Element visible | 2000ms | Normal UI |
| Dialog/animation | 2000ms | With transition |
| Cleanup | 500ms | Fast fail |
| API call | 5000ms | Network tolerance |
| Single test | 15000ms | Max limit |

## Anti-Patterns

| Pattern | Problem | Fix |
| --- | --- | --- |
| 40-line defensive code | Over-engineering | Simple assertions |
| `reload()` then `goto()` | Redundant | `reload()` only |
| `Promise.race` with `.catch(() => null)` | Silent failure | Verify at least one succeeds |
| `beforeAll` auth | Page mismatch | Use `beforeEach` |
| `waitForTimeout()` | Flaky | Proper assertions |

## Debug Flow

```text
Test slow/timeout?
├─ curl API → returns data?
├─ Create debug test → console errors?
└─ Root cause: test issue or app bug?
```

Key insight: Slow test often = app bug, not test issue

## Selector Priority

1. `getByRole('button', { name: 'Submit' })` — Semantic
2. `getByText('Submit')` — Text content
3. `locator('button:has-text("Submit")')` — CSS + text
4. `locator('.submit-btn')` — Class
5. `locator('#submit')` — ID
6. `locator('div > button:nth-child(2)')` — Structure (last resort)

## Test Execution Strategy

### Failure Interruption Principle

When a group of E2E tests has a significant failure rate (>30%), immediately stop testing, fix the issues, then resume.

Applicable scenarios:

- Running a group of E2E tests (e.g., auth group, config group, custom action group)
- Multiple consecutive failures within the same test group
- Failure rate exceeds 30% threshold

Golden Ratio Thresholds:

See [fail-fast.md](fail-fast.md) for recommended thresholds.

Why interrupt:

1. Save time - Avoid wasting precious E2E test time on tests destined to fail
2. Fast feedback - Identify and fix root causes early, not accumulating errors
3. Avoid test noise - Prevent连锁 failures from early failures
4. Improve efficiency - Focus on core issues rather than blindly fixing symptoms

Example:

```bash
# ✅ Correct: Stop when failure rate > 30%
npm run test:e2e
# Fail 7/20 (35%) > 30%, stop immediately
# Fix issues → rerun
npm run test:e2e

# ❌ Wrong: Blindly run all tests, waste 2 hours
npm run test:e2e
# Find 15/20 tests failing, continue waiting...
```

理论基础: This principle aligns with the "Fail Fast" principle in software engineering, a mature testing strategy best practice.

---

## Wait Strategy

```typescript
// ✅ Playwright auto-waiting
await expect(element).toBeVisible()
await expect(element).toHaveText('Expected')

// ❌ Never
await page.waitForTimeout(1000)
```

> The Web architecture-contract gate (dependency-cruiser + eslint concurrency baseline) has moved to [web-patterns.md](web-patterns.md) → Architecture-Contract Gate (Web / TypeScript).
> This file is now Playwright/E2E-specific.
