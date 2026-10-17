"""Deterministic policy unit tests (no LLM)."""

from datetime import datetime, timezone

from django.test import SimpleTestCase, override_settings

from agent.session import SessionState
from agent.tools.mock_api import PaylaneTools
from agent.tools.policy import elapsed_days, evaluate_refund
from agent.tools.store import MockStore

FIXED = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


@override_settings(FIXED_NOW=FIXED)
class PolicyTests(SimpleTestCase):
    def setUp(self):
        self.store = MockStore()
        self.session = SessionState()
        self.tools = PaylaneTools(store=self.store, session=self.session)

    def _verify_alice(self):
        r = self.tools.get_customer("alice@paylane.test", "4242")
        self.assertTrue(r["ok"])
        self.assertTrue(self.session.verified)

    def test_elapsed_days_exactly_30(self):
        age = elapsed_days("2026-09-17T12:00:00Z", now=FIXED)
        self.assertEqual(age, 30.0)

    def test_eligible_refund(self):
        self._verify_alice()
        txn = self.store.get_transaction("txn_ok_50")
        cust = self.store.get_customer_by_id("cust_alice")
        d = evaluate_refund(
            session_verified=True, customer=cust, txn=txn, amount=50.0, now=FIXED
        )
        self.assertTrue(d.allowed)

    def test_exactly_30_days_not_allowed(self):
        txn = self.store.get_transaction("txn_day30")
        cust = self.store.get_customer_by_id("cust_alice")
        d = evaluate_refund(
            session_verified=True, customer=cust, txn=txn, amount=40.0, now=FIXED
        )
        self.assertFalse(d.allowed)
        self.assertTrue(d.should_escalate)
        self.assertEqual(d.reason, "exactly_30_days_escalate")

    def test_issue_refund_blocked_without_verify(self):
        r = self.tools.issue_refund("txn_ok_50", 50.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "identity_not_verified")

    def test_issue_refund_happy_path(self):
        self._verify_alice()
        r = self.tools.issue_refund("txn_ok_50", 50.0)
        self.assertTrue(r["ok"])
        r2 = self.tools.issue_refund("txn_ok_50", 50.0)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reason"], "already_refunded")

    def test_over_amount_escalates_flag(self):
        self._verify_alice()
        r = self.tools.issue_refund("txn_big_120", 120.0)
        self.assertFalse(r["ok"])
        self.assertTrue(r["should_escalate"])

    def test_three_failed_verifications_lock(self):
        for last4 in ("0001", "0002", "0003"):
            self.tools.get_customer("alice@paylane.test", last4)
        self.assertTrue(self.session.locked)
        self.assertTrue(self.session.escalated)
        self.assertFalse(self.session.verified)

    def test_partial_refund_rejected(self):
        self._verify_alice()
        r = self.tools.issue_refund("txn_ok_50", 10.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "partial_or_mismatch_amount_not_allowed")

    def test_pending_rejected(self):
        self._verify_alice()
        r = self.tools.issue_refund("txn_pending", 28.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "pending_cannot_be_refunded")

    def test_unverified_customer_account(self):
        self.tools.get_customer("cara@paylane.test", "9999")
        r = self.tools.issue_refund("txn_cara_40", 40.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "customer_not_verified_for_auto_refund")
