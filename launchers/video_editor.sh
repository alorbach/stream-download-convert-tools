#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/video_editor.py"

cd "$PROJECT_ROOT"

echo "===================================="
echo "Video Editor Launcher"
echo "===================================="
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment not found. Creating venv..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        echo "[ERROR] Please ensure Python 3.7+ is installed"
        exit 1
    fi
    echo "[SUCCESS] Virtual environment created"
    echo ""
fi

echo "[INFO] Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "[INFO] Installing/updating dependencies..."
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "[WARNING] Some dependencies may not have installed correctly"
fi

echo "[INFO] Launching Video Editor..."
echo ""

python "$PYTHON_SCRIPT"

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Application exited with error code $?"
    read -p "Press Enter to continue..."
fi

# Try to deactivate venv gracefully
deactivate 2>/dev/null || true

