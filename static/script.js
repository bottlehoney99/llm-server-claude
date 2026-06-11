// ─────────────────────────────────────────────
// 게임 개발 AI 튜터 — 프론트엔드 로직
// ─────────────────────────────────────────────

const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const statusEl = document.getElementById("status");

// 세션 ID (localStorage 미사용 — 브라우저 메모리에만 유지)
let sessionId = null;
let isStreaming = false;

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
      body: JSON.stringify({ session_id: sessionId, message: text }),
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

// 빠른 버튼
document.querySelectorAll(".quick-btn").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.prompt));
});

// 새 대화
resetBtn.addEventListener("click", async () => {
  if (sessionId) {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: "" }),
    });
  }
  sessionId = null;
  location.reload();
});
