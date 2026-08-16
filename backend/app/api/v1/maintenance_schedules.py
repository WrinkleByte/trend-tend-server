import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    Principal,
    get_current_principal,
    household_scoped_query,
    verify_owned_reference,
)
from app.core.recurrence import ScheduleState, compute_due_status
from app.db.session import get_db
from app.models.asset import Asset, VehicleDetails
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.mixins import utcnow
from app.schemas.maintenance_schedule import (
    MaintenanceScheduleCreate,
    MaintenanceScheduleResponse,
    MaintenanceScheduleUpdate,
)

router = APIRouter(prefix="/maintenance-schedules", tags=["maintenance-schedules"])


async def _current_usage(db: AsyncSession, schedule: MaintenanceSchedule) -> int | None:
    if schedule.usage_field != "current_mileage":
        return None
    result = await db.execute(
        VehicleDetails.__table__.select().where(
            VehicleDetails.asset_id == schedule.asset_id
        )
    )
    row = result.first()
    return row.current_mileage if row else None


async def _to_response(
    db: AsyncSession, schedule: MaintenanceSchedule
) -> MaintenanceScheduleResponse:
    state = ScheduleState(
        interval_type=schedule.interval_type,
        interval_days=schedule.interval_days,
        interval_usage_amount=schedule.interval_usage_amount,
        anchor_date=schedule.anchor_date,
        anchor_usage_value=schedule.anchor_usage_value,
    )
    current_usage = await _current_usage(db, schedule)
    due = compute_due_status(
        state, today=datetime.now(UTC).date(), current_usage=current_usage
    )
    return MaintenanceScheduleResponse.model_validate(
        {
            **schedule.__dict__,
            "next_due_date": due.next_due_date,
            "next_due_usage": due.next_due_usage,
            "is_overdue": due.is_overdue,
        }
    )


@router.get("", response_model=list[MaintenanceScheduleResponse])
async def list_schedules(
    asset_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[MaintenanceScheduleResponse]:
    query = household_scoped_query(MaintenanceSchedule, principal)
    if asset_id is not None:
        query = query.where(MaintenanceSchedule.asset_id == asset_id)
    result = await db.execute(query.order_by(MaintenanceSchedule.name))
    return [await _to_response(db, s) for s in result.scalars().all()]


@router.post(
    "", response_model=MaintenanceScheduleResponse, status_code=status.HTTP_201_CREATED
)
async def create_schedule(
    payload: MaintenanceScheduleCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceScheduleResponse:
    await verify_owned_reference(db, principal, Asset, payload.asset_id, "Asset")
    schedule = MaintenanceSchedule(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        **payload.model_dump(),
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _to_response(db, schedule)


async def _get_owned_schedule(
    db: AsyncSession, principal: Principal, schedule_id: uuid.UUID
) -> MaintenanceSchedule:
    query = household_scoped_query(MaintenanceSchedule, principal).where(
        MaintenanceSchedule.id == schedule_id
    )
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance schedule not found")
    return schedule


@router.get("/{schedule_id}", response_model=MaintenanceScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceScheduleResponse:
    schedule = await _get_owned_schedule(db, principal, schedule_id)
    return await _to_response(db, schedule)


@router.patch("/{schedule_id}", response_model=MaintenanceScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    payload: MaintenanceScheduleUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceScheduleResponse:
    schedule = await _get_owned_schedule(db, principal, schedule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    schedule.updated_by_device_id = principal.device_id
    schedule.version += 1
    schedule.updated_at = utcnow()
    await db.commit()
    await db.refresh(schedule)
    return await _to_response(db, schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    schedule = await _get_owned_schedule(db, principal, schedule_id)
    schedule.deleted_at = utcnow()
    schedule.updated_by_device_id = principal.device_id
    schedule.version += 1
    await db.commit()
