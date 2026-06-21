# ShopFlow AI Refund Agent — Workpodd Demo

Standalone vertical slice for the **Workpodd AI Customer Support Agent** challenge: an LLM-powered refund agent with CRM mock data, strict policy validation, customer chat UI, voice input, and admin reasoning logs.

## Folder structure

```
workpodd_refund_demo/
├── README.md
├── requirements.txt           # Python dependencies for the demo
├── .env.example               # Environment variable template (copy to .env)
├── data/
│   ├── crm_profiles.json      # 15 customer profiles + orders
│   └── refund_policy.md       # Strict refund policy document
├── backend/
│   ├── agent.py               # Tool-calling agent loop
│   ├── tools.py               # CRM + policy tools
│   ├── llm_client.py          # Azure/OpenAI client
│   ├── message_parser.py      # Email / order ID extraction
│   ├── voice_service.py       # STT, TTS, Realtime voice
│   ├── reasoning_log.py       # In-memory admin logs + SSE
│   ├── views.py               # Django API + static UI
│   ├── urls.py                # API routes
│   └── ui_urls.py             # Frontend routes
└── frontend/
    ├── index.html
    ├── styles.css
    ├── app.js
    └── voice-realtime.js
```

---

## Prerequisites

- **Python 3.10+**
- **Azure OpenAI** or **OpenAI** API access (for the LLM agent)
- **Chrome or Edge** (recommended for browser voice input)
- This demo runs inside the **Django backend** (`manage.py` at repo root). Routes are wired in `ml_backend/urls.py`.

---

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <backend-repo-root>   # folder containing manage.py
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

Install demo dependencies:

```bash
pip install -r workpodd_refund_demo/requirements.txt
```

If you are running the full NexaCLM backend, install the main `requirements.txt` instead — it includes everything above.

---

## Environment setup

### 1. Copy the template

```bash
cp workpodd_refund_demo/.env.example .env
```

Place `.env` in the **backend repo root** (same folder as `manage.py`). Do **not** commit `.env` to GitHub.

### 2. Fill in required variables (minimum)

| Variable | Description | Example |
|----------|-------------|---------|
| `env_type` | Must be `NexaByte` for Azure | `NexaByte` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | From Azure portal → Keys |
| `LE_OPENAI_BASE` | Azure OpenAI endpoint URL | `https://your-resource.openai.azure.com` |
| `LE_OPENAI_GPT4_TURBO` | **Deployment name** for chat (not model id) | `gpt-4` |

**Or** use direct OpenAI instead of Azure:

| Variable | Description |
|----------|-------------|
| `LE_OPEN_AI_KEY` | OpenAI API key (`sk-...`) |

### 3. Optional voice variables

| Variable | Purpose |
|----------|---------|
| `AZURE_OPENAI_TTS_DEPLOYMENT` | Spoken agent replies (e.g. `tts-hd`) |
| `AZURE_OPENAI_TTS_BASE` | TTS endpoint if deployed in a **different Azure region** |
| `AZURE_OPENAI_TTS_API_KEY` | API key for that regional TTS resource |
| `AZURE_OPENAI_TTS_API_VERSION` | e.g. `2024-03-01-preview` |
| `AZURE_OPENAI_WHISPER_DEPLOYMENT` | Server-side Whisper STT (optional) |
| `AZURE_OPENAI_REALTIME_DEPLOYMENT` | Live WebRTC voice (optional) |

> **Note:** TTS is often deployed in a different Azure region (e.g. North Central US) than chat (e.g. South India). Set `AZURE_OPENAI_TTS_BASE` and `AZURE_OPENAI_TTS_API_KEY` from that resource’s portal page. Browser push-to-talk works without Whisper.

See `.env.example` for the full list with comments.

---

## Run the demo

From the backend repo root:

```bash
source venv/bin/activate
python manage.py runserver 8000
```

Open in your browser:

| What | URL |
|------|-----|
| **Demo UI** | http://localhost:8000/workpodd-demo/ |
| **API base** | http://localhost:8000/api/v1/workpodd-demo/ |
| **Health check** | http://localhost:8000/api/v1/workpodd-demo/health |
| **Voice config** | http://localhost:8000/api/v1/workpodd-demo/voice/capabilities |

---

## How to use the UI

The screen has two panels: **Customer chat** (left) and **Admin — Agent reasoning** (right).

### Text chat

1. **Set customer email** in the top field, or pick a customer from the **Quick demo customer** dropdown.
2. Type a refund request in the message box and press **Send** (or use a **hint chip**).
3. Watch the **reasoning panel** on the right — it shows each tool call, result, and final decision in real time.
4. The agent replies in the chat when done.

**Example (approve):**

- Customer: **Alice Chen** — `alice.chen@email.com`
- Message: `I'd like a refund for order ORD-5001. The headphones are defective.`

**Example (deny):**

- Customer: **Bob Martinez** — `bob.m@email.com`
- Message: `I need a refund for my recent order.`

### Voice (hold to talk)

1. Set the **email** field first (important — prevents bad speech-to-text from breaking lookup).
2. Optionally check **Speak agent reply (TTS)** to hear the agent’s response.
3. **Hold** the **Hold to talk** button, speak, then **release**.
4. Your words appear as a user message; the agent responds automatically.
5. Status line shows `Heard (browser): "..."` or `Heard (Whisper): "..."`.

Use **Chrome or Edge** for best browser speech recognition.

### Admin reasoning panel

- Updates live via **Server-Sent Events (SSE)** during each conversation.
- Entry types: `thought`, `tool_call`, `tool_result`, `decision`, `error`.
- Use this to demo **how the agent thinks** and **which tools it calls** before approving or denying.

---

## Demo scenarios (15 CRM profiles)

| Customer | Email | Scenario |
|----------|-------|----------|
| Alice Chen | alice.chen@email.com | Approve ORD-5001 ($129, premium, within window) |
| Bob Martinez | bob.m@email.com | Deny — refund limit reached |
| Emma Thompson | emma.t@email.com | Deny — digital ebook downloaded |
| David Kim | david.kim@email.com | Deny — flagged account |
| Frank O'Brien | frank.ob@email.com | Deny — final sale item |
| Henry Davis | henry.d@email.com | Deny — amount > $500 |
| Ivy Patel | ivy.patel@email.com | Deny — outside premium return window |

Use the **customer dropdown** or **hint chips** for one-click test messages.

---

## Voice pipeline (bonus)

| Mode | How | Requirements |
|------|-----|--------------|
| **Hold to talk** | Record → STT → agent → optional TTS | Browser STT (Chrome) **or** Azure Whisper |
| **Speak agent reply** | TTS plays MP3 after agent responds | `AZURE_OPENAI_TTS_*` or `LE_OPEN_AI_KEY` |
| **Live voice (Realtime)** | WebRTC live call with tool calling | `AZURE_OPENAI_REALTIME_DEPLOYMENT` or `LE_OPEN_AI_KEY` |

If Realtime is not configured, the **Live voice** button is disabled in the UI.

---

## Architecture

```
Customer UI ──POST /chat──► Agent loop (OpenAI tools)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              lookup_customer  check_policy  process_refund
                    │           │           │
                    └───────────┴───────────┘
                                │
                    Reasoning log (SSE) ──► Admin panel
```

### Agent tools

1. `lookup_customer` — CRM lookup by email or ID  
2. `get_order_details` — Order must belong to customer  
3. `check_refund_policy` — **Required** before any approval (deterministic rules in code)  
4. `process_refund` — Only when policy returns `approved: true`  
5. `escalate_to_human` — Manager approval / edge cases  

The LLM orchestrates the conversation; **policy enforcement lives in `tools.py`**, not in free-form model output.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/workpodd-demo/health` | Health check |
| GET | `/api/v1/workpodd-demo/customers` | List demo CRM profiles |
| GET | `/api/v1/workpodd-demo/policy` | Refund policy text |
| POST | `/api/v1/workpodd-demo/chat` | `{ message, session_id?, customer_email? }` |
| GET | `/api/v1/workpodd-demo/voice/capabilities` | Which voice backends are configured |
| POST | `/api/v1/workpodd-demo/voice/chat` | Audio or `{ transcript }` → agent + optional TTS |
| POST | `/api/v1/workpodd-demo/voice/speak` | `{ text }` → MP3 |
| POST | `/api/v1/workpodd-demo/voice/realtime-session` | Ephemeral token for WebRTC |
| POST | `/api/v1/workpodd-demo/voice/execute-tool` | Run CRM tool from Realtime client |
| GET | `/api/v1/workpodd-demo/logs` | All sessions |
| GET | `/api/v1/workpodd-demo/logs/{id}` | Session reasoning log |
| GET | `/api/v1/workpodd-demo/logs/{id}/stream` | SSE reasoning stream |

### Example: chat API

```bash
curl -X POST http://localhost:8000/api/v1/workpodd-demo/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Refund order ORD-5001, product is defective",
    "customer_email": "alice.chen@email.com"
  }'
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `DeploymentNotFound` on chat | Set `LE_OPENAI_GPT4_TURBO` (or `AZURE_OPENAI_GPT4O`) to your **exact Azure deployment name** |
| TTS not working | Set `AZURE_OPENAI_TTS_DEPLOYMENT`, `AZURE_OPENAI_TTS_BASE`, `AZURE_OPENAI_TTS_API_KEY`; restart server |
| Voice shows `(browser)` only | Normal if Whisper is not deployed; browser STT still works in Chrome |
| Live voice disabled | Realtime not configured — optional for the demo |
| Reasoning panel empty | Send a message first; panel fills when a session starts |
| Sessions reset on restart | Expected — in-memory store for demo only |

---

## Video walkthrough checklist (7–10 min)

1. **Standard refund** — Alice + ORD-5001 → approval + reasoning log tool chain  
2. **Policy violation** — Bob or Emma → agent denies with policy reason  
3. **Voice** — Hold 🎤 and speak a refund request  
4. **Code tour** — `agent.py`, `tools.py`, `reasoning_log.py`, `voice_service.py`  
5. **Admin panel** — Live `tool_call` / `tool_result` / `decision` entries  

---

## Notes

- In-memory sessions reset on server restart (fine for demo).  
- No auth required on demo routes (`AllowAny`).  
- Commit `.env.example` to GitHub; never commit `.env` with real keys.  
- For Workpodd submission: include **GitHub repo link**, **README**, and **Loom / Google Drive video**.

---

Built as a Workpodd careers vertical slice demo.
