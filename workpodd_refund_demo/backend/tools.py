"""CRM + refund policy tools for the support agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEMO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = DEMO_ROOT / "data"

TIER_WINDOWS = {"standard": 30, "premium": 45, "vip": 60}
TIER_REFUND_LIMITS = {"standard": 2, "premium": 4, "vip": 6}
AUTO_APPROVE_MAX = 150.0
MANAGER_MAX = 500.0

NON_REFUNDABLE_CATEGORIES = {"digital", "gift_card", "personalized"}


def load_crm() -> Dict:
    with open(DATA_DIR / "crm_profiles.json", encoding="utf-8") as f:
        return json.load(f)


def _load_policy_text() -> str:
    return (DATA_DIR / "refund_policy.md").read_text(encoding="utf-8")


def lookup_customer(email: str = "", customer_id: str = "") -> Dict[str, Any]:
    crm = load_crm()
    email = (email or "").strip().lower()
    customer_id = (customer_id or "").strip().upper()
    for c in crm["customers"]:
        if email and c["email"].lower() == email:
            return {"found": True, "customer": _public_customer(c)}
        if customer_id and c["customer_id"].upper() == customer_id:
            return {"found": True, "customer": _public_customer(c)}
    return {"found": False, "message": "Customer not found in CRM"}


def _public_customer(c: Dict) -> Dict:
    return {
        "customer_id": c["customer_id"],
        "name": c["name"],
        "email": c["email"],
        "tier": c["tier"],
        "account_status": c["account_status"],
        "refunds_ytd": c["refunds_ytd"],
        "order_ids": [o["order_id"] for o in c["orders"]],
    }


def _find_customer_and_order(customer_id: str, order_id: str) -> Tuple[Optional[Dict], Optional[Dict]]:
    crm = load_crm()
    for c in crm["customers"]:
        if c["customer_id"].upper() != customer_id.upper():
            continue
        for o in c["orders"]:
            if o["order_id"].upper() == order_id.upper():
                return c, o
        return c, None
    return None, None


def get_order_details(customer_id: str, order_id: str) -> Dict[str, Any]:
    customer, order = _find_customer_and_order(customer_id, order_id)
    if not customer:
        return {"found": False, "message": "Customer not found"}
    if not order:
        return {"found": False, "message": "Order not found for this customer"}
    return {
        "found": True,
        "order": {
            **order,
            "customer_id": customer["customer_id"],
            "customer_name": customer["name"],
            "customer_tier": customer["tier"],
        },
    }


def check_refund_policy(
    customer_id: str,
    order_id: str,
    reason: str = "",
) -> Dict[str, Any]:
    customer, order = _find_customer_and_order(customer_id, order_id)
    if not customer or not order:
        return {"approved": False, "decision": "deny", "reasons": ["Customer or order not found"]}

    reasons: List[str] = []
    tier = customer["tier"]
    window = TIER_WINDOWS.get(tier, 30)
    limit = TIER_REFUND_LIMITS.get(tier, 2)

    if customer["account_status"] in ("suspended", "flagged"):
        reasons.append(f"Account status is {customer['account_status']} (Policy §6)")

    if customer["refunds_ytd"] >= limit:
        reasons.append(
            f"Customer exceeded {limit} refunds in 12 months (current: {customer['refunds_ytd']}) (Policy §2)"
        )

    if order["status"] != "delivered":
        reasons.append(f"Order status is '{order['status']}' — must be delivered (Policy §4)")

    if order.get("final_sale"):
        reasons.append("Item is Final Sale — non-refundable (Policy §3)")

    if order.get("digital_downloaded"):
        reasons.append("Digital product was downloaded — non-refundable (Policy §3)")

    cat = (order.get("category") or "").lower()
    if cat in NON_REFUNDABLE_CATEGORIES:
        reasons.append(f"Category '{cat}' is non-refundable (Policy §3)")

    days = order.get("delivered_days_ago")
    if days is None:
        reasons.append("Delivery date unknown — cannot verify return window")
    elif days > window:
        reasons.append(
            f"Outside {window}-day window for {tier} tier ({days} days since delivery) (Policy §1)"
        )

    amount = float(order.get("amount") or 0)
    requires_manager = False
    if amount > MANAGER_MAX:
        reasons.append(f"Amount ${amount:.2f} exceeds $500 — must escalate (Policy §5)")
    elif amount > AUTO_APPROVE_MAX:
        requires_manager = True

    approved = len(reasons) == 0 and not requires_manager
    decision = "approve" if approved else ("escalate" if requires_manager and not reasons else "deny")

    return {
        "approved": approved,
        "decision": decision,
        "requires_manager": requires_manager,
        "reasons": reasons,
        "policy_sections_cited": reasons,
        "eligible_window_days": window,
        "order_amount": amount,
        "customer_tier": tier,
        "refunds_remaining": max(0, limit - customer["refunds_ytd"]),
    }


def process_refund(customer_id: str, order_id: str) -> Dict[str, Any]:
    check = check_refund_policy(customer_id, order_id)
    if not check["approved"]:
        return {
            "success": False,
            "message": "Refund blocked by policy",
            "policy_check": check,
        }
    customer, order = _find_customer_and_order(customer_id, order_id)
    refund_id = f"REF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return {
        "success": True,
        "refund_id": refund_id,
        "amount": order["amount"],
        "order_id": order_id,
        "customer_id": customer_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Refund {refund_id} processed for ${order['amount']:.2f}",
    }


def escalate_to_human(customer_id: str, order_id: str, reason: str) -> Dict[str, Any]:
    ticket_id = f"TKT-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    return {
        "success": True,
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "order_id": order_id,
        "reason": reason,
        "message": f"Escalated to human agent. Ticket {ticket_id}",
    }


def get_policy_summary() -> str:
    return _load_policy_text()


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Find customer in CRM by email or customer_id",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "customer_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "Get order details; order must belong to customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["customer_id", "order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_refund_policy",
            "description": "Validate order against strict refund policy BEFORE approving",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "order_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["customer_id", "order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": "Process refund ONLY after check_refund_policy returns approved=true",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["customer_id", "order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate to human for manager approval or complex cases",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "order_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["customer_id", "order_id", "reason"],
            },
        },
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "lookup_customer":
        return lookup_customer(args.get("email", ""), args.get("customer_id", ""))
    if name == "get_order_details":
        return get_order_details(args["customer_id"], args["order_id"])
    if name == "check_refund_policy":
        return check_refund_policy(args["customer_id"], args["order_id"], args.get("reason", ""))
    if name == "process_refund":
        return process_refund(args["customer_id"], args["order_id"])
    if name == "escalate_to_human":
        return escalate_to_human(args["customer_id"], args["order_id"], args.get("reason", ""))
    return {"error": f"Unknown tool: {name}"}
