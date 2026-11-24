import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is not set")

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com").rstrip("/")


def _normalize_database_url(raw: str) -> tuple[str, dict]:
    """Приводит DATABASE_URL к виду, понятному SQLAlchemy async.

    * postgres:// и postgresql:// -> postgresql+asyncpg://
    * относительный путь SQLite -> абсолютный (от папки проекта), чтобы база
      не «терялась» при запуске из другой рабочей директории.
    """
    connect_args: dict = {}
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    if url.startswith("postgresql+asyncpg://") and "?" in url:
        base, query = url.split("?", 1)
        kept = []
        for part in query.split("&"):
            if part.startswith("sslmode="):
                if part.split("=", 1)[1] in ("require", "verify-ca", "verify-full"):
                    connect_args["ssl"] = True
            elif part:
                kept.append(part)
        url = base + ("?" + "&".join(kept) if kept else "")

    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        path = url[len(prefix):]
        if path and path != ":memory:" and not Path(path).is_absolute():
            url = prefix + str((BASE_DIR / path).resolve())
    return url, connect_args


DATABASE_URL, DB_CONNECT_ARGS = _normalize_database_url(
    os.getenv("DATABASE_URL") or f"sqlite+aiosqlite:///{BASE_DIR / 'orders.db'}"
)

_upload = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR = str(_upload if _upload.is_absolute() else (BASE_DIR / _upload).resolve())

MAX_PHOTOS = int(os.getenv("MAX_PHOTOS", "10"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))
INIT_DATA_TTL = int(os.getenv("INIT_DATA_TTL", "86400"))

MAX_ITEM_PHOTOS = 5
