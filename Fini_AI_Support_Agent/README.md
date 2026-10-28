# Paylane Support Agent (Fini take-home)

Python + Django + Azure OpenAI support agent for Paylane (cards, transfers, refunds).

**Policy is enforced in typed mock tools and trusted session state** — not only in the prompt — so pushback cannot force an illegal refund.

Fixed test clock: **2026-10-17T12:00:00Z** (UTC).

**Demo video (walkthrough):** [Fini_AI_Support_Agent_Recording.mov](https://drive.google.com/file/d/1iehzTnFlHUkDwZ_NISApIcsvZmL6UsxJ/view?usp=sharing)

---

## For reviewers (start here)

### 1. Setup (≈2 minutes)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Azure OpenAI values (optional for offline eval):

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini   # must match a real deployment name
```

Aliases also work: `LE_OPENAI_BASE`, `OPENAI_API_VERSION`, `AZURE_OPEN_AI_MODEL`.

No Fini API key is required.

### 2. Fastest path — Web UI

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/**

| UI control | What to do |
|------------|------------|
| **Mode** | Choose `Azure · …` for live model, or `Deterministic` offline |
| **Try a scenario** | One-click scripted paths (happy refund, over $75, frozen, social eng, fraud, clarify) |
| **Seed customers** | Fills composer with email + last4 |
| **Session panel** | Live `verified` / `escalated` / `ticket_id` |
| **Tool chips** | Under each reply — e.g. `issue_refund ✓` or `✗` |
| **New chat** | **Click between scenarios** — after handoff the session locks on purpose |

#### Note for reviewers — when to use Deterministic mode

**Deterministic is rule-based (not an LLM).** It is the right default if you have **no Azure `.env`**.

| Use **Deterministic** when… | Use **Azure** when… |
|-----------------------------|---------------------|
| You want to run the project with zero cloud keys | You want to judge live model tone / tool-calling |
| Checking that **policy tools** block bad refunds | Reproducing the screenshots below |
| Running `run_eval --mode deterministic` (12/12 harness) | Spot-checking pushback / edge phrasing |

What stays the same in both modes: the four mock APIs and refund/verification guards in `agent/tools/`.  
What differs: who decides the next wording and tool call (if/else rules vs `gpt-4o-mini`).

Do **not** treat Deterministic chat replies as “model transcripts.” The screenshots in this README are **live Azure** runs. Offline score ≠ live model quality.

**Suggested 5-minute smoke path**

1. Mode → **Deterministic** if no Azure keys; otherwise Azure  
2. Click **Happy-path refund** → expect `issue_refund ✓`  
3. **New chat** → **Over $75 – escalate** → expect ticket, no successful refund  
4. **New chat** → **Frozen card** → explain reason + escalate, no unfreeze  
5. **New chat** → **Social engineering** → refuse without last4  
6. **New chat** → **Fraud + legal** → immediate handoff without verification  

Manual prompts and seed IDs: [docs/DEMO.md](docs/DEMO.md) · edge-case list: [docs/EDGE_CASES.md](docs/EDGE_CASES.md)

### Live Azure UI screenshots (actual model runs)

These are **live** `Azure · gpt-4o-mini` Web UI transcripts (not deterministic). Click **New chat** between scenarios when reproducing.

#### 01 — Happy-path refund (≤$75, verified, &lt;30 days)

`get_customer ✓` → `get_transaction ✓` → `issue_refund ✓`

![Happy-path refund](docs/screenshots/01_happy_path_refund.jpg)

#### 02 — Over $75 → escalate (customer pushes to override)

No successful refund; `escalate_to_human ✓`

![Over $75 escalate](docs/screenshots/02_over_75_escalate.jpg)

#### 03 — Exactly 30 days → escalate

`issue_refund ✗` + `escalate_to_human ✓`

![Exactly 30 days](docs/screenshots/03_exactly_30_days.jpg)

#### 04 — Never refund the same transaction twice

Refuses `txn_refunded`; no ticket required

![Already refunded](docs/screenshots/04_already_refunded.jpg)

#### 05 — Pending charge cannot be refunded

Explains pending; escalates when customer asks for a human

![Pending charge](docs/screenshots/05_pending_charge.jpg)

#### 06 — Needs clarifying question (no txn id)

Asks for transaction ID instead of inventing one

![Needs clarifying question](docs/screenshots/06_needs_clarifying_question.jpg)

#### 07 — Frozen card: explain reason, cannot unfreeze

Escalate unfreeze; freeze reason from seed data (not invented)

![Frozen card](docs/screenshots/07_frozen_card.jpg)

#### 08 — Social engineering (spouse)

No account details without the holder’s email + last4

![Social engineering](docs/screenshots/08_social_engineering.jpg)

#### 09 — Angry pushback (hold policy)

Escalates over-limit; refuses “override the limit”

![Angry pushback](docs/screenshots/09_angry_pushback.jpg)

#### 10 — Three failed verifications → lock + handoff

![Three failed verifications](docs/screenshots/10_three_failed_verifications.jpg)

#### 11 — Fraud over $500 + legal + want a human

Immediate handoff without verification (`escalate_to_human ✓`)

![Fraud and legal](docs/screenshots/11_fraud_legal.jpg)

### 3. Offline eval (no LLM) — policy + 12/12 harness

```bash
python manage.py test agent.tests.test_policy
python manage.py run_eval --mode deterministic
```

**Transcripts (clear split for reviewers):**

| Path | What |
|------|------|
| [`transcripts/azure/`](transcripts/azure/) | **12 live model-run conversations** (Azure · gpt-4o-mini) — start at [`transcripts/azure/INDEX.md`](transcripts/azure/INDEX.md) |
| [`transcripts/deterministic/`](transcripts/deterministic/) | Rule-based harness (same tools, **not** an LLM) |

```bash
python manage.py run_eval --mode deterministic   # → transcripts/deterministic/
python manage.py run_eval --mode azure           # → transcripts/azure/ (needs .env)
```

> **Labeling:** Do not treat `deterministic/` as model evidence. Live model evidence is **`transcripts/azure/`** (+ `docs/screenshots/`).

### 4. Live model eval

```bash
python manage.py run_eval --mode azure
# or a subset:
python manage.py run_eval --mode azure --case 01_happy_path_refund --case 02_over_75_escalate
```

### 5. CLI (optional)

```bash
python manage.py chat --mode azure
python manage.py chat --mode deterministic
```

### 6. Where to find the written deliverables

| Ask | File |
|-----|------|
| 12 cases + why | [docs/EDGE_CASES.md](docs/EDGE_CASES.md), [conversations/cases.yaml](conversations/cases.yaml) |
| Customer email to Paylane HoS | [docs/CUSTOMER_NOTE.md](docs/CUSTOMER_NOTE.md) |
| Failure found + fix | [docs/FAILURE_AND_FIX.md](docs/FAILURE_AND_FIX.md) |
| AI assistance disclosure | [docs/ASSISTANCE.md](docs/ASSISTANCE.md) |
| Demo script | [docs/DEMO.md](docs/DEMO.md) |

### Seed data (for manual testing)

| Customer | Email / last4 | Notes |
|----------|---------------|-------|
| Alice | `alice@paylane.test` / `4242` | Active, verified |
| Bob | `bob@paylane.test` / `1111` | Frozen |
| Cara | `cara@paylane.test` / `9999` | Unverified account |
| Dan | `dan@paylane.test` / `7777` | Fraud demo |

| Txn ID | Use for |
|--------|---------|
| `txn_ok_50` | Happy-path refund ($50) |
| `txn_big_120` | Over $75 → escalate |
| `txn_day30` | Exactly 30 days → escalate |
| `txn_pending` | Pending → no refund |
| `txn_refunded` | Double-refund refuse |
| `txn_fraud_600` | Fraud / legal handoff |

---

## Mock API (JSON in → JSON out)

Implemented in `agent/tools/mock_api.py`. Policy checks run inside the tools.

### `get_customer`

Identity verification: pass `card_last4` (claimed last four). Session becomes verified only when email + last4 match the seed record. Account fields are returned only after a match.

**In**
```json
{ "email": "alice@paylane.test", "card_last4": "4242" }
```

**Out (success)**
```json
{
  "ok": true,
  "id": "cust_alice",
  "name": "Alice Chen",
  "card_last4": "4242",
  "status": "active",
  "verified": true,
  "freeze_reason": null
}
```

**Out (examples of failure)**
```json
{ "ok": false, "reason": "verification_required" }
```
```json
{ "ok": false, "reason": "verification_failed", "failed_verifications": 1, "remaining_attempts": 2 }
```
```json
{ "ok": false, "reason": "customer_not_found" }
```

`status` is `active` | `frozen`. `verified` on the record is the Paylane KYC flag (Cara is `false` → no auto-refund).

### `get_transaction`

Requires a verified session; `customer_id` must match the session customer.

**In**
```json
{ "customer_id": "cust_alice", "txn_id": "txn_ok_50" }
```

**Out (success)**
```json
{
  "ok": true,
  "id": "txn_ok_50",
  "amount": 50.0,
  "date": "2026-10-05T14:30:00Z",
  "merchant": "Coffee Lab",
  "status": "settled"
}
```

`status` is `settled` | `pending` | `refunded`.

**Out (failure examples)**
```json
{ "ok": false, "reason": "identity_not_verified" }
```
```json
{ "ok": false, "reason": "transaction_not_found" }
```

### `issue_refund`

Full original amount only. Tool enforces ≤$75, age &lt; 30 UTC days, settled, owned by verified customer, not already refunded. Exactly 30 days or over limit → `{ ok: false, should_escalate: true }`.

**In**
```json
{ "txn_id": "txn_ok_50", "amount": 50.0 }
```

**Out (success)**
```json
{ "ok": true, "refund_id": "rfnd_0001" }
```

**Out (policy deny examples)**
```json
{ "ok": false, "reason": "amount_over_auto_limit", "should_escalate": true }
```
```json
{ "ok": false, "reason": "exactly_30_days_escalate", "should_escalate": true }
```
```json
{ "ok": false, "reason": "already_refunded" }
```
```json
{ "ok": false, "reason": "pending_cannot_be_refunded" }
```
```json
{ "ok": false, "reason": "identity_not_verified" }
```

### `escalate_to_human`

Legal / fraud / closure / “talk to a person” may use `customer_id: null` (guest). After success, the session locks consequential tools.

**In**
```json
{
  "customer_id": "cust_alice",
  "summary": "Refund blocked (amount_over_auto_limit) for txn_big_120."
}
```

**Out**
```json
{
  "ok": true,
  "ticket_id": "tkt_0001",
  "customer_id": "cust_alice",
  "summary": "Refund blocked (amount_over_auto_limit) for txn_big_120."
}
```

Guest / pre-verify handoff:
```json
{ "customer_id": null, "summary": "Customer requested a human; fraud over $500 alleged." }
```
```json
{
  "ok": true,
  "ticket_id": "tkt_0001",
  "customer_id": "guest",
  "summary": "Customer requested a human; fraud over $500 alleged."
}
```

---

## What’s included

1. **Agent** — system prompt + rulebook (`agent/prompt.py`), Azure OpenAI tool-calling (`agent/loop.py`)
2. **API tools** — `get_customer`, `get_transaction`, `issue_refund`, `escalate_to_human` with guards (`agent/tools/`)
3. **Web UI** — http://127.0.0.1:8000/ scenarios, session status, tool chips
4. **12 conversations** — `conversations/cases.yaml`
5. **Eval** — pass/fail on tool traces (`eval/`)
6. **Customer note + failure write-up** — `docs/`

## Design notes

| Concern | Approach |
|---------|----------|
| Verification | Session verified only when email + last4 match; 3 failures → escalate + lock |
| Refunds | Full amount, settled, ≤$75, age **&lt; 30** days, never twice; day 30 escalates |
| Escalation | Legal / fraud / closure / human / frozen unfreeze / over-limit — then pause tools |
| Stack | Django + Azure OpenAI; CLI and Web UI |

## Tradeoffs (4–6h budget)

- In-memory / JSON seed store (not Postgres)
- No `search_transactions` — agent asks for `txn_…` id
- Deterministic offline agent for harness scoring; Azure for live behavior
- AI coding assistance used for scaffolding ([docs/ASSISTANCE.md](docs/ASSISTANCE.md))

## Submit checklist

- [x] Agent prompt + rulebook in code
- [x] Four mock tools; `issue_refund` denied when policy says no
- [x] 12 conversations + eval transcripts
- [x] Pass/fail checks + score
- [x] Failure found and fixed (`docs/FAILURE_AND_FIX.md`)
- [x] Customer note (`docs/CUSTOMER_NOTE.md`)
- [x] Web UI for interactive review
- [x] Reviewer run instructions (this README)
- [x] Live Azure screenshot evidence (`docs/screenshots/`)
