# Web Patterns

Web / JavaScript / TypeScript project reference: the JS/TS language family across **browser and Node.js**. Detection, toolchain, parallel-conflict scenarios, framework breadth, and the Architecture-Contract Gate. Frontend work routes to `frontend-developer`; Node backend to `backend-developer` (see [role-agent-mapping.md](role-agent-mapping.md)).

## What "web" means here

One platform — the **npm/Node ecosystem** — not just "websites." It covers:

- **Runtimes**: browser (SPA/SSG/SSR) **and** Node.js (API servers, CLIs, build tools, edge functions). Detected by `package.json` (not by file extension).
- **Languages**: TypeScript (first-class) and JavaScript (first-class for structure/ lint; type-checking is opt-in via `tsconfig`). JSX/TSX, and single-file components (`.vue`, `.svelte`) are all in the fast-gate extension set.
- **Frameworks**: React, Vue, Svelte, Solid; meta-frameworks Next.js, Nuxt, SvelteKit, Astro, Remix; Node backends Express, Fastify, NestJS, Hono.

It is ONE platform (not split into "frontend" + "node") because the toolchain is shared: one package manager (npm/pnpm/yarn), one linter (eslint), one cycle/layer gate (dependency-cruiser), one type checker (tsc), one test runner (vitest/playwright). Breadth is expressed here and in the triggers, not by splitting the registry.

## Project Detection

| Marker | Flavor | Build / type | Test |
| --- | --- | --- | --- |
| `package.json` (+ `tsconfig.json`) | TypeScript (browser or Node) | `tsc --noEmit`; framework build | vitest / playwright |
| `package.json` (no `tsconfig.json`) | JavaScript | (no type gate unless `allowJs`) | vitest / playwright / node:test |
| `next.config.{js,mjs,ts}` | Next.js (React, SSR/SSG) | `next build` | vitest + playwright |
| `nuxt.config.{js,mjs,ts}` | Nuxt (Vue, SSR/SSG) | `nuxt build` | vitest + playwright |
| `svelte.config.js` | Svelte / SvelteKit | `svelte-kit build` | vitest + playwright |
| `astro.config.{js,mjs,ts}` | Astro (islands / SSG) | `astro build` | vitest + playwright |
| `vite.config.{js,mjs,ts}` (no meta-fw) | Vite SPA (React/Vue/Svelte/Solid) | `vite build` + `tsc` | vitest |
| `remix.config.js` / Vite + `@remix-run` | Remix | `remix build` | vitest + playwright |
| `package.json` w/ `express`/`fastify`/`@nestjs`/`hono` dep | Node backend | `tsc --noEmit` | vitest / supertest |

Prefer `pnpm`/`yarn` lockfiles when present (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`). Detect the package manager from the lockfile, not from guesses.

## Language breadth

- **TypeScript** — first-class. The type gate runs `tsc --noEmit` (requires `tsconfig.json`). `.ts`/`.tsx`.
- **JavaScript** — first-class for the fast gate (eslint) and the arch gate (dependency-cruiser parses JS). The **type gate is tsconfig-gated**: a pure-JS project with no `tsconfig.json` gets an honest-degrade skip (`tsc: no tsconfig.json — type-check skipped`). To opt JS into type-checking, add a `tsconfig.json` with `"allowJs": true` (and `"checkJs": true` for checked JS).
- **JSX / TSX** — handled by eslint + depcruise + tsc.
- **Vue / Svelte SFCs** (`.vue`, `.svelte`) — in the fast-gate extension set; eslint applies (configure the framework's eslint plugin).

## Toolchain Commands

```bash
npm ci                       # install (npm). pnpm: pnpm install --frozen-lockfile; yarn: yarn install --frozen-lockfile
npx tsc --noEmit             # type-check (TS; or JS with allowJs)
npx eslint .                 # lint (fast gate also runs per-file)
npx depcruise --config .dependency-cruiser.cjs src   # arch gate: cycles + layer boundaries
npx vitest run               # unit/component tests
npx playwright test          # E2E (see e2e-patterns.md)
```

## Framework & runtime patterns

- **Frontend (browser)** → `frontend-developer`. Natural parallel boundaries: routes / pages / feature components / stores. React+Next, Vue+Nuxt, Svelte+SvelteKit, Astro islands, Remix routes all follow the same shape — independent routes/components parallelize; shared layout/store/router config serializes.
- **Node backend** → `backend-developer`. Natural boundaries: route modules / controllers / services. Express, Fastify, NestJS, Hono: routers and their handlers are independent; the app composition file (`app.ts`/`server.ts`) and the dependency list are shared → serialize.
- **Monorepo** (turborepo / nx / pnpm workspaces) — each package/app is a parallel boundary; the root `package.json`, lockfile, and shared `tsconfig` base serialize.

## Parallel Conflict Scenarios

package.json Merge Conflicts: `dependencies` / `devDependencies` / `scripts` are append targets — multiple agents adding packages or scripts produce merge conflicts. Mitigation:

1. Mark `package.json` in `files_touched` for any task that adds/modifies deps or scripts.
2. Schedule all manifest-modifying tasks sequentially.
3. After convergence, run the install once to regenerate the lock file.

Lock File Conflicts: `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` are generated. Never edit by hand or by parallel agents. Regenerate once after `package.json` converges.

Shared Config Conflicts: `tsconfig.json`, `vite.config.*`, `eslint.config.*`, framework configs (`next.config.*`, `nuxt.config.*`, `svelte.config.js`, `astro.config.*`), and the root `index.html` are shared — serialize edits. Router definition files (e.g. Next `app/` route segments, Remix route modules) serialize at the segment level but independent routes parallelize.

Web-specific entries for the Conflict Detection Matrix:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `package.json` | Yes | Schedule sequentially |
| Same lock file | Yes | Schedule sequentially (regenerate once) |
| Same `tsconfig.json` / build config | Yes | Schedule sequentially |
| Same framework config (`next.config`, `nuxt.config`, …) | Yes | Schedule sequentially |
| Different route/page/component files, no shared imports | No | Parallel |
| Different route files, one imports the other | Yes | Schedule sequentially (or extract a shared module first) |
| Monorepo: different packages/workspaces | No | Parallel |

## Architecture-Contract Gate (Web / TypeScript)

The inner-ring architecture-contract gate for Web (JavaScript / TypeScript). Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_web.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_web.py [src]   # src defaults to 'src'
```

Checks:

- Circular dependencies + layer boundaries — dependency-cruiser (`--output-type err`, parsed from the violation blocks). Configure via `.dependency-cruiser.cjs` (template in `infra/templates/`). Reliable from entry files; pass `src/index.ts` or a `src/**/*` glob so depcruise actually traverses.
- Concurrency baseline — eslint `no-restricted-syntax` flagging synchronous APIs (`fs.readFileSync`, `child_process.execSync`) inside async request handlers. Runs only if an eslint config is present.
- Type baseline — `tsc --noEmit --pretty false` (parsed from the `file(line,col): error TSxxxx: message` lines). Requires `tsconfig.json`; pure-JS projects opt in via `allowJs`.

HONEST GAP — JavaScript without a `tsconfig.json` gets no type-check (the gate degrades with an explicit coverage note, never silently green). dependency-cruiser and eslint apply to JS and TS alike.

A missing tool degrades that check to a no-op pass with an explicit coverage note — the gate is never silently green.

### Sibling inner-ring gates (cross-ecosystem, same 越权日志 schema)

- `arch_contract_tests.py` — `vitest run` (JSON report) / `playwright test`.
- `arch_contract_deps.py` — leaked secrets (gitleaks) + dependency vulnerabilities (`npm audit`).
- `arch_contract_api.py` — frontend↔backend API contract (OpenAPI presence, generated- client freshness, fetch/axios path consistency). Advisory.

## Nested & mixed-language projects

"Web" is detected by `package.json` anywhere in the tree (root OR a subdir), so a nested frontend (e.g. `frontend/package.json` next to a root `pom.xml` backend) is detected and gated:

- `arm.py` copies `.dependency-cruiser.cjs` and lists the Web toolchain even when the frontend is nested; `arch_contract_deps.py` / `arch_contract_tests.py` run `npm audit` / `vitest` in **each** dir holding a `package.json` (root + nested).
- The per-language arch gate is orchestrator-pointed at the subdir. To run the web gate on a nested frontend:

  ```bash
  SOLIDFORGE_PROJECT_DIR=frontend python3 infra/scripts/arch_contract_web.py src
  ```

  (or `cd frontend` first). For a Java+Web repo, also run `arch_contract_java.py` from the backend dir, and `arch_contract_api.py` (root) for the cross-language contract.
- Shared serialization point: the API contract (OpenAPI). If both sides generate from one `openapi.json`, mark it in `files_touched` so parallel tasks don't diverge.

## E2E / Playwright

For Playwright E2E specifics — API-first auth, timeout strategy, selector priority, wait strategy, the fail-fast reporter — see [e2e-patterns.md](e2e-patterns.md) and [fail-fast.md](fail-fast.md). Those are peer L4 docs for the testing sub-domain; this file covers the web platform itself.
