import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import admin, marketplace, orders, reviews, shops, stages, users
from bot.handlers import dp
from config import BASE_DIR, UPLOAD_DIR, WEBAPP_URL
from database import init_db
from services.logging_config import setup_logging
from services.telegram_service import bot

setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = str(BASE_DIR / "static")
os.makedirs(UPLOAD_DIR, exist_ok=True)  # до монтирования StaticFiles


async def _run_polling():
    try:
        await dp.start_polling(bot, handle_signals=False)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Bot polling stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    polling_task = asyncio.create_task(_run_polling())
    yield
    polling_task.cancel()
    try:
        await polling_task
    except (asyncio.CancelledError, Exception):
        pass
    await bot.session.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[WEBAPP_URL], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path in ("/", "/admin"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(stages.router)
app.include_router(users.router)
app.include_router(marketplace.router)
app.include_router(marketplace.categories_router)
app.include_router(shops.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/admin")
async def admin_page():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


@app.get("/health")
async def health():
    return {"ok": True}
