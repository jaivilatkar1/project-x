"""
Contract Intelligence Assistant — intent routing, tool context, LLM answer.
"""
import json
import logging
import re
from typing import List, Optional

from assistantService.data.user_data import PROMPTS
from assistantService.helpers.utils import ResponseMessage
from assistantService.models import ChatMessage, ChatSession, UsersModel
from assistantService.services.assistant_agent import (
    MAX_TOOLS_PER_ROUND,
    TOOL_REGISTRY,
    merge_context,
    plan_tools,
    run_tool,
)
from assistantService.services.assistant_tools import AssistantTools, resolve_contract_by_name
from assistantService.services.llm_service import LLMService

logger = logging.getLogger(__name__)

INTENT_KEYWORDS = [
    ("reject", ["ipl", "cricket", "movie", "song", "python code", "write code", "weather", "bigg boss"]),
    ("risk", ["risk", "liability", "exposure", "highest risk"]),
    ("workflow", ["workflow", "next step", "approval", "legal review", "pending"]),
    # Product before playbook — "how do I upload a playbook?" is product help, not gap analysis.
    ("product", ["how do i", "where can i", "how to use", "upload playbook", "feature"]),
    ("playbook", ["playbook", "compliant", "compliance", "standard"]),
    ("clause_draft", ["draft", "generate clause", "arbitration clause", "governing law"]),
    ("redline", ["redline", "better wording", "rewrite", "improve clause"]),
    ("obligation", [
        "extract obligation", "list obligation", "find obligation", "show obligation",
        "what obligations", "actionable obligation", "my obligations", "obligations",
    ]),
    ("contract", [
        "clause", "payment term", "renew", "termination", "this contract", "page",
        "summarize", "summary", "overview", "key terms", "what does this",
        "explain this contract", "parties",
    ]),
    ("support", [
        "not working", "doesn't work", "does not work", "error", "failed",
        "bug", "issue", "problem", "stuck", "login issue", "payment issue",
        "billing issue", "refund", "help me fix", "support",
    ]),
]

# Tool results already formatted for chat — skip second LLM rewrite.
PASS_THROUGH_TOOLS = frozenset({
    "extract_obligations",
    "extract_redlines",
    "suggest_redlines",
})

SUMMARY_RAG_QUERY = (
    "parties payment termination confidentiality liability renewal "
    "governing law obligations"
)

REJECT_ANSWER = (
    "I'm designed to help with contracts, legal documents, and clm. "
    "I can't assist with that topic. Ask about a clause, risk, playbook, or workflow instead."
)

NO_FILE_ANSWER = (
    "Select a contract in Repository or open one in the table view, "
    "then ask again — e.g. “Summarize this contract” or “What are the payment terms?”"
)

SUPPORT_FOOTER = (
    "If this is still unresolved, contact support: "
    "support@example.com "
    "(include screenshot, error text, contract id, and steps)."
)

# confidence_reasoning scores 0–100; below this we flag low confidence in the UI
LOW_CONFIDENCE_THRESHOLD = 70
ENABLE_AUTO_REVISE = True

class AssistantService:
    def detect_intent(self, message: str) -> str:
        m = (message or "").lower()
        for name, keywords in INTENT_KEYWORDS:
            if any(k in m for k in keywords):
                return name
        return "general"

    def resolve_intent(self, message: str, file_id: Optional[str] = None) -> str:
        intent = self.detect_intent(message)
        if intent == "reject":
            return intent
        if file_id and intent == "general":
            return "contract"
        return intent

    def _history_text(self, session: ChatSession, limit: int = 20) -> str:
        msgs = list(
            ChatMessage.objects.filter(session=session).order_by("-created_at")[:limit]
        )
        msgs.reverse()
        return "\n\n".join(f"{m.role}: {m.message}" for m in msgs)

    def _execute_plan(
        self,
        tools: AssistantTools,
        question: str,
        tool_names: List[str],
        rag_query: Optional[str] = None,
    ) -> dict:
        search_query = rag_query or question
        parts = []
        for name in tool_names[:MAX_TOOLS_PER_ROUND]:
            meta = TOOL_REGISTRY.get(name)
            if not meta:
                continue
            if meta.get("need_file_id") and not tools.file_id:
                parts.append({"text": "", "citations": [], "status": "no_file"})
                continue
            q = search_query if name == "search_contract" else question
            parts.append(run_tool(tools, name, q))
            if parts[-1].get("status") == "not_ready":
                break
        return merge_context(parts)

    @staticmethod
    def _looks_like_contract_question(question: str) -> bool:
        q = (question or "").lower()
        markers = (
            "summarize", "summary", "contract", ".pdf", "payment", "clause",
            "termination", "this contract", "signed", "nda", "msa",
        )
        return any(m in q for m in markers)

    def _resolve_file_id(
        self, user_id: str, question: str, file_id: Optional[str] = None
    ) -> Optional[str]:
        if file_id:
            return file_id
        if not self._looks_like_contract_question(question):
            return None
        hit = resolve_contract_by_name(user_id, question)
        return hit["file_id"] if hit else None

    @staticmethod
    def _rag_question(intent: str, question: str) -> str:
        if intent != "contract":
            return question
        q = (question or "").lower()
        if any(k in q for k in ("summarize", "summary", "overview", "explain this contract", "key terms")):
            return SUMMARY_RAG_QUERY
        return question

    @staticmethod
    def _parse_answer(raw: str) -> str:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("answer"):
                return str(parsed["answer"])
        except (json.JSONDecodeError, TypeError):
            pass
        return raw or ""

    @staticmethod
    def _ensure_readable_format(answer: str, question: str = "") -> str:
        """Force Rufus-style bullets when the model returns a dense paragraph."""
        text = (answer or "").strip()
        if not text:
            return text

        # Normalize escaped newlines from JSON/model output
        text = text.replace("\\n", "\n").replace("\r\n", "\n")

        has_bullets = bool(
            re.search(r"(?m)^\s*[-*•]\s+\S", text)
            or re.search(r"(?m)^\s*\d+[.)]\s+\S", text)
        )
        if has_bullets:
            return text

        q = (question or "").lower()
        wants_points = any(
            k in q
            for k in (
                "point",
                "bullet",
                "summar",
                "list",
                "overview",
                "key term",
                "key points",
            )
        )
        newline_count = text.count("\n")
        long_dense = len(text) > 160 and newline_count < 2

        if not (wants_points or long_dense):
            return text

        # Prefer splitting on sentence boundaries
        parts = re.split(r"(?<=[.!?])\s+", text)
        parts = [p.strip(" -•\t") for p in parts if p and p.strip()]
        if len(parts) < 2:
            # Fallback: split on semicolons / " and " clauses carefully
            parts = [p.strip() for p in re.split(r";\s+", text) if p.strip()]

        if len(parts) < 2:
            return text

        intro = ""
        bullets = parts
        if len(parts[0]) <= 140 and len(parts) > 2:
            intro = parts[0]
            bullets = parts[1:]

        # If still too few bullets for a "points" ask, split long clauses further
        if wants_points and len(bullets) < 3:
            expanded = []
            for b in bullets:
                if len(b) < 140:
                    expanded.append(b)
                    continue
                chunks = re.split(r";\s+|,\s+(?=including\b|with\b|covering\b)|,\s+and\s+", b)
                chunks = [c.strip(" ,") for c in chunks if c and len(c.strip(" ,")) > 20]
                if len(chunks) >= 2:
                    expanded.extend(chunks)
                else:
                    expanded.append(b)
            bullets = expanded

        bullets = bullets[:8]
        body = "\n".join(f"- {b}" for b in bullets)
        if intro:
            return f"{intro}\n\n**Summary:**\n{body}"
        return f"**Summary:**\n{body}"

    def _response_data(
        self,
        session: ChatSession,
        intent: str,
        answer: str,
        citations=None,
        provider_used: str = "",
        resolved_file_id: Optional[str] = None,
        eval_id: Optional[str] = None,
        auto_score=None,
        auto_reason: str = "",
        low_confidence: bool = False,
        was_revised: bool = False,
        original_answer: Optional[str] = ""
    ) -> dict:
        return {
            "sessionId": str(session.session_id),
            "intent": intent,
            "answer": answer,
            "citations": citations or [],
            "provider_used": provider_used,
            "resolvedFileId": resolved_file_id,
            "evalId": eval_id,
            "autoScore": auto_score,
            "autoReason": auto_reason or "",
            "lowConfidence": bool(low_confidence),
            "wasRevised": bool(was_revised),
            "originalAnswer": original_answer or ""
        }

    def _save_blocked_answer(
        self,
        session,
        intent,
        answer,
        citations=None,
        resolved_file_id: Optional[str] = None,
    ):
        ChatMessage.objects.create(
            session=session,
            role="assistant",
            message=answer,
            intent=intent,
            citations=citations or [],
            provider_used="",
        )
        session.save(update_fields=["updated_at"])
        return ResponseMessage.success_message(
            "ok",
            data=self._response_data(
                session,
                intent,
                answer,
                citations=citations,
                resolved_file_id=resolved_file_id,
            ),
        )

    def chat(
        self,
        user_id: str,
        question: str,
        file_id: Optional[str] = None,
        session_id: Optional[str] = None,
        use_llm_planner: bool = True,
    ):
        user = UsersModel.objects.filter(RowKey=user_id).first()
        if not user:
            return ResponseMessage.error_message("User not found")

        file_id = self._resolve_file_id(user_id, question, file_id)
        resolved_file_id = file_id

        session = None
        if session_id:
            session = ChatSession.objects.filter(session_id=session_id, user=user).first()

        if not session:
            session = ChatSession.objects.create(
                user=user,
                contract_id=file_id if file_id else None,
            )
        elif file_id and not session.contract_id:
            session.contract_id = file_id
            session.save(update_fields=["contract_id", "updated_at"])

        ChatMessage.objects.create(session=session, role="user", message=question)
        intent = self.resolve_intent(question, file_id=file_id)

        if intent == "reject":
            return self._save_blocked_answer(
                session, intent, REJECT_ANSWER, resolved_file_id=resolved_file_id
            )

        tools = AssistantTools(user_id=user_id, file_id=file_id)

        # Rules-first planner; optional LLM only when rules return no tools.
        plan = plan_tools(
            question,
            file_id=file_id,
            user_id=user_id,
            use_llm_fallback=use_llm_planner,
        )
        if plan.get("reject"):
            return self._save_blocked_answer(
                session, "reject", REJECT_ANSWER, resolved_file_id=resolved_file_id
            )

        tool_names = plan.get("tools") or []
        rag_query = plan.get("rag_query") or self._rag_question(intent, question)
        context = self._execute_plan(tools, question, tool_names, rag_query)
        status = context.get("status", "ok")

        needs_contract = intent in {
            "contract",
            "redline",
            "risk",
            "playbook",
            "workflow",
            "obligation",
        } or (
            "search_contract" in tool_names
            or "search_risks" in tool_names
            or "search_playbook_gaps" in tool_names
            or "workflow_next" in tool_names
            or "extract_obligations" in tool_names
            or "extract_redlines" in tool_names
            or "suggest_redlines" in tool_names
        )

        if status == "no_file" and needs_contract:
            return self._save_blocked_answer(
                session, intent, NO_FILE_ANSWER, resolved_file_id=resolved_file_id
            )

        if status == "not_ready":
            return self._save_blocked_answer(
                session,
                intent,
                context.get("text") or "",
                resolved_file_id=resolved_file_id,
            )

        history = self._history_text(session)
        citations = context.get("citations") or []
        provider = ""
        preferred_model = (getattr(user, "isAccuracy", None) or "mistral-small").strip()

        # Structured extractors already return a chat-ready list — don't rewrite.
        use_pass_through = (
            status == "ok"
            and bool((context.get("text") or "").strip())
            and any(t in PASS_THROUGH_TOOLS for t in tool_names)
            and "product_help" not in tool_names
        )

        if use_pass_through:
            answer = self._ensure_readable_format(
                context.get("text") or "",
                question=question,
            )
        else:
            try:
                llm = LLMService(
                    prompt_type="assistant_answer",
                    system_prompt=PROMPTS["assistant_system"],
                    placeholder_values={
                        "system": PROMPTS["assistant_system"],
                        "context": context.get("text") or "",
                        "history": history,
                        "question": question,
                        "intent": intent,
                    },
                    llm_type=preferred_model,
                    operation="assistant_chat",
                    user_id=user_id,
                    timeout=60,
                    max_tries=3,
                )
                result = llm.sync_generator()
            except Exception as exc:
                logger.exception("Assistant LLM call failed")
                return ResponseMessage.error_message("Failed to generate answer", error=str(exc))

            answer = self._ensure_readable_format(
                self._parse_answer(result.get("answer") or ""),
                question=question,
            )
            provider = getattr(llm.llm_instance, "active_provider", "") or ""

        if intent == "support":
            answer = self._append_support_footer(answer)

        ChatMessage.objects.create(
            session=session,
            role="assistant",
            message=answer,
            intent=intent,
            citations=citations,
            provider_used=provider,
        )
        session.save(update_fields=["updated_at"])

        eval_id = None
        auto_score = None
        auto_reason = ""
        low_confidence = False
        was_revised = False
        original_answer = ""
        try:
            from assistantService.services.eval_service import (
                create_eval_record,
                run_auto_eval,
                regenerate_low_confidence_answer,
                LOW_CONFIDENCE_THRESHOLD,
            )

            draft_answer = answer
            rec = create_eval_record(
                user_id=user_id,
                session_id=str(session.session_id),
                question=question,
                answer=draft_answer,
                context_text=context.get("text") or "",
                intent=intent,
                provider_used=provider,
                model_used=preferred_model,
                citations=citations,
            )
            run_auto_eval(rec, agreement_type="agreement")
            eval_id = str(rec.id)
            auto_score = rec.auto_score
            auto_reason = rec.auto_reason or ""

            if (
                not use_pass_through
                and auto_score is not None
                and float(auto_score) < LOW_CONFIDENCE_THRESHOLD
            ):
                low_confidence = True
                if ENABLE_AUTO_REVISE:
                    revised, revise_status = regenerate_low_confidence_answer(
                        user_id=user_id,
                        question=question,
                        context_text=context.get("text") or "",
                        answer=draft_answer,
                        auto_reason=auto_reason or "",
                    )
                    if revised and revised.strip() != (draft_answer or "").strip():
                        was_revised = True
                        original_answer = draft_answer
                        answer = revised.strip()

                        msg = (
                            ChatMessage.objects.filter(session=session, role="assistant")
                            .order_by("-created_at")
                            .first()
                        )
                        if msg:
                            msg.message = answer
                            msg.save(update_fields=["message"])

                        # Score the revised answer, then keep original for preference export
                        rec.answer = answer
                        run_auto_eval(rec, agreement_type="agreement")
                        auto_score = rec.auto_score
                        auto_reason = rec.auto_reason or ""
                        low_confidence = (
                            auto_score is not None
                            and float(auto_score) < LOW_CONFIDENCE_THRESHOLD
                        )

                        rec.answer = original_answer
                        rec.corrected_answer = answer
                        rec.auto_eval_status = "auto_revised"
                        rec.save(
                            update_fields=[
                                "answer",
                                "corrected_answer",
                                "auto_eval_status",
                                "updated_at",
                            ]
                        )
                    else:
                        logger.info(
                            "Auto-revise skipped/no change (status=%s)", revise_status
                        )
        except Exception:
            logger.exception("Assistant auto-eval failed")

        return ResponseMessage.success_message(
            "ok",
            data=self._response_data(
                session,
                intent,
                answer,
                citations=citations,
                provider_used=provider,
                resolved_file_id=resolved_file_id,
                eval_id=eval_id,
                auto_score=auto_score,
                auto_reason=auto_reason,
                low_confidence=low_confidence,
                was_revised=was_revised,
                original_answer=original_answer if was_revised else "",
            ),
        )

    @staticmethod
    def _append_support_footer(answer: str) -> str:
        text = (answer or "").strip()
        if not text:
            return SUPPORT_FOOTER
        if "support@example.com" in text.lower():
            return text
        return f"{text}\n\n{SUPPORT_FOOTER}"
