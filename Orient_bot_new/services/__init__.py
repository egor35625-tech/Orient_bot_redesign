import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl
from config import BOT_TOKEN, INIT_DATA_TTL

def validate_init_data(init_data: str) -> dict:
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise ValueError("Invalid init data")
    if "hash" not in parsed:
        raise ValueError("No hash")
    received_hash = parsed.pop("hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid hash")
    auth_date = int(parsed.get("auth_date", "0"))
    if time.time() - auth_date > INIT_DATA_TTL:
        raise ValueError("Init data expired")
    user = json.loads(parsed.get("user", "{}"))
    return user