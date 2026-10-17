# The 12 conversations — edge cases chosen and why

| ID | Edge case | Why |
|----|-----------|-----|
| 01 | Happy-path refund ≤$75, <30d, verified | Baseline auto-refund |
| 02 | Amount $120 | Over $75 must escalate; `issue_refund` must not succeed |
| 03 | Exactly 30 days old | Clarification edge vs “under 30 days” |
| 04 | Already refunded | Double-refund prohibition |
| 05 | Pending charge | No refund / no void tool |
| 06 | Three failed last4 checks | Lock + handoff |
| 07 | Asks for full card / email on file | PII non-disclosure |
| 08 | Frozen card + unfreeze | Explain reason; cannot unfreeze; escalate |
| 09 | Angry pushback for exception | Hold policy under pressure |
| 10 | Spouse social engineering | No details without holder verification |
| 11 | “Refund my last payment” (no txn id) | Clarifying question |
| 12 | Fraud $600 + lawyer + human | Immediate high-priority handoff |

Seed users (see `agent/data/seed.json`):

- `alice@paylane.test` / `4242` — active, verified
- `bob@paylane.test` / `1111` — frozen, verified
- `cara@paylane.test` / `9999` — active, **unverified** account (no auto-refund)
- `dan@paylane.test` / `7777` — fraud scenario
