import logging
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config import ADMIN_IDS
from bot.keyboards import main_menu_keyboard, admin_order_keyboard, review_moderation_keyboard
from bot.states import AdminStates
from database import async_session
from models import Order, User, Message as OrderMessage, Review, OrderStage
from services.notification_service import (
    notify_client_price, notify_client_message, notify_client_status, notify_client_stage,
)
from services.stage_service import get_all_stages, get_next_stage, get_prev_stage, get_rejected_stage

logger = logging.getLogger(__name__)
router = Router()

def _stage_label(order):
    return order.current_stage.label if order.current_stage else "—"

@router.message(Command("start"))
async def start(message: Message):
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(
        "Добро пожаловать в Orient! Откройте маркет в мини-приложении.",
        reply_markup=main_menu_keyboard(is_admin)
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Помощь:\n"
        "/start — главное меню\n"
        "/myorders — мои заказы\n"
        "/admin — панель управления\n"
        "/orders — список заказов\n"
        "/reply <id> <текст> — ответ клиенту"
    )

@router.message(Command("myorders"))
async def my_orders(message: Message):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("У вас пока нет заказов.")
            return
        result = await db.execute(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()))
        orders = result.scalars().all()
        if not orders:
            await message.answer("У вас пока нет заказов.")
            return
        text = "Ваши заказы:\n\n" + "\n".join(
            f"#{o.id} — {_stage_label(o)} — {o.price or 'цена не указана'}" for o in orders
        )
        await message.answer(text)

@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Админ-панель:", reply_markup=main_menu_keyboard(is_admin=True))

@router.message(Command("orders"))
async def orders_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with async_session() as db:
        result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(20))
        orders = result.scalars().all()
        if not orders:
            await message.answer("Нет заказов.")
            return
        for o in orders:
            await message.answer(
                f"#{o.id} — {_stage_label(o)} — {o.price or '—'}",
                reply_markup=admin_order_keyboard(o.id)
            )

@router.message(Command("reply"))
async def reply_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Использование: /reply <order_id> <текст>")
        return
    order_id = int(parts[1])
    text = parts[2]
    async with async_session() as db:
        order = await db.get(Order, order_id)
        if not order:
            await message.answer("Заказ не найден")
            return
        user = await db.get(User, order.user_id)
        msg = OrderMessage(order_id=order.id, sender_id=message.from_user.id, message_text=text, message_type="text")
        db.add(msg)
        await db.commit()
        await notify_client_message(order, user, text, prefix="💬 Ответ по заказу")
    await message.answer("Отправлено клиенту.")

@router.callback_query(F.data.startswith("order:"))
async def admin_order_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    order_id = int(parts[2])
    if action == "price":
        await state.set_state(AdminStates.waiting_price)
        await state.update_data(order_id=order_id)
        await callback.message.answer("Введите стоимость заказа:")
    elif action == "reply":
        await state.set_state(AdminStates.waiting_reply)
        await state.update_data(order_id=order_id)
        await callback.message.answer("Введите сообщение для клиента:")
    elif action == "question":
        await state.set_state(AdminStates.waiting_question)
        await state.update_data(order_id=order_id)
        await callback.message.answer("Введите вопрос для клиента:")
    elif action == "info":
        async with async_session() as db:
            result = await db.execute(
                select(Order).options(selectinload(Order.messages), selectinload(Order.current_stage)).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order:
                user = await db.get(User, order.user_id)
                history = "\n".join(
                    f"{'👤' if m.sender_id == user.telegram_id else '👨‍💼'} {m.message_text}"
                    for m in order.messages[-10:]
                ) or "—"
                await callback.message.answer(
                    f"Заказ #{order.id}\n"
                    f"Клиент: {user.first_name or '—'} @{user.username or '—'}\n"
                    f"Телефон: {order.phone or '—'}\n"
                    f"Email: {order.email or '—'}\n"
                    f"Адрес: {order.delivery_address or '—'}\n"
                    f"Промокод: {order.promo_code or '—'}\n"
                    f"Описание: {order.description}\n"
                    f"Комментарий: {order.additional_comment or '—'}\n"
                    f"Этап: {_stage_label(order)}\n"
                    f"Цена: {order.price or '—'}\n\n"
                    f"История:\n{history}"
                )
    await callback.answer()

@router.callback_query(F.data.startswith("stage:"))
async def stage_action(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    if action == "menu":
        async with async_session() as db:
            stages = await get_all_stages(db)
            text = "Этапы заказа:\n\n" + "\n".join(
                f"{s.position}. {s.label}{' (финал)' if s.is_final else ''}{' (отклонён)' if s.is_rejected else ''}"
                for s in stages
            )
            await callback.message.answer(text + "\n\nУправление — в админ-панели.")
        await callback.answer()
        return
    order_id = int(parts[2])
    async with async_session() as db:
        order = await db.get(Order, order_id)
        if not order:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        user = await db.get(User, order.user_id)
        if action == "next":
            stage = await get_next_stage(db, order.current_stage_id)
            if not stage:
                await callback.answer("Уже последний этап", show_alert=True)
                return
        elif action == "prev":
            stage = await get_prev_stage(db, order.current_stage_id)
            if not stage:
                await callback.answer("Уже первый этап", show_alert=True)
                return
        elif action == "complete":
            stages = await get_all_stages(db)
            stage = next((s for s in stages if s.is_final and not s.is_rejected), None)
        elif action == "reject":
            stage = await get_rejected_stage(db)
        else:
            await callback.answer()
            return
        if not stage:
            await callback.answer("Этап не настроен", show_alert=True)
            return
        order.current_stage_id = stage.id
        if stage.is_rejected:
            order.status = "rejected"
        elif stage.is_final:
            order.status = "completed"
        else:
            order.status = "active"
        await db.commit()
        await notify_client_stage(order, user, stage)
        await callback.message.answer(f"Заказ #{order_id}: {stage.label}")
    await callback.answer()

@router.callback_query(F.data.startswith("review:"))
async def review_action(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    review_id = int(parts[2])
    async with async_session() as db:
        review = await db.get(Review, review_id)
        if not review:
            await callback.answer("Отзыв не найден", show_alert=True)
            return
        review.status = "published" if action == "publish" else "hidden"
        await db.commit()
    await callback.message.answer(f"Отзыв #{review_id}: {'опубликован' if action == 'publish' else 'скрыт'}")
    await callback.answer()

@router.message(AdminStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    order_id = data["order_id"]
    price = message.text.strip()
    async with async_session() as db:
        order = await db.get(Order, order_id)
        if not order:
            await message.answer("Заказ не найден")
            await state.clear()
            return
        order.price = price
        await db.commit()
        user = await db.get(User, order.user_id)
        await notify_client_price(order, user)
    await message.answer(f"Цена {price} отправлена клиенту.")
    await state.clear()

@router.message(AdminStates.waiting_reply)
async def process_reply(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    order_id = data["order_id"]
    text = message.text.strip()
    async with async_session() as db:
        order = await db.get(Order, order_id)
        if not order:
            await message.answer("Заказ не найден")
            await state.clear()
            return
        user = await db.get(User, order.user_id)
        msg = OrderMessage(order_id=order.id, sender_id=message.from_user.id, message_text=text, message_type="text")
        db.add(msg)
        await db.commit()
        await notify_client_message(order, user, text)
    await message.answer("Сообщение отправлено клиенту.")
    await state.clear()

@router.message(AdminStates.waiting_question)
async def process_question(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    order_id = data["order_id"]
    text = message.text.strip()
    async with async_session() as db:
        order = await db.get(Order, order_id)
        if not order:
            await message.answer("Заказ не найден")
            await state.clear()
            return
        user = await db.get(User, order.user_id)
        msg = OrderMessage(order_id=order.id, sender_id=message.from_user.id, message_text=text, message_type="question")
        db.add(msg)
        await db.commit()
        await notify_client_message(order, user, f"❓ {text}", prefix="Вопрос по заказу")
    await message.answer("Вопрос отправлен клиенту.")
    await state.clear()

dp = Dispatcher()
dp.include_router(router)