import redis
import uuid
import json

# Connect to the new Redis container
r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def save_button_context(prompt: str) -> str:
    """Saves a rich prompt to Redis and returns a short 8-char ID."""
    action_id = str(uuid.uuid4())[:8]
    # Store for 72 hours (after which the Telegram button will just say 'expired')
    r.setex(f"btn:{action_id}", 259200, prompt)
    return action_id

def get_button_context(action_id: str) -> str | None:
    """Retrieves the rich prompt using the short ID."""
    return r.get(f"btn:{action_id}")
