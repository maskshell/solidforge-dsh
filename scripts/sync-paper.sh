#!/usr/bin/env bash
# sync-paper.sh — explicit snapshot sync from the canonical paper KB.
# Copies the four paper artifacts VERBATIM (no transforms) and reports freshness.
# The snapshot must NEVER drift silently: run this only as a deliberate act.
set -euo pipefail

KB="${FEDAOT_KB:-$HOME/dev/ws-wiki/fedaot-kb}/docs/papers"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HERE/docs/papers"

FILES="spec-gaming-orthogonal-axis.md spec-gaming-orthogonal-axis.pdf \
spec-gaming-orthogonal-axis.tex spec-gaming-orthogonal-axis.pub-readiness.md \
spec-gaming-orthogonal-axis.convergence.json spec-gaming-orthogonal-axis.loopx-reconvergence.json \
loopx-research.md loopx-research.psv/coverage-record.json"

for f in $FILES; do
  if [ ! -f "$KB/$f" ]; then
    echo "error: canonical artifact missing: $KB/$f (set FEDAOT_KB to override the KB root)" >&2
    exit 1
  fi
done

for f in $FILES; do
  mkdir -p "$DEST/$(dirname "$f")"
  if ! cmp -s "$KB/$f" "$DEST/$f"; then
    cp "$KB/$f" "$DEST/$f"
    echo "  synced $f"
  else
    echo "  unchanged $f"
  fi
done

if ! diff -rq "$KB/spec-gaming-orthogonal-axis.pub-readiness.csr" "$DEST/spec-gaming-orthogonal-axis.pub-readiness.csr" >/dev/null 2>&1; then
  rsync -a --delete --exclude '.DS_Store' "$KB/spec-gaming-orthogonal-axis.pub-readiness.csr/" "$DEST/spec-gaming-orthogonal-axis.pub-readiness.csr/"
  echo "  synced spec-gaming-orthogonal-axis.pub-readiness.csr/"
else
  echo "  unchanged spec-gaming-orthogonal-axis.pub-readiness.csr/"
fi

echo "freshness:"
if stat -c '%y' /dev/null >/dev/null 2>&1; then
  STAT_FMT='%y'   # GNU
else
  STAT_FMT='%Sm'  # BSD/macOS
fi
for f in spec-gaming-orthogonal-axis.md spec-gaming-orthogonal-axis.pdf; do
  printf "  %-40s %s\n" "$f" "$(stat -f "$STAT_FMT" "$KB/$f" 2>/dev/null || stat -c "$STAT_FMT" "$KB/$f")"
done
echo "note: the PDF must be at least as new as the .md; regenerate from the .tex when it is not."
