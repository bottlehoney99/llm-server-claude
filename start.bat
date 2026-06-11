@echo off
chcp 65001 >nul
echo ============================================
echo   Game Dev AI Tutor - Server Start
echo ============================================
echo.

echo [1/3] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo   Ollama not running. Starting it...
    start "" ollama serve
    timeout /t 3 >nul
)

echo [2/3] Checking model (llama3.1:8b)...
ollama list | findstr "llama3.1:8b" >nul
if errorlevel 1 (
    echo   Model not found. Downloading... (about 4.7GB)
    ollama pull llama3.1:8b
)

echo [3/3] Starting web server...
echo.
echo   Open http://localhost:8080 in your browser.
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
