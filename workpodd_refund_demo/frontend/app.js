window.API_BASE = window.location.origin + "/api/v1/workpodd-demo";

let sessionId = "";
let eventSource = null;
let mediaRecorder = null;
let recordingChunks = [];
let realtimeActive = false;
let voiceCapabilities = null;
let speechRecognition = null;
let browserTranscript = "";

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const customerEmail = document.getElementById("customerEmail");
const sendBtn = document.getElementById("sendBtn");
const reasoningLog = document.getElementById("reasoningLog");
const sessionLabel = document.getElementById("sessionLabel");
const demoCustomer = document.getElementById("demoCustomer");
const connectionStatus = document.getElementById("connectionStatus");
const pttBtn = document.getElementById("pttBtn");
const realtimeBtn = document.getElementById("realtimeBtn");
const voiceStatus = document.getElementById("voiceStatus");
const speakReply = document.getElementById("speakReply");
const agentAudio = document.getElementById("agentAudio");

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "agent"}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderLogEntry(entry) {
  const el = document.createElement("div");
  el.className = `log-entry ${entry.kind || "thought"}`;
  el.innerHTML = `<div class="log-meta">#${entry.step} · ${entry.kind} · ${entry.timestamp || ""}</div><div class="log-body">${escapeHtml(entry.content || "")}</div>`;
  reasoningLog.appendChild(el);
  reasoningLog.scrollTop = reasoningLog.scrollHeight;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function setVoiceStatus(msg) {
  voiceStatus.textContent = msg || "";
}

function playBase64Audio(b64, mime) {
  agentAudio.src = `data:${mime || "audio/mpeg"};base64,${b64}`;
  agentAudio.play().catch(() => {});
}

function startReasoningStream(sid) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  reasoningLog.innerHTML = "";
  sessionLabel.textContent = sid.slice(0, 8) + "…";
  sessionId = sid;

  eventSource = new EventSource(`${window.API_BASE}/logs/${sid}/stream`);
  eventSource.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "done") {
        eventSource.close();
        return;
      }
      renderLogEntry(data);
    } catch (_) {}
  };
  eventSource.onerror = () => pollLogs(sid);
}

async function pollLogs(sid) {
  const res = await fetch(`${window.API_BASE}/logs/${sid}`);
  const data = await res.json();
  reasoningLog.innerHTML = "";
  (data.logs || []).forEach(renderLogEntry);
}

async function loadCustomers() {
  try {
    const res = await fetch(`${window.API_BASE}/customers`);
    const data = await res.json();
    (data.customers || []).forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.email;
      opt.textContent = `${c.name} (${c.tier}) · ${c.sample_order || "no order"}`;
      opt.dataset.order = c.sample_order || "";
      demoCustomer.appendChild(opt);
    });
    connectionStatus.textContent = "Connected";
  } catch (e) {
    connectionStatus.textContent = "API offline";
  }
}

demoCustomer.addEventListener("change", () => {
  const opt = demoCustomer.selectedOptions[0];
  if (!opt || !opt.value) return;
  customerEmail.value = opt.value;
  if (opt.dataset.order) {
    chatInput.value = `Hi, my email is ${opt.value}. I'd like a refund for order ${opt.dataset.order}.`;
  }
});

document.querySelectorAll(".hint-chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    chatInput.value = btn.dataset.msg || "";
    chatInput.focus();
  });
});

async function sendChatMessage(message) {
  appendMessage("user", message);
  chatInput.value = "";
  sendBtn.disabled = true;
  connectionStatus.textContent = "Agent thinking…";

  try {
    const res = await fetch(`${window.API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: sessionId || undefined,
        customer_email: customerEmail.value.trim(),
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.message || "Chat failed");

    if (!sessionId) startReasoningStream(data.session_id);
    else pollLogs(sessionId);

    if (data.parsed?.email && !customerEmail.value) {
      customerEmail.value = data.parsed.email;
    }

    appendMessage("agent", data.reply);
    connectionStatus.textContent = "Ready";

    if (speakReply.checked && data.reply) {
      const tts = await fetch(`${window.API_BASE}/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: data.reply }),
      });
      if (tts.ok) {
        const blob = await tts.blob();
        agentAudio.src = URL.createObjectURL(blob);
        agentAudio.play().catch(() => {});
      }
    }
  } catch (err) {
    appendMessage("agent", "Sorry, something went wrong.");
    connectionStatus.textContent = "Error";
    console.error(err);
  } finally {
    sendBtn.disabled = false;
  }
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  await sendChatMessage(message);
});

// --- Push-to-talk: server Whisper (or browser STT fallback) + agent + TTS ---
function startBrowserRecognition() {
  browserTranscript = "";
  if (!SpeechRecognition) return;
  speechRecognition = new SpeechRecognition();
  speechRecognition.continuous = true;
  speechRecognition.interimResults = true;
  speechRecognition.lang = "en-US";
  speechRecognition.onresult = (e) => {
    let text = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      text += e.results[i][0].transcript;
    }
    if (text.trim()) browserTranscript = text.trim();
  };
  speechRecognition.onerror = () => {};
  try {
    speechRecognition.start();
  } catch (_) {}
}

function stopBrowserRecognition() {
  if (speechRecognition) {
    try {
      speechRecognition.stop();
    } catch (_) {}
    speechRecognition = null;
  }
}

async function sendVoiceChat({ blob, transcript }) {
  const speak = speakReply.checked ? "true" : "false";
  const email = customerEmail.value.trim();

  if (transcript) {
    const res = await fetch(`${window.API_BASE}/voice/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript,
        customer_email: email,
        session_id: sessionId,
        speak,
      }),
    });
    return res.json();
  }

  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  form.append("customer_email", email);
  form.append("session_id", sessionId);
  form.append("speak", speak);
  const res = await fetch(`${window.API_BASE}/voice/chat`, { method: "POST", body: form });
  const data = await res.json();
  if (!data.success && res.status === 503 && data.fallback === "browser_stt" && browserTranscript) {
    setVoiceStatus("Server STT unavailable — using browser speech…");
    return sendVoiceChat({ transcript: browserTranscript });
  }
  if (!data.success) throw new Error(data.message || "Voice request failed");
  return data;
}

function handleVoiceResponse(data) {
  if (data.transcript) {
    appendMessage("user", data.transcript);
    if (data.parsed?.email) customerEmail.value = data.parsed.email;
  }

  if (!sessionId && data.session_id) startReasoningStream(data.session_id);
  else if (sessionId) pollLogs(sessionId);

  appendMessage("agent", data.reply);
  const src = data.stt_source === "client" ? "browser" : "Whisper";
  setVoiceStatus(
    `Heard (${src}): "${data.transcript}"${data.parsed?.order_id ? ` · Order ${data.parsed.order_id}` : ""}`
  );

  if (data.audio_base64) playBase64Audio(data.audio_base64, data.audio_mime);
  else if (data.tts_error) setVoiceStatus(`${voiceStatus.textContent} · ${data.tts_error}`);
}

async function startRecording() {
  recordingChunks = [];
  browserTranscript = "";
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  startBrowserRecognition();
  mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) recordingChunks.push(e.data);
  };
  mediaRecorder.start();
  pttBtn.classList.add("recording");
  const mode =
    voiceCapabilities?.whisper?.configured && voiceCapabilities?.whisper?.deployment
      ? "Whisper"
      : "browser speech";
  setVoiceStatus(`Recording… release to send (${mode})`);
}

async function stopRecordingAndSend() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;

  return new Promise((resolve) => {
    mediaRecorder.onstop = async () => {
      pttBtn.classList.remove("recording");
      stopBrowserRecognition();
      mediaRecorder.stream.getTracks().forEach((t) => t.stop());
      setVoiceStatus("Transcribing…");

      const blob = new Blob(recordingChunks, { type: "audio/webm" });

      try {
        const data = await sendVoiceChat({ blob });
        handleVoiceResponse(data);
      } catch (err) {
        if (browserTranscript) {
          try {
            setVoiceStatus("Retrying with browser speech…");
            const data = await sendVoiceChat({ transcript: browserTranscript });
            handleVoiceResponse(data);
            resolve();
            return;
          } catch (retryErr) {
            setVoiceStatus(`Voice failed: ${retryErr.message}`);
            appendMessage("agent", `Voice error: ${retryErr.message}`);
            resolve();
            return;
          }
        }
        setVoiceStatus(`Voice failed: ${err.message}`);
        appendMessage("agent", `Voice error: ${err.message}`);
      }
      resolve();
    };
    mediaRecorder.stop();
  });
}

pttBtn.addEventListener("mousedown", (e) => {
  e.preventDefault();
  startRecording().catch((err) => setVoiceStatus(`Mic error: ${err.message}`));
});
pttBtn.addEventListener("mouseup", () => stopRecordingAndSend());
pttBtn.addEventListener("mouseleave", () => {
  if (mediaRecorder?.state === "recording") stopRecordingAndSend();
});
pttBtn.addEventListener("touchstart", (e) => {
  e.preventDefault();
  startRecording().catch((err) => setVoiceStatus(`Mic error: ${err.message}`));
});
pttBtn.addEventListener("touchend", (e) => {
  e.preventDefault();
  stopRecordingAndSend();
});

// --- OpenAI Realtime live voice ---
realtimeBtn.addEventListener("click", async () => {
  if (realtimeActive) {
    RealtimeVoice.stop();
    realtimeActive = false;
    realtimeBtn.textContent = "📞 Live voice (Realtime)";
    return;
  }

  try {
    const sid = await RealtimeVoice.start(
      customerEmail.value.trim(),
      setVoiceStatus,
      (role, text) => appendMessage(role, text)
    );
    if (sid) startReasoningStream(sid);
    realtimeActive = true;
    realtimeBtn.textContent = "⏹ Stop live voice";
  } catch (err) {
    setVoiceStatus(`Realtime: ${err.message}`);
  }
});

async function loadVoiceCapabilities() {
  try {
    const res = await fetch(`${window.API_BASE}/voice/capabilities`);
    const data = await res.json();
    if (!data.success) return;
    voiceCapabilities = data;

    if (!data.realtime?.configured) {
      realtimeBtn.disabled = true;
      realtimeBtn.title = data.realtime?.hint || "Live voice not configured on server";
      realtimeBtn.textContent = "📞 Live voice (not configured)";
    }

    if (!data.whisper?.configured && !SpeechRecognition) {
      pttBtn.title = "No Whisper deployment and browser speech unsupported — use text chat";
    } else if (!data.whisper?.configured) {
      pttBtn.title = "Uses browser speech (no Whisper deployment on Azure)";
    }
  } catch (_) {}
}

appendMessage(
  "agent",
  "Hello! I'm ShopFlow AI Support. Set your email above, then hold 🎤 to speak or type below. Live voice needs a Realtime deployment."
);
loadCustomers();
loadVoiceCapabilities();
