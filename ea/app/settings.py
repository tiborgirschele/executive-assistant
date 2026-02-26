from __future__ import annotations
import os
from dataclasses import dataclass

def _int(name: str, default: int) -> int:
    try: return int(str(os.getenv(name, str(default))).strip())
    except Exception: return int(default)

def _float(name: str, default: float) -> float:
    try: return float(str(os.getenv(name, str(default))).strip())
    except Exception: return float(default)

def _str(name: str, default: str) -> str:
    return str(os.getenv(name, default) or default).strip()

@dataclass(frozen=True)
class Settings:
    tz: str = _str("TZ", _str("EA_TZ", "Europe/Vienna"))
    internal_port: int = _int("EA_INTERNAL_PORT", 8090)
    db_dsn: str = _str("EA_DB_DSN", _str("DATABASE_URL", f"postgresql://postgres:{_str('EA_DB_PASSWORD','ea')}@ea-db:5432/{_str('EA_DB_NAME','ea')}"))
    
    telegram_bot_token: str = _str("EA_TELEGRAM_BOT_TOKEN", _str("TELEGRAM_BOT_TOKEN", ""))
    telegram_poll_timeout_s: int = _int("EA_TELEGRAM_POLL_TIMEOUT_S", 30)
    telegram_poll_backoff_s: int = _int("EA_TELEGRAM_POLL_BACKOFF_S", 10)
    
    tenants_yaml: str = _str("EA_TENANTS_YAML", "/config/tenants.yml")
    places_yaml: str = _str("EA_PLACES_YAML", "/config/places.yml")
    attachments_dir: str = _str("EA_ATTACHMENTS_DIR", "/attachments")
    docker_sock: str = _str("EA_DOCKER_SOCK", "/var/run/docker.sock")
    
    litellm_base_url: str = _str("EA_LITELLM_BASE_URL", "http://litellm:4000")
    litellm_api_key: str = _str("EA_LITELLM_API_KEY", "")
    llm_model: str = _str("EA_LLM_MODEL", "gemini/gemini-2.0-flash")
    
    location_poll_interval_s: float = _float("EA_LOCATION_POLL_INTERVAL_S", 30.0)
    default_location_cooldown_min: int = _int("EA_DEFAULT_LOCATION_COOLDOWN_MIN", 180)
    daily_briefing_time: str = _str("EA_DAILY_BRIEFING_TIME", "07:30")
    
    calendar_ics_secret: str = _str("EA_CALENDAR_ICS_SECRET", "")
    calendar_lookahead_hours: int = _int("EA_CALENDAR_LOOKAHEAD_HOURS", 24)
    calendar_remind_soon_min: int = _int("EA_CALENDAR_REMIND_SOON_MIN", 10)
    calendar_leave_buffer_min: int = _int("EA_CALENDAR_LEAVE_BUFFER_MIN", 10)
    calendar_loop_interval_s: float = _float("EA_CALENDAR_LOOP_INTERVAL_S", 60.0)
    calendar_default_duration_min: int = _int("EA_CALENDAR_DEFAULT_DURATION_MIN", 45)

    # ADDED: Keyring password required to unlock OpenClaw credentials
    gog_keyring_password: str = _str("EA_GOG_KEYRING_PASSWORD", "rangersofB5")

settings = Settings()