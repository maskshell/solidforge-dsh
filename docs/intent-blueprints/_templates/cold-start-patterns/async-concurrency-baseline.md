# Cold-Start Pattern: Concurrency Baseline (async-safe)

Tier: Warning (Few-Shot, cold-start fallback).

## What the Architecture-Contract Gate rejects

Blocking calls executed directly inside an `async def` starve the event loop.
The gate flags `time.sleep`, synchronous `requests.*`, and synchronous file reads inside async functions.

## Anti-pattern

```python
async def fetch_user(uid):
    time.sleep(2)                 # WRONG: blocks the loop
    return requests.get(url).json()
```

## Fix

```python
async def fetch_user(uid):
    await asyncio.sleep(0)        # cooperative, or real async client
    return await asyncio.to_thread(_blocking_fetch, uid)
```

Prefer an async-native client (httpx.AsyncClient, aiofiles) over offloading blocking calls; offloading is the fallback, not the default.
