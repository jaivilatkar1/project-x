(() => {
  const app = document.getElementById("app");
  const messagesEl = document.getElementById("messages");
  const welcomeEl = document.getElementById("welcome");
  const composer = document.getElementById("composer");
  const input = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const newChatBtn = document.getElementById("newChatBtn");
  const modeSelect = document.getElementById("modeSelect");
  const scenarioList = document.getElementById("scenarioList");
  const connPulse = document.getElementById("connPulse");
  const connLabel = document.getElementById("connLabel");

  const scenarios = JSON.parse(
    document.getElementById("scenarios-data").textContent
  );

  let sessionId = null;
  let busy = false;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setBusy(on, label) {
    busy = on;
    sendBtn.disabled = on;
    modeSelect.disabled = on;
    newChatBtn.disabled = on;
    scenarioList.querySelectorAll("button").forEach((b) => {
      b.disabled = on;
    });
    connPulse.dataset.state = on ? "busy" : "idle";
    connLabel.textContent = label || (on ? "Thinking…" : "Ready");
  }

  function setErrorState(msg) {
    connPulse.dataset.state = "error";
    connLabel.textContent = msg || "Error";
  }

  function updateStatus(state) {
    if (!state) return;
    const verified = document.getElementById("stVerified");
    const customer = document.getElementById("stCustomer");
    const escalated = document.getElementById("stEscalated");
    const ticket = document.getElementById("stTicket");
    const banner = document.getElementById("handoffBanner");

    verified.textContent = state.verified ? "yes" : "no";
    verified.className = state.verified ? "on" : "";
    customer.textContent = state.customer_id || "—";
    escalated.textContent = state.escalated ? "yes" : "no";
    escalated.className = state.escalated ? "warn" : "";
    ticket.textContent = state.ticket_id || "—";
    if (state.locked && !state.escalated) {
      escalated.textContent = "locked";
      escalated.className = "bad";
    }
    if (banner) {
      banner.hidden = !(state.locked || state.escalated);
    }
  }

  function hideWelcome() {
    if (welcomeEl) welcomeEl.remove();
  }

  function appendBubble(role, text) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function appendTools(tools) {
    if (!tools || !tools.length) return;
    const row = document.createElement("div");
    row.className = "tools";
    tools.forEach((t) => {
      const chip = document.createElement("span");
      chip.className = "tool-chip";
      const ok = t.result && t.result.ok;
      chip.textContent = `${t.name}${ok === false ? " ✗" : ok ? " ✓" : ""}`;
      chip.title = JSON.stringify(t.result || {}, null, 0).slice(0, 280);
      row.appendChild(chip);
    });
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function api(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.detail || data.error || res.statusText);
      err.payload = data;
      throw err;
    }
    return data;
  }

  async function ensureSession(forceNew) {
    if (sessionId && !forceNew) return;
    const data = await api("/api/session", { mode: modeSelect.value });
    sessionId = data.state.session_id;
    updateStatus(data.state);
  }

  async function resetChat() {
    setBusy(true, "Resetting…");
    try {
      const data = await api("/api/session/reset", {
        session_id: sessionId,
        mode: modeSelect.value,
      });
      sessionId = data.state.session_id;
      messagesEl.innerHTML = "";
      const welcome = document.createElement("div");
      welcome.className = "welcome";
      welcome.id = "welcome";
      welcome.innerHTML =
        '<p class="welcome-kicker">Paylane</p>' +
        '<p class="welcome-lead">Hi — I can help with cards, transfers, and refunds.</p>' +
        '<p class="welcome-sub">I’ll verify email + last 4 before account details. Pick a scenario, or type below.</p>';
      messagesEl.appendChild(welcome);
      updateStatus(data.state);
      setBusy(false);
    } catch (e) {
      setErrorState("Reset failed");
      appendBubble("error", e.message);
      setBusy(false);
    }
  }

  async function sendMessage(text, { silentInput } = {}) {
    const message = (text || "").trim();
    if (!message || busy) return;

    await ensureSession(false);
    appendBubble("user", message);
    if (!silentInput) {
      input.value = "";
      autosize();
    }

    setBusy(true, "Agent working…");
    try {
      const data = await api("/api/chat", {
        session_id: sessionId,
        message,
        mode: modeSelect.value,
      });
      sessionId = data.state.session_id;
      appendBubble("assistant", data.reply || "(empty reply)");
      appendTools(data.tools);
      updateStatus(data.state);
      setBusy(false);
    } catch (e) {
      setErrorState("Request failed");
      appendBubble("error", e.message || "Something went wrong");
      if (e.payload && e.payload.state) updateStatus(e.payload.state);
      setBusy(false);
    }
  }

  async function playScenario(messages) {
    if (busy || !messages || !messages.length) return;
    await resetChat();
    for (const msg of messages) {
      await sendMessage(msg, { silentInput: true });
      if (connPulse.dataset.state === "error") break;
      await new Promise((r) => setTimeout(r, 350));
    }
    input.focus();
  }

  function renderScenarios() {
    scenarioList.innerHTML = "";
    scenarios.forEach((s) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "scenario";
      btn.innerHTML =
        `<span class="scenario-title">${escapeHtml(s.title)}</span>` +
        `<span class="scenario-blurb">${escapeHtml(s.blurb)}</span>`;
      btn.addEventListener("click", () => playScenario(s.messages));
      li.appendChild(btn);
      scenarioList.appendChild(li);
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  input.addEventListener("input", autosize);

  newChatBtn.addEventListener("click", () => resetChat());

  modeSelect.addEventListener("change", async () => {
    await resetChat();
  });

  document.getElementById("seedRow").addEventListener("click", (e) => {
    const btn = e.target.closest(".seed");
    if (!btn) return;
    input.value = btn.dataset.fill || "";
    autosize();
    input.focus();
  });

  if (app.dataset.azureReady !== "true") {
    modeSelect.value = "deterministic";
  }

  renderScenarios();
  ensureSession(true).catch((e) => {
    setErrorState("Session failed");
    appendBubble("error", e.message);
  });

  input.focus();
})();
