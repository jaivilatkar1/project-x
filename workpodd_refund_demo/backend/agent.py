"""Refund support agent — OpenAI tool-calling loop with reasoning logs."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .llm_client import chat_with_tools, parse_tool_args
from .message_parser import is_valid_email
from .reasoning_log import reasoning_store
from .tools import TOOL_DEFINITIONS, execute_tool, get_policy_summary

MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are ShopFlow AI Customer Support Agent handling e-commerce refund requests.

RULES:
1. If VERIFIED CUSTOMER EMAIL is provided below, use THAT email for lookup_customer — never guess or use placeholder emails.
2. If VERIFIED ORDER ID is provided, use it for order/policy/refund tools.
3. Always call check_refund_policy before process_refund.
4. Never call process_refund if policy check does not return approved=true.
5. If policy returns requires_manager=true, use escalate_to_human instead of process_refund.
6. When denying a refund, cite the specific policy reason politely ("holding the line").
7. Be concise, empathetic, and professional.

REFUND POLICY SUMMARY:
{policy}
"""


def _sanitize_tool_args(
    fn_name: str,
    args: Dict[str, Any],
    session_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Prevent bad voice/STT extractions (e.g. email=hello) from breaking CRM lookup."""
    args = dict(args or {})
    verified_email = (session_ctx.get("customer_email") or "").strip().lower()
    verified_order = (session_ctx.get("order_id") or "").strip().upper()
    verified_cid = (session_ctx.get("customer_id") or "").strip().upper()

    if fn_name == "lookup_customer":
        email = (args.get("email") or "").strip().lower()
        if not is_valid_email(email):
            if verified_email:
                args["email"] = verified_email
            else:
                args.pop("email", None)
        if not args.get("email") and not args.get("customer_id") and verified_cid:
            args["customer_id"] = verified_cid

    for tool in ("get_order_details", "check_refund_policy", "process_refund", "escalate_to_human"):
        if fn_name == tool:
            if verified_cid and not args.get("customer_id"):
                args["customer_id"] = verified_cid
            if verified_order and not args.get("order_id"):
                args["order_id"] = verified_order
    return args


def _update_session_from_tool(session_ctx: Dict[str, Any], fn_name: str, result: Dict[str, Any]):
    if fn_name == "lookup_customer" and result.get("found"):
        c = result.get("customer") or {}
        session_ctx["customer_id"] = c.get("customer_id", "")
        session_ctx["customer_email"] = c.get("email", session_ctx.get("customer_email", ""))
    if fn_name == "get_order_details" and result.get("found"):
        session_ctx["order_id"] = (result.get("order") or {}).get("order_id") or session_ctx.get("order_id", "")


def run_agent_turn(
    session_id: str,
    user_message: str,
    *,
    customer_email: str = "",
    order_id: str = "",
    customer_id: str = "",
    history: Optional[List[Dict[str, str]]] = None,
    session_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run one customer message through the agent loop; append reasoning logs."""
    ctx = session_ctx if session_ctx is not None else {}
    if customer_email:
        ctx["customer_email"] = customer_email
    if order_id:
        ctx["order_id"] = order_id
    if customer_id:
        ctx["customer_id"] = customer_id

    policy = get_policy_summary()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(policy=policy[:4000])},
    ]

    verified_bits = []
    if ctx.get("customer_email"):
        verified_bits.append(f"VERIFIED CUSTOMER EMAIL: {ctx['customer_email']}")
    if ctx.get("customer_id"):
        verified_bits.append(f"VERIFIED CUSTOMER ID: {ctx['customer_id']}")
    if ctx.get("order_id"):
        verified_bits.append(f"VERIFIED ORDER ID: {ctx['order_id']}")
    if verified_bits:
        messages.append({"role": "system", "content": "\n".join(verified_bits)})

    if history:
        messages.extend(history[-12:])
    messages.append({"role": "user", "content": user_message})

    reasoning_store.append(session_id, "thought", f"Customer: {user_message[:200]}")
    tool_calls_made = 0
    final_reply = ""

    for iteration in range(MAX_ITERATIONS):
        try:
            response = chat_with_tools(messages, TOOL_DEFINITIONS)
        except Exception as exc:
            reasoning_store.append(session_id, "error", str(exc))
            reasoning_store.finish(session_id, "error")
            return {
                "reply": "I'm having trouble connecting to our systems. Please try again shortly.",
                "session_id": session_id,
                "error": str(exc),
            }

        choice = response.choices[0].message
        assistant_msg: Dict[str, Any] = {"role": "assistant", "content": choice.content or ""}
        if choice.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.tool_calls
            ]
        messages.append(assistant_msg)

        if not choice.tool_calls:
            final_reply = (choice.content or "").strip()
            reasoning_store.append(session_id, "decision", final_reply[:500])
            break

        for tc in choice.tool_calls:
            tool_calls_made += 1
            fn_name = tc.function.name
            fn_args = _sanitize_tool_args(fn_name, parse_tool_args(tc.function.arguments), ctx)
            reasoning_store.append(
                session_id,
                "tool_call",
                f"{fn_name}({json.dumps(fn_args)})",
                {"tool": fn_name, "arguments": fn_args},
            )
            result = execute_tool(fn_name, fn_args)
            _update_session_from_tool(ctx, fn_name, result)
            reasoning_store.append(
                session_id,
                "tool_result",
                json.dumps(result)[:600],
                {"tool": fn_name, "result": result},
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

            if fn_name == "process_refund" and result.get("success"):
                reasoning_store.finish(session_id, "refund_processed")
            elif fn_name == "check_refund_policy" and result.get("decision") == "deny":
                reasoning_store.append(session_id, "thought", "Policy violation — holding the line")

    if not final_reply:
        final_reply = (
            "I've reviewed your request. Please confirm your email and order number "
            "(for example ORD-5001) so I can continue."
        )
        reasoning_store.finish(session_id, "incomplete")

    return {
        "reply": final_reply,
        "session_id": session_id,
        "tool_calls_made": tool_calls_made,
        "iterations": iteration + 1,
        "session_ctx": ctx,
    }
