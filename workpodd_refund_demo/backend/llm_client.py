"""LLM + audio clients — Azure / OpenAI env pattern from assistantService."""

import os
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

env_type = os.getenv("env_type")
azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")
openai_base = (os.getenv("LE_OPENAI_BASE") or "").rstrip("/")
azure_openai_version = os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
openai_gpt_key = os.getenv("LE_OPEN_AI_KEY")

CHAT_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_GPT4O")
    or os.getenv("AZURE_OPENAI_GPT4O_MINI")
    or os.getenv("LE_OPENAI_GPT4_TURBO")
    or "gpt-4o"
)
WHISPER_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT")
    or os.getenv("WHISPER_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_WHISPER")
)
TTS_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_TTS_DEPLOYMENT")
    or os.getenv("OPENAI_TTS_MODEL")
    or "tts-1"
)
# TTS may live on a different regional Azure resource (e.g. North Central US)
TTS_BASE = (os.getenv("AZURE_OPENAI_TTS_BASE") or os.getenv("AZURE_OPENAI_TTS_ENDPOINT") or "").rstrip("/")
TTS_API_KEY = os.getenv("AZURE_OPENAI_TTS_API_KEY") or azure_openai_key
TTS_API_VERSION = os.getenv(
    "AZURE_OPENAI_TTS_API_VERSION",
    os.getenv("OPENAI_API_VERSION", "2024-08-01-preview"),
)
REALTIME_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_REALTIME_DEPLOYMENT")
    or os.getenv("OPENAI_REALTIME_MODEL")
)
REALTIME_API_VERSION = os.getenv(
    "AZURE_OPENAI_REALTIME_API_VERSION", "2024-10-01-preview"
)
WHISPER_API_VERSION = os.getenv(
    "AZURE_OPENAI_WHISPER_API_VERSION",
    os.getenv("AZURE_OPENAI_GPT4O_API_VERSION") or azure_openai_version,
)


def is_azure() -> bool:
    return env_type == "NexaByte" and bool(azure_openai_key and openai_base)


def get_chat_client() -> Tuple[Any, str]:
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError as exc:
        raise RuntimeError("Install openai: pip install openai") from exc

    if is_azure():
        return AzureOpenAI(
            api_key=azure_openai_key,
            azure_endpoint=openai_base,
            api_version=os.getenv("AZURE_OPENAI_GPT4O_API_VERSION") or azure_openai_version,
        ), CHAT_DEPLOYMENT
    if openai_gpt_key:
        return OpenAI(api_key=openai_gpt_key), os.getenv("OPENAI_GPT4O_MODEL", "gpt-4o")
    raise RuntimeError("No LLM credentials configured.")


def get_openai_client():
    """Backward-compatible alias used by voice_service."""
    return get_chat_client()


def get_direct_openai_client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install openai: pip install openai") from exc
    if not openai_gpt_key:
        return None
    return OpenAI(api_key=openai_gpt_key)


def get_azure_audio_client(api_version: Optional[str] = None):
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise RuntimeError("Install openai: pip install openai") from exc
    if not is_azure():
        return None
    return AzureOpenAI(
        api_key=azure_openai_key,
        azure_endpoint=openai_base,
        api_version=api_version or WHISPER_API_VERSION,
    )


def get_azure_tts_client():
    """TTS client — uses dedicated regional endpoint when AZURE_OPENAI_TTS_BASE is set."""
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise RuntimeError("Install openai: pip install openai") from exc
    if not is_azure() or not TTS_DEPLOYMENT:
        return None
    endpoint = TTS_BASE or openai_base
    api_key = TTS_API_KEY if TTS_BASE else azure_openai_key
    if not endpoint or not api_key:
        return None
    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=TTS_API_VERSION,
    )


def has_azure_tts() -> bool:
    return bool(is_azure() and TTS_DEPLOYMENT and (TTS_BASE or openai_base))


def get_voice_capabilities() -> Dict[str, Any]:
    caps = {
        "azure": is_azure(),
        "has_openai_key": bool(openai_gpt_key),
        "whisper": {
            "configured": bool(WHISPER_DEPLOYMENT or openai_gpt_key),
            "deployment": WHISPER_DEPLOYMENT or ("whisper-1 (OpenAI direct)" if openai_gpt_key else None),
            "fallback": "browser_stt_or_gpt4o_audio",
        },
        "tts": {
            "configured": bool(has_azure_tts() or openai_gpt_key),
            "deployment": TTS_DEPLOYMENT,
            "endpoint": TTS_BASE or openai_base or None,
            "regional_resource": bool(TTS_BASE),
        },
        "realtime": {
            "configured": bool(
                openai_gpt_key
                or (is_azure() and os.getenv("AZURE_OPENAI_REALTIME_DEPLOYMENT"))
            ),
            "deployment": REALTIME_DEPLOYMENT,
            "provider": "azure" if is_azure() and not openai_gpt_key else "openai",
        },
    }
    if is_azure() and not WHISPER_DEPLOYMENT and not openai_gpt_key:
        caps["whisper"]["hint"] = (
            "Set AZURE_OPENAI_WHISPER_DEPLOYMENT to your Azure Whisper deployment name, "
            "or set LE_OPEN_AI_KEY for OpenAI Whisper. Browser STT fallback always available."
        )
    if not openai_gpt_key and is_azure() and not has_azure_tts():
        caps["tts"]["hint"] = (
            "Set AZURE_OPENAI_TTS_DEPLOYMENT. If TTS is in another region, also set "
            "AZURE_OPENAI_TTS_BASE and AZURE_OPENAI_TTS_API_KEY from that resource."
        )
    if not openai_gpt_key and is_azure() and not os.getenv("AZURE_OPENAI_REALTIME_DEPLOYMENT"):
        caps["realtime"]["hint"] = (
            "Set AZURE_OPENAI_REALTIME_DEPLOYMENT or LE_OPEN_AI_KEY for live voice."
        )
    return caps


def chat_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    *,
    max_tokens: int = 1200,
) -> Any:
    client, model = get_chat_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
        max_tokens=max_tokens,
    )


def chat_simple(messages: List[Dict[str, str]], *, max_tokens: int = 800) -> str:
    client, model = get_chat_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def parse_tool_args(raw: str) -> Dict[str, Any]:
    try:
        import json

        return json.loads(raw or "{}")
    except Exception:
        return {}
