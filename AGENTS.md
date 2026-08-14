## L1 Constitution (uncodable red lines)

Red lines that cannot be encoded as deterministic architecture-contract rules live here. These are Blockers: a violation returns the work for rewrite. Codable red lines (circular dependencies, layer isolation, concurrency baselines) are enforced deterministically by the inner Architecture-Contract Gate — do not duplicate them here; declare them in the project's arch-contract config (.importlinter.ini / .dependency-cruiser.cjs / .swiftlint.yml).

- Abstraction level must be appropriate: a helper must not leak domain logic into a generic utility, and a high-level policy must not reach into a low-level primitive directly.
- Naming must reflect intent, not implementation accident. A name that contradicts what the code does is a Blocker.
- No emergent coupling: two modules that are not explicitly wired must not secretly depend on each other's internal behavior or ordering.
- No "delete the error" fixes: removing a failing module, hardcoding a value to turn a test green, or wrapping logic in a bare catch to silence a failure are Blockers (the fast gate + blueprint diff catch most of these).
- All authentication/authorization that cannot be statically proven to flow through the unified gateway is a Blocker.

When a Reviewer flags one of these, the convergence loop treats it as an outer- ring Blocker and returns the change for rewrite — not a Warning.
