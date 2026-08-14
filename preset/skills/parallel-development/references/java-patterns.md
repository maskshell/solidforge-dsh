# Java Patterns

Java / Maven / Gradle project reference (JDK 17+ baseline): detection, toolchain, parallel-conflict scenarios, and the Architecture-Contract Gate. Java uses `backend-developer` (no special agent — see [role-agent-mapping.md](role-agent-mapping.md)).

JDK 17+ is the baseline (LTS; records, sealed types, text blocks, pattern matching, switch expressions all available). The gates assume a JDK 17+ `java`/`javac`/`jdeps` on PATH; the project's exact release is declared in the build (`<maven.compiler.release>` in `pom.xml`, or `sourceCompatibility`/`toolchain` in `build.gradle`).

## Project Detection

| File | Project Type | Build | Test |
| --- | --- | --- | --- |
| `pom.xml` (single- or multi-module) | Maven | `mvn compile` | `mvn test` |
| `pom.xml` aggregator + `<modules>` | Maven multi-module | `mvn compile -pl :module` | `mvn test -pl :module` |
| `build.gradle` (Groovy DSL) | Gradle | `gradle compileJava` | `gradle test` |
| `build.gradle.kts` (Kotlin DSL) | Gradle | `gradle compileJava` | `gradle test` |
| `settings.gradle(.kts)` + subprojects | Gradle multi-project | `gradle :sub:compileJava` | `gradle :sub:test` |

Prefer the wrapper scripts (`./mvnw`, `./gradlew`) over a system `mvn`/`gradle` — they pin the exact build-tool version per repo. The gates do the same.

## Toolchain Commands

```bash
./mvnw -q compile            # Maven: compile + type-check (javac is the type checker)
./mvnw test                  # Maven: unit tests (Surefire -> target/surefire-reports/*.xml)
./gradlew compileJava        # Gradle: compile + type-check
./gradlew test               # Gradle: unit tests (-> build/test-results/test/*.xml)
google-java-format --dry-run --set-exit-if-changed $(find src -name '*.java')  # fast gate
```

## Parallel Conflict Scenarios

| File / Resource | Conflict? | Action |
| --- | --- | --- |
| Same `.java` file | Yes | Sequential |
| Different `.java`, no import coupling | No | Parallel |
| `pom.xml` (`<dependencies>` / `<plugins>`) | Yes | Serialize; resolve once |
| `build.gradle` / `build.gradle.kts` `dependencies {}` / `plugins {}` | Yes | Serialize |
| Maven lock / Gradle `gradle.lockfile` | Yes | Regenerate once after the build file converges (`mvn -N dependency:lock` / `gradle dependencies --write-locks`) |
| Multi-module: different Maven modules (`-pl :a` vs `-pl :b`) | No | Parallel |
| Multi-project: different Gradle subprojects (`:a` vs `:b`) | No | Parallel |
| Shared annotation processor / `annotationProcessor()` | Yes | Serialize — affects every compile |

Natural parallel boundaries: Maven modules (`-pl :module`), Gradle subprojects (`:sub`), and independent packages/classes within a module (no shared mutable state). Use `files_touched` at the module/subproject level for the scheduler.

`pom.xml` / `build.gradle` are append targets — multiple agents adding dependencies or plugins produce merge conflicts. Serialize dependency-changing tasks, then regenerate the lock file once after convergence.

## Architecture-Contract Gate (Java)

The inner-ring architecture-contract gate for Java. Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_java.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_java.py
```

Checks:

- Style + import-direction baseline — `checkstyle -f xml -c checkstyle.xml src/main/java` (parsed from the XML output). Resolves a `checkstyle` shim, then `$CHECKSTYLE_JAR`, then a `checkstyle-*-all.jar` in the project root. The copied `checkstyle.xml` carries the rules; its ImportControl block (commented in the template) encodes package-layer import rules.
- Package cycles — `jdeps --cyclic` (JDK-bundled; no install) on `target/classes` (Maven) or `build/classes/java/main` (Gradle), if the project has been compiled. Best-effort parse of the cyclic edge lines.

HONEST GAP — Java has no single first-class standalone layer/dependency-direction enforcer that fits this gate's config+CLI model. ImportControl (in `checkstyle.xml`) covers codable package-layer rules; beyond that, declared layering is NOT enforced deterministically here and remains an outer-ring semantic concern. For idiomatic, fine-grained layer/cycle rules, add ArchUnit tests to the project — they run through the TEST gate (`mvn test` / `gradle test` -> JUnit XML, reused parser) and surface as Blockers there. See [arch-contracts.md](arch-contracts.md).

A missing tool degrades that check to a no-op pass with an explicit coverage note — the gate is never silently green.

### Sibling inner-ring gates (cross-ecosystem, same 越权日志 schema)

- `arch_contract_tests.py` — `mvn test` / `gradle test`; Surefire / Gradle JUnit XML (reused parser).
- `arch_contract_deps.py` — leaked secrets (gitleaks) + dependency vulnerabilities (OWASP `dependency-check`).
- `arch_contract_api.py` — when a frontend (package.json) is also present: checks the OpenAPI/Swagger artifact (springdoc-openapi output), generated-client freshness, and frontend→backend path consistency. Advisory.

## Nested & mixed-language projects

Java is detected by `pom.xml` / `build.gradle` anywhere in the tree (root OR a subdir), so a backend nested under `backend/` (next to a root or `frontend/` web app) is detected and gated:

- `arm.py` copies `checkstyle.xml` and lists the Java toolchain even when the backend is nested (run via `arm-tools`); `arch_contract_deps.py` / `arch_contract_tests.py` run `dependency-check` / `mvn test` / `gradle test` in **each** dir holding a Java marker (root + nested).
- The per-language arch gate is orchestrator-pointed at the subdir:

  ```bash
  SOLIDFORGE_PROJECT_DIR=backend python3 infra/scripts/arch_contract_java.py
  ```

  (or `cd backend` first). `jdeps` then reads `backend/target/classes`.
- For a Java backend + Web frontend repo, run `arch_contract_api.py` (root) for the cross-language API contract — expose the backend API via springdoc-openapi into `openapi.json` and generate the frontend client from it.

## --with-tools (arm)

Java gate tools are system-toolchain / standalone tools, not project deps in the package-manager sense. `arm.py --with-tools` (via `arm-tools --with-tools`) prints (does not auto-run):

```bash
brew install maven gradle                          # build + test gates (or use ./mvnw / ./gradlew)
# fast gate: google-java-format (standalone jar / shim on PATH)
# arch gate: checkstyle — set $CHECKSTYLE_JAR, drop a checkstyle-*-all.jar in the repo, or install a shim
# supply-chain: dependency-check (brew install dependency-check, or the OWASP Maven/Gradle plugin)
```

`checkstyle.xml` (copied to project root) declares the rules and severities; tune it to the project's L1 red lines. The fast-gate formatter (google-java-format) and the ArchUnit test option are declared in the project build, not by this template.
