# AST-Grep Patterns (Optional Reference)

Common ast-grep patterns for automated code review in parallel development workflows.

## Contents

- [When to Use](#when-to-use)
- [MCP Tools](#mcp-tools)
- [Common Patterns](#common-patterns)
  - [Vue 3 SFC Structure Validation](#vue-3-sfc-structure-validation)
  - [TypeScript Quality Checks](#typescript-quality-checks)
  - [Rust Quality Checks](#rust-quality-checks)
  - [Swift Quality Checks](#swift-quality-checks)
  - [Python Quality Checks](#python-quality-checks)
  - [Import Statement Patterns](#import-statement-patterns)
  - [Component Naming Conventions](#component-naming-conventions)
  - [Duplicate Code Detection](#duplicate-code-detection)
- [Workflow Integration Examples](#workflow-integration-examples)
  - [Feature Development Workflow](#feature-development-workflow)
  - [Refactoring Workflow](#refactoring-workflow)
- [Project-Specific Rules](#project-specific-rules)
- [Notes](#notes)

## When to Use

- Code Reviewer Agent needs automated pattern checking
- Refactoring workflow requires duplicate code detection
- Project has defined code structure standards
- Validating parallel-generated code consistency

## MCP Tools

```text
mcp__ast-grep__find_code         - Find code by AST pattern
mcp__ast-grep__find_code_by_rule - Find by YAML rule
mcp__ast-grep__test_match_code_rule - Validate code against rule
mcp__ast-grep__dump_syntax_tree  - Debug syntax structure
```

## Common Patterns

### Vue 3 SFC Structure Validation

Check if component has `<script setup>`:

```yaml
id: vue-script-setup
language: vue
rule:
  pattern: '<script setup>$$$</script>'
```

Check for proper TypeScript usage in template:

```yaml
id: vue-ts-props
language: vue
rule:
  pattern: 'defineProps<$$$>'
```

### TypeScript Quality Checks

Ban `any` type:

```yaml
id: no-any-type
language: typescript
rule:
  pattern: ': any'
  not:
    has: 'as any'
```

Ensure async functions have error handling:

```yaml
id: async-error-handling
language: typescript
rule:
  pattern: 'async $FUNC($$$) { $$$ }'
  not:
    ast:
      kind: try_statement
```

### Rust Quality Checks

Ban `unwrap()` in production code (allow in tests):

```yaml
id: no-unwrap-production
language: rust
rule:
  pattern: '$EXPR.unwrap()'
  not:
    has:
      kind: function_item
      name: '$NAME'
    within:
      kind: module
      name: 'tests'
```

Ensure `?` operator is used for error propagation:

```yaml
id: prefer-question-operator
language: rust
rule:
  pattern: 'match $EXPR { Ok(v) => v, Err(e) => return Err(e) }'
```

Check for proper error handling in `Result` returns:

```yaml
id: proper-result-handling
language: rust
rule:
  pattern: 'async fn $NAME($$$) -> Result<$RET, $ERR> { $$$ }'
  not:
    has:
      kind: macro_invocation
      text: '?'
```

Validate `Send` + `Sync` trait bounds for concurrent types:

```yaml
id: send-sync-bounds
language: rust
rule:
  pattern: 'pub struct $NAME<T> { $$$ }'
  not:
    has:
      kind: impl_item
      constraints: 'T: Send + Sync'
```

Check for missing lifetime annotations:

```yaml
id: lifetime-annotation
language: rust
rule:
  pattern: 'fn $NAME(&$SELF, &$OTHER: &$TYPE) -> &$RT'
  not:
    has:
      kind: lifetime_parameter
```

### Swift Quality Checks

Ban `try!` (force-try that crashes on error):

```yaml
id: no-force-try
language: swift
rule:
  pattern: 'try! $EXPR'
```

Ban `fatalError()` outside of test code:

```yaml
id: no-fatalerror-production
language: swift
rule:
  pattern: 'fatalError($MSG)'
  not:
    inside:
      kind: class_declaration
      regex: 'Tests$'
```

Detect closures capturing `self` without `[weak self]` (advisory — high false positive rate):

```yaml
id: missing-weak-self
language: swift
rule:
  pattern: '{ $$$ in $$$ self $$$ }'
  not:
    has:
      kind: capture_list_item
      field: name
      regex: 'weak'
```

Important caveat: This pattern matches ALL closures referencing `self` without `[weak self]`, including non-escaping closures (Button actions, ForEach, onAppear, .map, .filter, etc.) that do NOT need weak self. Non-escaping closures are deallocated with the calling scope — they cannot create retain cycles. Reserve `[weak self]` for:

- Closures stored as properties (escaping)
- Closures passed to async callbacks (URLSession completion, DispatchQueue.asyncAfter)
- Closures captured by long-lived objects

This pattern produces a high false positive rate in SwiftUI code. Treat matches as advisory suggestions for review, not as bugs.

Detect non-Sendable types lacking explicit conformance — advisory, only relevant for types crossing actor boundaries:

```yaml
id: missing-sendable
language: swift
rule:
  pattern: 'class $NAME { $$$ }'
  not:
    has:
      kind: inherit
      pattern: 'Sendable'
```

Note: Most classes in iOS apps (ViewModels, ViewControllers, Managers) are `@MainActor`-isolated and do NOT need Sendable conformance. This pattern only matters for types passed across actor boundaries (e.g., data models passed to a background actor, response types from network calls). Treat matches as advisory for cross-actor types only, not as a blanket requirement.

Detect `DispatchQueue.main.async` when `@MainActor` should be used:

```yaml
id: dispatch-main-async-suspect
language: swift
rule:
  pattern: 'DispatchQueue.main.async { $$$ }'
```

Ban `sleep()` in test code (use expectations instead):

```yaml
id: no-sleep-in-tests
language: swift
rule:
  pattern: 'sleep($N)'
  inside:
    kind: class_declaration
    regex: 'Tests$'
```

Detect `@State` mutation inside computed property bodies — advisory pattern, relies on manual review:

```yaml
id: state-mutation-in-computed-property
language: swift
rule:
  pattern: 'var $NAME: $TYPE { $BODY }'
  has:
    kind: assignment
```

Note: This pattern flags any computed property containing an assignment, which may or may not be a `@State` mutation. SwiftUI emits a runtime warning ("Modifying state during view update") when a `@State` property is mutated during a view body evaluation. AST-level detection is inherently imprecise for this check — rely on the runtime warning and manual review rather than pattern matching alone.

Detect `ObservedObject` that should be `@StateObject` (ownership issue):

```yaml
id: observedobject-instead-of-stateobject
language: swift
rule:
  pattern: '@ObservedObject var $NAME = $INIT'
```

Detect `ObservableObject` usage that should migrate to `@Observable` (advisory — new code should prefer @Observable):

```yaml
id: observableobject-should-be-observable
language: swift
rule:
  pattern: '$CLASS: ObservableObject'
```

Note: `@Observable` (Swift Observation framework) replaces `ObservableObject + @Published` for new ViewModels. It provides property-level change tracking instead of object-level notifications, reducing unnecessary view re-renders. Existing stable code using `ObservableObject` does not need immediate migration — apply on-touch when modifying a ViewModel. SwiftUI views consuming `@Observable` ViewModels use `@State` (ownership) or receive the instance via `@Environment` instead of `@StateObject` / `@ObservedObject`.

Detect `@Published` that should be plain properties under `@Observable`:

```yaml
id: published-in-observable
language: swift
rule:
  pattern: '@Published var $NAME'
  inside:
    kind: class_declaration
    has:
      pattern: '@Observable'
```

This detects a common migration error: `@Published` has no effect inside `@Observable` classes. Remove `@Published` — `@Observable` tracks all stored properties automatically.

Detect empty catch blocks (silent error swallowing):

```yaml
id: empty-catch
language: swift
rule:
  pattern: 'catch { }'
```

Check for `Task` without actor isolation when calling MainActor methods:

```yaml
id: task-without-mainactor
language: swift
rule:
  pattern: 'Task { $$$ }'
  not:
    has:
      pattern: 'Task { @MainActor in $$$ }'
```

### Python Quality Checks

Detect mutable default arguments (list/dict/set defaults are shared across calls — a common source of bugs):

```yaml
id: mutable-default-argument
language: python
rule:
  pattern: 'def $FUNC($$$, $PARAM=[])'
```

```yaml
id: mutable-default-argument-dict
language: python
rule:
  pattern: 'def $FUNC($$$, $PARAM={})'
```

```yaml
id: mutable-default-argument-set
language: python
rule:
  pattern: 'def $FUNC($$$, $PARAM=set())'
```

Ban bare `except:` (catches all exceptions including KeyboardInterrupt and SystemExit):

```yaml
id: no-bare-except
language: python
rule:
  pattern: 'except:'
```

Detect `except Exception` followed by `pass` (silently swallows all errors):

```yaml
id: silent-exception-swallow
language: python
rule:
  pattern: 'except Exception: pass'
```

Detect `eval()` usage (security risk — arbitrary code execution):

```yaml
id: no-eval
language: python
rule:
  pattern: 'eval($EXPR)'
```

Detect `exec()` usage (same security risk):

```yaml
id: no-exec
language: python
rule:
  pattern: 'exec($EXPR)'
```

Detect wildcard imports in production code (pollutes namespace, hides dependencies):

```yaml
id: no-wildcard-import
language: python
rule:
  pattern: 'from $MODULE import *'
```

Detect `assert` statements outside test files (assertions are stripped with `-O` flag — not for runtime validation):

```yaml
id: assert-in-production
language: python
rule:
  pattern: 'assert $EXPR'
  not:
    inside:
      kind: module
      regex: 'test_'
```

Detect string concatenation or f-string in SQL queries (SQL injection risk — advisory, high false positive rate):

```yaml
id: sql-string-concat
language: python
rule:
  pattern: 'cursor.execute($STR + $$$)'
```

```yaml
id: sql-f-string
language: python
rule:
  pattern: 'cursor.execute(f$$$)'
```

Note: These SQL patterns have high false positive rates — they flag any string concatenation or f-string passed to execute(). Parameterized queries using `cursor.execute("SELECT ... WHERE id = %s", (id,))` are safe and will not be flagged. Treat matches as advisory suggestions for review.

Detect `== None` instead of `is None` (identity check is the Pythonic way):

```yaml
id: none-equality-check
language: python
rule:
  pattern: '$EXPR == None'
```

Detect `type(x) == Y` instead of `isinstance(x, Y)` (fails for subclasses):

```yaml
id: type-equality-check
language: python
rule:
  pattern: 'type($EXPR) == $TYPE'
```

### Import Statement Patterns

Find all composables imports:

```yaml
id: composables-imports
language: typescript
rule:
  pattern: "import $$$ from '@/composables/$$$'"
```

Check for relative imports beyond parent:

```yaml
id: no-deep-relative-imports
language: typescript
rule:
  pattern: "from '../../$$$'"
```

### Component Naming Conventions

Vue component files should match component name:

```yaml
id: vue-component-name-match
language: vue
rule:
  pattern: 'export default { name: "$$$" }'
```

### Duplicate Code Detection

Find similar function structures:

```yaml
id: function-pattern
language: typescript
rule:
  pattern: 'function $NAME($$$) { return $EXPR }'
```

Find similar component options:

```yaml
id: vue-options-api
language: vue
rule:
  pattern: 'export default { $$$ }'
```

## Workflow Integration Examples

### Feature Development Workflow

Phase 6: Integration & Review

Web (Vue/React):

```markdown
Task(code-reviewer): Review AppHeader implementation
  - Use ast-grep to validate structure patterns
  - Check for banned patterns (any, console.log, etc.)
  - Verify naming conventions
```

iOS (Swift/SwiftUI):

```markdown
Task(code-reviewer): Review SwiftUI feature implementation
  - Check for try! and fatalError in production code
  - Validate [weak self] in closures
  - Detect DispatchQueue.main.async that should use @MainActor
  - Find missing Sendable conformance on shared types
```

Python:

```markdown
Task(code-reviewer): Review Python feature implementation
  - Check for mutable default arguments ([], {}, set())
  - Detect bare except: and silent exception swallowing
  - Flag eval() and exec() usage
  - Find wildcard imports (from X import *)
  - Detect SQL string concatenation (injection risk)
  - Flag assert in non-test code
```

### Refactoring Workflow

Phase 1: Analysis

Web:

```markdown
Task(architect): Analyze codebase for refactoring opportunities
  - Use ast-grep to find duplicate code structures
  - Identify components with similar patterns
  - Report consolidation opportunities
```

iOS:

```markdown
Task(architect): Analyze Swift codebase for refactoring opportunities
  - Use ast-grep to find missing @MainActor annotations
  - Detect force-unwrap and force-try patterns
  - Identify empty catch blocks swallowing errors
  - Find @ObservedObject that should be @StateObject
```

Python:

```markdown
Task(architect): Analyze Python codebase for refactoring opportunities
  - Detect mutable default arguments
  - Find bare except: and silent error swallowing
  - Flag wildcard imports
  - Detect eval()/exec() usage
  - Find type(x) == Y that should use isinstance()
```

## Project-Specific Rules

Important: These patterns are project-specific. Each project should define its own rules in:

- Project `.cursor/rules/` or project-specific skill
- Team coding standards
- Architecture documentation

## Notes

1. Optional Reference: This file is provided as a reference only. Code Reviewer Agents may or may not use these patterns based on project needs.
2. Performance Considerations: ast-grep is fast for single-file searches but may be slow for large codebases. Use targeted searches.
3. Complementary Tools: ast-grep works well alongside linters (ESLint, Prettier) and type checkers. It is not a replacement.
4. Pattern Quality: Poorly written patterns may produce false positives or miss issues. Test patterns before relying on them.
