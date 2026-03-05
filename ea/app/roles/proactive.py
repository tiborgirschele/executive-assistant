from __future__ import annotations

import asyncio
import os

from app.config import load_tenants
from app.planner.proactive import ProactivePlanner


def _tenant_keys() -> list[str]:
    raw = str(os.environ.get("EA_PROACTIVE_TENANTS") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    tenants, _tg, _sys = load_tenants()
    return [str(k).strip() for k in sorted((tenants or {}).keys()) if str(k).strip()]


async def run_proactive() -> None:
    print("==================================================", flush=True)
    print("🧭 EA OS PROACTIVE ROLE: ONLINE", flush=True)
    print("==================================================", flush=True)
    tick_sec = max(15, int(os.environ.get("EA_PROACTIVE_TICK_SEC") or 120))
    while True:
        keys = _tenant_keys()
        if not keys:
            await asyncio.sleep(tick_sec)
            continue
        try:
            planner = ProactivePlanner()
        except Exception as err:
            print(f"⚠️ proactive planner init failed: {err}", flush=True)
            await asyncio.sleep(tick_sec)
            continue
        for tenant_key in keys:
            try:
                queued = planner.deterministic_prefilter(tenant_key=tenant_key)
                scored = planner.score_with_budget(tenant_key=tenant_key, candidates=queued)
                created = planner.schedule_items(tenant_key=tenant_key, scored=scored)
                if created:
                    print(
                        f"🧭 proactive scheduled tenant={tenant_key} items={len(created)} first={created[0]}",
                        flush=True,
                    )
            except Exception as err:
                print(f"⚠️ proactive tick failed tenant={tenant_key}: {err}", flush=True)
        await asyncio.sleep(tick_sec)


if __name__ == "__main__":
    asyncio.run(run_proactive())
