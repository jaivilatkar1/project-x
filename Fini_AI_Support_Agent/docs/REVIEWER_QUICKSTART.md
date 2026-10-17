# Reviewer quickstart (1 page)

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add Azure keys only if you want live model
python manage.py runserver
```

→ **http://127.0.0.1:8000/**

### Deterministic mode (use this without Azure)

- **What it is:** a rule-based agent (not an LLM) that still calls the **same** policy-enforced mock tools.
- **When to use it:** no `.env` keys, fast smoke test, `run_eval --mode deterministic`.
- **When not to:** judging live model tone — switch Mode to **Azure** (needs your own deployment).
- **Same in both modes:** refund/verify/escalate guards cannot be bypassed by chat wording.

Set the UI Mode dropdown to **Deterministic** if you did not configure Azure.

## Important

Click **New chat** between scenarios. After escalate/handoff the session locks on purpose.

## Map to the brief

| Brief rule | Try |
|------------|-----|
| Refund ≤$75, &lt;30d, verified | Scenario: Happy-path refund |
| Above $75 / pushback | Over $75 – escalate |
| Exactly 30 days | New chat → verify Alice → `Refund txn_day30` |
| Never twice | verify Alice → `Refund txn_refunded again` |
| Pending | verify Alice → `Please refund txn_pending` |
| Frozen / no unfreeze | Frozen card |
| Social engineering | Social engineering |
| Fraud / legal / human | Fraud + legal |
| Missing txn id | Needs clarifying question |
| 3 failed checks | New chat → last4 `0001`, `0002`, `0003` |

## Offline score

```bash
python manage.py run_eval --mode deterministic
```

See `transcripts/eval_report.json`.

## Written answers

- Edge cases chosen: `docs/EDGE_CASES.md`
- Email to Paylane HoS: `docs/CUSTOMER_NOTE.md`
- Failure + fix: `docs/FAILURE_AND_FIX.md`
