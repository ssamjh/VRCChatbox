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
%VENV_DIR%\Scripts\python.exe -m pip install --upgrade pip
%VENV_DIR%\Scripts\pip install python-osc PyQt6 requests websockets pyinstaller bleak faster-whisper sounddevice webrtcvad-wheels numpy nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12
if errorlevel 1 ( echo Dependency install failed & pause & exit /b 1 )

echo Building...
REM nvidia-cublas-cu12 / nvidia-cudnn-cu12 supply the CUDA runtime DLLs CTranslate2
REM loads for GPU inference. Bundling them adds ~1.5-2 GB but lets the .exe use the
REM GPU. whisper_stt._register_cuda_dll_dirs() adds their bundled bin dirs to the
REM DLL search path at runtime. CPU still works as a fallback.
%VENV_DIR%\Scripts\pyinstaller ^
    --onedir ^
    --windowed ^
    --name VRCChatbox ^
    --noconfirm ^
    --additional-hooks-dir pyinstaller_hooks ^
    --collect-all websockets ^
    --collect-all bleak ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --collect-all sounddevice ^
    --collect-all nvidia ^
    --collect-binaries nvidia.cublas ^
    --collect-binaries nvidia.cudnn ^
    --collect-binaries nvidia.cuda_runtime ^
    --collect-binaries nvidia.cuda_nvrtc ^
    --hidden-import PyQt6.QtSvg ^
    --hidden-import bleak.backends.winrt ^
    --hidden-import webrtcvad ^
    app.py
if errorlevel 1 ( echo Build failed & pause & exit /b 1 )

echo.
echo Done: dist\VRCChatbox\VRCChatbox.exe
pause
