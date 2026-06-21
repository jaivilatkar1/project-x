"""Extract email and order IDs from chat/voice transcripts."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .tools import load_crm

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Spoken email: "alice dot chen at email dot com"
SPOKEN_EMAIL_RE = re.compile(
    r"([a-z0-9]+(?:\s+dot\s+[a-z0-9]+)+)\s+at\s+([a-z0-9]+(?:\s+dot\s+[a-z0-9]+)+)",
    re.IGNORECASE,
)
ORDER_NUM_RE = re.compile(r"(?i)(?:order\s+)?(?:ord(?:er)?|od)[\s-]*0*(\d{4,5})")


def _known_orders() -> set:
    ids = set()
    for c in load_crm().get("customers", []):
        for o in c.get("orders", []):
            ids.add(o["order_id"].upper())
    return ids


def _normalize_spoken_email(text: str) -> Optional[str]:
    m = SPOKEN_EMAIL_RE.search(text.lower())
    if not m:
        return None
    local = m.group(1).replace(" dot ", ".").replace(" ", "")
    domain = m.group(2).replace(" dot ", ".").replace(" ", "")
    return f"{local}@{domain}"


def extract_order_id(text: str) -> Optional[str]:
    known = _known_orders()
    upper = text.upper()
    for oid in sorted(known, key=len, reverse=True):
        if oid in upper:
            return oid
        compact = oid.replace("-", "")
        if compact in upper.replace(" ", "").replace("-", ""):
            return oid

    digit_runs = re.findall(r"\d{4,6}", text)
    for oid in known:
        num = oid.split("-")[-1]
        for d in digit_runs:
            if d == num:
                return oid
            # STT often outputs 50001 for ORD-5001 (extra zero)
            if len(d) == 5 and len(num) == 4:
                collapsed = d[:3] + d[4:]
                if collapsed == num:
                    return oid

    for m in re.finditer(r"\d{4,6}", text):
        digits = m.group(0)
        candidates = {f"ORD-{digits}", f"ORD-{digits[-4:]}"}
        if len(digits) == 5 and digits.startswith("0"):
            candidates.add(f"ORD-{digits[1:]}")
        if len(digits) == 5 and digits.endswith("1") and digits[:4].isdigit():
            candidates.add(f"ORD-{digits[:4]}")
        for c in candidates:
            if c.upper() in known:
                return c.upper()
        for oid in known:
            if oid.endswith(digits[-4:]):
                return oid

    for m in ORDER_NUM_RE.finditer(text):
        digits = m.group(1)
        candidate = f"ORD-{digits[-4:]}" if len(digits) >= 4 else f"ORD-{digits}"
        if candidate.upper() in known:
            return candidate.upper()
    return None


def extract_email(text: str, fallback: str = "") -> str:
    m = EMAIL_RE.search(text)
    if m:
        return m.group(0).lower()
    spoken = _normalize_spoken_email(text)
    if spoken:
        return spoken.lower()
    return (fallback or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.fullmatch(email.strip()))


def parse_message(text: str, ui_email: str = "") -> Dict[str, Any]:
    """Parse user message; UI email field takes priority when set."""
    email = (ui_email or "").strip().lower() or extract_email(text)
    order_id = extract_order_id(text)
    enriched = text.strip()
    hints = []
    if email and email not in text.lower():
        hints.append(f"customer_email={email}")
    if order_id and order_id not in text.upper():
        hints.append(f"order_id={order_id}")
    if hints:
        enriched = f"{text.strip()}\n[System parsed: {', '.join(hints)}]"
    return {
        "raw": text.strip(),
        "enriched": enriched,
        "email": email,
        "order_id": order_id,
    }
