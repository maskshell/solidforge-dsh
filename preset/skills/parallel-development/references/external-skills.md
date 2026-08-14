# External-Skill Integration

How an external (black-box) skill plugs into the convergence loop. External skills are engines we invoke but do not own; the contract is artifact+invocation based, never internal-wiring based. The first registered instance is **Impeccable** (`pbakaus/impeccable`). Decisions: ADR #21 in [design-decisions.md](design-decisions.md).

## The contract (one column per external skill)

| Field | Impeccable | Spectral |
| --- | --- | --- |
| `skill_ref` | `impeccable` — install via `npx impeccable install` | `spectral` — `brew install spectral-cli` (or `npm i -g @stoplight/spectral-cli`) |
| `skill_domain` | UI/UX (visual) design governance | API-contract (OpenAPI) ruleset compliance |
| `artifact` | `DESIGN.md` (+ `PRODUCT.md`); DESIGN.md frozen at Phase 0 via side-car sentinel | the OpenAPI/Swagger spec (`openapi.{json,yaml}` / `swagger.*`); frozen at Phase 0 via side-car sentinel (Depth 2) |
| `consumption` | a `visual_ref` pointer (DESIGN.md path) in the Intent Blueprint; tokens/components/a11y flow into the NFR | the frozen spec is the authoritative API contract; `agents/backend-developer.agent.md` codes against it |
| `gate` | Impeccable 44-rule detector: tools/post-execute hook (per-edit advisory) + convergence `detect.mjs --json` sweep → 越权日志 | Spectral CLI `-f json` convergence sweep via `infra/scripts/spectral_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`) |
| `implementer_role` | `agents/frontend-developer.agent.md` (faithful DESIGN.md consumption; no library-default substitution) | `agents/backend-developer.agent.md` (faithful frozen-spec consumption) |
| `review_augment` | `/impeccable critique` (scored) + `audit` | `spectral lint` findings → outer ring; complementary to `arch-contract-api` (presence/path) |
| `maturity_tier` | 44 rules deterministic; Claude Code hook surfaces advisory (non-blocking); loop treats design findings advisory by default, opt-in strict | `spectral:oas` ruleset deterministic; advisory (non-blocking); opt-in strict is a Future side-car |
| `coverage_gap` | visual fidelity beyond the 44 rules + runtime a11y → outer-ring (`critique` / `audit`) | Spectral error/info levels collapse to `warning` (schema enum); does NOT verify code matches spec (`arch-contract-api` + contract tests) |

Spectral reuses the same four-seam model as Impeccable (artifact producer = author the OpenAPI spec; gate = `spectral_adapter.py`; implementer = `backend-developer`; review = findings → outer ring). Its Depth-2 freeze uses a side-car sentinel mirroring DESIGN.md's — see ADR #23 and the `openapi` anchor kind in `blueprint_guard.py`.

## Depth-1 advisory rule gates (no per-feature frozen anchor)

External-skill linter gates at the convergence point whose **ruleset is repo-wide config** — they have NO per-feature frozen artifact (unlike Impeccable's DESIGN.md or Spectral's OpenAPI spec), so no `blueprint_guard` anchor kind and no implementer-against-anchor seam. Same adapter shape as Spectral, minus the freeze; advisory (never `blocker`); no-op with a coverage note when not armed.

### Semgrep (source SAST)

- `skill_ref` — `semgrep`; `brew install semgrep` (or `pip install semgrep`).
- `skill_domain` — source SAST: CVE-pattern code (OWASP top-ten, injection, path-traversal, hardcoded-credential patterns, weak crypto, unsafe deserialization, ...).
- `ruleset` — a committed `.semgrep/` dir or `semgrep.yml` (offline-deterministic); `--config auto` fallback fetches the Semgrep registry (network, cached).
- `gate` — `semgrep --json --config <ruleset>` convergence sweep via `infra/scripts/semgrep_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`).
- `complementary_to` — `/security-review` (LLM review, semantic) + `arch_contract_deps.py` (leaked secrets + dependency CVEs). Semgrep is the SOURCE-code SAST axis — a different layer; do not delete the others for it.
- `coverage_gap` — ERROR/WARNING/INFO collapse to `warning` (schema enum); SAST is false-positive-prone → advisory review input, never an auto-Blocker; secrets-in-history + dependency CVEs stay `arch-contract-deps`.

### Vale (docs / prose)

- `skill_ref` — `vale`; install via `brew install vale` / GitHub release.
- `skill_domain` — docs/prose quality: terminology, voice, spelling, inclusiveness.
- `ruleset` — a committed `.vale.ini` + `styles/` (REQUIRED — Vale styles are opinion, no objective default; no config → no-op with a coverage note).
- `gate` — `vale --format=JSON` convergence sweep via `infra/scripts/vale_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`).
- `complementary_to` — blueprint-crafting (which checks upstream-doc STRUCTURE — anchors + authority-chain — not prose quality) + the language arch gates (which lint CODE). Vale is the prose-QUALITY axis.
- `coverage_gap` — suggestion/warning/error collapse to `warning` (schema enum); requires `.vale.ini`; technical accuracy / example correctness / link validity → outer ring (Vale is prose-style only).

### oasdiff (API breaking-change)

- `skill_ref` — `oasdiff`; install via `brew install oasdiff`.
- `skill_domain` — API-contract breaking-change detection: diffs the working OpenAPI/Swagger spec against its git HEAD version (removed required fields, changed types, deleted endpoints, dropped response codes).
- `ruleset` — none (it diffs two spec versions; the base is git HEAD, not a committed config).
- `gate` — `oasdiff breaking --format json <git-HEAD-base> <working>` per tracked spec via `infra/scripts/oasdiff_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`).
- `complementary_to` — Spectral (spec STYLE) + `arch-contract-api` (presence/path). oasdiff is the BACKWARD-COMPAT axis — neither of the others diffs versions.
- `coverage_gap` — only diffs specs tracked in git (a brand-new spec has no base → skipped with an explicit note, not a silent green); advisory (a breaking change may be intentional, e.g. a major-version bump) — never `blocker` by default.

### license (dependency license compliance)

- `skill_ref` — `trivy` (license mode); install via `brew install trivy`.
- `skill_domain` — dependency license compliance: scans lockfiles/dep manifests for a license inventory (GPL/AGPL/copyleft, unknown licenses).
- `ruleset` — none mandatory; a project policy (allow/deny list) makes findings actionable.
- `gate` — `trivy fs --scanners license --format json` convergence sweep via `infra/scripts/license_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`).
- `complementary_to` — `arch-contract-deps` (secrets + dependency CVEs — NOT licenses). License is the LEGAL/COMPLIANCE axis.
- `coverage_gap` — Trivy is security-scanner-shaped (license is one mode); without a policy this is a raw INVENTORY (noisy); per-license severity is advisory (license policy is opinion, not a code defect); copyleft/compatibility analysis is legal judgment → outer ring.

### iac (infrastructure-as-code misconfig)

- `skill_ref` — `checkov`; install via `brew install checkov` / `pip install checkov`.
- `skill_domain` — IaC misconfig: Terraform / Kubernetes / Dockerfile misconfiguration (open S3 buckets, permissive security groups, missing versioning/logging, privileged containers).
- `ruleset` — checkov's built-in framework policies (auto-detected); customizable via `--check` / `--skip-check`.
- `gate` — `checkov --directory <root> --output json` convergence sweep via `infra/scripts/iac_adapter.py` → 越权日志 (advisory; severity collapsed to `warning`). No-op when no IaC files present.
- `complementary_to` — the app-language arch gates (clippy/checkstyle/swiftlint/eslint lint CODE; IaC files are outside that model). iac is the INFRA-CONFIG axis.
- `coverage_gap` — only fires when IaC files present (out of the app-language platform model `platforms.json` — an external-skill gate, not a platform); checkov findings are file-level (line often absent → 0); advisory (IaC misconfig is context-dependent, false-positives common); does NOT cover runtime/cloud misconfig (outer ring).

## The four seams (Impeccable operates each)

- **A — artifact producer.** `/impeccable init` + `document` + `extract` + `shape` (and its `asset-producer` subagent) produce `PRODUCT.md` + `DESIGN.md`. The loop freezes `DESIGN.md` at Phase 0 → the convergence anchor.
- **B — design gate.** Impeccable's tools/post-execute detector hook = the per-edit design gate (advisory, auto-installed). PLUS a convergence sweep: `detect.mjs --json` → 越权日志 (see adapter below).
- **C — implementation.** `frontend-developer` implements from the frozen `DESIGN.md` under the existing gates. Use `/impeccable shape` (design plan) + `frontend-developer` (impl); do NOT use `/impeccable craft` in-loop (shape→build is reflexive). `polish` / `bolder` / `quieter` / `animate` (refinement of existing code) are fine as gated ops.
- **D — review.** The reviewer visual line is augmented by `/impeccable critique` (scored) + `audit`. Verdict `visual-drift`; default advisory rewrite, opt-in `enforcement: strict` → hard rollback. (`enforcement` is a loop-controlled side-car signal — NOT a DESIGN.md field; DESIGN.md's frontmatter is Impeccable-owned. It rides the same sentinel as the freeze; see below.)

## DESIGN.md freeze — side-car sentinel (not frontmatter)

`DESIGN.md`'s frontmatter is an Impeccable token-export (`colors` / `typography` / `components`) with NO `status` field, so `blueprint_guard`'s frontmatter-`status` check would not fire. The `design` anchor kind in `blueprint_guard.py` recognizes `**/DESIGN.md` and denies edits while a SIDE-CAR sentinel is set (a loop-state flag or `.design.frozen`), set at Phase 0, cleared at converge. This is the first anchor whose freeze signal is not its own frontmatter (ADR #21) — it decouples the freeze from content Impeccable may regenerate (`document` / `extract`).

## detect --json → 越权日志 adapter (`infra/scripts/impeccable_detect_adapter.py`)

The convergence-point design gate is `impeccable_detect_adapter.py` — a thin sibling gate (like `arch_contract_api.py`) the orchestrator runs at convergence. It shells out to the ARMED detector (`.solidforge/skills/impeccable/scripts/detect.mjs --json` — a Claude Code companion; in DSH this degrades to a coverage-noted no-op until an equivalent exists) WITHOUT `--no-config` (so detect loads the frozen DESIGN.md as context and cross-checks implementation tokens against it — e.g. a color not in the palette surfaces `design-system-color`), then wraps the bare array into 越权日志.

`detect.mjs --json` emits a BARE JSON ARRAY of findings, each `{antipattern, name, description, severity, file, line, snippet}` (verified empirically — `severity` IS present, e.g. `"warning"`; `name` is the human rule name; `line` may be null for file-level findings; empty → `[]`; exit 2 = findings present, 0 = none). The convergence adapter:

- wrap into `{gate:"impeccable-detect", passed:true, coverage, findings[]}` (passed stays true — all advisory);
- `antipattern → rule`, `name` folds into detail, `file → file`, `line → line ?? 0`, `description → detail`;
- INHERIT `severity` (e.g. `"warning"`) from the finding — do NOT overwrite (the source carries it);
- optionally synthesize `suggestion` from `name`/`antipattern` → the matching `/impeccable` command;
- treat exit 2 as "findings present", not a blocker — pass/fail from the parsed JSON.

`detect` loads the local `DESIGN.md` / `design.json` as context by default (`--no-design-system` skips) — it already cross-checks the design system.

## Adding another external skill

External skills do NOT touch `platforms.json` (that models languages we own). Add: a row in the contract table above; freeze its artifact under a `blueprint_guard` anchor kind with a side-car sentinel (if its frontmatter is not ours); reuse or add a gate (wrap its deterministic detector if it has one); map its commands to the four seams; add an ADR if non-obvious. No `disconnect_check` edit — this doc is the registry for external skills.

## Coverage gaps (rule 3 — never silently green)

- Visual fidelity beyond the 44 deterministic rules is NOT enforced — outer-ring (visual line + `critique`).
- detect findings carry NO `suggestion` (the adapter synthesizes/omits it); `severity` IS present (inherited, not assigned). Some findings are file-level (no line → 0).
- Runtime a11y is `/impeccable audit` + outer-ring/test-gate, not the detector.
