import hashlib
from functools import lru_cache


@lru_cache
def get_message_hash(message_text: str, message_number: str, sender_callsign: str) -> str:
    """Returns a string hash of the message that can be used as a unique key to identify it"""
    text_hash = hashlib.sha256(message_text.encode('utf-8')).hexdigest()
    return f"{text_hash}-{sender_callsign}-{message_number}"
