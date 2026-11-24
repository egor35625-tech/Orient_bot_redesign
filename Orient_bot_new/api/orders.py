import os
import uuid
import html
import aiofiles
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_session
from models import User, Order, OrderPhoto, Message, Review
from schemas import OrderOut, OrderListOut, MessageOut, ReviewCreate, ReviewOut
from api.deps import get_current_user
from config import MAX_PHOTOS, MAX_FILE_SIZE, UPLOAD_DIR, ADMIN_IDS
from services.notification_service import notify_admin_new_order, notify_client_message, notify_admin_new_review
from services.rate_limit import rate_limit, client_key
from services.stage_service import get_all_stages

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.post("", response_model=dict)
async def create_order(
    request: Request,
    description: str = Form(...),
    additional_comment: str | None = Form(None),
    phone: str = Form(...),
    email: str | None = Form(None),
    delivery_address: str = Form(...),
    promo_code: str | None = Form(None),
    consent: str = Form("false"),
    photos: list[UploadFile] = File(default=[]),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    rate_limit(client_key(request, user_data["id"]), limit=5, window=60)
    if not description.strip():
        raise HTTPException(400, "Description is required")
    if not phone.strip():
        raise HTTPException(400, "Phone is required")
    if not delivery_address.strip():
        raise HTTPException(400, "Delivery address is required")
    if consent.lower() != "true":
        raise HTTPException(400, "Consent is required")
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(400, f"Max {MAX_PHOTOS} photos")

    if idempotency_key:
        existing = await db.execute(select(Order).where(Order.idempotency_key == idempotency_key))
        ex = existing.scalar_one_or_none()
        if ex:
            return {"order_id": ex.id, "status": "duplicate"}

    result = await db.execute(select(User).where(User.telegram_id == user_data["id"]))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=user_data["id"],
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
        )
        db.add(user)
        await db.flush()

    stages = await get_all_stages(db)
    first_stage_id = stages[0].id if stages else None

    order = Order(
        user_id=user.id,
        description=html.escape(description.strip()),
        additional_comment=html.escape(additional_comment.strip()) if additional_comment else None,
        phone=html.escape(phone.strip()),
        email=html.escape(email.strip()) if email else None,
        delivery_address=html.escape(delivery_address.strip()),
        promo_code=html.escape(promo_code.strip()) if promo_code else None,
        consent_at=datetime.now(timezone.utc),
        current_stage_id=first_stage_id,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    await db.flush()

    order_dir = os.path.join(UPLOAD_DIR, str(user.telegram_id), str(order.id))
    os.makedirs(order_dir, exist_ok=True)
    saved_photos = []
    for photo in photos:
        content = await photo.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, "File too large")
        ext = os.path.splitext(photo.filename or "")[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(400, "Invalid file type")
        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(order_dir, filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        op = OrderPhoto(order_id=order.id, file_path=file_path)
        db.add(op)
        saved_photos.append(op)

    await db.commit()
    await db.refresh(order)
    await db.refresh(order, ["current_stage"])
    await notify_admin_new_order(order, user, saved_photos)
    return {"order_id": order.id, "status": "created"}

@router.get("/my", response_model=list[OrderListOut])
async def my_orders(user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Order).join(User).where(User.telegram_id == user_data["id"]).order_by(Order.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.photos), selectinload(Order.messages), selectinload(Order.user))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if user_data["id"] not in ADMIN_IDS and order.user.telegram_id != user_data["id"]:
        raise HTTPException(403, "Forbidden")
    return order

@router.get("/{order_id}/messages", response_model=list[MessageOut])
async def get_messages(order_id: int, user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    if user_data["id"] not in ADMIN_IDS:
        user = await db.get(User, order.user_id)
        if user.telegram_id != user_data["id"]:
            raise HTTPException(403)
    msgs = await db.execute(select(Message).where(Message.order_id == order_id).order_by(Message.created_at))
    return msgs.scalars().all()

@router.post("/{order_id}/messages")
async def send_message(
    order_id: int,
    data: dict,
    request: Request,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    rate_limit(client_key(request, user_data["id"]), limit=20, window=60)
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    is_admin = user_data["id"] in ADMIN_IDS
    user = await db.get(User, order.user_id)
    if not is_admin and user.telegram_id != user_data["id"]:
        raise HTTPException(403)
    text = html.escape((data.get("text") or "").strip())
    if not text:
        raise HTTPException(400, "Empty message")
    msg = Message(order_id=order_id, sender_id=user_data["id"], message_text=text, message_type="text")
    db.add(msg)
    await db.commit()
    if is_admin:
        await notify_client_message(order, user, text, prefix="💬 Ответ по заказу")
    else:
        from services.telegram_service import bot
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"💬 Клиент (заказ #{order.id}):\n{text}")
            except Exception:
                pass
    return {"ok": True}

@router.get("/{order_id}/photos/{photo_id}")
async def get_photo(order_id: int, photo_id: int, user_data: dict = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    photo = await db.get(OrderPhoto, photo_id)
    if not photo or photo.order_id != order_id:
        raise HTTPException(404)
    order = await db.get(Order, order_id)
    if user_data["id"] not in ADMIN_IDS:
        user = await db.get(User, order.user_id)
        if user.telegram_id != user_data["id"]:
            raise HTTPException(403)
    return FileResponse(photo.file_path)

@router.post("/{order_id}/review", response_model=ReviewOut)
async def leave_review(
    order_id: int,
    data: ReviewCreate,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    user = await db.get(User, order.user_id)
    if user.telegram_id != user_data["id"]:
        raise HTTPException(403)
    if order.status != "completed":
        raise HTTPException(400, "Review available only for completed orders")
    existing = await db.execute(select(Review).where(Review.order_id == order_id))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Review already exists")
    review = Review(
        order_id=order_id,
        author_name=html.escape(data.author_name) if data.author_name else None,
        text=html.escape(data.text),
        rating=data.rating,
        status="pending",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    await notify_admin_new_review(review, order)
    return review