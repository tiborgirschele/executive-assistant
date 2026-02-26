from __future__ import annotations
import traceback
from app.llm_vision import complete_json_with_image

async def extract_calendar_from_image(image_bytes: bytes, mime_type: str) -> dict:
    prompt = '''Extract all appointments from this image. 
    Return ONLY a JSON object with this exact schema:
    {"events": [{"title": "Name of event", "start": "YYYY-MM-DD HH:MM", "end": "YYYY-MM-DD HH:MM", "location": "Optional"}]}
    If end time is missing, assume 1 hour duration.
    '''
    try:
        res = await complete_json_with_image(prompt, image_bytes, mime=mime_type, timeout_s=90.0)
        if "events" not in res:
            res["events"] = []
        return res
    except Exception as e:
        print(f"Vision API Error: {e}\n{traceback.format_exc()}", flush=True)
        return {"events": [], "error": str(e)}
