"""In-memory reasoning log store for admin dashboard (session-scoped)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ReasoningEntry:
    step: int
    kind: str  # thought | tool_call | tool_result | decision | error
    content: str
    detail: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReasoningLogStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, List[ReasoningEntry]] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}

    def create_session(self, customer_email: str = "") -> str:
        sid = str(uuid.uuid4())
        with self._lock:
            self._sessions[sid] = []
            self._meta[sid] = {
                "session_id": sid,
                "customer_email": customer_email,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        return sid

    def ensure_session(self, session_id: str, customer_email: str = "") -> str:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
                self._meta[session_id] = {
                    "session_id": session_id,
                    "customer_email": customer_email,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "active",
                }
            return session_id

    def append(self, session_id: str, kind: str, content: str, detail: Optional[Dict] = None):
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            step = len(self._sessions[session_id]) + 1
            self._sessions[session_id].append(
                ReasoningEntry(step=step, kind=kind, content=content, detail=detail)
            )

    def finish(self, session_id: str, outcome: str):
        with self._lock:
            if session_id in self._meta:
                self._meta[session_id]["status"] = outcome

    def get_logs(self, session_id: str) -> List[Dict]:
        with self._lock:
            return [asdict(e) for e in self._sessions.get(session_id, [])]

    def list_sessions(self) -> List[Dict]:
        with self._lock:
            out = []
            for sid, meta in self._meta.items():
                out.append(
                    {
                        **meta,
                        "log_count": len(self._sessions.get(sid, [])),
                        "last_entry": (
                            self._sessions[sid][-1].content[:80]
                            if self._sessions.get(sid)
                            else ""
                        ),
                    }
                )
            return sorted(out, key=lambda x: x["created_at"], reverse=True)


reasoning_store = ReasoningLogStore()
