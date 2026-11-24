import logging
import os
import uuid
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_admin_user
from config import ADMIN_IDS
from database import get_session
from models import (
    AdminUser,
    MarketplaceItem,
    Message as OrderMessage,
    Order,
    OrderStage,
    Profile,
    Review,
    Shop,
    ShopApplication,
    ShopOrder,
    ShopStage,
    User,
)
from schemas import (
    AdminNotesUpdate,
    AdminUserCreate,
    OrderOut,
    PriceUpdate,
    ReplyMessage,
    ReviewOut,
    ShopApplicationOut,
    ShopApplicationReject,
    ShopBlockIn,
    StageCreate,
    StageOut,
    StageReorder,
    StageUpdate,
)
from services.media import delete_media
from services.notification_service import (
    notify_client_message,
    notify_client_price,
    notify_client_stage,
)
from services.shop_service import (
    DEFAULT_SHOP_STAGES,
    delete_shop_cascade,
    release_expired_blocks,
    utcnow,
)
from services.stage_service import (
    get_all_stages,
    get_next_stage,
    get_prev_stage,
    get_rejected_stage,
)
from services.telegram_service import bot
from services.text import make_search_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    status: str | None = None,
    q: str | None = None,
    promo: bool = False,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    query = (
        select(Order)
        .options(
            selectinload(Order.photos),
            selectinload(Order.user),
            selectinload(Order.messages),
            selectinload(Order.current_stage),
        )
        .order_by(Order.created_at.desc())
    )
    if status:
        query = query.where(Order.status == status)
    if promo:
        query = query.where(Order.promo_code.isnot(None))
    if q:
        if q.isdigit():
            query = query.where(Order.id == int(q))
        else:
            query = query.join(User).where(
                User.username.ilike(f"%{q}%")
                | User.first_name.ilike(f"%{q}%")
                | Order.description.ilike(f"%{q}%")
            )
    return (await db.execute(query)).scalars().all()


@router.get("/stats")
async def stats(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    total = await db.scalar(select(func.count()).select_from(Order))
    active = await db.scalar(
        select(func.count()).select_from(Order).where(Order.status == "active")
    )
    completed = await db.scalar(
        select(func.count()).select_from(Order).where(Order.status == "completed")
    )
    rejected = await db.scalar(
        select(func.count()).select_from(Order).where(Order.status == "rejected")
    )
    shops_total = await db.scalar(select(func.count()).select_from(Shop))
    pending_apps = await db.scalar(
        select(func.count())
        .select_from(ShopApplication)
        .where(ShopApplication.status == "pending")
    )
    return {
        "total": total,
        "active": active,
        "completed": completed,
        "rejected": rejected,
        "shops_total": shops_total,
        "pending_shop_applications": pending_apps,
    }


# --- МОДЕРАЦИЯ МАГАЗИНОВ ---
async def _safe_send(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.warning("Cannot send message to %s: %s", chat_id, e)


def _shop_snapshot(shop: Shop | None) -> dict | None:
    if not shop:
        return None
    return {
        "id": shop.id, "name": shop.name, "description": shop.description, "city": shop.city,
        "phone": shop.phone, "contact_mode": shop.contact_mode, "manager_username": shop.manager_username,
        "manager_telegram_id": shop.manager_telegram_id, "instagram_url": shop.instagram_url,
        "tiktok_url": shop.tiktok_url, "pickup_address": shop.pickup_address,
        "delivery_methods": shop.delivery_methods, "logo": shop.logo,
    }


async def _usernames(db: AsyncSession, tg_ids: set[int]) -> dict[int, str]:
    if not tg_ids:
        return {}
    rows = await db.execute(
        select(User.telegram_id, Profile.tg_username)
        .join(Profile, Profile.user_id == User.id)
        .where(User.telegram_id.in_(tg_ids))
    )
    return {tg: name for tg, name in rows.all() if name}


@router.get("/shop-applications")
async def list_shop_applications(
    status: str | None = "pending",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    query = select(ShopApplication).order_by(ShopApplication.id.desc()).limit(200)
    if status:
        query = query.where(ShopApplication.status == status)
    apps = (await db.execute(query)).scalars().all()
    names = await _usernames(db, {a.applicant_telegram_id for a in apps})
    shops = {}
    for sid in {a.shop_id for a in apps if a.shop_id}:
        shops[sid] = await db.get(Shop, sid)
    out = []
    for a in apps:
        data = ShopApplicationOut.model_validate(a).model_dump(mode="json")
        data["applicant_username"] = names.get(a.applicant_telegram_id)
        data["current"] = _shop_snapshot(shops.get(a.shop_id)) if a.kind == "edit" else None
        out.append(data)
    return out


def _apply_application(shop: Shop, app_obj: ShopApplication) -> None:
    shop.name = app_obj.shop_name
    shop.description = app_obj.description
    shop.country = "BY"
    shop.city = app_obj.city
    shop.manager_telegram_id = app_obj.manager_telegram_id
    shop.manager_username = app_obj.manager_username
    shop.instagram_url = app_obj.instagram_url
    shop.tiktok_url = app_obj.tiktok_url
    shop.phone = app_obj.phone
    shop.contact_mode = app_obj.contact_mode or "messages"
    shop.pickup_address = app_obj.pickup_address
    shop.delivery_methods = app_obj.delivery_methods
    shop.search_text = make_search_text(shop.name, shop.description, shop.city)


@router.post("/shop-applications/{app_id}/approve")
async def approve_shop_application(
    app_id: int,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    app_obj = await db.get(ShopApplication, app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app_obj.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    old_logo_to_delete = None
    if app_obj.kind == "edit":
        shop = await db.get(Shop, app_obj.shop_id) if app_obj.shop_id else None
        if not shop:
            raise HTTPException(status_code=400, detail="Магазин, к которому относится заявка, не найден")
        clash = (await db.execute(
            select(Shop.id).where(func.lower(Shop.name) == app_obj.shop_name.lower(), Shop.id != shop.id)
        )).first()
        if clash:
            raise HTTPException(status_code=400, detail="Магазин с таким названием уже зарегистрирован")
        _apply_application(shop, app_obj)
        if app_obj.logo is not None:  # "" — удалить, путь — заменить
            old_logo_to_delete = shop.logo
            shop.logo = app_obj.logo or None
        note = "✅ Изменения в вашем магазине «{}» одобрены и уже опубликованы."
    else:
        if (await db.execute(select(Shop.id).where(func.lower(Shop.name) == app_obj.shop_name.lower()))).first():
            raise HTTPException(status_code=400, detail="Магазин с таким названием уже зарегистрирован")
        if (await db.execute(select(Shop.id).where(Shop.owner_telegram_id == app_obj.applicant_telegram_id))).first():
            raise HTTPException(status_code=400, detail="У этого пользователя уже есть магазин")
        shop = Shop(owner_telegram_id=app_obj.applicant_telegram_id, name=app_obj.shop_name, logo=app_obj.logo or None)
        _apply_application(shop, app_obj)
        db.add(shop)
        await db.flush()
        db.add_all([ShopStage(shop_id=shop.id, label=label, position=idx) for idx, label in enumerate(DEFAULT_SHOP_STAGES, start=1)])
        note = "🎉 Ваша заявка на магазин «{}» одобрена! Теперь вы можете публиковать товары от имени магазина и управлять заказами."

    app_obj.status = "approved"
    app_obj.shop_id = shop.id
    await db.commit()
    delete_media(old_logo_to_delete)
    await _safe_send(app_obj.applicant_telegram_id, note.format(shop.name))
    return {"ok": True, "shop_id": shop.id}


@router.post("/shop-applications/{app_id}/reject")
async def reject_shop_application(
    app_id: int,
    data: ShopApplicationReject,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    app_obj = await db.get(ShopApplication, app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app_obj.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    app_obj.status = "rejected"
    app_obj.reject_reason = (data.reason or "").strip() or None
    logo_to_delete = app_obj.logo or None
    app_obj.logo = None
    await db.commit()
    delete_media(logo_to_delete)

    reason_text = f"\nПричина: {app_obj.reject_reason}" if app_obj.reject_reason else ""
    what = "изменение магазина" if app_obj.kind == "edit" else "создание магазина"
    await _safe_send(app_obj.applicant_telegram_id, f"❌ Заявка на {what} «{app_obj.shop_name}» отклонена.{reason_text}")
    return {"ok": True}


@router.get("/shops")
async def admin_list_shops(
    q: str | None = None,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    await release_expired_blocks(db)
    query = select(Shop).order_by(Shop.created_at.desc()).limit(200)
    if q and q.strip():
        query = query.where(Shop.search_text.like(f"%{q.strip().casefold()}%"))
    shops = (await db.execute(query)).scalars().all()
    names = await _usernames(db, {s.owner_telegram_id for s in shops})
    out = []
    for s in shops:
        items_count = await db.scalar(
            select(func.count()).select_from(MarketplaceItem).where(MarketplaceItem.shop_id == s.id, MarketplaceItem.is_active.is_(True))
        )
        out.append({
            "id": s.id, "name": s.name, "logo": s.logo, "city": s.city,
            "owner_telegram_id": s.owner_telegram_id, "owner_username": names.get(s.owner_telegram_id),
            "status": s.status, "blocked_until": s.blocked_until.isoformat() + "Z" if s.blocked_until else None,
            "block_reason": s.block_reason, "items_count": items_count or 0, "orders_count": s.orders_count or 0,
        })
    return out


@router.post("/shops/{shop_id}/block")
async def block_shop(
    shop_id: int,
    data: ShopBlockIn,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Магазин не найден")
    shop.status = "blocked"
    shop.blocked_until = (utcnow() + timedelta(days=data.days)) if data.days else None
    shop.block_reason = (data.reason or "").strip() or None
    await db.commit()
    term = f"на {data.days} дн." if data.days else "навсегда"
    reason = f"\nПричина: {shop.block_reason}" if shop.block_reason else ""
    await _safe_send(shop.owner_telegram_id, f"⛔ Ваш магазин «{shop.name}» заблокирован {term}.{reason}")
    return {"ok": True}


@router.post("/shops/{shop_id}/unblock")
async def unblock_shop(shop_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Магазин не найден")
    shop.status, shop.blocked_until, shop.block_reason = "active", None, None
    await db.commit()
    await _safe_send(shop.owner_telegram_id, f"✅ Ваш магазин «{shop.name}» разблокирован.")
    return {"ok": True}


@router.delete("/shops/{shop_id}")
async def admin_delete_shop(shop_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Магазин не найден")
    owner_id, name = shop.owner_telegram_id, shop.name
    await delete_shop_cascade(db, shop)
    await db.commit()
    await _safe_send(owner_id, f"🗑 Ваш магазин «{name}» удалён модератором.")
    return {"ok": True}


# --- АДМИНЫ ---
@router.get("/admins")
async def list_admins(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    env_admins = [{"telegram_id": aid, "is_main": True} for aid in ADMIN_IDS]
    db_admins = [
        {"telegram_id": a.telegram_id, "is_main": False}
        for a in (await db.execute(select(AdminUser))).scalars().all()
    ]
    return env_admins + db_admins


@router.post("/admins")
async def add_admin(
    data: AdminUserCreate,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    if data.telegram_id in ADMIN_IDS:
        raise HTTPException(400, "Уже главный админ")
    if (
        await db.execute(
            select(AdminUser).where(AdminUser.telegram_id == data.telegram_id)
        )
    ).scalar_one_or_none():
        raise HTTPException(400, "Уже добавлен")
    db.add(AdminUser(telegram_id=data.telegram_id, added_by=admin["id"]))
    await db.commit()
    return {"ok": True}


@router.delete("/admins/{tg_id}")
async def remove_admin(
    tg_id: int,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    adm = (
        await db.execute(select(AdminUser).where(AdminUser.telegram_id == tg_id))
    ).scalar_one_or_none()
    if not adm:
        raise HTTPException(404)
    await db.delete(adm)
    await db.commit()
    return {"ok": True}


# --- ЗАМЕТКИ И ЭКСПОРТ ---
@router.patch("/orders/{order_id}/notes")
async def update_notes(
    order_id: int,
    data: AdminNotesUpdate,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    order.admin_notes = data.notes
    await db.commit()
    return {"ok": True}


@router.post("/export/google")
async def export_to_google(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    webhook_url = os.getenv("GOOGLE_SHEETS_WEBHOOK")
    if not webhook_url:
        raise HTTPException(400, "GOOGLE_SHEETS_WEBHOOK не настроен")
    orders = (
        (
            await db.execute(
                select(Order)
                .where(Order.exported_to_sheets == False)
                .order_by(Order.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        return {"ok": True, "message": "Нет новых заказов"}
    payload = []
    for o in orders:
        user = await db.get(User, o.user_id)
        payload.append(
            {
                "id": o.id,
                "date": o.created_at.strftime("%Y-%m-%d %H:%M"),
                "client": user.first_name or "",
                "username": f"@{user.username}" if user.username else "",
                "phone": o.phone or "",
                "address": o.delivery_address or "",
                "description": o.description,
                "price": o.price or "",
                "status": o.status,
                "stage": o.current_stage.label if o.current_stage else "",
            }
        )
        o.exported_to_sheets = True
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"orders": payload})
        if resp.status_code not in (200, 201):
            raise HTTPException(500, "Ошибка Google")
    await db.commit()
    return {"ok": True, "exported": len(payload)}


# --- ЭТАПЫ И СТАТУСЫ СЕРВИСА ---
@router.get("/stages", response_model=list[StageOut])
async def admin_list_stages(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    return await get_all_stages(db)


@router.post("/stages", response_model=StageOut)
async def create_stage(
    data: StageCreate,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    stages = await get_all_stages(db)
    pos = (
        data.position
        if data.position is not None
        else (stages[-1].position + 1 if stages else 1)
    )
    stage = OrderStage(code=data.code or f"stage_{uuid.uuid4().hex[:8]}", label=data.label, position=pos)
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return stage


@router.post("/orders/{order_id}/stage/next")
async def stage_next(
    order_id: int,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    stage = await get_next_stage(db, order.current_stage_id)
    if not stage:
        raise HTTPException(400, "Последний этап")
    order.current_stage_id = stage.id
    order.status = (
        "rejected"
        if stage.is_rejected
        else ("completed" if stage.is_final else "active")
    )
    user = await db.get(User, order.user_id)
    await db.commit()
    await notify_client_stage(order, user, stage)
    return {"ok": True, "stage": stage.label}


async def _order_and_user(db: AsyncSession, order_id: int):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    return order, await db.get(User, order.user_id)


async def _set_stage(db: AsyncSession, order: Order, user: User, stage: OrderStage):
    order.current_stage_id = stage.id
    order.status = "rejected" if stage.is_rejected else ("completed" if stage.is_final else "active")
    await db.commit()
    await notify_client_stage(order, user, stage)


@router.post("/orders/{order_id}/stage/prev")
async def stage_prev(order_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    order, user = await _order_and_user(db, order_id)
    stage = await get_prev_stage(db, order.current_stage_id)
    if not stage:
        raise HTTPException(400, "Первый этап")
    await _set_stage(db, order, user, stage)
    return {"ok": True, "stage": stage.label}


@router.post("/orders/{order_id}/complete")
async def order_complete(order_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    order, user = await _order_and_user(db, order_id)
    stages = await get_all_stages(db)
    stage = next((s for s in stages if s.is_final and not s.is_rejected), None)
    if not stage:
        raise HTTPException(400, "Финальный этап не настроен")
    await _set_stage(db, order, user, stage)
    return {"ok": True, "stage": stage.label}


@router.post("/orders/{order_id}/reject")
async def order_reject(order_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    order, user = await _order_and_user(db, order_id)
    stage = await get_rejected_stage(db)
    if not stage:
        raise HTTPException(400, "Этап отклонения не настроен")
    await _set_stage(db, order, user, stage)
    return {"ok": True, "stage": stage.label}


@router.post("/orders/{order_id}/price")
async def order_price(order_id: int, data: PriceUpdate, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    order, user = await _order_and_user(db, order_id)
    order.price, order.currency = data.price.strip(), data.currency
    await db.commit()
    await notify_client_price(order, user)
    return {"ok": True}


@router.post("/orders/{order_id}/reply")
async def order_reply(order_id: int, data: ReplyMessage, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    order, user = await _order_and_user(db, order_id)
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    db.add(OrderMessage(order_id=order.id, sender_id=admin["id"], message_text=text, message_type="text"))
    await db.commit()
    await notify_client_message(order, user, text, prefix="💬 Ответ по заказу")
    return {"ok": True}


# --- ОТЗЫВЫ (общие) ---
@router.get("/reviews", response_model=list[ReviewOut])
async def admin_reviews(admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    return (await db.execute(select(Review).order_by(Review.created_at.desc()).limit(200))).scalars().all()


async def _set_review_status(db: AsyncSession, review_id: int, status: str):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(404, "Отзыв не найден")
    review.status = status
    await db.commit()
    return {"ok": True}


@router.post("/reviews/{review_id}/publish")
async def review_publish(review_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    return await _set_review_status(db, review_id, "published")


@router.post("/reviews/{review_id}/hide")
async def review_hide(review_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    return await _set_review_status(db, review_id, "hidden")


# --- УПРАВЛЕНИЕ ЭТАПАМИ ---
@router.post("/stages/reorder")
async def reorder_stages(data: StageReorder, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    stages = {s.id: s for s in await get_all_stages(db)}
    if set(data.ids) != set(stages):
        raise HTTPException(400, "Список этапов не совпадает с текущим")
    for pos, sid in enumerate(data.ids, start=1):
        stages[sid].position = pos
    await db.commit()
    return {"ok": True}


@router.patch("/stages/{stage_id}", response_model=StageOut)
async def update_stage(stage_id: int, data: StageUpdate, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    stage = await db.get(OrderStage, stage_id)
    if not stage:
        raise HTTPException(404, "Этап не найден")
    if data.label is not None and data.label.strip():
        stage.label = data.label.strip()
    if data.position is not None:
        stage.position = data.position
    await db.commit()
    await db.refresh(stage)
    return stage


@router.delete("/stages/{stage_id}")
async def delete_stage(stage_id: int, admin: dict = Depends(get_admin_user), db: AsyncSession = Depends(get_session)):
    stage = await db.get(OrderStage, stage_id)
    if not stage:
        raise HTTPException(404, "Этап не найден")
    if stage.is_final or stage.is_rejected:
        raise HTTPException(400, "Нельзя удалить финальный этап или этап отклонения")
    used = await db.scalar(select(func.count()).select_from(Order).where(Order.current_stage_id == stage_id))
    if used:
        raise HTTPException(400, "Этап используется в заказах")
    await db.delete(stage)
    await db.commit()
    return {"ok": True}
