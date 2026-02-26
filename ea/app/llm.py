import json
import httpx
from app.settings import settings

async def complete(prompt: str) -> str:
    base = getattr(settings, "litellm_base_url", "")
    model = getattr(settings, "llm_model", "")
    api_key = getattr(settings, "litellm_api_key", "")
    
    if not base or not model:
        return "{}"
        
    url = base.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM API Error: {e}", flush=True)
        return "{}"
