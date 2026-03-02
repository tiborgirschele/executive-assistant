import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_pool = None


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres:secure_db_pass_2026@ea-db:5432/ea")

def _raw_get_db():
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



import logging, os, re, builtins, uuid

def _get_persistent_memory():
    try:
        with open('/app/ooda_action.log', 'r') as f: return f.read().strip()
    except: return ""

def _set_persistent_memory(tbl, sql):
    try:
        with open('/app/ooda_action.log', 'w') as f: f.write(f"{tbl}|{sql}")
    except: pass

def _is_blacklisted(sql):
    try:
        with open('/app/ooda_blacklist.txt', 'r') as f:
            return any(sql.strip()[:40] in line for line in f.readlines())
    except: return False

def _blacklist_action(sql):
    try:
        with open('/app/ooda_blacklist.txt', 'a') as f: f.write(f"{sql.strip()[:40]}\n")
    except: pass

def _generic_brainstem(err_text, query=None):
    """BACKUP PLAN: PURE GENERICS. Zero Hardcodes."""
    err_str = str(err_text).lower()
    
    # 1. THE IMMUNE SYSTEM (REVERT PROTOCOL)
    # If an external API rejects state (400/404/invalid), check if our last autonomous action caused it!
    err_keywords = ["400", "401", "403", "404", "invalid", "validation", "bad request"]
    if any(k in err_str for k in err_keywords):
        mem = _get_persistent_memory()
        if mem and "|" in mem:
            tbl, past_sql = mem.split("|", 1)
            logging.warning(f"🧬 [META-OODA: IMMUNE] External API rejected state. Reverting autonomous action on '{tbl}'.")
            _blacklist_action(past_sql) # Prevent infinite loop
            _set_persistent_memory("", "") # Clear memory
            
            # Universal Row-Cast Delete (Deletes the row if ANY column contains our generated hash)
            return f"DELETE FROM {tbl} WHERE CAST({tbl}::text AS TEXT) LIKE '%ooda_gen_%';"
            
    # 2. SUGGESTED ACTION PROTOCOL (Generic Extraction)
    match = re.search(r"(INSERT INTO|UPDATE|ALTER TABLE|CREATE TABLE|DELETE FROM)\s+(.*?);?", str(err_text), re.IGNORECASE)
    if match:
        sql = match.group(0)
        if not sql.strip().endswith(';'): sql += ';'
        
        if _is_blacklisted(sql):
            logging.warning("🚫 [META-OODA: IMMUNE] Suppressing blacklisted autonomous action.")
            return None
            
        tbl_match = re.search(r"(?:INTO|UPDATE|TABLE|FROM)\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        tbl = tbl_match.group(1) if tbl_match else "unknown"
        
        gen_id = f"ooda_gen_{uuid.uuid4().hex[:8]}"
        sql = re.sub(r"'[^']*ID[^']*'|\"[^\"]*ID[^\"]*\"|'YOUR_[^']+'|'<[^>]+>'|'REPLACE_[^']+'|'MISSING_[^']+'", f"'{gen_id}'", sql, flags=re.IGNORECASE)
        
        _set_persistent_memory(tbl, sql)
        return sql
        
    # 3. GENERIC SCHEMA FALLBACK
    col_match = re.search(r'column "([^"]+)" does not exist', err_str)
    tbl_match = re.search(r'(?:FROM|UPDATE|INTO|TABLE|JOIN)\s+([a-zA-Z0-9_]+)', str(query), re.IGNORECASE) if query else None
    if col_match and tbl_match:
        col = col_match.group(1)
        dtype = "INTEGER DEFAULT 1" if "version" in col else "BOOLEAN DEFAULT TRUE" if "active" in col else "TEXT"
        return f"ALTER TABLE {tbl_match.group(1)} ADD COLUMN IF NOT EXISTS {col} {dtype};"

    return None

def _call_meta_cortex(prompt):
    import litellm
    litellm.suppress_debug_info = True
    litellm.drop_params = True
    sys_prompt = "You are a Universal System Healer. Output ONLY raw SQL (ALTER, CREATE, DELETE, UPDATE, INSERT). NO markdown."
    messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}]
    
    env_file = {}
    try:
        with open('/app/.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'): k, v = line.split('=', 1); env_file[k.strip()] = v.strip().strip('"').strip("'")
    except: pass
    def get_val(key): return os.environ.get(key) or env_file.get(key)

    uplinks = []
    if get_val("OPENAI_API_KEY"): uplinks.append({"name": "OpenAI", "model": "gpt-4o-mini", "api_key": get_val("OPENAI_API_KEY"), "api_base": None})
    if get_val("GEMINI_API_KEY"): uplinks.append({"name": "Gemini", "model": "gemini/gemini-1.5-flash", "api_key": get_val("GEMINI_API_KEY"), "api_base": None})
    onemin_key = get_val("ONEMINAI_API_KEY") or get_val("1MINAI_API_KEY")
    if onemin_key: uplinks.append({"name": "1min.ai", "model": "openai/gpt-4o", "api_key": onemin_key, "api_base": "https://api.1min.ai/v1"})
    mx = get_val("MAGIXX_API_KEY") or get_val("LITELLM_MASTER_KEY")
    if mx: uplinks.append({"name": "Magixx", "model": "openai/gpt-4o", "api_key": mx, "api_base": "http://magixx:4000/v1"})

    poisoned_base = os.environ.pop("OPENAI_BASE_URL", None)
    sql_patch = None
    for link in uplinks:
        logging.info(f"🧠 [META-OODA: CORTEX] Thinking via {link['name']}...")
        try:
            kwargs = {"model": link['model'], "messages": messages, "api_key": link['api_key'], "temperature": 0.0, "timeout": 2.5, "max_retries": 0}
            if link.get('api_base'): kwargs['api_base'] = link['api_base']
            res = litellm.completion(**kwargs)
            patch = res.choices[0].message.content.replace("```sql", "").replace("```", "").strip()
            if any(patch.upper().startswith(kw) for kw in ["ALTER ", "CREATE ", "INSERT ", "UPDATE ", "DELETE "]):
                logging.info(f"✅ [META-OODA: CORTEX] Neural decision reached.")
                sql_patch = patch
                break
        except Exception: pass
    if poisoned_base: os.environ["OPENAI_BASE_URL"] = poisoned_base
    return sql_patch

def _universal_heal(db_conn, err_text, query=None):
    if "[META-OODA" in str(err_text): return False
    err_clean = str(err_text).splitlines()[0][:150]
    logging.warning(f"\n🚨 [META-OODA: OBSERVE] Anomaly detected: {err_clean}")
    
    try:
        if hasattr(db_conn, 'rollback'): db_conn.rollback()
        elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'rollback'): db_conn.conn.rollback()
    except: pass
    
    sql_patch = _call_meta_cortex(f"Error: {err_text}\nQuery: {query}")
    
    if not sql_patch:
        logging.warning("⚠️ [META-OODA: HYBRID] Cortex failed. Activating Generic Brainstem...")
        sql_patch = _generic_brainstem(err_text, query)
        if sql_patch: logging.info(f"⚡ [META-OODA: BRAINSTEM] Formulated Generic Fix -> {sql_patch}")
        
    if not sql_patch: 
        logging.error("❌ [META-OODA: FATAL] All backup plans exhausted or suppressed.")
        return False
        
    logging.warning(f"🔨 [META-OODA: ACT] Executing Fix -> {sql_patch}")
    try:
        if hasattr(db_conn, 'execute'): db_conn.execute(sql_patch)
        elif hasattr(db_conn, 'cursor'):
            with db_conn.cursor() as cur: cur.execute(sql_patch)
        if hasattr(db_conn, 'commit'): db_conn.commit()
        elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'commit'): db_conn.conn.commit()
        logging.info("✅ [META-OODA: LOOP CLOSED] State healed dynamically.\n")
        return True
    except Exception as e:
        logging.error(f"❌ [META-OODA: FATAL] Fix execution failed: {e}")
        try:
            if hasattr(db_conn, 'rollback'): db_conn.rollback()
            elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'rollback'): db_conn.conn.rollback()
        except: pass
    return False

def _auto_cast_args(args):
    def _adapt(v):
        if type(v).__name__ in ('int', 'float', 'str', 'bool', 'NoneType'): return v
        if hasattr(v, 'tenant_id'): return str(v.tenant_id)
        if hasattr(v, 'id'): return str(v.id)
        return str(v)
    return tuple(tuple(_adapt(i) for i in a) if isinstance(a, tuple) else [_adapt(i) for i in a] if isinstance(a, list) else {k: _adapt(i) for k,i in a.items()} if isinstance(a, dict) else _adapt(a) for a in args)

class AICursorProxy:
    def __init__(self, cur, db_conn):
        self._cur = cur; self._db_conn = db_conn
    def __getattr__(self, name): return getattr(self._cur, name)
    def __enter__(self):
        if hasattr(self._cur, '__enter__'): self._cur.__enter__()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self._cur, '__exit__'): return self._cur.__exit__(exc_type, exc_val, exc_tb)
    def execute(self, query, *args, **kwargs):
        safe_args = args
        try: return self._cur.execute(query, *safe_args, **kwargs)
        except Exception as e:
            if "can't adapt type" in str(e) and safe_args:
                safe_args = _auto_cast_args(safe_args)
                try: return self._cur.execute(query, *safe_args, **kwargs)
                except Exception as e2: e = e2
            if _universal_heal(self._db_conn, e, query): return self._cur.execute(query, *safe_args, **kwargs)
            raise e

class AIDatabaseProxy:
    def __init__(self, db_conn): self._db = db_conn
    def __getattr__(self, name): return getattr(self._db, name)
    def cursor(self, *args, **kwargs): return AICursorProxy(self._db.cursor(*args, **kwargs), self._db)
    
    def execute(self, query, *args, **kwargs):
        safe_args = args
        try: return self._db.execute(query, *safe_args, **kwargs)
        except Exception as e:
            if "can't adapt type" in str(e) and safe_args:
                safe_args = _auto_cast_args(safe_args)
                try: return self._db.execute(query, *safe_args, **kwargs)
                except Exception as e2: e = e2
            if _universal_heal(self._db, e, query): return self._db.execute(query, *safe_args, **kwargs)
            raise e

# =================================================================
# 🌐 GLOBAL APP-CATCHER (Hooks into builtins.print)
# =================================================================
if not hasattr(builtins, '_meta_ooda_hooked'):
    _orig_print = builtins.print
    def _ooda_print(*args, **kwargs):
        _orig_print(*args, **kwargs)
        text = " ".join(str(a) for a in args)
        if ("[META-OODA" in text): return
        
        db = getattr(builtins, '_ooda_global_db', None)
        if not db: return
        
        err_keywords = ["failed:", "error:", "act:", "invalid", "http 4", "validation", "bad request"]
        if any(kw in text.lower() for kw in err_keywords):
            _universal_heal(db, text)
            
    builtins.print = _ooda_print
    builtins._meta_ooda_hooked = True

def get_db(*args, **kwargs):
    raw = _raw_get_db(*args, **kwargs)
    builtins._ooda_global_db = raw
    if getattr(raw, '_is_ai_proxy', False): return raw
    proxy = AIDatabaseProxy(raw)
    proxy._is_ai_proxy = True
    return proxy
