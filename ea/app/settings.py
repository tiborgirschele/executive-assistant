from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str
    role: str
    host: str
    port: int
    log_level: str
    ledger_backend: str
    database_url: str


def get_settings() -> Settings:
    app_name = (os.environ.get("EA_APP_NAME") or "ea-rewrite").strip() or "ea-rewrite"
    role = (os.environ.get("EA_ROLE") or "api").strip().lower() or "api"
    host = (os.environ.get("EA_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    try:
        port = int(os.environ.get("EA_PORT") or "8090")
    except Exception:
        port = 8090
    log_level = (os.environ.get("EA_LOG_LEVEL") or "INFO").strip().upper() or "INFO"
    ledger_backend = (os.environ.get("EA_LEDGER_BACKEND") or "auto").strip().lower() or "auto"
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    return Settings(
        app_name=app_name,
        role=role,
        host=host,
        port=max(1, min(65535, port)),
        log_level=log_level,
        ledger_backend=ledger_backend,
        database_url=database_url,
    )
