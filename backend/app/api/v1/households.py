from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal
from app.db.session import get_db
from app.models.household import Household
from app.schemas.household import HouseholdResponse

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdResponse)
async def get_current_household(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> Household:
    result = await db.execute(select(Household).where(Household.id == principal.household_id))
    return result.scalar_one()
