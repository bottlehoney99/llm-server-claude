# 🎮 게임 개발 AI 튜터 서버

특성화고 1학년 학생들이 pygame으로 게임을 만들도록 돕는 로컬 LLM 서버입니다.
개인 PC에서 Ollama(llama3.1:8b)를 띄우고, 학생들이 웹 브라우저로 접속합니다.

---

## 📁 폴더 구성

```
game_tutor_server/
├── server.py            # 메인 서버 (FastAPI + Ollama 연결)
├── requirements.txt     # 파이썬 라이브러리 목록
├── start.bat            # Windows 실행 스크립트
├── start.sh             # Mac/Linux 실행 스크립트
├── README.md            # 이 문서
└── static/
    ├── index.html       # 채팅 웹페이지
    ├── style.css        # 디자인
    └── script.js        # 채팅 동작 (스트리밍, 코드복사 등)
```

---

## 🚀 빠른 시작

### 사전 준비 (최초 1회)

1. **Ollama 설치** — https://ollama.com/download
2. **Python 3.10 이상 설치** — https://python.org
3. **라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   ```

### 실행

**Windows:** `start.bat` 더블클릭
**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

실행하면 Ollama 확인 → 모델 다운로드 → 서버 시작이 자동으로 진행됩니다.
브라우저에서 **http://localhost:8080** 으로 접속하세요.

> 수동 실행: `python server.py` (Ollama가 이미 켜져 있을 때)

---

## 🌐 학생들이 접속하게 하기 (Cloudflare Tunnel)

집 PC 서버를 학교에서 접속하려면 터널이 필요합니다.

```bash
# cloudflared 설치 후
cloudflared tunnel --url http://localhost:8080
```

실행하면 `https://랜덤이름.trycloudflare.com` 주소가 나옵니다. 이 주소를 학생에게 공유하세요.

> ⚠️ **보안 주의:** 이 임시 터널은 주소를 아는 누구나 접속할 수 있습니다.
> 실제 수업 배포 시에는 Cloudflare Access로 학교 이메일 인증을 거는 것을 권장합니다.
> (명세서 v2 문서의 보안 섹션 참고)

---

## ⚙️ 설정 바꾸기

`server.py` 상단 또는 환경변수로 조정할 수 있습니다.

| 항목 | 기본값 | 설명 |
|------|--------|------|
| MODEL_NAME | llama3.1:8b | 사용할 모델 |
| PORT | 8080 | 서버 포트 |
| MAX_HISTORY_TURNS | 6 | 기억할 대화 턴 수 |
| num_predict | 1536 | 응답 최대 길이 |
| num_ctx | 8192 | 컨텍스트 크기 |

환경변수 예시:
```bash
# 다른 모델로 바꾸기
MODEL_NAME=qwen2.5:7b python server.py

# 포트 바꾸기
PORT=3000 python server.py
```

---

## 👥 동시 접속 (중요)

Ollama는 기본적으로 **한 번에 1개 요청만** 처리합니다.
20명이 동시에 쓰면 순서대로 처리되어 뒷사람이 오래 기다립니다.

병렬 처리를 늘리려면 Ollama 환경변수를 설정하세요:

```bash
# Windows (시스템 환경변수에 추가)
OLLAMA_NUM_PARALLEL=2

# Mac/Linux
export OLLAMA_NUM_PARALLEL=2
```

> RTX 5070 12GB 기준 2~3개 병렬이 적당합니다. 설정 후 `nvidia-smi`로 VRAM을 확인하세요.

---

## 🔧 문제 해결

| 증상 | 원인 / 해결 |
|------|------------|
| "Ollama 미연결" 표시 | Ollama가 꺼져 있음 → `ollama serve` 실행 |
| "모델 로딩 필요" 표시 | 모델 미설치 → `ollama pull llama3.1:8b` |
| 응답이 너무 느림 | GPU 미사용 가능성 → `ollama ps`로 `100% GPU` 확인 |
| 영어로 답변함 | 모델 한계 → EXAONE/Qwen 등 한국어 모델로 교체 |
| 응답이 중간에 잘림 | `num_predict` 값을 늘리기 (server.py) |
| 포트 충돌 | 다른 프로그램이 8080 사용 중 → PORT 변경 |

---

## 📝 기능 요약

- ✅ Ollama 로컬 모델 연결 + 실시간 스트리밍 응답
- ✅ 게임 개발 에이전트 시스템 프롬프트 내장 (한국어 강제)
- ✅ 세션별 대화 기록 유지 (서버 메모리)
- ✅ 코드 블록 자동 강조 + 복사 버튼
- ✅ 빠른 질문 버튼 (창 만들기, 아이디어 추천 등)
- ✅ 서버 상태 표시 (Ollama 연결/모델 로딩)
- ✅ 모바일 반응형

---

## ⚠️ 한계 (배포 전 확인)

- 대화 기록이 **서버 메모리에만** 저장됩니다. 재시작하면 사라집니다.
  (영구 저장이 필요하면 SQLite 연동 필요)
- 로그인/계정 기능이 없습니다. (접근 통제는 Cloudflare Access로)
- pygame 코드는 학생 PC에서 직접 실행해야 합니다. (서버에서 실행 불가)
