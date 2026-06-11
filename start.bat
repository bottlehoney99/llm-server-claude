@echo off
chcp 65001 >nul
echo ============================================
echo   게임 개발 AI 튜터 서버 시작
echo ============================================
echo.

REM 1. Ollama 실행 확인
echo [1/3] Ollama 상태 확인 중...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo   Ollama가 실행되고 있지 않습니다. 새 창에서 Ollama를 시작합니다...
    start "" ollama serve
    timeout /t 3 >nul
)

REM 2. 모델 확인
echo [2/3] 모델 확인 중... (llama3.1:8b)
ollama list | findstr "llama3.1:8b" >nul
if errorlevel 1 (
    echo   모델이 없습니다. 다운로드를 시작합니다... (약 4.7GB)
    ollama pull llama3.1:8b
)

REM 3. 서버 실행
echo [3/3] 웹 서버 시작...
echo.
echo   브라우저에서 http://localhost:8080 으로 접속하세요.
echo   종료하려면 이 창에서 Ctrl+C 를 누르세요.
echo.
python server.py

pause
