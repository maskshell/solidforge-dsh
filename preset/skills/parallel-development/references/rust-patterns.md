# Rust Patterns

Rust / Cargo project reference: detection, toolchain, parallel-conflict
scenarios, and the Architecture-Contract Gate. Rust uses `backend-developer`
(no special agent — see [role-agent-mapping.md](role-agent-mapping.md)).

## Project Detection

| File | Project Type | Build | Test |
| --- | --- | --- | --- |
| `Cargo.toml` (workspace or single crate) | Cargo | `cargo build` | `cargo test` |
| `Cargo.toml` with `[workspace]` | Cargo workspace | `cargo build` (per-member via `-p`) | `cargo test -p <member>` |

Toolchain via `rustup`. Edition (`2021` / `2024`) is declared in `Cargo.toml`
(`[package].edition`); the fast gate passes `--edition 2021` as a safe default.

## Toolchain Commands

```bash
cargo check                       # fast type-check (no codegen)
cargo fmt --check                 # formatting (fast gate, per-file)
cargo clippy --all-targets        # lint / concurrency baseline (arch-contract gate)
cargo test                        # unit + integration tests
cargo test -p <member>            # one workspace member
```

## Parallel Conflict Scenarios

| File / Resource | Conflict? | Action |
| --- | --- | --- |
| Same `.rs` file | Yes | Sequential |
| Different `.rs`, no `use` coupling | No | Parallel |
| `Cargo.toml` (`[dependencies]` / `[features]`) | Yes | Serialize; resolve once |
| `Cargo.lock` | Yes | Never edit by hand; regenerate via `cargo update` once after `Cargo.toml` converges |
| `build.rs` (build script) | Yes | Serialize — affects every crate build |
| Workspace `Cargo.toml` `[workspace.dependencies]` | Yes | Serialize |

Natural parallel boundaries: workspace members (`-∆

## Architecture-Contract Gate (Rust)

The inner-ring architecture-contract gate for Rust. Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_rust.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_rust.py [package]
```

Checks:

- Correctness / concurrency baseline — `cargo clippy --all-targets --message-format=json` (Send/Sync violations, `unsafe` misuse, obvious anti-patterns). Parsed from the JSON message stream.
- Orphaned modules (optional) — `cargo-modules` (`cargo install cargo-modules`), if installed.

HONEST GAP — Rust has NO first-class layer / dependency-direction enforcer (no import-linter / dependency-cruiser equivalent). The module graph is acyclic by compilation, but declared layering is not deterministically enforceable. This gate therefore covers only what is codable (clippy + optional cargo-modules) and explicitly reports layer-direction contracts as NOT enforced — they remain an outer-ring semantic concern. See [arch-contracts.md](arch-contracts.md).

A missing tool degrades that check to a no-op pass with an explicit coverage note — the gate is never silently green.

## --with-tools (arm)

Rust gate tools are system toolchain components, not project deps. `arm.py --with-tools` (via `arm-tools --with-tools`) prints (does not auto-run):

```bash
rustup component add clippy rustfmt      # fast gate (rustfmt) + arch gate (clippy)
cargo install cargo-modules              # optional: orphaned-module check
```

`clippy.toml` (copied to project root) tunes clippy thresholds; lint allow/deny is declared in `src/lib.rs` / `src/main.rs` via `#![deny(clippy::...)]`.
