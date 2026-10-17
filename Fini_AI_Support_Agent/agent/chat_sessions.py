"""In-memory chat sessions for the web UI (one SupportAgent per browser conversation)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from agent.loop import Mode, SupportAgent
from agent.tools.store import MockStore


@dataclass
class ChatSession:
    id: str
    agent: SupportAgent
    history: list[dict[str, Any]]


_lock = threading.Lock()
_sessions: dict[str, ChatSession] = {}


def _default_mode() -> Mode:
    if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
        return "azure"
    return "deterministic"


def create_session(mode: Mode | None = None) -> ChatSession:
    mode = mode or _default_mode()
    sid = uuid.uuid4().hex
    agent = SupportAgent(mode=mode, store=MockStore())
    session = ChatSession(id=sid, agent=agent, history=[])
    with _lock:
        _sessions[sid] = session
    return session


def get_session(session_id: str) -> ChatSession | None:
    with _lock:
        return _sessions.get(session_id)


def reset_session(session_id: str, mode: Mode | None = None) -> ChatSession:
    mode = mode or _default_mode()
    with _lock:
        existing = _sessions.get(session_id)
        if existing is not None:
            mode = mode or existing.agent.mode
    agent = SupportAgent(mode=mode, store=MockStore())
    session = ChatSession(id=session_id, agent=agent, history=[])
    with _lock:
        _sessions[session_id] = session
    return session


def session_snapshot(chat: ChatSession) -> dict[str, Any]:
    s = chat.agent.session
    return {
        "session_id": chat.id,
        "mode": chat.agent.mode,
        "verified": s.verified,
        "locked": s.locked,
        "escalated": s.escalated,
        "ticket_id": s.ticket_id,
        "customer_id": s.customer_id,
        "failed_verifications": s.failed_verifications,
        "refunds_issued": list(s.refunds_issued),
    }
