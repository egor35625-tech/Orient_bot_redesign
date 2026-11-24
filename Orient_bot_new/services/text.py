import re

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()\-]{5,19}$")
DELIVERY_ALLOWED = ("pickup", "cdek", "post")
CONTACT_MODES = ("messages", "calls")


def make_search_text(*parts) -> str:
    """Нижний регистр средствами Python: SQLite lower()/LIKE не понимают кириллицу."""
    return " ".join(str(p) for p in parts if p).casefold()


def like_pattern(q: str) -> str:
    q = q.strip().casefold()
    q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{q}%"


def parse_price(raw: str | None) -> tuple[str | None, float | None]:
    """'1 200,5' -> ('1200.5', 1200.5). Пустое -> (None, None). Нечисловое -> ValueError."""
    if raw is None:
        return None, None
    s = str(raw).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not s:
        return None, None
    if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", s):
        raise ValueError("Цена должна быть числом, например 120 или 99.90")
    value = float(s)
    text = str(int(value)) if value == int(value) else f"{value:.2f}".rstrip("0")
    return text, value


def clean_username(raw: str | None) -> str | None:
    """@name / https://t.me/name -> name. Пусто -> None. Неверный формат -> ValueError."""
    s = (raw or "").strip()
    if not s:
        return None
    s = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", s, flags=re.I)
    s = s.lstrip("@").split("?")[0].strip("/")
    if not USERNAME_RE.match(s):
        raise ValueError("Некорректный @username: 5–32 символа, латиница, цифры и _, начинается с буквы")
    return s


def clean_phone(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if not PHONE_RE.match(s):
        raise ValueError("Некорректный номер телефона")
    return s


def clean_contact_mode(raw: str | None, phone: str) -> str:
    mode = (raw or "messages").strip()
    if mode not in CONTACT_MODES:
        raise ValueError("Некорректный способ связи")
    return mode if phone else "messages"


def clean_delivery(raw: str | None) -> str | None:
    methods = [m for m in (raw or "").split(",") if m.strip() in DELIVERY_ALLOWED]
    ordered = [m for m in DELIVERY_ALLOWED if m in methods]
    return ",".join(ordered) or None


def clean_str(raw: str | None, max_len: int) -> str | None:
    s = (raw or "").strip()
    return s[:max_len] or None
