#!/bin/sh
# Install newr, the package manager for the discord-py-skills pack.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/drewdestar/discord-py-skills/main/install.sh | sh
# Or, from a clone:
#   sh install.sh
set -e

REPO="drewdestar/discord-py-skills"
NEWR_HOME="${NEWR_HOME:-$HOME/.newr}"
BIN_DIR="$NEWR_HOME/bin"

mkdir -p "$BIN_DIR"

if [ -f "$(dirname "$0")/newr" ]; then
  # Running from a clone: install the local copy.
  cp "$(dirname "$0")/newr" "$BIN_DIR/newr"
else
  curl -fsSL "https://raw.githubusercontent.com/$REPO/main/newr" -o "$BIN_DIR/newr"
fi
chmod +x "$BIN_DIR/newr"

echo "newr installed to $BIN_DIR/newr"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add it to your PATH:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
echo "Then try:  newr search && newr install slash-commands"
