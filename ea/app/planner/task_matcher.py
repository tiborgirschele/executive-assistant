from __future__ import annotations


def infer_domain(text_lower: str) -> str:
    sample = str(text_lower or "").lower()
    travel_keywords = ("trip", "flight", "hotel", "airport", "layover", "travel", "route", "itinerary")
    finance_keywords = ("pay", "invoice", "iban", "refund", "budget", "cost", "wire transfer", "bank transfer")
    travel_hit = any(k in sample for k in travel_keywords)
    finance_hit = any(k in sample for k in finance_keywords)
    if "transfer" in sample and any(k in sample for k in ("iban", "invoice", "payment", "wire", "bank")):
        finance_hit = True
    if travel_hit and not finance_hit:
        return "travel"
    if finance_hit and not travel_hit:
        return "finance"
    if travel_hit and finance_hit:
        if any(k in sample for k in ("airport transfer", "hotel transfer", "route", "layover", "itinerary")):
            return "travel"
        return "finance"
    if "transfer" in sample:
        return "finance"
    if any(k in sample for k in ("meeting", "project", "deadline", "proposal", "roadmap", "deliverable")):
        return "project"
    if any(k in sample for k in ("health", "doctor", "therapy", "med", "appointment", "symptom")):
        return "health"
    return "general"


def detect_high_risk_action(text_lower: str) -> bool:
    sample = str(text_lower or "").lower()
    high_risk_keywords = ("pay", "book", "cancel", "delete", "terminate", "sign", "approve")
    transfer_high_risk = False
    if "transfer" in sample and "airport transfer" not in sample and "hotel transfer" not in sample:
        transfer_high_risk = any(k in sample for k in ("iban", "bank", "wire", "invoice", "payment", "money"))
    return any(k in sample for k in high_risk_keywords) or transfer_high_risk


def match_task_type(
    text_lower: str,
    *,
    domain: str,
    high_risk: bool,
    url_present: bool,
) -> str:
    sample = str(text_lower or "").lower()
    dom = str(domain or "").strip().lower()
    if any(k in sample for k in ("research pass", "secondary research", "deep research")):
        return "run_secondary_research_pass"
    if any(k in sample for k in ("strategy pack", "strategy memo", "strategic options")):
        return "strategy_pack"
    if any(k in sample for k in ("feedback intake", "collect feedback", "feedback form")):
        return "feedback_intake"
    if any(k in sample for k in ("bridge event", "webhook ingest", "external event")):
        return "bridge_external_event"
    if any(k in sample for k in ("bridge action", "dispatch action", "external action")):
        return "bridge_external_action"
    if any(k in sample for k in ("polish", "humanize", "rewrite", "tone")):
        return "polish_human_tone"
    if any(k in sample for k in ("prompt pack", "compile prompt", "prompt template")):
        return "compile_prompt_pack"
    if any(k in sample for k in ("intake", "questionnaire", "form", "survey")):
        return "collect_structured_intake"
    if dom == "travel":
        if any(k in sample for k in ("route video", "arrival video", "render route")):
            return "route_video_render"
        if any(k in sample for k in ("reprice", "price drop", "optimize cost", "cheaper option")):
            return "optimize_trip_cost"
        if any(k in sample for k in ("book", "rebook", "reroute", "cancel", "layover", "risk", "rescue")):
            return "travel_rescue"
        return "trip_context_pack"
    if url_present and any(k in sample for k in ("summarize", "extract", "analyze", "review")):
        return "run_secondary_research_pass"
    if dom == "finance":
        if high_risk:
            return "approval_router"
        return "typed_safe_action"
    return ""


__all__ = ["detect_high_risk_action", "infer_domain", "match_task_type"]
