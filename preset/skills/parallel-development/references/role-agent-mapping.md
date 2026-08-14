# Role to Agent Mapping

Complete mapping between AI Agent roles and the preset's role-agent prompt corpus (`agents/*.agent.md`), spawned via the `subagent` tool.

## Contents

- [Role Mappings](#role-mappings)
  - [Requirements Analyst](#requirements-analyst)
  - [Architect](#architect)
  - [Detailed Designer](#detailed-designer)
  - [Backend Developer](#backend-developer)
  - [Frontend Developer](#frontend-developer)
  - [iOS Developer](#ios-developer)
  - [Apple Platform Architect](#apple-platform-architect)
  - [Test Engineer](#test-engineer)
  - [E2E Test Engineer](#e2e-test-engineer)
  - [Code Reviewer](#code-reviewer)
  - [Security Specialist](#security-specialist)
  - [DevOps Engineer](#devops-engineer)
  - [Graphiti Config Generator](#graphiti-config-generator)
  - [Documentation Writer](#documentation-writer)

## Role Mappings

### Requirements Analyst

Agent: `agents/requirements-manager.agent.md`

Purpose: Analyze user requirements, identify priorities and dependencies

Triggers:
English: "analyze requirements", "what features", "break down requirements"
Chinese: "需要什么功能", "分析需求", "功能分解"

Example tasks:
Analyze feature requests
Break down complex requirements
Identify acceptance criteria
Map requirements to User Stories

### Architect

Agent: `agents/architect.agent.md`

Purpose: Design system architecture and module boundaries

Triggers:
English: "design architecture", "how to design", "system design"
Chinese: "如何设计", "架构设计", "系统设计"

Example tasks:
Design module structure
Define interfaces between components
Make technical decisions
Evaluate architectural trade-offs

> **"design" is a three-role fork** (disambiguation in [external-skills.md](external-skills.md)): bare "design" / "system design" / "design architecture" → `architect` (software-architecture design, the default above). "design the UI" / "visual design" / "design tokens" / "配色" / "视觉设计" → `/impeccable` (UI/UX design — produces + governs the frozen `DESIGN.md`; via its `asset-producer` subagent + `init`/`shape`/`critique` commands). "build"/ "implement" the frontend → `frontend-developer` (frontend development).

### Detailed Designer

Agent: `Plan`

Purpose: Create detailed implementation plans

Triggers:
English: "implementation plan", "how to implement", "detailed design"
Chinese: "实现计划", "如何实现", "详细设计"

Example tasks:
Create step-by-step implementation plan
Identify files to create/modify
Estimate complexity
Define acceptance criteria

### Backend Developer

Agent: `agents/backend-developer.agent.md`

Purpose: Implement backend code features, APIs, and services

Language Auto-Detection: The agent automatically detects the programming language from project files and context.

| Detection | Language |
| --- | --- |
| `.rs` files, `Cargo.toml`, "cargo" | Rust |
| `.py` files, `requirements.txt`, "fastapi" | Python |
| `.go` files, `go.mod` | Go |
| `.java`/`.kt` files, `pom.xml`, `build.gradle` | Java/Kotlin |
| `.ts`/`.js` files, `package.json` | Node.js |

Triggers:
English: "implement", "create", "build", "develop", "backend", "api", "server", "rust", "cargo", "python", "fastapi", "django", "flask", "sqlalchemy", "pydantic", "pytest", "poetry", "uv", "node", "node.js", "express", "fastify", "nestjs", "hono", "go", "golang", "gin", "echo", "gofiber"
Chinese: "实现", "创建", "构建", "开发", "后端", "API", "服务端", "rust", "python", "fastapi", "django", "flask"

Example tasks:
Build REST APIs
Design database schemas
Implement authentication
Write backend tests

### Frontend Developer

Agent: `agents/frontend-developer.agent.md`

Purpose: Build Vue 3 or React UI components

Triggers:
English: "vue", "react", "frontend", "component", "next.js", "nextjs", "nuxt", "svelte", "sveltekit", "astro", "remix"
Chinese: "vue", "react", "前端", "组件"

Example tasks:
Build Vue 3 components
Build React components
Implement UI components
Write frontend tests

#### Visual-Blueprint-driven dispatch

When the convergence loop anchors a frozen `DESIGN.md` (Impeccable; see [external-skills.md](external-skills.md)), dispatch `agents/frontend-developer.agent.md` with a prompt that steers faithful implementation — mirror the iOS/Python prompt-template style:

```text
You are a frontend developer implementing against a FROZEN Visual Blueprint.
Design spec: <design_ref>  (read the frozen DESIGN.md — its frontmatter is the token export)
Implement: {FeatureName} in {file}
Requirements:
- Derive every color/type/spacing/radius token from DESIGN.md — do NOT substitute library defaults (Shadcn/AntD/Element Plus/Naive UI).
- You are the INDEPENDENT implementer: the visual-fidelity gate (Impeccable detector + convergence `detect`) and the reviewer's visual line check conformance to the frozen design.
- Write Vitest unit tests covering the component.
```

Do NOT use `/impeccable craft` in-loop (shape→build is reflexive); the design plan comes from `/impeccable shape` (Seam A). `polish`/`bolder`/`quieter`/`animate` are fine as gated refinement.

### iOS Developer

Agent: `agents/ios-developer.agent.md`

Purpose: Implement iOS/macOS app features using Swift, SwiftUI, or UIKit

Language Auto-Detection:

| Detection | Platform |
| --- | --- |
| `.swift` files, `Package.swift` | Swift / SPM |
| `*.xcodeproj`, `.m` / `.h` files | iOS / macOS (ObjC) |
| `*.xcworkspace`, `Podfile` | iOS / macOS (CocoaPods) |

Triggers:
English: "swift", "swiftui", "uikit", "ios", "macos", "xcode", "xctest", "xcodebuild", "swift package", "SPM", "app store", "view controller", "@main", "appkit", "watchos", "visionos"
Chinese: "swift", "swiftui", "uikit", "iOS", "macOS", "Xcode", "苹果开发", "iOS开发", "苹果应用"

Example tasks:
Build SwiftUI views and components
Implement UIKit view controllers
Create Swift Packages and SPM targets
Write XCTest unit tests and XCUITest UI tests
Implement MVVM / The Composable Architecture patterns
Build app lifecycle handlers and background tasks

#### iOS Prompt Templates

Standardized prompts for common iOS development tasks. Use these as the task prompt when assigning the `agents/ios-developer.agent.md` role for iOS work. Adjust specifics (project name, architecture pattern) to match the actual project.

ViewModel implementation (SwiftUI + @Observable):

```text
You are an iOS developer specializing in Swift and SwiftUI.
Implement {ViewModelName} as an @Observable class with @MainActor isolation.
Requirements:
- Use Swift Observation framework (@Observable), NOT ObservableObject
- Mark the class @MainActor since it drives UI state
- Use async/await for any asynchronous operations
- Ensure all types crossing actor boundaries are Sendable
- Follow MVVM: the ViewModel should call service/repository protocols, not concrete implementations
- Write Swift Testing (@Test, #expect) unit tests in {TestFileName}
```

SwiftUI View implementation:

```text
You are an iOS SwiftUI developer.
Implement {ViewName} that consumes the @Observable {ViewModelName}.
Requirements:
- Use @State for ViewModel ownership (not @StateObject/@ObservedObject)
- Support Dynamic Type and Dark Mode
- Use accessibility identifiers on interactive elements for XCUITest
- Follow the project's navigation pattern ({NavigationStack/NavigationSplitView})
- No force unwraps (try!, !) in production code
```

Actor / Service implementation:

```text
You are an iOS Swift developer specializing in Swift Concurrency.
Implement {ServiceName} as a Swift actor (or struct with async methods if stateless).
Requirements:
- All public types crossing actor boundaries must be Sendable
- Use structured concurrency (TaskGroup, async let) — avoid unstructured Task.detached
- Handle errors with typed throws if the project uses Swift 6, otherwise use standard throws
- Inject dependencies via protocol, not concrete types
- Write Swift Testing (@Test, #expect) unit tests with mocked dependencies
```

XCTest / XCUITest writing:

```text
You are an iOS test engineer.
Write {test_type} tests for {FeatureName} using {XCTest / Swift Testing}.
Requirements:
- For unit tests: prefer Swift Testing (@Test, #expect, @Suite) for new tests
- For UI tests: use XCUITest with accessibility identifiers (not label text)
- Include happy path, error scenarios, and edge cases
- No sleep() — use waitForExistence(timeout:) for UI, #expect for unit
- Each test must be independent — no shared mutable state between tests
```

Refactoring (iOS):

```text
You are an iOS developer refactoring {ModuleName}.
Requirements:
- Keep all existing tests passing — do not change test assertions
- If migrating ObservableObject → @Observable: remove @Published, use plain properties
- If migrating to Swift Concurrency: add Sendable conformance, use async/await instead of completion handlers
- Run `swift test --filter {TargetName}` after each change to verify
- Preserve public API — only refactor internal implementation
```

#### Python Prompt Templates

Standardized prompts for common Python development tasks. Use these as the `prompt` parameter when assigning `backend-developer` agents for Python work.

FastAPI endpoint implementation:

```text
You are a Python backend developer specializing in FastAPI.
Implement {FeatureName} endpoints in {router_file}.
Requirements:
- Use Pydantic models for request/response validation
- Use dependency injection (Depends) for database sessions and authentication
- Include proper error handling with HTTPException
- Write pytest tests using FastAPI TestClient in {test_file}
- Use async/await for all database operations
```

Django model + views:

```text
You are a Python backend developer specializing in Django.
Implement {FeatureName} in the {app_name} Django app.
Requirements:
- Define Django models with proper field types and constraints
- Use Django REST Framework serializers and viewsets for API endpoints
- Include proper migration files
- Write Django TestCase classes covering CRUD operations
- Follow Django conventions for URL routing and app configuration
```

SQLAlchemy model + repository:

```text
You are a Python backend developer specializing in SQLAlchemy.
Implement {ModelName} with async SQLAlchemy 2.0 patterns.
Requirements:
- Use declarative mapping with Mapped and mapped_column type annotations
- Implement an async repository pattern with AsyncSession
- Use selectinload or subqueryload for relationship loading (no lazy loading in async)
- Write pytest tests with mocked or test database sessions
- Include Alembic migration after model changes
```

Service layer / business logic:

```text
You are a Python developer implementing business logic.
Implement {ServiceName} service layer for {FeatureName}.
Requirements:
- Follow dependency injection — accept database session and external clients via constructor
- Keep the service framework-agnostic (no FastAPI/Django imports)
- Use Python type hints for all public methods
- Raise domain-specific exceptions for error cases
- Write pytest tests with mocked dependencies
```

pytest test writing:

```text
You are a Python test engineer.
Write pytest tests for {ModuleOrFeature} in {test_file}.
Requirements:
- Use pytest fixtures for test setup and dependency injection
- Use @pytest.mark.parametrize for data-driven test cases
- Include happy path, error scenarios, and edge cases
- No external dependencies — mock database, HTTP calls, and file system
- Tests must be independent — no shared mutable state between tests
- Place shared fixtures in conftest.py, test-specific fixtures in the test file
```

Refactoring (Python):

```text
You are a Python developer refactoring {ModuleName}.
Requirements:
- Keep all existing tests passing — do not change test assertions
- Use modern Python patterns (type hints, dataclasses/pydantic, f-strings)
- Follow PEP 8 style (enforced by ruff)
- Run `ruff check` and `mypy` after each change to verify
- Preserve public API — only refactor internal implementation
```

### Apple Platform Architect

Agent: `agents/architect.agent.md`

Purpose: Design multi-platform Apple ecosystem architecture, module boundaries, and data flow

Triggers:
English: "ios architecture", "apple design", "swift module design", "app structure", "multi-platform apple"
Chinese: "iOS架构", "苹果平台设计", "Swift模块设计", "应用结构"

> **Architect vs iOS Developer split**: Apple Platform Architect owns module / architecture decisions (module layering, dependency direction, SwiftUI-vs-UIKit per screen, schema design) — route there for those. `agents/ios-developer.agent.md` owns implementation (the actual Swift/SwiftUI/UIKit code). Same split as the three-role `design` fork under [Architect](#architect).

Example tasks:
Design Swift Package module boundaries
Plan actor isolation and data flow across features
Decide SwiftUI vs UIKit for specific screens
Plan Core Data / SwiftData schema
Evaluate Combine vs async/await for reactive flows
Design App Intents / Widget / App Clip boundaries

### Test Engineer

Agent: `agents/tester.agent.md` (Web/Backend) or `agents/ios-developer.agent.md` for XCTest unit / `agents/ios-tester.agent.md` for XCUITest (iOS)

Purpose: Write comprehensive tests. Framework selection adapts to the detected project type.

Framework Auto-Detection:

| Project Type | Test Framework | Test Runner |
| --- | --- | --- |
| Web (Vue/React/Node) | Jest / Vitest / Playwright | `npm test` / `npx vitest` |
| iOS (Swift/SwiftUI) | Swift Testing (`@Test`, `#expect`) for unit/integration; XCTest for UI automation (XCUITest) and performance benchmarks | `swift test` / `xcodebuild test` |
| Rust | cargo test | `cargo test` |
| Java (JDK 17+) | JUnit 5 | `mvn test` / `gradle test` |
| Go | testing | `go test` |
| Python | pytest / unittest | `pytest` |

Triggers:
English: "write tests", "test coverage", "create test cases", "unit test", "integration test"
Chinese: "编写测试", "测试覆盖", "创建测试用例", "单元测试", "集成测试"

Example tasks:
Write unit tests (framework detected from project type)
Create test plans
Analyze test coverage
Write snapshot tests

### E2E Test Engineer

Agents: Dedicated Playwright agents (Web) or XCUITest (iOS)

Purpose: Browser-based end-to-end testing (Web) or native UI testing (iOS)

Web: Playwright-based as below. iOS: See [ios-patterns.md](ios-patterns.md) for XCUITest workflow, Simulator management, and XCUITest selector strategy.

MCP Dependency: Requires `mcp__playwright-test` (Web). No MCP dependency for XCUITest (uses `xcodebuild test` + `xcrun simctl`).

Automatic Fallback Behavior:

1. Check if Playwright MCP is available (Web) or if `xcodebuild` is available (iOS)
2. If available: Use `playwright-test-planner` -> `playwright-test-generator` -> `playwright-test-healer` workflow (Web); or use `agents/ios-tester.agent.md` for XCUITest UI/E2E + `agents/ios-developer.agent.md` for XCTest unit (iOS)
3. If not available: Notify user about missing MCP/toolchain and fall back to `tester` agent for manual test writing

Agents:

- `playwright-test-planner` - Explore app UI and create test plans
- `playwright-test-generator` - Generate Playwright tests from plans
- `playwright-test-healer` - Debug and fix failing tests

Triggers:
English: "E2E test", "browser test", "playwright", "generate E2E tests", "fix test"
Chinese: "E2E 测试", "浏览器测试", "端到端测试", "生成 E2E 测试", "修复测试"

Example tasks:
Explore UI and create test plan
Generate automated browser tests
Fix failing Playwright tests
Validate user flows with real browser

### Code Reviewer

Agent: `agents/code-reviewer.agent.md`

Purpose: Review code quality and identify issues

Triggers:
English: "code review", "review code", "check code quality"
Chinese: "代码评审", "review 代码", "检查代码质量"

Review focus adapts to the project's language and framework. For language-specific patterns and automated checks, use [ast-grep-patterns.md](ast-grep-patterns.md). For iOS-specific review concerns (Swift Concurrency, memory management, safety patterns, performance anti-patterns), see [ios-patterns.md](ios-patterns.md) § Performance Regression Detection.

Example tasks:
Review pull requests
Identify bugs and incidental security issues (for dedicated security review → `agents/security-specialist.agent.md`)
Check coding standards
Suggest improvements

### Security Specialist

Agent: `agents/security-specialist.agent.md`

Purpose: Dedicated outer-ring security review beyond `code-reviewer`'s incidental OWASP coverage

Triggers:
English: "security review", "OWASP", "auth review", "authorization review", "threat model", "secret scan", "vulnerability assessment", "pre-production security"
Chinese: "安全审查", "安全评估", "威胁建模", "漏洞扫描", "权限审查"

> **vs `code-reviewer`**: `code-reviewer` handles incidental security within general code review. Route to `security-specialist` for dedicated security review (pre-production security pass, auth/authz design, threat model, secret audit, IaC security). It is strictly **outer-ring** — it does NOT duplicate the inner-ring deterministic gates (`semgrep_adapter`, `license_adapter`/Trivy, `arch_contract_deps`, `iac_adapter`/Checkov); it triages their output and covers what they miss (logic flaws, access-control design, cross-file secret flows).

Example tasks:
OWASP Top 10 / auth-authz review before production
Secret audit across the codebase
Triage semgrep/trivy/checkov gate output into ranked findings
Threat model for a sensitive data flow
IaC security review (open buckets, permissive SGs, privileged containers)

### DevOps Engineer

Agent: `agents/devops-engineer.agent.md`

Purpose: CI/CD, deployment, infrastructure

Triggers:
English: "deploy", "CI/CD", "infrastructure", "pipeline"
Chinese: "部署", "CI/CD", "基础设施", "流水线"

Example tasks:
Configure CI/CD pipelines
Manage Docker containers
Set up deployment scripts
Troubleshoot infrastructure issues

### Graphiti Config Generator

Agent: `agents/graphiti-config-generator.agent.md`

Purpose: Generate Graphiti Memory MCP configurations

Triggers:
English: "generate graphiti config", "setup memory", "create .graphiti.json"
Chinese: "生成 graphiti 配置", "配置记忆", "创建 graphiti"

Example tasks:
Generate .graphiti.json for new projects
Detect project type and configure memory patterns
Set up entity types and search patterns for tech stacks

### Documentation Writer

Agent: `agents/documentation-writer.agent.md`

Purpose: Write and maintain project documentation, track progress

Triggers:
English: "update status", "project progress", "track progress"
Chinese: "更新状态", "项目进度", "跟踪进度"

Example tasks:
Update implementation status
Write progress reports
Update project trackers
Document technical debt
