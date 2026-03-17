#!/usr/bin/env bash
# ocha installer — clone to ~/.ocha and link the command globally
set -e

INSTALL_DIR="${OCHA_HOME:-$HOME/.ocha}"
REPO_URL="git@github.com:appsdave/ocha.git"
BIN_NAME="ocha"

echo "🚀 Installing ocha..."

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
  echo "   Updating existing installation at $INSTALL_DIR"
  cd "$INSTALL_DIR"
  git pull origin main 2>/dev/null || git pull
else
  echo "   Cloning to $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Install dependencies
echo "   Installing dependencies..."
npm install --production 2>&1 | tail -1

# Create symlink in a PATH directory
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/bin/ocha.js" "$BIN_DIR/$BIN_NAME"
chmod +x "$INSTALL_DIR/bin/ocha.js"

# Check if BIN_DIR is in PATH
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
  SHELL_RC=""
  if [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
  elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
  elif [ -f "$HOME/.profile" ]; then
    SHELL_RC="$HOME/.profile"
  fi

  if [ -n "$SHELL_RC" ]; then
    echo "" >> "$SHELL_RC"
    echo '# ocha CLI' >> "$SHELL_RC"
    echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
    echo "   Added $BIN_DIR to PATH in $SHELL_RC"
    echo "   Run: source $SHELL_RC"
  else
    echo "   ⚠ Add $BIN_DIR to your PATH manually"
  fi
fi

echo ""
echo "✅ ocha installed!"
echo "   Location: $INSTALL_DIR"
echo "   Command:  $BIN_DIR/$BIN_NAME"
echo ""
echo "   To update later: ocha self-update"
echo "   To uninstall:    rm -rf $INSTALL_DIR $BIN_DIR/$BIN_NAME"
