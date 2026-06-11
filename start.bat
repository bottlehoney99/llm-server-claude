@echo off
chcp 65001 >nul
echo ============================================
echo   Game Dev AI Tutor - Server Start
echo ============================================
echo.

REM 동시 사용(20명) 대비 Ollama 설정: 병렬 2개 처리 + 모델 1개만 VRAM 로딩(OOM 방지)
REM 주의: 이미 떠 있는 ollama serve에는 적용 안 됨. 적용하려면 Ollama를 완전히 종료 후 재시작.
set OLLAMA_NUM_PARALLEL=2
set OLLAMA_MAX_LOADED_MODELS=1

echo [1/3] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo   Ollama not running. Starting it...
    start "" ollama serve
    timeout /t 3 >nul
)

echo [2/3] Checking model (qwen3:8b)...
ollama list | findstr "qwen3:8b" >nul
if errorlevel 1 (
    echo   Model not found. Downloading... (about 5.2GB)
    ollama pull qwen3:8b
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
