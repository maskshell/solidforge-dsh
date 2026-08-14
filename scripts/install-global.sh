#!/usr/bin/env bash
# install-global.sh — install the @maskshell/solidforge plugin into a dsh
# profile's USER PATCH LAYER, making it available to every session of that
# profile (no preset switching): skills enter the host layer of the registry,
# /solidforge:<skill> colon gestures inject at the pre-step boundary, and
# /solidforge + /arm-tools commands register globally.
#
# Usage:
#   bash scripts/install-global.sh [profile] [--with-persona]
#   bash scripts/install-global.sh --revert [profile]
#
# Flags:
#   --with-persona  additive `solidforge:discipline` system-prompt section
#                   (two-axis discipline + abbreviation map) for ANY preset
#   (gates and commands are NOT available from the patch layer: its context
#   cannot see the tools/subprocess/commands services — the loader only
#   bridges services declared in `inject`. Mount the same package as a
#   solidforge PRESET row with `config: {commands: true}` for the commands;
#   the per-session dynamic plugins keep owning the gates.)
#
# Mechanics (verified against dsh-app-boot):
#   - The profile's cordis.patch.yml is the user's own patch layer, applied
#     after every bundle layer and hot-reloaded (HMR) on long-lived surfaces.
#   - A patch entry `- insert: [{id, name, config}]` adds a root-level row;
#     root rows are unscoped, so their listeners see every agent's events.
#   - The Loader resolves row names from the profile directory's node_modules.
#
# The plugin reads the SolidForge skill bodies LIVE from the installed preset
# ($DSH_HOME/.agent-presets/solidforge) — the preset stays the single source
# of content; the plugin degrades honestly when it is absent.
set -u

PROFILE="web"
REVERT=0
WITH_PERSONA=0
WITH_GATES=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --revert) REVERT=1 ;;
    --with-persona) WITH_PERSONA=1 ;;
    
    -*) echo "error: unknown flag: $1" >&2; exit 2 ;;
    *) PROFILE="$1" ;;
  esac
  shift
done

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
PROFILE_DIR="$DSH_HOME/profiles/$PROFILE"
PATCH_FILE="$PROFILE_DIR/cordis.patch.yml"
PKG_DIR="$DSH_HOME/node_modules/@maskshell/solidforge"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/packages/solidforge-plugin"
MARKER="id: solidforge"

if [ ! -d "$PROFILE_DIR" ]; then
  echo "error: profile directory not found: $PROFILE_DIR" >&2
  exit 1
fi

strip_entry() {
  # Remove EVERY top-level `- insert:` entry whose id is solidforge (the
  # installer always re-appends one fresh entry afterwards). The patch file is
  # a top-level BLOCK sequence (no brackets); after removing the last entry,
  # an empty `[]` list is restored so the file stays valid.
  python3 - "$PATCH_FILE" <<'EOF'
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
kept = []
i = 0
while i < len(lines):
    if lines[i].lstrip().startswith('- insert:') and i + 1 < len(lines) and 'id: solidforge' in lines[i + 1]:
        i += 1
        while i < len(lines) and not (lines[i].startswith('- ') or lines[i].startswith('#')):
            i += 1
        continue
    kept.append(lines[i])
    i += 1
while kept and kept[-1].strip() == '':
    kept.pop()
body = ''.join(kept)
other_items = any(line.startswith('- ') for line in kept)
if not other_items:
    body = body.rstrip('\n') + '\n[]\n'
with open(path, 'w', encoding='utf-8') as f:
    f.write(body)
EOF
}

append_entry() {
  python3 - "$PATCH_FILE" "$WITH_PERSONA" "$WITH_GATES" <<'EOF'
import sys
path = sys.argv[1]
persona = sys.argv[2] == '1'
gates = sys.argv[3] == '1'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
lines = ["- insert:", "    - id: solidforge", "      name: '@maskshell/solidforge'"]
if persona or gates:
    lines.append("      config:")
    if persona:
        lines.append("        persona: true")
    if gates:
        lines.append("        gates: true")
entry = "\n".join(lines) + "\n"
if '[]' in text:
    idx = text.rfind('[]')
    text = text[:idx] + entry + text[idx + 2:]
else:
    text = text.rstrip('\n') + '\n' + entry
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('  appended solidforge patch entry to', path)
EOF
}

if [ "$REVERT" = 1 ]; then
  if [ -f "$PATCH_FILE" ] && grep -q "$MARKER" "$PATCH_FILE"; then
    strip_entry
    echo "  removed solidforge patch entry from $PATCH_FILE"
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
  strip_entry && echo "  replaced existing solidforge patch entry"
fi
append_entry

echo "== done. The patch layer is hot-reloaded by the running web process;"
echo "   new sessions (any preset) get the five skills, /solidforge:<skill>"
echo "   colon gestures, and the /solidforge + /arm-tools commands."
[ "$WITH_PERSONA" = 1 ] && echo "   persona: true — additive discipline section in every session."
echo "   Revert: bash scripts/install-global.sh --revert [$PROFILE]"
