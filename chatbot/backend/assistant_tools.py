"""
Tool wrappers for Contract Intelligence Assistant.
"""
import logging
import re
from typing import Optional
import os
from dotenv import load_dotenv
from django.db.models import Q

from assistantService.models import (
    ClauseLibrary,
    ContractChunksModel,
    ContractOnboardingResult,
    ContractsMetadata,
    KnowledgeBase,
    PlaybookAnalysisMitigation,
    UsersModel,
    WorkflowRun,
    WorkflowStepRun,
)
from assistantService.services.chunk_prefilter import ChunkPrefilter
from assistantService.services.clause_library_service import ClauseLibraryService
from assistantService.services.contracts import Contract
from assistantService.services.docx_redline_extractor import track_changes_from_docx_bytes
from assistantService.services.llm_service import LLMService
from assistantService.data import user_data
import json
import requests

logger = logging.getLogger(__name__)

def _is_pdf_name(name: str, doc_type: str = "") -> bool:
    n = (name or "").lower()
    d = (doc_type or "").lower()
    return n.endswith(".pdf") or d in ("pdf", "application/pdf")

def _is_docx_name(name: str, doc_type: str = "") -> bool:
    n = (name or "").lower()
    d = (doc_type or "").lower()
    return n.endswith(".docx") or n.endswith(".doc") or d in ("docx", "doc")

def _extract_plain_text(file_bytes: bytes, name: str = "") -> str:
    """Extract plain text from PDF or DOCX bytes for version-diff fallback."""
    n = (name or "").lower()
    try:
        if n.endswith(".pdf") or (file_bytes[:4] == b"%PDF"):
            import fitz

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            try:
                return "\n".join((page.get_text() or "").strip() for page in doc).strip()
            finally:
                doc.close()

        if n.endswith(".docx") or n.endswith(".doc") or file_bytes[:2] == b"PK":
            import io
            from docx import Document

            document = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in document.paragraphs if p.text).strip()
    except Exception as exc:
        logger.warning("Plain text extraction failed for %s: %s", name or "file", exc)
    return ""

load_dotenv()

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@example.com")
SUPPORT_PAGE_URL = os.getenv("SUPPORT_PAGE_URL", "https://example.com")
SUPPORT_HOURS = os.getenv("SUPPORT_HOURS", "Mon-Fri, 9:00 AM - 6:00 PM IST")

_CONTRACT_QUERY_STOP = re.compile(
    r"\b(summarize|summary|overview|this|contract|the|please|analyse|analyze|review)\b",
    re.I,
)
_NAME_SUFFIXES = (
    " - final signed copy",
    " - ready for sign",
    " - redlined",
    " - signed",
)

def _extract_chunk_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "content", "body", "clause"):
            val = content.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return str(content)
    if isinstance(content, list):
        parts = [_extract_chunk_text(item) for item in content]
        return "\n".join([p for p in parts if p])
    return str(content)

def _extract_page(content):
    if not isinstance(content, dict):
        return None
    for key in ("page_number", "page", "pageNumber", "page_no"):
        val = content.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None

def _normalize_contract_query(text: str) -> str:
    t = (text or "").lower()
    t = _CONTRACT_QUERY_STOP.sub(" ", t)
    t = re.sub(r"\.pdf\b", "", t, flags=re.I)
    for suffix in _NAME_SUFFIXES:
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    return " ".join(t.split()).strip()

def resolve_contract_by_name(user_id: str, question: str) -> Optional[dict]:
    """Match a contract in the user's repository by name substring."""
    needle = _normalize_contract_query(question)
    if len(needle) < 3:
        return None

    qs = ContractsMetadata.objects.filter(
        Q(PartitionKey=user_id) | Q(UserId=user_id)
    )

    row = qs.filter(ContractName__iexact=needle).first()
    if not row:
        row = qs.filter(ContractName__icontains=needle).first()
    if not row:
        for c in qs.only("RowKey", "ContractName")[:200]:
            base = (c.ContractName or "").lower()
            for suffix in _NAME_SUFFIXES:
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
            if needle in base:
                row = c
                break

    if not row:
        return None
    return {"file_id": str(row.RowKey), "contract_name": row.ContractName or ""}

def _chunk_owner_ids(file_id: str, user_id: str) -> list:
    """Chunk rows may be stored under contract owner id, not the chatting user."""
    meta = ContractsMetadata.objects.filter(RowKey=file_id).first()
    owners = {user_id, ""}
    if meta:
        if meta.PartitionKey:
            owners.add(meta.PartitionKey)
        if meta.UserId:
            owners.add(meta.UserId)
    return list(owners)

class AssistantTools:
    def __init__(self, user_id: str, file_id: Optional[str] = None):
        self.user_id = user_id
        self.file_id = file_id

    def search_contract(self, question: str, limit: int = 8) -> dict:
        if not self.file_id:
            return {
                "text": "",
                "citations": [],
                "status": "no_file",
            }

        owner_ids = _chunk_owner_ids(self.file_id, self.user_id)
        qs = ContractChunksModel.objects.filter(contract_id_id=self.file_id).filter(
            Q(user_id__in=owner_ids)
        )

        total = qs.count()
        if total == 0:
            meta = ContractsMetadata.objects.filter(RowKey=self.file_id).first()
            name = (meta.ContractName if meta else self.file_id) or self.file_id
            return {
                "text": (
                    f"Contract '{name}' is in your repository but analysis/chunks are not ready yet. "
                    "Run analysis or open the contract and wait for processing to finish, then ask again."
                ),
                "citations": [],
                "status": "not_ready",
            }

        rows = list(qs.only("primary_key", "title", "content")[:120])
        chunk_dicts = []
        for c in rows:
            text = _extract_chunk_text(c.content)
            chunk_dicts.append({
                "chunk_id": str(c.primary_key),
                "term": f"{c.title or ''} {text[:800]}".strip(),
                "title": c.title or "",
                "content": text,
                "raw": c,
            })

        prefilter = ChunkPrefilter(self.user_id)
        ranked = prefilter.prefilter_chunks(question, chunk_dicts, top_k=limit)
        if not ranked:
            ranked = chunk_dicts[:limit]

        texts = []
        citations = []
        for item in ranked:
            label = item.get("title") or item.get("chunk_id") or "Clause"
            body = item.get("content") or item.get("term") or ""
            page = _extract_page(getattr(item.get("raw"), "content", None))
            if body:
                texts.append(f"[{label}] {body[:1200]}")
            citations.append({
                "chunk_id": item.get("chunk_id"),
                "page": page,
                "label": label,
                "snippet": (body or "")[:200],
            })

        return {"text": "\n\n".join(texts), "citations": citations, "status": "ok"}

    def search_risks(self) -> dict:
        if not self.file_id:
            return {"text": "No contract selected.", "citations": []}

        lines = []
        citations = []

        onboarding = ContractOnboardingResult.objects.filter(contract_id=self.file_id).first()
        if onboarding:
            lines.append(
                f"Onboarding risk: {onboarding.risk_level or 'unknown'} — {onboarding.risk_reason or ''}"
            )
            if onboarding.actions:
                lines.append(
                    "Suggested actions: " + "; ".join(map(str, onboarding.actions[:10]))
                )

        rows = (
            PlaybookAnalysisMitigation.objects.filter(file_id_id=self.file_id)
            .order_by("-updated_at")[:20]
        )
        for r in rows:
            summary = r.analysis or r.rationale or r.new_version or "No analysis text"
            lines.append(f"- {r.keyterm_id} ({r.comparison_type}): {summary}")
            citations.append({
                "keyterm_id": r.keyterm_id,
                "page": r.page,
                "label": r.keyterm_id,
                "comparison_type": r.comparison_type,
                "id": str(r.row_key),
            })

        return {
            "text": "\n".join(lines) if lines else "No risk / playbook analysis found for this contract.",
            "citations": citations,
        }

    def search_playbook_gaps(self) -> dict:
        return self.search_risks()

    def search_clause_library(self, query: str, limit: int = 10) -> dict:
        try:
            result = ClauseLibraryService(self.user_id).search_clauses(query=query, limit=limit)
            clauses = (result or {}).get("data", {}).get("clauses") or []
            if clauses:
                text = "\n\n".join(
                    f"{c.get('title')}: {c.get('content')}"
                    for c in clauses
                    if c.get("content")
                )
                citations = [
                    {
                        "label": c.get("title"),
                        "clause_id": c.get("clause_id"),
                        "snippet": (c.get("content") or "")[:200],
                    }
                    for c in clauses
                ]
                return {"text": text or "No matching clauses found.", "citations": citations}
        except Exception as exc:
            logger.warning("ClauseLibraryService search failed, falling back: %s", exc)

        user = UsersModel.objects.filter(RowKey=self.user_id).first()
        qs = ClauseLibrary.objects.filter(is_approved=True)
        if user:
            qs = qs.filter(user_id=user)
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(content__icontains=query)
                | Q(category__icontains=query)
            )
        qs = qs.order_by("-updated_at")[:limit]
        text = "\n\n".join(f"{c.title}: {c.content}" for c in qs)
        citations = [{"label": c.title, "clause_id": str(c.clause_id)} for c in qs]
        return {"text": text or "No matching clause library entries.", "citations": citations}

    def product_help(self, query: str, limit: int = 5) -> dict:
        qs = KnowledgeBase.objects.filter(category="product")
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(content__icontains=query))
        qs = qs.order_by("-created_at")[:limit]

        if not qs.exists():
            return {
                "text": (
                    "clm quick help:\n"
                    "- Upload contracts from Repository / Upload.\n"
                    "- Run analysis for key terms and risks.\n"
                    "- Compare with Playbook standards.\n"
                    "- Use Review in MS Word for redlining.\n"
                    "- Check Workflow inbox for approvals / next steps."
                ),
                "citations": [],
            }

        text = "\n\n".join(f"{k.title}: {k.content}" for k in qs)
        citations = [{"label": k.title, "kb_id": str(k.kb_id)} for k in qs]
        return {"text": text, "citations": citations}

    def workflow_next(self) -> dict:
        if not self.file_id:
            return {
                "text": "No contract selected. Open a contract to see workflow next steps.",
                "citations": [],
            }

        lines = []
        citations = []

        onboarding = ContractOnboardingResult.objects.filter(contract_id=self.file_id).first()
        if onboarding and onboarding.actions:
            lines.append("Onboarding next actions:")
            for action in onboarding.actions[:10]:
                if isinstance(action, dict):
                    label = action.get("description") or action.get("title") or action.get("name") or str(action)
                else:
                    label = str(action)
                lines.append(f"- {label}")

        latest_run = (
            WorkflowRun.objects.filter(contract_id=self.file_id)
            .order_by("-started_at")
            .first()
        )
        if latest_run:
            lines.append(
                f"Latest workflow run: status={latest_run.status}, trigger={latest_run.trigger_type}"
            )
            steps = WorkflowStepRun.objects.filter(run=latest_run).order_by("started_at")
            for step in steps:
                lines.append(f"- Step {step.step_name}: {step.status}")
                if step.error_message:
                    lines.append(f"  error: {step.error_message}")
                citations.append({
                    "label": step.step_name,
                    "status": step.status,
                    "run_id": str(latest_run.run_id),
                    "step_id": str(step.step_id),
                })

        if not lines:
            return {
                "text": (
                    "No workflow runs found for this contract yet. "
                    "After signing/upload triggers, check Workflow inbox for pending approvals."
                ),
                "citations": [],
            }

        return {"text": "\n".join(lines), "citations": citations}

    def support_contact(self, query: str = "") -> dict:
        text = (
        "Support handoff:\n"
        f"- Email: {SUPPORT_EMAIL}\n"
        f"- Support page: {SUPPORT_PAGE_URL}\n"
        f"- Hours: {SUPPORT_HOURS}\n"
        "- Include: contract id (if any), screenshot, exact error message, and steps to reproduce."
        )
        return {"text": text, "citations": [
            {"label": "Support Email", "value": SUPPORT_EMAIL},
            {"label": "Support Page", "value": SUPPORT_PAGE_URL},
            {"label": "Support Hours", "value": SUPPORT_HOURS},
        ], "status": "ok"}

    @staticmethod
    def diff_two_texts(old_text: str, new_text: str, limit: int = 1000) -> str:
        import difflib

        old_lines = (old_text or "").splitlines()
        new_lines = (new_text or "").splitlines()
        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="original",
                tofile="current",
                lineterm="",
                n=1,
            )
        )
        if not diff:
            return "No textual differences found between original and current versions."
        return "Redline-style version diff:\n" + "\n".join(diff[:limit])

    def _download_contract_bytes(self, file_id: str) -> bytes:
        contract = Contract(self.user_id)
        md = contract.get_contract_metadata(file_ids=[file_id]) or {}
        rows = md.get("data") or []
        if not rows:
            raise ValueError(f"No contract metadata found for {file_id}")
        blob_url = rows[0].get("blobUrl") or ""
        if not blob_url:
            raise ValueError(f"No blob URL found for {file_id}")
        response = requests.get(blob_url, timeout=60)
        response.raise_for_status()
        return response.content

    def _version_diff_against_original(self, meta, current_bytes: bytes) -> dict:
        original_id = getattr(meta, "original_contract_id", None)
        name = (meta.ContractName or "").lower()
        if not original_id:
            if name.endswith(".pdf"):
                msg = (
                    "PDF has no Word tracked changes. "
                    "Link/upload an original version to compare, or use a DOCX saved with Track Changes."
                )
            else:
                msg = (
                    "No Word tracked changes found, and no linked original version is available "
                    "to compare. Upload a DOCX with Track Changes, or link an original contract."
                )
            return {"text": msg, "citations": [], "status": "no_original"}
        try:
            original_meta = ContractsMetadata.objects.filter(RowKey=original_id).first()
            original_name = (original_meta.ContractName if original_meta else "") or ""
            old_bytes = self._download_contract_bytes(str(original_id))
            old_text = _extract_plain_text(old_bytes, original_name)
            new_text = _extract_plain_text(current_bytes, meta.ContractName or "")
            if not old_text.strip() or not new_text.strip():
                return {
                    "text": "Could not extract comparable text from original/current versions.",
                    "citations": [],
                    "status": "error",
                }
            return {
                "text": self.diff_two_texts(old_text, new_text),
                "citations": [],
                "status": "ok",
            }
        except Exception as exc:
            logger.exception("Version diff failed for %s", self.file_id)
            return {
                "text": f"Error comparing to original version: {exc}",
                "citations": [],
                "status": "error",
            }

    def extract_redlines(self) -> dict:
        if not self.file_id:
            return {"text": "", "citations": [], "status": "no_file"}

        meta = ContractsMetadata.objects.filter(RowKey=self.file_id).first()
        if not meta:
            return {"text": "Contract not found.", "citations": [], "status": "not_found"}

        name = meta.ContractName or ""
        doc_type = getattr(meta, "DocType", None) or ""

        try:
            file_bytes = self._download_contract_bytes(self.file_id)
        except Exception as exc:
            return {
                "text": f"Error downloading contract: {exc}",
                "citations": [],
                "status": "error",
            }

        # PDF: no native Word track changes — compare to linked original if present.
        if _is_pdf_name(name, doc_type):
            return self._version_diff_against_original(meta, file_bytes)

        # DOCX: extract w:ins / w:del; fall back to version diff if none.
        if _is_docx_name(name, doc_type) or file_bytes[:2] == b"PK":
            parsed = track_changes_from_docx_bytes(file_bytes)
            if parsed.get("status_code") == 500:
                return {
                    "text": parsed.get("summary_text", "Could not parse DOCX revisions."),
                    "citations": [],
                    "status": "error",
                }
            if parsed.get("has_revisions"):
                return {
                    "text": parsed.get("summary_text", ""),
                    "citations": [],
                    "status": "ok",
                }
            return self._version_diff_against_original(meta, file_bytes)

        # return {
        #     "text": (
        #         "Unsupported file type for redline extraction. "
        #         "Use a DOCX with Track Changes, or a PDF/DOCX with a linked original version."
        #     ),
        #     "citations": [],
        #     "status": "unsupported",
        # }
        return self.suggest_redlines(
            "Propose material redlines for this contract based on typical playbook standards."
        )

    def suggest_redlines(self, question: str = "") -> dict:
        if not self.file_id:
            return {"text": "", "citations": [], "status": "no_file"}
        contract_text = self.search_contract(question, limit=10)
        if contract_text.get("status") != "ok":
            return contract_text

        playbook_text = self.search_risks()
        context = ("=== CONTRACT EXCERPTS ===\n"+(contract_text.get("text") or "(None)")+
        "\n\n=== PLAYBOOK RISKS ===\n"+(playbook_text.get("text") or "(None)"))

        llm = LLMService(prompt_type="assistant_suggest_redlines", system_prompt=user_data.PROMPTS["assistant_suggest_redlines"],
        placeholder_values={"context": context}, llm_type="mistral-small", operation="suggest_redlines",
        user_id=self.user_id, timeout=45, max_tries=2)

        raw = (llm.sync_generator() or {}).get("answer") or ""
        data = {}
        try:
            text = raw.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text) if text else {}
        except Exception as e:
            return {"text": f"Error parsing JSON: {e}", "citations": [], "status": "error"}
        
        lines = ["Suggested redlines (AI-proposed — not Word tracked changes):"]
        if data.get("summary"):
            lines.append(data["summary"])
        for i, r in enumerate(data.get("redlines", []), 1):
            action = (r.get("action") or "replace").upper()
            clause = r.get("clause") or "Clause"
            cur = (r.get("current_text") or "").strip()
            prop = (r.get("proposed_text") or "").strip()
            reason = (r.get("reason") or "").strip()
            lines.append(f"{i}. [{action}] {clause}")
            if cur:
                lines.append(f" [-] {cur}")
            if prop:
                lines.append(f" [+] {prop}")
            if reason:
                lines.append(f"  reason: {reason}")
        citations = (contract_text.get("citations") or []) + (playbook_text.get("citations") or [])
        return {"text": "\n".join(lines), "citations": citations, "status": "ok"}

    def extract_obligations(self, question: str = "") -> dict:
        """
        AI-extract actionable obligations (chat suggestions only — not persisted).
        Mirrors suggest_redlines: RAG excerpts → LLM JSON → formatted list.
        """
        if not self.file_id:
            return {
                "text": "Select a contract first, then ask to extract obligations.",
                "citations": [],
                "status": "no_file",
            }

        rag_question = (question or "").strip() or (
            "obligations duties payment notice confidentiality return destroy "
            "indemnify insurance audit reporting termination surviving"
        )
        contract_text = self.search_contract(rag_question, limit=12)
        if contract_text.get("status") != "ok":
            return contract_text

        context = "=== CONTRACT EXCERPTS ===\n" + (contract_text.get("text") or "(None)")
        llm_service = LLMService(
            prompt_type="assistant_extract_obligations",
            system_prompt=user_data.PROMPTS["assistant_extract_obligations"],
            placeholder_values={"context": context},
            llm_type="mistral-small",
            operation="extract_obligations",
            user_id=self.user_id,
            timeout=60,
            max_tries=2,
        )

        raw = (llm_service.sync_generator() or {}).get("answer") or ""
        try:
            text = raw.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text) if text else {}
        except Exception as e:
            return {
                "text": f"Error parsing obligations JSON: {e}\n\nRaw:\n{raw[:1500]}",
                "citations": contract_text.get("citations") or [],
                "status": "error",
            }

        obligations = data.get("obligations") if isinstance(data, dict) else None
        if not isinstance(obligations, list) or not obligations:
            return {
                "text": "No obligations could be extracted from the available contract excerpts.",
                "citations": contract_text.get("citations") or [],
                "status": "ok",
                "obligations": [],
            }

        lines = [
            "Extracted obligations (AI suggestions — nothing saved until you add them):",
        ]
        if data.get("summary"):
            lines.append(str(data["summary"]).strip())
        lines.append("")

        normalized = []
        for i, item in enumerate(obligations[:12], 1):
            if not isinstance(item, dict):
                continue
            text_ob = (item.get("text") or "").strip()
            if not text_ob:
                continue
            # Prompt field is assignee_role; accept assigned_to as alias
            category = (item.get("category") or "Other").strip()
            party = (item.get("party") or "Unspecified").strip()
            trigger = (item.get("trigger") or "").strip()
            due_hint = (item.get("due_hint") or "").strip()
            assignee = (
                item.get("assignee_role")
                or item.get("assigned_to")
                or "Unassigned"
            )
            assignee = str(assignee).strip() or "Unassigned"
            priority = str(item.get("priority") or "medium").strip().lower()
            evidence = (item.get("evidence") or "").strip()

            lines.append(f"{i}. {text_ob}")
            tag_bits = [category, party]
            if trigger:
                tag_bits.append(trigger)
            lines.append("   Tags: " + " · ".join(tag_bits))
            lines.append(f"   Assign to: {assignee} | Priority: {priority}")
            if due_hint:
                lines.append(f"   Due hint: {due_hint}")
            if evidence:
                lines.append(f"   Evidence: {evidence}")
            lines.append("")

            normalized.append(
                {
                    "text": text_ob,
                    "category": category,
                    "party": party,
                    "trigger": trigger,
                    "due_hint": due_hint,
                    "assignee_role": assignee,
                    "priority": priority,
                    "evidence": evidence,
                }
            )

        if not normalized:
            return {
                "text": "No obligations could be extracted from the available contract excerpts.",
                "citations": contract_text.get("citations") or [],
                "status": "ok",
                "obligations": [],
            }

        return {
            "text": "\n".join(lines).strip(),
            "citations": contract_text.get("citations") or [],
            "status": "ok",
            "obligations": normalized,
        }
