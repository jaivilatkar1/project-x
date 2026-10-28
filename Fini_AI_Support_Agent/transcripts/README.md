# Conversation transcripts — how to select the right set

| Folder | Meaning | LLM? |
|--------|---------|------|
| **[`azure/`](azure/)** | **The 12 live model-run conversations** Deep asked for | Yes — Azure · gpt-4o-mini |
| **[`deterministic/`](deterministic/)** | Offline harness using the **same tools/policy** | No — rule-based |

## Reviewers: start here for model runs

→ **[`azure/INDEX.md`](azure/INDEX.md)**  
→ Twelve JSON files: `azure/01_…json` … `azure/12_….json`

Each Azure file has `"mode": "azure"` and either:

- `"source": "azure_eval_api"` — raw tool-calling dump from `run_eval --mode azure`, or  
- `"source": "live_azure_ui_capture"` — dialogue from the original live Web UI runs (paired with `docs/screenshots/`).

## Regenerating

```bash
python manage.py run_eval --mode deterministic   # writes transcripts/deterministic/
python manage.py run_eval --mode azure           # writes transcripts/azure/ (needs .env)
```
