#!/usr/bin/env python3
"""check-profile-catalog.py — every dsh-substrate profile's `model` must exist in
the installed pi-ai provider catalog.

Why (2026-10-18): pi-ai resolves models STRICTLY — "Strict resolution rejects
unserviceable models before settings writes" — and a provider route's catalog
ships only its own model ids. Each shipped profile pins ONE model id. When the
installed catalog moves (a pi-ai version bump), a pinned id silently stops
resolving and that heterogeneous leg fails at request time, silently from the
loop's point of view.

Found this way on 2026-10-18:
  - `zai-coding-cn` pinned `glm-5.2`; the catalog offers
    glm-4.6v / glm-5.3 / glm-5.3-flash / glm-5.3-highspeed
  - `qwen-token-plan-cn` pinned `qwen3.8-max-preview`; the catalog offers
    qwen3.6-flash, qwen3.7-max, qwen3.8-flash, qwen3.8-max, …
Both legs would have failed at request time.

Also flags a profile that sets `reasoning_effort` on a model the catalog marks
`reasoning: false` (a silent no-op / reject depending on the adapter path).

Data source: `@earendil-works/pi-ai/dist/providers/data/<route>.json` — the
generated catalog the adapter itself consumes, so this gate reads the SAME data
the runtime resolves against rather than a hand-maintained list.

Honest SKIP when no pi-ai install resolves (a bare CI checkout), never a silent
green. stdlib-only (ADR #1).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES_GLOB = "preset/skills/*/infra/scripts/profiles/*.json"


def candidate_pi_ai_dirs() -> list[Path]:
    """Directories that may hold the installed @earendil-works/pi-ai package."""
    out: list[Path] = []
    env = os.environ.get("DSH_PKG_ROOT")
    if env:
        out.append(Path(env) / "@earendil-works" / "pi-ai")
    home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
    out.append(home / "node_modules" / "@earendil-works" / "pi-ai")
    npx = Path.home() / ".npm" / "_npx"
    if npx.is_dir():
        out.extend(sorted(npx.glob("*/node_modules/@earendil-works/pi-ai"), reverse=True))
    return out


def locate_catalog() -> Path | None:
    for pkg in candidate_pi_ai_dirs():
        data = pkg / "dist" / "providers" / "data"
        if data.is_dir():
            return data
    return None


def main() -> int:
    data = locate_catalog()
    if data is None:
        print(
            "SKIP: profile catalog — no @earendil-works/pi-ai install resolved "
            "(out of scope on this machine, NOT verified green).",
            file=sys.stderr,
        )
        return 0

    failures: list[str] = []
    checked = 0
    for path in sorted(ROOT.glob(PROFILES_GLOB)):
        route = path.stem
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: unreadable profile ({exc})")
            continue
        if profile.get("substrate", "dsh") != "dsh":
            continue  # claude-code substrate: pi-ai catalog does not apply
        catalog_file = data / f"{route}.json"
        if not catalog_file.is_file():
            failures.append(
                f"{path}: route '{route}' has NO catalog file — pi-ai cannot resolve "
                f"this route's models (removed or renamed upstream?)"
            )
            continue
        catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        models = {m["id"]: m for api in catalog.values() for m in api.values()}
        model = profile.get("model")
        checked += 1
        if model not in models:
            failures.append(
                f"{path}: model {model!r} is NOT in the '{route}' catalog "
                f"(available: {', '.join(sorted(models)[:6])}…)"
            )
            continue
        if profile.get("reasoning_effort") is not None and models[model].get("reasoning") is not True:
            failures.append(
                f"{path}: sets reasoning_effort={profile.get('reasoning_effort')!r} but "
                f"the catalog marks model {model!r} as reasoning=false"
            )

    if failures:
        for f in failures:
            print("FAIL: " + f, file=sys.stderr)
        print(f"\nprofile catalog: {len(failures)} violation(s)", file=sys.stderr)
        return 1

    if checked == 0:
        print(
            "SKIP: profile catalog — no dsh-substrate profile was checked.",
            file=sys.stderr,
        )
        return 0

    print(f"PASS: profile models resolve — {checked} dsh-substrate profile(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
