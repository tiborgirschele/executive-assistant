from __future__ import annotations
import json
from datetime import datetime, timezone
from app.db import log_to_db

def log_event(tenant: str | None, component: str, event_type: str, message: str, payload: dict | None = None) -> None:
    payload = payload or {}
    # stdout for docker logs
    try:
        print(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "tenant": tenant,
            "component": component,
            "event_type": event_type,
            "message": message,
            "payload": payload
        }, ensure_ascii=False))
    except Exception:
        pass
    try:
        log_to_db(tenant, component, event_type, message, payload)
    except Exception:
        pass
