from sqlalchemy.orm import selectinload

from models import MarketplaceItem, Shop, User


def item_load_options():
    """Всё, что нужно для item_out, загружается заранее (async: ленивая загрузка запрещена)."""
    return (
        selectinload(MarketplaceItem.photos),
        selectinload(MarketplaceItem.user).selectinload(User.profile),
        selectinload(MarketplaceItem.shop),
    )


def item_out(item: MarketplaceItem, viewer_tg_id: int | None = None) -> dict:
    """Собирает ответ. У объявлений магазина контакты/город/доставка берутся из магазина,
    поэтому правки магазина (после модерации) сразу видны во всех его объявлениях."""
    shop: Shop | None = item.shop
    profile = item.user.profile if item.user else None
    if shop:
        seller = shop.manager_username or (profile.tg_username if profile else None)
        phone, mode = shop.phone or "", shop.contact_mode or "messages"
        city, delivery, pickup = shop.city, shop.delivery_methods, shop.pickup_address
    else:
        seller = profile.tg_username if profile else None
        phone, mode = item.phone or "", item.contact_mode or "messages"
        city, delivery, pickup = item.city, item.delivery_methods, item.pickup_address
    return {
        "id": item.id,
        "shop_id": item.shop_id,
        "category_id": item.category_id,
        "title": item.title,
        "description": item.description or "",
        "price": item.price,
        "currency": item.currency,
        "phone": phone,
        "contact_mode": mode if phone else "messages",
        "city": city,
        "country": "BY",
        "delivery_methods": delivery,
        "pickup_address": pickup,
        "views": item.views or 0,
        "created_at": item.created_at,
        "seller_username": seller,
        "is_mine": bool(viewer_tg_id and item.user and item.user.telegram_id == viewer_tg_id),
        "shop": {"id": shop.id, "name": shop.name, "logo": shop.logo, "status": shop.status} if shop else None,
        "photos": [{"id": p.id, "file_path": p.file_path} for p in item.photos],
    }
