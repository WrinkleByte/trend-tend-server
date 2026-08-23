import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_instance_admin
from app.core.household_deletion import delete_household_data
from app.core.user_deletion import UserOwnsHouseholdsError, delete_user_data
from app.db.session import get_db
from app.models.asset import Asset
from app.models.fuel_log import FuelLog
from app.models.household import Household, HouseholdMembership, HouseholdRole
from app.models.maintenance_record import MaintenanceRecord
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.trip_log import TripLog
from app.models.user import User
from app.schemas.admin import (
    AdminAddMembershipRequest,
    AdminHouseholdMember,
    AdminHouseholdRecordCounts,
    AdminHouseholdSummary,
    AdminUserMembership,
    AdminUserSummary,
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


@router.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_household_as_admin(
    household_id: uuid.UUID,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Same hard delete as an owner deleting their own household
    (households.py's delete_household) — just reachable for any household
    on the instance, gated on instance-admin instead of ownership."""
    household = (await db.execute(select(Household).where(Household.id == household_id))).scalar_one_or_none()
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")

    await delete_household_data(db, household_id)
    await db.commit()


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


@router.get("/users", response_model=list[AdminUserSummary])
async def list_all_users(
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserSummary]:
    """Every user on the instance, cross-household, including anyone with
    zero memberships -- list_all_households above only ever shows users
    *through* a household, so an orphaned account (Vikunja #101) never
    appears there at all. This is the one place that surfaces them."""
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    memberships_result = await db.execute(
        select(HouseholdMembership, Household.name)
        .join(Household, Household.id == HouseholdMembership.household_id)
        .order_by(HouseholdMembership.joined_at)
    )
    memberships_by_user: dict[uuid.UUID, list[AdminUserMembership]] = {}
    for membership, household_name in memberships_result.all():
        memberships_by_user.setdefault(membership.user_id, []).append(
            AdminUserMembership(household_id=membership.household_id, household_name=household_name, role=membership.role)
        )

    return [
        AdminUserSummary(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_instance_admin=user.is_instance_admin,
            created_at=user.created_at,
            memberships=memberships_by_user.get(user.id, []),
        )
        for user in users
    ]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def purge_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently deletes a user and their auth/membership footprint (see
    delete_user_data's doc comment for exactly what) -- the "purge" tool
    Vikunja #101 asked for, for accounts (orphaned or otherwise) an admin
    decides shouldn't exist. Deliberately does not touch household *data*;
    delete a household separately (the endpoint above) if that's also
    wanted. An instance admin can't purge themselves -- self-service
    account deletion, if ever wanted, is a different, deliberate feature,
    not a side effect of this cross-household tool."""
    if user_id == principal.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot purge your own account")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    try:
        await delete_user_data(db, user_id)
    except UserOwnsHouseholdsError as exc:
        names = ", ".join(name for _, name in exc.households)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This user owns {len(exc.households)} household(s) ({names}) — delete or reassign those first.",
        ) from exc
    await db.commit()


@router.post("/users/{user_id}/memberships", response_model=AdminUserSummary)
async def add_user_membership(
    user_id: uuid.UUID,
    payload: AdminAddMembershipRequest,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserSummary:
    """Directly adds a user to a household, bypassing the invite/accept
    flow entirely -- the "reset an orphan" tool Vikunja #101 asked for.
    Intended for exactly the state that flow can get stuck in: a real
    account with zero memberships, which login() rejects outright and
    which register() can never re-create (the email is already taken) --
    see this endpoint's sibling delete above and the card for the full
    story. Just as usable for any other membership fix-up an admin needs,
    not gated to orphans specifically."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    household = (await db.execute(select(Household).where(Household.id == payload.household_id))).scalar_one_or_none()
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")

    existing = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == payload.household_id, HouseholdMembership.user_id == user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member of this household")

    db.add(
        HouseholdMembership(
            id=uuid.uuid4(),
            household_id=payload.household_id,
            user_id=user_id,
            role=payload.role,
            invited_by_user_id=principal.user_id,
        )
    )
    await db.commit()

    memberships_result = await db.execute(
        select(HouseholdMembership, Household.name)
        .join(Household, Household.id == HouseholdMembership.household_id)
        .where(HouseholdMembership.user_id == user_id)
        .order_by(HouseholdMembership.joined_at)
    )
    memberships = [
        AdminUserMembership(household_id=membership.household_id, household_name=name, role=membership.role)
        for membership, name in memberships_result.all()
    ]
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_instance_admin=user.is_instance_admin,
        created_at=user.created_at,
        memberships=memberships,
    )


@router.delete("/users/{user_id}/memberships/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_membership(
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    principal: Principal = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Removes one membership without touching the user account itself or
    any other household they belong to -- narrower than purge_user, for
    when the fix is "wrong household," not "delete this account." Refuses
    if it would strip a household's last owner (mirrors the same safety
    demote_user_from_instance_admin applies to the last instance admin)."""
    membership = (
        await db.execute(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id, HouseholdMembership.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    if membership.role == HouseholdRole.OWNER:
        other_owners = await db.execute(
            select(func.count())
            .select_from(HouseholdMembership)
            .where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == HouseholdRole.OWNER,
                HouseholdMembership.user_id != user_id,
            )
        )
        if other_owners.scalar_one() == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove a household's last owner")

    await db.delete(membership)
    await db.commit()
