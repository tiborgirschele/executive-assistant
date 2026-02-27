import yaml, os, json

class TenantConfig(dict):
    def __getattr__(self, key): return self.get(key)
    def __setattr__(self, key, value): self[key] = value

def load_tenants():
    for p in ["/app/config.yaml", "/app/tenants.yaml", "config.yaml", "tenants.yaml", "/docker/EA/tenants.yaml"]:
        if os.path.exists(p):
            try:
                with open(p, "r") as f: data = yaml.safe_load(f) or {}
                tenants = {k: TenantConfig(v) for k, v in data.get("tenants", {}).items() if isinstance(v, dict)}
                for k, v in tenants.items(): v['key'] = k
                return tenants, data.get("telegram", {}), data.get("system", {})
            except: pass
            
    # RESTORED: Hardcoded Admin Fallback so you NEVER get locked out!
    fallback = TenantConfig({
        'key': 'tibor',
        'label': 'Tibor',
        'openclaw_container': 'openclaw-gateway-tibor',
        'google_account': 'tibor.girschele@gmail.com',
        'family_openclaw_container': 'openclaw-gateway-family-girschele',
        'include_family': True
    })
    return {'tibor': fallback}, {}, {}

def get_tenant(chat_id):
    tenants, tg_cfg, _ = load_tenants()
    
    if isinstance(tg_cfg, dict) and 'allowed_chats' in tg_cfg:
        for k, v in tg_cfg['allowed_chats'].items():
            if str(v) == str(chat_id): return tenants.get(k, tenants.get('tibor'))
    for name, t in tenants.items():
        if str(t.get("telegram_chat_id", "")) == str(chat_id): return t
        
    try:
        with open("/attachments/dynamic_users.json", "r") as f:
            users = json.load(f)
            if str(chat_id) in users:
                u = users[str(chat_id)]
                if u.get("is_admin"):
                    t = tenants.get('tibor', TenantConfig({'key': 'tibor', 'label': 'Tibor', 'openclaw_container': 'openclaw-gateway-tibor'}))
                    t['telegram_chat_id'] = chat_id
                    t['google_account'] = u.get("email", t.get('google_account'))
                    return t
                return TenantConfig({
                    "key": f"user_{chat_id}",
                    "label": u.get("name", f"User {chat_id}"),
                    "telegram_chat_id": chat_id,
                    "google_account": u.get("email", ""),
                    "openclaw_container": "openclaw-gateway-tibor",
                    "include_family": False
                })
    except: pass
    
    # AUTO-ADMIN BOOTSTRAP: If dynamic_users is empty, you claim Admin automatically!
    if not os.path.exists("/attachments/dynamic_users.json"):
        os.makedirs("/attachments", exist_ok=True)
        with open("/attachments/dynamic_users.json", "w") as f:
            json.dump({str(chat_id): {"name": "Tibor (Admin)", "email": "tibor.girschele@gmail.com", "is_admin": True}}, f)
        t = tenants.get('tibor', TenantConfig({'key': 'tibor', 'label': 'Tibor', 'openclaw_container': 'openclaw-gateway-tibor'}))
        t['telegram_chat_id'] = chat_id
        return t
        
    return None

def get_admin_chat_id():
    tenants, tg_cfg, _ = load_tenants()
    if isinstance(tg_cfg, dict) and 'allowed_chats' in tg_cfg:
        for v in tg_cfg['allowed_chats'].values(): return str(v)
    try:
        with open("/attachments/dynamic_users.json", "r") as f:
            for cid, u in json.load(f).items():
                if u.get("is_admin"): return str(cid)
    except: pass
    if 'tibor' in tenants and tenants['tibor'].get('telegram_chat_id'): return str(tenants['tibor']['telegram_chat_id'])
    return None

def tenant_by_chat_id(chat_id):
    t = get_tenant(chat_id)
    return t.key if t else None
