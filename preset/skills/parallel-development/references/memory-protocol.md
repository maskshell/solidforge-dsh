# Memory Protocol

Generic memory integration protocol for all AI agents.

> Note: Tool names below use Claude Code runtime format (`mcp__servername__toolname`).
> Best practice documentation uses `ServerName:tool_name` format.

## Contents

- [Overview](#overview)
- [Context Loading (MANDATORY)](#context-loading-mandatory)
- [Context Storage (MANDATORY)](#context-storage-mandatory)
- [Episode Types to Store](#episode-types-to-store)
- [Domain-Specific Queries](#domain-specific-queries)
  - [Backend Development](#backend-development)
  - [Frontend Development](#frontend-development)
  - [iOS / Apple Platform Development](#ios--apple-platform-development)
  - [Python Development](#python-development)
  - [Testing](#testing)
  - [Code Review](#code-review)
  - [Architecture](#architecture)
- [Best Practices](#best-practices)
  - [DO](#do)
  - [DON'T](#dont)
- [Integration with Workflows](#integration-with-workflows)

## Overview

Agents use Graphiti MCP to:

- Load context before starting work (search memory)
- Store context during/after work (add memory)

## Context Loading (MANDATORY)

When: ALWAYS before starting work
Purpose: Find relevant past decisions, patterns, issues

Generic Pattern:

```cli
# Search for domain-specific patterns
mcp__graphiti__search_nodes(query="[domain] patterns", max_nodes=5)

# Search for project-specific context
mcp__graphiti__search_memory_facts(query="[project] [feature]", max_facts=5)

# Search for similar past work
mcp__graphiti__search_memory_facts(query="similar [task type]", max_facts=5)
```

## Context Storage (MANDATORY)

When: After key decisions, implementations, or discoveries
Purpose: Preserve knowledge for future retrieval

Generic Pattern:

```cli
mcp__graphiti__add_memory(
  name="[Type]: [Subject]",
  episode_body="[Details: what, why, how]",
  source="text",
  source_description="[category]"
)
```

## Episode Types to Store

| Type | When to Store | Example |
| --- | --- | --- |
| Decision | After choosing an approach | Framework choice, architecture decision |
| Pattern | After discovering reusable pattern | API design, module structure |
| Implementation | After completing code/function | Component built, API endpoint created |
| Issue Fixed | After resolving problem | Bug fix, workaround applied |
| Lesson | After completing work | What went well/poorly, improvements |
| Requirement | During analysis phase | User requirements, acceptance criteria |

## Domain-Specific Queries

### Backend Development

```cli
# Context Loading
mcp__graphiti__search_nodes(query="Rust Python Go Java patterns", max_nodes=5)
mcp__graphiti__search_memory_facts(query="API authentication database", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Decision: Used Axum over Actix-web", episode_body="Rationale: ...")
mcp__graphiti__add_memory(name="Pattern: Repository with sqlx", episode_body="Data access layer: ...")
```

### Frontend Development

```cli
# Context Loading
mcp__graphiti__search_nodes(query="Vue React patterns", max_nodes=5)
mcp__graphiti__search_memory_facts(query="state management routing", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Component: AppHeader", episode_body="Props: ..., State: ...")
mcp__graphiti__add_memory(name="Pattern: Composable for auth", episode_body="useAuth() implementation: ...")
```

### Testing

```cli
# Context Loading
mcp__graphiti__search_nodes(query="testing frameworks", max_nodes=5)
mcp__graphiti__search_memory_facts(query="test patterns coverage", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Test Strategy: [feature]", episode_body="Unit tests: ..., E2E: ...")
mcp__graphiti__add_memory(name="Test Pattern: [type]", episode_body="Used X framework for Y tests")
```

### Code Review

```cli
# Context Loading
mcp__graphiti__search_memory_facts(query="code quality standards", max_facts=5)
mcp__graphiti__search_nodes(query="common issues bugs", max_nodes=5)

# Context Storage
mcp__graphiti__add_memory(name="Review: [feature]", episode_body="Issues found: ..., Approval: ...")
mcp__graphiti__add_memory(name="Issue Fixed: [description]", episode_body="Root cause: ..., Solution: ...")
```

### Architecture

```cli
# Context Loading
mcp__graphiti__search_nodes(query="architecture patterns design", max_nodes=5)
mcp__graphiti__search_memory_facts(query="framework selection", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Architecture: module structure", episode_body="src/api/, src/models/, ...")
mcp__graphiti__add_memory(name="Decision: chose modular design", episode_body="Rationale: ...")
```

### iOS / Apple Platform Development

```cli
# Context Loading
mcp__graphiti__search_nodes(query="Swift SwiftUI UIKit patterns", max_nodes=5)
mcp__graphiti__search_memory_facts(query="iOS architecture MVVM TCA actor isolation", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Decision: Chose SwiftUI over UIKit", episode_body="Rationale: iOS 16+ baseline, declarative UI preferred")
mcp__graphiti__add_memory(name="Pattern: MVVM with @Observable ViewModel", episode_body="ViewModel marked @Observable + @MainActor, uses @State for ownership in views, service layer uses async/await with actor isolation")
mcp__graphiti__add_memory(name="Component: LoginView", episode_body="SwiftUI view with @State viewModel consuming @Observable LoginViewModel, handles Sign in with Apple + email/password")
mcp__graphiti__add_memory(name="Test Pattern: XCUITest login flow", episode_body="Uses accessibility identifiers: emailField, passwordField, signInButton")
mcp__graphiti__add_memory(name="Test Pattern: Swift Testing unit tests", episode_body="Uses @Test and #expect for ViewModel and service layer tests, @Suite for grouping")
```

### Python Development

```cli
# Context Loading
mcp__graphiti__search_nodes(query="Python FastAPI Django Flask patterns", max_nodes=5)
mcp__graphiti__search_memory_facts(query="Python ORM SQLAlchemy database migration", max_facts=5)
mcp__graphiti__search_memory_facts(query="Python package management pyproject pytest", max_facts=5)

# Context Storage
mcp__graphiti__add_memory(name="Decision: Chose FastAPI over Django", episode_body="Rationale: async-first, type-driven validation with Pydantic, OpenAPI auto-generation")
mcp__graphiti__add_memory(name="Pattern: FastAPI router with dependency injection", episode_body="Router uses Depends() for DB session and auth, Pydantic schemas for request/response validation")
mcp__graphiti__add_memory(name="Pattern: SQLAlchemy async repository", episode_body="AsyncSession with selectinload for eager loading, repository protocol for testability")
mcp__graphiti__add_memory(name="Pattern: pytest fixture scoping", episode_body="function scope for test isolation, session scope for read-only shared data, conftest.py per test directory")
mcp__graphiti__add_memory(name="Component: UserService", episode_body="FastAPI router with CRUD endpoints, Pydantic UserCreate/UserResponse schemas, async SQLAlchemy repository")
mcp__graphiti__add_memory(name="Decision: uv for package management", episode_body="Rationale: Rust resolver performance, workspace support, unified toolchain with ruff and ty")
```

## Best Practices

### DO

Search memory before starting work
Store decisions with rationale
Store patterns for reuse
Store lessons learned
Use descriptive episode names

### DON'T

Store trivial/obvious information
Store without context/rationale
Duplicate existing episodes
Use vague episode names

## Integration with Workflows

Memory operations are integrated into each phase of the workflow files:

- [feature-dev.md](feature-dev.md)
- [bug-fix.md](bug-fix.md)
- [refactoring.md](refactoring.md)
- [e2e-testing.md](e2e-testing.md)
- [documentation.md](documentation.md)

## Golden-Path Episodes

The convergence loop curates a golden-path registry via the `@Agent-Golden-Ref` episode convention: curated best-practice Few-Shot slices used as L2 precedent (Warning tier) by the outer-ring reviewer. See [golden-paths.md](golden-paths.md). Each episode carries `responsible_party`, `reviewed_at`, and `expires_at` (quarterly) metadata; `golden_degrade.py` re-tags expired entries to `@Golden-Ref-STALE`.

Add a golden path:

```cli
mcp__graphiti__add_memory(
  name="Golden-Ref: <pattern name>",
  episode_body="@Agent-Golden-Ref\nresponsible_party: <owner>\nreviewed_at: <date>\nexpires_at: <date+quarter>\ndomain: python|swift|web|rust|java|go|visual\nmodule: <path>\n\n<best-practice slice + why>",
  source="text",
  source_description="golden-path"
)
```

The `domain:` enum above must stay identical to the one in [golden-paths.md](golden-paths.md) — same controlled vocabulary, must not drift.

Retrieve L2 precedent during outer review:

```cli
mcp__graphiti__search_memory_facts(query="@Agent-Golden-Ref <domain> <concept>", max_facts=3)
```

Never bulk-index the codebase; promote only core-framework-layer code or code a senior developer explicitly marked.
