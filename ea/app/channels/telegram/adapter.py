from __future__ import annotations


class TelegramObservationAdapter:
    """Converts raw Telegram webhook/poll payloads into generic observation fields."""

    channel = "telegram"

    def to_observation_fields(self, update: dict[str, object]) -> dict[str, object]:
        msg = update.get("message") if isinstance(update, dict) else None
        if not isinstance(msg, dict):
            return {
                "principal_id": "unknown",
                "event_type": "telegram.update",
                "payload": dict(update if isinstance(update, dict) else {}),
            }
        chat = msg.get("chat")
        chat_id = ""
        if isinstance(chat, dict):
            chat_id = str(chat.get("id") or "")
        text = str(msg.get("text") or "")
        return {
            "principal_id": chat_id or "unknown",
            "event_type": "telegram.message",
            "payload": {
                "text": text,
                "message_id": msg.get("message_id"),
                "date": msg.get("date"),
                "raw": update,
            },
        }
