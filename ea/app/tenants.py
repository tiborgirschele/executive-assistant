import os, yaml
from dataclasses import dataclass
from typing import Dict, List
from app.settings import settings

@dataclass(frozen=True)
class Tenant:
    name: str
    bot_token: str
    allow_chat_ids: List[int]
    openclaw_container: str | None
    templates: dict

def load_tenants(tenants_yaml_path: str) -> dict[str, Tenant]:
    try:
        with open(tenants_yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except:
        raw = {}
    
    tenants: dict[str, Tenant] = {}
    for name, cfg in raw.items():
        tg = (cfg or {}).get("telegram", {}) or {}
        token_env = tg.get("bot_token_env")
        token = os.environ.get(token_env) if token_env else tg.get("bot_token")
        allow = [int(x) for x in (tg.get("allow_chat_ids") or [])]
        oc = (cfg or {}).get("openclaw", {}) or {}
        templates = (cfg or {}).get("templates", {}) or {}
        
        tenants[name] = Tenant(
            name=name,
            bot_token=token or settings.telegram_bot_token,
            allow_chat_ids=allow,
            openclaw_container=oc.get("docker_container"),
            templates=templates,
        )
    return tenants

def build_chat_index(tenants: dict[str, Tenant]) -> Dict[int, str]:
    idx: Dict[int, str] = {}
    for t in tenants.values():
        for cid in t.allow_chat_ids:
            if cid in idx and idx[cid] != t.name:
                pass # Ignore conflict logging for now
            idx[cid] = t.name
    return idx

_tenants_cache = load_tenants(settings.tenants_yaml)
_chat_index = build_chat_index(_tenants_cache)

def resolve_tenant(chat_id: int) -> str:
    return _chat_index.get(int(chat_id), "")
