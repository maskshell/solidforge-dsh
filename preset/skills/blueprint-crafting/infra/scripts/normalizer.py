#!/usr/bin/env python3
"""normalizer.py — heterogeneous source format -> plan-model, graded extraction.

Iteration I2 (arch-design §2, §4; iteration-plan §4). The seam this module owns: source documents are NOT machine-form, so extraction is GRADED — structured latches (frontmatter todos[] / json item blocks / markdown tables) are high-confidence, while prose dependency inference is low-confidence (semantic-infer).
Per workspace rule 4, the semantic-infer layer is ADVISORY: it populates a best-effort value and tags the confidence in `coverage`; it is NEVER a Blocker. The constraints-checker (I3) is what Blocks; the normalizer only normalizes + tags.

Output = {"plan_model": <schema-valid per plan-model.schema.json>, "coverage": {...}}.
The plan-model carries the best-effort values; coverage documents the per-field extraction confidence (and what could not be extracted). ADR #2 (determinism holds over the normalized model, not the source) is realized here: the confidence tag is the seam.

Formats (auto-detected; overridable):
  - cursor-plan  : frontmatter `todos[]` JSON array  -> latch (high-confidence)
  - work-package : fenced ```json item list (id/depends_on/dod) -> latch
  - rich-md      : markdown table (ID/Deps/DoD) -> latch; prose sequence notes -> semantic-infer (low-confidence) for extra deps / parallel_group

Library module imported by infra/test/normalizer_goldens.py. CLI for inspection:

    python3 infra/scripts/normalizer.py <file> [--format cursor-plan|work-package|rich-md]
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_model as pm  # noqa: E402 — within-skill reuse (needs the sys.path.insert above)

# confidence labels (the graded-extraction vocabulary; rule 4: advisory, never Blocker)
LATCH = "latch (high-confidence)"
SEMANTIC_INFER = "semantic-infer (low-confidence)"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
TODOS_BLOCK_RE = re.compile(r"```todos\s*\n(.*?)\n```", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

REGISTRY_PATH = os.path.join(HERE, "constraints.json")

# prose dependency inference heuristic — deliberately simple, honestly tagged low-conf.
# matches "<id> (also)? (depends on|follows|pulls in|must follow) <id>"
PROSE_DEP_RE = re.compile(
    r"\b([A-Za-z][\w-]*)\s+(?:also\s+)?(?:depends\s+on|follows|pulls\s+in|must\s+follow)\s+"
    r"([A-Za-z][\w-]*)\b",
    re.IGNORECASE,
)


# --- frontmatter (minimal; scalars + JSON-literal values) --------------------


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end() :]
    fm = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if (val[:1], val[-1:]) in (('"', '"'), ("'", "'")):
            val = val[1:-1]
        fm[key] = val
    return fm, body


def _maybe_json(val):
    """Parse a frontmatter value that may be a JSON literal ([...] or {...})."""
    if not val:
        return None
    if val[0] in "[{":
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None
    return None


# --- format detection --------------------------------------------------------


def detect_format(text):
    fm, _ = parse_frontmatter(text)
    if "todos" in fm and _maybe_json(fm["todos"]) is not None:
        return "cursor-plan"
    if JSON_BLOCK_RE.search(text) and _json_block_is_items(text):
        return "work-package"
    if re.search(r"\|\s*ID\s*\|", text, re.IGNORECASE):
        return "rich-md"
    return "rich-md"  # default fallback


def _json_block_is_items(text):
    """A ```json block is a work-package item list if it parses to a list of dicts
    with an 'id' (or 'item_id') key."""
    for m in JSON_BLOCK_RE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list) and data and isinstance(data[0], dict):
            if "id" in data[0] or "item_id" in data[0]:
                return True
    return False


# --- per-format parsers ------------------------------------------------------
# Each returns (items, notes) where items is a list of plan-model item dicts and notes is a list of {item_id, field, source, confidence} extraction records.


def _note(notes, item_id, field, source, confidence):
    notes.append(
        {"item_id": item_id, "field": field, "source": source, "confidence": confidence}
    )


def _dep_list(raw):
    """Parse a depends_on cell/value: 'r-1, r-2' or ['r-1','r-2'] or '—'/'-'/'' -> []."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if s in ("", "—", "-", "–", "none", "None"):
        return []
    return [c.strip() for c in re.split(r"[,;]", s) if c.strip()]


def parse_cursor_plan(text):
    fm, body = parse_frontmatter(text)
    todos = _maybe_json(fm.get("todos", "")) or []
    items, notes = [], []
    for seq, t in enumerate(todos):
        if not isinstance(t, dict):
            continue
        iid = str(t.get("id") or t.get("item_id") or "").strip()
        if not iid:
            continue
        depends_on = _dep_list(t.get("depends_on"))
        it = {
            "item_id": iid,
            "seq": t.get("seq", seq),
            "depends_on": depends_on,
            "dod_ref": str(t.get("dod") or t.get("dod_ref") or ""),
        }
        if t.get("content") or t.get("title"):
            it["title"] = str(t.get("content") or t.get("title"))
        if t.get("status"):
            it["scope"] = f"status={t.get('status')}"
        items.append(it)
        # todos[] is the latch — every extracted field is high-confidence
        for f in ("item_id", "seq", "depends_on", "dod_ref"):
            _note(notes, iid, f, "frontmatter todos[]", LATCH)
    return items, notes


def parse_work_package(text):
    items, notes = [], []
    m = JSON_BLOCK_RE.search(text)
    raw = json.loads(m.group(1)) if m else []
    for seq, t in enumerate(raw):
        if not isinstance(t, dict):
            continue
        iid = str(t.get("id") or t.get("item_id") or "").strip()
        if not iid:
            continue
        depends_on = _dep_list(t.get("depends_on"))
        it = {
            "item_id": iid,
            "seq": t.get("seq", seq),
            "depends_on": depends_on,
            "dod_ref": str(t.get("dod") or t.get("dod_ref") or ""),
        }
        if t.get("title"):
            it["title"] = str(t["title"])
        if t.get("files"):
            it["scope"] = "files: " + ", ".join(map(str, t["files"]))
        items.append(it)
        for f in ("item_id", "seq", "depends_on", "dod_ref"):
            _note(notes, iid, f, "```json item block", LATCH)
    return items, notes


def parse_rich_md(text):
    fm, body = parse_frontmatter(text)
    lines = body.splitlines()
    # locate the table header with an ID column
    hdr_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if re.search(r"\|\s*ID\s*\|", line, re.IGNORECASE)
        ),
        None,
    )
    items, notes = [], []
    known_ids = []
    if hdr_idx is not None:
        headers = [
            h.strip().lower() for h in lines[hdr_idx].strip().strip("|").split("|")
        ]
        col = {h: i for i, h in enumerate(headers)}
        for line in lines[hdr_idx + 2 :]:  # skip header + separator
            if not line.strip().startswith("|"):
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) <= max(col.values(), default=0):
                continue
            row = {h: cells[i] for h, i in col.items() if i < len(cells)}
            iid = (row.get("id") or "").strip()
            if not iid:
                continue
            depends_on = _dep_list(row.get("deps"))
            it = {
                "item_id": iid,
                "seq": len(items),
                "depends_on": depends_on,
                "dod_ref": str(row.get("dod") or ""),
            }
            if row.get("title"):
                it["title"] = row["title"]
            comp = (row.get("complexity") or "").strip()
            if comp in (
                "S",
                "M",
                "L",
                "XL",
            ):  # only emit a clean tier; ranges/free-text degrade (optional field)
                it["complexity"] = comp
            items.append(it)
            known_ids.append(iid)
            for f in ("item_id", "seq", "depends_on", "dod_ref"):
                _note(notes, iid, f, "markdown table", LATCH)
    return items, notes  # prose-dep inference is applied uniformly in normalize()


_PARSERS = {
    "cursor-plan": parse_cursor_plan,
    "work-package": parse_work_package,
    "rich-md": parse_rich_md,
}


# --- artifact-type + anchor extraction (closes the §10 dogfood gap) -----------


def detect_artifact_type(text):
    """Detect the artifact_type from frontmatter or the first H1. Falls back to
    iteration-plan. Drives which anchors the normalizer extracts."""
    fm, body = parse_frontmatter(text)
    if fm.get("artifact_type"):
        return fm["artifact_type"]
    m = H1_RE.search(body or text)
    h1 = m.group(1).lower() if m else ""
    if "iteration plan" in h1:
        return "iteration-plan"
    if "architecture design" in h1 or "arch-design" in h1:
        return "arch-design"
    if "product spec" in h1 or " prd" in h1 or h1.startswith("prd"):
        return "product-spec"
    if "executable summary" in h1 or "plan queue" in h1:
        return "executable-summary"
    if "research" in h1:
        return "research"
    return "iteration-plan"  # default


def _load_registry():
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return {}


def extract_anchors(text, artifact_type, registry=None):
    """Best-effort anchor extraction for the iteration-plan §10 dogfood.
    Returns the anchors map (anchor -> {present, ref, confidence}) or None if the type has no profile (e.g. research, handled by research_constraints).
    Keywords are bilingual (English + Chinese), registry-driven (constraints.json -> anchor_detection; ADR #15) so Chinese-language artifacts are detected, not vacuously missed. Heading match = latch (high-confidence); prose-only match = semantic-infer (low-confidence); no match = present=False (the checker degrades this to a coverage note when anchors_meta.source=normalizer-extracted — rule 4, no Blocker-on-a-heuristic-miss)."""
    reg = registry if registry is not None else _load_registry()
    profile = reg.get("profiles", {}).get(artifact_type)
    if not profile:
        return None
    required = profile.get("anchors", [])
    detect_map = reg.get("anchor_detection", {})
    headings_low = [
        line.lower() for line in text.splitlines() if line.lstrip().startswith("#")
    ]
    low = text.lower()
    anchors = {}
    for anchor in required:
        kws = [
            k.lower() for k in (detect_map.get(anchor) or [anchor.replace("-", " ")])
        ]
        if any(any(k in h for k in kws) for h in headings_low):
            anchors[anchor] = {"present": True, "ref": "heading", "confidence": LATCH}
        elif any(k in low for k in kws):
            anchors[anchor] = {
                "present": True,
                "ref": "prose",
                "confidence": SEMANTIC_INFER,
            }
        else:
            anchors[anchor] = {
                "present": False,
                "ref": "",
                "confidence": "not-detected",
            }
    return anchors


# --- normalize ---------------------------------------------------------------


def normalize(text, format=None):
    fmt = format or detect_format(text)
    parser = _PARSERS.get(fmt, parse_rich_md)
    items, notes = parser(text)
    # uniform prose-dep inference (semantic-infer, low-confidence) across formats.
    # rule 4: advisory — populates a best-effort value + tags confidence; never a Blocker.
    _, body = parse_frontmatter(text)
    known_set = {it["item_id"] for it in items}
    for a, b in PROSE_DEP_RE.findall(body):
        a, b = a.strip(), b.strip()
        if a in known_set and b in known_set:
            deps = next((it["depends_on"] for it in items if it["item_id"] == a), None)
            if deps is not None and b not in deps:
                deps.append(b)
                _note(notes, a, "depends_on", f"prose: '{a} ... {b}'", SEMANTIC_INFER)
    fm, _ = parse_frontmatter(text)
    artifact_type = detect_artifact_type(text)
    authority = []
    if _maybe_json(fm.get("authority_chain")):
        authority = [str(x) for x in _maybe_json(fm["authority_chain"])]
    elif fm.get("plan_ref"):
        authority = [fm["plan_ref"]]
    elif fm.get("plan_id"):
        authority = [f"docs/{fm['plan_id']}.md"]
    if not authority:
        authority = [f"(normalized from {fmt})"]
    plan_model = {
        "plan_model_version": "v1",
        "artifact_type": artifact_type,
        "authority_chain": authority,
        "items": items,
        "subset_tags": {k: list(v) for k, v in pm.SUBSET_TAGS.items()},
    }
    # best-effort anchor extraction (iteration-plan §10 dogfood). Anchors are heuristic (keyword detection) -> tagged anchors_meta.source=normalizer-extracted so the checker degrades an undetected anchor to a coverage note, not a Blocker (rule 4).
    anchors = extract_anchors(text, artifact_type)
    if anchors is not None:
        plan_model["anchors"] = anchors
        plan_model["anchors_meta"] = {"source": "normalizer-extracted"}
    coverage = {
        "format": fmt,
        "extraction": notes,
        "not_extracted": _not_extracted(items, notes),
        "rule4_note": "semantic-infer fields are advisory (workspace rule 4); never a Blocker.",
    }
    return {"plan_model": plan_model, "coverage": coverage}


def _not_extracted(items, notes):
    """Fields absent from the source (no latch, no inference) — disclosed honestly."""
    out = []
    extracted = {(n["item_id"], n["field"]) for n in notes}
    upstream = set(pm.UPSTREAM_ONLY)
    for it in items:
        for field in sorted(upstream):
            if field not in it and (it["item_id"], field) not in extracted:
                out.append(f"{it['item_id']}.{field} (absent in source)")
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(
            "usage: normalizer.py <file> [--format cursor-plan|work-package|rich-md]"
        )
    path = sys.argv[1]
    fmt = None
    if "--format" in sys.argv:
        fmt = sys.argv[sys.argv.index("--format") + 1]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    print(json.dumps(normalize(text, format=fmt), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
