"""Typed session state for verification, escalation, and tool gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SessionState:
    """Trusted application state — not controlled by the model."""

    verified: bool = False
    customer_id: str | None = None
    customer_email: str | None = None
    failed_verifications: int = 0
    escalated: bool = False
    ticket_id: str | None = None
    locked: bool = False  # after 3 failed checks or post-escalation stop for issue
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    refunds_issued: list[str] = field(default_factory=list)

    def record_tool(self, name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        self.tool_trace.append({"tool": name, "args": args, "result": result})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
