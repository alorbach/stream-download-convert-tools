#!/bin/bash
# MP3 to Video Converter Launcher for Linux/Mac
# Copyright 2025 Andre Lorbach

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to the root directory
cd "$ROOT_DIR" || exit 1

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment"
    exit 1
fi

# Install/update requirements
echo "Installing/updating requirements..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install requirements"
    exit 1
fi

# Launch the application
echo "Starting MP3 to Video Converter..."
python scripts/mp3_to_video_converter.py

# Check exit status
if [ $? -ne 0 ]; then
    echo ""
    echo "Application exited with an error"
    read -p "Press Enter to continue..."
fi
