@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set VENV_DIR=%PROJECT_ROOT%\venv
set PYTHON_SCRIPT=%PROJECT_ROOT%\scripts\video_tools_unified.py

cd /d "%PROJECT_ROOT%"

echo ====================================
echo Video Tools - Unified Launcher
echo ====================================
echo.

if not exist "%VENV_DIR%" (
    echo [INFO] Virtual environment not found. Creating venv...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
python "%PROJECT_ROOT%\scripts\install_ai_upscale_deps.py"
if errorlevel 1 (
    echo [WARNING] AI upscale deps install failed; PyTorch upscale may be unavailable.
)

echo [INFO] Launching Video Tools - Unified...
python "%PYTHON_SCRIPT%"

if errorlevel 1 (
    echo [ERROR] Application exited with error code %errorlevel%
    pause
)

deactivate
