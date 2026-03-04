from __future__ import annotations

import hashlib
import uuid
from typing import Any

from app.actions import create_action
from app.db import get_db
from app.outbox import enqueue_outbox


def generate_draft_hash(tenant: str, iban: str, amount: float, currency: str, creditor: str) -> str:
    raw_hash = f"{tenant}|{iban}||{amount}|{currency}|||{creditor}"
    return hashlib.sha256(raw_hash.encode()).hexdigest()


def generate_demo_draft(tenant: str, chat_id: int) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    creditor = "Stripe Cloud"
    iban = "AT891234567890123456"
    amount = 145.20
    currency = "EUR"
    reference = "INV-2026"
    draft_hash = generate_draft_hash(tenant, iban, amount, currency, creditor)

    db = get_db()
    db.execute(
        """
        INSERT INTO payment_drafts (
            draft_id,
            tenant,
            source_artifact_id,
            creditor_name,
            iban,
            amount,
            currency,
            reference,
            draft_hash,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'drafted')
        """,
        (
            draft_id,
            tenant,
            artifact_id,
            creditor,
            iban,
            amount,
            currency,
            reference,
            draft_hash,
        ),
    )

    act_confirm = create_action(
        tenant,
        "confirm_payment",
        {"draft_id": draft_id, "draft_hash": draft_hash},
    )
    act_cancel = create_action(
        tenant,
        "cancel_payment",
        {"draft_id": draft_id},
    )

    msg = (
        "🧾 <b>Payment Draft Generated</b>\n\n"
        f"<b>Creditor:</b> {creditor}\n"
        f"<b>IBAN:</b> <code>{iban}</code>\n"
        f"<b>Amount:</b> {amount} {currency}\n"
        f"<b>Ref:</b> {reference}\n\n"
        "Status: 🟡 <i>Awaiting Confirmation</i>"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "✅ Confirm & Pay", "callback_data": f"act:{act_confirm}"}],
            [{"text": "❌ Cancel", "callback_data": f"act:{act_cancel}"}],
        ]
    }
    enqueue_outbox(
        tenant,
        chat_id,
        {
            "type": "message",
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": kb,
        },
    )
    return {"ok": True, "draft_id": draft_id, "action_ids": {"confirm": act_confirm, "cancel": act_cancel}}


def handle_payment_action(tenant: str, chat_id: int, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    draft_id = payload.get("draft_id")

    if action_type == "cancel_payment":
        db.execute(
            "UPDATE payment_drafts SET status = 'cancelled', updated_at = NOW() WHERE draft_id = %s",
            (draft_id,),
        )
        enqueue_outbox(
            tenant,
            chat_id,
            {"type": "message", "text": "🚫 Payment Draft Cancelled."},
        )
        return {"ok": True, "status": "cancelled", "draft_id": draft_id}

    expected_hash = payload.get("draft_hash")
    draft = db.fetchone(
        "SELECT * FROM payment_drafts WHERE draft_id = %s AND tenant = %s",
        (draft_id, tenant),
    )
    if not draft or draft["status"] != "drafted":
        enqueue_outbox(
            tenant,
            chat_id,
            {"type": "message", "text": "❌ Error: Draft not found or already processed."},
        )
        return {"ok": False, "status": "missing_or_processed", "draft_id": draft_id}

    current_hash = generate_draft_hash(
        tenant,
        draft["iban"],
        draft["amount"],
        draft["currency"],
        draft["creditor_name"],
    )
    if current_hash != expected_hash:
        enqueue_outbox(
            tenant,
            chat_id,
            {
                "type": "message",
                "text": "🚨 Security Alert: Invoice data was modified (TOCTOU). Confirmation blocked.",
            },
        )
        return {"ok": False, "status": "hash_mismatch", "draft_id": draft_id}

    db.execute(
        "UPDATE payment_drafts SET status = 'user_confirmed', confirmed_by_chat_id = %s, updated_at = NOW() WHERE draft_id = %s",
        (chat_id, draft_id),
    )
    db.execute(
        "INSERT INTO payment_draft_events (id, draft_id, tenant, event_type, actor_chat_id) VALUES (%s, %s, %s, 'confirmed', %s)",
        (str(uuid.uuid4()), draft_id, tenant, chat_id),
    )
    enqueue_outbox(
        tenant,
        chat_id,
        {
            "type": "message",
            "text": (
                "🟢 <b>Payment Confirmed</b>\n\n"
                f"{draft['amount']} {draft['currency']} to {draft['creditor_name']} has been locked for bank execution."
            ),
            "parse_mode": "HTML",
        },
    )
    return {"ok": True, "status": "user_confirmed", "draft_id": draft_id}


def run_operation(
    *,
    operation: str,
    tenant: str,
    chat_id: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    op = str(operation or "").strip().lower()
    body = dict(payload or {})
    if op == "generate_demo_draft":
        return generate_demo_draft(tenant, chat_id)
    if op == "handle_action":
        action_type = str(body.get("action_type") or "").strip()
        action_payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        if not action_type:
            return {"ok": False, "status": "missing_action_type"}
        return handle_payment_action(tenant, chat_id, action_type, action_payload)
    return {"ok": False, "status": "unknown_operation", "operation": op}


__all__ = [
    "generate_draft_hash",
    "generate_demo_draft",
    "handle_payment_action",
    "run_operation",
]
