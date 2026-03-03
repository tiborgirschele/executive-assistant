from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ea"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_psycopg2_stub() -> None:
    if "psycopg2" in sys.modules:
        return

    psycopg2 = types.ModuleType("psycopg2")
    pool_mod = types.ModuleType("psycopg2.pool")
    extras_mod = types.ModuleType("psycopg2.extras")

    class _ThreadedConnectionPool:
        def __init__(self, *args, **kwargs):
            pass

        def getconn(self):
            raise RuntimeError("psycopg2 stub connection requested")

        def putconn(self, _conn):
            return None

    class _RealDictCursor:
        pass

    pool_mod.ThreadedConnectionPool = _ThreadedConnectionPool
    extras_mod.RealDictCursor = _RealDictCursor
    psycopg2.pool = pool_mod
    psycopg2.extras = extras_mod
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.pool"] = pool_mod
    sys.modules["psycopg2.extras"] = extras_mod


_install_psycopg2_stub()

import app.queue as q


class _FakeDB:
    def __init__(self) -> None:
        self.last_query = ""

    def fetchone(self, query: str):
        self.last_query = query
        return None


def main() -> None:
    fake = _FakeDB()
    original = q.get_db
    try:
        q.get_db = lambda: fake
        assert q.claim_update() is None
        claim_update_query = " ".join(fake.last_query.split()).lower()
        assert "status='processing'" in claim_update_query
        assert "updated_at < now() - interval '15 minutes'" in claim_update_query

        fake.last_query = ""
        assert q.claim_outbox_message() is None
        claim_outbox_query = " ".join(fake.last_query.split()).lower()
        assert "status='processing'" in claim_outbox_query
        assert "updated_at < now() - interval '15 minutes'" in claim_outbox_query
    finally:
        q.get_db = original

    print("PASS: queue reclaim stale processing")


if __name__ == "__main__":
    main()
