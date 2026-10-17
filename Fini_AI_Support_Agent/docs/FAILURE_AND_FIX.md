# Failure found in eval — and the fix

## Failure

**Case:** `03_exactly_30_days` (transaction dated exactly 30 elapsed days before the fixed clock).

**Symptom (first policy draft):** `evaluate_refund` used `age <= 30` as eligible (“under 30 days” misread as inclusive). The tool returned `{ok: true}` for `txn_day30`, and the agent could auto-refund a charge that the clarifications say must escalate.

**Score impact:** Conversation 03 failed the check `issue_refund_ok: false` / missing escalate.

## Fix

1. **Policy (source of truth):** Auto-refund only when `age < 30`. If `age == 30` exactly → `exactly_30_days_escalate` with `should_escalate=True`. If `age > 30` → `transaction_too_old`.
2. **Prompt:** Explicit line that exactly 30 days escalates; do not call `issue_refund` when the tool says no.
3. **Unit test:** `test_exactly_30_days_not_allowed` locks the clock at `2026-10-17T12:00:00Z` against `2026-09-17T12:00:00Z`.

## Secondary fix (deterministic runner)

Single-turn messages that both verify and request a refund (`02_over_75_escalate`, `08_frozen_unfreeze`) initially stopped after verification. The offline agent now falls through to action handling in the same turn so evals match multi-intent user messages.

## How to re-check

```bash
python manage.py test agent.tests.test_policy
python manage.py run_eval --mode deterministic
```
