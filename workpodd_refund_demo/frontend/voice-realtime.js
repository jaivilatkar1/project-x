/** OpenAI Realtime WebRTC voice — bonus pipeline for Workpodd demo */

const RealtimeVoice = (() => {
  let pc = null;
  let dc = null;
  let micStream = null;
  let reasoningSessionId = "";
  let onStatus = () => {};
  let onTranscript = () => {};

  async function executeTool(name, args) {
    const res = await fetch(`${window.API_BASE}/voice/execute-tool`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: reasoningSessionId,
        tool: name,
        arguments: args,
      }),
    });
    const data = await res.json();
    return data.result || { error: "tool failed" };
  }

  function handleEvent(ev) {
    const t = ev.type;
    if (t === "response.audio_transcript.done" && ev.transcript) {
      onTranscript("agent", ev.transcript);
    }
    if (t === "conversation.item.input_audio_transcription.completed" && ev.transcript) {
      onTranscript("user", ev.transcript);
    }
    if (t === "response.function_call_arguments.done") {
      const name = ev.name;
      let args = {};
      try {
        args = JSON.parse(ev.arguments || "{}");
      } catch (_) {}
      executeTool(name, args).then((result) => {
        if (!dc || dc.readyState !== "open") return;
        dc.send(
          JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "function_call_output",
              call_id: ev.call_id,
              output: JSON.stringify(result),
            },
          })
        );
        dc.send(JSON.stringify({ type: "response.create" }));
      });
    }
    if (t === "error") {
      onStatus(`Realtime error: ${ev.error?.message || "unknown"}`);
    }
  }

  async function start(customerEmail, statusCb, transcriptCb) {
    onStatus = statusCb || onStatus;
    onTranscript = transcriptCb || onTranscript;
    onStatus("Starting OpenAI Realtime session…");

    const res = await fetch(`${window.API_BASE}/voice/realtime-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_email: customerEmail }),
    });
    const data = await res.json();
    if (!data.success) {
      throw new Error(data.message || "Realtime unavailable");
    }

    reasoningSessionId = data.reasoning_session_id;
    const token = data.client_secret;
    const webrtcUrl = data.webrtc_url;

    pc = new RTCPeerConnection();
    const audioEl = document.getElementById("agentAudio");
    pc.ontrack = (e) => {
      audioEl.srcObject = e.streams[0];
    };

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micStream.getTracks().forEach((t) => pc.addTrack(t, micStream));

    dc = pc.createDataChannel("oai-events");
    dc.onopen = () => onStatus("Live voice connected — speak now");
    dc.onmessage = (m) => {
      try {
        handleEvent(JSON.parse(m.data));
      } catch (_) {}
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/sdp",
    };
    const sdpResp = await fetch(webrtcUrl, {
      method: "POST",
      headers,
      body: offer.sdp,
    });
    if (!sdpResp.ok) {
      throw new Error(`WebRTC failed: ${await sdpResp.text()}`);
    }
    const answer = { type: "answer", sdp: await sdpResp.text() };
    await pc.setRemoteDescription(answer);
    return reasoningSessionId;
  }

  function stop() {
    if (dc) {
      dc.close();
      dc = null;
    }
    if (pc) {
      pc.close();
      pc = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    }
    onStatus("Live voice stopped");
  }

  return { start, stop, getSessionId: () => reasoningSessionId };
})();

window.RealtimeVoice = RealtimeVoice;
