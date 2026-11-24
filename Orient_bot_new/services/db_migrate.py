"""Безопасные миграции при старте: без потери данных и без ручного удаления БД."""
import logging

from sqlalchemy import inspect, select, text, update, delete
from sqlalchemy.engine import Connection

from services.text import make_search_text, parse_price

logger = logging.getLogger(__name__)

SEED_CATEGORIES = [
    ("Одежда", "👕"), ("Обувь", "👟"), ("Куртки", "🧥"), ("Кофты", "🧶"),
    ("Брюки", "👖"), ("Аксессуары", "👜"), ("Сумки", "🎒"),
]
REMOVED_CATEGORIES = ("Техника", "Дом и быт", "Другое")


def _add_missing_columns(conn: Connection, Base) -> None:
    insp = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            coltype = col.type.compile(dialect=conn.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'
            if col.server_default is not None:
                default = str(col.server_default.arg).replace("'", "''")
                ddl += f" DEFAULT '{default}'"
            logger.info("Schema sync: %s", ddl)
            conn.execute(text(ddl))


def _fix_indexes_and_data(conn: Connection) -> None:
    # Название магазина больше не уникально в заявках (заявки на правку и повторные подачи).
    for stmt in (
        "DROP INDEX IF EXISTS ix_shop_applications_shop_name",
        "CREATE INDEX IF NOT EXISTS ix_shop_applications_shop_name ON shop_applications (shop_name)",
        "CREATE INDEX IF NOT EXISTS ix_profiles_tg_username ON profiles (tg_username)",
        "CREATE INDEX IF NOT EXISTS ix_marketplace_items_price_value ON marketplace_items (price_value)",
        # Только Беларусь.
        "UPDATE marketplace_items SET country='BY' WHERE country IS NULL OR country<>'BY'",
        "UPDATE shops SET country='BY' WHERE country IS NULL OR country<>'BY'",
        "UPDATE shop_applications SET country='BY' WHERE country IS NULL OR country<>'BY'",
        "UPDATE profiles SET country='BY' WHERE country IS NULL OR country<>'BY'",
        # Функция «Ищу» удалена: такие объявления скрываем (данные не удаляем).
        "UPDATE marketplace_items SET is_active=false WHERE type<>'sell'"
        if conn.dialect.name == "postgresql"
        else "UPDATE marketplace_items SET is_active=0 WHERE type<>'sell'",
    ):
        try:
            conn.execute(text(stmt))
        except Exception as e:  # таблицы могут отсутствовать в нестандартных БД
            logger.warning("Migration step skipped (%s): %s", stmt[:60], e)


async def run_startup_migrations(engine, Base, async_session) -> None:
    import models  # noqa: F401  (регистрирует таблицы в Base.metadata)
    from models import Category, MarketplaceItem, Shop

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(lambda c: _add_missing_columns(c, Base))
        await conn.run_sync(_fix_indexes_and_data)

    async with async_session() as session:
        # Категории: первичное наполнение и удаление ненужных.
        has_any = (await session.execute(select(Category.id).limit(1))).first()
        if not has_any:
            session.add_all([Category(name=n, icon=i, position=pos) for pos, (n, i) in enumerate(SEED_CATEGORIES)])
        else:
            removed_ids = (await session.execute(
                select(Category.id).where(Category.name.in_(REMOVED_CATEGORIES))
            )).scalars().all()
            if removed_ids:
                await session.execute(
                    update(MarketplaceItem).where(MarketplaceItem.category_id.in_(removed_ids)).values(category_id=None)
                )
                await session.execute(delete(Category).where(Category.id.in_(removed_ids)))

        # Бэкфилл числовой цены и поискового текста для старых записей.
        items = (await session.execute(
            select(MarketplaceItem).where(
                (MarketplaceItem.search_text.is_(None))
                | ((MarketplaceItem.price.isnot(None)) & (MarketplaceItem.price_value.is_(None)))
            )
        )).scalars().all()
        for it in items:
            it.search_text = make_search_text(it.title, it.description)
            if it.price and it.price_value is None:
                try:
                    it.price, it.price_value = parse_price(it.price)
                except ValueError:
                    it.price_value = None
        shops = (await session.execute(select(Shop).where(Shop.search_text.is_(None)))).scalars().all()
        for sh in shops:
            sh.search_text = make_search_text(sh.name, sh.description, sh.city)
        await session.commit()
