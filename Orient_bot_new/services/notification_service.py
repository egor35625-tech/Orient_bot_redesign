import logging
from aiogram.types import FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from services.telegram_service import bot
from config import ADMIN_IDS, WEBAPP_URL
from bot.keyboards import admin_order_keyboard

logger = logging.getLogger(__name__)

async def notify_admin_new_order(order, user, photos):
    contacts = (
        f"📞 Телефон: {order.phone or '—'}\n"
        f"✉️ Email: {order.email or '—'}\n"
        f"📍 Адрес: {order.delivery_address or '—'}\n"
        f"🎁 Промокод: {order.promo_code or '—'}\n"
    )
    text = (
        f"🛍 НОВЫЙ ЗАКАЗ\n\n"
        f"Номер заказа: #{order.id}\n"
        f"Клиент: {user.first_name or '—'}\n"
        f"Username: @{user.username or '—'}\n"
        f"Telegram ID: {user.telegram_id}\n\n"
        f"{contacts}\n"
        f"Описание:\n{order.description}\n\n"
        f"Дополнительный комментарий:\n{order.additional_comment or '—'}\n\n"
        f"Дата оформления:\n{order.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    contact_kb = InlineKeyboardMarkup(inline_keyboard=[])
    if order.phone:
        contact_kb.inline_keyboard.append([InlineKeyboardButton(text="📞 Позвонить", url=f"tel:{order.phone}")])
    if order.email:
        contact_kb.inline_keyboard.append([InlineKeyboardButton(text="✉️ Email", url=f"mailto:{order.email}")])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_order_keyboard(order.id))
            if contact_kb.inline_keyboard:
                await bot.send_message(admin_id, "Быстрые действия:", reply_markup=contact_kb)
            if photos:
                media = [InputMediaPhoto(media=FSInputFile(p.file_path)) for p in photos[:10]]
                sent = await bot.send_media_group(admin_id, media)
                for p, m in zip(photos[:10], sent):
                    if m.photo:
                        p.file_id = m.photo[-1].file_id
        except Exception as e:
            logger.exception("Failed to notify admin %s: %s", admin_id, e)

async def notify_admin_new_review(review, order):
    text = (
        f"⭐ НОВЫЙ ОТЗЫВ\n\n"
        f"Оценка: {'★' * review.rating}{'☆' * (5 - review.rating)}\n"
        f"Автор: {review.author_name or '—'}\n"
    )
    if review.order_id:
        text += f"Заказ: #{review.order_id}\n"
    text += f"\nТекст:\n{review.text}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"review:publish:{review.id}")],
        [InlineKeyboardButton(text="❌ Скрыть", callback_data=f"review:hide:{review.id}")],
    ])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:
            logger.exception("Failed to notify admin about review: %s", e)

async def notify_client_price(order, user):
    try:
        await bot.send_message(
            user.telegram_id,
            f"Здравствуйте! Стоимость вашего заказа #{order.id} составляет {order.price} {order.currency}"
        )
    except Exception as e:
        logger.exception("Failed to notify client %s: %s", user.telegram_id, e)

async def notify_client_status(order, user):
    try:
        await bot.send_message(
            user.telegram_id,
            f"Статус вашего заказа #{order.id}: {order.status}"
        )
    except Exception as e:
        logger.exception("Failed to notify client %s: %s", user.telegram_id, e)

async def notify_client_stage(order, user, stage):
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Открыть заказ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}?order_id={order.id}")
            )]
        ])
        await bot.send_message(
            user.telegram_id,
            f"📦 Ваш заказ #{order.id}\n\nНовый этап: <b>{stage.label}</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Failed to notify client %s: %s", user.telegram_id, e)

async def notify_client_message(order, user, text, prefix="💬 Сообщение"):
    try:
        await bot.send_message(user.telegram_id, f"{prefix} по заказу #{order.id}:\n{text}")
    except Exception as e:
        logger.exception("Failed to notify client %s: %s", user.telegram_id, e)