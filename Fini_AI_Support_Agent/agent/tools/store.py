"""In-memory mock Paylane data loaded from seed.json."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from django.conf import settings


class MockStore:
    def __init__(self, seed_path: Path | None = None) -> None:
        path = seed_path or settings.AGENT_SEED_PATH
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.customers: dict[str, dict[str, Any]] = {
            c["email"].lower(): copy.deepcopy(c) for c in raw["customers"]
        }
        self.customers_by_id: dict[str, dict[str, Any]] = {
            c["id"]: self.customers[c["email"].lower()] for c in raw["customers"]
        }
        self.transactions: dict[str, dict[str, Any]] = {
            t["id"]: copy.deepcopy(t) for t in raw["transactions"]
        }
        self._refund_seq = 0
        self._ticket_seq = 0

    def get_customer_by_email(self, email: str) -> dict[str, Any] | None:
        return self.customers.get(email.lower().strip())

    def get_customer_by_id(self, customer_id: str) -> dict[str, Any] | None:
        return self.customers_by_id.get(customer_id)

    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        return self.transactions.get(txn_id)

    def next_refund_id(self) -> str:
        self._refund_seq += 1
        return f"rfnd_{self._refund_seq:04d}"

    def next_ticket_id(self) -> str:
        self._ticket_seq += 1
        return f"tkt_{self._ticket_seq:04d}"
