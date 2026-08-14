# L4 — definition sources (SolidForge + fedaot-wiki upstream)

> Source-of-truth index for L4 (and prerequisites, criteria, boundary, caveats). Re-aligned to the new fedaot-wiki `ai-coding-agent-maturity` (ADR #38): 4 degradations (Specification Gaming added, **orthogonal**) + **capacity/demand split** + **orthogonal verification axis**.

## fedaot-wiki upstream (the theory source — SolidForge maturity.md:8 anchors pathology here)

Three-layer split (the wiki self-describes): pathology (`ai-coding-failure-modes`) / therapeutics (`convergence-repair-loop`) / epidemiology+grading (`ai-coding-agent-maturity`). SolidForge mirrors all three in-skill.

| wiki page (fedaot-kb) | role | relation to L4 | SolidForge mirror |
| --- | --- | --- | --- |
| `ai-coding-agent-maturity` | epidemiology + grading (ULTIMATE upstream of the L1-L4 ladder) | L1-L4 table + the **FOUR** degradation definitions (Context Rot / Error Compounding / Goal Drift / **Specification Gaming** — the 4th is orthogonal to L1-L4) + **capacity vs demand split** (capacity = 3-degradation defense; fuzzy/novel/high/horizon are demand, NOT capacity) + **orthogonal verification axis** (different-family oracle; L4 = intrinsic ceiling; self-certification paradox) + "step thresholds are estimates" + "L1-L4 is an evaluation heuristic, not an industry standard" | `maturity.md` (L1-L4 ladder + 4 degradations + orthogonal axis + capacity/demand), `loop_state.py` l4 logic |
| `convergence-repair-loop` | therapeutics | four first-principles + dual-ring + intent blueprint + read-only anchor + snapshot hard-rollback + context folding + arch-contract + Phase 0-4 | `convergent-loop.md`, `intent-blueprint.md`, `arch-contracts.md` |
| `ai-coding-failure-modes` | pathology | 9 failure modes + silent failures + doom loop + 7 anti-patterns + productivity paradox + codebase cognitive debt | `maturity.md:8` pathology source |

## SolidForge in-skill (implementation + instrumented criterion)

| source | content |
| --- | --- |
| `references/maturity.md` ladder + §Orthogonal axis | L4 = 3-degradation defense under convergence (Specification Gaming orthogonal); capacity/demand split (demand ≠ capacity); verification-source decoupling (different-family oracle); L4 = intrinsic ceiling; SolidForge has no different-family-oracle gate today (future-direction gap) |
| `infra/scripts/loop_state.py:341-362` (`build_run_record`) | **the instrumented criterion** — `capacity_l4 = converged AND 3 defended` (is_l4_probe + horizon_met are DEMAND, not capacity); `provisional_verdict` enum unchanged (`not-a-probe` semantics narrowed) |
| `infra/scripts/loop_state.py:248-270` (`derive_terminal_cause`) | `terminal_cause` enum (the "converged-termination" prerequisite) |
| `infra/scripts/loop_state.py:446-453` (init subparser) | L4-probe DEMAND declaration entry (`--codebase-novelty` / `--req-clarity` / `--difficulty` / `--attended` / `--target-horizon-steps`) |
| `references/plan-driven-mode.md:200/202` | per-task = L4 kernel / chaining = L3 router boundary |
| `references/design-decisions.md` ADR #6/#13 | resource cap = `inconclusive` (not failure); step cap = capability signal |
| `references/design-decisions.md` ADR #16 | `mark-converged` refuses without `record-outer` (DoD invariant — `context_rot_defended`) |
| `references/design-decisions.md` ADR #37 | plan_queue→loop_state wiring; no plan-level L4 |
| `references/design-decisions.md` ADR #38 | **this re-alignment** — 4-degradation + capacity/demand + orthogonal-axis |
| `infra/schemas/run-record.schema.json` | l4_assessment block contract (descriptions mark capacity vs demand; enum unchanged) |
| `skills/blueprint-crafting/infra/schemas/plan-model.schema.json` | bc plan-model has `complexity`/`risk`, NO L4 descriptor — bc does not feed L4-probe demand |

## bc↔L4 tension — REVOKED (ADR #38)

The earlier analysis ("bc converges fuzzy→specd, conflicts with L4-probe `requirement_clarity=fuzzy`") is **revoked**. L4 capacity does NOT require fuzzy (fuzzy is demand, not capacity). bc→pd pipeline runs are not L4-probe-grade for a different, still-valid reason: **plan-driven = L3 router** (`plan-driven-mode.md:202`), not L4 kernel.

## Two corrections the upstream makes explicit

1. **`>60 steps` horizon is an estimate, not authoritative** — and under the new wiki, horizon is **demand** (run-lifetime), NOT capacity. `loop_state.py DEFAULT_TARGET_HORIZON=60` is a demand threshold, not a capacity gate.
2. **L1-L4 is "an evaluation heuristic, not an industry-mandated standard."**

## L4-evidenced prerequisites (ADR #38 capacity/demand split)

**Capacity (the l4-evidenced gate — demand-independent):**

1. `terminal_cause == "converged"`
2. `error_compounding_defended` (terminal_cause != "step-capped")
3. `goal_drift_defended` (terminal_cause ∈ {converged, resource-capped})
4. `context_rot_defended` (outer_reviews >= 1)

**Demand (evidence weight — NOT the gate):**

- `is_l4_probe` (novel/fuzzy/high/unattended task declaration)
- `horizon_met` (steps >= target)

All 4 capacity prerequisites hold → `l4-evidenced` (regardless of demand). Demand markers weigh the evidence (probe-grade + long-horizon = strongest), but do NOT gate the verdict.

Plus the **per-task prerequisite**: L4 evaluates a single-task run, NOT plan-driven chaining (L3 router). And `human_confirm_required=true` is unchanged (L4 = process-axis; outcome-axis correctness stays human-only).

## Source chain

```text
fedaot-wiki (theory)
  ai-coding-agent-maturity  ──→  maturity.md (L1-L4 + 4 degradations + orthogonal axis + capacity/demand)
  convergence-repair-loop   ──→  convergent-loop.md (dual ring + breaker + DoD)
  ai-coding-failure-modes   ──→  pathology
                                      │
                                      ▼
  loop_state.py build_run_record (capacity_l4 = converged + 3 defended; demand = is_l4_probe + horizon)
  plan-driven-mode.md:200/202 (per-task=L4 / chaining=L3)
  design-decisions.md ADR #6/#13/#16/#37/#38
  run-record.schema.json
```
