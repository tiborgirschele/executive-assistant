from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def process_replay_once(*, replay_event_id: int, success: bool, error_text: str = "") -> None:
    db = get_db()
    row = db.fetchone("SELECT attempt_count FROM replay_events WHERE id = %s", (replay_event_id,))
    if not row:
        raise ValueError("replay_event_not_found")
    attempt = int(row["attempt_count"] or 0) + 1
    if success:
        db.execute(
            "UPDATE replay_events SET attempt_count=%s, status='completed', updated_at=%s WHERE id=%s",
            (attempt, _utcnow(), replay_event_id),
        )
        return
    status = "retry" if attempt < 3 else "deadletter"
    db.execute(
        """
        UPDATE replay_events
        SET attempt_count=%s, status=%s, last_error=%s, updated_at=%s
        WHERE id=%s
        """,
        (attempt, status, error_text[:500], _utcnow(), replay_event_id),
    )

