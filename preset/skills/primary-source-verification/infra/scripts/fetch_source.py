#!/usr/bin/env python3
"""Fetch a cited source URL -> parsed text. Stdlib-only (urllib), no runtime deps.

Credential surface (proposal §8 + iteration-plan PSV-I3 / outer-ring novel-1):
open sources (arXiv abstracts, Crossref, repos, docs) are fetched with NO
credential. HTTP 401/403 (or a paywall signal) -> NOT fetched; the caller
returns the claim `unverifiable` (escalate to human). There is NO Anthropic-
gateway LLM token here -- psv disclaims cross-source-review's heterogeneous
`claude -p` substrate; the oracle is the fetched TEXT, not a different-family
model. If a paywalled-fetch credential is ever needed, it must be a separately-
named HTTP surface, never csr's `_ANTHROPIC_AUTH_TOKEN` namespace.

CLI:
    python3 fetch_source.py <url> [--timeout 30]
        exit 0, stdout = fetched text (capped, utf-8, errors replaced)
        exit 1, stdout = {"unverifiable": true, "reason": "<why>"}  (paywalled / error)

The fetched TEXT is the oracle (proposal §3 step 2 / §9 Q4). A testable
primitive the orchestrator MAY use (the orchestrator can also use its built-in
fetch tool); the deterministic, gated core is coverage_driver.py.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

_MAX_BYTES = 200_000
_USER_AGENT = "primary-source-verification/0.1 (source-grounded per-claim verifier)"


def fetch(url: str, timeout: int = 30) -> tuple[str | None, str]:
    """Return (text, status). text is None on paywall/error; status explains why."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(_MAX_BYTES).decode("utf-8", errors="replace")
            return body, f"ok (HTTP {resp.status})"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return None, f"paywalled/forbidden (HTTP {exc.code})"
        return None, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"fetch error: {type(exc).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch a cited source URL -> text (stdlib)."
    )
    ap.add_argument("url", help="The source URL to fetch.")
    ap.add_argument(
        "--timeout", type=int, default=30, help="Per-request timeout (seconds)."
    )
    args = ap.parse_args()

    body, status = fetch(args.url, args.timeout)
    if body is None:
        json.dump({"unverifiable": True, "reason": status}, sys.stdout)
        sys.stdout.write("\n")
        return 1
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
