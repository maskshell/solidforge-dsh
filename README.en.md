# SolidForge-DSH

**"Tests are green" should never equal "you got it right".** SolidForge-DSH is the DeepSeek Harness-native implementation of the reference implementation behind *[Specification Gaming as an Orthogonal Failure Axis in Autonomous Coding Loops](docs/papers/spec-gaming-orthogonal-axis.md)* (snapshotted with the repo; cite via the [PDF](docs/papers/spec-gaming-orthogonal-axis.pdf) and [CITATION.cff](CITATION.cff); the paper is a draft). It splits coding-agent reliability into **two axes** and cages both with deterministic gates, adversarial review, and heterogeneous verification.

> [中文 README](README.md) · [User Guide](USER_GUIDE.en.md) · [Paper](docs/papers/spec-gaming-orthogonal-axis.pdf) · [Port design](docs/port-design.md) · [Concept map](docs/claude-code-to-dsh-map.md) · [Dogfood trail](docs/dogfood/README-dogfood.md)

---

## The problem (30 seconds)

Autonomous coding loops have a structurally invisible failure class: **the agent writes its own tests and grades its own work.** "Green tests" merely satisfy a proxy specification the agent itself constructed — delete the failing test, rewrite the assertion to match the code, swallow the triggering exception with `try/catch`… the code can be all-green yet miss your intent entirely. Worse, **same-source review cannot reach it**: a reviewer sharing the agent's training data shares its blind spots.

SolidForge-DSH answers with two axes — both are required:

| Axis | Defends against | Mechanism |
| --- | --- | --- |
| **A · Flow-control completeness** | context rot / error compounding / goal drift | Dual-ring convergence: deterministic inner ring (per-edit fast gate + architecture-contract gate) + same-source adversarial outer ring + state-machine circuit breakers |
| **B · Verification-source decoupling** | specification gaming | The oracle judging the OUTCOME must not share your blind spots: `rightness` is a schema constant the agent cannot write (always `human_confirm_required`) + a heterogeneous review leg runs **out of process on a different model family** |

## One minute to understand

```text
Frozen Intent Blueprint ──▶ parallel implementation (TDD, subagents)
                                   │
                         ┌─────────▼──────────┐
                         │ Inner ring (deterministic)  fast gate per edit → arch-contract → extra conditions
                         │ Outer ring (adversarial)   same-source reviewer (primary) + hetero leg (opt-in, out-of-process)
                         └─────────┬──────────┘
                                   ▼
        Run record: process_converged (machine-checkable) ‖ rightness (always human_confirm_required)
```

Five sentences: **green gates prove process convergence, not correctness; correctness is confirmed by a human (or a genuinely heterogeneous oracle); spec-gaming defense is structural (schema constants, event listeners, process boundaries) — never a prompt.**

## Quick start

```bash
git clone https://github.com/maskshell/solidforge-dsh.git && cd solidforge-dsh
bash scripts/install.sh        # installs the agent preset → $DSH_HOME/.agent-presets/solidforge
```

1. Start a session on the **solidforge** preset in DeepSeek Harness;
2. Arm your target project once (arch-configs, constitution, blueprint templates, `.env.solidforge.example`):

   ```bash
   python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <your-project>
   ```

3. Say "implement X in parallel, TDD" — the convergence loop takes over: dual rings, breakers, rollback, run records, all automatic.
4. (Optional) activate the three structural plugins from a cordis session — see [User Guide](USER_GUIDE.en.md) §Activating plugins.

Step-by-step onboarding: **[USER_GUIDE.en.md](USER_GUIDE.en.md)**.

## Five core concepts (progressively)

1. **Dual-ring convergence**: the deterministic inner ring (lint/types/tests/architecture contracts) must be green before the outer ring; the outer ring is same-source adversarial review with per-finding dispositions (fix/reject/escalate), fully audited.
2. **Frozen Intent Blueprint**: PRD/architecture/acceptance criteria freeze at spec convergence; changes go through a revision channel only; a `status: frozen` guard denies edits.
3. **Process/Outcome split**: the run record strictly separates `process_converged` from `rightness` — the latter is an enum constant `human_confirm_required` that neither the agent nor the loop can write. Green never means right, structurally.
4. **Heterogeneous review**: high-stakes items can add an adversarial second opinion from a **different model family** (default: a fresh `dsh --profile headless` subprocess pinned to a heterogeneous route — same harness, different LLM, out of process; e.g. `zai-coding-cn`/GLM, `minimax-cn`/MiniMax-M3). The same-source ring always runs first; heterogeneity is additive.
5. **Circuit breakers**: repeated same-fingerprint failures → escalate to the outer ring; inner cap reached → degrade/split; budget exhausted → hard-terminate with a diagnosis. The loop never spins unbounded.

## What's in this repo

| Piece | Location | Role |
| --- | --- | --- |
| Agent preset | `preset/agent.cordis.yml` + `preset/preset.yml` | The session composition (persona + standard tools + preset-local skill mounting) |
| Five skills | `preset/skills/{parallel-development,blueprint-crafting,cross-source-review,primary-source-verification,prior-art-search}/` | The convergence loop, the specify side, document convergence (csr, process-axis), the two outcome-axis verifiers (psv/pas, per-claim against fetched sources) |
| 22 role agents | `preset/agents/*.agent.md` | Role-prompt corpus dispatched via the `subagent` tool |
| Deterministic infra | `preset/skills/*/infra/` | stdlib-only Python gates/state machine/schemas + test suites |
| Structural plugins | `plugins/*.host.js` | Tool-event gates, the rightness invariant, the hetero-review tool (activation: see the User Guide) |
| arm-tools | `preset/commands/arm-tools.md` | Project-side provisioning (Layer 2) |

## Honest disclosure

This project is evidence of **realizability**, not **efficacy** — the two-axis defense evaluation (paper §8.3) remains open. Upstream [SolidForge](https://github.com/maskshell/solidforge) is the paper's reference implementation (a Claude Code plugin); this repo is its **re-derived port** to the DeepSeek Harness (key difference: heterogeneity = a different LLM on the SAME harness via an out-of-process `dsh headless` subprocess, not importing Claude Code; see [docs/port-design.md](docs/port-design.md)). This repo's own README was converged with the ported psv→csr pipeline; the full trail (including two heterogeneous-oracle false-positive cases) is in [docs/dogfood/](docs/dogfood/).

## Verification

```bash
python3 preset/skills/parallel-development/infra/test/hetero_review_wiring.py   # wiring/breakers/hetero substrate/family guards
python3 preset/skills/blueprint-crafting/infra/test/run_record_schema.py        # the rightness constant
python3 preset/skills/cross-source-review/infra/scripts/converge_fixtures/verify.py
```

More evidence and install self-checks: [test/verification.md](test/verification.md).
