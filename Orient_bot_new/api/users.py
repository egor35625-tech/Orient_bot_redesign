from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import ensure_user, get_current_user, is_admin_id
from database import get_session
from models import Profile
from schemas import ProfileOut, ProfileUpdate
from services.text import clean_str, clean_username

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _profile_out(user, profile, tg: dict, is_admin: bool) -> dict:
    return {
        "first_name": user.first_name,
        "telegram_username": tg.get("username"),
        "tg_username": profile.tg_username if profile else None,
        "city": profile.city if profile else None,
        "default_address": profile.default_address if profile else None,
        "is_registered": bool(profile and profile.tg_username),
        "is_admin": is_admin,
    }


async def _get_profile(db: AsyncSession, user_id: int) -> Profile | None:
    return (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()


@router.get("", response_model=ProfileOut)
async def get_profile(user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    user = await ensure_user(db, user_data)
    profile = await _get_profile(db, user.id)
    await db.commit()
    return _profile_out(user, profile, user_data, await is_admin_id(db, user.telegram_id))


@router.put("", response_model=ProfileOut)
async def update_profile(
    data: ProfileUpdate,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    user = await ensure_user(db, user_data)
    profile = await _get_profile(db, user.id)
    if not profile:
        profile = Profile(user_id=user.id, country="BY")
        db.add(profile)

    if data.tg_username is not None:
        try:
            username = clean_username(data.tg_username)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not username:
            raise HTTPException(400, "Укажите ваш @username в Telegram")
        taken = (await db.execute(
            select(Profile.id).where(func.lower(Profile.tg_username) == username.lower(), Profile.user_id != user.id)
        )).first()
        if taken:
            raise HTTPException(409, "Этот @username уже занят другим пользователем")
        profile.tg_username = username
    if not profile.tg_username:
        raise HTTPException(400, "Для регистрации укажите ваш @username в Telegram")

    if data.city is not None:
        profile.city = clean_str(data.city, 128)
    if data.default_address is not None:
        profile.default_address = clean_str(data.default_address, 500)
    profile.country = "BY"

    await db.commit()
    return _profile_out(user, profile, user_data, await is_admin_id(db, user.telegram_id))
