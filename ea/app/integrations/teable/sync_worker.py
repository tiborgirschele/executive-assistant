from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

DEFAULT_TEABLE_API_BASE_URL = "https://app.teable.ai/api"
LEGACY_TEABLE_API_BASE_URL = "https://app.teable.io/api"

TEABLE_TOKEN = str(os.environ.get("TEABLE_TOKEN") or "").strip()
TEABLE_BASE_ID = str(os.environ.get("TEABLE_BASE_ID") or "").strip()
TEABLE_SYNC_POLL_SEC = max(5, int(os.environ.get("EA_TEABLE_SYNC_POLL_SEC") or 15))
ATTACHMENTS_DIR = str(os.environ.get("EA_ATTACHMENTS_DIR") or "/attachments").strip() or "/attachments"
BRAIN_PATH = str(os.environ.get("EA_BRAIN_PATH") or os.path.join(ATTACHMENTS_DIR, "brain.json"))
STATE_PATH = str(os.environ.get("EA_TEABLE_SYNC_STATE_PATH") or os.path.join(ATTACHMENTS_DIR, "teable_sync_state.json"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_teable_base_url(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip() or DEFAULT_TEABLE_API_BASE_URL
    candidate = candidate.rstrip("/")
    if candidate.startswith("https://app.teable.io"):
        candidate = candidate.replace("https://app.teable.io", "https://app.teable.ai", 1)
    if not candidate.endswith("/api"):
        candidate = f"{candidate}/api"
    return candidate


TEABLE_API_BASE_URL = resolve_teable_base_url(os.environ.get("TEABLE_API_BASE_URL"))


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _save_json(path: str, payload: Any) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_sync_state(path: str) -> dict[str, Any]:
    raw = _load_json(path, {"synced_concepts": [], "updated_at": None, "skipped_concepts": {}})
    if isinstance(raw, list):
        return {"synced_concepts": [str(x) for x in raw if str(x).strip()], "updated_at": None, "skipped_concepts": {}}
    if not isinstance(raw, dict):
        return {"synced_concepts": [], "updated_at": None, "skipped_concepts": {}}
    synced = raw.get("synced_concepts")
    if isinstance(synced, list):
        sync_list = [str(x) for x in synced if str(x).strip()]
    else:
        sync_list = []
    skipped = raw.get("skipped_concepts")
    return {
        "synced_concepts": sync_list,
        "updated_at": raw.get("updated_at"),
        "skipped_concepts": skipped if isinstance(skipped, dict) else {},
    }


def _safe_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(os.environ.get("EA_TEABLE_SYNC_DEFAULT_CONFIDENCE") or 0.80)
    return max(0.0, min(parsed, 1.0))


def _looks_runtime_dump(text: str) -> bool:
    sample = str(text or "")
    low = sample.lower()
    if len(sample) > 6000:
        return True
    dump_markers = (
        "traceback",
        "\"role\":",
        "tool_call",
        "[options:",
        "fatal event loop deadlock",
    )
    return sum(1 for marker in dump_markers if marker in low) >= 2


def build_memory_record_fields(concept: str, raw_fact: Any) -> dict[str, Any] | None:
    concept_clean = str(concept or "").strip()[:120]
    if not concept_clean:
        return None

    source = "brain_json"
    confidence = _safe_confidence(None)
    last_verified = _utc_now_iso()
    sensitivity = str(os.environ.get("EA_TEABLE_SYNC_SENSITIVITY") or "personal")
    sharing_policy = str(os.environ.get("EA_TEABLE_SYNC_SHARING") or "private")
    reviewer = str(os.environ.get("EA_TEABLE_SYNC_REVIEWER") or "ea-runtime")
    core_fact = ""

    if isinstance(raw_fact, dict):
        core_fact = str(
            raw_fact.get("core_fact")
            or raw_fact.get("fact")
            or raw_fact.get("value")
            or ""
        ).strip()
        source = str(raw_fact.get("source") or source).strip() or source
        confidence = _safe_confidence(raw_fact.get("confidence"))
        last_verified = str(raw_fact.get("last_verified") or last_verified).strip() or last_verified
        sensitivity = str(raw_fact.get("sensitivity") or sensitivity).strip() or sensitivity
        sharing_policy = str(raw_fact.get("sharing_policy") or sharing_policy).strip() or sharing_policy
        reviewer = str(raw_fact.get("reviewer") or reviewer).strip() or reviewer
    elif isinstance(raw_fact, str):
        core_fact = raw_fact.strip()
    else:
        return None

    if not core_fact or _looks_runtime_dump(core_fact):
        return None

    return {
        "Concept": concept_clean,
        "Core Fact": core_fact[:2000],
        "Source": source[:120],
        "Confidence": confidence,
        "Last Verified": last_verified[:64],
        "Sensitivity": sensitivity[:64],
        "Sharing Policy": sharing_policy[:64],
        "Reviewer": reviewer[:120],
    }


async def _fetch_memory_table_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str | None:
    response = await client.get(f"{TEABLE_API_BASE_URL}/base/{TEABLE_BASE_ID}/table", headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Teable table lookup failed: {response.status_code} {response.text[:200]}", flush=True)
        return None
    try:
        tables = response.json()
    except Exception:
        print("⚠️ Teable table lookup returned invalid JSON", flush=True)
        return None
    if not isinstance(tables, list):
        return None
    memory_table = next((tbl for tbl in tables if str(tbl.get("name") or "").strip().lower() == "memory"), None)
    if not memory_table:
        print("⚠️ Teable Memory table not found; skipping sync cycle.", flush=True)
        return None
    return str(memory_table.get("id") or "").strip() or None


async def _push_record(
    client: httpx.AsyncClient,
    *,
    table_id: str,
    headers: dict[str, str],
    fields: dict[str, Any],
) -> bool:
    payload = {"records": [{"fields": fields}]}
    response = await client.post(f"{TEABLE_API_BASE_URL}/table/{table_id}/record", json=payload, headers=headers)
    if response.status_code in (200, 201):
        return True
    minimal_fields = {"Concept": fields.get("Concept"), "Core Fact": fields.get("Core Fact")}
    fallback_response = await client.post(
        f"{TEABLE_API_BASE_URL}/table/{table_id}/record",
        json={"records": [{"fields": minimal_fields}]},
        headers=headers,
    )
    if fallback_response.status_code in (200, 201):
        print("ℹ️ Teable accepted minimal memory fields after provenance fallback.", flush=True)
        return True
    print(
        f"⚠️ Teable push failed: {response.status_code}/{fallback_response.status_code} "
        f"{fallback_response.text[:200]}",
        flush=True,
    )
    return False


async def run_teable_sync() -> None:
    print("==================================================", flush=True)
    print("🗃️ EA OS TEABLE SYNC: ONLINE (Curated Memory Projection)", flush=True)
    print(f"🗃️ Teable API base: {TEABLE_API_BASE_URL}", flush=True)
    print("==================================================", flush=True)

    if not TEABLE_TOKEN or not TEABLE_BASE_ID:
        print("⚠️ TEABLE_TOKEN or TEABLE_BASE_ID missing. Syncer running idle.", flush=True)
        while True:
            await asyncio.sleep(3600)

    headers = {"Authorization": f"Bearer {TEABLE_TOKEN}", "Content-Type": "application/json"}

    while True:
        try:
            brain = _load_json(BRAIN_PATH, {})
            if not isinstance(brain, dict):
                brain = {}
            state = _load_sync_state(STATE_PATH)
            synced_concepts = {str(x) for x in state.get("synced_concepts", []) if str(x).strip()}
            skipped = dict(state.get("skipped_concepts") or {})

            if brain:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    table_id = await _fetch_memory_table_id(client, headers)
                    if table_id:
                        for concept in sorted(brain.keys()):
                            concept_key = str(concept or "").strip()
                            if not concept_key or concept_key in synced_concepts:
                                continue
                            fields = build_memory_record_fields(concept_key, brain.get(concept))
                            if not fields:
                                skipped[concept_key] = "unsupported_or_runtime_like"
                                continue
                            print(f"🗃️ Syncing curated memory: [{concept_key}]", flush=True)
                            pushed = await _push_record(client, table_id=table_id, headers=headers, fields=fields)
                            if pushed:
                                synced_concepts.add(concept_key)
                                if concept_key in skipped:
                                    skipped.pop(concept_key, None)
                                state = {
                                    "synced_concepts": sorted(synced_concepts),
                                    "updated_at": _utc_now_iso(),
                                    "skipped_concepts": skipped,
                                }
                                _save_json(STATE_PATH, state)
                                await asyncio.sleep(1)
            else:
                if not os.path.exists(BRAIN_PATH):
                    print(f"ℹ️ No curated memory file at {BRAIN_PATH}; waiting.", flush=True)
        except Exception as exc:
            print(f"🚨 TEABLE ERROR: {exc}", flush=True)

        await asyncio.sleep(TEABLE_SYNC_POLL_SEC)


if __name__ == "__main__":
    asyncio.run(run_teable_sync())
