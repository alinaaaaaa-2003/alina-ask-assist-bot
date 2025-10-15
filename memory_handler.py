import redis
import json
from typing import List, Dict
import os
# Connect to Redis (assuming default localhost:6379)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379") # Reads environment variable, defaults to localhost for local testing
r = redis.from_url(REDIS_URL, decode_responses=True)

# Configuration: Store the last 6 messages for context
MAX_CONTEXT_MESSAGES = 6

# --- NEW: DRY Helper Function ---
def _format_message(role: str, content: str, type: str = "normal") -> str:
    """Formats the Python message dictionary into a JSON string for Redis storage."""
    message_data = {"role": role, "content": content, "type": type}
    return json.dumps(message_data)
# --- END NEW HELPER ---


def save_message(session_id: str, role: str, content: str, type: str = "normal"):
    """Saves a message (user or assistant) to the Redis list, including its type."""
    
    # 1. Use the helper function to format the message (DRY applied)
    message = _format_message(role, content, type)
    
    # 2. lpush adds the new message to the HEAD of the list (most recent)
    r.lpush(session_id, message)
    
    # 3. Trim the list to retain only the MAX_CONTEXT_MESSAGES
    r.ltrim(session_id, 0, MAX_CONTEXT_MESSAGES - 1)

def get_context(session_id: str) -> List[Dict[str, str]]:
    """Retrieves the conversation history, ordered chronologically (oldest first)."""
    
    # LRANGE retrieves the list elements.
    raw_history = r.lrange(session_id, 0, MAX_CONTEXT_MESSAGES - 1)
    
    # Deserialize and reverse the order to present chronologically to the LLM
    history = [json.loads(msg) for msg in raw_history]
    history.reverse()
    
    return history

def clear_session(session_id: str):
    """Removes all messages for a session (optional feature)."""
    r.delete(session_id)