import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import Ctx, get_current_user, get_optional_user, get_registered, is_admin_id
from config import ADMIN_IDS, WEBAPP_URL
from database import get_session
from models import (
    AdminUser, MarketplaceItem, Shop, ShopApplication, ShopOrder, ShopOrderMessage,
    ShopReview, ShopStage,
)
from schemas import (
    ShopApplicationOut, ShopOrderMessageCreate, ShopOrderMessageOut, ShopOrderOut,
    ShopOrderStageSet, ShopOut, ShopReviewCreate, ShopReviewOut, StageCreate,
)
from services.market_service import item_load_options, item_out
from services.media import delete_media, save_image
from services.rate_limit import client_key, rate_limit
from services.shop_service import (  # noqa: F401  (DEFAULT_SHOP_STAGES реэкспортируется для admin.py)
    DEFAULT_SHOP_STAGES, release_expired_blocks, username_by_tg_ids,
)
from services.telegram_service import bot
from services.text import (
    clean_contact_mode, clean_delivery, clean_phone, clean_str, clean_username,
    like_pattern, make_search_text,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shops", tags=["shops"])


def _is_staff(shop: Shop, tg_id: int) -> bool:
    return tg_id == shop.owner_telegram_id or (shop.manager_telegram_id is not None and tg_id == shop.manager_telegram_id)


async def _notify_admins(db: AsyncSession, text: str, with_panel_button: bool = True):
    db_admins = (await db.execute(select(AdminUser.telegram_id))).scalars().all()
    markup = None
    if with_panel_button and WEBAPP_URL.startswith("https://"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Открыть модерацию", web_app=WebAppInfo(url=f"{WEBAPP_URL}/admin"))]
        ])
    for admin_id in set(ADMIN_IDS) | set(db_admins):
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as e:
            logger.warning("Cannot notify admin %s: %s", admin_id, e)


async def _safe_send(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.warning("Cannot send message to %s: %s", chat_id, e)


# --- СПИСОК МАГАЗИНОВ ---
@router.get("", response_model=list[ShopOut])
async def list_shops(
    q: str | None = None,
    min_rating: float | None = None,
    sort: str = "boost",
    db: AsyncSession = Depends(get_session),
):
    await release_expired_blocks(db)
    query = select(Shop).options(selectinload(Shop.stages)).where(Shop.status == "active")
    if q and q.strip():
        query = query.where(Shop.search_text.like(like_pattern(q), escape="\\"))
    if min_rating is not None:
        query = query.where(Shop.rating_avg >= min_rating)
    if sort == "rating":
        query = query.order_by(Shop.rating_avg.desc(), Shop.reviews_count.desc())
    elif sort == "orders":
        query = query.order_by(Shop.orders_count.desc(), Shop.rating_avg.desc())
    elif sort == "new":
        query = query.order_by(Shop.created_at.desc())
    else:
        query = query.order_by(
            Shop.boost_until.desc().nullslast(), Shop.rating_avg.desc(),
            Shop.orders_count.desc(), Shop.created_at.desc(),
        )
    return (await db.execute(query)).scalars().all()


# --- МОЙ МАГАЗИН И ЗАЯВКИ ---
@router.get("/my/status")
async def my_shop_status(user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await release_expired_blocks(db)
    tg_id = user_data["id"]
    owned = (await db.execute(
        select(Shop).options(selectinload(Shop.stages)).where(Shop.owner_telegram_id == tg_id)
    )).scalars().first()
    managed = None
    if not owned:
        managed = (await db.execute(
            select(Shop).options(selectinload(Shop.stages)).where(Shop.manager_telegram_id == tg_id)
        )).scalars().first()
    latest_app = (await db.execute(
        select(ShopApplication).where(ShopApplication.applicant_telegram_id == tg_id)
        .order_by(ShopApplication.id.desc()).limit(1)
    )).scalars().first()
    return {
        "shop": ShopOut.model_validate(owned) if owned else None,
        "managed_shop": ShopOut.model_validate(managed) if managed else None,
        "application": ShopApplicationOut.model_validate(latest_app) if latest_app else None,
    }


@router.post("/applications", response_model=ShopApplicationOut)
async def submit_shop_application(
    request: Request,
    shop_name: str = Form(...),
    description: str | None = Form(None),
    city: str | None = Form(None),
    phone: str | None = Form(None),
    contact_mode: str | None = Form("messages"),
    manager_username: str | None = Form(None),
    manager_telegram_id: str | None = Form(None),
    instagram_url: str | None = Form(None),
    tiktok_url: str | None = Form(None),
    pickup_address: str | None = Form(None),
    delivery_methods: str | None = Form(None),
    remove_logo: str = Form("0"),
    logo: UploadFile | None = File(None),
    ctx: Ctx = Depends(get_registered),
    db: AsyncSession = Depends(get_session),
):
    """Единая точка: создание магазина (kind=create) или правка существующего (kind=edit).
    В обоих случаях изменения применяются только после одобрения модератором."""
    tg_id = ctx.user.telegram_id
    rate_limit(client_key(request, tg_id), limit=5, window=300)

    name = (shop_name or "").strip()
    if len(name) < 2 or len(name) > 60:
        raise HTTPException(400, "Название магазина: от 2 до 60 символов")

    owned = (await db.execute(select(Shop).where(Shop.owner_telegram_id == tg_id))).scalars().first()
    pending = (await db.execute(
        select(ShopApplication.id).where(ShopApplication.applicant_telegram_id == tg_id, ShopApplication.status == "pending")
    )).first()
    if pending:
        raise HTTPException(400, "Ваша предыдущая заявка ещё на рассмотрении")

    name_clash = (await db.execute(
        select(Shop.id).where(func.lower(Shop.name) == name.lower(), Shop.id != (owned.id if owned else -1))
    )).first()
    app_clash = (await db.execute(
        select(ShopApplication.id).where(
            func.lower(ShopApplication.shop_name) == name.lower(),
            ShopApplication.status == "pending",
            ShopApplication.applicant_telegram_id != tg_id,
        )
    )).first()
    if name_clash or app_clash:
        raise HTTPException(400, "Магазин с таким названием уже существует. Выберите другое название.")

    try:
        phone_c = clean_phone(phone)
        mode = clean_contact_mode(contact_mode, phone_c)
        mgr_username = clean_username(manager_username)
    except ValueError as e:
        raise HTTPException(400, str(e))
    mgr_id_raw = (manager_telegram_id or "").strip()
    if mgr_id_raw and not mgr_id_raw.isdigit():
        raise HTTPException(400, "Telegram ID менеджера должен состоять из цифр")

    logo_value: str | None = None  # None — не менять
    if logo is not None and logo.filename:
        logo_value = await save_image(logo, f"shops/{tg_id}", max_bytes=5 * 1024 * 1024)
    elif owned and remove_logo == "1":
        logo_value = ""

    app_obj = ShopApplication(
        applicant_telegram_id=tg_id,
        kind="edit" if owned else "create",
        shop_id=owned.id if owned else None,
        shop_name=name,
        description=clean_str(description, 2000),
        country="BY",
        city=clean_str(city, 128),
        manager_telegram_id=int(mgr_id_raw) if mgr_id_raw else None,
        manager_username=mgr_username,
        instagram_url=clean_str(instagram_url, 512),
        tiktok_url=clean_str(tiktok_url, 512),
        logo=logo_value,
        phone=phone_c or None,
        contact_mode=mode,
        pickup_address=clean_str(pickup_address, 500),
        delivery_methods=clean_delivery(delivery_methods),
        status="pending",
    )
    db.add(app_obj)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        delete_media(logo_value)
        raise
    await db.refresh(app_obj)

    kind_txt = "✏️ Изменение магазина" if owned else "🏬 Новый магазин"
    await _notify_admins(db, (
        f"{kind_txt} — заявка #{app_obj.id}\n"
        f"Название: {app_obj.shop_name}\n"
        f"Город: {app_obj.city or '—'}\n"
        f"Заявитель: @{ctx.username} (ID {tg_id})\n"
        f"Откройте модерацию для одобрения или отклонения."
    ))
    return app_obj


# --- КАРТОЧКА МАГАЗИНА ---
@router.get("/{shop_id}")
async def get_shop(shop_id: int, viewer: dict | None = Depends(get_optional_user), db: AsyncSession = Depends(get_session)):
    await release_expired_blocks(db)
    shop = (await db.execute(select(Shop).options(selectinload(Shop.stages)).where(Shop.id == shop_id))).scalar_one_or_none()
    viewer_id = viewer["id"] if viewer else None
    if not shop or (shop.status != "active" and not (viewer_id and (shop.owner_telegram_id == viewer_id or await is_admin_id(db, viewer_id)))):
        raise HTTPException(404, "Магазин не найден")
    items = (await db.execute(
        select(MarketplaceItem).options(*item_load_options())
        .where(MarketplaceItem.shop_id == shop_id, MarketplaceItem.is_active.is_(True))
        .order_by(MarketplaceItem.created_at.desc())
    )).scalars().all()
    reviews = (await db.execute(
        select(ShopReview).where(ShopReview.shop_id == shop_id).order_by(ShopReview.created_at.desc())
    )).scalars().all()
    return {
        "shop": ShopOut.model_validate(shop),
        "items": [item_out(i, viewer_id) for i in items],
        "reviews": [ShopReviewOut.model_validate(r) for r in reviews],
    }


@router.get("/{shop_id}/reviews", response_model=list[ShopReviewOut])
async def list_shop_reviews(shop_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(ShopReview).where(ShopReview.shop_id == shop_id).order_by(ShopReview.created_at.desc()))
    return result.scalars().all()


@router.post("/{shop_id}/reviews", response_model=ShopReviewOut)
async def create_shop_review(
    shop_id: int, data: ShopReviewCreate,
    ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session),
):
    shop = await db.get(Shop, shop_id)
    if not shop or shop.status != "active":
        raise HTTPException(404, "Магазин не найден")
    tg_id = ctx.user.telegram_id
    if _is_staff(shop, tg_id):
        raise HTTPException(400, "Нельзя оставить отзыв о собственном магазине")
    if (await db.execute(select(ShopReview.id).where(ShopReview.shop_id == shop_id, ShopReview.author_telegram_id == tg_id))).first():
        raise HTTPException(400, "Вы уже оставляли отзыв об этом магазине")

    review = ShopReview(
        shop_id=shop_id, author_telegram_id=tg_id,
        author_name=(data.author_name or "").strip() or ctx.user.first_name or f"@{ctx.username}",
        rating=data.rating, text=data.text.strip(),
    )
    db.add(review)
    await db.flush()
    stats = (await db.execute(
        select(func.count(ShopReview.id), func.avg(ShopReview.rating)).where(ShopReview.shop_id == shop_id)
    )).one()
    shop.reviews_count = int(stats[0] or 0)
    shop.rating_avg = round(float(stats[1] or 0.0), 2)
    await db.commit()
    await db.refresh(review)
    return review


@router.post("/{shop_id}/stages")
async def add_shop_stage(
    shop_id: int, data: StageCreate,
    user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Магазин не найден")
    if not _is_staff(shop, user_data["id"]):
        raise HTTPException(403, "Недостаточно прав")
    stages = (await db.execute(select(ShopStage).where(ShopStage.shop_id == shop_id).order_by(ShopStage.position))).scalars().all()
    pos = data.position if data.position is not None else ((stages[-1].position + 1) if stages else 1)
    stage = ShopStage(shop_id=shop_id, label=data.label.strip(), position=pos)
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return {"id": stage.id, "shop_id": stage.shop_id, "label": stage.label, "position": stage.position}


# --- ЗАКАЗЫ ---
@router.post("/{shop_id}/order/{item_id}")
async def create_order(
    shop_id: int, item_id: int,
    ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session),
):
    await release_expired_blocks(db)
    shop = await db.get(Shop, shop_id)
    item = await db.get(MarketplaceItem, item_id)
    if not shop or not item or item.shop_id != shop.id or not item.is_active or shop.status != "active":
        raise HTTPException(404, "Товар недоступен")
    tg_id = ctx.user.telegram_id
    if _is_staff(shop, tg_id):
        raise HTTPException(400, "Нельзя покупать товары собственного магазина")

    order = ShopOrder(shop_id=shop.id, item_id=item.id, buyer_telegram_id=tg_id, status="active")
    db.add(order)
    await db.flush()
    first_stage = (await db.execute(
        select(ShopStage).where(ShopStage.shop_id == shop.id).order_by(ShopStage.position).limit(1)
    )).scalar_one_or_none()
    if first_stage:
        order.current_stage_id = first_stage.id
    shop.orders_count = (shop.orders_count or 0) + 1
    await db.commit()
    await db.refresh(order)

    price_text = f"{item.price} {item.currency}" if item.price else "По договорённости"
    recipients = {shop.owner_telegram_id}
    if shop.manager_telegram_id:
        recipients.add(shop.manager_telegram_id)
    for rid in recipients:
        await _safe_send(rid, (
            f"🔔 Новый заказ #{order.id} в магазине «{shop.name}»\n"
            f"Товар: {item.title}\nЦена: {price_text}\nПокупатель: @{ctx.username}"
        ))
    await _safe_send(tg_id, (
        f"✅ Заказ #{order.id} оформлен!\nМагазин: {shop.name}\nТовар: {item.title}\n"
        f"Этап: {first_stage.label if first_stage else 'Новый'}"
    ))
    return {"ok": True, "order_id": order.id}


async def _orders_out(db: AsyncSession, orders: list[ShopOrder], with_buyers: bool) -> list[dict]:
    buyers = await username_by_tg_ids(db, {o.buyer_telegram_id for o in orders}) if with_buyers else {}
    stages_by_shop: dict[int, list] = {}
    if with_buyers:
        for sid in {o.shop_id for o in orders}:
            stages_by_shop[sid] = (await db.execute(
                select(ShopStage).where(ShopStage.shop_id == sid).order_by(ShopStage.position)
            )).scalars().all()
    out = []
    for o in orders:
        out.append(ShopOrderOut.model_validate({
            "id": o.id, "shop_id": o.shop_id, "item_id": o.item_id,
            "buyer_telegram_id": o.buyer_telegram_id, "buyer_username": buyers.get(o.buyer_telegram_id),
            "status": o.status, "current_stage_id": o.current_stage_id,
            "current_stage": o.current_stage, "created_at": o.created_at,
            "item": {"id": o.item.id, "title": o.item.title, "price": o.item.price, "currency": o.item.currency} if o.item else None,
            "shop": {"id": o.shop.id, "name": o.shop.name, "logo": o.shop.logo, "status": o.shop.status} if o.shop else None,
            "shop_stages": stages_by_shop.get(o.shop_id, []),
        }, from_attributes=True).model_dump(mode="json"))
    return out


_ORDER_LOAD = (selectinload(ShopOrder.item), selectinload(ShopOrder.current_stage), selectinload(ShopOrder.shop))


@router.get("/orders/my")
async def my_shop_orders(user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Заказы магазина (для владельца/менеджера)."""
    tg_id = user_data["id"]
    shop = (await db.execute(select(Shop).where((Shop.owner_telegram_id == tg_id) | (Shop.manager_telegram_id == tg_id)).order_by(
        (Shop.owner_telegram_id == tg_id).desc()
    ))).scalars().first()
    if not shop:
        return []
    orders = (await db.execute(
        select(ShopOrder).options(*_ORDER_LOAD).where(ShopOrder.shop_id == shop.id).order_by(ShopOrder.created_at.desc())
    )).scalars().all()
    return await _orders_out(db, orders, with_buyers=True)


@router.get("/orders/buyer")
async def my_buyer_orders(user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Покупки пользователя."""
    orders = (await db.execute(
        select(ShopOrder).options(*_ORDER_LOAD)
        .where(ShopOrder.buyer_telegram_id == user_data["id"]).order_by(ShopOrder.created_at.desc())
    )).scalars().all()
    return await _orders_out(db, orders, with_buyers=False)


@router.post("/orders/{order_id}/stage")
async def set_order_stage(
    order_id: int, data: ShopOrderStageSet,
    user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    order = await db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    shop = await db.get(Shop, order.shop_id)
    if not shop or not _is_staff(shop, user_data["id"]):
        raise HTTPException(403, "Недостаточно прав")
    stage = await db.get(ShopStage, data.stage_id)
    if not stage or stage.shop_id != shop.id:
        raise HTTPException(400, "Этап не принадлежит этому магазину")
    order.current_stage_id = stage.id
    low = stage.label.lower()
    order.status = "completed" if ("выполн" in low or "доставл" in low) else ("cancelled" if "отмен" in low else "active")
    await db.commit()
    await _safe_send(order.buyer_telegram_id, f"📦 Заказ #{order.id} ({shop.name})\nНовый статус: {stage.label}")
    return {"ok": True, "stage": stage.label, "status": order.status}


@router.post("/orders/{order_id}/stage/next")
async def next_stage(order_id: int, user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    order = await db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    shop = await db.get(Shop, order.shop_id)
    if not shop or not _is_staff(shop, user_data["id"]):
        raise HTTPException(403, "Недостаточно прав")
    stages = (await db.execute(select(ShopStage).where(ShopStage.shop_id == order.shop_id).order_by(ShopStage.position))).scalars().all()
    if not stages:
        raise HTTPException(400, "У магазина не настроены этапы")
    idx = next((i for i, s in enumerate(stages) if s.id == order.current_stage_id), -1)
    if idx + 1 >= len(stages):
        return {"ok": True, "stage": stages[-1].label}
    nxt = stages[idx + 1]
    order.current_stage_id = nxt.id
    low = nxt.label.lower()
    order.status = "completed" if ("выполн" in low or "доставл" in low) else ("cancelled" if "отмен" in low else "active")
    await db.commit()
    await _safe_send(order.buyer_telegram_id, f"📦 Заказ #{order.id} ({shop.name})\nНовый статус: {nxt.label}")
    return {"ok": True, "stage": nxt.label}


async def _order_access(db: AsyncSession, order_id: int, tg_id: int):
    order = await db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    shop = await db.get(Shop, order.shop_id)
    is_buyer = tg_id == order.buyer_telegram_id
    is_seller = shop is not None and _is_staff(shop, tg_id)
    if not is_buyer and not is_seller:
        raise HTTPException(403, "Нет доступа к чату этого заказа")
    return order, shop, is_buyer, is_seller


@router.get("/orders/{order_id}/messages", response_model=list[ShopOrderMessageOut])
async def get_order_messages(order_id: int, user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await _order_access(db, order_id, user_data["id"])
    result = await db.execute(select(ShopOrderMessage).where(ShopOrderMessage.shop_order_id == order_id).order_by(ShopOrderMessage.created_at.asc(), ShopOrderMessage.id.asc()))
    return result.scalars().all()


@router.post("/orders/{order_id}/messages", response_model=ShopOrderMessageOut)
async def send_order_message(
    order_id: int, data: ShopOrderMessageCreate, request: Request,
    user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    tg_id = user_data["id"]
    rate_limit(client_key(request, tg_id), limit=30, window=60)
    order, shop, is_buyer, is_seller = await _order_access(db, order_id, tg_id)
    msg = ShopOrderMessage(shop_order_id=order_id, sender_telegram_id=tg_id, sender_role="seller" if is_seller else "buyer", text=data.text.strip())
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    if is_seller and not is_buyer:
        await _safe_send(order.buyer_telegram_id, f"💬 Ответ магазина «{shop.name}» по заказу #{order.id}:\n{msg.text}")
    elif shop:
        for rid in {shop.owner_telegram_id, shop.manager_telegram_id} - {None}:
            await _safe_send(rid, f"💬 Сообщение от покупателя по заказу #{order.id} ({shop.name}):\n{msg.text}")
    return msg
