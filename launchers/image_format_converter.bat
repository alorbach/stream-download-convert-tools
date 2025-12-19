@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set VENV_DIR=%PROJECT_ROOT%\venv
set PYTHON_SCRIPT=%PROJECT_ROOT%\scripts\image_format_converter.py

cd /d "%PROJECT_ROOT%"

echo ====================================
echo Image Format Converter Launcher
echo ====================================
echo.

if not exist "%VENV_DIR%" (
    echo [INFO] Virtual environment not found. Creating venv...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        echo [ERROR] Please ensure Python 3.7+ is installed
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created
    echo.
)

echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo [INFO] Installing/updating dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Some dependencies may not have installed correctly
)

echo [INFO] Launching Image Format Converter...
echo.

python "%PYTHON_SCRIPT%"

if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%
    pause
)

rem Try to deactivate venv if needed, but don't fail if it doesn't exist
if exist "%VENV_DIR%\Scripts\deactivate.bat" (
    call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul
)
