from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL, DB_CONNECT_ARGS


class Base(DeclarativeBase):
    pass


_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if DB_CONNECT_ARGS:
    _kwargs["connect_args"] = DB_CONNECT_ARGS
if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"timeout": 30}

engine = create_async_engine(DATABASE_URL, **_kwargs)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Создаёт таблицы, дозаводит недостающие колонки и чистит данные.

    Никогда не удаляет пользовательские данные: работает поверх существующей БД.
    """
    from services.db_migrate import run_startup_migrations
    await run_startup_migrations(engine, Base, async_session)


async def get_session():
    async with async_session() as session:
        yield session
