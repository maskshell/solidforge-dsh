#!/usr/bin/env bash
# install.sh — install the solidforge preset into the DSH user preset root and
# bake the installed path into the dynamic plugin sources.
#
#   bash scripts/install.sh
#
# - copies preset/ -> $DSH_HOME/.agent-presets/solidforge/ (rsync; stale files removed)
# - copies plugins/*.host.js -> preset's plugins/ with __SOLIDFORGE_PRESET_ROOT__
#   replaced by the real install path (so cordis_define can load them verbatim)
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
DEST="$DSH_HOME/.agent-presets/solidforge"

echo "== installing solidforge preset -> $DEST"
mkdir -p "$DEST"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude '.DS_Store' --exclude '__pycache__' \
    "$HERE/preset/" "$DEST/"
else
  rm -rf "$DEST" && cp -R "$HERE/preset" "$DEST"
fi

mkdir -p "$DEST/plugins"
rm -f "$DEST"/plugins/*.host.js   # stale baked plugins (e.g. retired sources) removed
for src in "$HERE"/plugins/*.host.js; do
  name="$(basename "$src")"
  sed "s|__SOLIDFORGE_PRESET_ROOT__|$DEST|g" "$src" > "$DEST/plugins/$name"
  chmod 644 "$DEST/plugins/$name"
  echo "  baked $name -> $DEST/plugins/$name"
done

echo "== installed. Files:"
find "$DEST" -type f | wc -l
python3 "$HERE/scripts/preset-stamp.py" write "$DEST" "$HERE" || echo "  (stamp write failed — continue)"
echo "== next steps:"
echo "  1. Start a session on the 'solidforge' preset (or any preset — the"
echo "     global plugin face via scripts/install-global.sh)."
echo "  2. Define + run the structural plugins once per session (cordis tools):"
echo "     - plugins/loop-gates.host.js   (tool-event gates)"
echo "     - plugins/run-record.host.js   (rightness-invariant run record)"
echo "     - plugins/hetero-review.host.js (cross-provider subprocess review)"
echo "  3. Optional global face (any session, no preset switching):"
echo "     bash scripts/install-global.sh [profile]"
echo "  4. Arm a target project: the arm-tools command (or python3 \$DEST/skills/parallel-development/infra/install/arm.py <project>)."
