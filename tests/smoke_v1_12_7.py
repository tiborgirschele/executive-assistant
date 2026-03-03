from __future__ import annotations

import importlib
import os
import sys
import types

ROOT = os.environ.get('EA_PYTHONPATH_ROOT')
if ROOT:
    sys.path.insert(0, ROOT)
else:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ea_root = os.path.join(repo_root, "ea")
    if ea_root not in sys.path:
        sys.path.insert(0, ea_root)


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

from app.telegram.safety import (  # noqa: E402
    SAFE_PLACEHOLDER_COPY,
    SAFE_SIMPLIFIED_COPY,
    detect_forbidden_pattern,
    sanitize_telegram_text,
)

assert detect_forbidden_pattern('{"error": {"message": "template_id invalid"}}') in {'json_block', 'template_id'}
assert sanitize_telegram_text('{"error": {"message": "template_id invalid"}}') == SAFE_SIMPLIFIED_COPY
assert sanitize_telegram_text('Traceback (most recent call last):\nNameError: boom') == SAFE_SIMPLIFIED_COPY
assert sanitize_telegram_text(SAFE_PLACEHOLDER_COPY, placeholder=True) == SAFE_PLACEHOLDER_COPY

# Import the safety module explicitly.
importlib.import_module('app.telegram.safety')
print('SMOKE_OK safety module')
