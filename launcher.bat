@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%
set VENV_DIR=%ROOT_DIR%\venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

REM Add Deno to PATH for yt-dlp JavaScript runtime support
set "DENO_PATH=%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe"
if exist "%DENO_PATH%\deno.exe" call :AddDenoToPath

goto :ContinueStartup

:AddDenoToPath
set "PATH=%DENO_PATH%;%PATH%"
goto :eof

:ContinueStartup

echo ============================================
echo Audio Tools - Main Launcher
echo ============================================
echo.

REM Check if virtual environment exists
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

REM Check if Python executable exists
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found in venv.
    echo [INFO] Expected location: %PYTHON_EXE%
    pause
    exit /b 1
)

REM Install/update dependencies
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
echo [INFO] Launching Launcher GUI (no console window)...
echo.

REM Launch the GUI with pythonw.exe so no command prompt window stays open
set PYTHONW_EXE=%VENV_DIR%\Scripts\pythonw.exe
if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" "%ROOT_DIR%\scripts\launcher_gui.py"
) else (
    "%PYTHON_EXE%" "%ROOT_DIR%\scripts\launcher_gui.py"
    if errorlevel 1 (
        echo [ERROR] Failed to launch GUI launcher.
        pause
        exit /b 1
    )
)

endlocal
