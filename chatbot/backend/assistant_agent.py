"""
Cost-effective tool planner for Contract Intelligence Assistant.

Rules plan first (no LLM). Optional LLM planner only when rules return no tools.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from assistantService.data.user_data import PROMPTS
from assistantService.services.assistant_tools import AssistantTools
from assistantService.services.llm_service import LLMService

logger = logging.getLogger(__name__)

SUMMARY_RAG_QUERY = (
    "parties payment termination confidentiality liability renewal "
    "governing law obligations"
)

# Names must match assistant_planner prompt + AssistantTools methods.
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "search_contract": {
        "description": "Search contract text via RAG",
        "method": "search_contract",
        "need_file_id": True,
        "takes_question": True,
    },
    "search_risks": {
        "description": "Search risk / onboarding analysis",
        "method": "search_risks",
        "need_file_id": True,
        "takes_question": False,
    },
    "search_playbook_gaps": {
        "description": "Search playbook gap analysis",
        "method": "search_playbook_gaps",
        "need_file_id": True,
        "takes_question": False,
    },
    "search_clause_library": {
        "description": "Search / draft from clause library",
        "method": "search_clause_library",
        "need_file_id": False,
        "takes_question": True,
    },
    "product_help": {
        "description": "clm product how-to",
        "method": "product_help",
        "need_file_id": False,
        "takes_question": True,
    },
    "workflow_next": {
        "description": "Workflow / approval next steps",
        "method": "workflow_next",
        "need_file_id": True,
        "takes_question": False,
    },
    "support_contact": {
        "description": "Support contact information",
        "method": "support_contact",
        "need_file_id": False,
        "takes_question": True,
    },
    "extract_redlines": {
        "description": "Extract existing tracked changes in the contract",
        "method": "extract_redlines",
        "need_file_id": True,
        "takes_question": False,
    },
    "suggest_redlines": {
        "description": "AI-propose redlines from contract/playbook (works on PDF)",
        "method": "suggest_redlines",
        "need_file_id": True,
        "takes_question": True,
    },
    "extract_obligations":{
        "description": "Extract actionable contract obligations (party, category, trigger)",
        "method": "extract_obligations",
        "need_file_id": True,
        "takes_question": True,
    }
}

MAX_TOOL_ROUNDS = 2
MAX_TOOLS_PER_ROUND = 3

def run_tool(tools: AssistantTools, name: str, question: str) -> dict:
    meta = TOOL_REGISTRY.get(name)
    if not meta:
        return {"text": "", "citations": [], "status": "ok"}

    method = getattr(tools, meta["method"], None)
    if method is None:
        logger.warning("Tool method missing: %s", meta["method"])
        return {"text": "", "citations": [], "status": "ok"}

    if meta.get("takes_question"):
        out = method(question)
    else:
        out = method()

    if not isinstance(out, dict):
        return {"text": str(out or ""), "citations": [], "status": "ok"}

    out.setdefault("text", "")
    out.setdefault("citations", [])
    out.setdefault("status", "ok")
    return out

def merge_context(contexts: List[Dict[str, Any]]) -> dict:
    texts: List[str] = []
    citations: List[dict] = []
    seen = set()
    status = "ok"

    for part in contexts or []:
        if not isinstance(part, dict):
            continue
        text = (part.get("text") or "").strip()
        if text:
            texts.append(text)
        for cite in part.get("citations") or []:
            key = (
                cite.get("chunk_id")
                or cite.get("id")
                or cite.get("clause_id")
                or cite.get("label")
                or json.dumps(cite, sort_keys=True, default=str)
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(cite)

        st = part.get("status") or "ok"
        if st == "not_ready":
            status = "not_ready"
        elif st == "no_file" and status == "ok":
            status = "no_file"
        elif st == "error" and status == "ok":
            status = "error"

    return {
        "text": "\n\n".join(texts),
        "citations": citations,
        "status": status,
    }

def plan_tools_rules(question: str, file_id: Optional[str] = None) -> List[str]:
    q = (question or "").lower()
    tools: List[str] = []

    contract_markers = (
        "summarize", "summary", "overview", "key terms", "this contract",
        "payment", "clause", "termination", "renew", "parties",
        ".pdf", "signed", "nda", "msa", "redline", "rewrite",
    )
    if any(k in q for k in contract_markers):
        tools.append("search_contract")

    if any(k in q for k in ("risk", "liability", "exposure", "highest risk")):
        tools.append("search_risks")

    if any(k in q for k in ("playbook", "compliant", "compliance", "gap")):
        # "how do i upload a playbook" is product — checked below first in service intent,
        # but still avoid playbook tool when clearly product how-to.
        if not any(k in q for k in ("how do i", "where can i", "how to", "upload playbook")):
            tools.append("search_playbook_gaps")

    if any(k in q for k in ("draft", "generate clause", "arbitration clause", "governing law", "clause library")):
        tools.append("search_clause_library")

    if any(k in q for k in ("how do i", "where can i", "how to use", "upload playbook", "feature", "tutorial", "guide")):
        tools.append("product_help")

    if any(k in q for k in ("workflow", "next step", "approval", "legal review", "pending")):
        tools.append("workflow_next")

    if any(
        k in q
        for k in (
            "support",
            "contact support",
            "technical support",
            "not working",
            "doesn't work",
            "does not work",
            "error",
            "failed",
            "bug",
            "issue",
            "stuck",
            "login issue",
            "payment issue",
            "billing issue",
            "refund",
        )
    ):
        tools.append("support_contact")

    if any(
        k in q
        for k in (
            "redline",
            "redlines",
            "red lining",
            "red lines",
            "tracked changes",
            "track changes",
            "revision history",
            "what was redlined",
            "find redlining",
        )
    ):
        tools.append("extract_redlines")

    if any(
        k in q
        for k in (
            "suggest redlines",
            "ai propose redlines",
            "ai suggest redlines",
            "ai propose redlining",
            "ai suggest redlining",
        )
    ):
        tools.append("suggest_redlines")

    if any(
        k in q
        for k in (
            "extract obligation",
            "extract obligations",
            "list obligation",
            "list obligations",
            "find obligation",
            "find obligations",
            "show obligation",
            "show obligations",
            "what are the obligation",
            "what obligations",
            "pull obligation",
            "obligation extract",
            "actionable obligation",
            "contract obligation",
            "my obligations",
            "obligations",
            "obligation",
        )
    ) and not any(k in q for k in ("how do i", "where can i", "how to")):
        tools.append("extract_obligations")

    # Structured extractors already RAG internally — avoid duplicate search_contract.
    if "extract_obligations" in tools or "extract_redlines" in tools or "suggest_redlines" in tools:
        tools = [t for t in tools if t != "search_contract"]

    # With a selected contract and no other signal, still allow contract RAG.
    if file_id and not tools:
        tools.append("search_contract")

    if not tools and not file_id:
        tools.append("product_help")

    return _dedupe_tools(tools)

def _dedupe_tools(tools: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for name in tools:
        if name not in TOOL_REGISTRY or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= MAX_TOOLS_PER_ROUND:
            break
    return out

def _parse_planner_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}

def plan_tools_llm(user_id: str, question: str, has_file: bool) -> dict:
    preferred_model = "mistral-small"
    try:
        from assistantService.models import UsersModel

        user = UsersModel.objects.filter(RowKey=user_id).only("isAccuracy").first()
        if user and getattr(user, "isAccuracy", None):
            preferred_model = str(user.isAccuracy).strip() or preferred_model
    except Exception:
        pass

    llm = LLMService(
        prompt_type="assistant_planner",
        system_prompt=PROMPTS["assistant_planner"],
        placeholder_values={
            "question": question,
            "has_file": str(bool(has_file)).lower(),
        },
        llm_type=preferred_model,
        operation="assistant_planner",
        user_id=user_id,
        timeout=10,
        max_tries=2,
    )
    raw = (llm.sync_generator() or {}).get("answer") or ""
    data = _parse_planner_json(raw)
    if not data:
        return {"tools": plan_tools_rules(question, file_id="x" if has_file else None)}

    tools = _dedupe_tools([str(t) for t in (data.get("tools") or [])])
    return {
        "tools": tools,
        "rag_query": data.get("rag_query"),
        "reject": bool(data.get("reject")),
    }

def plan_tools(
    question: str,
    file_id: Optional[str] = None,
    user_id: Optional[str] = None,
    use_llm_fallback: bool = True,
) -> dict:
    """
    Rules first. Optional LLM planner only when rules return no tools.
    """
    tools = plan_tools_rules(question, file_id=file_id)
    rag_query = None
    reject = False

    if not tools and use_llm_fallback and user_id:
        try:
            llm_plan = plan_tools_llm(user_id, question, bool(file_id))
            if llm_plan.get("reject"):
                return {"tools": [], "rag_query": None, "reject": True}
            tools = _dedupe_tools(llm_plan.get("tools") or [])
            rag_query = llm_plan.get("rag_query") or None
        except Exception:
            logger.exception("LLM tool planner failed; using defaults")

    if not tools and file_id:
        tools = ["search_contract"]
    elif not tools:
        tools = ["product_help"]

    q = (question or "").lower()
    if not rag_query and "search_contract" in tools:
        if any(k in q for k in ("summarize", "summary", "overview", "explain this contract", "key terms")):
            rag_query = SUMMARY_RAG_QUERY

    return {"tools": tools, "rag_query": rag_query, "reject": reject}
