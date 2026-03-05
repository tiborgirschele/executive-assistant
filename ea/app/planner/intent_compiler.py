from __future__ import annotations

import hashlib
import re
import time
from typing import Any


def _domain_from_text(text_lower: str) -> str:
    if any(k in text_lower for k in ("pay", "invoice", "iban", "transfer", "refund", "budget", "cost")):
        return "finance"
    if any(k in text_lower for k in ("trip", "flight", "hotel", "airport", "layover", "travel", "route")):
        return "travel"
    if any(k in text_lower for k in ("meeting", "project", "deadline", "proposal", "roadmap", "deliverable")):
        return "project"
    if any(k in text_lower for k in ("health", "doctor", "therapy", "med", "appointment", "symptom")):
        return "health"
    return "general"


def compile_intent_spec_v2(
    *,
    text: str,
    tenant: str = "",
    chat_id: int | None = None,
    has_url: bool | None = None,
) -> dict[str, Any]:
    raw = str(text or "").strip()
    text_lower = raw.lower()
    url_present = bool(has_url) or bool(re.search(r"https?://", raw))
    high_risk = any(
        k in text_lower
        for k in (
            "pay",
            "transfer",
            "book",
            "cancel",
            "delete",
            "terminate",
            "sign",
            "approve",
        )
    )
    question_like = raw.endswith("?") or any(
        w in text_lower for w in ("what", "why", "how", "when", "where", "summarize", "explain")
    )
    domain = _domain_from_text(text_lower)
    deadline_hint = (
        "urgent"
        if any(k in text_lower for k in ("urgent", "asap", "today", "now", "immediately"))
        else "normal"
    )
    approval_class = "explicit_callback_required" if high_risk else "none"
    risk_class = "high_impact_action" if high_risk else "routine_assistive"
    deliverable_type = "answer_now" if question_like else "execute_or_plan"
    budget_class = "high_guardrail" if high_risk else "standard"
    evidence_requirements: list[str] = []
    if url_present:
        evidence_requirements.append("url_evidence")
    if domain == "finance":
        evidence_requirements.append("payment_context")
    if domain == "travel":
        evidence_requirements.append("travel_context")
    if not evidence_requirements:
        evidence_requirements.append("user_request_context")
    source_refs = re.findall(r"https?://[^\s]+", raw) if url_present else []
    objective = raw[:1200]
    commitment_key = ""
    if domain in {"travel", "finance", "project", "health"}:
        digest = hashlib.sha1(objective.encode("utf-8", errors="ignore")).hexdigest()[:12]
        commitment_key = f"{domain}:{str(tenant or '')}:{digest}"
    return {
        "intent_type": "url_analysis" if url_present else "free_text",
        "objective": objective,
        "domain": domain,
        "deliverable": deliverable_type,
        "deliverable_type": deliverable_type,
        "autonomy_level": "approval_required" if high_risk else "assistive",
        "approval_class": approval_class,
        "risk_level": "high" if high_risk else "normal",
        "risk_class": risk_class,
        "budget_class": budget_class,
        "deadline_hint": deadline_hint,
        "has_url": url_present,
        "evidence_requirements": evidence_requirements,
        "source_refs": source_refs,
        "stakeholders": [],
        "output_contract": {"format": "telegram_message", "style": "concise", "max_chars": 3500},
        "commitment_key": commitment_key,
        "tenant": str(tenant or ""),
        "chat_id": int(chat_id) if chat_id is not None else None,
        "compiled_at_epoch_s": int(time.time()),
    }


__all__ = ["compile_intent_spec_v2"]
