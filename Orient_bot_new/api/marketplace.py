from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Ctx, get_optional_user, get_registered
from config import MAX_ITEM_PHOTOS
from database import get_session
from models import Category, MarketplaceItem, MarketplacePhoto, Shop
from schemas import MarketItemOut, MyItemsOut
from services.market_service import item_load_options, item_out
from services.media import delete_media, save_image
from services.shop_service import release_expired_blocks
from services.text import (
    clean_contact_mode, clean_delivery, clean_phone, clean_str, like_pattern,
    make_search_text, parse_price,
)

router = APIRouter(prefix="/api/market", tags=["market"])
categories_router = APIRouter(tags=["categories"])

CURRENCIES = ("BYN", "USD", "EUR", "RUB")


@categories_router.get("/api/categories")
async def list_categories(db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Category).order_by(Category.position, Category.id))).scalars().all()
    return [{"id": c.id, "parent_id": c.parent_id, "name": c.name, "icon": c.icon, "position": c.position} for c in rows]


def _visible_filter():
    """Активные объявления; объявления заблокированных магазинов скрыты."""
    return (
        MarketplaceItem.is_active.is_(True),
        MarketplaceItem.type == "sell",
        (MarketplaceItem.shop_id.is_(None)) | (Shop.status == "active"),
    )


@router.get("", response_model=list[MarketItemOut])
async def list_items(
    q: str | None = None,
    category_id: int | None = None,
    shop_id: int | None = None,
    sort: str = "new",
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    viewer: dict | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
):
    await release_expired_blocks(db)
    query = (
        select(MarketplaceItem)
        .outerjoin(Shop, MarketplaceItem.shop_id == Shop.id)
        .options(*item_load_options())
        .where(*_visible_filter())
    )
    if category_id:
        query = query.where(MarketplaceItem.category_id == category_id)
    if shop_id:
        query = query.where(MarketplaceItem.shop_id == shop_id)
    if q and q.strip():
        query = query.where(MarketplaceItem.search_text.like(like_pattern(q), escape="\\"))
    if sort == "price_asc":
        query = query.order_by(MarketplaceItem.price_value.asc().nullslast(), MarketplaceItem.id.desc())
    elif sort == "price_desc":
        query = query.order_by(MarketplaceItem.price_value.desc().nullslast(), MarketplaceItem.id.desc())
    elif sort == "views":
        query = query.order_by(MarketplaceItem.views.desc(), MarketplaceItem.id.desc())
    else:
        query = query.order_by(MarketplaceItem.created_at.desc(), MarketplaceItem.id.desc())
    items = (await db.execute(query.limit(limit).offset(offset))).scalars().all()
    viewer_id = viewer["id"] if viewer else None
    return [item_out(i, viewer_id) for i in items]


@router.get("/my", response_model=MyItemsOut)
async def my_items(ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(
        select(MarketplaceItem)
        .options(*item_load_options())
        .where(MarketplaceItem.user_id == ctx.user.id, MarketplaceItem.is_active.is_(True), MarketplaceItem.type == "sell")
        .order_by(MarketplaceItem.created_at.desc(), MarketplaceItem.id.desc())
    )).scalars().all()
    out = [item_out(i, ctx.user.telegram_id) for i in rows]
    return {"private": [i for i in out if not i["shop_id"]], "shop": [i for i in out if i["shop_id"]]}


async def _owned_shop(db: AsyncSession, tg_id: int, shop_id: int) -> Shop:
    shop = await db.get(Shop, shop_id)
    # Добавлять и менять объявления магазина может только его владелец (не менеджер).
    if not shop or shop.owner_telegram_id != tg_id:
        raise HTTPException(403, "Объявления в магазин может добавлять только его владелец")
    if shop.status != "active":
        raise HTTPException(403, "Магазин заблокирован модератором")
    return shop


def _to_int(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise HTTPException(400, "Некорректный числовой параметр")
    return int(raw)


def _validate_common(title: str, description: str, price: str | None, currency: str, category_id: str | None):
    title = title.strip()
    if len(title) < 2:
        raise HTTPException(400, "Введите название (минимум 2 символа)")
    if len(title) > 120:
        raise HTTPException(400, "Название слишком длинное (максимум 120 символов)")
    if len(description) > 4000:
        raise HTTPException(400, "Описание слишком длинное (максимум 4000 символов)")
    if currency not in CURRENCIES:
        raise HTTPException(400, "Некорректная валюта")
    try:
        price_text, price_value = parse_price(price)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return title, price_text, price_value


async def _check_category(db: AsyncSession, category_id: int | None):
    if category_id and not await db.get(Category, category_id):
        raise HTTPException(400, "Категория не найдена")


def _contact_fields(shop: Shop | None, phone: str | None, contact_mode: str | None, city: str | None,
                    delivery_methods: str | None, pickup_address: str | None) -> dict:
    if shop:  # контакты и доставка магазина берутся из самого магазина
        return {"phone": "", "contact_mode": "messages", "city": None, "delivery_methods": None, "pickup_address": None}
    try:
        phone_c = clean_phone(phone)
        mode = clean_contact_mode(contact_mode, phone_c)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "phone": phone_c, "contact_mode": mode, "city": clean_str(city, 128),
        "delivery_methods": clean_delivery(delivery_methods), "pickup_address": clean_str(pickup_address, 500),
    }


@router.post("", response_model=dict)
async def create_item(
    title: str = Form(...), description: str = Form(""),
    price: str | None = Form(None), currency: str = Form("BYN"),
    category_id: str | None = Form(None), shop_id: str | None = Form(None),
    phone: str | None = Form(None), contact_mode: str | None = Form("messages"),
    city: str | None = Form(None), delivery_methods: str | None = Form(None),
    pickup_address: str | None = Form(None),
    photos: list[UploadFile] = File(default=[]),
    ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session),
):
    title, price_text, price_value = _validate_common(title, description.strip(), price, currency, category_id)
    category_id, shop_id = _to_int(category_id), _to_int(shop_id)
    await _check_category(db, category_id)
    shop = await _owned_shop(db, ctx.user.telegram_id, shop_id) if shop_id else None
    files = [f for f in photos if f and f.filename]
    if len(files) > MAX_ITEM_PHOTOS:
        raise HTTPException(400, f"Максимум {MAX_ITEM_PHOTOS} фото")
    fields = _contact_fields(shop, phone, contact_mode, city, delivery_methods, pickup_address)

    item = MarketplaceItem(
        user_id=ctx.user.id, shop_id=shop.id if shop else None, category_id=category_id, type="sell",
        title=title, description=description.strip(), price=price_text, price_value=price_value,
        currency=currency, search_text=make_search_text(title, description), country="BY", **fields,
    )
    db.add(item)
    await db.flush()
    saved: list[str] = []
    try:
        for f in files:
            path = await save_image(f, f"market/{item.id}")
            saved.append(path)
            db.add(MarketplacePhoto(item_id=item.id, file_path=path))
        await db.commit()
    except Exception:
        await db.rollback()
        for p in saved:
            delete_media(p)
        raise
    return {"ok": True, "id": item.id}


async def _get_own_item(db: AsyncSession, item_id: int, ctx: Ctx) -> MarketplaceItem:
    item = (await db.execute(
        select(MarketplaceItem).options(*item_load_options()).where(MarketplaceItem.id == item_id)
    )).scalar_one_or_none()
    if not item or not item.is_active:
        raise HTTPException(404, "Объявление не найдено")
    if item.user_id != ctx.user.id:
        raise HTTPException(403, "Это не ваше объявление")
    if item.shop_id:
        await _owned_shop(db, ctx.user.telegram_id, item.shop_id)
    return item


@router.put("/{item_id}", response_model=dict)
async def update_item(
    item_id: int,
    title: str = Form(...), description: str = Form(""),
    price: str | None = Form(None), currency: str = Form("BYN"),
    category_id: str | None = Form(None),
    phone: str | None = Form(None), contact_mode: str | None = Form("messages"),
    city: str | None = Form(None), delivery_methods: str | None = Form(None),
    pickup_address: str | None = Form(None),
    remove_photos: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
    ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session),
):
    item = await _get_own_item(db, item_id, ctx)
    title, price_text, price_value = _validate_common(title, description.strip(), price, currency, category_id)
    category_id = _to_int(category_id)
    await _check_category(db, category_id)

    remove_ids = {int(x) for x in remove_photos.split(",") if x.strip().isdigit()}
    to_remove = [p for p in item.photos if p.id in remove_ids]
    new_files = [f for f in photos if f and f.filename]
    if len(item.photos) - len(to_remove) + len(new_files) > MAX_ITEM_PHOTOS:
        raise HTTPException(400, f"Максимум {MAX_ITEM_PHOTOS} фото")

    fields = _contact_fields(item.shop, phone, contact_mode, city, delivery_methods, pickup_address)
    item.title, item.description = title, description.strip()
    item.price, item.price_value, item.currency = price_text, price_value, currency
    item.category_id = category_id
    item.search_text = make_search_text(title, description)
    for k, v in fields.items():
        setattr(item, k, v)

    saved: list[str] = []
    try:
        for f in new_files:
            path = await save_image(f, f"market/{item.id}")
            saved.append(path)
            db.add(MarketplacePhoto(item_id=item.id, file_path=path))
        for p in to_remove:
            await db.delete(p)
        await db.commit()
    except Exception:
        await db.rollback()
        for p in saved:
            delete_media(p)
        raise
    for p in to_remove:
        delete_media(p.file_path)
    return {"ok": True, "id": item.id}


@router.delete("/{item_id}", response_model=dict)
async def delete_item(item_id: int, ctx: Ctx = Depends(get_registered), db: AsyncSession = Depends(get_session)):
    item = (await db.execute(
        select(MarketplaceItem).options(*item_load_options()).where(MarketplaceItem.id == item_id)
    )).scalar_one_or_none()
    if not item or not item.is_active:
        raise HTTPException(404, "Объявление не найдено")
    if item.user_id != ctx.user.id:
        raise HTTPException(403, "Это не ваше объявление")
    # Мягкое удаление: заказы на этот товар остаются в истории покупок.
    item.is_active = False
    paths = [p.file_path for p in item.photos]
    for p in list(item.photos):
        await db.delete(p)
    await db.commit()
    for path in paths:
        delete_media(path)
    return {"ok": True}


@router.post("/{item_id}/view", response_model=dict)
async def count_view(item_id: int, db: AsyncSession = Depends(get_session)):
    item = await db.get(MarketplaceItem, item_id)
    if not item or not item.is_active:
        raise HTTPException(404, "Объявление не найдено")
    item.views = (item.views or 0) + 1
    await db.commit()
    return {"ok": True}
