from __future__ import annotations
import json, time
from contextlib import contextmanager
import psycopg
from app.settings import settings

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tenant TEXT NULL,
  component TEXT NOT NULL,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_ts ON audit_events (tenant, ts DESC);

CREATE TABLE IF NOT EXISTS telegram_updates (
  update_id BIGINT PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_polls (
  poll_id TEXT PRIMARY KEY,
  message_id BIGINT NULL,
  chat_id BIGINT NULL,
  tenant TEXT NULL,
  options JSONB NOT NULL,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS poll_actions (
  poll_id TEXT NOT NULL,
  option_text TEXT NOT NULL,
  action_type TEXT NOT NULL,
  action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (poll_id, option_text)
);

CREATE TABLE IF NOT EXISTS poll_answer_state (
  poll_id TEXT NOT NULL,
  user_id BIGINT NOT NULL,
  selected JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (poll_id, user_id)
);

CREATE TABLE IF NOT EXISTS telegram_messages (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  chat_id BIGINT NULL,
  user_id BIGINT NULL,
  text TEXT NULL,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_ts ON telegram_messages (ts DESC);

CREATE TABLE IF NOT EXISTS location_events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tenant TEXT NOT NULL,
  lat DOUBLE PRECISION NULL,
  lon DOUBLE PRECISION NULL,
  accuracy DOUBLE PRECISION NULL,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_location_events_tenant_ts ON location_events (tenant, ts DESC);

CREATE TABLE IF NOT EXISTS location_cursors (
  tenant TEXT PRIMARY KEY,
  last_id BIGINT NOT NULL DEFAULT 0,
  updated_ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS location_notifications (
  id BIGSERIAL PRIMARY KEY,
  tenant TEXT NOT NULL,
  place_id TEXT NOT NULL,
  suggestion_key TEXT NOT NULL,
  sent_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_location_notifications_tenant_ts ON location_notifications (tenant, sent_ts DESC);

CREATE TABLE IF NOT EXISTS whatsapp_memory (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tenant TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'summary',
  text TEXT NOT NULL,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_whatsapp_memory_tenant_ts ON whatsapp_memory (tenant, ts DESC);

CREATE TABLE IF NOT EXISTS shopping_list (
  id BIGSERIAL PRIMARY KEY,
  tenant TEXT NOT NULL,
  item TEXT NOT NULL,
  checked BOOLEAN NOT NULL DEFAULT FALSE,
  updated_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_shopping_list_tenant_checked ON shopping_list (tenant, checked);

CREATE TABLE IF NOT EXISTS preferences (
  tenant TEXT NOT NULL,
  key TEXT NOT NULL,
  value JSONB NOT NULL,
  updated_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant, key)
);
"""

@contextmanager
def connect():
    conn = psycopg.connect(settings.db_dsn)
    try:
        yield conn
    finally:
        conn.close()

def init_db(max_wait_s: int = 40) -> None:
    start = time.time()
    last_err = None
    while True:
        try:
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(SCHEMA_SQL)
                conn.commit()
            return
        except Exception as e:
            last_err = e
            if time.time() - start > max_wait_s:
                raise RuntimeError(f"DB init failed after {max_wait_s}s: {last_err}")
            time.sleep(2)

def log_to_db(tenant: str | None, component: str, event_type: str, message: str, payload: dict) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_events (tenant, component, event_type, message, payload) VALUES (%s,%s,%s,%s,%s)",
                (tenant, component, event_type, message, json.dumps(payload or {})),
            )
        conn.commit()

def upsert_preference(tenant: str, key: str, value: dict) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO preferences (tenant, key, value, updated_ts)
                VALUES (%s,%s,%s,NOW())
                ON CONFLICT (tenant, key)
                DO UPDATE SET value=EXCLUDED.value, updated_ts=NOW()
                """,
                (tenant, key, json.dumps(value or {})),
            )
        conn.commit()
