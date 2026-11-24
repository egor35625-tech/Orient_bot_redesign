import html
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_session
from models import Review
from schemas import ReviewCreate, ReviewOut
from api.deps import get_current_user
from services.notification_service import notify_admin_new_review
from services.rate_limit import rate_limit, client_key

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

@router.get("", response_model=list[ReviewOut])
async def list_published(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Review).where(Review.status == "published").order_by(Review.created_at.desc()).limit(50)
    )
    return result.scalars().all()

@router.post("", response_model=ReviewOut)
async def create_review(
    data: ReviewCreate,
    request: Request,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    rate_limit(client_key(request, user_data["id"]), limit=3, window=300)
    review = Review(
        order_id=None,
        author_name=html.escape(data.author_name) if data.author_name else user_data.get("first_name"),
        text=html.escape(data.text),
        rating=data.rating,
        status="pending",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    await notify_admin_new_review(review, None)
    return review