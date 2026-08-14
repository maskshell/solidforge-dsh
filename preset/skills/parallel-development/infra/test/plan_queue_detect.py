#!/usr/bin/env python3
"""plan_queue rich-path behaviors — producer detection + resolution seeding +
upstream-provenance bridge + research→inform.

detect_producer returns 'blueprint-crafting' on a bc-stamped queue (rich path) and
None on a plain / empty / missing queue (free path) — fail-safe: detection never
raises and never blocks. seed_from_structure seeds resolved ODPs bc carried.
build_upstream_provenance bridges bc's sibling run-record. read_research returns
read_research is SCHEMA-AWARE but NOT schema-gated (parses bc's claims/sources when present; accepts any form — R2).

Run: python3 infra/test/plan_queue_detect.py
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts")))

import plan_queue as pq  # noqa: E402


def _fail(msg):
    raise AssertionError(msg)


def check_detect_producer():
    # bc-stamped structure (freeze stamps every item) -> "blueprint-crafting"
    bc_struct = {
        "I0": {
            "item_id": "I0",
            "seq": 0,
            "producer": "blueprint-crafting",
            "plan_model_version": "v1",
        },
        "I1": {"item_id": "I1", "seq": 1, "producer": "blueprint-crafting"},
    }
    if pq.detect_producer(bc_struct) != "blueprint-crafting":
        _fail(f"bc-stamped queue not detected: {pq.detect_producer(bc_struct)!r}")
    # plain (free-path) structure -> None
    plain_struct = {
        "I0": {"item_id": "I0", "seq": 0},
        "I1": {"item_id": "I1", "seq": 1},
    }
    if pq.detect_producer(plain_struct) is not None:
        _fail(
            f"plain queue must detect None (free path): {pq.detect_producer(plain_struct)!r}"
        )
    # fail-safe: empty / None -> None, never raise
    if pq.detect_producer({}) is not None:
        _fail("empty structure must detect None")
    if pq.detect_producer(None) is not None:
        _fail("None structure must detect None (not raise)")
    print(
        "  detect_producer (bc -> blueprint-crafting; plain/empty/None -> None): PASS"
    )


def check_seed_resolutions_from_structure():
    """odp2-verdict-design D2: seed_from_structure seeds resolved ODPs bc carried
    (an open_decision with a `resolution`), so `claim` will not re-ask them;
    idempotent (an operator-set resolution is not clobbered); plain queues (no
    resolution) seed nothing."""
    structure = {
        "I0": {
            "item_id": "I0",
            "seq": 0,
            "depends_on": [],
            "open_decisions": [
                {
                    "id": "ODP-RES",
                    "kind": "resolve-now",
                    "resolution": "decided: option B",
                },
                {"id": "ODP-OPEN", "kind": "resolve-now"},  # unresolved — no resolution
            ],
        }
    }
    state = pq.default_state(None)
    pq.seed_from_structure(state, structure)
    odps = state["items"]["I0"]["odps"]
    if odps.get("ODP-RES") != {
        "status": "resolved",
        "resolution": "decided: option B",
        "defaulted": False,
    }:
        _fail(
            f"resolved ODP not seeded from the carried resolution: {odps.get('ODP-RES')}"
        )
    if "ODP-OPEN" in odps:
        _fail(f"unresolved ODP must not be seeded as resolved: {odps.get('ODP-OPEN')}")
    # ODP-RES (seeded) is no longer unresolved; ODP-OPEN (no resolution) correctly
    # remains (claim would still refuse it — an unresolved resolve-now ODP blocks).
    unresolved = pq.unresolved_resolve_now_ids(state, structure, "I0")
    if "ODP-RES" in unresolved:
        _fail(
            f"seeded ODP-RES must clear the resolve-now gate; still unresolved: {unresolved}"
        )
    if "ODP-OPEN" not in unresolved:
        _fail(f"ODP-OPEN (no resolution) must remain unresolved: {unresolved}")
    # idempotent: an operator-set resolution is not clobbered on re-seed
    odps["ODP-RES"] = {
        "status": "resolved",
        "resolution": "operator override",
        "defaulted": False,
    }
    pq.seed_from_structure(state, structure)
    if state["items"]["I0"]["odps"]["ODP-RES"]["resolution"] != "operator override":
        _fail(
            "seed_from_structure clobbered an operator-set resolution (not idempotent)"
        )
    # plain (free-path) queue: no resolution -> nothing seeded
    plain = {
        "I0": {
            "item_id": "I0",
            "seq": 0,
            "depends_on": [],
            "open_decisions": [{"id": "X", "kind": "resolve-now"}],
        }
    }
    pstate = pq.default_state(None)
    pq.seed_from_structure(pstate, plain)
    if pstate["items"]["I0"]["odps"]:
        _fail(
            f"plain queue (no resolution) must seed nothing: {pstate['items']['I0']['odps']}"
        )
    print(
        "  seed_from_structure seeds carried resolutions (claim gate cleared; idempotent): PASS"
    )


def check_build_upstream_provenance():
    """odp2-verdict-design D1: build_upstream_provenance reads bc's sibling
    .run-record.json and returns {producer, process_converged, profile}; None when
    the queue is not bc-origin or the sibling is absent (fail-safe)."""
    with tempfile.TemporaryDirectory() as td:
        # bc queue (producer marker) + sibling run-record
        qpath = os.path.join(td, "x.queue.md")
        rpath = os.path.join(td, "x.run-record.json")
        with open(qpath, "w", encoding="utf-8") as fh:
            fh.write(
                '## Items\n\n```json\n[{"item_id":"I0","seq":0,'
                '"producer":"blueprint-crafting"}]\n```\n'
            )
        with open(rpath, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "process_converged": True,
                    "inner_ring": {"profile": "iteration-plan"},
                },
                fh,
            )
        up = pq.build_upstream_provenance(qpath)
        if up != {
            "producer": "blueprint-crafting",
            "process_converged": True,
            "profile": "iteration-plan",
        }:
            _fail(f"bc sibling run-record not bridged to upstream: {up}")
        # non-bc queue -> None
        plain = os.path.join(td, "p.queue.md")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write('## Items\n\n```json\n[{"item_id":"I0","seq":0}]\n```\n')
        if pq.build_upstream_provenance(plain) is not None:
            _fail("non-bc queue must return None (free path)")
        # bc queue but no sibling run-record -> None (fail-safe)
        nosib = os.path.join(td, "n.queue.md")
        with open(nosib, "w", encoding="utf-8") as fh:
            fh.write(
                '## Items\n\n```json\n[{"item_id":"I0","seq":0,'
                '"producer":"blueprint-crafting"}]\n```\n'
            )
        if pq.build_upstream_provenance(nosib) is not None:
            _fail("bc queue with no sibling run-record must return None")
    print("  build_upstream_provenance bridges bc sibling run-record (fail-safe): PASS")


def check_read_research():
    """charter R5 + R2: read_research is SCHEMA-AWARE but NOT schema-gated.

    - bc's {claims, sources} -> parsed (precise identification; uses bc's output).
    - free-form / no-schema -> content returned as-is (NOT rejected).
    - missing -> None (the only None path)."""
    with tempfile.TemporaryDirectory() as td:
        # bc's structured .research.json -> parsed to {kind, claims, sources}
        jp = os.path.join(td, "x.research.json")
        with open(jp, "w", encoding="utf-8") as fh:
            json.dump({"claims": [{"text": "X is true."}], "sources": []}, fh)
        jr = pq.read_research(jp)
        if jr.get("kind") != "research-json" or jr.get("claims") != [
            {"text": "X is true."}
        ]:
            _fail(f"bc schema research must be parsed (schema-aware): {jr}")
        # a free-form markdown research doc -> accepted (NOT gated)
        mp = os.path.join(td, "note.md")
        with open(mp, "w", encoding="utf-8") as fh:
            fh.write("# Research\nLibrary X is suitable.\n")
        mr = pq.read_research(mp)
        if mr.get("kind") != "free-form" or "Library X" not in mr.get("content", ""):
            _fail(f"free-form markdown must be accepted (not gated): {mr}")
        # a JSON file with no claims/sources key -> accepted free-form (no gate)
        nopclaims = os.path.join(td, "plain.json")
        with open(nopclaims, "w", encoding="utf-8") as fh:
            json.dump({"summary": "free-form finding"}, fh)
        pr = pq.read_research(nopclaims)
        if pr.get("kind") != "free-form":
            _fail(
                f"JSON without bc's schema must be accepted free-form (no gate): {pr}"
            )
        # missing -> None (the only None path)
        if pq.read_research(os.path.join(td, "nope")) is not None:
            _fail("read_research must return None only when missing")
    print("  read_research schema-aware + free-form (no gate): PASS")


def main():
    print("plan_queue rich-path (detect + seed + upstream + research):")
    failures = []
    for fn in (
        check_detect_producer,
        check_seed_resolutions_from_structure,
        check_build_upstream_provenance,
        check_read_research,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print("\ndetect_producer: rich-path detection is fail-safe.")
    sys.exit(0)


if __name__ == "__main__":
    main()
