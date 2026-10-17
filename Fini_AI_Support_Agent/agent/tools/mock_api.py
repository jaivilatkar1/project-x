"""Mock Paylane API tools. Policy is enforced here, not only in the prompt."""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

from agent.session import SessionState
from agent.tools.policy import evaluate_refund, should_auto_lock
from agent.tools.store import MockStore

# Patterns that imply immediate handoff without requiring verification.
_HANDOFF_HINTS = re.compile(
    r"\b(lawyer|attorney|legal\s+action|sue|lawsuit|close\s+(my\s+)?account|"
    r"account\s+closure|speak\s+to\s+(a\s+)?(human|person|agent|representative)|"
    r"talk\s+to\s+(a\s+)?(human|person|agent)|real\s+person|fraud)\b",
    re.I,
)


def _public_customer(customer: dict[str, Any]) -> dict[str, Any]:
    """Return fields safe to share with the model after identity verification."""
    return {
        "id": customer["id"],
        "name": customer["name"],
        "card_last4": customer["card_last4"],
        "status": customer["status"],
        "verified": customer["verified"],
        # freeze_reason only after verification; never invent one
        "freeze_reason": customer.get("freeze_reason"),
    }


class PaylaneTools:
    """Implements the four specified tools with session-aware guards."""

    def __init__(self, store: MockStore | None = None, session: SessionState | None = None) -> None:
        self.store = store or MockStore()
        self.session = session or SessionState()

    def _blocked(self) -> dict[str, Any] | None:
        if self.session.locked:
            if self.session.escalated:
                detail = (
                    "This chat was handed off to a human. Account tools are paused here. "
                    "Start a New chat for a different scenario or customer."
                )
            else:
                detail = (
                    "Session locked after three failed identity checks. "
                    "A human ticket was opened; start a New chat to try again."
                )
            return {
                "ok": False,
                "reason": "session_locked",
                "detail": detail,
                "escalated": self.session.escalated,
                "ticket_id": self.session.ticket_id,
            }
        return None

    def get_customer(self, email: str, card_last4: str | None = None) -> dict[str, Any]:
        """
        Lookup customer by email.

        Identity verification (clarification): session becomes verified only when
        both email and last4 match the mock record. card_last4 is the caller's
        claimed value — required before any account detail is returned.
        """
        blocked = self._blocked()
        if blocked:
            self.session.record_tool("get_customer", {"email": email, "card_last4": card_last4}, blocked)
            return blocked

        customer = self.store.get_customer_by_email(email)
        if customer is None:
            result = {"ok": False, "reason": "customer_not_found"}
            self.session.record_tool("get_customer", {"email": email, "card_last4": card_last4}, result)
            return result

        if not card_last4:
            result = {
                "ok": False,
                "reason": "verification_required",
                "detail": (
                    "Before account details, confirm the email on file and the last "
                    "4 digits of the card. Call get_customer again with card_last4."
                ),
            }
            self.session.record_tool("get_customer", {"email": email, "card_last4": card_last4}, result)
            return result

        claimed = str(card_last4).strip()
        if claimed != customer["card_last4"]:
            self.session.failed_verifications += 1
            if should_auto_lock(self.session.failed_verifications):
                self.session.locked = True
                esc = self.escalate_to_human(
                    customer_id=customer["id"],
                    summary="Three failed identity verification attempts; session locked.",
                )
                result = {
                    "ok": False,
                    "reason": "verification_failed_locked",
                    "failed_verifications": self.session.failed_verifications,
                    "escalation": esc,
                }
            else:
                result = {
                    "ok": False,
                    "reason": "verification_failed",
                    "failed_verifications": self.session.failed_verifications,
                    "remaining_attempts": settings.MAX_FAILED_VERIFICATIONS
                    - self.session.failed_verifications,
                }
            self.session.record_tool("get_customer", {"email": email, "card_last4": "****"}, result)
            return result

        # Success — trusted session state
        self.session.verified = True
        self.session.customer_id = customer["id"]
        self.session.customer_email = customer["email"]
        result = {"ok": True, **_public_customer(customer)}
        # Never echo the full email back as a revealed secret; model already has claim.
        self.session.record_tool("get_customer", {"email": email, "card_last4": "****"}, result)
        return result

    def get_transaction(self, customer_id: str, txn_id: str) -> dict[str, Any]:
        blocked = self._blocked()
        if blocked:
            self.session.record_tool(
                "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, blocked
            )
            return blocked

        if not self.session.verified:
            result = {"ok": False, "reason": "identity_not_verified"}
            self.session.record_tool(
                "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, result
            )
            return result

        if customer_id != self.session.customer_id:
            result = {"ok": False, "reason": "customer_id_mismatch"}
            self.session.record_tool(
                "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, result
            )
            return result

        txn = self.store.get_transaction(txn_id)
        if txn is None:
            result = {"ok": False, "reason": "transaction_not_found"}
            self.session.record_tool(
                "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, result
            )
            return result

        if txn["customer_id"] != customer_id:
            result = {"ok": False, "reason": "transaction_not_owned_by_customer"}
            self.session.record_tool(
                "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, result
            )
            return result

        result = {
            "ok": True,
            "id": txn["id"],
            "amount": txn["amount"],
            "date": txn["date"],
            "merchant": txn["merchant"],
            "status": txn["status"],
        }
        self.session.record_tool(
            "get_transaction", {"customer_id": customer_id, "txn_id": txn_id}, result
        )
        return result

    def issue_refund(self, txn_id: str, amount: float) -> dict[str, Any]:
        blocked = self._blocked()
        if blocked:
            self.session.record_tool("issue_refund", {"txn_id": txn_id, "amount": amount}, blocked)
            return blocked

        if self.session.escalated:
            result = {
                "ok": False,
                "reason": "already_escalated",
                "detail": "Stop consequential actions after handoff.",
            }
            self.session.record_tool("issue_refund", {"txn_id": txn_id, "amount": amount}, result)
            return result

        customer = (
            self.store.get_customer_by_id(self.session.customer_id)
            if self.session.customer_id
            else None
        )
        txn = self.store.get_transaction(txn_id)
        decision = evaluate_refund(
            session_verified=self.session.verified,
            customer=customer,
            txn=txn,
            amount=float(amount),
        )

        if not decision.allowed:
            result: dict[str, Any] = {
                "ok": False,
                "reason": decision.reason,
                "should_escalate": decision.should_escalate,
            }
            self.session.record_tool("issue_refund", {"txn_id": txn_id, "amount": amount}, result)
            return result

        assert txn is not None
        txn["status"] = "refunded"
        refund_id = self.store.next_refund_id()
        self.session.refunds_issued.append(txn_id)
        result = {"ok": True, "refund_id": refund_id}
        self.session.record_tool("issue_refund", {"txn_id": txn_id, "amount": amount}, result)
        return result

    def escalate_to_human(self, customer_id: str | None, summary: str) -> dict[str, Any]:
        """Handoff. Legal/closure/person requests may use null/guest IDs."""
        ticket_id = self.store.next_ticket_id()
        self.session.escalated = True
        self.session.ticket_id = ticket_id
        # Stop consequential account actions for this issue after handoff.
        self.session.locked = True
        result = {
            "ok": True,
            "ticket_id": ticket_id,
            "customer_id": customer_id or "guest",
            "summary": summary,
        }
        self.session.record_tool(
            "escalate_to_human",
            {"customer_id": customer_id, "summary": summary},
            result,
        )
        return result

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_customer":
            return self.get_customer(
                email=arguments["email"],
                card_last4=arguments.get("card_last4"),
            )
        if name == "get_transaction":
            return self.get_transaction(
                customer_id=arguments["customer_id"],
                txn_id=arguments["txn_id"],
            )
        if name == "issue_refund":
            return self.issue_refund(
                txn_id=arguments["txn_id"],
                amount=float(arguments["amount"]),
            )
        if name == "escalate_to_human":
            return self.escalate_to_human(
                customer_id=arguments.get("customer_id"),
                summary=arguments.get("summary", ""),
            )
        return {"ok": False, "reason": f"unknown_tool:{name}"}


def looks_like_immediate_handoff(text: str) -> bool:
    return bool(_HANDOFF_HINTS.search(text or ""))
