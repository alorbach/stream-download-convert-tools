#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$SCRIPT_DIR"
VENV_DIR="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_DIR/bin/python"

echo "============================================"
echo "Audio Tools - Main Launcher"
echo "============================================"
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment not found. Creating one..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        echo "[INFO] Make sure Python 3.7+ is installed and in PATH."
        exit 1
    fi
    echo "[SUCCESS] Virtual environment created."
    echo ""
fi

# Check if Python executable exists
if [ ! -f "$PYTHON_EXE" ]; then
    echo "[ERROR] Python executable not found in venv."
    echo "[INFO] Expected location: $PYTHON_EXE"
    exit 1
fi

# Install/update dependencies
echo "[INFO] Checking dependencies..."
"$PYTHON_EXE" -m pip --version >/dev/null 2>&1
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
echo "[INFO] Available Audio/Video Tools:"
echo ""
echo "1. Audio Tools Unified"
echo "2. YouTube Downloader"
echo "3. Video to MP3 Converter"
echo "4. Audio Modifier"
echo "5. MP3 to Video Converter"
echo "6. Video Editor"
echo "7. Exit"
echo ""

while true; do
    read -p "Please select a tool (1-7): " choice
    
    case $choice in
        1)
            echo ""
            echo "[INFO] Launching Audio Tools Unified..."
            bash "$ROOT_DIR/launchers/audio_tools_unified.sh"
            break
            ;;
        2)
            echo ""
            echo "[INFO] Launching YouTube Downloader..."
            bash "$ROOT_DIR/launchers/youtube_downloader.sh"
            break
            ;;
        3)
            echo ""
            echo "[INFO] Launching Video to MP3 Converter..."
            bash "$ROOT_DIR/launchers/video_to_mp3_converter.sh"
            break
            ;;
        4)
            echo ""
            echo "[INFO] Launching Audio Modifier..."
            bash "$ROOT_DIR/launchers/audio_modifier.sh"
            break
            ;;
        5)
            echo ""
            echo "[INFO] Launching MP3 to Video Converter..."
            bash "$ROOT_DIR/launchers/mp3_to_video_converter.sh"
            break
            ;;
        6)
            echo ""
            echo "[INFO] Launching Video Editor..."
            bash "$ROOT_DIR/launchers/video_editor.sh"
            break
            ;;
        7)
            echo ""
            echo "[INFO] Goodbye!"
            exit 0
            ;;
        *)
            echo "[ERROR] Invalid choice. Please select 1-7."
            ;;
    esac
done

echo ""
read -p "Press Enter to continue..."
