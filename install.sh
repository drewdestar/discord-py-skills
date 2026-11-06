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
  # Windows launcher (harmless on Unix; Windows users take it from the repo).
  [ -f "$(dirname "$0")/newr.bat" ] && cp "$(dirname "$0")/newr.bat" "$BIN_DIR/newr.bat"
else
  curl -fsSL "https://raw.githubusercontent.com/$REPO/main/newr" -o "$BIN_DIR/newr"
fi
chmod +x "$BIN_DIR/newr"

echo "newr installed to $BIN_DIR/newr"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    # Put BIN_DIR on PATH for future shells, then print the line for
    # this shell. Appends once; re-running the installer never
    # duplicates it.
    SHELL_NAME=$(basename "${SHELL:-sh}")
    case "$SHELL_NAME" in
      zsh) RC="$HOME/.zshrc" ;;
      bash) RC="$HOME/.bashrc" ;;
      *) RC="$HOME/.profile" ;;
    esac
    if ! grep -Fqs "$BIN_DIR" "$RC" 2>/dev/null; then
      printf '\nexport PATH="%s:$PATH"  # newr\n' "$BIN_DIR" >> "$RC"
      echo "Added $BIN_DIR to PATH in $RC"
    fi
    echo "For this shell, run:  export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac
echo "Then try:  newr search && newr install slash-commands"
