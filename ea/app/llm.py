import json, urllib.request
from app.settings import settings

def ask_llm(prompt: str, system_prompt: str = "Du bist ein präziser Executive Assistant.") -> str:
    """
    Das V1.5 Cognitive Gateway: Kaskadierendes OODA-Fallback.
    Primär: Magixx (EA_LLM_CHAIN) -> Fallback: LiteLLM -> Fallback: Gemini
    """
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    
    # 1. PRIO: Magixx Gateway (EA_LLM_CHAIN z.B. o1-mini)
    if settings.magixx_api_key:
        try:
            url = f"{(settings.magixx_base_url or 'https://api.magixx.com').rstrip('/')}/chat/completions"
            model = settings.llm_chain.replace("magixx:", "") if settings.llm_chain else "o1-mini"
            data = json.dumps({"model": model, "messages": messages}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {settings.magixx_api_key}'})
            res = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
            return res['choices'][0]['message']['content']
        except Exception as e:
            print(f"⚠️ OODA (Magixx Failed): {e}. Orienting to Fallback...", flush=True)

    # 2. PRIO: LiteLLM Gateway
    if settings.litellm_api_key:
        try:
            url = f"{(settings.litellm_base_url or 'http://litellm:4000').rstrip('/')}/chat/completions"
            data = json.dumps({"model": "gpt-4o-mini", "messages": messages}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {settings.litellm_api_key}'})
            res = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
            return res['choices'][0]['message']['content']
        except Exception as e:
            print(f"⚠️ OODA (LiteLLM Failed): {e}. Orienting to Fallback...", flush=True)

    # 3. PRIO: Gemini Native (Letzter Strohhalm)
    if getattr(settings, 'gemini_api_key', None):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            data = json.dumps({"contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            res = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
            return res['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"⚠️ OODA (Gemini Failed): {e}.", flush=True)

    return "❌ OODA FATAL: Alle kognitiven Gateways (Magixx, LiteLLM, Gemini) sind offline. System ist blind."
