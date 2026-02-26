from __future__ import annotations
import base64, json, re
from typing import Any, Dict, Optional
import httpx
from app.settings import settings

_JSON_RE = re.compile(r"\{[\s\S]*\}", re.M)

def _extract_json(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    m = _JSON_RE.search(t)
    if not m:
        raise ValueError("no JSON object found in model output")
    return json.loads(m.group(0))

async def complete_json_with_image(prompt: str, image_bytes: bytes, *, mime: str = "image/jpeg", timeout_s: float = 90.0) -> Dict[str, Any]:
    """
    Calls LiteLLM OpenAI-compatible /v1/chat/completions with multimodal content.
    Returns parsed JSON dict (strictly extracted).
    """
    if not settings.litellm_base_url:
        raise RuntimeError("missing EA_LITELLM_BASE_URL")
    if not settings.llm_model:
        raise RuntimeError("missing EA_LLM_MODEL")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    url = settings.litellm_base_url.rstrip("/") + "/v1/chat/completions"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.litellm_api_key:
        headers["Authorization"] = f"Bearer {settings.litellm_api_key}"

    body = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON. No markdown. No extra text."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json() or {}

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"no choices: {data}")

    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")

    # content may be string OR list of parts
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(str(p.get("text") or ""))
        text = "\n".join(parts).strip()
    else:
        text = str(content or "").strip()

    if not text:
        raise RuntimeError("empty model output")

    return _extract_json(text)
