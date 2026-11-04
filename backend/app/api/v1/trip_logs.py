# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    Principal,
    get_current_principal,
    household_scoped_query,
    verify_owned_reference,
)
from app.db.session import get_db
from app.models.asset import Asset
from app.models.mixins import utcnow
from app.models.trip_log import TripLog
from app.schemas.trip_log import TripLogCreate, TripLogResponse, TripLogUpdate

router = APIRouter(prefix="/trip-logs", tags=["trip-logs"])


@router.get("", response_model=list[TripLogResponse])
async def list_trip_logs(
    asset_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[TripLog]:
    query = household_scoped_query(TripLog, principal)
    if asset_id is not None:
        query = query.where(TripLog.asset_id == asset_id)
    result = await db.execute(query.order_by(TripLog.performed_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=TripLogResponse, status_code=status.HTTP_201_CREATED)
async def create_trip_log(
    payload: TripLogCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TripLog:
    await verify_owned_reference(db, principal, Asset, payload.asset_id, "Asset")
    trip_log = TripLog(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        updated_by_user_id=principal.user_id,
        **payload.model_dump(),
    )
    db.add(trip_log)
    await db.commit()
    await db.refresh(trip_log)
    return trip_log


async def _get_owned_trip_log(
    db: AsyncSession, principal: Principal, trip_log_id: uuid.UUID
) -> TripLog:
    query = household_scoped_query(TripLog, principal).where(TripLog.id == trip_log_id)
    result = await db.execute(query)
    trip_log = result.scalar_one_or_none()
    if trip_log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip log not found")
    return trip_log


@router.get("/{trip_log_id}", response_model=TripLogResponse)
async def get_trip_log(
    trip_log_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TripLog:
    return await _get_owned_trip_log(db, principal, trip_log_id)


@router.patch("/{trip_log_id}", response_model=TripLogResponse)
async def update_trip_log(
    trip_log_id: uuid.UUID,
    payload: TripLogUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TripLog:
    trip_log = await _get_owned_trip_log(db, principal, trip_log_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trip_log, field, value)
    trip_log.updated_by_device_id = principal.device_id
    trip_log.updated_by_user_id = principal.user_id
    trip_log.version += 1
    trip_log.updated_at = utcnow()
    await db.commit()
    await db.refresh(trip_log)
    return trip_log


@router.delete("/{trip_log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip_log(
    trip_log_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    trip_log = await _get_owned_trip_log(db, principal, trip_log_id)
    trip_log.deleted_at = utcnow()
    trip_log.updated_by_device_id = principal.device_id
    trip_log.updated_by_user_id = principal.user_id
    trip_log.version += 1
    await db.commit()
