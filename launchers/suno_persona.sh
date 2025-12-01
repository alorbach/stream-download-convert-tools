#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/suno_persona.py"

cd "$PROJECT_ROOT"

echo "===================================="
echo "Suno Persona Manager Launcher"
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

echo "[INFO] Launching Suno Persona Manager..."
echo ""

python "$PYTHON_SCRIPT"

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Application exited with error"
fi

deactivate 2>/dev/null

