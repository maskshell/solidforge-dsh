# Architecture-Contract Gate (架构契约门)

The deterministic, codable architecture checks that run in the INNER ring at the convergence point (not per edit). Because an LLM cannot reliably judge architecture by reading, codable architecture standards become deterministic scan rules; the outer-ring LLM only handles the uncodable semantic residue.

The gate is a script: `arch_contract_<platform>.py` (installed at `infra/scripts/`). It emits a structured "越权日志" (violation log) and exits non-zero (Blocker) on any violation.

## 越权日志 (violation log) JSON schema

```json
{
  "gate": "arch-contract-python",
  "passed": false,
  "coverage": ["import-linter: layer/forbidden contracts checked", "..."],
  "findings": [
    {
      "severity": "blocker",
      "rule": "layer-violation",
      "file": "app/repositories/user_repo.py",
      "line": 14,
      "detail": "repository imports app.api.router (forbidden)",
      "suggestion": "route via the service layer / an interface"
    }
  ]
}
```

`severity` is `blocker` or `warning`. A single blocker finding -> gate exits 1 and the loop stays in the inner ring. `coverage` always lists what was checked and what was skipped (a tool missing degrades to a no-op pass with an explicit note — the gate is never silently green).

## L1 constitution: codable vs uncodable split

The architecture contracts are the CODEABLE part of the L1 constitution (red lines). Each red line is either enforced deterministically here, or lives as text in the project `AGENTS.md` L1 Constitution section (see `infra/templates/claude-md-l1-constitution.md` — filename kept for upstream provenance).

| Red line | Codable? | Enforced where |
| --- | --- | --- |
| No circular dependencies | codable | arch-contract gate -> Blocker |
| Layer / dependency isolation (no repo->api) | codable | arch-contract gate -> Blocker |
| Concurrency baseline (no sync-in-async, no unbounded pools, Sendable) | codable | arch-contract gate -> Blocker |
| No hardcoded secrets | codable | fast gate (ruff S105 / eslint) -> Blocker |
| Auth through unified gateway | partly | arch-contract where statically detectable; else L1 text |
| Abstraction level / naming / emergent coupling | uncodable | L1 text in AGENTS.md -> reviewer Blocker |

Do NOT duplicate a codable red line as text; declare it in the platform config.

## Per-platform tools (commands live in the L4 pattern files)

- Python: import-linter (layers/forbidden contracts) + pylint cyclic-import + a stdlib ast scan for sync-in-async + pyright type-check (`--outputjson`). Config template: `.importlinter.ini`. Commands: see [python-patterns.md](python-patterns.md) -> Architecture-Contract Gate (Python).
- Swift: SwiftLint custom_rules (`--reporter json`, layer/boundary) + `swift build -Xswiftc -strict-concurrency=complete` (Sendable/actor baseline; the compiler build also type-checks). Config template: `.swiftlint.yml`. Commands: see [ios-patterns.md](ios-patterns.md) -> Architecture-Contract Gate (Swift).
- Web/TS: dependency-cruiser (no-circular + layer rules) + eslint no-restricted-syntax (sync-in-async) + tsc type-check (`--noEmit --pretty false`). Config template: `.dependency-cruiser.cjs`. Commands: see [web-patterns.md](web-patterns.md) -> Architecture-Contract Gate (Web / TypeScript). NOTE: the type gate (`tsc`) needs a `tsconfig.json`; pure-JS projects opt in via `allowJs` (otherwise that check degrades honestly). dependency-cruiser + eslint apply to JS and TS alike.
- Rust: `cargo clippy --message-format=json` (correctness/concurrency baseline; suggested_replacement surfaced into `suggestion`; the compile also type-checks) + optional `cargo-modules` (orphaned modules). Config template: `clippy.toml`. Commands: see [rust-patterns.md](rust-patterns.md) -> Architecture-Contract Gate (Rust). NOTE: Rust has NO first-class layer/dependency-direction enforcer — layer contracts are NOT enforced deterministically here and remain an outer-ring semantic concern. This is the thinnest gate; it degrades honestly via `coverage`.
- Java: `checkstyle -f xml -c checkstyle.xml` (style + ImportControl package-layer import rules; parsed from the XML output) + `jdeps --cyclic` (package cycles; JDK-bundled, no install). Config template: `checkstyle.xml`. Commands: see [java-patterns.md](java-patterns.md) -> Architecture-Contract Gate (Java). NOTE: fine-grained layer-direction beyond Checkstyle ImportControl is NOT enforced deterministically here — it remains an outer-ring concern (or add ArchUnit rules, which run through the test gate via mvn/gradle test). Thin gate; degrades honestly via `coverage`.
- Go: `go build ./...` (the compiler rejects import cycles + compile errors; runs FIRST and skips `go vet` on failure — vet shares the compiler front-end) + `go vet ./...` (static: printf-format, struct tags, lock copies) + `golangci-lint run --out-format=json` (style + depguard layer/dependency-direction rules; severity mapped by `FromLinter`). Config template: `.golangci.yml`. Commands: see [go-patterns.md](go-patterns.md) -> Architecture-Contract Gate (Go). NOTE: Go is a STRONG gate — layer isolation is enforced two ways: the `internal/` compiler-enforced structural boundary (always on) + depguard for finer non-`internal` package rules; cycles are compiler-rejected. The `-race` concurrency baseline is test-time/runtime (there is no `go vet -race`), so it runs in the test gate (`go test -race`), not here.

## Sibling inner-ring gates: supply-chain, tests & API contract

Beyond the per-language architecture-contract gate, three cross-ecosystem gates run at the same inner convergence point and emit the same 越权日志 schema. **They detect ecosystems recursively** (a marker at the repo root OR nested — a frontend in `frontend/`, a backend in `backend/`, a monorepo package), so a mixed frontend+backend repo gets BOTH sides gated: each check runs once per dir holding its marker.

- `arch_contract_deps.py` — leaked secrets (gitleaks, cross-language; secret values are redacted from findings) + dependency vulnerabilities (pip-audit / npm audit / cargo audit / OWASP dependency-check for Java). Agents hallucinate outdated/vulnerable deps and hardcoded credentials; this gate is the deterministic patch for that.
- `arch_contract_tests.py` — failing tests as Blockers (pytest --json-report / vitest --reporter=json / nextest --junit-out or cargo test / swift test / mvn or gradle test via JUnit XML), AND the AC→test-name set gate (P1): the frozen Intent Blueprint's AC→test mapping is diffed against per-language collected test names — a missing declared name is a `test-name-missing` Blocker (blocks naked "delete the failing test"); degrades to a coverage note when the blueprint has no mapping (rule 3); AND the per-language coverage gate (P3): measures execution coverage and emits a `coverage-below-threshold` WARNING when the blueprint declares an NFR coverage floor (measure-only default; WARNING not Blocker — execution coverage, not assertion quality). The test suite is the Agent's objective function.
- `arch_contract_api.py` — (mixed frontend+backend repos only) API-contract consistency: is there an OpenAPI/Swagger artifact? is the generated client stale? do the frontend's fetch/axios call sites hit paths in the spec? Advisory (`warning`) in v1 — semantic shape matching stays outer-ring. See [web-patterns.md](web-patterns.md) / [java-patterns.md](java-patterns.md) for the mixed-project workflow.
- **External-skill design gate (Impeccable)** — when a project arms Impeccable (`npx impeccable
  install`), its 44-rule deterministic detector provides the design-fidelity gate: a provider-native
  tools/post-execute hook (per-edit, advisory) + a convergence sweep run via
  `infra/scripts/impeccable_detect_adapter.py` (shells out to the armed `detect.mjs --json` WITHOUT
  `--no-config`, so it loads the frozen DESIGN.md and cross-checks implementation tokens — then wraps
  the findings into 越权日志). NOT a hand-rolled `arch_contract_*.py` — an external engine leveraged at
  the convergence point. See [external-skills.md](external-skills.md) for the adapter + freeze model.
- **External-skill API-ruleset gate (Spectral)** — when a project arms Spectral
  (`brew install spectral-cli` or `npm i -g @stoplight/spectral-cli`), its `spectral:oas` + `.spectral.yaml` ruleset provides the
  API-spec gate: a convergence sweep run via `infra/scripts/spectral_adapter.py` (shells out to
  `spectral lint -f json`, wraps findings into 越权日志; advisory, severity collapsed to `warning`).
  COMPLEMENTARY to `arch_contract_api.py` (which checks presence/freshness/path-consistency);
  Spectral checks the spec's OWN ruleset compliance. NOT a hand-rolled `arch_contract_*.py` — an
  external engine leveraged at the convergence point. See [external-skills.md](external-skills.md).
- **External-skill SAST gate (Semgrep)** — when a project arms Semgrep
  (`brew install semgrep` or `pip install semgrep`), a convergence sweep runs via
  `infra/scripts/semgrep_adapter.py` (shells out to `semgrep --json --config <ruleset>`, wraps
  findings into 越权日志; advisory, severity collapsed to `warning`). A DEPTH-1 rule gate — no
  per-feature frozen anchor (the ruleset is repo-wide config). COMPLEMENTARY to `/security-review`
  (LLM) and `arch_contract_deps.py` (secrets + dependency CVEs): Semgrep is the SOURCE-code SAST
  axis. NOT a hand-rolled `arch_contract_*.py` — an external engine leveraged at the convergence
  point. See [external-skills.md](external-skills.md).
- **External-skill prose gate (Vale)** — when a project arms Vale (`brew install vale`
  / GitHub release) with a committed `.vale.ini` + `styles/` (or scaffolded via `arm.py --scaffold-configs vale`, which also runs `vale sync`), a convergence sweep runs via
  `infra/scripts/vale_adapter.py` (shells out to `vale --format=JSON`, wraps findings into
  越权日志; advisory, severity collapsed to `warning`). A DEPTH-1 rule gate covering the
  docs-QUALITY axis: blueprint-crafting checks upstream-doc STRUCTURE (anchors +
  authority-chain) and the language arch gates lint CODE, but neither lints prose. NOT a
  hand-rolled gate — an external engine leveraged at the convergence point. See
  [external-skills.md](external-skills.md).
- **External-skill breaking-change gate (oasdiff)** — when a project arms oasdiff
  (`brew install oasdiff`), a convergence sweep runs via `infra/scripts/oasdiff_adapter.py`
  (shells out to `oasdiff breaking --format json`, diffs each tracked OpenAPI/Swagger spec
  against its git HEAD version, wraps findings into 越权日志; advisory, severity collapsed to
  `warning`). The BACKWARD-COMPAT axis — complementary to Spectral (spec style) and
  `arch_contract_api.py` (presence/path), neither of which diffs versions. NOT a hand-rolled
  gate — an external engine leveraged at the convergence point. See
  [external-skills.md](external-skills.md).
- **External-skill license gate (Trivy)** — when a project arms Trivy (`brew install trivy`),
  a convergence sweep runs via `infra/scripts/license_adapter.py` (shells out to
  `trivy fs --scanners license --format json`, wraps findings into 越权日志; advisory, severity
  collapsed to `warning`). The LEGAL/COMPLIANCE axis — complementary to
  `arch_contract_deps.py` (secrets + dependency CVEs, NOT licenses). Without a project policy
  the output is a raw inventory. NOT a hand-rolled gate — an external engine leveraged at the
  convergence point. See [external-skills.md](external-skills.md).
- **External-skill IaC gate (Checkov)** — when a project arms Checkov
  (`brew install checkov` / `pip install checkov`), a convergence sweep runs via
  `infra/scripts/iac_adapter.py` (shells out to `checkov --directory <root> --output json`,
  wraps findings into 越权日志; advisory, severity collapsed to `warning`). The INFRA-CONFIG
  axis — opt-in for infra-bearing projects (no-op when no Terraform/K8s/Dockerfile; out of the
  app-language platform model `platforms.json` — an external-skill gate, NOT a platform). NOT a
  hand-rolled gate — an external engine leveraged at the convergence point. See
  [external-skills.md](external-skills.md).

All degrade per-tool to a no-op with an explicit `coverage` note (never a silent green). See `infra/schemas/violation-log.schema.json` for the shared emission contract.

## When to run it

At the inner convergence point — after the fast gate is clean across the changed set and before the outer ring. It is heavier (needs full context) so it is NOT a per-edit tools/post-execute hook. The orchestrator invokes it explicitly:

```bash
python3 infra/scripts/arch_contract_python.py [package]
```

Exit 0 + no blockers -> proceed to the outer ring. Exit 1 -> fix in the inner ring, re-run. Never enter the outer ring on a red architecture-contract gate.

## Structured feedback contract

Findings carry `file:line` and a concrete `suggestion`. The outer reviewer and the Coder consume this as a Blocker signal, not a vague "not elegant" note.

The emission shape is formalized in `infra/schemas/violation-log.schema.json` — `{gate, passed, coverage[], findings[{severity, rule, file, line, detail, suggestion}]}` with `severity ∈ {blocker, warning}`.
Every arch gate MUST conform; `infra/test/smoke_gates.py` validates each gate's real output against it via the stdlib validator in `infra/test/violation_log_schema.py` (no external dep).
Adding a field is a deliberate schema change, not a silent `emit()` edit.
