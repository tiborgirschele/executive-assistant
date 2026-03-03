from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ea"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_import_stubs() -> None:
    if "httpx" not in sys.modules:
        httpx = types.ModuleType("httpx")

        class _AsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        httpx.AsyncClient = _AsyncClient
        sys.modules["httpx"] = httpx

    if "psycopg2" not in sys.modules:
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


_install_import_stubs()

from app.roles.outbox import _is_telegram_entity_parse_error, _strip_telegram_html


def main() -> None:
    err = '{"ok":false,"description":"Bad Request: can\'t parse entities: Unsupported start tag \"pre\""}'
    assert _is_telegram_entity_parse_error(400, err)
    assert not _is_telegram_entity_parse_error(500, err)
    assert not _is_telegram_entity_parse_error(400, "random 400")

    cleaned = _strip_telegram_html("<b>Hello</b> <pre>bad</pre> &amp; <i>world</i>")
    assert "<b>" not in cleaned
    assert "<pre>" not in cleaned
    assert "Hello" in cleaned
    assert "bad" in cleaned
    assert "&" in cleaned

    print("PASS: outbox entity-fallback helpers")


if __name__ == "__main__":
    main()
