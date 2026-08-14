# Fail-Fast Reporter Configuration

Configure `@playwright-reporter/fail-fast` for intelligent test execution with automatic halting. Web/Playwright only.

iOS/XCUITest projects: Skip this file. The Playwright fail-fast reporter does not apply to XCUITest. For iOS, use `xcodebuild test` exit codes and `.xcresult` bundle analysis to detect failure patterns. Parse test results with `xcrun xcresulttool get --path result.xcresult --format json`. Apply the same threshold rationale: halt if >30% failure rate. See [ios-patterns.md](ios-patterns.md) for the full XCUITest workflow.

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration Options](#configuration-options)
- [Recommended Thresholds](#recommended-thresholds)
- [Environment Variables](#environment-variables)
- [Detection Strategies](#detection-strategies)
- [Project Configuration Examples](#project-configuration-examples)
- [YAML Configuration](#yaml-configuration)
- [Programmatic API](#programmatic-api)
- [Output Example](#output-example)
- [Best Practices](#best-practices)
- [Migration Guide](#migration-guide)
- [Troubleshooting](#troubleshooting)
- [Further Reading](#further-reading)

## Installation

```bash
npm install @playwright-reporter/fail-fast
```

## Quick Start

### 1. Create Configuration File

```json
// fail-fast.config.json
{
  "threshold": 30,
  "minTests": 5,
  "haltOnThreshold": true,
  "projects": {
    "auth": { "threshold": 20, "patterns": ["**/auth/**"] },
    "config": { "threshold": 30, "patterns": ["**/config/**"] },
    "custom": { "threshold": 40, "patterns": ["**/custom/**"] }
  }
}
```

### 2. Update Playwright Config

```typescript
import { FailFastReporter } from '@playwright-reporter/fail-fast'

export default defineConfig({
  reporter: [[new FailFastReporter({ configPath: './fail-fast.config.json' })]]
})
```

### 3. Run Tests

```bash
npx playwright test
FAIL_FAST_THRESHOLD=25 npx playwright test
```

## Configuration Options

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `threshold` | number | `30` | Failure threshold (0-100) |
| `minTests` | number | `5` | Minimum tests before applying threshold |
| `haltOnThreshold` | boolean | `true` | Halt when threshold exceeded |
| `projects` | object | `{}` | Project-specific configurations |

## Recommended Thresholds

| Project Type | Threshold | Rationale |
| --- | --- | --- |
| Authentication | 20% | Affects all dependent tests |
| Configuration | 30% | Impacts multiple features |
| Custom Actions | 40% | Relatively independent |
| UI Components | 35% | May have flaky selectors |

## Environment Variables

| Variable | Description |
| --- | --- |
| `FAIL_FAST_THRESHOLD` | Override global threshold |
| `FAIL_FAST_MIN_TESTS` | Override minimum tests |
| `FAIL_FAST_CONFIG` | Path to config file |

## Detection Strategies

```json
{
  "detection": {
    "strategy": "pattern-matcher",
    "fallbackThreshold": 30,
    "autoDetect": true
  }
}
```

Available Strategies:

- `pattern-matcher`: Match test file paths against glob patterns
- `metadata`: Read from test file comments
- `custom`: User-defined detection logic

## Project Configuration Examples

### Pattern-Based

```json
{
  "projects": {
    "auth": {
      "threshold": 20,
      "patterns": ["**/auth/**", "**/*-auth.spec.ts", "US-02-*"],
      "minTests": 3
    }
  }
}
```

### Metadata-Based

```typescript
/**
 * @fail-fast-project: auth
 * @fail-fast-threshold: 20
 */
test.describe('Authentication', () => {
  // tests...
})
```

## YAML Configuration

```yaml
# fail-fast.config.yaml
threshold: 30
minTests: 5
haltOnThreshold: true

projects:
  auth:
    threshold: 20
    patterns:
      - "**/auth/**"
      - "US-02-*"
    minTests: 3

detection:
  strategy: pattern-matcher
  fallbackThreshold: 30
```

## Programmatic API

### Agent API (for AI agents)

```typescript
import { FailFastAgent } from '@playwright-reporter/fail-fast/agent'

const agent = new FailFastAgent({
  config: './fail-fast.config.json',
  onHalt: async (event) => {
    await handleHighFailureRate(event)
  }
})

const result = await agent.runTests({ testDir: './tests/e2e', project: 'auth' })

if (result.halted) {
  console.log(`Tests halted at ${result.failureRate}% failure rate`)
}
```

### Reporter API

```typescript
new FailFastReporter({
  threshold: 30,
  minTests: 5,
  onHalt: async (event) => {
    console.log(`Halted: ${event.reason}`)
  }
})
```

## Output Example

```text
=========================================
  Fail-Fast Reporter
=========================================

Project:   auth
Threshold: 20%
Halt when: > 20% failures after 3+ tests

[auth] RUN   5/10 tests | 4 passed | 1 failed | 20% rate

[HALT] Failure rate 20% exceeds threshold 20%
[HALT] Completed: 5/5 tests
[HALT] Stopping execution early to save time

=========================================
  Test Summary (Halted)
=========================================

Status:    HALTED
Group:      auth
Threshold: 20%

Results (so far):
  Completed: 5
  Passed:  4
  Failed:  1
  Rate:    20%

Action required:
  1. Review failed tests above
  2. Fix root cause(s)
  3. Re-run with: npm run test:e2e:fail-fast:auth
```

## Best Practices

1. Set appropriate thresholds: Lower for critical paths (auth), higher for independent features
2. Use project grouping: Apply appropriate thresholds per test group
3. Address root causes: Fix common issues before individual test healing
4. Configure minimum tests: Avoid premature halting with `minTests`
5. Use environment overrides: Override thresholds in CI/CD when needed

## Migration Guide

### From Custom Reporter

```bash
# 1. Install package
npm install @playwright-reporter/fail-fast

# 2. Create config file
# 3. Update playwright.config.ts
# 4. Test with both reporters in parallel
# 5. Remove old reporter when verified
```

### Command Migration

```bash
# Old
npm run test:e2e -- --reporter=./tests/reporters/custom-reporter.ts

# New
npm run test:e2e
```

## Troubleshooting

Tests not halting?

- Check `minTests` threshold is met
- Verify `haltOnThreshold: true`
- Check project detection is working

Wrong project detected?

- Verify pattern matching in config
- Use `@fail-fast-project` metadata comments
- Check detection strategy configuration

Threshold too aggressive?

- Increase `threshold` value
- Set higher `minTests` requirement
- Use environment variable override for specific runs

## Further Reading

- [Playwright Reporters](https://playwright.dev/docs/test-reporters)
- [E2E Testing Workflow](e2e-testing.md)
