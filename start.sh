#!/bin/bash
echo "============================================"
echo "  게임 개발 AI 튜터 서버 시작"
echo "============================================"
echo

# 동시 사용(20명) 대비 Ollama 설정: 병렬 2개 처리 + 모델 1개만 VRAM 로딩(OOM 방지)
# 주의: 이미 떠 있는 ollama serve에는 적용 안 됨. 적용하려면 Ollama 종료 후 재시작.
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1

# 1. Ollama 실행 확인
echo "[1/3] Ollama 상태 확인 중..."
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  Ollama가 실행되고 있지 않습니다. 백그라운드로 시작합니다..."
    ollama serve >/dev/null 2>&1 &
    sleep 3
fi

# 2. 모델 확인
echo "[2/3] 모델 확인 중... (gemma4:12b)"
if ! ollama list | grep -q "gemma4:12b"; then
    echo "  모델이 없습니다. 다운로드를 시작합니다... (약 7.6GB)"
    ollama pull gemma4:12b
fi

# 3. 서버 실행
echo "[3/3] 웹 서버 시작..."
echo
echo "  브라우저에서 http://localhost:8080 으로 접속하세요."
echo "  종료하려면 Ctrl+C 를 누르세요."
echo
python3 server.py
