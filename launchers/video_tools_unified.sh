#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/video_tools_unified.py"

cd "$PROJECT_ROOT"

echo "===================================="
echo "Video Tools - Unified Launcher"
echo "===================================="

if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
python "$PROJECT_ROOT/scripts/install_ai_upscale_deps.py" || \
    echo "[WARNING] AI upscale deps install failed; PyTorch upscale may be unavailable."

echo "[INFO] Launching Video Tools - Unified..."
python "$PYTHON_SCRIPT"

deactivate
