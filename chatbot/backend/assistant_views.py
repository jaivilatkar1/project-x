from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from assistantService.helpers.utils import ResponseMessage
from assistantService.models import ChatMessage, ChatSession, UsersModel
from assistantService.services.assistant_service import AssistantService

def _user_id(request) -> str | None:
    """Read userId from body (POST) or query params (GET)."""
    return (
        request.data.get("userId")
        or request.data.get("user_id")
        or request.query_params.get("userId")
        or request.query_params.get("user_id")
    )

def _auth_user_id(request) -> str | None:
    """User id from JWT payload (CustomJWT) or authenticated UsersModel."""
    auth = getattr(request, "auth", None)
    if isinstance(auth, dict):
        uid = auth.get("userId")
        if uid:
            return str(uid)
    if auth is not None and hasattr(auth, "get"):
        try:
            uid = auth.get("userId")
            if uid:
                return str(uid)
        except Exception:
            pass

    user = getattr(request, "user", None)
    if user is None:
        return None

    row_key = getattr(user, "RowKey", None)
    if isinstance(row_key, str) and row_key:
        return row_key

    # CustomJWTAuthentication returns a queryset filtered by PartitionKey=userId
    try:
        from django.db.models.query import QuerySet

        if isinstance(user, QuerySet):
            first = user.first()
            if first is not None:
                return str(first.RowKey or first.PartitionKey)
    except Exception:
        pass

    return None

def _ensure_user_match(request, body_user_id: str):
    """Reject when JWT userId is present and does not match body/query userId."""
    auth_uid = _auth_user_id(request)
    if auth_uid and body_user_id and auth_uid != body_user_id:
        return Response(
            ResponseMessage.error_message("userId does not match authenticated user"),
            status=403,
        )
    return None

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    """
    POST /api/v1/assistants/chat
    Body: { userId, question|message, fileId?, sessionId? }
    """
    try:
        user_id = _user_id(request)
        question = (request.data.get("question") or request.data.get("message") or "").strip()
        file_id = (
            request.data.get("fileId")
            or request.data.get("file_id")
            or request.data.get("contractId")
        )
        session_id = request.data.get("sessionId") or request.data.get("session_id")

        if not user_id:
            return Response(ResponseMessage.error_message("userId is required"), status=400)
        if not question:
            return Response(ResponseMessage.error_message("question is required"), status=400)

        denied = _ensure_user_match(request, user_id)
        if denied:
            return denied

        result = AssistantService().chat(
            user_id=user_id,
            question=question,
            file_id=file_id,
            session_id=session_id,
        )
        status = 200 if result.get("success") else 400
        return Response(result, status=status)
    except Exception as e:
        return Response(
            ResponseMessage.error_message("Failed to chat", error=str(e)),
            status=500,
        )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def history(request):
    """
    GET /api/v1/assistants/history?userId=...&sessionId=...
    """
    try:
        user_id = _user_id(request)
        session_id = request.query_params.get("sessionId") or request.query_params.get("session_id")

        if not user_id:
            return Response(ResponseMessage.error_message("userId is required"), status=400)
        if not session_id:
            return Response(ResponseMessage.error_message("sessionId is required"), status=400)

        denied = _ensure_user_match(request, user_id)
        if denied:
            return denied

        user = UsersModel.objects.filter(RowKey=user_id).first()
        if not user:
            return Response(ResponseMessage.error_message("User not found"), status=404)

        session = ChatSession.objects.filter(session_id=session_id, user=user).first()
        if not session:
            return Response(ResponseMessage.error_message("Session not found"), status=404)

        messages = (
            ChatMessage.objects.filter(session=session)
            .order_by("created_at")
            .values(
                "message_id",
                "role",
                "message",
                "intent",
                "citations",
                "provider_used",
                "created_at",
            )
        )
        return Response(
            ResponseMessage.success_message(
                "ok",
                data={
                    "sessionId": str(session.session_id),
                    "fileId": str(session.contract_id) if session.contract_id else None,
                    "resolvedFileId": str(session.contract_id) if session.contract_id else None,
                    "messages": list(messages),
                },
            )
        )
    except Exception as e:
        return Response(
            ResponseMessage.error_message("Failed to get history", error=str(e)),
            status=500,
        )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sessions(request):
    """
    GET /api/v1/assistants/sessions?userId=...&fileId?=
    """
    try:
        user_id = _user_id(request)
        file_id = request.query_params.get("fileId") or request.query_params.get("file_id")

        if not user_id:
            return Response(ResponseMessage.error_message("userId is required"), status=400)

        denied = _ensure_user_match(request, user_id)
        if denied:
            return denied

        user = UsersModel.objects.filter(RowKey=user_id).first()
        if not user:
            return Response(ResponseMessage.error_message("User not found"), status=404)

        qs = ChatSession.objects.filter(user=user).order_by("-updated_at")
        if file_id:
            qs = qs.filter(contract_id=file_id)

        rows = qs.values("session_id", "contract_id", "title", "created_at", "updated_at")[:50]
        data = [
            {
                "sessionId": str(r["session_id"]),
                "fileId": str(r["contract_id"]) if r["contract_id"] else None,
                "title": r["title"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
        return Response(ResponseMessage.success_message("ok", data=data))
    except Exception as e:
        return Response(
            ResponseMessage.error_message("Failed to list sessions", error=str(e)),
            status=500,
        )
