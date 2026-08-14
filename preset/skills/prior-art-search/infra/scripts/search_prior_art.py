#!/usr/bin/env python3
"""Search the prior-art corpus for a novelty claim's search_target -> candidate prior art.

Stdlib-only (urllib + xml.etree), no runtime deps. This is the SEARCH oracle of
prior-art-search — the analog of psv's fetch_source.py, but it does not fetch a CITED
source; it SEARCHES the prior-art corpus for UNcited prior art that already makes the
claim (proposal §3 step 2; ADR §8 Q4 / design-decisions.md ADR #4).

Credential surface (iteration-plan NC-I3; install.md; ADR #5):
- OPEN prior art (arXiv abstracts via the export.arxiv.org API, public repos) is searched
  with NO credential. arXiv is the default source class and needs no key.
- WEB-search APIs use a SEPARATELY-NAMED HTTP API-key surface (env PRIOR_ART_SEARCH_API_KEY),
  NEVER csr's `_ANTHROPIC_AUTH_TOKEN` LLM-token namespace and NEVER psv's fetched-source surface.
  When the web key is absent, the web path is skipped (open arXiv path still runs).

Oracle-strength caveat (load-bearing, design-decisions.md ADR #4): a search result adds a
SELECTION-side weakness (ranking bias, recall limits, found text is model-extracted) on top
of the COMPARISON-side weakness the collision-verifier carries. clear-under-search downstream
means "no collision in what was searched," NOT "novel." That is WHY prior-art-search never
emits novel_confirmed — the weaker oracle is named here, not hidden.

The found prior-art TEXT (arXiv abstract) is returned so the collision-verifier can QUOTE it
(the fetched-quote invariant, design-decisions.md ADR #3; enforced by fetched_quote_gate.py).
A bare search-snippet/title is NOT enough — the abstract is the fetched prior-art text.

CLI:
    python3 search_prior_art.py <query> [--max-results 5] [--source arxiv|web|auto] [--timeout 30]
        exit 0, stdout = {"query","candidates":[{title,abstract,url,source}],"sources":[...]}
                 (candidates may be EMPTY with "clear_under_search": true when a source completed
                 a search but found nothing -- the clear-under-search path, NOT inconclusive)
        exit 1, stdout = {"inconclusive": true, "reason": "<why>"}  (no source completed a search)

The orchestrator MAY also use its built-in search/fetch tools; the deterministic, gated core
is coverage_driver.py. This primitive is the testable stdlib search unit.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_MAX_BYTES = 200_000
_USER_AGENT = (
    "prior-art-search/0.1 (search-grounded per-novelty-claim collision detector)"
)
_ARXIV_API = "http://export.arxiv.org/api/query"
_WEB_KEY_ENV = "PRIOR_ART_SEARCH_API_KEY"  # separately-named HTTP surface (ADR #5)

# arXiv Atom feed namespaces
_NS = {"a": "http://www.w3.org/2005/Atom"}


def _search_arxiv(
    query: str, max_results: int, timeout: int
) -> tuple[list[dict] | None, str]:
    """Query the open arXiv API. Return (candidates, status); candidates None on error.

    No credential. Each candidate carries the fetched prior-art TEXT (the abstract) so the
    collision-verifier can quote it.
    """
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "max_results": str(max_results),
            "sortBy": "relevance",
        }
    )
    url = f"{_ARXIV_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(_MAX_BYTES).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"arxiv fetch error: {type(exc).__name__}"
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return None, f"arxiv parse error: {type(exc).__name__}"
    candidates = []
    for entry in root.findall("a:entry", _NS):
        title_el = entry.find("a:title", _NS)
        summary_el = entry.find("a:summary", _NS)
        id_el = entry.find("a:id", _NS)
        title = (
            (title_el.text or "").strip().replace("\n", " ")
            if title_el is not None
            else ""
        )
        abstract = (summary_el.text or "").strip() if summary_el is not None else ""
        arxiv_id = (id_el.text or "").strip() if id_el is not None else ""
        if not abstract:
            continue  # no fetched prior-art text -> cannot quote -> skip
        candidates.append(
            {"title": title, "abstract": abstract, "url": arxiv_id, "source": "arxiv"}
        )
    return candidates, f"ok (arxiv, {len(candidates)} candidates)"


def _search_web(
    _query: str, _max_results: int, _timeout: int
) -> tuple[list[dict] | None, str]:
    """Query a web-search API via the separately-named key surface.

    Phase A: the web path is KEY-GATED and provider-specific; without a concrete provider
    contract it returns inconclusive (the open arXiv path remains the credential-free default).
    A future provider wires its endpoint here under PRIOR_ART_SEARCH_API_KEY — never
    the csr LLM-token namespace (ADR #5).
    """
    if not os.environ.get(_WEB_KEY_ENV):
        return None, "web-search key absent (PRIOR_ART_SEARCH_API_KEY unset)"
    return (
        None,
        "web-search provider not wired in Phase A (open arXiv path is the default)",
    )


def search(query: str, max_results: int = 5, source: str = "auto", timeout: int = 30):
    """Return (candidates, statuses, searched_ok).

    candidates = merged candidate list; statuses = per-source status strings; searched_ok =
    True iff at least one source COMPLETED a real search (even with 0 results), distinct from
    a search that could not run at all. An empty merge with searched_ok=True is the
    clear-under-search path (searched, found nothing); an empty merge with searched_ok=False
    is inconclusive (could not search). This disambiguation is load-bearing (NC-I3 outer-ring
    W-1): an empty-but-successful search must NOT be flagged inconclusive, or clear-under-search
    degrades to a coverage escalation.
    """
    statuses = []
    merged: list[dict] = []
    searched_ok = False
    want_arxiv = source in ("arxiv", "auto")
    want_web = source in ("web", "auto")
    if want_arxiv:
        cand, status = _search_arxiv(query, max_results, timeout)
        statuses.append(f"arxiv: {status}")
        if cand is not None:  # success even if empty ([] != None); None = error
            searched_ok = True
            merged.extend(cand)
    if want_web:
        cand, status = _search_web(query, max_results, timeout)
        statuses.append(f"web: {status}")
        if cand:
            merged.extend(cand)
    return merged, statuses, searched_ok


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Search the prior-art corpus (arXiv open API default) for a novelty claim."
    )
    ap.add_argument(
        "query", help="The novelty claim's search_target (prior-art query)."
    )
    ap.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Max candidates per source (default 5).",
    )
    ap.add_argument(
        "--source",
        choices=["arxiv", "web", "auto"],
        default="auto",
        help="arxiv (open, no key) | web (key-gated, NOT wired Phase A) | auto (default).",
    )
    ap.add_argument(
        "--timeout", type=int, default=30, help="Per-request timeout (seconds)."
    )
    args = ap.parse_args()

    merged, statuses, searched_ok = search(
        args.query, args.max_results, args.source, args.timeout
    )
    if not merged:
        if searched_ok:
            # Searched successfully and found nothing -> the clear-under-search path (the
            # comparator assigns clear-under-search). NOT inconclusive: a completed search
            # with no collision found must not degrade to a coverage escalation (NC-I3 W-1).
            json.dump(
                {
                    "query": args.query,
                    "candidates": [],
                    "sources": statuses,
                    "clear_under_search": True,
                },
                sys.stdout,
            )
            sys.stdout.write("\n")
            return 0
        # No source completed a search -> could not search -> inconclusive.
        json.dump(
            {
                "inconclusive": True,
                "reason": "search did not complete; " + " | ".join(statuses),
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 1
    json.dump(
        {"query": args.query, "candidates": merged, "sources": statuses}, sys.stdout
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
