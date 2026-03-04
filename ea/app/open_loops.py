import json, os, uuid, threading

LOOPS_FILE = "/attachments/open_loops.json"

class OpenLoops:
    _LOCK = threading.RLock()

    @classmethod
    def _load(cls):
        if not os.path.exists(LOOPS_FILE): return {}
        try:
            with open(LOOPS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    @classmethod
    def _save(cls, data):
        os.makedirs(os.path.dirname(LOOPS_FILE), exist_ok=True)
        tmp = LOOPS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, LOOPS_FILE)

    @classmethod
    def _ensure_tenant(cls, d, tenant):
        if tenant not in d: d[tenant] = {"shopping": [], "payments": [], "calendars": []}
        for k in ["shopping", "payments", "calendars"]:
            if k not in d[tenant]: d[tenant][k] = []

    @classmethod
    def add_shopping(cls, tenant: str, item: str):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            if item not in d[tenant]["shopping"]: d[tenant]["shopping"].append(item)
            cls._save(d)

    @classmethod
    def clear_shopping(cls, tenant: str):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            d[tenant]["shopping"] = []
            cls._save(d)

    @classmethod
    def add_payment(cls, tenant: str, desc: str, amount: str, iban: str, status: str = "ready"):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            pid = str(uuid.uuid4())[:8]
            d[tenant]["payments"].append({"id": pid, "desc": desc, "amount": amount, "iban": iban, "status": status})
            cls._save(d)
            return pid

    @classmethod
    def remove_payment(cls, tenant: str, pid: str):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            d[tenant]["payments"] = [p for p in d[tenant]["payments"] if p["id"] != pid]
            cls._save(d)

    @classmethod
    def add_calendar(cls, tenant: str, preview: str, events: list):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            cid = str(uuid.uuid4())[:8]
            d[tenant]["calendars"].append({"id": cid, "preview": preview, "events": events})
            cls._save(d)
            return cid

    @classmethod
    def remove_calendar(cls, tenant: str, cid: str):
        with cls._LOCK:
            d = cls._load()
            cls._ensure_tenant(d, tenant)
            d[tenant]["calendars"] = [c for c in d[tenant]["calendars"] if c["id"] != cid]
            cls._save(d)
            
    @classmethod
    def get_calendar(cls, tenant: str, cid: str):
        with cls._LOCK:
            d = cls._load()
            for c in d.get(tenant, {}).get("calendars", []):
                if c["id"] == cid: return c
            return None

    @classmethod
    def get_dashboard(cls, tenant: str):
        with cls._LOCK:
            d = cls._load().get(tenant, {})
        txt = ""
        btns = []
        
        if d.get("payments"):
            txt += "💳 <b>Pending Payments:</b>\n"
            for p in d["payments"]: 
                if p.get("status") == "needs_doc":
                    txt += f"  └ ⚠️ {p['desc']} (Needs PDF)\n"
                    btns.append([{"text": f"🛑 Drop Payment", "callback_data": f"drop_pay:{p['id']}"}])
                else:
                    txt += f"  └ {p['desc']} (€{p['amount']})\n"
                    btns.append([{"text": f"✅ Paid: {p['desc'][:15]}", "callback_data": f"mark_paid:{p['id']}"}])
                    
        if d.get("calendars"):
            txt += "🗓️ <b>Pending Calendar Imports:</b>\n"
            for c in d["calendars"]:
                txt += f"  └ Import Request ({len(c['events'])} events)\n"
                btns.append([{"text": "✅ Execute Cal Import", "callback_data": f"exec_cal:{c['id']}"}])
                btns.append([{"text": "🛑 Discard Cal Import", "callback_data": f"drop_cal:{c['id']}"}])
                
        if d.get("shopping"):
            txt += "🛒 <b>Shopping List:</b>\n"
            for s in d["shopping"]: txt += f"  └ {s}\n"
            btns.append([{"text": "🧹 Clear Shopping", "callback_data": "clear_shopping"}])
        
        if txt: txt = "🚨 <b>OPEN LOOPS (ACTION REQUIRED)</b>\n" + txt + "\n━━━━━━━━━━━━━━━━━━\n\n"
        return txt, btns
