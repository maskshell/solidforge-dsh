#!/usr/bin/env bash
# install-global.sh — install the @maskshell/solidforge plugin into a dsh
# profile's USER PATCH LAYER, making it available to every session of that
# profile (no preset switching): skills enter the host layer of the registry,
# /solidforge:<skill> colon gestures inject at the pre-step boundary, and
# /solidforge + /arm-tools commands register globally.
#
# Usage:
#   bash scripts/install-global.sh [profile]     install (default profile: web)
#   bash scripts/install-global.sh --revert [profile]   uninstall
#
# Mechanics (verified against dsh-app-boot):
#   - The profile's cordis.patch.yml is the user's own patch layer, applied
#     after every bundle layer and hot-reloaded (HMR) on long-lived surfaces.
#   - A patch entry `- insert: [{id, name}]` adds a root-level row; root rows
#     are unscoped, so their listeners see every agent's scoped events.
#   - The Loader resolves row names from the profile directory's node_modules.
#
# The plugin reads the SolidForge skill bodies LIVE from the installed preset
# ($DSH_HOME/.agent-presets/solidforge) — the preset stays the single source
# of content; the plugin degrades honestly when it is absent.
set -u

PROFILE="web"
if [ "${1:-}" = "--revert" ]; then
  REVERT=1
  [ "${2:-}" != "" ] && PROFILE="$2"
else
  REVERT=0
  [ "${1:-}" != "" ] && PROFILE="$1"
fi

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
PROFILE_DIR="$DSH_HOME/profiles/$PROFILE"
PATCH_FILE="$PROFILE_DIR/cordis.patch.yml"
PKG_DIR="$PROFILE_DIR/node_modules/@maskshell/solidforge"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/packages/solidforge-plugin"
MARKER="id: solidforge"

if [ ! -d "$PROFILE_DIR" ]; then
  echo "error: profile directory not found: $PROFILE_DIR" >&2
  exit 1
fi

if [ "$REVERT" = 1 ]; then
  if [ -f "$PATCH_FILE" ] && grep -q "$MARKER" "$PATCH_FILE"; then
    python3 - "$PATCH_FILE" <<'EOF'
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
# The solidforge entry is appended last; walk up from its id line to the
# '- insert:' line and drop the block through the closing bracket.
start = end = None
for i, line in enumerate(lines):
    if 'id: solidforge' in line:
        end = i
for i in range(end, -1, -1):
    if lines[i].lstrip().startswith('- insert:'):
        start = i
        break
if start is None or end is None:
    sys.exit('revert: solidforge entry shape not recognized in ' + path)
# find the list-closing bracket after the entry (it is the trailing entry)
closing = None
for i in range(end, len(lines)):
    if lines[i].rstrip() == ']':
        closing = i
        break
if closing is None:
    sys.exit('revert: closing bracket not found in ' + path)
del lines[start:closing + 1]
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('  removed solidforge patch entry from', path)
EOF
  else
    echo "  patch entry not present (already reverted)"
  fi
  rm -rf "$PKG_DIR"
  echo "== solidforge plugin uninstalled from profile '$PROFILE'"
  exit 0
fi

mkdir -p "$PKG_DIR/lib"
cp "$SRC/package.json" "$PKG_DIR/package.json"
cp "$SRC/lib/index.js" "$PKG_DIR/lib/index.js"
echo "== installed @maskshell/solidforge -> $PKG_DIR"

if grep -q "$MARKER" "$PATCH_FILE"; then
  echo "  patch entry already present in $PATCH_FILE"
else
  python3 - "$PATCH_FILE" <<'EOF'
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
entry = "- insert:\n    - id: solidforge\n      name: '@maskshell/solidforge'\n"
# Replace the empty list token itself (comments above it stay put); when the
# list is not empty, insert the entry before the closing bracket.
if '[]' in text:
    idx = text.rfind('[]')
    text = text[:idx] + entry + text[idx + 2:]
else:
    idx = text.rfind(']')
    if idx == -1:
        sys.exit('patch file has no closing bracket: ' + path)
    text = text[:idx] + entry + text[idx:]
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('  appended solidforge patch entry to', path)
EOF
fi

echo "== done. The patch layer is hot-reloaded by the running web process;"
echo "   new sessions (any preset) get the five skills, /solidforge:<skill>"
echo "   colon gestures, and the /solidforge + /arm-tools commands."
echo "   Revert: bash scripts/install-global.sh --revert [$PROFILE]"
