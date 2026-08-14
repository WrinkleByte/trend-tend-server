import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_instance_admin
from app.db.session import get_db
from app.models.asset import Asset
from app.models.fuel_log import FuelLog
from app.models.household import Household, HouseholdMembership
from app.models.maintenance_record import MaintenanceRecord
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.trip_log import TripLog
from app.models.user import User
from app.schemas.admin import (
    AdminHouseholdMember,
    AdminHouseholdRecordCounts,
    AdminHouseholdSummary,
    PromoteUserResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _count_active(db: AsyncSession, model, household_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(model)
        .where(model.household_id == household_id, model.deleted_at.is_(None))
    )
    return result.scalar_one()


@router.get("/households", response_model=list[AdminHouseholdSummary])
async def list_all_households(
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminHouseholdSummary]:
    """Cross-household by design — the one place in the app that
    deliberately doesn't go through household_scoped_query, gated on
    instance-admin instead of household membership. Runs a handful of
    queries per household rather than one large aggregate join; fine at
    the household counts a self-hosted instance actually has."""
    households = (await db.execute(select(Household).order_by(Household.created_at))).scalars().all()

    summaries = []
    for household in households:
        members_result = await db.execute(
            select(HouseholdMembership, User)
            .join(User, User.id == HouseholdMembership.user_id)
            .where(HouseholdMembership.household_id == household.id)
            .order_by(HouseholdMembership.joined_at)
        )
        members = [
            AdminHouseholdMember(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=membership.role,
                is_instance_admin=user.is_instance_admin,
                joined_at=membership.joined_at,
            )
            for membership, user in members_result.all()
        ]

        record_counts = AdminHouseholdRecordCounts(
            assets=await _count_active(db, Asset, household.id),
            fuel_logs=await _count_active(db, FuelLog, household.id),
            trip_logs=await _count_active(db, TripLog, household.id),
            maintenance_records=await _count_active(db, MaintenanceRecord, household.id),
            maintenance_schedules=await _count_active(db, MaintenanceSchedule, household.id),
        )

        summaries.append(
            AdminHouseholdSummary(
                id=household.id,
                name=household.name,
                created_at=household.created_at,
                members=members,
                record_counts=record_counts,
            )
        )

    return summaries


@router.post("/users/{user_id}/promote", response_model=PromoteUserResponse)
async def promote_user_to_instance_admin(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> PromoteUserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.is_instance_admin = True
    await db.commit()
    await db.refresh(user)
    return PromoteUserResponse(id=user.id, email=user.email, is_instance_admin=user.is_instance_admin)


@router.post("/users/{user_id}/demote", response_model=PromoteUserResponse)
async def demote_user_from_instance_admin(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> PromoteUserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.is_instance_admin:
        admin_count = (
            await db.execute(select(func.count()).select_from(User).where(User.is_instance_admin.is_(True)))
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot demote the last remaining instance admin")

    user.is_instance_admin = False
    await db.commit()
    await db.refresh(user)
    return PromoteUserResponse(id=user.id, email=user.email, is_instance_admin=user.is_instance_admin)
