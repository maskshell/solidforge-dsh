# Code Reviewer Agent Code Patterns

## Review Output Format

```markdown
# Code Review Report

## Overview
[Brief summary of changes reviewed]

## Critical Issues (Must Fix)
- [ ] Issue 1 - Severity: High
  - Location: [file:line]
  - Description: [clear explanation]
  - Recommendation: [specific fix]

## Important Issues (Should Fix)
- [ ] Issue 1 - Severity: Medium
  - Location: [file:line]
  - Description: [clear explanation]
  - Recommendation: [specific fix]

## Suggestions (Nice to Have)
- [ ] Suggestion 1
  - Location: [file:line]
  - Description: [improvement opportunity]

## Positive Aspects
- [What was done well]

## Security Considerations
- [Specific security items requiring attention]

## Test Coverage
- [Assessment of testing completeness]

## Approval Status
- [ ] Approved
- [ ] Approved with changes requested
- [ ] Requires changes before approval
```

## Language-Specific Review Guidelines

### Rust-Specific Review Guidelines

**Ownership & Borrowing:**

- Verify no unnecessary clones (use `&` references when possible)
- Check for dangling references (ensure lifetimes are correct)
- Validate `mut` usage is appropriate (avoid over-mutating)
- Ensure `Copy` types are used where appropriate for performance

**Error Handling:**

- Prefer `?` operator over explicit `match` for Result propagation
- Verify `unwrap()`/`expect()` are not used in production code paths
- Check custom error types implement `std::error::Error` when needed
- Ensure error messages are descriptive and actionable

**Concurrency (async/.await):**

- Verify `Send` + `Sync` bounds for shared state in async contexts
- Check for proper `tokio::spawn` or `rayon` parallelization
- Validate no blocking calls in async contexts (`tokio::task::spawn_blocking`)
- Review `Arc<RwLock<>>` vs `Mutex<>` usage for performance

**Memory Safety:**

- Scrutinize all `unsafe` blocks - require justification and documentation
- Verify `unsafe` code follows Rustnomicon guidelines
- Check for proper `Drop` implementation for resource cleanup
- Validate no memory leaks (use `Leak` detector in tests)

**API Design:**

- Verify `pub` API follows semantic versioning principles
- Check that public types have documentation comments (`///`)
- Validate builder pattern or constructor functions for complex types
- Ensure error types are `Send + Sync + 'static` for library compatibility

**Testing:**

- Verify unit tests use `#[cfg(test)]` module
- Check integration tests are in `tests/` directory
- Validate property-based tests with `proptest` for critical functions
- Ensure benchmarks use `#[bench]` and don't affect release builds

### Python-Specific Review Guidelines

**Type Hints:**

- Verify type hints are present and accurate
- Check for `Any` usage that should be more specific
- Validate generic types are properly parameterized

**Async Patterns:**

- Verify `async`/`await` is used consistently
- Check for blocking calls in async contexts
- Validate proper error handling in async code

**Package Structure:**

- Verify proper package layout (`src/` vs flat structure)
- Check for circular imports
- Validate `__init__.py` usage is appropriate

### TypeScript/React-Specific Review Guidelines

**Hooks Patterns:**

- Verify hooks follow Rules of Hooks (only call at top level)
- Check for missing dependency arrays in `useEffect`
- Validate custom hooks are properly typed

**Component Design:**

- Verify components are properly typed with Props
- Check for unnecessary re-renders (missing memo)
- Validate proper use of React.FC or explicit types

**State Management:**

- Verify state is properly initialized
- Check for proper state update patterns (functional updates)
- Validate reducers/actions are properly typed

### Lua/OpenResty-Specific Review Guidelines

**Phase Handlers:**

- Verify correct phase for each handler (init_by_lua, content_by_lua, etc.)
- Check for blocking operations in phases that shouldn't block
- Validate proper use of `ngx.*` API

**Shared Dictionaries:**

- Verify dictionary size is appropriate
- Check for proper key naming conventions
- Validate atomic operations are used (incr vs set + 1)

**NGINX Integration:**

- Verify proper access to `ngx.var`, `ngx.ctx`
- Check for proper header manipulation
- Validate correct use of `ngx.req` and `ngx.resp`
