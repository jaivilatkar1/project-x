"""Django API views for Workpodd refund demo."""

import json
from pathlib import Path

from django.http import FileResponse, HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .agent import run_agent_turn
from .message_parser import parse_message
from .reasoning_log import reasoning_store
from .tools import execute_tool, get_policy_summary, load_crm
from .llm_client import get_voice_capabilities
from .voice_service import create_realtime_session, text_to_speech, transcribe_audio

DEMO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = DEMO_ROOT / "frontend"

_chat_history: dict = {}
_session_ctx: dict = {}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return JsonResponse({"status": "ok", "demo": "workpodd-refund-agent"})


@api_view(["GET"])
@permission_classes([AllowAny])
def list_customers(request):
    crm = load_crm()
    rows = [
        {
            "customer_id": c["customer_id"],
            "name": c["name"],
            "email": c["email"],
            "tier": c["tier"],
            "sample_order": c["orders"][0]["order_id"] if c["orders"] else None,
        }
        for c in crm["customers"]
    ]
    return JsonResponse({"customers": rows})


@api_view(["GET"])
@permission_classes([AllowAny])
def get_policy(request):
    return JsonResponse({"policy": get_policy_summary()})


def _run_chat(session_id: str, message: str, customer_email: str, parsed: dict):
    if not session_id:
        session_id = reasoning_store.create_session(customer_email)
    else:
        reasoning_store.ensure_session(session_id, customer_email)

    ctx = _session_ctx.setdefault(session_id, {})
    if parsed.get("email"):
        ctx["customer_email"] = parsed["email"]
        customer_email = parsed["email"]
    if parsed.get("order_id"):
        ctx["order_id"] = parsed["order_id"]

    history = _chat_history.setdefault(session_id, [])
    result = run_agent_turn(
        session_id,
        parsed["enriched"],
        customer_email=customer_email,
        order_id=ctx.get("order_id", ""),
        customer_id=ctx.get("customer_id", ""),
        history=history,
        session_ctx=ctx,
    )
    _session_ctx[session_id] = result.get("session_ctx") or ctx
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": result["reply"]})
    return session_id, result


@api_view(["POST"])
@permission_classes([AllowAny])
def chat(request):
    body = request.data or {}
    message = (body.get("message") or "").strip()
    session_id = body.get("session_id") or ""
    customer_email = (body.get("customer_email") or "").strip()

    if not message:
        return JsonResponse({"success": False, "message": "message is required"}, status=400)

    parsed = parse_message(message, customer_email)
    session_id, result = _run_chat(session_id, message, customer_email, parsed)

    return JsonResponse(
        {
            "success": True,
            "session_id": session_id,
            "reply": result["reply"],
            "tool_calls_made": result.get("tool_calls_made", 0),
            "parsed": {
                "email": parsed.get("email"),
                "order_id": parsed.get("order_id"),
            },
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_transcribe(request):
    """Whisper STT — upload audio (webm/wav/mp3), returns transcript + parsed entities."""
    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"success": False, "message": "audio file required"}, status=400)

    customer_email = (request.POST.get("customer_email") or "").strip()
    try:
        raw = transcribe_audio(audio.read(), filename=audio.name or "audio.webm")
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    parsed = parse_message(raw, customer_email)
    return JsonResponse(
        {
            "success": True,
            "transcript": raw,
            "parsed": parsed,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def voice_capabilities(request):
    """Which voice backends are configured (Whisper / TTS / Realtime)."""
    return JsonResponse({"success": True, **get_voice_capabilities()})


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_chat(request):
    """STT (Whisper or client transcript) + agent + optional TTS."""
    body = request.data if hasattr(request, "data") and request.data else {}
    audio = request.FILES.get("audio")
    raw = (request.POST.get("transcript") or body.get("transcript") or "").strip()
    stt_source = "client"

    session_id = request.POST.get("session_id") or body.get("session_id") or ""
    customer_email = (request.POST.get("customer_email") or body.get("customer_email") or "").strip()
    speak_raw = request.POST.get("speak", body.get("speak", "true"))
    speak = str(speak_raw).lower() != "false"

    if audio and not raw:
        try:
            raw = transcribe_audio(audio.read(), filename=audio.name or "audio.webm")
            stt_source = "server"
        except Exception as exc:
            return JsonResponse(
                {
                    "success": False,
                    "message": str(exc),
                    "fallback": "browser_stt",
                },
                status=503,
            )

    if not raw:
        return JsonResponse(
            {"success": False, "message": "audio file or transcript required"},
            status=400,
        )

    parsed = parse_message(raw, customer_email)
    session_id, result = _run_chat(session_id, raw, customer_email, parsed)

    payload = {
        "success": True,
        "session_id": session_id,
        "transcript": raw,
        "stt_source": stt_source,
        "parsed": {"email": parsed.get("email"), "order_id": parsed.get("order_id")},
        "reply": result["reply"],
        "tool_calls_made": result.get("tool_calls_made", 0),
    }

    if speak and result.get("reply"):
        mp3, tts_err = text_to_speech(result["reply"])
        if mp3:
            payload["audio_base64"] = __import__("base64").b64encode(mp3).decode("ascii")
            payload["audio_mime"] = "audio/mpeg"
        elif tts_err:
            payload["tts_error"] = tts_err

    return JsonResponse(payload)


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_speak(request):
    """TTS for agent reply text."""
    text = (request.data.get("text") or "").strip()
    if not text:
        return JsonResponse({"success": False, "message": "text required"}, status=400)
    mp3, tts_err = text_to_speech(text)
    if not mp3:
        return JsonResponse(
            {"success": False, "message": tts_err or "TTS failed"},
            status=503,
        )
    return HttpResponse(mp3, content_type="audio/mpeg")


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_realtime_session(request):
    """OpenAI Realtime ephemeral token for WebRTC live voice."""
    customer_email = (request.data.get("customer_email") or "").strip()
    try:
        session = create_realtime_session(customer_email=customer_email)
        sid = reasoning_store.create_session(customer_email)
        session["reasoning_session_id"] = sid
        return JsonResponse({"success": True, **session})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=503)


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_execute_tool(request):
    """Execute CRM tool from Realtime WebRTC client; logs to reasoning panel."""
    body = request.data or {}
    session_id = body.get("session_id") or ""
    fn_name = body.get("tool") or body.get("name")
    fn_args = body.get("arguments") or {}

    if not fn_name:
        return JsonResponse({"success": False, "message": "tool name required"}, status=400)

    if session_id:
        reasoning_store.ensure_session(session_id, "")
        ctx = _session_ctx.setdefault(session_id, {})
        from .agent import _sanitize_tool_args

        fn_args = _sanitize_tool_args(fn_name, fn_args, ctx)
        reasoning_store.append(session_id, "tool_call", f"{fn_name}({json.dumps(fn_args)})")
        result = execute_tool(fn_name, fn_args)
        reasoning_store.append(session_id, "tool_result", json.dumps(result)[:600])
        _session_ctx[session_id] = ctx
    else:
        result = execute_tool(fn_name, fn_args)

    return JsonResponse({"success": True, "result": result})


@api_view(["GET"])
@permission_classes([AllowAny])
def reasoning_logs(request, session_id=None):
    if session_id:
        return JsonResponse({"session_id": session_id, "logs": reasoning_store.get_logs(session_id)})
    return JsonResponse({"sessions": reasoning_store.list_sessions()})


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@csrf_exempt
@require_GET
def reasoning_stream(request, session_id):
    def event_stream():
        seen = 0
        while True:
            logs = reasoning_store.get_logs(session_id)
            if len(logs) > seen:
                for entry in logs[seen:]:
                    yield _sse_event(entry)
                seen = len(logs)
            import time

            time.sleep(0.8)
            if seen and logs and logs[-1].get("kind") in ("decision", "error"):
                yield _sse_event({"type": "done"})
                break
            if seen > 40:
                yield _sse_event({"type": "done"})
                break

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_GET
def serve_demo_ui(request):
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return HttpResponse("Demo UI not found", status=404)
    return FileResponse(open(index, "rb"), content_type="text/html")


@require_GET
def serve_demo_static(request, filename):
    path = FRONTEND_DIR / filename
    if not path.exists() or not path.is_file():
        return HttpResponse("Not found", status=404)
    if filename.endswith(".css"):
        ctype = "text/css"
    elif filename.endswith(".js"):
        ctype = "application/javascript"
    else:
        ctype = "application/octet-stream"
    return FileResponse(open(path, "rb"), content_type=ctype)
