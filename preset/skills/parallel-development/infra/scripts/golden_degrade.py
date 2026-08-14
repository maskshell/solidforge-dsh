#!/usr/bin/env python3
"""golden_degrade.py — expire stale @Agent-Golden-Ref entries.

Graphiti storage is reached via MCP (a standalone process cannot call MCP tools), so this script provides the DETERMINISTIC part: given a set of golden- path episodes, compute which are past their `expires_at` review date and emit the list to re-tag. The agent then performs the actual re-tagging via mcp__graphiti__add_memory (re-store body with `@Golden-Ref-STALE`) and/or mcp__graphiti__delete_entity_edge for the stale original.

Typical agent workflow (see references/golden-paths.md):
  1. search_memory_facts(query="@Agent-Golden-Ref")  -> episodes
  2. pipe the episodes JSON into this script            -> expired list
  3. for each expired name, re-store as @Golden-Ref-STALE (Warning tier, no longer a few-shot source)

Input: JSON array on stdin or --file. Each item: {"name":..., "episode_body":...} (or "body").
An item's body must contain an `expires_at: YYYY-MM-DD` line to be evaluated; items lacking expires_at are reported as `unreviewed`.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

EXPIRES_RE = re.compile(
    r"expires_at\s*:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?", re.IGNORECASE
)
RESPONSIBLE_RE = re.compile(r"responsible_party\s*:\s*(.+)$", re.MULTILINE)


def today():
    return datetime.now(timezone.utc).date()


def parse_date(s):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def evaluate(episodes):
    now = today()
    expired = []
    unreviewed = []
    ok = []
    for ep in episodes:
        body = ep.get("episode_body") or ep.get("body") or ""
        name = ep.get("name") or ep.get("fact") or "(unnamed)"
        m = EXPIRES_RE.search(body)
        if not m:
            unreviewed.append({"name": name, "reason": "no expires_at field"})
            continue
        exp = parse_date(m.group(1))
        if exp is None:
            unreviewed.append(
                {
                    "name": name,
                    "expires_at_raw": m.group(1),
                    "reason": "unparseable expires_at",
                }
            )
            continue
        owner = ""
        rm = RESPONSIBLE_RE.search(body)
        if rm:
            owner = rm.group(1).strip()
        if exp < now:
            expired.append(
                {"name": name, "expires_at": str(exp), "responsible_party": owner}
            )
        else:
            ok.append({"name": name, "expires_at": str(exp)})
    return expired, unreviewed, ok


def main():
    ap = argparse.ArgumentParser(description="expire stale golden-path episodes")
    ap.add_argument("--file", help="JSON file of episodes (default: stdin)")
    args = ap.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()

    try:
        episodes = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid JSON input: {e}"}))
        sys.exit(1)
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes") or episodes.get("facts") or []

    expired, unreviewed, ok = evaluate(episodes)
    result = {
        "checked": len(episodes),
        "expired": expired,
        "unreviewed": unreviewed,
        "current": ok,
        "instruction": (
            f"Re-tag {len(expired)} expired golden-path(s) as @Golden-Ref-STALE via "
            "mcp__graphiti__add_memory (Warning tier, not a few-shot source), and prompt the "
            "responsible_party to re-review or remove."
        )
        if expired
        else "No expired golden paths.",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
