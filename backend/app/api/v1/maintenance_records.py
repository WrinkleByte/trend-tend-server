import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    Principal,
    get_current_principal,
    household_scoped_query,
    verify_owned_reference,
)
from app.db.session import get_db
from app.models.asset import Asset
from app.models.maintenance_record import MaintenanceRecord
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.mixins import utcnow
from app.schemas.maintenance_record import (
    MaintenanceRecordBulkCreate,
    MaintenanceRecordBulkResult,
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    MaintenanceRecordUpdate,
)

router = APIRouter(prefix="/maintenance-records", tags=["maintenance-records"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[MaintenanceRecordResponse])
async def list_records(
    asset_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[MaintenanceRecord]:
    query = household_scoped_query(MaintenanceRecord, principal)
    if asset_id is not None:
        query = query.where(MaintenanceRecord.asset_id == asset_id)
    result = await db.execute(query.order_by(MaintenanceRecord.performed_at.desc()))
    return list(result.scalars().all())


@router.post(
    "", response_model=MaintenanceRecordResponse, status_code=status.HTTP_201_CREATED
)
async def create_record(
    payload: MaintenanceRecordCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecord:
    await verify_owned_reference(db, principal, Asset, payload.asset_id, "Asset")
    if payload.schedule_id is not None:
        await verify_owned_reference(
            db,
            principal,
            MaintenanceSchedule,
            payload.schedule_id,
            "Maintenance schedule",
        )
    record = MaintenanceRecord(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        **payload.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.post(
    "/bulk", response_model=list[MaintenanceRecordBulkResult], status_code=status.HTTP_207_MULTI_STATUS
)
async def create_records_bulk(
    payload: MaintenanceRecordBulkCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[MaintenanceRecordBulkResult]:
    """One round trip for an entire CSV/Fuelly import instead of N sequential
    POSTs (Vikunja #39). Each row gets its own SAVEPOINT, same pattern as
    sync.py's push handler and fuel_logs.py's bulk endpoint -- a bad row
    rolls back only its own work and is reported individually, the rest of
    the batch still commits."""
    results: list[MaintenanceRecordBulkResult] = []
    for index, raw_item in enumerate(payload.items):
        try:
            item = MaintenanceRecordCreate.model_validate(raw_item)
        except ValidationError as e:
            results.append(MaintenanceRecordBulkResult(index=index, status="error", error=e.errors()[0]["msg"]))
            continue

        try:
            await verify_owned_reference(db, principal, Asset, item.asset_id, "Asset")
            if item.schedule_id is not None:
                await verify_owned_reference(
                    db, principal, MaintenanceSchedule, item.schedule_id, "Maintenance schedule"
                )
        except HTTPException as e:
            results.append(MaintenanceRecordBulkResult(index=index, status="error", error=str(e.detail)))
            continue

        try:
            async with db.begin_nested():
                record = MaintenanceRecord(
                    id=uuid.uuid4(),
                    household_id=principal.household_id,
                    updated_by_device_id=principal.device_id,
                    **item.model_dump(),
                )
                db.add(record)
                await db.flush()
            results.append(MaintenanceRecordBulkResult(index=index, status="created", id=record.id))
        except SQLAlchemyError:
            logger.exception("bulk maintenance record create failed at index %d", index)
            results.append(
                MaintenanceRecordBulkResult(index=index, status="error", error="Could not create this record.")
            )

    await db.commit()
    return results


async def _get_owned_record(
    db: AsyncSession, principal: Principal, record_id: uuid.UUID
) -> MaintenanceRecord:
    query = household_scoped_query(MaintenanceRecord, principal).where(
        MaintenanceRecord.id == record_id
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance record not found")
    return record


@router.get("/{record_id}", response_model=MaintenanceRecordResponse)
async def get_record(
    record_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecord:
    return await _get_owned_record(db, principal, record_id)


@router.patch("/{record_id}", response_model=MaintenanceRecordResponse)
async def update_record(
    record_id: uuid.UUID,
    payload: MaintenanceRecordUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceRecord:
    record = await _get_owned_record(db, principal, record_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    record.updated_by_device_id = principal.device_id
    record.version += 1
    record.updated_at = utcnow()
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    record_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    record = await _get_owned_record(db, principal, record_id)
    record.deleted_at = utcnow()
    record.updated_by_device_id = principal.device_id
    record.version += 1
    await db.commit()
