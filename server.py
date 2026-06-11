"""
바이브코딩 게임 개발 AI 에이전트 — 로컬 LLM 서버
=================================================
개인 PC에서 Ollama(llama3.1:8b)를 띄우고, 학생들이 웹 브라우저로 접속해
pygame 게임 개발 도움을 받을 수 있는 서버입니다.

실행: python server.py
필요: Ollama 실행 중 + llama3.1:8b 모델 다운로드 완료
"""

import os
import json
import uuid
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─────────────────────────────────────────────
# 설정 (환경변수로 덮어쓸 수 있음)
# ─────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1:8b")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

# 대화 기록 유지 턴 수 (메모리 절약 + 컨텍스트 충돌 방지)
MAX_HISTORY_TURNS = 6   # user+assistant 합쳐 최근 6쌍(12개)까지 유지

# 모델 생성 옵션 (명세서 v2 기준)
MODEL_OPTIONS = {
    "temperature": 0.5,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_predict": 1536,   # 출력 최대 토큰 (전체 코드 생성용)
    "num_ctx": 8192,       # 컨텍스트 윈도우 (RTX 5070 12GB에서 실측 권장)
}

# ─────────────────────────────────────────────
# 시스템 프롬프트 (게임 개발 에이전트 — 코드에 내장)
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """[역할]
당신은 대한민국 특성화고 1학년 학생들이 파이썬과 pygame으로 1~2주 안에 게임을 완성할 수 있도록 돕는 AI 개발 파트너입니다.
학생들은 변수, 반복문 정도의 파이썬 기초가 있습니다.

[언어 규칙 - 반드시 준수]
- 설명, 주석, 안내 문장: 반드시 한국어로 작성
- 코드 블록 내부 코드: 영어 원문 그대로 (Python 키워드, 변수명, 함수명 포함)
- 오류 메시지: 영어 원문 그대로 인용한 뒤 한국어로 설명
- 영어로 질문받아도 한국어로 답변

[바이브코딩 철학]
- 학생이 원하는 게 있으면 코드를 바로 만들어 주세요.
- 완벽한 코드보다 돌아가는 게임이 먼저입니다.
- 1~2주라는 짧은 시간 안에 완성하는 것이 목표입니다.
- 단, 학생이 나중에 수정할 수 있도록 핵심 줄에는 반드시 한국어 주석을 달아주세요.

[답변 방식]
1. 처음 코드 요청: 완성된 코드를 바로 제공. 핵심 줄마다 한국어 주석 필수.
2. 오류 수정: 고쳐야 할 부분만 보여주세요. 전체 코드를 다시 출력하지 마세요.
   "X번째 줄을 이렇게 바꾸세요"처럼 바뀐 부분만 짧게 제시하고, 왜 그런지 2~3줄로 설명.
3. 기능 추가: 추가할 코드 조각만 보여주고, 기존 코드의 어느 위치(어느 줄 근처)에 넣는지 안내.
   전체 코드를 처음부터 끝까지 다시 출력하지 마세요.
4. 막막하다는 표현: 가장 간단한 동작 버전부터 단계적으로 제공.

[중요 - 코드 출력 규칙]
- 전체 코드를 다시 출력하는 것은 학생이 "전체 코드 다시 보여줘"라고 명확히 요청할 때만 하세요.
- 그 외에는 바뀌거나 추가되는 부분만 보여주세요. 매번 전체 구조를 반복하면 학생이 혼란스러워합니다.
- 코드 조각을 줄 때는 어느 위치에 들어가는지 한국어로 분명히 알려주세요.

[코드 작성 규칙]
- 한국어 주석 필수
- 변수명은 의미 있게 작성 (player_x, enemy_speed 등)
- 한 파일에 전체 코드 작성 (파일 분리 금지)
- 사용자 정의 class 사용 금지 (학생 수준 초과)
- pygame.Rect, pygame.Surface 등 라이브러리 내장 객체는 사용 가능
- pygame 기본 구조 유지: 초기화 → 게임루프 → 이벤트 처리 → 업데이트 → 화면 그리기
- 플레이어가 화면 밖으로 나가지 않도록 경계 처리 필수

[게임 아이디어 추천]
- 쉬움 (1주): 공 피하기, 클릭 게임, 뱀 게임
- 보통 (2주): 슈팅 게임, 점프 플랫포머
- 비추천 (1~2주 불가): RPG, 퍼즐, 멀티플레이어

[금지 사항]
- 사용자 정의 class 작성 금지
- 복잡한 자료구조 설명 금지
- "이건 어렵기 때문에 못 만들어요" 식의 포기 유도 금지
- 영어로 답변 금지

[CRITICAL - 언어 강제]
You must always respond in Korean (한국어).
Code blocks should contain English code. All explanations must be in Korean.
No English explanations allowed outside of code blocks."""

# ─────────────────────────────────────────────
# 앱 초기화
# ─────────────────────────────────────────────
app = FastAPI(title="게임 개발 AI 튜터")

# 세션별 대화 기록 (메모리 저장)
# 주의: 서버 재시작 시 사라짐. 영구 저장이 필요하면 SQLite/Redis로 교체.
sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@app.get("/")
async def index():
    """채팅 웹페이지 제공"""
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    """Ollama 연결 상태 + 모델 로딩 여부 확인"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            model_ready = any(MODEL_NAME in m for m in models)
            return {
                "ollama": "연결됨",
                "model": MODEL_NAME,
                "model_ready": model_ready,
                "available_models": models,
            }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ollama": "연결 실패", "error": str(e),
                     "hint": "Ollama가 실행 중인지 확인하세요 (ollama serve)"},
        )


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """학생 메시지를 받아 Ollama로 스트리밍 응답"""
    # 세션 ID 없으면 새로 발급
    session_id = req.session_id or str(uuid.uuid4())
    history = sessions.get(session_id, [])

    # 메시지 구성: 시스템 + 기존 기록 + 새 질문
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": req.message}]
    )

    async def generate():
        # 첫 줄에 세션 ID 전달 (프론트가 저장)
        yield json.dumps({"session_id": session_id}) + "\n"

        full_reply = ""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": MODEL_NAME,
                        "messages": messages,
                        "stream": True,
                        "options": MODEL_OPTIONS,
                    },
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield json.dumps({"error": f"모델 오류: {body.decode()}"}) + "\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_reply += chunk
                            yield json.dumps({"chunk": chunk}) + "\n"
                        if data.get("done"):
                            break
        except httpx.ConnectError:
            yield json.dumps({"error": "Ollama에 연결할 수 없습니다. 서버 상태를 확인하세요."}) + "\n"
            return
        except Exception as e:
            yield json.dumps({"error": f"오류 발생: {str(e)}"}) + "\n"
            return

        # 대화 기록 저장 (최근 N턴만 유지)
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": full_reply})
        sessions[session_id] = history[-(MAX_HISTORY_TURNS * 2):]

        yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/api/reset")
async def reset(req: ChatRequest):
    """대화 기록 초기화 (새 대화 시작)"""
    if req.session_id and req.session_id in sessions:
        del sessions[req.session_id]
    return {"status": "초기화 완료"}


# 정적 파일 (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    print(f"""
╔════════════════════════════════════════════╗
║   게임 개발 AI 튜터 서버 시작                ║
╠════════════════════════════════════════════╣
║   모델:   {MODEL_NAME:<32}║
║   주소:   http://{HOST}:{PORT}{' ' * (24 - len(str(PORT)))}║
║   Ollama: {OLLAMA_URL:<32}║
╚════════════════════════════════════════════╝
""")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
