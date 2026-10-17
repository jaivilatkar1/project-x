"""Run conversation cases through the agent and score them."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from django.conf import settings

from agent.loop import Mode, SupportAgent
from agent.tools.store import MockStore
from eval.checks import CheckResult, evaluate_case

ModeName = Literal["azure", "deterministic"]


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or settings.CONVERSATIONS_PATH
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["cases"]


def run_case(case: dict[str, Any], mode: ModeName) -> tuple[Any, CheckResult]:
    store = MockStore()  # fresh data per case
    agent = SupportAgent(mode=mode, store=store)
    result = agent.run_user_turns(case["messages"])
    check = evaluate_case(case, result)
    return result, check


def save_transcript(
    case: dict[str, Any],
    result: Any,
    check: CheckResult,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{case['id']}.json"
    payload = {
        "case_id": case["id"],
        "title": case.get("title"),
        "why": case.get("why"),
        "mode": result.mode,
        "messages_user": case["messages"],
        "transcript": result.messages,
        "session": result.session.to_dict(),
        "final_text": result.final_text,
        "eval": {
            "passed": check.passed,
            "failures": check.failures,
            "notes": check.notes,
        },
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_all(
    mode: ModeName = "deterministic",
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    cases = load_cases()
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]

    checks: list[CheckResult] = []
    transcript_paths: list[str] = []

    for case in cases:
        result, check = run_case(case, mode=mode)
        path = save_transcript(case, result, check, settings.TRANSCRIPTS_DIR)
        transcript_paths.append(str(path))
        checks.append(check)

    passed = sum(1 for c in checks if c.passed)
    report = {
        "mode": mode,
        "score": f"{passed}/{len(checks)}",
        "passed": passed,
        "total": len(checks),
        "results": [
            {
                "case_id": c.case_id,
                "passed": c.passed,
                "failures": c.failures,
                "notes": c.notes,
            }
            for c in checks
        ],
        "transcripts": transcript_paths,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "mode=deterministic uses the offline rule-based agent with the same "
            "policy-enforced tools. mode=azure uses live Azure OpenAI transcripts."
        ),
    }
    settings.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.EVAL_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
