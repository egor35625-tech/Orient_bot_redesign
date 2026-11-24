import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram.types import Update
from database import init_db
from services.telegram_service import bot
from services.logging_config import setup_logging
from bot.handlers import dp
from config import UPLOAD_DIR, WEBAPP_URL
from api import orders, admin, reviews, stages

setup_logging()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
WEBHOOK_URL = f"{WEBAPP_URL}/webhook/{WEBHOOK_SECRET}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    yield
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(stages.router)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/admin")
async def admin_page():
    return FileResponse("static/admin.html")