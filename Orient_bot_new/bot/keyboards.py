from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import WEBAPP_URL

def main_menu_keyboard(is_admin=False):
    buttons = [[InlineKeyboardButton(text="🛍 Открыть маркет", web_app=WebAppInfo(url=WEBAPP_URL))]]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", web_app=WebAppInfo(url=f"{WEBAPP_URL}/admin"))])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_order_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Указать цену", callback_data=f"order:price:{order_id}")],
        [InlineKeyboardButton(text="💬 Ответить клиенту", callback_data=f"order:reply:{order_id}")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data=f"order:question:{order_id}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"stage:prev:{order_id}"),
         InlineKeyboardButton(text="Следующий ▶", callback_data=f"stage:next:{order_id}")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data=f"stage:complete:{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"stage:reject:{order_id}")],
        [InlineKeyboardButton(text="⚙️ Этапы", callback_data="stages:menu")],
        [InlineKeyboardButton(text="📋 Информация о заказе", callback_data=f"order:info:{order_id}")],
    ])

def review_moderation_keyboard(review_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"review:publish:{review_id}")],
        [InlineKeyboardButton(text="❌ Скрыть", callback_data=f"review:hide:{review_id}")],
    ])