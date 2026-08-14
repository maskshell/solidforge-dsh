# Reference Files

Comprehensive reference documentation for parallel development workflows.

## Workflows

All workflows start with Phase 0 (Intent Freeze) and end with the dual-ring Convergent Fix Loop.

| Workflow | Use When | Phases |
| --- | --- | --- |
| [Feature Development](feature-dev.md) | Adding new functionality with TDD | 8 phases (0–7) |
| [Bug Fix](bug-fix.md) | Fixing reported bugs | 6 phases (0–5) |
| [Refactoring](refactoring.md) | Improving code structure | 5 phases (0–4) |
| [E2E Testing](e2e-testing.md) | Browser-based E2E tests | 6 phases |
| [Documentation](documentation.md) | Updating project docs | 2 phases |

## Convergence Loop & Deterministic Infrastructure

| File | Purpose |
| --- | --- |
| [convergent-loop.md](convergent-loop.md) | Dual-ring convergence loop: state machine, context folding, reviewer prompt, breaker thresholds |
| [intent-blueprint.md](intent-blueprint.md) | Intent Blueprint format, freeze, read-only guard, revision channel |
| [arch-contracts.md](arch-contracts.md) | Architecture-contract gate (越权日志 schema, L1 codable/uncodable split) |
| [golden-paths.md](golden-paths.md) | Golden-path registry (@Agent-Golden-Ref), quarterly expiry, L1/L2 injection |
| [install.md](install.md) | Opt-in deterministic infra install (hooks, scripts, templates ship in `../infra/`) |
| [external-skills.md](external-skills.md) | External-skill integration contract (black-box skills like Impeccable: DESIGN.md anchor, detector/hook gate, command→seam map) |

## Infra Internals & Maintenance

| File | Purpose |
| --- | --- |
| [hooks-reference.md](hooks-reference.md) | Verified Claude Code Hook mechanics + per-hook contract |
| [design-decisions.md](design-decisions.md) | ADR log: non-obvious design choices and rejected alternatives |
| [extending.md](extending.md) | Add a language; the loading-chain rule (registry + checker) |

## Maturity & Evaluation

| File | Purpose |
| --- | --- |
| [maturity.md](maturity.md) | L1–L4 maturity yardstick, this skill's self-assessment (L4 architecture / L3.5 operational), and the flow-control self-review gate |

## Patterns & Configurations

| File | Purpose |
| --- | --- |
| [ast-grep-patterns.md](ast-grep-patterns.md) | Automated code review patterns (Vue, TS, Rust, Swift) |
| [ios-patterns.md](ios-patterns.md) | iOS/Apple platform toolchain, Simulator, Code Signing, pbxproj, Swift Concurrency, Instruments, Apple platform testing |
| [rust-patterns.md](rust-patterns.md) | Rust/Cargo toolchain, parallel conflicts (Cargo.lock/Cargo.toml), architecture-contract gate |
| [java-patterns.md](java-patterns.md) | Java/Maven/Gradle (JDK 17+) toolchain, parallel conflicts (pom.xml/build.gradle), architecture-contract gate (checkstyle + jdeps) |
| [go-patterns.md](go-patterns.md) | Go (go.mod / workspace) toolchain, parallel conflicts (go.mod/go.sum), (strong) architecture-contract gate (go build + go vet + golangci-lint depguard + `internal/` boundary) |
| [web-patterns.md](web-patterns.md) | Web (JavaScript/TypeScript) on browser + Node.js: detection, language breadth, framework/runtime patterns (React/Vue/Svelte/Next/Express), parallel conflicts, architecture-contract gate |
| [python-patterns.md](python-patterns.md) | Python toolchain, testing, dependency management, parallel conflicts, framework patterns |
| [e2e-patterns.md](e2e-patterns.md) | Playwright E2E testing patterns (auth, timeouts, selectors, wait strategy) |
| [fail-fast.md](fail-fast.md) | Fail-fast reporter config & advanced troubleshooting |
| [parallel-patterns.md](parallel-patterns.md) | Parallel execution patterns (including Apple platform scenarios) |

## Core Concepts

| File | Purpose |
| --- | --- |
| [roles.md](roles.md) | Role definitions and responsibilities |
| [role-agent-mapping.md](role-agent-mapping.md) | Task-to-agent mapping |
| [memory-protocol.md](memory-protocol.md) | Graphiti memory integration |

## Quick Reference

All workflows follow TDD pattern:

- **RED** - Write tests first (expect failure)
- **GREEN** - Implement code to pass tests
- **REFACTOR** - Improve code while keeping tests green

See [SKILL.md](../SKILL.md) for quick start guide.
