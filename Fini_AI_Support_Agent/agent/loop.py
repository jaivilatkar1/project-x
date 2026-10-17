"""Agent conversation loop: Azure OpenAI tool-calling + offline deterministic mode."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from django.conf import settings

from agent.prompt import SYSTEM_PROMPT
from agent.session import SessionState
from agent.tools.mock_api import PaylaneTools
from agent.tools.registry import TOOL_DEFINITIONS
from agent.tools.store import MockStore

Mode = Literal["azure", "deterministic"]


@dataclass
class TurnResult:
    assistant_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConversationResult:
    mode: Mode
    messages: list[dict[str, Any]]
    session: SessionState
    final_text: str


def _azure_client():
    from openai import AzureOpenAI

    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
        raise RuntimeError(
            "Azure OpenAI is not configured. Set AZURE_OPENAI_API_KEY and "
            "AZURE_OPENAI_ENDPOINT (see .env.example)."
        )
    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )


class SupportAgent:
    def __init__(
        self,
        mode: Mode = "azure",
        store: MockStore | None = None,
        session: SessionState | None = None,
        max_tool_rounds: int = 8,
    ) -> None:
        self.mode = mode
        self.store = store or MockStore()
        self.session = session or SessionState()
        self.tools = PaylaneTools(store=self.store, session=self.session)
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    def run_user_turns(self, user_messages: list[str]) -> ConversationResult:
        final = ""
        for text in user_messages:
            turn = self.handle_user_message(text)
            final = turn.assistant_text
        return ConversationResult(
            mode=self.mode,
            messages=list(self.messages),
            session=self.session,
            final_text=final,
        )

    def handle_user_message(self, text: str) -> TurnResult:
        self.messages.append({"role": "user", "content": text})
        if self.mode == "deterministic":
            return self._deterministic_turn(text)
        return self._azure_turn()

    def _execute_tool_calls(self, tool_calls: list[Any]) -> list[dict[str, Any]]:
        recorded: list[dict[str, Any]] = []
        for tc in tool_calls:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            result = self.tools.dispatch(name, args)
            recorded.append({"id": tc.id, "name": name, "args": args, "result": result})
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )
        return recorded

    def _azure_turn(self) -> TurnResult:
        client = _azure_client()
        all_tools: list[dict[str, Any]] = []
        assistant_text = ""

        for _ in range(self.max_tool_rounds):
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = response.choices[0].message
            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if msg.tool_calls:
                assistant_payload["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ]
            self.messages.append(assistant_payload)

            if not msg.tool_calls:
                assistant_text = msg.content or ""
                break

            all_tools.extend(self._execute_tool_calls(msg.tool_calls))
        else:
            assistant_text = (
                assistant_text
                or "I hit a processing limit — let me connect you with a teammate."
            )

        return TurnResult(assistant_text=assistant_text, tool_calls=all_tools)

    # --- Offline deterministic agent (same tools/policy; not an LLM) ---

    def _deterministic_turn(self, text: str) -> TurnResult:
        """Rule-based agent for offline eval demos. Labeled mode=deterministic."""
        lower = text.lower()
        tool_calls: list[dict[str, Any]] = []

        def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
            result = self.tools.dispatch(name, args)
            tool_calls.append({"name": name, "args": args, "result": result})
            self.messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"det_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                }
            )
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": f"det_{len(tool_calls)}",
                    "content": json.dumps(result),
                }
            )
            return result

        reply = self._deterministic_policy(lower, text, call)
        self.messages.append({"role": "assistant", "content": reply})
        return TurnResult(assistant_text=reply, tool_calls=tool_calls)

    def _deterministic_policy(self, lower: str, text: str, call) -> str:
        # Immediate handoffs
        if re.search(r"\b(lawyer|attorney|legal action|sue|lawsuit)\b", lower):
            r = call(
                "escalate_to_human",
                {
                    "customer_id": self.session.customer_id,
                    "summary": "Customer mentioned legal action.",
                },
            )
            return (
                f"I'm sorry you're dealing with this. I've opened ticket {r['ticket_id']} "
                "for a specialist — I won't take further account actions on this."
            )

        if re.search(r"close (my )?account|account closure", lower):
            r = call(
                "escalate_to_human",
                {
                    "customer_id": self.session.customer_id,
                    "summary": "Account closure request.",
                },
            )
            return f"I can help start that with a person. Ticket {r['ticket_id']} is open."

        if re.search(
            r"speak to (a )?(human|person|agent)|talk to (a )?(human|person)|real person",
            lower,
        ):
            r = call(
                "escalate_to_human",
                {
                    "customer_id": self.session.customer_id,
                    "summary": "Customer asked for a human agent.",
                },
            )
            return f"Of course — ticket {r['ticket_id']}. A teammate will take it from here."

        if "fraud" in lower or "unauthorized" in lower or "didn't make" in lower:
            priority = "high" if re.search(r"\$?\s*([6-9]\d{2}|\d{4,})", lower) else "normal"
            r = call(
                "escalate_to_human",
                {
                    "customer_id": self.session.customer_id,
                    "summary": f"Suspected unauthorized/fraud report ({priority}).",
                },
            )
            return (
                f"Thanks for flagging this — I'm escalating it now "
                f"(ticket {r['ticket_id']}). Please don't share full card numbers here."
            )

        if self.session.locked:
            return (
                "This chat is locked for account actions. A human has the ticket — "
                "they'll follow up."
            )

        email = _extract_email(text)
        last4 = _extract_last4(text)

        # Verification flow — may continue into action handling in the same turn.
        verified_preamble = ""
        if not self.session.verified:
            if email and last4:
                r = call("get_customer", {"email": email, "card_last4": last4})
                if r.get("ok"):
                    status = r.get("status")
                    extra = ""
                    if status == "frozen":
                        reason = r.get("freeze_reason") or "our risk team flagged the card"
                        extra = (
                            f" Your card is frozen because: {reason}. "
                            "I can't unfreeze it myself."
                        )
                    verified_preamble = (
                        f"Thanks, you're verified, {r['name']}. "
                        f"Card ending {r['card_last4']} is on file.{extra} "
                    )
                    # Fall through if this same message also asks for an action.
                    if not any(
                        k in lower
                        for k in (
                            "refund",
                            "txn_",
                            "unfreeze",
                            "frozen",
                            "fraud",
                            "lawyer",
                            "human",
                            "full card",
                            "full number",
                        )
                    ):
                        return verified_preamble + "How can I help?"
                else:
                    if r.get("reason") == "verification_failed_locked":
                        tid = r.get("escalation", {}).get("ticket_id", "pending")
                        return (
                            f"I couldn't verify those details after several tries. "
                            f"Ticket {tid} is with a person now."
                        )
                    if r.get("reason") == "verification_failed":
                        return (
                            "That email and last4 didn't match. "
                            f"{r.get('remaining_attempts')} tries left — want to try again?"
                        )
                    if r.get("reason") == "customer_not_found":
                        return "I couldn't find an account with that email. Double-check it?"
                    return "I couldn't verify that yet. Please share email and last4."
            elif email and not last4:
                call("get_customer", {"email": email})
                return (
                    "Thanks. To protect the account, please confirm the last 4 digits "
                    "of your card."
                )
            elif any(
                k in lower
                for k in ("refund", "transaction", "card", "frozen", "charge", "payment")
            ):
                return (
                    "Happy to help. Please share the email on your Paylane account and "
                    "the last 4 digits of your card so I can verify it's you."
                )
            else:
                return (
                    "Hi — I can help with cards, transfers, and refunds. "
                    "What do you need today?"
                )

        def _prefix(msg: str) -> str:
            return (verified_preamble + msg).strip()

        # Verified paths
        if "unfreeze" in lower or (
            "frozen" in lower and ("unfreeze" in lower or "why" in lower or "please" in lower)
        ):
            cust = self.store.get_customer_by_id(self.session.customer_id or "")
            if cust and cust.get("status") == "frozen":
                r = call(
                    "escalate_to_human",
                    {
                        "customer_id": self.session.customer_id,
                        "summary": "Customer requests card unfreeze / freeze explanation follow-up.",
                    },
                )
                reason = cust.get("freeze_reason") or "a risk review"
                return _prefix(
                    f"Your card is frozen due to: {reason}. I can't unfreeze it myself — "
                    f"ticket {r['ticket_id']} is with a specialist."
                )

        if "full card" in lower or "full number" in lower or "what is my email" in lower:
            return _prefix(
                "I can't share full card numbers or read back the email on file. "
                "I can only confirm the last4 you already provided."
            )

        txn_id = _extract_txn_id(text)
        if "refund" in lower or txn_id:
            if not txn_id:
                return _prefix(
                    "I can check a refund once I have the transaction id "
                    "(looks like txn_…)."
                )
            tr = call(
                "get_transaction",
                {"customer_id": self.session.customer_id, "txn_id": txn_id},
            )
            if not tr.get("ok"):
                return _prefix("I couldn't load that transaction. Can you confirm the id?")

            if tr["status"] == "pending":
                return _prefix(
                    "That charge is still pending, so I can't refund it yet. "
                    "There's no void tool on my side — want me to escalate to a person?"
                )

            amount = float(tr["amount"])
            rr = call("issue_refund", {"txn_id": txn_id, "amount": amount})
            if rr.get("ok"):
                return _prefix(
                    f"Done — refund {rr['refund_id']} for ${amount:.2f} is submitted."
                )

            reason = rr.get("reason", "not_allowed")
            if rr.get("should_escalate") or reason in {
                "amount_over_auto_limit",
                "exactly_30_days_escalate",
                "transaction_too_old",
                "customer_not_verified_for_auto_refund",
            }:
                er = call(
                    "escalate_to_human",
                    {
                        "customer_id": self.session.customer_id,
                        "summary": f"Refund blocked ({reason}) for {txn_id}.",
                    },
                )
                return _prefix(
                    f"I can't auto-refund that ({reason.replace('_', ' ')}). "
                    f"I've opened ticket {er['ticket_id']} for a teammate."
                )
            if reason == "already_refunded":
                return _prefix(
                    "That transaction was already refunded — I can't refund it again."
                )
            return _prefix(
                f"I can't refund that right now ({reason.replace('_', ' ')})."
            )

        if "spouse" in lower or "husband" in lower or "wife" in lower or "his account" in lower:
            return (
                "I can only help the account holder after they verify email and last4. "
                "I won't share account details with someone else."
            )

        return _prefix(
            "You're verified. Share a transaction id for a refund, or tell me what you need."
        )


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LAST4_RE = re.compile(r"\b(\d{4})\b")
_TXN_RE = re.compile(r"\b(txn_[a-z0-9_]+)\b", re.I)


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_last4(text: str) -> str | None:
    # Prefer explicit "last4" / "ending" context; else first 4-digit token that isn't a year-like alone
    contextual = re.search(
        r"(?:last\s*4|last4|ending(?:\s+in)?|digits?)\D{0,12}(\d{4})",
        text,
        re.I,
    )
    if contextual:
        return contextual.group(1)
    # If email present, take a 4-digit group elsewhere
    if _EMAIL_RE.search(text):
        for m in _LAST4_RE.finditer(text):
            return m.group(1)
    return None


def _extract_txn_id(text: str) -> str | None:
    m = _TXN_RE.search(text)
    return m.group(1) if m else None
