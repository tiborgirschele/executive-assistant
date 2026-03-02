import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_pool = None


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres:secure_db_pass_2026@ea-db:5432/ea")

def get_db():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, _database_url())
    
    class DBMgr:
        def execute(self, query, vars=None):
            conn = _pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(query, vars)
                conn.commit()
            finally:
                _pool.putconn(conn)
                
        def fetchone(self, query, vars=None):
            conn = _pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, vars)
                    res = cur.fetchone()
                conn.commit()
                return res
            finally:
                _pool.putconn(conn)
                
        def fetchall(self, query, vars=None):
            conn = _pool.getconn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, vars)
                    res = cur.fetchall()
                conn.commit()
                return res
            finally:
                _pool.putconn(conn)
    return DBMgr()


def init_db_sync() -> None:
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            tenant TEXT,
            component TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            payload JSONB
        );
        CREATE INDEX IF NOT EXISTS audit_log_ts_idx ON audit_log(ts DESC);
        """
    )


async def init_db(*args, **kwargs):
    init_db_sync()


@contextmanager
def connect():
    conn = psycopg2.connect(_database_url())
    try:
        yield conn
    finally:
        conn.close()


def connect_sync():
    return connect()


def log_to_db(tenant=None, component=None, event_type=None, message=None, payload=None):
    if not component or not event_type or not message:
        return
    get_db().execute(
        """
        INSERT INTO audit_log (tenant, component, event_type, message, payload)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        [tenant, component, event_type, message, psycopg2.extras.Json(payload or {})],
    )
