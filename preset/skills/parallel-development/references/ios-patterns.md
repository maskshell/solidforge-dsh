# iOS & Apple Platform Development Patterns

Comprehensive reference for iOS/macOS/watchOS development in parallel workflows. Covers the full Apple ecosystem toolchain, from project detection through testing, profiling, and code signing.

## Contents

- [Project Detection](#project-detection)
- [Toolchain Commands](#toolchain-commands)
  - [Build Commands](#build-commands)
  - [Test Commands](#test-commands)
  - [SPM Commands](#spm-commands)
- [Simulator Management](#simulator-management)
- [Code Signing & Provisioning](#code-signing--provisioning)
- [pbxproj Conflict Resolution](#pbxproj-conflict-resolution)
- [Swift Concurrency & Parallelism](#swift-concurrency--parallelism)
  - [Actor Isolation](#actor-isolation)
  - [Common Concurrency Pitfalls](#common-concurrency-pitfalls)
  - [Parallel Agent Coordination for Swift Concurrency](#parallel-agent-coordination-for-swift-concurrency)
  - [Sendable Compliance](#sendable-compliance)
  - [Concurrency in Convergent Fix Loop](#concurrency-in-convergent-fix-loop)
  - [Swift 6.2 Considerations](#swift-62-considerations)
- [Instruments & Performance Profiling](#instruments--performance-profiling)
- [Apple Platform Testing](#apple-platform-testing)
  - [XCTest Coverage](#xctest-coverage)
  - [Swift Testing (Xcode 16+)](#swift-testing-xcode-16)
  - [XCUITest (iOS E2E)](#xcuitest-ios-e2e)
- [SPM Parallel Safety](#spm-parallel-safety)

## Project Detection

Detect the project type by looking for these files in the project root. The first match determines the toolchain:

| File | Project Type | Build Tool | Test Tool |
| --- | --- | --- | --- |
| `*.xcodeproj` or `*.xcworkspace` | Xcode project/workspace | `xcodebuild` | `xcodebuild test` |
| `Package.swift` (no `.xcodeproj`) | Swift Package Manager only | `swift build` | `swift test` |
| `Package.swift` + `.xcodeproj` | SPM + Xcode (tuist/XcodeGen) | `xcodebuild` | `xcodebuild test` |
| `Podfile` | CocoaPods | `xcodebuild -workspace` | `xcodebuild test` |
| `Cartfile` | Carthage | `xcodebuild` | `xcodebuild test` |
| `project.yml` or `Project.swift` | XcodeGen or Tuist | generated `.xcodeproj` + `xcodebuild` | generated `.xcodeproj` + `xcodebuild test` |
| `*.playground` | Swift Playgrounds | N/A | N/A |

### Multi-Platform Projects

When a project contains multiple targets (iOS + macOS + watchOS), identify the primary scheme first:

```bash
xcodebuild -project X.xcodeproj -list
```

This outputs available schemes and targets. Select the scheme that matches the user's stated platform. If unspecified, default to the first iOS scheme.

## Toolchain Commands

### Build Commands

Build for iOS Simulator (default for development):

```bash
xcodebuild \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -configuration Debug \
  build
```

Build with SPM only:

```bash
swift build --configuration debug
```

Build for macOS:

```bash
xcodebuild \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=macOS' \
  build
```

Build for device (requires signing):

```bash
xcodebuild \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS,name=Any iOS Device' \
  -configuration Release \
  build
```

#### Common xcodebuild Flags

| Flag | Purpose |
| --- | --- |
| `-project <.xcodeproj>` | Specify project file |
| `-workspace <.xcworkspace>` | Specify workspace (CocoaPods) |
| `-scheme <name>` | Target scheme to build |
| `-destination '<spec>'` | Platform/device to build for |
| `-configuration <Debug\|Release>` | Build configuration |
| `-derivedDataPath <path>` | Custom derived data location |
| `-resultBundlePath <path>` | Output .xcresult bundle |
| `-quiet` | Suppress verbose output |
| `CODE_SIGNING_ALLOWED=NO` | Skip code signing (simulator only) |

#### Parallel Build Safety

When multiple agents run `xcodebuild` concurrently:

- Use separate derived data paths with deterministic labels (not random UUIDs — the path must be predictable for later `xcrun simctl install`):

  ```bash
  xcodebuild ... -derivedDataPath .build/derived-data-agent-1
  xcodebuild ... -derivedDataPath .build/derived-data-agent-2
  ```

- Note: `-derivedDataPath` has known issues in some Xcode versions (may be ignored or cause crashes). If builds fail with custom derived data paths, fall back to sequential builds sharing the default derived data location.
- Never run concurrent builds with the same scheme + destination + derived data — this causes build database corruption.
- SPM resolution is NOT concurrency-safe: only one agent should run `swift package resolve` at a time.

### Test Commands

Run XCTest suite (Simulator):

```bash
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -resultBundlePath test-results.xcresult
```

Run a single test class:

```bash
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -only-testing:AppTests/MyFeatureTests
```

Run SPM tests:

```bash
swift test                      # All tests
swift test --filter MyFeatureTests  # Single test target
swift test --parallel            # Parallel test execution (Swift 5.10+)
```

Run tests with code coverage:

```bash
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -enableCodeCoverage YES \
  -resultBundlePath coverage.xcresult
```

View code coverage from .xcresult:

```bash
xcrun xccov view --report coverage.xcresult
```

#### Test Result Bundle

`.xcresult` bundles contain structured test data:

```bash
# List test results
xcrun xcresulttool get --path result.xcresult --format json

# Extract code coverage
xcrun xccov view --report --json result.xcresult
```

#### Lint (SwiftLint)

SwiftLint is the standard linter for Swift projects. Configure via `.swiftlint.yml` in the project root:

```bash
# Run lint (warnings only)
swiftlint lint --config .swiftlint.yml

# Run with warnings treated as errors (recommended for CI/validation)
swiftlint lint --strict --config .swiftlint.yml

# Auto-correct fixable violations
swiftlint autocorrect --config .swiftlint.yml
```

If the project has no `.swiftlint.yml`, this step is optional. Swift Concurrency validation (via `-strict-concurrency=complete`) provides a built-in lint pass for concurrency issues.

### SPM Commands

```bash
swift package init --type library    # New library
swift package init --type executable # New executable
swift package update                  # Update dependencies
swift package resolve                 # Resolve and pin versions
swift package show-dependencies       # Dependency graph
swift package dump-package            # JSON representation
```

## Simulator Management

Simulator device names change with each Xcode release (e.g., "iPhone 16 Pro" → "iPhone 17 Pro"). Before running any simulator command, discover available devices:

```bash
# List all available simulator devices and their UDIDs
xcrun simctl list devices available

# Find the newest iPhone model
xcrun simctl list devices available | grep "iPhone" | tail -5
```

Commands in this section use `iPhone 16 Pro` as a placeholder — substitute with the newest available iPhone model from the listing above.

### Boot and Preparation

```bash
# List available simulators
xcrun simctl list devices available

# Boot a specific simulator
xcrun simctl boot "iPhone 16 Pro"

# Wait for boot to complete
xcrun simctl bootstatus "iPhone 16 Pro" -b

# Check current state
xcrun simctl list devices | grep Booted
```

### App Installation and Launch

```bash
# Install app
xcrun simctl install booted path/to/App.app

# Launch app by bundle ID
xcrun simctl launch booted com.example.app

# Launch with environment variable
xcrun simctl launch --console booted com.example.app

# Terminate app
xcrun simctl terminate booted com.example.app
```

### Data Management

```bash
# Reset simulator (clean state)
xcrun simctl erase all

# Reset specific simulator
xcrun simctl erase "iPhone 16 Pro"

# Copy file to simulator
xcrun simctl addmedia booted ~/photo.jpg

# Set privacy permissions (photos, camera, etc.)
xcrun simctl privacy booted grant photos com.example.app
xcrun simctl privacy booted grant camera com.example.app
xcrun simctl privacy booted grant notifications com.example.app
xcrun simctl privacy booted grant location-always com.example.app
```

### Network Simulation

Network conditioning for the simulator is done at the host (macOS) level, not inside the simulator. The `networksetup` tool is a macOS utility and does not work via `simctl spawn`:

```bash
# Correct approach: use the host-side Network Link Conditioner
# 1. Install from Xcode Additional Tools: open "Additional Tools for Xcode" → "Network Link Conditioner.prefPane"
# 2. Enable via System Settings or Terminal:
#    networksetup -listnetworkserviceorder  # find your active network service
#    sudo ditto # use dnctl/pf for scriptable conditioning (advanced)
```

For simple offline testing, disable the host's network interface or use the simulator's built-in Developer settings (Settings → Developer → Network Link Conditioner on the simulated device).

### UI Testing (XCUITest)

```bash
# Run XCUITest target
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppUITests \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest'
```

### E2E Environment Verification

For iOS, the E2E equivalent of `curl -I http://localhost/` is:

```bash
# 1. Check simulator is available
xcrun simctl list devices available | grep "iPhone 16 Pro"

# 2. Boot if needed
xcrun simctl boot "iPhone 16 Pro" 2>/dev/null | --- | true

# 3. Build and install
xcodebuild -project App.xcodeproj -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -derivedDataPath .build/derived-data \
  build

# 4. Install
xcrun simctl install booted .build/derived-data/Build/Products/Debug-iphonesimulator/App.app

# 5. Launch
xcrun simctl launch booted com.example.app
```

## Code Signing & Provisioning

### Development (Simulator)

Simulator builds do NOT require code signing. For development workflows:

```bash
xcodebuild ... CODE_SIGNING_ALLOWED=NO
```

### Development (Device)

Device builds require signing. Check status:

```bash
# List signing identities
security find-identity -v -p codesigning

# Check provisioning profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/
```

### Common Signing Issues

| Issue | Diagnosis | Fix |
| --- | --- | --- |
| "No signing certificate" | `security find-identity -v -p codesigning` returns empty | Install development cert from Apple Developer |
| "Provisioning profile expired" | Check profile expiry | Renew in Apple Developer portal |
| "No provisioning profile for bundle ID" | Wrong/missing profile | Register bundle ID, create profile |
| "Keychain access denied" | Keychain locked | `security unlock-keychain` |

### CI/CD Signing

For automated environments, use manual signing with stored credentials:

```bash
xcodebuild \
  CODE_SIGN_STYLE=Manual \
  PROVISIONING_PROFILE_SPECIFIER="Match Development com.example.app" \
  CODE_SIGN_IDENTITY="Apple Development" \
  ...
```

Or use `fastlane match` for automated certificate/provisioning profile management:

```bash
fastlane match development --readonly
```

### When Signing Goes Wrong

- Do not regenerate certificates without checking if they're shared across a team
- Do not revoke distribution certificates — this breaks existing App Store builds
- Check whether the issue is local (one machine) or org-wide (expired profile)

## pbxproj Conflict Resolution

`*.xcodeproj/project.pbxproj` is the highest-conflict file in iOS projects. It's a flat, UUID-keyed plist that git merge tools handle poorly.

### Strategy by Project Setup

Option 1: Use XcodeGen (recommended for parallel development)

Generate the `.xcodeproj` from a YAML/JSON spec. Agents edit the spec, not pbxproj:

```bash
# Generate project from spec
xcodegen generate --spec project.yml

# .gitignore the generated files
*.xcodeproj
*.xcworkspace
```

`project.yml` is human-readable and merge-friendly. Agents editing different targets produce non-conflicting diffs.

Option 2: Use Tuist

Similar to XcodeGen but with Swift-based project manifests:

```bash
tuist generate
```

Project definition split across `Project.swift` and `Target.swift` files — each agent's target definition is a separate file, eliminating merge conflicts entirely.

Option 3: Manual pbxproj Management

If the project cannot be migrated to a generator:

1. .gitattributes merge driver:

   ```text
   *.pbxproj merge=union
   ```

   Union merge adds UUIDs from both sides — handles additions but not deletions.

2. Sequentialize pbxproj edits: Never let two agents modify pbxproj simultaneously. The concurrency scheduler's `files_touched` conflict detection handles this automatically when `.xcodeproj/project.pbxproj` is listed.

3. Post-merge validation: After any pbxproj merge, run:

   ```bash
   xcodebuild -project App.xcodeproj -list
   ```

   If this fails, the merge is corrupted. Regenerate or manually repair.

4. Common pbxproj merge failures:
   - Duplicate file references (same file added by two agents) → remove duplicate `PBXFileReference` entries
   - Missing build phase entries → file exists in project but not in target → re-add via Xcode UI
   - Orphaned UUID references → pointers to deleted objects → remove stale entries

### Pre-flight for pbxproj-heavy Projects

Before parallel development begins:

- Check if `project.yml` or `Project.swift` exists (XcodeGen/Tuist) — if so, prefer editing those
- If only `.xcodeproj` exists, warn the user about potential merge conflicts and suggest XcodeGen migration
- Mark `project.pbxproj` as a shared resource in the concurrency scheduler

## Swift Concurrency & Parallelism

Swift's actor model imposes constraints that parallel agents must respect.

### Actor Isolation

Swift 6 enforces strict concurrency checking. Agents writing code that will integrate must agree on actor boundaries:

```swift
// @MainActor — UI work always on main thread
@MainActor
@Observable
class ViewModel {
    var items: [Item] = []

    func loadItems() async {
        // This runs on MainActor
        items = await fetchItems()  // await suspends but resumes on MainActor
    }
}

// Non-isolated service
actor DataService {
    func fetchItems() async throws -> [Item] {
        // Runs on actor's executor, not main thread
        return try await api.getItems()
    }
}
```

### Common Concurrency Pitfalls

| Pattern | Problem | Solution |
| --- | --- | --- |
| `Task { ... }` without actor context | Runs on generic executor, may touch MainActor state | Use `Task { @MainActor in ... }` for UI (Swift 6.0), or use `Task.immediate` (Swift 6.2) |
| Passing non-Sendable types across actor boundaries | Compiler warning in Swift 6, data race in Swift 5 | Mark as Sendable or use @unchecked Sendable |
| `await` inside `@MainActor` func with long operation | Blocks main thread during await | Move CPU work off MainActor |
| `nonisolated async` jumping off caller's actor (Swift 6.0) | Unexpected isolation boundary crossing | Swift 6.2: `nonisolated async` stays on caller's actor by default; use `@concurrent` to opt into old behavior |
| `DispatchQueue.main.async` in Swift Concurrency code | Mixing GCD and structured concurrency | Use `@MainActor` isolation instead |

### Parallel Agent Coordination for Swift Concurrency

When multiple agents implement features that communicate through actors:

1. Define actor interfaces first (Phase 2: Architecture). The architect agent produces protocol + actor stubs.
2. Agents implement against protocols, not concrete actors — this allows independent compilation.
3. Use `@preconcurrency import` during GREEN phase to suppress strict concurrency errors temporarily, then remove in REFACTOR.
4. Run full Swift 6 concurrency checking in Convergent Fix Loop Tier 1:

   ```bash
   swift build -Xswiftc -strict-concurrency=complete
   ```

Architecture phase requirements for parallel iOS development — these artifacts must be produced in Phase 2 (Architecture) before Phase 5 (GREEN) can run agents in parallel. Without them, agents working independently will disagree on actor boundaries and shared types, causing convergence failures.

- Actor isolation map: Which features run on `@MainActor`, which use custom actors, which are non-isolated. This determines which agents can run in parallel (agents on different actors have no file overlap; agents sharing `@MainActor` must coordinate).
- Sendable shared types: Value types and reference types that cross actor boundaries, defined as protocols or concrete types with `Sendable` conformance. Agents implement against these types — without upfront definitions, each agent invents its own, causing merge conflicts.
- Protocol / interface definitions: The architect produces protocol stubs for service boundaries. Agents implement concrete types against protocols, enabling independent compilation.
- Dependency direction: Explicit declaration of which feature modules depend on which shared modules. This feeds into `files_touched` conflict detection in the concurrency scheduler (see [parallel-patterns.md](parallel-patterns.md) § Conflict Detection Matrix).

### Sendable Compliance

Agents adding new types that cross actor boundaries must ensure Sendable:

```swift
// Value types are implicitly Sendable if all members are Sendable
struct User: Codable, Sendable {
    let id: UUID
    let name: String
}

// Reference types need explicit Sendable conformance
final class Cache<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String: Value] = [:]
    // Must handle synchronization internally
}
```

### Concurrency in Convergent Fix Loop

For iOS projects using Swift Concurrency, Tier 1 validation should include:

```bash
# Enable complete concurrency checking
swift build -Xswiftc -strict-concurrency=complete 2>&1 | grep -E "warning:|error:"
# Or via xcodebuild
xcodebuild ... OTHER_SWIFT_FLAGS="-strict-concurrency=complete"
```

Swift 5.x projects: warnings are informational. Swift 6 projects: errors must be resolved.

### Swift 6.2 Considerations

Swift 6.2 introduces "Approachable Concurrency" — a reversal of the default isolation assumptions that reduces annotation burden for apps that are effectively single-threaded (most iOS apps). Key changes relevant to parallel development:

Default Isolation (SE-0466):

Modules can opt into `-default-isolation MainActor`, making unannotated code run on `@MainActor` by default. This means:

- Most app modules need zero isolation annotations — they're already single-threaded
- Only code that explicitly needs concurrency uses `nonisolated` or `@concurrent`
- Parallel agents working on UI features no longer need to annotate every ViewModel with `@MainActor` — it's the default

```bash
# Enable default MainActor isolation for a module
swift build -Xswiftc -default-isolation -Xswiftc MainActor
# Or in Package.swift:
# .target(name: "App", swiftSettings: [.unsafeFlags(["-default-isolation", "MainActor"])])
```

Caller Execution Semantics (SE-0461):

In Swift 6.0, `nonisolated async` functions always jump off the caller's actor. In Swift 6.2, they stay on the caller's actor by default. New `@concurrent` attribute explicitly requests the old behavior (jump to cooperative thread pool).

This affects parallel agent coordination: agents implementing `nonisolated async` functions no longer trigger unintended isolation boundary crossings. Use `@concurrent` when CPU-bound work genuinely needs to run off the main actor.

`Task.immediate` (SE-0472):

```swift
// Starts executing synchronously if already on the target executor
// Only suspends at the first suspension point
Task.immediate { @MainActor in
    // Provides data to UI immediately, then can await asynchronously
    self.items = cachedItems
    await refreshFromNetwork()
}
```

Use `Task.immediate` when bridging synchronous UI setup with async data loading — common in `onAppear` and `task` modifiers.

Implications for parallel development:

1. Simpler GREEN phase: With default MainActor isolation, agents write less boilerplate. Focus prompts on business logic, not isolation annotations.
2. Convergent Fix Loop Tier 1: Add `-default-isolation MainActor` to build commands when the project adopts Swift 6.2. Concurrency errors that remain are genuine issues, not annotation noise.
3. Cross-module protocols: When agents in different modules define protocols, isolation conformance (SE-0470) allows protocols to be constrained to specific actors. Define shared protocol isolation in the architecture phase.

## Instruments & Performance Profiling

### When to Profile

Performance validation is integrated into Convergent Fix Loop Tier 2 for iOS projects when:

- Feature involves image/video processing
- Feature involves large data sets or Core Data migrations
- User explicitly requests performance review
- HEAVY/MEDIUM effort level is specified

### Core Instruments Templates

```bash
# Launch Instruments with a template
xcrun xctrace record \
  --template "Time Profiler" \
  --attach <pid> \
  --output profile.trace \
  --time-limit 30s

# Common templates:
# - "Time Profiler" — CPU profiling
# - "Allocations" — Memory allocation tracking
# - "Leaks" — Memory leak detection
# - "Swift Concurrency" — Task/actor profiling
# - "Core Data" — Core Data performance
# - "Network" — Network request profiling
```

### Automated Profiling via CLI

```bash
# 1. Launch the app
xcrun simctl launch booted com.example.app &
APP_PID=$!

# 2. Attach Instruments
xcrun xctrace record \
  --template "Allocations" \
  --attach $APP_PID \
  --output allocations.trace \
  --time-limit 20s

# 3. Analyze results
xcrun xctrace export --input allocations.trace --xpath '/trace-toc/run[@number="1"]/data/table[@schema="malloc-info"]' --output allocations.xml
```

### Performance Regression Detection

In Convergent Fix Loop Tier 2, the code-reviewer agent checks for:

| Anti-pattern | Detection | Why It Matters |
| --- | --- | --- |
| `viewDidLoad` with synchronous network calls | grep for `URLSession.*data.*viewDidLoad` | Blocks UI |
| Main actor blocking work | Manual review: `@MainActor` functions containing synchronous loops or CPU-bound work without `await` | Freezes UI during execution |
| O(n²) SwiftUI body evaluation | Manual review of nested ForEach loops | Causes scroll stutter |
| Large `@Published` changes triggering full redraw | Manual review of `@Published` properties that cascade through multiple views | Performance regression |
| `try!` in production code paths | AST pattern `try!` (see [ast-grep-patterns.md](ast-grep-patterns.md)) | Crash risk |

Note: `@frozen` on public enums only applies in library evolution mode (used by Apple's SDKs). It is not relevant for most iOS applications — skip this check unless building a distributable framework.

## Apple Platform Testing

### XCTest Coverage

Run tests and collect coverage:

```bash
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -enableCodeCoverage YES \
  -resultBundlePath coverage.xcresult

# View coverage report
xcrun xccov view --report coverage.xcresult

# JSON output for programmatic analysis
xcrun xccov view --report --json coverage.xcresult > coverage.json
```

### Swift Testing (Xcode 16+)

Swift Testing is Apple's recommended test framework for new tests. It uses macro-driven, value-oriented models instead of XCTest's class inheritance. Both frameworks can coexist in the same test target — migrate incrementally.

When to use Swift Testing vs XCTest:

| Scenario | Framework |
| --- | --- |
| New unit or integration tests | Swift Testing (`@Test`, `#expect`) |
| UI automation tests (XCUITest) | XCTest (Swift Testing does not support UI automation) |
| Performance benchmarks (`measure`) | XCTest (Swift Testing has no equivalent) |
| Parameterized tests | Swift Testing (`@Test(arguments:)`) — each parameter runs as an independent parallel sub-result |
| Existing stable XCTest suite | Migrate on-touch: when you modify a test, rewrite it in Swift Testing |

Core patterns:

```swift
import Testing

// Free function test (no class needed)
@Test func userDefaultsStoresValue() {
    let defaults = UserDefaults.standard
    defaults.set("hello", forKey: "greeting")
    #expect(defaults.string(forKey: "greeting") == "hello")
}

// Struct-based suite with shared setup
@Suite("Login ViewModel")
struct LoginViewModelTests {
    let viewModel: LoginViewModel

    init() {
        // Replaces setUp — runs fresh for each test
        viewModel = LoginViewModel()
    }

    @Test("Successful login updates state")
    func successfulLogin() async {
        await viewModel.login(email: "test@example.com", password: "pass")
        #expect(viewModel.isLoggedIn)
    }

    @Test("Invalid email shows error")
    func invalidEmail() {
        viewModel.email = "not-an-email"
        viewModel.validate()
        #expect(viewModel.errorMessage != nil)
    }
}

// Parameterized test — each argument runs independently and in parallel
@Test(arguments: [
    "test@example.com",
    "user@domain.org",
    "admin@company.co",
])
func emailValidationAcceptsValid(email: String) {
    #expect(EmailValidator.isValid(email))
}

// Trait system for conditional execution
@Test(.enabled(if: ProcessInfo.processInfo.environment["CI"] == nil))
func localOnlyTest() {
    // Skipped in CI environments
}

@Suite(.serialized)  // Run tests in this suite sequentially
struct DatabaseTests {
    @Test func insertRecord() { ... }
    @Test func deleteRecord() { ... }
}
```

Running Swift Testing from command line:

```bash
# All tests (XCTest + Swift Testing run together)
xcodebuild test \
  -project App.xcodeproj \
  -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest'

# SPM projects
swift test

# Filter by test name
swift test --filter LoginViewModelTests
```

Swift Testing tests appear alongside XCTest in Xcode's test navigator and `xcodebuild` output. No separate command needed.

Advantages for parallel development:

- Parameterized tests (`@Test(arguments:)`) default to parallel execution — free parallelism without managing task groups
- `#expect` captures the full expression tree and shows both sides on failure, reducing debugging round-trips when reviewing agent output
- Trait system replaces scattered `#if` blocks with declarative, composable configuration — easier for agents to reason about

Migration strategy: New tests use Swift Testing. UI automation and performance benchmarks stay with XCTest. Both coexist in the same target. Do not rewrite stable tests en masse — migrate on-touch.

Compilation note: Macro expansion slows compilation in large test suites. Mitigate by splitting into multiple source files rather than concentrating hundreds of `@Test` functions in one file.

### XCUITest (iOS E2E)

XCUITest is the iOS equivalent of Playwright for browser testing. Key differences from Playwright:

- Runs in Simulator or on device, not in a browser context
- Accesses native UI elements via accessibility hierarchy
- Uses `XCUIApplication` instead of `page`

```swift
import XCTest

final class LoginUITests: XCTestCase {
    let app = XCUIApplication()

    override func setUp() {
        continueAfterFailure = false
        app.launch()
    }

    func testLoginFlow() {
        let emailField = app.textFields["Email"]
        XCTAssertTrue(emailField.waitForExistence(timeout: 5))
        emailField.tap()
        emailField.typeText("test@example.com")

        let passwordField = app.secureTextFields["Password"]
        passwordField.tap()
        passwordField.typeText("password123")

        app.buttons["Sign In"].tap()

        let welcomeText = app.staticTexts["Welcome"]
        XCTAssertTrue(welcomeText.waitForExistence(timeout: 10))
    }
}
```

### XCUITest Selector Strategy

Priority order (mirrors Playwright selector priority):

1. `app.buttons["Submit"]` — Accessibility identifier (semantic, most stable). Set via `.accessibilityIdentifier("Submit")` in SwiftUI or `element.accessibilityIdentifier = "Submit"` in UIKit.
2. `app.staticTexts["Welcome"]` — Accessibility label
3. `app.buttons.element(boundBy: 0)` — Index-based (fragile, last resort)
4. Avoid XCUIElement query matching by subview position — breaks with layout changes

### SwiftUI Previews

SwiftUI Previews serve as a fast, low-cost integration smoke test during parallel development. When multiple agents modify shared views or view models, Previews break silently — the canvas shows an error but no test suite runs.

Per-agent Preview verification: After completing GREEN phase implementation, each agent should verify that its views' Previews build successfully:

```bash
# Build the target (includes Preview providers)
xcodebuild -project App.xcodeproj -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  build 2>&1 | grep -i "preview"
```

A failing Preview often reveals an interface mismatch (changed ViewModel initializer, renamed property, broken dependency) before the full test suite runs. Treat Preview build failures as early integration signals during the Convergent Fix Loop.

### Apple Platform Test Checklist

Mirrors and extends the E2E test coverage checklist:

- [ ] Happy path (normal flow)
- [ ] Error scenarios (invalid input, network failure)
- [ ] App lifecycle transitions (background → foreground)

  ```swift
  XCUIDevice.shared.press(.home)
  app.activate()
  ```

- [ ] Dynamic Type (accessibility text sizes)
- [ ] Dark Mode toggle
- [ ] Low memory warning handling (`simctl simulate memorywarning`)
- [ ] Deep link / Universal Link handling

  ```bash
  xcrun simctl openurl booted "myapp://path/to/content"
  ```

- [ ] Push Notification simulation

  ```bash
  xcrun simctl push booted com.example.app notification.apns
  ```

- [ ] No `sleep()` / `waitForExistence(timeout:)` preferred
- [ ] Timeout ≤ 30 seconds per test
- [ ] New tests use Swift Testing (`@Test`, `#expect`) unless UI automation or performance benchmark
- [ ] Parameterized edge cases use `@Test(arguments:)` instead of for-loops

### iOS Fail-Fast Pattern

For iOS/XCUITest projects, `@playwright-reporter/fail-fast` does not apply. Use `xcodebuild test` exit codes and `.xcresult` bundle analysis instead. The pattern below provides concrete implementation for the fail-fast strategy described in the SKILL.md Fail-Fast section.

Parse test results from .xcresult:

```bash
# After xcodebuild test completes with -resultBundlePath test-results.xcresult
# Extract test summary as JSON
xcrun xcresulttool get --path test-results.xcresult --format json > test-results.json

# Count total and failed tests (requires xcresulttool JSON parsing)
# The JSON structure contains actions → tests → testableSummaries
# Look for testStatus values: "Success", "Failure"
```

Fail-fast threshold detection script:

```bash
#!/bin/bash
# ios-fail-fast.sh — Parse xcresults and halt if failure rate exceeds threshold
# Usage: ios-fail-fast.sh <xcresult-path> [threshold-percentage]

XCRESULT_PATH="${1:?Usage: ios-fail-fast.sh <xcresult-path> [threshold]}"
THRESHOLD="${2:-30}"  # Default 30% failure rate

# Extract test counts from xcresult bundle xcodebuild test exit code: 0 = all pass, nonzero = at least one failure
RESULT_JSON=$(xcrun xcresulttool get --path "$XCRESULT_PATH" --format json 2>/dev/null)

# Count failures and total using xcresulttool output
# The exact JSON structure varies by Xcode version — use xcresulttool get test-summary if available (Xcode 16+), otherwise parse the full JSON
FAILED=$(echo "$RESULT_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
failed = 0
total = 0
def walk(obj):
    global failed, total
    if isinstance(obj, dict):
        if obj.get('testStatus') == 'Failure':
            failed += 1
            total += 1
        elif obj.get('testStatus') == 'Success':
            total += 1
        for v in obj.values():
            walk(v)
    elif isinstance(obj, list):
        for item in obj:
            walk(item)
walk(data)
print(f'{failed} {total}')
" 2>/dev/null | --- | echo "0 0")

FAILED_COUNT=$(echo "$FAILED" | awk '{print $1}')
TOTAL_COUNT=$(echo "$FAILED" | awk '{print $2}')

if [ "$TOTAL_COUNT" -eq 0 ]; then
    echo "No test results found in $XCRESULT_PATH"
    exit 1
fi

RATE=$((FAILED_COUNT * 100 / TOTAL_COUNT))
echo "Tests: $FAILED_COUNT/$TOTAL_COUNT failed ($RATE%)" >&2

if [ "$RATE" -gt "$THRESHOLD" ]; then
    echo "HALT: Failure rate $RATE% exceeds threshold $THRESHOLD%" >&2
    echo "Address root causes before proceeding with individual test fixes." >&2
    exit 2  # Exit code 2 = halted by fail-fast
fi

echo "PASS: Failure rate $RATE% within threshold $THRESHOLD%"
exit 0
```

Integration with Convergent Fix Loop:

In Tier 1 validation, after running `xcodebuild test`:

```bash
# 1. Run tests
xcodebuild test \
  -project App.xcodeproj -scheme AppScheme \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -resultBundlePath test-results.xcresult

# 2. Check fail-fast threshold (30% default, same rationale as Web config)
bash ios-fail-fast.sh test-results.xcresult 30
EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
    # Halted — systemic issue. Fix root cause before healing individual tests.
    echo "Systemic failure detected. Review xcresult for common failure patterns."
    # Extract the most common failure message to guide root cause analysis:
    xcrun xcresulttool get --path test-results.xcresult --format json | \
      python3 -c "
import json, sys
from collections import Counter
data = json.load(sys.stdin)
failures = []
def walk(obj):
    if isinstance(obj, dict):
        if obj.get('testStatus') == 'Failure' and obj.get('failureMessage'):
            failures.append(obj['failureMessage'])
        for v in obj.values():
            walk(v)
    elif isinstance(obj, list):
        for item in obj:
            walk(item)
walk(data)
for msg, count in Counter(failures).most_common(5):
    print(f'  [{count}x] {msg}')
"
fi
```

Threshold rationale (mirrors Web/Playwright thresholds):

| Feature Type | Threshold | Rationale |
| --- | --- | --- |
| Authentication / Sign-in | 20% | Auth failures block all downstream flows |
| Core Data / Persistence | 25% | Data layer failures propagate to all features |
| Feature-specific (per module) | 40% | Features are relatively independent |
| XCUITest (end-to-end) | 30% | Default — E2E failures may indicate systemic UI issues |

### Modularization & Parallel Strategy

How the project's module structure affects parallel execution opportunities:

Feature-based modularization (recommended for parallel development):

Each feature module contains its own Presentation/Domain/Data layers as an independent SPM package or Xcode target. Agents working on `Features/Login/` and `Features/Profile/` have zero file overlap — maximum parallelism.

```text
Sources/
  Features/
    Login/          ← Agent A: LoginViewModel, LoginView, LoginService
    Profile/        ← Agent B: ProfileViewModel, ProfileView, ProfileService
    Feed/           ← Agent C: FeedViewModel, FeedView, FeedRepository
  Shared/
    Networking/     ← Shared dependency — must be stable before parallel work
    Persistence/    ← Shared dependency — must be stable before parallel work
    UIComponents/   ← Shared dependency — agents can add but not modify existing
```

Conflict detection at target granularity:

When using SPM local packages, mark `files_touched` at the target level to capture intra-target dependencies:

```json
{
  "files_touched": ["Sources/Features/Login/**/*.swift", "Tests/Features/Login/**/*.swift"],
  "targets": ["FeatureLogin"],
  "depends_on": []
}
```

Different SPM targets with no shared source dependencies can run in parallel. Agents working on different targets share only the compiled `.build/` output — use `--scratch-path` isolation if running builds concurrently.

Layer-based modularization (less parallel-friendly):

All UI in one module, all data in another. Parallel agents working on different features within the same layer share files and conflict more often. Suitable for smaller teams but requires more sequential scheduling.

Hybrid strategy (common in practice):

Lower layers (Networking, Persistence) are independent packages — stable, rarely modified. Upper layers (Feature targets) are organized by feature — high parallelism. Schedule:

1. Serial phase: Ensure shared infrastructure packages compile and their tests pass.
2. Parallel phase: Multiple agents work on independent feature targets simultaneously.
3. Serial integration: Resolve any cross-feature protocol mismatches in Convergent Fix Loop.

Build time optimization: Modularized projects benefit from SPM's incremental builds. Unmodified packages are not recompiled. When an agent modifies `FeatureLogin`, only that target recompiles — `FeatureProfile`'s build artifacts are cached. This is the primary compile-time benefit of modularization for parallel workflows.

### iOS Error Recovery for Parallel Agents

When an agent fails during an iOS task, check these platform-specific conditions before reporting to the user:

Build failure (xcodebuild or swift build):

1. Derived data corruption — multiple agents writing to the same derived data path causes build database corruption.
   - Detect: `xcodebuild` error contains "build database is locked", "could not read from build database", or produces nonsensical compile errors for files that should compile.
   - Recover: Delete the derived data directory and rebuild.

     ```bash
     rm -rf .build/derived-data-agent-N/
     # Then re-run the build from Tier 1
     ```

   - Prevent: Use separate `-derivedDataPath` per agent (see § Parallel Build Safety above).

2. SPM resolution conflict — two agents ran `swift package resolve` simultaneously, corrupting `Package.resolved`.
   - Detect: `Package.resolved` contains merge conflict markers, or `swift build` fails with "dependency graph has unresolvable dependencies".
   - Recover: Delete `Package.resolved` and re-resolve once (serial).

     ```bash
     rm -f Package.resolved
     swift package resolve  # Single agent, serial
     ```

   - Prevent: The conflict detection matrix in [parallel-patterns.md](parallel-patterns.md) marks `Package.swift` and `Package.resolved` as shared resources.

3. Simulator unavailable — no booted simulator or runtime not installed.
   - Detect: `xcodebuild` error contains "no matching simulator", or `xcrun simctl` returns no booted devices.
   - Recover: Boot or create a simulator.

     ```bash
     xcrun simctl list runtimes
     xcrun simctl list devices available | grep "iPhone" | tail -3
     xcrun simctl boot "iPhone 16 Pro" 2>/dev/null | --- | true
     ```

   - Prevent: Pre-flight check (`xcrun simctl list runtimes`) should catch this before agents launch.

4. Code signing failure on device builds — agent tried to build for physical device without signing credentials.
   - Detect: `xcodebuild` error contains "no signing certificate", "provisioning profile expired", or "keychain access denied".
   - Recover: For development, switch to simulator destination and add `CODE_SIGNING_ALLOWED=NO`.
   - Prevent: Pre-flight should detect if the task targets a physical device and verify signing credentials exist.

When to auto-retry vs. report to user:

- Auto-retry once: derived data corruption, SPM resolution conflict, simulator not booted. These are transient, environment-level issues.
- Report immediately: code signing failure (requires user action), missing simulator runtime (requires Xcode installation), genuine code errors (need human review of agent output).

After auto-retry, if the same failure persists, treat it as a genuine error and report to the user with the failure context.

### Lifecycle Testing

```swift
func testBackgroundRestoration() {
    // Set state
    app.textFields["Name"].tap()
    app.textFields["Name"].typeText("Saved Name")

    // Background the app
    XCUIDevice.shared.press(.home)

    // Wait for the app state transition to complete, then restore
    let restoredField = app.textFields["Saved Name"]
    let exists = restoredField.waitForExistence(timeout: 5)
    app.activate()
    XCTAssertTrue(exists, "Field should exist after app activation")
    XCTAssertEqual(app.textFields["Name"].value as? String, "Saved Name")
}

func testLowMemoryWarning() {
    XCUIDevice.shared.press(.home)
    // Simulate memory warning via simctl on the booted device:
    // xcrun simctl spawn booted launchctl kickstart -k system/com.apple.memorystatus
    app.activate()
    let criticalElement = app.staticTexts["CriticalData"]
    XCTAssertTrue(criticalElement.waitForExistence(timeout: 5), "Critical data should survive memory warning")
}
```

### Snapshot Testing

For visual regression testing, use swift-snapshot-testing:

```swift
import SnapshotTesting

func testProfileView() {
    let view = ProfileView(user: .mock)
    // Use the newest available device config from ViewImageConfig.
    // As of swift-snapshot-testing 1.17, available cases include:
    // .iPhoneSe, .iPhone8, .iPhone8Plus, .iPhoneX through .iPhone15ProMax
    // Check ViewImageConfig.swift in the library source for the most current list.
    assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone15ProMax)))
}
```

Snapshot tests require a reference image set. Agents generating UI code should also update snapshot references when the UI changes. Run `swift test --filter SnapshotTests` to regenerate reference images when the UI intentionally changes.

Stability constraints for snapshot tests:

- Use fixed layout environments: `.environment(\.dynamicTypeSize, .large)` to decouple from system font settings
- Use fixed color scheme: `.environment(\.colorScheme, .light)` to avoid dark mode differences
- Reference images must match the Simulator's screen scale and OS version — commit references from a consistent CI environment

Preview-bridged snapshots (Prefire): The Prefire library auto-generates snapshot tests from `#Preview` declarations, eliminating duplicate configuration between previews and tests. This is useful during parallel development — each agent's `#Preview` doubles as a snapshot test baseline.

## SPM Parallel Safety

### Concurrency Constraints

Swift Package Manager has known concurrency limits:

| Operation | Concurrency Safe? | Notes |
| --- | --- | --- |
| `swift package resolve` | ❌ No | Serial access only — writes to `.build/` and `Package.resolved` |
| `swift build` | ⚠️ Conditional | Safe only if using separate `.build/` directories |
| `swift build` (with macro targets) | ❌ No | Macro plugins serialize compilation across targets — concurrent builds with macros conflict |
| `swift test` | ⚠️ Conditional | Safe only if using separate `.build/` directories |
| `swift package update` | ❌ No | Serial access only — modifies `Package.resolved` |
| Editing `Package.swift` | ❌ No | Serialize via concurrency scheduler |
| Adding a Swift Macro (`@freestanding` / `@attached`) | ❌ No | Two agents adding macros to the same package creates plugin conflicts; serialize at the package level |

### Parallel SPM Strategy

For parallel agent workflows in SPM projects:

1. Only one agent edits `Package.swift` at a time — the concurrency scheduler already handles this via `files_touched: ["Package.swift"]`.

2. Use separate scratch paths for parallel builds:

   ```bash
   swift build --scratch-path .build/agent-1/
   swift build --scratch-path .build/agent-2/
   ```

3. Resolve dependencies once, then build in parallel:
   - Serial phase: `swift package resolve` (one agent)
   - Parallel phase: multiple `swift build --scratch-path .build/agent-N/` (many agents)

4. Target-level isolation: When the project has multiple SPM targets (libraries), agents working on different targets with no shared dependencies can operate independently. The scheduler should mark `files_touched` at target granularity:

   ```json
   {
     "files_touched": ["Sources/MyFeature/*.swift", "Tests/MyFeatureTests/*.swift"],
     "targets": ["MyFeature"]
   }
   ```

### Package.resolved Conflict

`Package.resolved` is a JSON file that pins exact dependency versions. Two agents running `swift package resolve` or `swift package update` will produce merge conflicts. Strategy:

- During feature development: don't modify dependencies. If a dependency update is needed, it's a separate task that runs sequentially.
- If both agents need new dependencies: merge by keeping both additions in `Package.swift`, then run `swift package resolve` once.

## Architecture-Contract Gate (Swift)

The inner-ring architecture-contract gate for Swift / Apple platforms. Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_swift.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_swift.py [package]
```

Checks:

- Layer / boundary rules — SwiftLint `custom_rules`. Configure via `.swiftlint.yml` (template in `infra/templates/`).

  ```bash
  swiftlint lint --config .swiftlint.yml
  ```

- Concurrency baseline — `swift build -Xswiftc -strict-concurrency=complete` (Sendable, actor isolation, data races). For Xcode projects the gate runs the equivalent `xcodebuild ... -Xswiftc -strict-concurrency=complete`. Only runs when a `Package.swift` or `.xcodeproj` is present.

A missing tool degrades that check to a no-op pass with an explicit coverage note — the gate is never silently green.
