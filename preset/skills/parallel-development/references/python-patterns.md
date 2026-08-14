# Python Application Development Patterns

Reference for Python application development in parallel workflows. Covers project detection, toolchain commands, testing strategy, dependency management, parallel conflict scenarios, and error recovery.

## Contents

- [Project Detection](#project-detection)
- [Toolchain Commands](#toolchain-commands)
- [Testing Strategy](#testing-strategy)
- [Dependency Management in Parallel Workflows](#dependency-management-in-parallel-workflows)
- [Parallel Conflict Scenarios](#parallel-conflict-scenarios)
- [Common Framework Patterns](#common-framework-patterns)
- [Error Recovery](#error-recovery)
- [Architecture Phase Artifacts](#architecture-phase-artifacts)
- [Performance Regression Detection](#performance-regression-detection)
- [Modularization & Parallel Strategy](#modularization--parallel-strategy)
- [Knowledge Source Index](#knowledge-source-index)

## Project Detection

Detect the project type by looking for these files in the project root. The first match determines the toolchain:

| File(s) | Package Manager | Lock File | Install Command | Run Command |
| --- | --- | --- | --- | --- |
| `pyproject.toml` with `[tool.uv]` or `uv.lock` | uv | `uv.lock` | `uv sync` | `uv run` |
| `pyproject.toml` with `[tool.poetry]` or `poetry.lock` | Poetry | `poetry.lock` | `poetry install` | `poetry run` |
| `pyproject.toml` with `[project]` (no uv/poetry markers) | pip/uv fallback | none or `requirements.lock` | `pip install -e .` | `python -m` |
| `Pipfile` | Pipenv | `Pipfile.lock` | `pipenv install` | `pipenv run` |
| `requirements.txt` (no pyproject.toml) | pip | none | `pip install -r requirements.txt` | `python` |
| `setup.py` or `setup.cfg` (legacy) | setuptools | none | `pip install -e .` | `python` |
| `environment.yml` | conda | none | `conda env create` | `conda run` |

Detection priority: check for `uv.lock` and `pyproject.toml` first (most modern), then Poetry markers, then legacy files. When both `pyproject.toml` and `requirements.txt` exist, pyproject.toml takes precedence.

### Virtual Environment Detection

Before running any toolchain command, verify the virtual environment is active:

| Marker | Meaning |
| --- | --- |
| `VIRTUAL_ENV` env var set | venv is active |
| `.venv/` directory exists | project-local venv exists (may need activation) |
| `uv run` available | uv manages environment automatically (no manual activation needed) |

For uv-managed projects, `uv run` handles environment creation and synchronization transparently. Do not manually activate venvs when using uv.

## Toolchain Commands

### Type Checking

The type checker is selected based on project configuration. If `pyproject.toml` specifies a type checker under `[tool.<name>]`, use that. Otherwise, detect availability:

```bash
# Check which type checker is configured or available
grep -q '\[tool.mypy\]' pyproject.toml && echo "mypy"
grep -q '\[tool.pyright\]' pyproject.toml && echo "pyright"
command -v mypy && echo "mypy available"
command -v pyright && echo "pyright available"
```

Run type checking:

```bash
# mypy (most common, Python-implemented)
mypy src/ --no-error-summary 2>&1 | head -50

# pyright / basedpyright (TypeScript-implemented, faster)
pyright src/

# ty (Rust-implemented, fastest, Astral ecosystem)
ty check src/
```

Type checking commands for the Convergent Fix Loop Tier 1:

```bash
# For projects using uv
uv run mypy src/

# For projects using poetry
poetry run mypy src/

# For projects using plain venv
python -m mypy src/
```

### Linting

Ruff is the standard linter/formatter for modern Python projects (replaces flake8, isort, black):

```bash
# Check only (no modifications)
ruff check src/

# Check and fix auto-fixable issues
ruff check --fix src/

# Format check (no modifications)
ruff format --check src/

# Format and fix
ruff format src/
```

Legacy projects may use separate tools:

```bash
# Legacy stack (only if ruff is not configured)
flake8 src/ --max-line-length=120
isort --check-only src/
black --check src/
```

### Testing

pytest is the standard test runner. Detect configuration:

```bash
# Check for pytest configuration
grep -q '\[tool.pytest' pyproject.toml && echo "pytest configured"
ls pytest.ini conftest.py 2>/dev/null
```

Run tests:

```bash
# Full test suite
pytest --tb=short -q

# With coverage
pytest --cov=src --cov-report=term-missing --tb=short -q

# Specific test file
pytest tests/unit/test_service.py -v

# Specific test by keyword
pytest -k "test_create_user" -v

# Stop on first failure (useful during fix loop)
pytest -x --tb=short

# Parallel test execution (if pytest-xdist installed)
pytest -n auto --tb=short
```

### Full Tier 1 Validation Sequence

For the Convergent Fix Loop, run these in order. Stop at the first failure:

```bash
# 1. Dependency sync (ensure environment matches lock file)
uv sync 2>/dev/null || poetry install 2>/dev/null || pip install -e ".[dev]" 2>/dev/null

# 2. Type check
uv run mypy src/ 2>/dev/null || mypy src/

# 3. Lint
uv run ruff check src/ 2>/dev/null || ruff check src/

# 4. Format check
uv run ruff format --check src/ 2>/dev/null || ruff format --check src/

# 5. Test suite
uv run pytest --tb=short -q 2>/dev/null || pytest --tb=short -q
```

Priority for fixes: type errors > lint errors > format errors > test failures. Fix type errors first because they often cause cascading test failures.

## Testing Strategy

### Test Directory Structure

```text
tests/
  conftest.py          # Shared fixtures (session/module scope)
  unit/                # Unit tests: no external dependencies
    conftest.py        # Unit test fixtures
    test_models.py
    test_services.py
  integration/         # Integration tests: cross-module, database, API
    conftest.py        # Integration fixtures (db connections, test client)
    test_api.py
    test_repository.py
```

### Fixture Scoping Rules for Parallel Development

Fixture scope determines when setup/teardown happens. Incorrect scope causes test pollution between parallel agents:

| Scope | Lifetime | Parallel Safety |
| --- | --- | --- |
| function | Per test function | Safe by default |
| class | Per test class | Safe if class tests are independent |
| module | Per test module | Safe for read-only fixtures |
| session | Entire test run | Unsafe if mutable — only for immutable shared data |

Rules for parallel agents modifying conftest.py:

- Each agent that adds fixtures should add them in a uniquely named fixture function (not modifying existing fixtures)
- Session-scoped fixtures must be read-only or use thread-safe mutation
- If two agents need the same fixture with different configurations, use parametrized fixtures or separate named fixtures

### Parametrized Tests as Parallel Contracts

When parallel agents write tests for the same interface (RED phase), parametrized tests serve as the shared contract:

```python
# tests/unit/test_user_service.py
import pytest

@pytest.mark.parametrize("input_data,expected", [
    ({"name": "Alice", "age": 30}, True),
    ({"name": "", "age": 30}, False),       # empty name rejected
    ({"name": "Bob", "age": -1}, False),    # negative age rejected
    ({"name": "Carol", "age": 150}, False), # unreasonable age rejected
])
def test_user_validation(input_data, expected):
    result = validate_user(input_data)
    assert result.is_valid == expected
```

Each agent independently implements against this contract in GREEN phase.

### Test Isolation for Parallel Safety

Tests must not depend on execution order. Violations manifest as: local pass + CI fail, or pass individually but fail in full suite.

Detection:

```bash
# Run tests in random order to detect order dependencies
pytest --random-order  # requires pytest-random-order plugin

# Run subset to detect missing dependencies
pytest tests/unit/test_service.py -v
```

Common causes of order-dependent tests:

- Module-level mutable state (global variables modified by tests)
- Shared database rows not cleaned between tests
- Fixture scope too wide for mutable data

## Dependency Management in Parallel Workflows

### Dependency File Conflicts

When multiple parallel agents add dependencies simultaneously, the following conflicts occur:

| File | Conflict Risk | Resolution |
| --- | --- | --- |
| `pyproject.toml` `[project.dependencies]` | High — multiple agents appending to same array | Serialize: only one agent modifies per turn |
| `pyproject.toml` `[tool.*]` sections | Low — different tool sections are independent | Parallel safe if sections differ |
| `uv.lock` / `poetry.lock` | High — must reflect pyproject.toml state | Regenerate after pyproject.toml converges |
| `requirements.txt` | High — flat file, append conflicts | Serialize: only one agent modifies per turn |

### Lock File Handling

Lock files must be regenerated after any dependency addition. In the scheduling loop:

1. Mark `pyproject.toml` and the lock file as `files_touched` for any task that adds dependencies
2. Schedule all dependency-adding tasks sequentially (they share pyproject.toml)
3. After all dependency additions converge, regenerate the lock file once:

   ```bash
   uv lock    # for uv projects
   poetry lock --no-update  # for Poetry projects
   ```

4. Then `uv sync` or `poetry install` to update the environment

### Monorepo / Workspace Projects

uv workspace projects (`[tool.uv.sources]` with path dependencies) introduce additional constraints:

- Multiple packages may share a single lock file
- Changes to one package's dependencies require lock file regeneration that affects all packages
- Schedule dependency changes to any workspace member sequentially

## Parallel Conflict Scenarios

### File-Level Conflicts

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same `.py` file in both `files_touched` | Yes | Schedule sequentially |
| Different `.py` files, no imports between them | No | Parallel |
| Different `.py` files, one imports the other | Yes | Schedule sequentially (imported module first) |
| Same `pyproject.toml` | Yes | Schedule sequentially |
| Same `uv.lock` / `poetry.lock` | Yes | Schedule sequentially |
| Same `conftest.py` | Yes | Schedule sequentially |
| Different `conftest.py` in different directories | No | Parallel |
| Same `__init__.py` | Yes | Schedule sequentially |
| Different test files in same directory | No | Parallel |

### Database Migration Conflicts

When using Alembic (SQLAlchemy) or Django migrations:

| Condition | Conflict? | Action |
| --- | --- | --- |
| Same migration file | Yes | Schedule sequentially |
| Different migration files, same app/alembic version | Yes | Must be sequential — migration order matters |
| Different migration files, different apps (Django) | No | Parallel — Django handles cross-app ordering |
| Migration + model file for same model | Yes | Schedule sequentially |

Alembic migration files contain chain references (`revision` and `down_revision`). Two agents creating migrations simultaneously will produce conflicting chain links. Solution:

1. Serialize all migration-creating tasks
2. After migrations converge, run `alembic upgrade head` to verify chain integrity
3. If chain is broken, merge migrations: `alembic merge heads -m "merge"`

Django's migration system is more parallel-friendly: migrations in different apps have independent chains. Only same-app migrations need serialization.

### conftest.py Conflicts

`conftest.py` files follow pytest's hierarchical discovery model. Conflicts occur when:

- Two agents add fixtures to the same conftest.py
- One agent adds a fixture that another agent's test depends on (implicit dependency)

Mitigation:

- Agents should add fixtures to their own test subdirectory's conftest.py when possible
- Only truly shared fixtures belong in the top-level conftest.py
- When modifying top-level conftest.py is necessary, serialize those modifications

### __init__.py Conflicts

`__init__.py` files serve dual roles: package markers and public API exports. Conflicts when:

- Multiple agents add exports to the same `__init__.py`
- One agent creates a subpackage that another agent's code imports from

Mitigation:

- Mark `__init__.py` of shared packages as `files_touched` when agents modify exports
- Prefer explicit imports (`from package.module import X`) over package-level re-exports during development
- Reconcile `__init__.py` exports in the integration phase after parallel agents complete

## Common Framework Patterns

### FastAPI

Project structure:

```text
app/
  __init__.py
  main.py              # FastAPI app instance
  api/
    deps.py            # Dependency injection (Depends)
    v1/
      router_users.py
      router_items.py
  models/              # SQLAlchemy models
  schemas/             # Pydantic models (request/response)
  services/            # Business logic
  tests/
    conftest.py        # TestClient fixture
    test_api/
```

Test pattern:

```python
# tests/conftest.py
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

# tests/test_api/test_users.py
def test_create_user(client):
    response = client.post("/api/v1/users", json={"name": "Alice"})
    assert response.status_code == 201
```

Parallel safety: routers in `app/api/v1/` are independent files. Each agent can implement a router with its tests, models, and schemas in parallel. The `app/main.py` that includes all routers is the shared file — serialize modifications to it.

Dependency injection with `Depends()` creates natural boundaries between parallel agents. Each agent implements its own dependency chain. Shared dependencies (database session, auth) are defined once in `api/deps.py` and consumed by all.

### Django

Project structure:

```text
project/
  manage.py
  project/             # Django project config
    settings.py
    urls.py
  apps/
    users/             # Django app
      models.py
      views.py
      tests.py
      migrations/
    orders/            # Django app
      models.py
      views.py
      tests.py
      migrations/
```

Parallel safety: Django apps are natural parallel boundaries. Each agent works on a separate app with its own models, views, tests, and migrations. Shared files requiring serialization:

- `project/settings.py` (when adding apps or middleware)
- `project/urls.py` (when adding URL patterns)
- Shared template directories
- Shared static files

Test pattern:

```python
# apps/users/tests/test_models.py
from django.test import TestCase
from apps.users.models import User

class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(email="test@example.com")
        self.assertEqual(user.email, "test@example.com")
```

Django's `TestCase` wraps each test in a database transaction and rolls back after the test. This provides test isolation by default. For read-only tests, use `SimpleTestCase` (no database overhead).

### Flask

Project structure:

```text
app/
  __init__.py           # create_app factory
  extensions.py         # Extension instances (db, migrate, etc.)
  blueprints/
    auth/
      __init__.py
      routes.py
      models.py
      tests/
    api/
      __init__.py
      routes.py
      models.py
      tests/
```

Parallel safety: Flask blueprints are independent modules. Each agent can implement a blueprint with its routes, models, and tests in parallel. Shared files:

- `app/__init__.py` (blueprint registration)
- `app/extensions.py` (shared extension instances)
- `migrations/` (if using Flask-Migrate/Alembic)

## Error Recovery

### Virtual Environment Corruption

Symptoms: `ModuleNotFoundError` for installed packages, `ImportError`, or unexpected `SyntaxError` in third-party code.

Recovery:

```bash
# For uv-managed projects
rm -rf .venv
uv sync

# For poetry-managed projects
poetry env remove python
poetry install

# For pip-managed projects
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This is a transient failure — auto-retry once after rebuilding the environment before reporting to the user.

### Dependency Version Conflicts

Symptoms: `ResolutionImpossible` (pip), `SolverProblemError` (poetry), or inconsistent `pip check` output.

Recovery:

1. Check if lock file matches pyproject.toml: `uv lock --check` or `poetry lock --check`
2. If mismatched, regenerate: `uv lock` or `poetry lock`
3. If resolution fails, check for conflicting constraints in dependency groups
4. Report unresolved conflicts to user with the conflicting packages and version ranges

### Import Cycle Detection

Symptoms: `ImportError` or `AttributeError` at import time, often appearing only when the full test suite runs.

Detection:

```bash
# Use pylint to detect import cycles
pylint --disable=all --enable=cyclic-import src/

# Or use pydeps for visualization
pydeps src/ --max-bacon=2
```

Import cycles often emerge after parallel agents independently add cross-module imports. Resolution requires understanding the dependency direction and breaking the cycle by extracting shared code into a separate module.

### Test Environment Mismatches

Symptoms: tests pass locally but fail in CI, or vice versa.

Diagnosis:

```bash
# Check Python version
python --version

# Check installed packages
pip list | grep -i <package>

# Compare environments
pip freeze > local.txt
# Compare with CI's pip freeze output
```

Common causes: different Python versions, missing dev dependencies, OS-specific behavior (path separators, file system case sensitivity). Use `requires-python` in pyproject.toml and pin dev dependencies to prevent drift.

## Architecture Phase Artifacts

When Phase 2 (Architecture) runs for a Python project, the architect must produce these artifacts before Phase 5 parallel implementation begins. Without them, parallel agents lack the constraints needed to avoid conflicting implementations.

### Required Artifacts

1. __API Boundary Map__: Which router/module owns which endpoints. Prevents two agents from implementing the same route or modifying the same router file.

   FastAPI example:

   ```text
   app/api/v1/
     users.py       → Agent A: GET/POST /api/v1/users, GET /api/v1/users/{id}
     orders.py      → Agent B: GET/POST /api/v1/orders, GET /api/v1/orders/{id}
     auth.py        → Agent C: POST /api/v1/auth/login, POST /api/v1/auth/refresh
   ```

   Django example:

   ```text
   apps/
     users/         → Agent A: /api/users/ (entire app owns this URL namespace)
     orders/        → Agent B: /api/orders/ (entire app owns this URL namespace)
   ```

2. __Model Ownership__: Which service owns which database models. Determines migration serialization order.

   ```text
   app/models/
     user.py        → Agent A (UserService owns User, UserProfile)
     order.py       → Agent B (OrderService owns Order, OrderItem)
   Shared: app/models/base.py → serialize modifications
   ```

3. __Migration Plan__: Ordered list of migrations with serialization markers. Migrations within the same Alembic chain or Django app must be sequential.

   ```text
   Sequential: 001_create_users → 002_create_orders → 003_create_order_items
   Reason: Orders depend on Users (FK), OrderItems depend on Orders (FK)
   ```

4. __Shared Dependency Inventory__: Files that multiple agents need to modify, requiring serialization.

   ```text
   Shared files (serialize all modifications):
   - app/main.py          (router registration)
   - app/api/deps.py      (shared dependency injection)
   - app/database.py      (engine/session factory)
   - tests/conftest.py    (shared fixtures)
   - pyproject.toml       (dependency additions)
   ```

5. __Import Direction Declaration__: Explicit dependency direction between modules to prevent circular imports. The import graph must be a DAG — if module A imports module B, module B must not import module A.

   ```text
   Allowed direction:  api.v1.users → services.user_service → models.user
   Forbidden:          models.user → services.user_service (upward import)

   For type-checking-only imports, use:
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from app.services import UserService  # no runtime import
   ```

### When Architecture Phase Can Be Skipped

For single-agent tasks (bug fixes, small features), these artifacts are unnecessary overhead. Skip when:

- Only one agent will implement (no parallelism)
- No new models or migrations needed
- No shared files will be modified

For deeper domain context on API design and database patterns, consult the wiki pages listed in [Knowledge Source Index](#knowledge-source-index).

## Performance Regression Detection

For the Convergent Fix Loop Tier 2 (code review), performance regression detection requires knowing which tools to use and what patterns to flag. Unlike iOS which has Instruments as a unified profiler, Python has specialized tools for different performance dimensions.

### Profiling Tools

| Tool | Type | Overhead | Best For |
| --- | --- | --- | --- |
| cProfile | Deterministic (stdlib) | 2-5× slowdown | Development: per-function call counts and cumulative time |
| py-spy | Sampling (OS-level) | <5% | Production: attach to running process, flame graph generation |
| Scalene | Hybrid (CPU+mem+GPU) | Moderate | Line-level analysis distinguishing Python vs native time |
| Memray | Allocation tracking | Moderate | Memory: peak allocation call stacks, flame graphs |
| tracemalloc | stdlib memory | Low | Quick diagnosis of Python object leaks |
| pytest-benchmark | Regression benchmark | Low | Automated performance regression tests in CI |

### Detection Patterns for Tier 2 Review

The code-reviewer agent should flag these performance anti-patterns:

1. __N+1 Queries__: Loop body makes a database query per iteration. Detection:

   ```python
   # Anti-pattern: N+1 query
   for user in users:
       orders = session.query(Order).filter(Order.user_id == user.id).all()

   # Fix: eager loading
   users = session.query(User).options(selectinload(User.orders)).all()
   ```

2. __Synchronous I/O in async context__: Blocking the event loop.

   ```python
   # Anti-pattern: blocks event loop
   result = requests.get(url)  # synchronous HTTP in async handler

   # Fix: async HTTP client
   result = await httpx.AsyncClient().get(url)
   ```

3. __Unbounded memory growth__: Loading entire datasets into memory.

   ```python
   # Anti-pattern: loads all rows
   all_records = session.query(Record).all()

   # Fix: streaming with yield_per
   for record in session.query(Record).yield_per(1000):
       process(record)
   ```

4. __Unnecessary serialization__: Converting between formats in hot paths.

   ```python
   # Anti-pattern: double-parse
   data = json.loads(json.dumps(obj))  # JSON roundtrip for deep copy

   # Fix: copy.deepcopy or model_copy
   data = obj.model_copy(deep=True)  # Pydantic native
   ```

### Running Performance Checks

When Tier 2 flags a potential performance issue, verify with profiling:

```bash
# Quick CPU profile of specific test
uv run python -m cProfile -s cumulate tests/test_performance.py

# Memory check for leak detection
uv run python -m tracemalloc --nb-frames 25 src/app.py

# Benchmark a specific operation
uv run pytest tests/test_performance.py --benchmark-only
```

For deeper performance engineering context, consult the wiki page listed in [Knowledge Source Index](#knowledge-source-index).

## Modularization & Parallel Strategy

How the project's module structure affects parallel execution opportunities. The choice between feature-based and layer-based modularization determines how many agents can work simultaneously without conflicts.

### Feature-Based Modularization (Recommended for Parallel Development)

Each feature is a vertical slice containing its own router/controller, models, schemas, services, and tests. Agents own entire features with zero file overlap.

FastAPI feature-based:

```text
app/
  features/
    users/
      router.py          # Agent A owns this directory
      models.py
      schemas.py
      service.py
      tests/
        test_router.py
        test_service.py
    orders/
      router.py          # Agent B owns this directory
      models.py
      schemas.py
      service.py
      tests/
  shared/                # Shared infrastructure (serialize modifications)
    database.py
    auth.py
    deps.py
```

Django feature-based (standard — Django apps ARE feature modules):

```text
apps/
  users/                 # Agent A owns this app
    models.py
    views.py
    serializers.py
    urls.py
    tests/
  orders/                # Agent B owns this app
    models.py
    views.py
    serializers.py
    urls.py
    tests/
```

Flask feature-based:

```text
app/
  blueprints/
    users/               # Agent A owns this blueprint
      __init__.py
      routes.py
      models.py
      services.py
      tests/
    orders/              # Agent B owns this blueprint
      routes.py
      models.py
      tests/
```

### Layer-Based Modularization (Requires More Serialization)

Shared directories for each layer (models/, schemas/, services/). Agents working on different features may touch the same files within a shared layer.

```text
app/
  models/
    user.py              # Agent A
    order.py             # Agent B
    __init__.py          # CONFLICT: both agents may add imports
  schemas/
    user.py              # Agent A
    order.py             # Agent B
  services/
    user_service.py      # Agent A
    order_service.py     # Agent B
  api/
    v1/
      users.py           # Agent A
      orders.py          # Agent B
```

Layer-based is safe when each agent works on distinct files within each layer. Conflicts arise in `__init__.py` files (re-exports) and shared configuration files. The conflict matrix in [Parallel Conflict Scenarios](#parallel-conflict-scenarios) covers these cases.

### Hybrid Strategy

Large projects often use a hybrid: feature-based for new features, layer-based for legacy code. The orchestrator should:

1. Detect the project's modularization style from directory structure
2. Assign agents to feature slices where possible (zero overlap)
3. For layer-based code, use `files_touched` to serialize shared file modifications

### Natural Parallel Boundaries by Framework

| Framework | Natural Parallel Unit | Shared Files Requiring Serialization |
| --- | --- | --- |
| FastAPI | Router file + its schemas/models | app/main.py, app/api/deps.py, conftest.py |
| Django | Django app (entire directory) | project/settings.py, project/urls.py, shared templates |
| Flask | Blueprint (entire directory) | app/__init__.py, app/extensions.py, shared templates |
| Generic Python | Independent module/package | __init__.py, pyproject.toml, conftest.py |

## Knowledge Source Index

This skill's operational reference covers toolchain commands, conflict scenarios, and framework patterns. For deeper domain understanding, __if the fedaot-wiki MCP is wired into your environment__, agents can consult it via `mcp__fedaot-wiki__get_page(name="<page-name>", wiki="common")` — a __private internal wiki, not bundled with this skill__. Its pages contain cross-linked knowledge graphs that provide conceptual depth beyond what this file covers.

### When to Consult

Load wiki pages when the task requires design decisions, debugging complex issues, or understanding trade-offs — not for routine operations (toolchain commands, conflict checks, test writing) which this file already covers.

### Mapping Table

| Skill Phase / Operation | Wiki Page | Consult When |
| --- | --- | --- |
| Phase 2: Architecture | `python-web-api-framework-design` | Designing API schema boundaries, choosing between FastAPI/Django/Flask patterns, understanding ASGI/WSGI differences |
| Phase 2: Architecture | `python-database-patterns` | Designing model ownership, repository pattern, Session lifecycle, migration strategy (expand-and-contract) |
| Phase 2: Architecture | `python-module-import-system` | Designing import direction to prevent circular imports, understanding `__init__.py` role in parallel conflicts |
| Phase 4: RED (Test Writing) | `python-testing-architecture` | Fixture scoping strategy beyond basic rules, mock layer selection, property-based testing with Hypothesis |
| Phase 5: GREEN (Implementation) | `python-async-concurrency-model` | Implementing async endpoints/services, event loop constraints, debugging async deadlocks |
| Phase 5: GREEN (Implementation) | `python-serialization-validation` | Pydantic V2 validation modes, `model_validate_json()` optimization, `TypeAdapter` reuse |
| Phase 5: GREEN (Implementation) | `python-data-model` | Implementing Protocol-based interfaces, dataclass patterns, operator overloading for domain models |
| Tier 1: Validation | `python-type-checker-landscape` | Selecting between mypy/pyright/ty, configuring strictness, understanding coverage trade-offs |
| Tier 1: Validation | `python-project-toolchain-architecture` | Tool configuration in pyproject.toml, understanding Ruff's rule categories, LSP integration |
| Tier 2: Code Review | `python-performance-engineering` | Profiling tools selection (cProfile/py-spy/Scalene/Memray), identifying optimization targets |
| Tier 2: Code Review | `python-security-architecture` | Security vulnerability patterns beyond ast-grep checks, input validation, authentication patterns |
| Error Recovery | `python-error-handling` | Designing exception hierarchies, error recovery patterns, distinguishing recoverable vs fatal errors |
| Error Recovery | `python-concurrency-strategy` | Selecting between threading/multiprocessing/asyncio for the project's workload type |
| Refactoring | `python-language-evolution` | Migration patterns (sync→async, old→new API), deprecation awareness across Python versions |
| Advanced: Concurrency | `python-gil-free-threading` | Free-threading compatibility auditing, C extension thread safety, ABI implications |
| Advanced: Data Pipelines | `python-functional-programming` | Composable generator pipelines, structural pattern matching for event dispatch, itertools composition |
| Advanced: Extensibility | `python-plugin-architecture` | Designing plugin systems with entry points or hook specifications, plugin isolation models |
| Advanced: Performance | `python-native-interop` | When to use C extensions/PyO3/Cython, FFI selection, ABI compatibility |
| Advanced: Network | `python-network-programming` | HTTP client patterns (HTTPX sync/async), WebSocket handling, retry and resilience patterns |

## Architecture-Contract Gate (Python)

The inner-ring architecture-contract gate for Python. Run at the inner convergence point (after the Fast Gate is clean, before the outer ring). Script: `arch_contract_python.py`; semantics in [arch-contracts.md](arch-contracts.md). Emits a 越权日志; non-zero exit = Blocker.

```bash
python3 infra/scripts/arch_contract_python.py [package]   # package defaults to .
```

Checks:

- Layer / forbidden import contracts — import-linter. Configure via `.importlinter.ini` (template in `infra/templates/`). The gate passes `--config .importlinter.ini` so the file is discovered regardless of name.

  ```bash
  lint-imports --config .importlinter.ini
  ```

- Cyclic imports — pylint:

  ```bash
  pylint --disable=all --enable=cyclic-import <package>
  ```

- Concurrency baseline — a stdlib `ast` scan for blocking calls (`time.sleep`, synchronous `requests.*`, synchronous file reads) directly inside `async def`, plus unbounded `ThreadPoolExecutor`. No external tool needed.

A missing tool degrades that check to a no-op pass with an explicit coverage note — the gate is never silently green.
