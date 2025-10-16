#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_DIR/bin/python"
SCRIPT_FILE="$ROOT_DIR/scripts/video_to_mp3_converter.py"

echo "============================================"
echo "Video to MP3 Converter Launcher"
echo "============================================"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment not found. Creating one..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        echo "[INFO] Make sure Python 3 is installed."
        exit 1
    fi
    echo "[SUCCESS] Virtual environment created."
    echo ""
fi

if [ ! -f "$PYTHON_EXE" ]; then
    echo "[ERROR] Python executable not found in venv."
    echo "[INFO] Expected location: $PYTHON_EXE"
    exit 1
fi

echo "[INFO] Checking dependencies..."
"$PYTHON_EXE" -m pip --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[ERROR] pip not available in virtual environment."
    exit 1
fi

if [ -f "$ROOT_DIR/requirements.txt" ]; then
    echo "[INFO] Installing/updating requirements..."
    "$PYTHON_EXE" -m pip install -q -r "$ROOT_DIR/requirements.txt"
else
    echo "[WARNING] requirements.txt not found."
fi

echo ""
echo "[INFO] Launching Video to MP3 Converter..."
echo ""

"$PYTHON_EXE" "$SCRIPT_FILE"

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Script execution failed."
    exit 1
fi

