// ─────────────────────────────────────────────
// 게임 개발 AI 튜터 — 프론트엔드 로직
// ─────────────────────────────────────────────

const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const homeBtn = document.getElementById("homeBtn");
const statusEl = document.getElementById("status");
const modelSelect = document.getElementById("modelSelect");

// 세션 ID (localStorage 미사용 — 브라우저 메모리에만 유지)
let sessionId = null;
let isStreaming = false;
let selectedModel = null;   // 사용자가 고른 모델 (null이면 서버 기본값)

// ─────────────────────────────────────────────
// 설치된 모델 목록 불러오기 → 드롭다운 채우기
// ─────────────────────────────────────────────
async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const models = data.models || [];
    selectedModel = data.default || models[0] || null;
    modelSelect.innerHTML = models
      .map(m => `<option value="${m}"${m === selectedModel ? " selected" : ""}>${m}</option>`)
      .join("");
  } catch {
    modelSelect.innerHTML = `<option>모델 목록 불러오기 실패</option>`;
  }
}
loadModels();

// 사용자가 모델을 바꾸면 기억해두고, 다음 질문부터 적용
modelSelect.addEventListener("change", () => {
  selectedModel = modelSelect.value;
});

// ─────────────────────────────────────────────
// 서버 상태 확인
// ─────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.ollama === "연결됨" && data.model_ready) {
      statusEl.textContent = "● 준비 완료";
      statusEl.className = "status status-ok";
    } else if (data.ollama === "연결됨") {
      statusEl.textContent = "● 모델 로딩 필요";
      statusEl.className = "status status-checking";
    } else {
      statusEl.textContent = "● Ollama 미연결";
      statusEl.className = "status status-error";
    }
  } catch {
    statusEl.textContent = "● 서버 오류";
    statusEl.className = "status status-error";
  }
}
checkHealth();
setInterval(checkHealth, 15000);

// ─────────────────────────────────────────────
// 간단한 마크다운 → HTML 변환 (코드블록 + 기본 서식)
// ─────────────────────────────────────────────
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(text) {
  const codeBlocks = [];
  // 코드블록 추출 (```...```)
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push({ lang, code: code.replace(/\n$/, "") });
    return `\u0000CODE${idx}\u0000`;
  });

  // HTML 이스케이프
  text = escapeHtml(text);

  // 인라인 코드
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  // 굵게
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // 줄바꿈 → 단락
  text = text.split(/\n\n+/).map(p => {
    if (p.includes("\u0000CODE")) return p;
    // 리스트 처리
    if (/^\s*[-*]\s/m.test(p)) {
      const items = p.split("\n").filter(l => l.trim())
        .map(l => `<li>${l.replace(/^\s*[-*]\s/, "")}</li>`).join("");
      return `<ul>${items}</ul>`;
    }
    return `<p>${p.replace(/\n/g, "<br>")}</p>`;
  }).join("");

  // 코드블록 복원
  text = text.replace(/\u0000CODE(\d+)\u0000/g, (_, i) => {
    const { code } = codeBlocks[i];
    const escaped = escapeHtml(code);
    return `<pre><button class="copy-btn" onclick="copyCode(this)">복사</button><code>${escaped}</code></pre>`;
  });

  return text;
}

// 코드 복사
window.copyCode = function (btn) {
  const code = btn.nextElementSibling.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = "복사됨!";
    setTimeout(() => (btn.textContent = "복사"), 1500);
  });
};

// ─────────────────────────────────────────────
// 메시지 추가
// ─────────────────────────────────────────────
function addMessage(role, content = "") {
  // 환영 화면 제거
  const welcome = messagesEl.querySelector(".welcome");
  if (welcome) welcome.remove();

  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.innerHTML = `
    <div class="msg-avatar">${role === "user" ? "🧑‍💻" : "🎮"}</div>
    <div class="msg-content"></div>
  `;
  const contentEl = msg.querySelector(".msg-content");
  if (role === "user") {
    contentEl.textContent = content;
  }
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return contentEl;
}

// ─────────────────────────────────────────────
// 메시지 전송 + 스트리밍 수신
// ─────────────────────────────────────────────
async function sendMessage(text) {
  if (!text.trim() || isStreaming) return;
  isStreaming = true;
  sendBtn.disabled = true;

  addMessage("user", text);
  inputEl.value = "";
  inputEl.style.height = "auto";

  const aiContent = addMessage("ai");
  aiContent.classList.add("cursor-blink");
  let fullText = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text, model: selectedModel }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();   // 마지막 미완성 줄 보관

      for (const line of lines) {
        if (!line.trim()) continue;
        const data = JSON.parse(line);
        if (data.session_id) sessionId = data.session_id;
        if (data.chunk) {
          fullText += data.chunk;
          aiContent.innerHTML = renderMarkdown(fullText);
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
        if (data.error) {
          aiContent.innerHTML = `<div class="error-msg">⚠️ ${data.error}</div>`;
        }
      }
    }
  } catch (e) {
    aiContent.innerHTML = `<div class="error-msg">⚠️ 연결 오류: ${e.message}</div>`;
  } finally {
    aiContent.classList.remove("cursor-blink");
    aiContent.innerHTML = renderMarkdown(fullText) || aiContent.innerHTML;
    isStreaming = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

// ─────────────────────────────────────────────
// 이벤트 연결
// ─────────────────────────────────────────────
sendBtn.addEventListener("click", () => sendMessage(inputEl.value));

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(inputEl.value);
  }
});

// 입력창 자동 높이 조절
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
});

// ─────────────────────────────────────────────
// 메뉴별 예시 질문 (자동 전송하지 않고 보여주기만 함)
// ─────────────────────────────────────────────
const MENU_EXAMPLES = {
  idea: {
    title: "💡 게임 아이디어 추천",
    desc: "어떤 게임을 만들지 고민될 때 참고하세요. 아래 예시처럼 물어봐도 되고, 직접 질문해도 돼요.",
    examples: [
      "1~2주 안에 만들 수 있는 쉬운 pygame 게임 5개 추천해줘.",
      "혼자 만들 수 있는 간단한 2D 게임 아이디어 알려줘.",
      "피하기 게임이랑 슈팅 게임 중에 뭐가 더 쉬워?",
      "친구들이랑 같이 즐길 수 있는 점수 경쟁 게임 아이디어 줘.",
    ],
  },
  structure: {
    title: "🧱 게임 기본 구조 설계하기",
    desc: "게임의 뼈대를 어떻게 잡을지 도와드려요. 아래 예시를 참고해서 만들고 싶은 게임을 설명해 보세요.",
    examples: [
      "공 피하기 게임을 만들고 싶어. 기본 구조를 어떻게 짜야 해?",
      "pygame 게임의 기본 틀(창, 게임루프)이 어떻게 생겼는지 알려줘.",
      "캐릭터가 움직이고 점수가 올라가는 게임은 어떤 순서로 만들어야 해?",
      "내가 만들 게임에 어떤 변수랑 함수가 필요할지 같이 정리해줘.",
    ],
  },
};

// 환영 화면으로 돌아가기
function showWelcome() {
  messagesEl.innerHTML = `
    <div class="welcome">
      <div class="welcome-icon">🚀</div>
      <h2>안녕하세요! 게임 개발을 도와드릴게요</h2>
      <p>아래 메뉴를 누르면 예시 질문을 보여드려요. 예시를 참고해서 직접 질문해 보세요.</p>
      <div class="quick-buttons">
        <button class="quick-btn" data-menu="idea">💡 게임 아이디어 추천</button>
        <button class="quick-btn" data-menu="structure">🧱 게임 기본 구조 설계하기</button>
      </div>
    </div>`;
  bindQuickButtons();
}

// 메뉴 클릭 시 예시 질문 화면 표시
function showExamples(menuKey) {
  const menu = MENU_EXAMPLES[menuKey];
  if (!menu) return;
  const exampleHtml = menu.examples.map(q =>
    `<button class="example-btn" data-q="${q.replace(/"/g, "&quot;")}">${q}</button>`
  ).join("");
  messagesEl.innerHTML = `
    <div class="welcome">
      <h2>${menu.title}</h2>
      <p>${menu.desc}</p>
      <div class="example-list">${exampleHtml}</div>
      <p class="example-hint">👇 예시를 누르면 입력창에 채워져요. 수정해서 보내도 돼요.</p>
    </div>`;
  // 예시 클릭 → 입력창에 채우기 (자동 전송 X)
  messagesEl.querySelectorAll(".example-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      inputEl.value = btn.dataset.q;
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
      inputEl.focus();
    });
  });
}

// 빠른 버튼(메뉴) 연결
function bindQuickButtons() {
  document.querySelectorAll(".quick-btn").forEach(btn => {
    btn.addEventListener("click", () => showExamples(btn.dataset.menu));
  });
}
bindQuickButtons();

// 홈 버튼
homeBtn.addEventListener("click", showWelcome);

// 새 대화 (기록 초기화 + 홈으로)
resetBtn.addEventListener("click", async () => {
  if (sessionId) {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: "" }),
    });
  }
  sessionId = null;
  showWelcome();
});
