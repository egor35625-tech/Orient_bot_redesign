from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from schemas import StageOut
from services.stage_service import get_all_stages

router = APIRouter(prefix="/api/stages", tags=["stages"])

@router.get("", response_model=list[StageOut])
async def list_stages(db: AsyncSession = Depends(get_session)):
    return await get_all_stages(db)