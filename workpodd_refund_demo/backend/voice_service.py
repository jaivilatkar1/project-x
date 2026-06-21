"""OpenAI / Azure voice pipeline: Whisper STT, TTS, Realtime — with fallbacks."""

from __future__ import annotations

import base64
import io
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from .llm_client import (
    CHAT_DEPLOYMENT,
    REALTIME_API_VERSION,
    REALTIME_DEPLOYMENT,
    TTS_API_KEY,
    TTS_API_VERSION,
    TTS_BASE,
    TTS_DEPLOYMENT,
    WHISPER_DEPLOYMENT,
    azure_openai_key,
    get_azure_audio_client,
    get_azure_tts_client,
    get_chat_client,
    get_direct_openai_client,
    get_voice_capabilities,
    has_azure_tts,
    is_azure,
    openai_base,
    openai_gpt_key,
)
from .tools import TOOL_DEFINITIONS, get_policy_summary

load_dotenv()

TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
TRANSCRIBE_PROMPT = (
    "E-commerce refund support call. Order IDs like ORD-5001. "
    "Emails like alice.chen@email.com. Transcribe exactly what the customer said."
)


def _whisper_transcribe(client, model: str, audio_bytes: bytes, filename: str) -> str:
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    resp = client.audio.transcriptions.create(
        model=model,
        file=buf,
        language="en",
        prompt=TRANSCRIBE_PROMPT,
    )
    return (resp.text or "").strip()


def _gpt4o_audio_transcribe(audio_bytes: bytes, filename: str) -> str:
    """Fallback: use chat GPT-4o deployment with input_audio (works on many Azure gpt-4o deploys)."""
    import json

    client, model = get_chat_client()
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    fmt = "webm" if filename.endswith(".webm") else "wav"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Transcribe this customer refund request verbatim. Output only the transcript.",
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {"data": b64, "format": fmt},
                        },
                    ],
                }
            ],
            max_tokens=500,
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"GPT-4o audio transcription failed: {exc}") from exc


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Try in order:
    1. Azure Whisper deployment (AZURE_OPENAI_WHISPER_DEPLOYMENT)
    2. Direct OpenAI whisper-1 (LE_OPEN_AI_KEY)
    3. GPT-4o input_audio on chat deployment
    """
    errors = []

    if WHISPER_DEPLOYMENT and is_azure():
        try:
            client = get_azure_audio_client()
            if client:
                return _whisper_transcribe(client, WHISPER_DEPLOYMENT, audio_bytes, filename)
        except Exception as exc:
            errors.append(f"Azure Whisper ({WHISPER_DEPLOYMENT}): {exc}")

    direct = get_direct_openai_client()
    if direct:
        try:
            return _whisper_transcribe(direct, "whisper-1", audio_bytes, filename)
        except Exception as exc:
            errors.append(f"OpenAI Whisper: {exc}")

    try:
        return _gpt4o_audio_transcribe(audio_bytes, filename)
    except Exception as exc:
        errors.append(str(exc))

    cap = get_voice_capabilities()
    hint = (cap.get("whisper") or {}).get("hint") or ""
    raise RuntimeError(
        "Speech-to-text unavailable. "
        + "; ".join(errors[:2])
        + (f" Hint: {hint}" if hint else "")
        + " Use browser voice fallback or type your message."
    )


def _azure_tts_via_rest(text: str) -> bytes:
    """Direct REST call — required for Foundry cognitiveservices.azure.com endpoints."""
    base = (TTS_BASE or openai_base).rstrip("/")
    url = (
        f"{base}/openai/deployments/{TTS_DEPLOYMENT}/audio/speech"
        f"?api-version={TTS_API_VERSION}"
    )
    api_key = TTS_API_KEY if TTS_BASE else azure_openai_key
    resp = requests.post(
        url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "input": text[:4096],
            "voice": TTS_VOICE,
            "response_format": "mp3",
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.content


def text_to_speech(text: str) -> tuple[Optional[bytes], Optional[str]]:
    """TTS — returns (mp3 bytes, error message)."""
    errors: list[str] = []

    if has_azure_tts():
        # Regional Foundry resources need REST; SDK returns 404 on cognitiveservices.azure.com
        if TTS_BASE:
            try:
                return _azure_tts_via_rest(text), None
            except Exception as exc:
                errors.append(f"Azure TTS REST: {exc}")
        else:
            try:
                client = get_azure_tts_client()
                if client:
                    resp = client.audio.speech.create(
                        model=TTS_DEPLOYMENT,
                        voice=TTS_VOICE,
                        input=text[:4096],
                        response_format="mp3",
                    )
                    return resp.content, None
            except Exception as exc:
                errors.append(f"Azure TTS: {exc}")

    direct = get_direct_openai_client()
    if direct:
        try:
            resp = direct.audio.speech.create(
                model="tts-1",
                voice=TTS_VOICE,
                input=text[:4096],
                response_format="mp3",
            )
            return resp.content, None
        except Exception as exc:
            errors.append(f"OpenAI TTS: {exc}")

    if errors:
        return None, errors[0]
    return None, "TTS not configured. Set AZURE_OPENAI_TTS_DEPLOYMENT or LE_OPEN_AI_KEY."


def _realtime_instructions(customer_email: str = "") -> str:
    policy = get_policy_summary()[:2500]
    text = f"""You are ShopFlow AI Customer Support on a live voice call for refund requests.
Speak clearly and briefly. Use tools before approving refunds.

Policy summary:
{policy}
"""
    if customer_email:
        text += f"\n\nCustomer email on file: {customer_email}"
    return text


def create_realtime_session(*, customer_email: str = "") -> Dict[str, Any]:
    """Create ephemeral Realtime session — OpenAI direct or Azure OpenAI."""
    instructions = _realtime_instructions(customer_email)
    realtime_model = REALTIME_DEPLOYMENT or os.getenv(
        "OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17"
    )
    payload = {
        "model": realtime_model,
        "voice": TTS_VOICE,
        "modalities": ["text", "audio"],
        "instructions": instructions,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "turn_detection": {"type": "server_vad"},
    }

    if openai_gpt_key:
        resp = requests.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {openai_gpt_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        provider = "openai"
        webrtc_base = "https://api.openai.com/v1/realtime"
    elif is_azure() and REALTIME_DEPLOYMENT:
        url = f"{openai_base}/openai/realtime/sessions?api-version={REALTIME_API_VERSION}"
        resp = requests.post(
            url,
            headers={
                "api-key": azure_openai_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        provider = "azure"
        webrtc_base = f"{openai_base}/openai/realtime"
    else:
        raise RuntimeError(
            "Live voice not configured. Set LE_OPEN_AI_KEY (OpenAI) or "
            "AZURE_OPENAI_REALTIME_DEPLOYMENT + Azure credentials. "
            "Use Hold to talk with browser STT fallback meanwhile."
        )

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Realtime session failed ({resp.status_code}): {resp.text[:400]}. "
            "Ensure Realtime deployment exists in Azure/OpenAI."
        )

    data = resp.json()
    secret = (data.get("client_secret") or {}).get("value")
    if not secret:
        raise RuntimeError("No client_secret in Realtime session response")

    return {
        "client_secret": secret,
        "model": realtime_model,
        "provider": provider,
        "webrtc_url": (
            f"{webrtc_base}?api-version={REALTIME_API_VERSION}"
            if provider == "azure"
            else f"{webrtc_base}?model={realtime_model}"
        ),
        "expires_at": (data.get("client_secret") or {}).get("expires_at"),
    }
