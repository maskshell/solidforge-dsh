# Cold-Start Pattern: Service-Layer Decoupling

Tier: Warning (Few-Shot, cold-start fallback). Mirror the shape, do not copy blindly.

## When the Architecture-Contract Gate flags a layer violation

A lower layer (e.g. repository) must not import a higher layer (e.g. API / router). Route cross-layer needs through the service layer.

## Shape

```text
api/        -> handlers only; depends on services
services/   -> orchestration + use cases; depends on repositories
repositories/ -> data access; depends on models only
models/     -> pure domain types; depends on nothing internal
```

## Anti-pattern the gate rejects

```python
# app/repositories/user_repo.py
from app.api.router import current_request   # WRONG: lower imports higher
```

## Fix

```python
# app/services/user_service.py
from app.repositories.user_repo import load
def get_user(uid):        # service orchestrates; api calls service
    return load(uid)
```
