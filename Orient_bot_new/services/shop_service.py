from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    MarketplaceItem, MarketplacePhoto, Profile, Shop, ShopOrder, ShopOrderMessage,
    ShopReview, ShopStage,
)
from services.media import delete_media

DEFAULT_SHOP_STAGES = [
    "Новый", "Подтверждён", "Собирается", "Передан в доставку",
    "Готов к выдаче", "Выполнен", "Отменён",
]


def utcnow() -> datetime:
    """Naive UTC: одинаково работает в SQLite и PostgreSQL (колонка blocked_until без tz)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def release_expired_blocks(db: AsyncSession) -> None:
    """Снимает истёкшие временные блокировки."""
    now = utcnow()
    cond = (Shop.status == "blocked") & (Shop.blocked_until.isnot(None)) & (Shop.blocked_until <= now)
    if (await db.execute(select(Shop.id).where(cond).limit(1))).first():
        await db.execute(
            update(Shop).where(cond).values(status="active", blocked_until=None, block_reason=None)
        )
        await db.commit()


async def username_by_tg_ids(db: AsyncSession, tg_ids: set[int]) -> dict[int, str]:
    if not tg_ids:
        return {}
    from models import User
    rows = await db.execute(
        select(User.telegram_id, Profile.tg_username)
        .join(Profile, Profile.user_id == User.id)
        .where(User.telegram_id.in_(tg_ids), Profile.tg_username.isnot(None))
    )
    return {tg: name for tg, name in rows.all()}


async def delete_shop_cascade(db: AsyncSession, shop: Shop) -> None:
    """Полное удаление магазина вместе с товарами, заказами, отзывами и файлами."""
    item_ids = (await db.execute(select(MarketplaceItem.id).where(MarketplaceItem.shop_id == shop.id))).scalars().all()
    order_ids = (await db.execute(select(ShopOrder.id).where(ShopOrder.shop_id == shop.id))).scalars().all()
    if order_ids:
        await db.execute(ShopOrderMessage.__table__.delete().where(ShopOrderMessage.shop_order_id.in_(order_ids)))
        await db.execute(ShopOrder.__table__.delete().where(ShopOrder.id.in_(order_ids)))
    if item_ids:
        photos = (await db.execute(select(MarketplacePhoto).where(MarketplacePhoto.item_id.in_(item_ids)))).scalars().all()
        for ph in photos:
            delete_media(ph.file_path)
        await db.execute(MarketplacePhoto.__table__.delete().where(MarketplacePhoto.item_id.in_(item_ids)))
        await db.execute(MarketplaceItem.__table__.delete().where(MarketplaceItem.id.in_(item_ids)))
    await db.execute(ShopStage.__table__.delete().where(ShopStage.shop_id == shop.id))
    await db.execute(ShopReview.__table__.delete().where(ShopReview.shop_id == shop.id))
    delete_media(shop.logo)
    await db.delete(shop)


def shop_is_visible(shop: Shop | None) -> bool:
    return shop is None or shop.status == "active"
