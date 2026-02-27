import os, psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_pool = None

def get_db():
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL", "postgresql://postgres:secure_db_pass_2026@ea-db:5432/ea")
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, url)
    
    class DBMgr:
        def __init__(self):
            self.conn = _pool.getconn()
        def __del__(self):
            try: _pool.putconn(self.conn)
            except: pass
        def execute(self, query, vars=None):
            with self.conn.cursor() as cur:
                cur.execute(query, vars)
            self.conn.commit()
        def fetchone(self, query, vars=None):
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, vars)
                res = cur.fetchone()
            self.conn.commit()
            return res
        def fetchall(self, query, vars=None):
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, vars)
                res = cur.fetchall()
            self.conn.commit()
            return res
    return DBMgr()
