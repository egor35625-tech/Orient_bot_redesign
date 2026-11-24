import os
import uuid
from fastapi import HTTPException, UploadFile

from config import UPLOAD_DIR

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _looks_like_image(head: bytes, ext: str) -> bool:
    if head.startswith(b"\xff\xd8\xff"):
        return ext in (".jpg", ".jpeg")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ext == ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ext == ".webp"
    return False


async def save_image(file: UploadFile, subdir: str, max_bytes: int = 8 * 1024 * 1024) -> str:
    """Сохраняет картинку и возвращает путь вида 'uploads/<subdir>/<имя>' (для БД и URL)."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, "Допустимы только фото JPG, PNG или WEBP")
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(400, f"Фото слишком большое (максимум {max_bytes // (1024 * 1024)} МБ)")
    if not _looks_like_image(content[:16], ext):
        raise HTTPException(400, "Файл не похож на изображение")
    target_dir = os.path.join(UPLOAD_DIR, *subdir.split("/"))
    os.makedirs(target_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(target_dir, name), "wb") as f:
        f.write(content)
    return f"uploads/{subdir}/{name}"


def delete_media(path: str | None) -> None:
    """Удаляет файл по пути из БД. Выход за пределы UPLOAD_DIR игнорируется."""
    if not path:
        return
    rel = path.lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/"):]
    full = os.path.realpath(os.path.join(UPLOAD_DIR, rel))
    root = os.path.realpath(UPLOAD_DIR)
    if not full.startswith(root + os.sep):
        return
    try:
        os.remove(full)
    except OSError:
        pass
