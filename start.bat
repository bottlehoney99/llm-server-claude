@echo off
chcp 65001 >nul
echo ============================================
echo   Game Dev AI Tutor - Server Start
echo ============================================
echo.

REM Concurrency settings. gemma4:12b uses ~10GB VRAM with one slot on a 12GB GPU,
REM so only 1 parallel request fits safely (2 would risk OOM). Keep 1 model in VRAM.
REM Note: these do NOT apply to an already-running "ollama serve".
REM To apply, fully quit Ollama (incl. tray app) and restart.
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_MAX_LOADED_MODELS=1

echo [1/3] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo   Ollama not running. Starting it...
    start "" ollama serve
    timeout /t 3 >nul
)

echo [2/3] Checking model (gemma4:12b)...
ollama list | findstr "gemma4:12b" >nul
if errorlevel 1 (
    echo   Model not found. Downloading... (about 7.6GB)
    ollama pull gemma4:12b
)

echo [3/3] Starting web server...
echo.
echo   Open http://localhost:8080 in your browser.
echo   Admin page: http://localhost:8080/admin (shutdown token shown below)
echo   Press Ctrl+C in this window to stop.
echo.

REM Use py launcher (Python 3.12 recommended)
py -3.12 server.py
if errorlevel 1 (
    echo.
    echo   py -3.12 failed, trying default python...
    python server.py
)

pause
