import os

EA_ATTACHMENTS_DIR = os.environ.get("EA_ATTACHMENTS_DIR", "/attachments")
EA_TENANTS_YAML = os.environ.get("EA_TENANTS_YAML", "/app/app/tenants.yml")

MARKUPGO_API_KEY = os.environ.get("MARKUPGO_API_KEY", "")
MARKUPGO_BASE_URL = os.environ.get("MARKUPGO_BASE_URL", "https://api.markupgo.com/api/v1")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# --- V2 Dynamic Settings Proxy ---
class _SettingsProxy:
    def __getattr__(self, name):
        val = globals().get(name)
        if val is not None: return val
        return __import__('os').environ.get(name)

settings = _SettingsProxy()
