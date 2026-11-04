# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

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
from app.models.fuel_log import FuelLog
from app.models.mixins import utcnow
from app.schemas.fuel_log import (
    FuelLogBulkCreate,
    FuelLogBulkResult,
    FuelLogCreate,
    FuelLogResponse,
    FuelLogUpdate,
)

router = APIRouter(prefix="/fuel-logs", tags=["fuel-logs"])
logger = logging.getLogger(__name__)


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
    await verify_owned_reference(db, principal, Asset, payload.asset_id, "Asset")
    fuel_log = FuelLog(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        updated_by_user_id=principal.user_id,
        **payload.model_dump(),
    )
    db.add(fuel_log)
    await db.commit()
    await db.refresh(fuel_log)
    return fuel_log


@router.post("/bulk", response_model=list[FuelLogBulkResult], status_code=status.HTTP_207_MULTI_STATUS)
async def create_fuel_logs_bulk(
    payload: FuelLogBulkCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[FuelLogBulkResult]:
    """One round trip for an entire CSV/Fuelly import instead of N sequential
    POSTs (Vikunja #39). Each row gets its own SAVEPOINT, same pattern as
    sync.py's push handler -- a bad row rolls back only its own work and is
    reported individually, the rest of the batch still commits."""
    results: list[FuelLogBulkResult] = []
    for index, raw_item in enumerate(payload.items):
        try:
            item = FuelLogCreate.model_validate(raw_item)
        except ValidationError as e:
            results.append(FuelLogBulkResult(index=index, status="error", error=e.errors()[0]["msg"]))
            continue

        try:
            await verify_owned_reference(db, principal, Asset, item.asset_id, "Asset")
        except HTTPException as e:
            results.append(FuelLogBulkResult(index=index, status="error", error=str(e.detail)))
            continue

        try:
            async with db.begin_nested():
                fuel_log = FuelLog(
                    id=uuid.uuid4(),
                    household_id=principal.household_id,
                    updated_by_device_id=principal.device_id,
                    updated_by_user_id=principal.user_id,
                    **item.model_dump(),
                )
                db.add(fuel_log)
                await db.flush()
            results.append(FuelLogBulkResult(index=index, status="created", id=fuel_log.id))
        except SQLAlchemyError:
            logger.exception("bulk fuel log create failed at index %d", index)
            results.append(FuelLogBulkResult(index=index, status="error", error="Could not create this fuel log."))

    await db.commit()
    return results


async def _get_owned_fuel_log(
    db: AsyncSession, principal: Principal, fuel_log_id: uuid.UUID
) -> FuelLog:
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
    fuel_log.updated_by_user_id = principal.user_id
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
    fuel_log.updated_by_user_id = principal.user_id
    fuel_log.version += 1
    await db.commit()
