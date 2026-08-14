# The paper: vendored snapshot

This directory carries a **verbatim snapshot** of the paper *Specification Gaming as an
Orthogonal Failure Axis in Autonomous Coding Loops* so the repo is self-contained and
citable even before the paper lands on arXiv.

## Artifacts

| File | Role |
| --- | --- |
| `spec-gaming-orthogonal-axis.md` | Text authority (canonical snapshot, copied verbatim; `last_updated: 2026-08-07` in its frontmatter) — diffable, reviewable, searchable |
| `spec-gaming-orthogonal-axis.pdf` | The citation artifact — built from the text via LaTeX on 2026-08-07, after the last text edit |
| `spec-gaming-orthogonal-axis.tex` | LaTeX source of the PDF (GENERATED from the text; rebuildable — the .md is the authority) |
| `spec-gaming-orthogonal-axis.pub-readiness.md` | Publication-readiness review + proposed fixes (2026-08-06; context, not part of the paper) |

### Provenance trails (the paper dogfooded on itself)

The paper's own convergence/verification history, published so every status claim in it is
auditable — the same transparency rule the upstream reference implementation applies to its
skill docs:

| File | Role |
| --- | --- |
| `spec-gaming-orthogonal-axis.convergence.json` | The paper's csr convergence record (4-round reconvergence of 2026-07-31, schema-validatable) |
| `spec-gaming-orthogonal-axis.loopx-reconvergence.json` | The LoopX-amendment reconvergence delta (§7 peer paragraph + §4.4 control-plane note) |
| `loopx-research.md` + `loopx-research.psv/coverage-record.json` | The LoopX evidence trail the reconvergence record cites (psv N31/W12/R3 coverage) |
| `spec-gaming-orthogonal-axis.pub-readiness.csr/` | The readiness review's own csr + psv + prior-art-collision records (per-round findings included) |

## Canonical source & drift rule

The **canonical source** remains the author's knowledge base:
`~/dev/ws-wiki/fedaot-kb/docs/papers/spec-gaming-orthogonal-axis.md` (its convergence /
verification trails live beside it: `.pub-readiness.csr/`, `.loopx-reconvergence.json`, …).

This snapshot is updated **only by an explicit sync step** — never silently. (One referenced
draft file, `loopx-amendment.md`, no longer exists in the KB — its content was merged into
the paper text, which the reconvergence record itself documents.)

```bash
bash scripts/sync-paper.sh    # re-copies md/pdf/tex/readiness from the canonical KB and reports freshness
```

## Citation

Use the repo's [`CITATION.cff`](../../CITATION.cff) (GitHub's "Cite this repository").
The stable link is the PDF permalink (owner placeholder until the repo is created):

```
https://github.com/maskshell/solidforge-dsh/raw/main/docs/papers/spec-gaming-orthogonal-axis.pdf
```

**The paper is a draft (frontmatter status: `draft-cross-source-converged`). Cite it with
the version date (2026-08-07) or the snapshot commit — not as a published work.** If/when
it lands on arXiv, update `CITATION.cff`'s `url`/`doi` to the arXiv version (which then
becomes canonical) and keep this snapshot as a mirror.
