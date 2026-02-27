import uuid, hashlib, json
from app.db import get_db
from app.actions import create_action
from app.outbox import enqueue_outbox

def generate_draft_hash(tenant, iban, amount, currency, creditor):
    raw_hash = f"{tenant}|{iban}||{amount}|{currency}|||{creditor}"
    return hashlib.sha256(raw_hash.encode()).hexdigest()

def generate_demo_draft(tenant: str, chat_id: int):
    draft_id = str(uuid.uuid4())
    art_id = str(uuid.uuid4())
    creditor, iban, amount, currency, ref = "Stripe Cloud", "AT891234567890123456", 145.20, "EUR", "INV-2026"
    
    draft_hash = generate_draft_hash(tenant, iban, amount, currency, creditor)
    
    db = get_db()
    db.execute("""
        INSERT INTO payment_drafts (draft_id, tenant, source_artifact_id, creditor_name, iban, amount, currency, reference, draft_hash, status) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'drafted')
    """, (draft_id, tenant, art_id, creditor, iban, amount, currency, ref, draft_hash))
    
    act_confirm = create_action(tenant, "confirm_payment", {"draft_id": draft_id, "draft_hash": draft_hash})
    act_cancel = create_action(tenant, "cancel_payment", {"draft_id": draft_id})
    
    msg = f"🧾 <b>Payment Draft Generated</b>\n\n<b>Creditor:</b> {creditor}\n<b>IBAN:</b> <code>{iban}</code>\n<b>Amount:</b> {amount} {currency}\n<b>Ref:</b> {ref}\n\nStatus: 🟡 <i>Awaiting Confirmation</i>"
    kb = {"inline_keyboard": [
        [{"text": "✅ Confirm & Pay", "callback_data": f"act:{act_confirm}"}],
        [{"text": "❌ Cancel", "callback_data": f"act:{act_cancel}"}]
    ]}
    
    enqueue_outbox(tenant, chat_id, {"type": "message", "text": msg, "parse_mode": "HTML", "reply_markup": kb})

def handle_payment_action(tenant: str, chat_id: int, action_type: str, payload: dict):
    db = get_db()
    draft_id = payload.get("draft_id")
    
    if action_type == 'cancel_payment':
        db.execute("UPDATE payment_drafts SET status = 'cancelled', updated_at = NOW() WHERE draft_id = %s", (draft_id,))
        enqueue_outbox(tenant, chat_id, {"type": "message", "text": "🚫 Payment Draft Cancelled."})
        return

    expected_hash = payload.get("draft_hash")
    draft = db.fetchone("SELECT * FROM payment_drafts WHERE draft_id = %s AND tenant = %s", (draft_id, tenant))
    
    if not draft or draft["status"] != "drafted":
        enqueue_outbox(tenant, chat_id, {"type": "message", "text": "❌ Error: Draft not found or already processed."})
        return
        
    current_hash = generate_draft_hash(tenant, draft['iban'], draft['amount'], draft['currency'], draft['creditor_name'])
    if current_hash != expected_hash:
        enqueue_outbox(tenant, chat_id, {"type": "message", "text": "🚨 Security Alert: Invoice data was modified (TOCTOU). Confirmation blocked."})
        return
        
    db.execute("UPDATE payment_drafts SET status = 'user_confirmed', confirmed_by_chat_id = %s, updated_at = NOW() WHERE draft_id = %s", (chat_id, draft_id))
    db.execute("INSERT INTO payment_draft_events (id, draft_id, tenant, event_type, actor_chat_id) VALUES (%s, %s, %s, 'confirmed', %s)", (str(uuid.uuid4()), draft_id, tenant, chat_id))
    
    enqueue_outbox(tenant, chat_id, {"type": "message", "text": f"🟢 <b>Payment Confirmed</b>\n\n{draft['amount']} {draft['currency']} to {draft['creditor_name']} has been locked for bank execution.", "parse_mode": "HTML"})
