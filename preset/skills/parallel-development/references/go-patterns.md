# Go Patterns

Go project reference: detection, toolchain, parallel-conflict scenarios, and the Architecture-Contract Gate. Go uses `backend-developer` (no special agent — see [role-agent-mapping.md](role-agent-mapping.md)).

The gates assume a Go toolchain (`go`, `gofmt`) on PATH; the exact language/toolchain version is declared in `go.mod`'s `go` directive (Go 1.21+ can auto-fetch a matching toolchain via the `toolchain` directive). Go is a **strong** architecture-contract gate — the strongest of the backend languages (see [arch-contracts.md](arch-contracts.md) and ADR #36 in [design-decisions.md](design-decisions.md)).

## Project Detection

| File | Project Type | Build | Test |
| --- | --- | --- | --- |
| `go.mod` (single module) | Go module | `go build ./...` | `go test ./...` |
| `go.mod` + `go.work` | Go multi-module workspace | `go build ./...` (workspace) | `go test ./...` (workspace) |
| `go.mod` in a subdir (monorepo member) | Go module (nested) | `go build ./...` (in that dir) | `go test ./...` (in that dir) |

Detection is recursive (root OR nested subdir), so a Go backend under `backend/` next to a web frontend is detected and gated. The per-language arch gate is orchestrator-pointed at the subdir (`SOLIDFORGE_PROJECT_DIR=backend`).

## Toolchain Commands

```bash
go build ./...                 # compile + type-check (the compiler is the type checker); rejects import cycles
go vet ./...                   # static checks (printf-format, struct tags, lock copies, ...) — runs after build passes
gofmt -l <file>                # fast gate: lists files needing formatting (exits 0 — gate on NON-EMPTY stdout)
golangci-lint run              # arch gate: style + depguard layer rules (consumes .golangci.yml)
go test -race ./...            # test gate + concurrency baseline (-race = data-race detector, test-time)
govulncheck ./...              # supply-chain: reachable known vulns (cross-ecosystem gate arch_contract_deps.py)
```

## Parallel Conflict Scenarios

| File / Resource | Conflict? | Action |
| --- | --- | --- |
| Same `.go` file | Yes | Sequential |
| Different `.go`, no import coupling | No | Parallel |
| `go.mod` (`require` / `replace` / `exclude`) | Yes | Serialize; resolve once |
| `go.sum` (generated checksums) | Yes | Regenerate once after `go.mod` converges (`go mod tidy`) |
| `go.work` (workspace) | Yes | Serialize — local module overrides affect every build |
| Multi-module workspace: different member modules | No | Parallel |
| Shared `//go:generate` directive / codegen | Yes | Serialize — affects every compile |

Natural parallel boundaries: Go packages (no shared mutable state), and workspace member modules. Use `files_touched` at the package/module level for the scheduler. `go.mod` / `go.sum` are append/generated targets — multiple agents editing `go.mod` produce merge conflicts; serialize dependency-changing tasks, then `go mod tidy` once after convergence.

## Architecture-Contract Gate (Go)

The inner-ring architecture-contract gate for Go. Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_go.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_go.py
```

Checks (run in this order):

- **`go build ./...`** (built-in) — the Go **compiler** rejects cyclic imports ("import cycle not allowed") and surfaces compile errors. A failure emits one `compile-or-cycle` Blocker AND **skips `go vet`** with a coverage note. `go vet` shares the compiler's type-check front-end, so it also fails on a cycle — running both would double-report the same root cause (inflating the thrashing breaker's distinct-fingerprint count).
- **`go vet ./...`** (built-in, only if build passed) — static checks (printf-format, struct tags, lock copies, unreachable code). Parsed from text output `<file>:<line>:<col>: <message>` → Blocker findings (`rule=go-vet`).
- **`golangci-lint run --out-format=json`** (optional) — style + the **depguard** layer/dependency-direction linter. Severity maps by **`FromLinter`** (`depguard`/`govet`/`staticcheck`/`errcheck`/`typecheck` → Blocker; `gofmt`/`gofumpt`/other style → warning) because golangci-lint's per-issue `Severity` field is **empty by default**. A configured `Severity: "error"` may promote an unmapped linter to Blocker but never demote a blocker linter.

### Layer isolation: `internal/` is primary, depguard is the complement

Go has TWO complementary layer/dependency-direction enforcers:

- **`internal/` — compiler-enforced (the PRIMARY mechanism).** The `internal/` directory's visibility is enforced by the compiler: importing it from outside its parent directory tree is a **compile failure**, always on, ships with `go`. The canonical layout is `cmd/` (entry points) → `internal/` (private impl) → `pkg/` (public libs), with dependencies pointing **inward** (`cmd → internal/pkg`, never reverse). This is Go's strongest encapsulation and the foundation of layer isolation.
- **`golangci-lint depguard` — config-driven (the COMPLEMENT).** Depguard encodes the finer dependency-direction rules **between non-`internal` packages** that `internal/` cannot express (e.g. "domain must not import web"). Its rules live in the copied `.golangci.yml` (depguard v2 `rules:` shape; requires golangci-lint ≥ v1.53). Uncomment the block in `.golangci.yml` to declare your layers.

So layer isolation is **strong** even with golangci-lint absent: `internal/` + the compiler's import-cycle rejection are both built-in. Only the depguard axis degrades (with an explicit coverage note — never silently green).

### Concurrency baseline (`-race`) runs in the test gate, not here

`-race` (ThreadSanitizer-backed) is Go's canonical data-race detector, but it is **runtime/test-time, not static** — there is no static equivalent as strong as Python's sync-in-async ast scan or Swift's `-strict-concurrency` (and there is no `go vet -race`). So `-race` runs in the **test gate** (`arch_contract_tests.py` `check_go` → `go test -race -json ./...`), not this arch gate. A data race surfaces there as a failed test → Blocker (data races are undefined behavior per the Go memory model).

### Honest coverage

- `go` absent → one coverage note ("go toolchain absent — build/vet/cycle checks all skipped"), honest no-op pass.
- `golangci-lint` absent → narrower note ("depguard layer rules skipped — `internal/` structural boundary still compiler-enforced"); `go build` + `go vet` still run.
- A missing tool never yields a silent green (workspace rule 3).

### Supply-chain coverage caveat

`govulncheck` does **reachability analysis** — it reports only vulns on actual call chains, not every vulnerable dependency. That reachability analysis **cannot see reflection or dynamic-load indirect call paths** (a documented gap); such paths are an outer-ring/coverage concern.

### Sibling inner-ring gates (cross-ecosystem, same 越权日志 schema)

- `arch_contract_tests.py` — `go test -race -json ./...` (parse_go_test; `-race` is the concurrency baseline).
- `arch_contract_deps.py` — leaked secrets (gitleaks) + dependency vulnerabilities (`govulncheck`, NDJSON osv↔finding join).
- `arch_contract_api.py` — NOT Go-scoped (Java+Web frontend↔backend OpenAPI only); Go OpenAPI-codegen consistency is a future enhancement.

## Nested & mixed-language projects

Go is detected by `go.mod` anywhere in the tree (root OR a subdir), so a backend nested under `backend/` is detected and gated:

- `arm.py` copies `.golangci.yml` and lists the Go toolchain even when the backend is nested (run via `arm-tools`); `arch_contract_deps.py` / `arch_contract_tests.py` run `govulncheck` / `go test` in **each** dir holding a `go.mod` (root + nested).
- The per-language arch gate is orchestrator-pointed at the subdir:

  ```bash
  SOLIDFORGE_PROJECT_DIR=backend python3 infra/scripts/arch_contract_go.py
  ```

## --with-tools (arm)

Go gate tools are system-toolchain tools (the `go` command ships `gofmt`/`go vet`/`go build`/`-race`), not project deps in the package-manager sense. `arm.py --with-tools` (via `arm-tools --with-tools`) prints (does not auto-run):

```bash
brew install go                                              # or the official installer
brew install golangci-lint                                   # arch gate: depguard layer rules
#   alt: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
go install golang.org/x/vuln/cmd/govulncheck@latest          # supply-chain gate
go install golang.org/x/tools/gopls@latest                   # LSP (gopls)
#   fast gate gofmt + test gate `go test -race` ship with go — no install
```

`.golangci.yml` (copied to project root) declares the linters + the commented depguard layer rules; tune it to the project's L1 red lines.
