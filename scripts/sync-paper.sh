#!/usr/bin/env bash
# sync-paper.sh — explicit snapshot sync from the canonical paper KB.
# Copies the four paper artifacts VERBATIM (no transforms) and reports freshness.
# The snapshot must NEVER drift silently: run this only as a deliberate act.
set -euo pipefail

KB="${FEDAOT_KB:-$HOME/dev/ws-wiki/fedaot-kb}/docs/papers"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HERE/docs/papers"

for f in spec-gaming-orthogonal-axis.md spec-gaming-orthogonal-axis.pdf \
         spec-gaming-orthogonal-axis.tex spec-gaming-orthogonal-axis.pub-readiness.md; do
  if [ ! -f "$KB/$f" ]; then
    echo "error: canonical artifact missing: $KB/$f (set FEDAOT_KB to override the KB root)" >&2
    exit 1
  fi
done

for f in spec-gaming-orthogonal-axis.md spec-gaming-orthogonal-axis.pdf \
         spec-gaming-orthogonal-axis.tex spec-gaming-orthogonal-axis.pub-readiness.md; do
  if ! cmp -s "$KB/$f" "$DEST/$f"; then
    cp "$KB/$f" "$DEST/$f"
    echo "  synced $f"
  else
    echo "  unchanged $f"
  fi
done

echo "freshness:"
for f in spec-gaming-orthogonal-axis.md spec-gaming-orthogonal-axis.pdf; do
  printf "  %-40s %s\n" "$f" "$(stat -f '%Sm' "$KB/$f")"
done
echo "note: the PDF must be at least as new as the .md; regenerate from the .tex when it is not."
