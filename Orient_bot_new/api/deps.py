from dataclasses import dataclass

from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN_IDS
from database import get_session
from models import AdminUser, Profile, User
from services.init_data import validate_init_data


async def get_current_user(x_telegram_init_data: str = Header(...)):
    try:
        user = validate_init_data(x_telegram_init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Некорректный пользователь Telegram")
    return user


async def get_optional_user(x_telegram_init_data: str | None = Header(None)):
    """Для публичных ручек: пользователь, если он авторизован, иначе None."""
    if not x_telegram_init_data:
        return None
    try:
        user = validate_init_data(x_telegram_init_data)
    except ValueError:
        return None
    return user if user.get("id") else None


async def is_admin_id(db: AsyncSession, tg_id: int | None) -> bool:
    if not tg_id:
        return False
    if tg_id in ADMIN_IDS:
        return True
    row = await db.execute(select(AdminUser.id).where(AdminUser.telegram_id == tg_id))
    return row.first() is not None


async def get_admin_user(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if await is_admin_id(db, user.get("id")):
        return user
    raise HTTPException(status_code=403, detail="Admin only")


async def ensure_user(db: AsyncSession, user_data: dict) -> User:
    """Находит или создаёт пользователя и синхронизирует имя/username из Telegram."""
    tg_id = user_data.get("id")
    user = (await db.execute(select(User).where(User.telegram_id == tg_id))).scalar_one_or_none()
    if not user:
        user = User(telegram_id=tg_id, username=user_data.get("username"), first_name=user_data.get("first_name"))
        db.add(user)
        await db.flush()
    else:
        if user_data.get("username") and user.username != user_data.get("username"):
            user.username = user_data.get("username")
        if user_data.get("first_name") and user.first_name != user_data.get("first_name"):
            user.first_name = user_data.get("first_name")
    return user


@dataclass
class Ctx:
    user: User
    profile: Profile
    tg: dict

    @property
    def username(self) -> str:
        return self.profile.tg_username


async def get_registered(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> Ctx:
    """Пользователь, завершивший регистрацию (указал @username)."""
    user = (await db.execute(select(User).where(User.telegram_id == user_data["id"]))).scalar_one_or_none()
    profile = None
    if user:
        profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
    if not user or not profile or not profile.tg_username:
        raise HTTPException(status_code=403, detail="Сначала зарегистрируйтесь: укажите ваш @username в Telegram")
    return Ctx(user=user, profile=profile, tg=user_data)
