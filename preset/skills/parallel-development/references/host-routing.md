# solidforge skill routing convention (DSH port)

This project uses three solidforge skills: blueprint-crafting (bc), parallel-development (pd), and cross-source-review (csr). The snippet below is what arm-tools appends to the project's AGENTS.md.

## Self-routing

bc and pd each judge scope via their built-in Scope Guard at invocation time and self-reroute. In ecosystem terms: code implementation belongs to pd, upstream documents belong to bc. This project does not restate the skills' internal routing decisions in its own rules; the skills' own Scope Guards are the single source of truth for bc↔pd routing. Note that neither bc's nor pd's Scope Guard currently contains a hint pointing to csr, because csr is in Phase A (explicit invocation only; auto-triggering may arrive in a later phase). pd routes document-review requests to the architect agent, not to csr, so the explicit invocation described below is the only path that reaches csr.

## csr: same-family primary, different-family additive, never auto-triggered

csr is a same-family (fresh-context) and different-family (cross-family) multi-round adversarial document-review engine. The same-family leg always runs and is primary; the different-family leg is an opt-in additive second opinion. csr also carries a soft entry-time Scope Guard that reminds or reroutes only when invoked (code→pd, document authoring→bc, rightness-of-conclusion→human as outcome-axis), but under Phase A it does NOT auto-trigger. Invoke the `cross-source-review` skill explicitly only when a high-quality document (requirements/PRD, design doc, arch-design, iteration plan, wiki/spec page, or similar) needs cross-source adversarial review to converge.

csr handles only doc-shaped artifacts; code review and code-side issues go to pd.
