@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%
set VENV_DIR=%ROOT_DIR%\venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

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
echo [INFO] Available Audio Tools:
echo.
echo 1. Audio Tools Unified
echo 2. YouTube Downloader
echo 3. Video to MP3 Converter  
echo 4. Audio Modifier
echo 5. Exit
echo.

:menu
set /p choice="Please select a tool (1-5): "

if "%choice%"=="1" goto audio_unified
if "%choice%"=="2" goto youtube_downloader
if "%choice%"=="3" goto video_converter
if "%choice%"=="4" goto audio_modifier
if "%choice%"=="5" goto exit
echo [ERROR] Invalid choice. Please select 1-5.
goto menu

:youtube_downloader
echo.
echo [INFO] Launching YouTube Downloader...
call "%ROOT_DIR%\launchers\youtube_downloader.bat"
goto end

:video_converter
echo.
echo [INFO] Launching Video to MP3 Converter...
call "%ROOT_DIR%\launchers\video_to_mp3_converter.bat"
goto end

:audio_modifier
echo.
echo [INFO] Launching Audio Modifier...
call "%ROOT_DIR%\launchers\audio_modifier.bat"
goto end

:audio_unified
echo.
echo [INFO] Launching Audio Tools Unified...
call "%ROOT_DIR%\launchers\audio_tools_unified.bat"
goto end

:exit
echo.
echo [INFO] Goodbye!
goto end

:end
echo.
pause
endlocal
