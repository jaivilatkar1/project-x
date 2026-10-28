# Live Azure model conversations (12/12)

These are **actual model-run** conversations (Azure · gpt-4o-mini), **not** deterministic harness output.

| Case | File | Screenshot |
|------|------|------------|
| 01_happy_path_refund | `01_happy_path_refund.json` | `docs/screenshots/01_happy_path_refund.jpg` |
| 02_over_75_escalate | `02_over_75_escalate.json` | `docs/screenshots/02_over_75_escalate.jpg` |
| 03_exactly_30_days | `03_exactly_30_days.json` | `docs/screenshots/03_exactly_30_days.jpg` |
| 04_already_refunded | `04_already_refunded.json` | `docs/screenshots/04_already_refunded.jpg` |
| 05_pending_charge | `05_pending_charge.json` | `docs/screenshots/05_pending_charge.jpg` |
| 06_three_failed_verifications | `06_three_failed_verifications.json` | `docs/screenshots/10_three_failed_verifications.jpg` |
| 07_pii_probe | `07_pii_probe.json` | — (UI capture in JSON) |
| 08_frozen_unfreeze | `08_frozen_unfreeze.json` | `docs/screenshots/07_frozen_card.jpg` |
| 09_angry_pushback | `09_angry_pushback.json` | `docs/screenshots/09_angry_pushback.jpg` |
| 10_social_engineering | `10_social_engineering.json` | `docs/screenshots/08_social_engineering.jpg` |
| 11_needs_clarifying_question | `11_needs_clarifying_question.json` | `docs/screenshots/06_needs_clarifying_question.jpg` |
| 12_legal_and_fraud | `12_legal_and_fraud.json` | `docs/screenshots/11_fraud_legal.jpg` |

**Field `mode`:** always `"azure"`.  
**Field `source`:** `azure_eval_api` (case 01 API dump) or `live_azure_ui_capture` (UI dialogue from original work).

Deterministic counterparts (rule-based, not an LLM): [`../deterministic/`](../deterministic/).
