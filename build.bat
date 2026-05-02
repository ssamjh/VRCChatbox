@echo off
setlocal
set VENV_DIR=.build_venv

if not exist %VENV_DIR% (
    echo Creating build virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 ( echo Failed to create venv & pause & exit /b 1 )
)

echo Stopping any running instance...
taskkill /f /im VRCChatbox.exe >nul 2>&1

echo Installing / updating dependencies...
%VENV_DIR%\Scripts\python.exe -m pip install --upgrade pip --quiet
%VENV_DIR%\Scripts\pip install python-osc PyQt6 requests websockets pyinstaller --quiet
if errorlevel 1 ( echo Dependency install failed & pause & exit /b 1 )

echo Building...
%VENV_DIR%\Scripts\pyinstaller ^
    --onedir ^
    --windowed ^
    --name VRCChatbox ^
    --noconfirm ^
    --collect-all websockets ^
    app.py
if errorlevel 1 ( echo Build failed & pause & exit /b 1 )

echo.
echo Done: dist\VRCChatbox\VRCChatbox.exe
pause
