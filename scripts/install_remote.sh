#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/ajpmeche-ux/ups-monitor.git"
TARGET_DIR="${1:-ups-monitor}"

if [[ -d "$TARGET_DIR" ]]; then
  echo "Directory '$TARGET_DIR' already exists."
else
  git clone "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Installation complete. Activate the environment with:"
echo "  source $TARGET_DIR/.venv/bin/activate"
echo "Then run the app with:"
echo "  python -m ups_monitor"
