#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/thakoralpesh3/apk-tv-converter-agent.git"
INSTALL_DIR="${HOME}/apk-tv-converter-agent"

echo "============================================================"
echo "  🚀 APK Cross-Converter AI Agent — Fast Cloud Installer   "
echo "============================================================"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository from GitHub..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Ensure tools
./setup_tools.sh

# Python virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

echo ""
echo "✓ Installation complete!"
echo "Starting APK TV Converter AI Studio Web Dashboard on http://localhost:8877 ..."
./launch_agent.sh --gui
