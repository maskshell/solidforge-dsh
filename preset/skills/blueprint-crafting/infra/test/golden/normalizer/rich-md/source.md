---
plan_id: rich-demo
---

# Rich markdown plan demo

## Iterations

| ID | Title | Complexity | Deps | DoD |
| --- | --- | --- | --- | --- |
| r-1 | scaffold | M | — | spec#r1 |
| r-2 | build core | L | r-1 | spec#r2 |
| r-3 | harden | M | r-2 | spec#r3 |

## Sequencing notes

The table above is the structured latch. Prose adds one nuance: r-3 also depends on r-1
because hardening needs the scaffold's contracts. That extra dependency is not in the
table, so it must be tagged semantic-infer (low-confidence), not latch.
