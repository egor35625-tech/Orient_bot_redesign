import time
from collections import defaultdict
from fastapi import HTTPException, Request

_buckets: dict[str, list[float]] = defaultdict(list)

def rate_limit(key: str, limit: int = 5, window: int = 60):
    now = time.time()
    bucket = _buckets[key]
    _buckets[key] = [t for t in bucket if now - t < window]
    if len(_buckets[key]) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests")
    _buckets[key].append(now)

def client_key(request: Request, telegram_id: int | None = None) -> str:
    return f"{telegram_id or 'anon'}:{request.client.host if request.client else 'unknown'}"