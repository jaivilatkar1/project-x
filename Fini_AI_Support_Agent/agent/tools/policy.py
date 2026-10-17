"""Deterministic Paylane policy checks. Tools enforce these; the prompt only guides."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.conf import settings


def _parse_date(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def elapsed_days(txn_date: str | datetime, now: datetime | None = None) -> float:
    now = now or settings.FIXED_NOW
    delta = now - _parse_date(txn_date)
    return delta.total_seconds() / 86400.0


@dataclass
class RefundDecision:
    allowed: bool
    reason: str
    should_escalate: bool = False


def evaluate_refund(
    *,
    session_verified: bool,
    customer: dict[str, Any] | None,
    txn: dict[str, Any] | None,
    amount: float,
    now: datetime | None = None,
) -> RefundDecision:
    """Refund only a full settled txn belonging to the verified customer under policy.

    Rules (clarifications):
    - Session identity verified; customer.verified True
    - Full original amount only; settled; never already refunded
    - Amount at most $75; age strictly under 30 elapsed UTC days
    - Exactly 30 days or older → escalate (no auto-refund)
    """

    if not session_verified:
        return RefundDecision(False, "identity_not_verified", should_escalate=False)

    if customer is None:
        return RefundDecision(False, "customer_not_found")

    if not customer.get("verified"):
        return RefundDecision(
            False,
            "customer_not_verified_for_auto_refund",
            should_escalate=True,
        )

    if txn is None:
        return RefundDecision(False, "transaction_not_found")

    if txn.get("customer_id") != customer.get("id"):
        return RefundDecision(False, "transaction_not_owned_by_customer")

    status = txn.get("status")
    if status == "pending":
        return RefundDecision(False, "pending_cannot_be_refunded")
    if status == "refunded":
        return RefundDecision(False, "already_refunded")
    if status != "settled":
        return RefundDecision(False, f"invalid_status:{status}")

    original = float(txn["amount"])
    if abs(amount - original) > 1e-6:
        return RefundDecision(False, "partial_or_mismatch_amount_not_allowed")

    if original > settings.REFUND_MAX_AMOUNT:
        return RefundDecision(False, "amount_over_auto_limit", should_escalate=True)

    age = elapsed_days(txn["date"], now=now)
    max_age = float(settings.REFUND_MAX_AGE_DAYS)
    # Auto-refund only when age < 30. Exactly 30 and older escalate.
    if abs(age - max_age) < 1e-9:
        return RefundDecision(False, "exactly_30_days_escalate", should_escalate=True)
    if age >= max_age:
        return RefundDecision(False, "transaction_too_old", should_escalate=True)

    return RefundDecision(True, "eligible")


def should_auto_lock(failed_verifications: int) -> bool:
    return failed_verifications >= settings.MAX_FAILED_VERIFICATIONS
