@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_DIR=%ROOT_DIR%\venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set SCRIPT_FILE=%ROOT_DIR%\scripts\audio_modifier.py

echo ============================================
echo Audio Modifier Launcher
echo ============================================
echo.

if not exist "%VENV_DIR%\" (
    echo [INFO] Virtual environment not found. Creating one...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo [INFO] Make sure Python is installed and in PATH.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.
    echo.
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found in venv.
    echo [INFO] Expected location: %PYTHON_EXE%
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not available in virtual environment.
    pause
    exit /b 1
)

if exist "%ROOT_DIR%\requirements.txt" (
    echo [INFO] Installing/updating requirements...
    "%PYTHON_EXE%" -m pip install -q -r "%ROOT_DIR%\requirements.txt"
) else (
    echo [WARNING] requirements.txt not found.
)

echo.
echo [INFO] Launching Audio Modifier...
echo.

"%PYTHON_EXE%" "%SCRIPT_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] Script execution failed.
    pause
    exit /b 1
)

endlocal

