from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import OrderStage

async def get_all_stages(db: AsyncSession) -> list[OrderStage]:
    result = await db.execute(select(OrderStage).order_by(OrderStage.position))
    return result.scalars().all()

async def get_stage(db: AsyncSession, stage_id: int) -> OrderStage | None:
    return await db.get(OrderStage, stage_id)

async def get_next_stage(db: AsyncSession, current_id: int | None) -> OrderStage | None:
    stages = await get_all_stages(db)
    if not stages:
        return None
    if current_id is None:
        return stages[0]
    for i, s in enumerate(stages):
        if s.id == current_id and i + 1 < len(stages):
            return stages[i + 1]
    return None

async def get_prev_stage(db: AsyncSession, current_id: int | None) -> OrderStage | None:
    stages = await get_all_stages(db)
    if not stages or current_id is None:
        return None
    for i, s in enumerate(stages):
        if s.id == current_id and i > 0:
            return stages[i - 1]
    return None

async def get_rejected_stage(db: AsyncSession) -> OrderStage | None:
    result = await db.execute(select(OrderStage).where(OrderStage.is_rejected == True))
    return result.scalar_one_or_none()