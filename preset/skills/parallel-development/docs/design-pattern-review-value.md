# Design-Pattern Review of This Workspace's Code — Value Analysis

> Status: **Analysis + methodology recommendation (no code change).** Answers
"is a software-engineering design-pattern review of this workspace's own code
worth doing, and if so, against what rubric?" Grounded in a verified
fact-profile of the code under review (64 real Python files, ~19,560 LOC, zero
`class` definitions). Concludes that the GoF 23-pattern rubric is the wrong
instrument here and names the three audit-shaped reviews that ARE worth doing.
Goes through its own different-family adversarial review loop (ADR #40) — see
Appendix A.
>
> Scope: the workspace's own code (`skills/*/infra/**`, `install/arm.py`). NOT a
review of host projects that consume the skills. NOT a code change.
> Companion rubric: [CLAUDE.md](../CLAUDE.md) workspace rules (esp. 1, 3, 4, 5,
7, 8, 10) +
[references/extending.md]
(../skills/parallel-development/references/extending.md)
(§ Self-application; per-language formula) +
[references/design-decisions.md]
(../skills/parallel-development/references/design-decisions.md)
(ADRs #11/#15/#16/#37/#38/#39/#40/#41).

## Context (fact profile of the code under review)

Verified facts (grep-counted this session) are distinguished from asserted
characterizations below. The "code" in this workspace is NOT a conventional OOP
application.

Verified (grep-counted):

- Real Python source: **64 files, 19,560 LOC**, all under `skills/*/infra/`
  - `install/`. The 1,900+ other `.py` files on disk are `.venv` dependencies
  (noise, excluded). No real source exists outside `skills/*/infra/` —
  `agents/`, `commands/`, `workspace/`, and the top-level `hooks/` carry no
  `.py`. The 64 files span TWO skills with distinct architectures:
  - `skills/parallel-development/infra/` — **43 files**. Adapter /
    per-language-dispatch / lifecycle (the patterns analyzed in D2). This
    skill is the convergence-loop orchestrator.
  - `skills/blueprint-crafting/infra/` — **21 files** (7 scripts + 14
    tests). A staged **pipeline** architecture (`normalizer.py` →
    `plan_model.py` → `constraints_check.py` → `freeze.py` → `produce.py` +
    `verdict.py` + `research_constraints.py`). Its pattern set differs from
    parallel-development's and is out of scope for the D2 analysis below.
- **Zero `class` definitions** across the entire real tree (`grep -rn
  "^class " skills/*/infra/` returns nothing). No inheritance, no
  polymorphism, no ABCs.
- Physical layout: `infra/install/` (1 file), `infra/hooks/` (4),
  `infra/scripts/` (29), `infra/test/` (30).

Asserted characterizations (verified in part; citations in D2):

- Style is procedural + functional: scripts emit and parse JSON.
- Cross-script import is deliberately minimal. Test scripts load the module
  under test by THREE different strategies (this heterogeneity is itself an
  input to the D3 consistency audit, not a uniform pattern):
  - `importlib.util.spec_from_file_location` — `arm_copy_config.py`,
    `arm_report_gates.py`, `arm_revert.py`, `scope_check.py`,
    `arch_deps_parsers.py`, `arch_tests_parsers.py` (load a specific `.py` as
    a module).
  - `sys.path` manipulation + direct import — `plan_queue_detect.py`
    (`import plan_queue as pq`).
  - `subprocess.run` (process-level isolation) — `hetero_review_wiring.py`
    (drives the different-family wrapper as a real subprocess).
- `infra/scripts/` subdivides by role into three sub-families:
  - **Adapter** — 7 files `*_adapter.py` (`semgrep`, `vale`, `spectral`,
    `oasdiff`, `iac`, `license`, `impeccable-detect`): each wraps a
    heterogeneous external tool and normalizes its output into the
    violation-log schema.
  - **Per-language dispatch** — 9 files `arch_contract_*.py` (6 languages
    `python/rust/java/swift/web/go` + 3 helpers `deps/api/tests`): one
    strategy per language for the architecture-contract gate.
  - **Lifecycle + util** — `loop_state.py`, `plan_queue.py`,
    `hetero_review.py`, `scope_check.py`, `snapshot.py`, and the rest.
- **Workspace rule 7 (`CLAUDE.md`)** mandates the **self-contained-script
  convention**: each gate duplicates `run` / `have` / `emit` /
  `find_marker_dirs` rather than importing a shared library, so each script
  stays independently deployable. This
  duplication-for-independent-deployability is a deliberate design choice
  (rule 7), not an oversight.

## Decision (core judgement)

**The GoF 23-pattern rubric is the wrong instrument for this code, and applying
it is net-negative.** The three audit-shaped reviews below are what is actually
worth doing.

### D1 — Do NOT run a GoF design-pattern review (misapplied here)

Scope note: this analysis narrows "design-pattern review" to the **GoF
23-pattern taxonomy**, because that is the framing most commonly meant by the
request. Other taxonomies (POSA, functional-programming patterns,
pipeline/stream patterns, cloud design patterns) are out of scope here and may
warrant their own analysis. The conclusion below does not extend to them.

GoF's 23 patterns almost universally presuppose **object-orientation + class
inheritance + mutable state**. Each pattern anchors on a substrate this codebase
lacks:

- Strategy / Template Method / State need a class hierarchy or an abstract
  base class.
- Observer / Decorator / Command need mutable object state or a long-lived
  object graph.
- Factory / Singleton / Builder need object construction as a first-class
  concern.

This codebase has `class == 0`, so a reviewer working from the GoF rubric has
nowhere to land. The path of least resistance is to *fabricate* the substrate
the rubric expects: recommend "abstract the gate scripts into an `AbstractGate`
base class with per-language subclasses." That recommendation directly
**violates workspace rule 7** (the self-contained-script convention is
deliberate, for independent deployability). The review would pay its own cost in
induced damage.

### D2 — "Design pattern" ≠ GoF; real patterns here are rule-codified

Scoped to `skills/parallel-development/infra/` (the larger of the two skills and
the one whose Adapter / Registry / Strategy patterns are in question).
`skills/blueprint-crafting/infra/` runs a staged pipeline (`normalizer →
plan_model → constraints_check → freeze → produce`) — a different pattern set,
not covered here.

A broader reading of design principles finds patterns that are real, correct,
and already enforced by the workspace's own machinery. Each is cited to its
source below. "Apply the pattern to find an improvement" finds nothing here,
because the improvement is already a gate or a registry entry:

- **Adapter** — 7 files `infra/scripts/*_adapter.py` (`semgrep_adapter.py`,
  `vale_adapter.py`, `spectral_adapter.py`, `oasdiff_adapter.py`,
  `iac_adapter.py`, `license_adapter.py`, `impeccable_detect_adapter.py`):
  each normalizes a heterogeneous external tool's output into the
  violation-log shape. In use, not latent.
- **Registry / data-driven dispatch** — `infra/test/platforms.json` is the
  single source of truth for per-language requirements; consumed by
  `infra/test/disconnect_check.py` (the checker). `infra/install/arm.py` is
  NOT a registry consumer — it carries its own hardcoded `ARCH_CONFIGS`
  predicates (ADR #18), and `disconnect_check.py` cross-checks the two for
  consistency (it greps `arm.py`'s module for the substrings `platforms.json`
  lists). Workspace rule 2 mandates "add a capability by updating the
  registry; never edit the checker."
- **Strategy / per-language dispatch** —
  `infra/scripts/arch_contract_{python,rust,java,swift,web,go}.py` (6
  strategies) plus 3 helpers (`arch_contract_deps.py`, `arch_contract_api.py`,
  `arch_contract_tests.py`): a strategy family indexed by language.
- **Shared contract / convention-over-configuration** —
  `infra/schemas/violation-log.schema.json` +
  `infra/schemas/run-record.schema.json` are the single output contract every
  gate emits.
- **Graceful degradation / fallback** — every `arch_contract_*.py` (all 9
  files) carries a coverage/no-op path for when its external tool is absent
  (rule 3); it emits an explicit `coverage` note and never fakes a green. ADR
  #41 extends this pattern to the different-family wrapper's substrate errors:
  a recoverable CC cap (budget / turns / overwhelmed) degrades rather than
  corrupting the verdict, with the subtype persisted as a fingerprint.
- **Procedural state machine / subprocess wrapper** — the Lifecycle+util
  sub-family: `loop_state.py`, `plan_queue.py`, `snapshot.py` each operate
  over JSON files via append-only state transitions. These ADRs cover
  different layers of that machine, not a single wiring: the append-only
  `events[]` log is ADR #11; the terminal DoD invariant at `mark-converged` is
  ADR #16; the plan-queue → loop_state hook integration is ADR #37;
  inline-mode bookkeeping discipline is ADR #39. `hetero_review.py` wraps a
  cross-provider subprocess (ADR #40). `scope_check.py` is a separate shape —
  a post-hoc git-diff belonging check (ADR #15), not a state machine; it
  appears in the Context importlib list above.

### D3 — Worth doing: three AUDIT-shaped tasks (finding drift, not patterns)

1. **Consistency audit of the self-contained convention (highest value).** Rule
7's "each gate duplicates `run`/`have`/`emit`/`find_marker_dirs`" is a
deliberate independence-vs-DRY trade-off. The question worth answering is where
that trade-off has drifted: which duplications are genuinely required for
independent deployability, and which have copy-paste-diverged — a bug fixed in
one site but not its siblings. This is hunting for drift, not hunting for a
missing pattern.
2. **Adapter-family shape alignment.** Do all `*_adapter.py` follow the same
shape (input → normalize → emit violation-log)? Has any one taken a shortcut
that breaks the contract? This is the domain of a contract / shape test, not a
GoF review.
3. **Per-language capability-matrix alignment.** Across the six
`arch_contract_*.py`, is the detection capability matrix aligned, or does one
language silently lack a check that another has (which would violate rule 3's
"never silently green")? This is what `extending.md`'s registry exists to
govern.

### D4 — Dogfooding the loop on our own code: partial-fit review mode

This workspace ships an architecture-review framework (the convergence loop +
the architecture-contract gate + the L1 constitution). Commit `277f58b` ("arm
the workspace for its own convergence loop (dogfood)") states the intended mode.
But "use our framework because it is ours" would be circular, so the fit must be
argued independently. The convergence loop was designed for multi-module
codebases with layer-isolation, dependency-direction, and concurrency
constraints, which means only SOME of its axes land on this code:

- **Apply** — the L1 constitution's non-codable red lines that do not
  presuppose OOP: abstraction-altitude (a helper must not leak domain logic
  into a generic utility), naming-intent (a name that contradicts behavior is
  a Blocker), no-emergent-coupling, no-delete-the-error fixes.
- **Vacuous here** — the layer-isolation and dependency-direction gates
  (`.importlinter.ini` / dependency-cruiser) have no substrate, because there
  is no module graph to speak of when `class == 0` and cross-script import is
  near-zero. The concurrency baseline is likewise near-vacuous for
  single-threaded gate scripts.

So the fit is partial: the convergence loop reviews THIS code along its naming /
abstraction / no-delete-the-error axes (the L1 residue), and contributes nothing
along its layer / dependency / concurrency axes (honestly empty, not
misapplied). That is still a better ruler than GoF for this code, because the
ruler is self-defined and its vacuous axes are empty rather than fabricated.
GoF, by contrast, fabricates a substrate (D1).

This partial-fit verdict independently confirms [extending.md §
Self-application](../skills/parallel-development/references/extending.md), which
reached the same conclusion ("the heavy L4 mechanisms are ill-fitting and
degenerate for self-edits ... there are no layers to enforce") from the L4
capacity/demand side. The two analyses cross-validate rather than duplicate each
other.

Concretely, "dogfood the convergence loop" does NOT mean running the full
hook-enforced loop on the skill source — the hook-enforced outer shell does NOT
self-apply (gates are opt-in + project-scoped, never onto the skill source;
`extending.md:145`). The correct self-edit practice (`extending.md:149`) is: run
the four deterministic self-gates (`disconnect_check` / `smoke_gates` /
`run_record` / `lint_self`), then one manual outer-ring `code-reviewer` pass on
the final diff. The full convergence loop is reserved for the host projects the
skill operates on, not for the skill itself.

## Why

- **GoF is the wrong ruler because its substrate (OOP + inheritance +
  mutable state) is absent** (`class == 0`). A rubric whose patterns have no
  anchor points produces either "nothing to say" or fabricated substrate — and
  fabrication here means rule-7 damage.
- **The broader patterns are already codified** (Adapter / Registry /
  Strategy / shared-contract / degradation), so a pattern-application review
  has no discovery surface — the patterns are not latent, they are gates and
  registries.
- **The anti-DRY duplication is a deliberate trade-off** (independent
  deployability vs DRY), so the right question is "where has the trade-off
  drifted," not "where should we DRY it up."
- **The three audit reviews map onto the workspace's own working method**
  (rule 1: a skill's self-gates are the definition of done; rule 5: a
  capability → update every enumeration → registry): a systematic finding's
  correct home is a new gate or a registry row, not a one-off review report.

## Rejected

- **Run a GoF design-pattern review.** Wrong substrate (`class == 0`);
  induces rule-7 violations. See D1.
- **"Abstract the gate scripts into a shared base class."** Directly
  violates rule 7's self-contained-script convention. Rejected at the design
  level, not just for this review.
- **Treat the output as a one-off review report.** Rejected: a finding that
  is systematic should become a gate or a registry entry (rule 1 / rule 5),
  not a document that decays.
- **Apply GoF selectively to the few places that resemble OOP.** Tempting
  but still misframed: the few state-bearing sites (`loop_state.py`,
  `plan_queue.py`) are procedural state machines over JSON files, not object
  graphs; the useful lens there is "state-transition correctness + schema
  honesty," not GoF roles.

## Recommended next actions (operational)

- Do NOT commission a GoF-pattern review of this workspace's code.
- If a "software-engineering design" pass is wanted, scope it to the three
  audits in D3 (consistency / adapter-shape / capability-matrix), as
  consistency audits, not pattern application.
- Where an audit surfaces a SYSTEMATIC gap, convert it to a gate or a
  registry row (rule 1 / rule 5), not a report. Two concrete candidate gates,
  if the audits confirm the gaps:
  - a **copy-paste-drift gate** across the
    `run`/`have`/`emit`/`find_marker_dirs` duplication (consistency audit #1),
    and
  - an **adapter-shape contract test** across `*_adapter.py` (consistency
    audit #2).
- For the workspace's own code quality, follow `extending.md:149`'s
  self-edit practice: run the four deterministic self-gates
  (`disconnect_check` / `smoke_gates` / `run_record` / `lint_self`) plus one
  manual outer-ring `code-reviewer` pass. Do NOT run the full hook-enforced
  convergence loop on the skill source (it does not self-apply;
  `extending.md:145`), and do not import an external GoF ruler.

## Appendix A — different-family adversarial review record

This document is going through the different-family (different-family)
adversarial review loop (ADR #40), using `infra/scripts/hetero_review.py` with
the DeepSeek profile. The loop is orchestrator-driven: same-family primary (the
author) writes; the different-family leg hunts what the primary missed or got
wrong; the primary responds per round; a round cap bounds the count of
different-family invocations.

Findings trend across rounds: 6 → 3 → 3 → 1 → 2 → 2 → 2. Verdict `pass` on
rounds 1, 4, 5, 7; `rewrite` on rounds 2, 3, 6. The substantive blockers — a
factual error introduced in v2 (round 2), a contradiction with the companion
rubric (round 3), a scope error that homogenized two skills (round 3) — all
landed in the document body and were fixed; round 6's blocker (a numerical slip
in this appendix) and warning (ADR grouping conflation on the state-machine
bullet) were both fixed in v7. The different-family leg caught what same-family
review missed at every round, which is exactly the complementary value ADR #38 /
ADR #40 predicts for doc-shaped artifacts, and the empirical grounds for this
document's own D-series conclusions.

Per-round record (primary response = document revision):

- **Round 1** — verdict `pass`, 6 warnings: circular-reasoning in D4;
  framing-conflation (GoF vs other taxonomies); evidence-asymmetry (D2
  uncited); overclaimed "verified" heading; rule-10 prose (em-dash /
  parenthetical carrying load-bearing logic); terminology drift ("Anti-DRY").
  Run-record: `runs/hetero-dpr-review-20260707T024527Z.json`. Primary
  response: v2 — rewrote Context (precise taxonomy, dropped the
  colloquialism), split D1 into bullets + a scope note, added file-path
  citations across D2, re-argued D4's fit independently.
- **Round 2** — verdict `rewrite`, 1 blocker + 2 warnings. Blocker: the v2
  `importlib.util` claim was factually wrong (there are three isolation
  strategies, not one). Warnings: D4 missed the extending.md §
  Self-application cross-reference; D2 left Lifecycle+util uncited.
  Run-record: `runs/hetero-dpr-review-20260707T025520Z.json`. Primary
  response: v3 — corrected the three isolation strategies with verified file
  lists, added the Lifecycle+util citation, added the extending.md
  cross-reference.
- **Round 3** — verdict `rewrite`, 1 blocker + 2 warnings. Blocker: "dogfood
  the convergence loop" contradicts `extending.md:145` (the hook-enforced
  outer shell does not self-apply). Warnings: ADR #41 listed in the rubric but
  never cited; scope homogenized parallel-development + blueprint-crafting.
  Run-record: `runs/hetero-dpr-review-20260707T030308Z.json`. Primary
  response: v4 — replaced the dogfood recommendation with `extending.md:149`'s
  self-edit practice (four self-gates + one code-reviewer pass), cited ADR #41
  on degradation, split the fact-profile by skill, and scoped D2 to
  parallel-development.
- **Round 4** — verdict `pass`, 1 warning: `scope_check.py` miscited as a
  state machine (ADR #15 is a belonging check; ADR #11 is the append-only
  events source). Run-record: `runs/hetero-dpr-review-20260707T031303Z.json`.
  Primary response: v5 — moved `scope_check.py` out of the state-machine
  bullet and cited ADR #11 for append-only events.
- **Round 5** — verdict `pass`, 2 advisory warnings (editing-level): tense
  inconsistency in this appendix ("went through" vs "rounds pending"); the
  extending.md rubric parenthetical named the wrong section. Run-record:
  `runs/hetero-dpr-review-20260707T032539Z.json`. Primary response: v6 —
  rewrote this appendix in present tense with the per-round record populated,
  and fixed the rubric parenthetical.
- **Round 6** — verdict `rewrite`, 1 blocker + 1 warning. Blocker: the
  appendix summary said "no blocker after round 2" but round 3 had one (a
  numerical contradiction inside the appendix). Warning: the ADR #16 / #37 /
  #39 grouping on the state-machine bullet conflated three different layers.
  Run-record: `runs/hetero-dpr-review-20260707T033309Z.json`. Primary
  response: v7 — replaced the summary with the per-round verdict distribution
  and split the ADR grouping into per-layer citations.
- **Round 7** — verdict `pass`, 2 warnings. Warning (substantive): line 56
  over-claimed `platforms.json` is "consumed by arm.py" — `arm.py` carries
  hardcoded `ARCH_CONFIGS` (ADR #18), not a registry read;
  `disconnect_check.py` cross-checks the two. Warning (advisory): the appendix
  summary under-reported v7's fix scope. Run-record:
  `runs/hetero-dpr-review-20260707T034244Z.json`. Primary response: v8 —
  corrected the registry-consumer claim, completed the fix acknowledgement,
  and recorded this round.

**Convergence call (primary, after round 7).** Across 7 rounds the
different-family leg surfaced real defects at every step: 3 substantive blockers
in the document body (rounds 2-3: a factual error, a companion-rubric
contradiction, a scope error) plus per-round citation / precision findings, all
fixed. Rounds 5-7 coverage repeatedly verified the document's core claims (fact
profile, ADR citations, `extending.md` cross-references, link reachability) as
accurate. The loop is judged **substantively converged on the document body**:
the remaining findings are single-point factual spot-checks (resolvable by
direct source verification, e.g. `arm.py` above) and appendix-meta precision,
not defects in the D1-D4 argument. This is a deliberate convergence call rather
than a "zero-finding" formal convergence — a thorough adversarial reviewer can
always find finer citation imprecision, so continuing past substantive
convergence is diminishing returns (ADR #38: the outcome axis is human; rule 4:
advisory findings do not block).
