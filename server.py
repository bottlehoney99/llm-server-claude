"""
바이브코딩 게임 개발 AI 에이전트 — 로컬 LLM 서버
=================================================
개인 PC에서 Ollama(qwen3:8b)를 띄우고, 학생들이 웹 브라우저로 접속해
pygame 게임 개발 도움을 받을 수 있는 서버입니다.

실행: python server.py
필요: Ollama 실행 중 + qwen3:8b 모델 다운로드 완료
"""

import os
import json
import uuid
import asyncio
import datetime
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─────────────────────────────────────────────
# 설정 (환경변수로 덮어쓸 수 있음)
# ─────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen3:8b")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

# 학생이 드롭다운에서 고를 수 있는 모델 화이트리스트.
# 20명 동시 환경에서는 여러 모델을 동시에 VRAM에 올리면 OOM이 나므로 1개로 고정한다.
# 다른 모델을 허용하려면 콤마로 구분: ALLOWED_MODELS="qwen3:8b,llama3.1:8b"
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", MODEL_NAME).split(",") if m.strip()]

# GPU 모니터링 설정
GPU_LOG_INTERVAL = int(os.environ.get("GPU_LOG_INTERVAL", "10"))   # 로그 기록 간격(초)
GPU_LOG_FILE = os.environ.get("GPU_LOG_FILE", "logs/gpu_log.csv")  # CSV 로그 경로

# 대화 기록 유지 턴 수 (메모리 절약 + 컨텍스트 충돌 방지)
MAX_HISTORY_TURNS = 6   # user+assistant 합쳐 최근 6쌍(12개)까지 유지

# 모델 생성 옵션 (명세서 v2 기준)
MODEL_OPTIONS = {
    "temperature": 0.5,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_predict": 1536,   # 출력 최대 토큰 (전체 코드 생성용)
    "num_ctx": 4096,       # 컨텍스트 윈도우 (20명 동시용으로 축소 — VRAM 절약 + 병렬 슬롯 확보)
}

# ─────────────────────────────────────────────
# 시스템 프롬프트 (게임 개발 에이전트 — 코드에 내장)
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """[★최우선 규칙 — 다른 모든 규칙보다 먼저 지킬 것]
처음 게임을 만드는 첫 요청이 아니라면, 전체 코드를 절대 다시 출력하지 마세요.
수정·추가·오류고치기 요청에는 "새로 들어가거나 바뀌는 줄"만 짧게 보여주세요(보통 3~15줄).
이미 만든 import / pygame.init / while 게임루프 전체를 다시 적는 것은 금지입니다.

[★수정·추가 요청 응답 템플릿 — 반드시 이 순서/형식대로]
1) 한 문장 안내: "○○ 부분에 아래 코드를 추가/수정하세요."
2) 짧은 코드 조각만 (바뀌는 줄만, 전체 X):
```python
# 여기에 새로/바뀌는 줄만
```
3) 📍 추가 위치: 기존 코드의 어느 함수/어느 줄 근처인지
4) ❓ 추가 이유: 왜 필요한지
5) ⚙️ 기능: 이 코드가 무슨 동작을 하는지
→ 전체 코드는 학생이 "전체 코드 다시 보여줘"라고 명확히 말할 때만 출력.

[역할]
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
   코드 조각을 준 뒤에는 반드시 아래 3가지를 짧게 설명하세요.
   - 📍 어느 부분에 추가했는지: 기존 코드의 어느 위치(어느 줄/함수 근처)에 넣는지
   - ❓ 왜 추가했는지: 이 코드가 필요한 이유, 어떤 요청을 해결하는지
   - ⚙️ 추가된 코드의 기능: 이 코드가 실제로 무슨 동작을 하는지 (한 줄씩 핵심 위주)
4. 막막하다는 표현: 가장 간단한 동작 버전부터 단계적으로 제공.

[중요 - 코드 출력 규칙 (가장 자주 어기는 규칙, 반드시 지킬 것)]
- 첫 코드 요청(처음 게임을 만들 때)이 아니라면, 전체 코드를 절대 다시 출력하지 마세요.
- 수정/추가 요청에는 "바뀌거나 새로 들어가는 줄"만 짧은 코드 조각으로 보여주세요.
  보통 3~15줄이면 충분합니다. 50줄이 넘는 코드 블록이 나온다면 규칙을 어기고 있는 것입니다.
- 전체 코드를 처음부터 끝까지 다시 출력하는 것은 학생이 "전체 코드 다시 보여줘",
  "처음부터 전체 코드 줘"라고 명확히 요청할 때만 하세요. 그 외에는 절대 금지.
- 매번 전체 구조(import, pygame.init, while 게임루프 전체...)를 반복하면 학생이 혼란스러워합니다.
- 코드 조각을 줄 때는 어느 위치(어느 함수/어느 줄 근처)에 들어가는지 한국어로 분명히 알려주세요.

[코드 출력 좋은 예 / 나쁜 예]
※ 나쁜 예 (이렇게 하지 마세요):
  "점프 기능을 추가했어요!" 라고 한 뒤 import부터 game loop 끝까지 전체 코드를 통째로 다시 출력.
※ 좋은 예 (이렇게 하세요):
  "이벤트 처리 부분(while running: 안의 for event 루프) 근처에 아래 줄을 추가하세요."
  ```python
  if keys[pygame.K_SPACE] and not is_jumping:  # 스페이스바 누르면 점프 시작
      is_jumping = True
      jump_speed = -15  # 위로 솟는 속도
  ```
  그 다음 📍추가 위치 / ❓추가 이유 / ⚙️기능을 짧게 설명.

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
No English explanations allowed outside of code blocks.

[마지막 확인 — 답하기 직전 스스로 점검]
이번이 첫 코드 요청이 아니라면: 전체 코드를 다시 쓰지 않았는가? 추가/변경되는 줄만 보여주고
📍위치 / ❓이유 / ⚙️기능을 설명했는가? 그렇지 않다면 전체 코드를 지우고 조각만 남기세요."""

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
    model: str | None = None   # 사용자가 고른 모델 (없으면 기본 MODEL_NAME 사용)


@app.get("/")
async def index():
    """채팅 웹페이지 제공"""
    return FileResponse("static/index.html")


@app.get("/api/models")
async def models():
    """선택 가능한 모델 목록 + 기본 모델 반환 (프론트 드롭다운용).
    화이트리스트(ALLOWED_MODELS)에 든 모델만 노출해 동시 다중 모델 로딩(OOM)을 막는다."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            installed = [m["name"] for m in r.json().get("models", [])]
            # 허용 목록 ∩ 실제 설치된 모델만 노출 (설치 안 된 모델 고르는 사고 방지)
            names = [m for m in ALLOWED_MODELS if m in installed] or [MODEL_NAME]
            return {"models": names, "default": MODEL_NAME}
    except Exception as e:
        # 목록을 못 가져와도 기본 모델은 쓸 수 있게 반환
        return {"models": [MODEL_NAME], "default": MODEL_NAME, "error": str(e)}


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

    # 사용자가 고른 모델 사용 (없으면 기본 모델). 단, 화이트리스트에 든 모델만 허용.
    # 허용 외 모델 요청은 무시하고 기본 모델로 대체해 예기치 않은 모델 로딩(OOM)을 막는다.
    model_name = req.model if req.model in ALLOWED_MODELS else MODEL_NAME

    # 후속 질문이면(이미 코드를 한 번 준 적이 있으면) 생성 직전에 규칙을 다시 주입.
    # 약한 로컬 모델은 시스템 프롬프트보다 "방금 읽은 마지막 문장"을 더 잘 따르므로,
    # 사용자 메시지 끝에 짧은 리마인더를 붙여 전체 코드 반복 출력을 막는다.
    user_content = req.message
    if history:
        user_content += (
            "\n\n(규칙: 전체 코드를 다시 쓰지 말 것. 새로 추가/변경되는 줄만 짧게 보여주고, "
            "📍추가 위치 / ❓이유 / ⚙️기능을 설명할 것.)"
        )

    # 메시지 구성: 시스템 + 기존 기록 + 새 질문
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_content}]
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
                        "model": model_name,
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


# ─────────────────────────────────────────────
# GPU 모니터링 (다른 PC에서도 /monitor 로 접속해 확인)
# ─────────────────────────────────────────────
async def read_gpu_stats() -> list[dict]:
    """nvidia-smi로 GPU 상태를 읽어 리스트로 반환. GPU/드라이버 없으면 빈 리스트."""
    query = "index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,fan.speed"
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    except (FileNotFoundError, asyncio.TimeoutError):
        return []

    gpus = []
    for line in out.decode(errors="ignore").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            continue

        def num(v):
            try:
                return float(v)
            except ValueError:
                return None

        gpus.append({
            "index": parts[0],
            "name": parts[1],
            "temp": num(parts[2]),           # ℃
            "util": num(parts[3]),           # %
            "mem_used": num(parts[4]),       # MiB
            "mem_total": num(parts[5]),      # MiB
            "power": num(parts[6]),          # W
            "fan": num(parts[7]),            # %
        })
    return gpus


@app.get("/api/gpu")
async def gpu():
    """현재 GPU 상태를 JSON으로 반환 (모니터링 페이지가 주기적으로 호출)"""
    gpus = await read_gpu_stats()
    return {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gpus": gpus,
        "available": bool(gpus),
    }


@app.get("/monitor")
async def monitor():
    """GPU 모니터링 대시보드 페이지 (다른 PC에서도 접속 가능)"""
    return FileResponse("static/monitor.html")


async def gpu_logger():
    """백그라운드에서 주기적으로 GPU 상태를 CSV 파일에 기록한다."""
    os.makedirs(os.path.dirname(GPU_LOG_FILE) or ".", exist_ok=True)
    # 헤더가 없으면 한 번 작성
    if not os.path.exists(GPU_LOG_FILE) or os.path.getsize(GPU_LOG_FILE) == 0:
        with open(GPU_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("time,gpu_index,name,temp_c,util_pct,mem_used_mib,mem_total_mib,power_w,fan_pct\n")

    while True:
        gpus = await read_gpu_stats()
        if gpus:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(GPU_LOG_FILE, "a", encoding="utf-8") as f:
                for g in gpus:
                    f.write(f"{ts},{g['index']},{g['name']},{g['temp']},{g['util']},"
                            f"{g['mem_used']},{g['mem_total']},{g['power']},{g['fan']}\n")
        await asyncio.sleep(GPU_LOG_INTERVAL)


@app.on_event("startup")
async def start_gpu_logger():
    """서버 시작 시 GPU 로깅 백그라운드 태스크 실행"""
    asyncio.create_task(gpu_logger())


# 정적 파일 (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import sys
    import uvicorn

    # 콘솔 인코딩이 UTF-8이 아니면(예: Windows cp949) 박스 문자가 깨지며 죽을 수 있어
    # stdout/stderr를 UTF-8로 재설정한다. 실패해도 무시.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    banner = f"""
╔════════════════════════════════════════════╗
║   게임 개발 AI 튜터 서버 시작                ║
╠════════════════════════════════════════════╣
║   모델:   {MODEL_NAME:<32}║
║   주소:   http://{HOST}:{PORT}{' ' * (24 - len(str(PORT)))}║
║   Ollama: {OLLAMA_URL:<32}║
╚════════════════════════════════════════════╝
"""
    try:
        print(banner)
    except UnicodeEncodeError:
        # 그래도 안 되면 ASCII로 폴백
        print(f"[게임 개발 AI 튜터] model={MODEL_NAME} addr=http://{HOST}:{PORT} ollama={OLLAMA_URL}"
              .encode("ascii", "replace").decode("ascii"))

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
