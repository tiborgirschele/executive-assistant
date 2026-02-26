from __future__ import annotations
import json, uuid
from datetime import datetime, timedelta, timezone
from app.db import connect

def ensure_schema():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ea_action_context (
                    id TEXT PRIMARY KEY,
                    payload TEXT,
                    expires_at TIMESTAMPTZ
                );
                CREATE TABLE IF NOT EXISTS ea_auth_sessions (
                    chat_id BIGINT PRIMARY KEY,
                    email TEXT,
                    container TEXT,
                    services TEXT,
                    expires_at TIMESTAMPTZ
                );
            """)
        conn.commit()

def save_action(payload: str, ttl_s: int=86400) -> str:
    try:
        ensure_schema()
        aid = str(uuid.uuid4())[:8]
        exp = datetime.now(timezone.utc) + timedelta(seconds=ttl_s)
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO ea_action_context (id, payload, expires_at) VALUES (%s, %s, %s)", (aid, payload, exp))
            conn.commit()
        return aid
    except Exception as e:
        print(f"DB Action Save Error: {e}")
        return "error"

def get_action(aid: str) -> str | None:
    try:
        ensure_schema()
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM ea_action_context WHERE id=%s AND expires_at > NOW()", (aid,))
                row = cur.fetchone()
                if row: return row["payload"] if isinstance(row, dict) else row[0]
    except: pass
    return None

def set_auth(chat_id: int, email: str, container: str, services: str):
    try:
        ensure_schema()
        exp = datetime.now(timezone.utc) + timedelta(minutes=15)
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ea_auth_sessions (chat_id, email, container, services, expires_at) 
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (chat_id) DO UPDATE SET email=EXCLUDED.email, container=EXCLUDED.container, services=EXCLUDED.services, expires_at=EXCLUDED.expires_at
                """, (chat_id, email, container, services, exp))
            conn.commit()
    except Exception as e: print(f"DB Auth Save Error: {e}")

def get_and_clear_auth(chat_id: int) -> dict | None:
    try:
        ensure_schema()
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT email, container, services FROM ea_auth_sessions WHERE chat_id=%s AND expires_at > NOW()", (chat_id,))
                row = cur.fetchone()
                if row:
                    cur.execute("DELETE FROM ea_auth_sessions WHERE chat_id=%s", (chat_id,))
                    conn.commit()
                    return dict(row) if isinstance(row, dict) else {"email": row[0], "container": row[1], "services": row[2]}
    except: pass
    return None

def clear_auth(chat_id: int):
    try:
        ensure_schema()
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ea_auth_sessions WHERE chat_id=%s", (chat_id,))
            conn.commit()
    except: pass
