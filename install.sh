#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${OCHA_REPO_URL:-https://github.com/appsdave/ocha.git}"
BRANCH="${OCHA_BRANCH:-main}"
INSTALL_DIR="${OCHA_INSTALL_DIR:-$HOME/.ocha}"
BIN_DIR="${OCHA_BIN_DIR:-$HOME/.local/bin}"

need_command() {
  command -v "$1" >/dev/null 2>&1
}

install_system_packages() {
  if need_command apt-get && need_command sudo; then
    echo "Installing required system packages with apt..."
    sudo apt-get update
    sudo apt-get install -y git python3 python3-pip python3-venv
    return
  fi

  echo "Missing required tools: git, python3, python3-pip, and python3-venv must be installed first." >&2
  exit 1
}

if ! need_command git || ! need_command python3 || ! python3 -m pip --version >/dev/null 2>&1 || ! python3 -m venv --help >/dev/null 2>&1; then
  install_system_packages
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing ocha install in $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  if [ -e "$INSTALL_DIR" ] && [ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
    echo "Install directory already exists and is not empty: $INSTALL_DIR" >&2
    exit 1
  fi
  rm -rf "$INSTALL_DIR"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  echo "Cloning ocha into $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

python3 - <<PY
import sys
from pathlib import Path

checkout = Path(${INSTALL_DIR@Q})
sys.path.insert(0, str(checkout / "ocha"))

from app.install import ensure_bootstrap

bootstrap = ensure_bootstrap(checkout)
print(f"Bootstrapped launcher: {bootstrap.launcher}")
PY

mkdir -p "$BIN_DIR"
ln -sfn "$INSTALL_DIR/.venv/bin/ocha" "$BIN_DIR/ocha"

echo
echo "ocha is installed."
echo "Launch: ocha"
echo "Update: ocha update"

case ":$PATH:" in
  *":$BIN_DIR:"*)
    ;;
  *)
    echo
    echo "Add $BIN_DIR to your PATH if 'ocha' is not found in a new shell:" >&2
    echo "  export PATH=\"$BIN_DIR:\$PATH\"" >&2
    ;;
esac