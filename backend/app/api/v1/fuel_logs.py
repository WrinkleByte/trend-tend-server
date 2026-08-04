import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.fuel_log import FuelLog
from app.models.mixins import utcnow
from app.schemas.fuel_log import FuelLogCreate, FuelLogResponse, FuelLogUpdate

router = APIRouter(prefix="/fuel-logs", tags=["fuel-logs"])


@router.get("", response_model=list[FuelLogResponse])
async def list_fuel_logs(
    asset_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[FuelLog]:
    query = household_scoped_query(FuelLog, principal)
    if asset_id is not None:
        query = query.where(FuelLog.asset_id == asset_id)
    result = await db.execute(query.order_by(FuelLog.performed_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=FuelLogResponse, status_code=status.HTTP_201_CREATED)
async def create_fuel_log(
    payload: FuelLogCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FuelLog:
    fuel_log = FuelLog(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        **payload.model_dump(),
    )
    db.add(fuel_log)
    await db.commit()
    await db.refresh(fuel_log)
    return fuel_log


async def _get_owned_fuel_log(db: AsyncSession, principal: Principal, fuel_log_id: uuid.UUID) -> FuelLog:
    query = household_scoped_query(FuelLog, principal).where(FuelLog.id == fuel_log_id)
    result = await db.execute(query)
    fuel_log = result.scalar_one_or_none()
    if fuel_log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel log not found")
    return fuel_log


@router.get("/{fuel_log_id}", response_model=FuelLogResponse)
async def get_fuel_log(
    fuel_log_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FuelLog:
    return await _get_owned_fuel_log(db, principal, fuel_log_id)


@router.patch("/{fuel_log_id}", response_model=FuelLogResponse)
async def update_fuel_log(
    fuel_log_id: uuid.UUID,
    payload: FuelLogUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FuelLog:
    fuel_log = await _get_owned_fuel_log(db, principal, fuel_log_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fuel_log, field, value)
    fuel_log.updated_by_device_id = principal.device_id
    fuel_log.version += 1
    fuel_log.updated_at = utcnow()
    await db.commit()
    await db.refresh(fuel_log)
    return fuel_log


@router.delete("/{fuel_log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fuel_log(
    fuel_log_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    fuel_log = await _get_owned_fuel_log(db, principal, fuel_log_id)
    fuel_log.deleted_at = utcnow()
    fuel_log.updated_by_device_id = principal.device_id
    fuel_log.version += 1
    await db.commit()
