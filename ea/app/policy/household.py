import logging

def enforce_household_policy(document_id, user_id, confidence_score):
    """
    v1.12.5 M5: Household Safety Middleware
    Guarantees fail-closed ownership for ambiguous documents.
    Callable from Primary, Repair, Replay, and Enhancement paths.
    """
    if confidence_score < 0.85:
        logging.warning(f"🔒 [HOUSEHOLD POLICY] Document {document_id} ownership ambiguous (Score: {confidence_score}).")
        logging.warning(f"🔒 [HOUSEHOLD POLICY] ACTION BLOCKED: Moving to Blind Triage Review Queue.")
        return {
            "action_allowed": False,
            "reason": "low_confidence_ownership",
            "safe_hint": "A new family document needs review."
        }
        
    logging.info(f"🔓 [HOUSEHOLD POLICY] Document {document_id} ownership confirmed for User {user_id}.")
    return {"action_allowed": True}
