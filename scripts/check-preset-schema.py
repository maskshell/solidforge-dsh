#!/usr/bin/env python3
"""check-preset-schema.py — deterministic gate for DSH plugin-config schema drift.

Why this exists (2026-09-18 incident): DSH upgraded 0.1.1-rc.2 -> 0.1.5-rc.2 and
`@deepseek-ai/dsh-persona` renamed its config field `text` -> required `prefix`.
The solidforge preset still declared `config: {text: ...}`, so EVERY new session
failed at creation with:

    agent-preset/invalid: preset "solidforge" failed to mount: failed to apply
    loader entry persona: invalid config: $.prefix missing required value

while already-loaded sessions kept working (the preset is mounted per session).
Nothing in the repo caught it — it surfaced as a user-visible GUI failure
("new session does nothing"). This gate turns that diagnosis into a repeatable
check: every loader row in the preset is validated against the installed DSH
packages' declared `Config` schema.

Checks per row:
  - every schema field the package REQUIRES must be present in the row's config;
  - every key the row sets must exist in the schema (catches the rename residue,
    e.g. a stale `text` next to a new `prefix`).

Honest degrade (never a silent green): when the DSH packages are not resolvable
(a bare CI checkout with no DSH install), the gate prints SKIP and exits 0 with
the reason. Stdlib-only (ADR #1).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESET = ROOT / "preset" / "agent.cordis.yml"

NAME_RE = re.compile(r"^(\s*)(?:-\s+)?name:\s*'([^']+)'")
CONFIG_RE = re.compile(r"^(\s*)config:\s*$")
ENTRY_RE = re.compile(r"^(\s*)-\s")


def candidate_roots() -> list[Path]:
    """Directories that may hold the installed @deepseek-ai/* packages."""
    roots: list[Path] = []
    env = os.environ.get("DSH_PKG_ROOT")
    if env:
        roots.append(Path(env))
    home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
    roots.append(home / "node_modules" / "@deepseek-ai")
    npx = Path.home() / ".npm" / "_npx"
    if npx.is_dir():
        roots.extend(sorted(npx.glob("*/node_modules/@deepseek-ai")))
    return roots


def locate_package(name: str) -> Path | None:
    """Resolve '@deepseek-ai/<pkg>[/subpath]' to its directory, if installed."""
    if not name.startswith("@deepseek-ai/"):
        return None
    parts = name.split("/")
    if len(parts) < 2 or not parts[1]:
        return None
    pkg = parts[1]
    for root in candidate_roots():
        candidate = root / pkg
        if candidate.is_dir():
            return candidate
    return None


def parse_rows(text: str) -> list[tuple[str, int, dict[str, int]]]:
    """Extract (name, indent, top-level config keys) for every loader row.

    Regex-based on purpose: the preset is a flat ordered list of `- id:` / `name:`
    / optional `config:` rows, and a YAML parser is not stdlib.
    """
    lines = text.splitlines()
    rows: list[tuple[str, int, dict[str, int]]] = []
    for i, line in enumerate(lines):
        m = NAME_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        name = m.group(2)
        keys: dict[str, int] = {}
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.strip():
                nindent = len(nxt) - len(nxt.lstrip())
                if nindent <= indent and ENTRY_RE.match(nxt):
                    break
            cm = CONFIG_RE.match(nxt)
            if cm and len(cm.group(1)) == indent:
                cfg_indent = len(cm.group(1))
                k = j + 1
                while k < len(lines):
                    body = lines[k]
                    if body.strip():
                        bindent = len(body) - len(body.lstrip())
                        if bindent <= cfg_indent:
                            break
                        if bindent == cfg_indent + 2:
                            km = re.match(r"\s*([A-Za-z_][A-Za-z0-9_-]*):", body)
                            if km:
                                keys[km.group(1)] = k + 1
                            elif body.lstrip().startswith("-"):
                                keys["<list>"] = k + 1
                    k += 1
                break
            j += 1
        rows.append((name, i + 1, keys))
    return rows


def schema_fields(pkg_dir: Path) -> tuple[dict[str, bool], str] | tuple[None, None]:
    """Top-level fields of the package's `Config` interface.

    Returns ({field: is_required}, source_name) or (None, None) when the package
    declares no Config interface (loose string/JSON config).
    """
    candidates = sorted(pkg_dir.glob("lib/types/**/*.d.ts")) + sorted(pkg_dir.glob("lib/*.d.ts"))
    for dts in candidates:
        try:
            txt = dts.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"(?:export\s+)?interface\s+Config\b[^{]*\{", txt)
        if not m:
            continue
        i, depth = m.end(), 1
        body = []
        while i < len(txt) and depth > 0:
            ch = txt[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth > 0:
                body.append(ch)
            i += 1
        fields: dict[str, bool] = {}
        for line in "".join(body).splitlines():
            fm = re.match(r"^    ([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:", line)
            if fm:
                fields[fm.group(1)] = fm.group(2) is None
        if fields:
            return fields, dts.name
    return None, None


def main() -> int:
    if not PRESET.is_file():
        print(f"FAIL: preset not found: {PRESET}", file=sys.stderr)
        return 1

    rows = parse_rows(PRESET.read_text(encoding="utf-8"))
    if not rows:
        print(f"FAIL: no loader rows parsed from {PRESET}", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    skipped_pkgs: set[str] = set()
    unresolved: set[str] = set()

    for name, lineno, keys in rows:
        if name.startswith("cordis:"):
            continue
        pkg_dir = locate_package(name)
        if pkg_dir is None:
            if name.startswith("@deepseek-ai/"):
                unresolved.add(name)
            else:
                skipped_pkgs.add(name)
            continue
        fields, src = schema_fields(pkg_dir)
        if fields is None:
            skipped_pkgs.add(name)
            continue
        checked += 1
        required = [f for f, req in fields.items() if req]
        missing = [f for f in required if f not in keys]
        unknown = [k for k in keys if k != "<list>" and k not in fields]
        for f in missing:
            failures.append(
                f"preset/agent.cordis.yml:{lineno}: row '{name}' omits required config "
                f"field '{f}' (schema: {src}) — mounting this row fails and the whole "
                f"preset refuses to load (new sessions cannot be created)"
            )
        for k in unknown:
            failures.append(
                f"preset/agent.cordis.yml:{lineno}: row '{name}' sets config key '{k}' "
                f"which {src} does not declare (renamed/removed upstream?)"
            )
        if not missing and not unknown and not required and not keys:
            pass

    if failures:
        for f in failures:
            print("FAIL: " + f, file=sys.stderr)
        print(f"\npreset schema: {len(failures)} violation(s)", file=sys.stderr)
        return 1

    if checked == 0:
        print(
            "SKIP: preset schema — no installed @deepseek-ai/* package was resolvable "
            f"and no row carried a typed Config (rows seen: {len(rows)}). "
            "Out of scope on this machine, NOT verified green.",
            file=sys.stderr,
        )
        return 0

    note = ""
    if unresolved:
        note = f" (unresolved: {', '.join(sorted(unresolved))})"
    print(
        f"PASS: preset schema conforms — {checked} row(s) validated against the "
        f"installed DSH Config schemas{note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
