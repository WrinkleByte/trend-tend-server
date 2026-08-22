import base64
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, literal, or_, select, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, verify_owned_reference
from app.db.session import get_db
from app.models.asset import Asset
from app.models.attachment import Attachment
from app.models.fuel_log import FuelLog
from app.models.maintenance_record import MaintenanceRecord
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.mixins import utcnow
from app.models.sync_device import SyncDevice
from app.models.trip_log import TripLog
from app.schemas.sync import (
    AssetSyncData,
    AttachmentSyncData,
    FuelLogSyncData,
    MaintenanceRecordSyncData,
    MaintenanceScheduleSyncData,
    SyncChangeIn,
    SyncChangeOut,
    SyncDeviceRegister,
    SyncDeviceResponse,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncPushResult,
    TripLogSyncData,
)

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger("app.sync")

# Raw SQLAlchemy error text names tables, columns and constraints. That is
# useful in a server log and nobody else's business over the wire, so the
# client gets a fixed string and the detail goes to the log (review S9).
_GENERIC_DB_ERROR_DETAIL = "Could not apply this change."

PAGE_SIZE = 200


@dataclass(frozen=True)
class EntitySyncConfig:
    model: type
    data_model: type[BaseModel]


# The generic sync protocol (docs/architecture.md Section 3) walks this
# registry rather than having bespoke pull/push logic per entity — adding a
# new syncable entity is one line here plus its *SyncData schema, not a new
# endpoint.
SYNC_REGISTRY: dict[str, EntitySyncConfig] = {
    "asset": EntitySyncConfig(Asset, AssetSyncData),
    "maintenance_record": EntitySyncConfig(
        MaintenanceRecord, MaintenanceRecordSyncData
    ),
    "maintenance_schedule": EntitySyncConfig(
        MaintenanceSchedule, MaintenanceScheduleSyncData
    ),
    "fuel_log": EntitySyncConfig(FuelLog, FuelLogSyncData),
    "trip_log": EntitySyncConfig(TripLog, TripLogSyncData),
    "attachment": EntitySyncConfig(Attachment, AttachmentSyncData),
}

# Every *SyncData schema above is a "full row replace" (see their shared doc
# comment) -- any of these fields present on an incoming change is a client-
# supplied foreign key that needs the same cross-tenant check
# verify_owned_reference gives the REST create endpoints, for both the
# create-new-row and update-existing-row paths in _apply_change below.
# Without this, a client could push a fuel_log/trip_log/maintenance_record/
# maintenance_schedule whose asset_id (or a maintenance_record's
# schedule_id) points at another household's row entirely.
_REFERENCE_FIELDS: dict[str, tuple[type, str]] = {
    "asset_id": (Asset, "Asset"),
    "schedule_id": (MaintenanceSchedule, "Maintenance schedule"),
}


def _serialize_row(entity_type: str, obj) -> dict:
    """Explicit field allowlist, not a dynamic walk of every ORM column
    (Vikunja #44's design review) -- reuses each entity's own *SyncData
    schema (the same one push validates incoming changes against) as the
    single source of truth for what this entity's wire shape is, in both
    directions. A column added to a model for some unrelated, internal
    reason no longer automatically becomes visible to every client the
    moment a migration lands; it has to be deliberately added to that
    entity's *SyncData schema first, same as it already does for push."""
    data_model = SYNC_REGISTRY[entity_type].data_model
    return data_model.model_validate(obj, from_attributes=True).model_dump(mode="json")


def _encode_cursor(updated_at: datetime, entity_id: uuid.UUID) -> str:
    raw = f"{updated_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        updated_at_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(updated_at_str), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid cursor") from exc


async def _get_active_device(
    db: AsyncSession, principal: Principal, device_id: uuid.UUID
) -> SyncDevice:
    result = await db.execute(
        select(SyncDevice).where(
            SyncDevice.id == device_id,
            SyncDevice.household_id == principal.household_id,
        )
    )
    device = result.scalar_one_or_none()
    if device is None or device.revoked_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown or revoked sync device")
    return device


@router.post(
    "/devices", response_model=SyncDeviceResponse, status_code=status.HTTP_201_CREATED
)
async def register_device(
    payload: SyncDeviceRegister,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SyncDevice:
    device = SyncDevice(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        user_id=principal.user_id,
        platform=payload.platform,
        device_name=payload.device_name,
        conflict_resolution_mode=payload.conflict_resolution_mode,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/devices", response_model=list[SyncDeviceResponse])
async def list_devices(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[SyncDevice]:
    """Every device paired to this household, revoked ones included.

    Revoked devices are deliberately still listed rather than hidden: "this
    phone was revoked on the 3rd" is the useful answer after losing one, and
    hiding it just makes a user wonder whether the revoke worked.
    """
    result = await db.execute(
        select(SyncDevice)
        .where(SyncDevice.household_id == principal.household_id)
        .order_by(SyncDevice.created_at)
    )
    return list(result.scalars().all())


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a lost or stolen paired device (Vikunja #36).

    SyncDevice.revoked_at and its enforcement in _get_active_device already
    existed -- what was missing was any way to *set* it, so the check could
    never actually fire. A device is revoked, never deleted: every synced row
    carries updated_by_device_id referencing it, so removing the row would
    orphan that history (and sync pull's own "not my writes" filter depends
    on those ids remaining resolvable).

    Idempotent: revoking an already-revoked device is a no-op rather than an
    error, since the caller's intent is already satisfied.
    """
    result = await db.execute(
        select(SyncDevice).where(
            SyncDevice.id == device_id,
            SyncDevice.household_id == principal.household_id,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sync device not found")

    if device.revoked_at is None:
        device.revoked_at = utcnow()
        await db.commit()


@router.post("/pull", response_model=SyncPullResponse)
async def pull(
    payload: SyncPullRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SyncPullResponse:
    device = await _get_active_device(db, principal, payload.device_id)
    cursor = _decode_cursor(payload.cursor) if payload.cursor else None

    selects = []
    for entity_type, config in SYNC_REGISTRY.items():
        model = config.model
        # updated_by_device_id IS DISTINCT FROM excludes this device's own
        # writes (including NULL, i.e. server-originated rows with no
        # device) without the NULL-comparison pitfall of a plain `!=`.
        conditions = [
            model.household_id == principal.household_id,
            model.updated_by_device_id.is_distinct_from(payload.device_id),
        ]
        if cursor is not None:
            cursor_updated_at, cursor_id = cursor
            conditions.append(
                or_(
                    model.updated_at > cursor_updated_at,
                    and_(model.updated_at == cursor_updated_at, model.id > cursor_id),
                )
            )
        selects.append(
            select(
                literal(entity_type).label("entity_type"),
                model.id.label("id"),
                model.version.label("version"),
                model.updated_at.label("updated_at"),
                model.deleted_at.label("deleted_at"),
            ).where(*conditions)
        )

    index_subquery = union_all(*selects).subquery()
    index_stmt = (
        select(index_subquery)
        .order_by(index_subquery.c.updated_at, index_subquery.c.id)
        .limit(PAGE_SIZE + 1)
    )
    index_rows = (await db.execute(index_stmt)).all()

    has_more = len(index_rows) > PAGE_SIZE
    page = index_rows[:PAGE_SIZE]

    ids_by_type: dict[str, list[uuid.UUID]] = {}
    for row in page:
        ids_by_type.setdefault(row.entity_type, []).append(row.id)

    full_rows: dict[tuple[str, uuid.UUID], object] = {}
    for entity_type, ids in ids_by_type.items():
        model = SYNC_REGISTRY[entity_type].model
        result = await db.execute(select(model).where(model.id.in_(ids)))
        for obj in result.scalars().all():
            full_rows[(entity_type, obj.id)] = obj

    changes = [
        SyncChangeOut(
            entity_type=row.entity_type,
            id=row.id,
            version=row.version,
            updated_at=row.updated_at,
            deleted=row.deleted_at is not None,
            data=_serialize_row(row.entity_type, full_rows[(row.entity_type, row.id)]),
        )
        for row in page
    ]

    if page:
        next_cursor = _encode_cursor(page[-1].updated_at, page[-1].id)
    else:
        next_cursor = payload.cursor

    device.last_sync_cursor = next_cursor
    device.last_sync_at = utcnow()
    await db.commit()

    return SyncPullResponse(changes=changes, next_cursor=next_cursor, has_more=has_more)


async def _apply_change(
    db: AsyncSession, principal: Principal, device_id: uuid.UUID, change: SyncChangeIn
) -> SyncPushResult:
    config = SYNC_REGISTRY.get(change.entity_type)
    if config is None:
        return SyncPushResult(
            id=change.id,
            status="rejected",
            reason="unknown_entity_type",
            detail=change.entity_type,
        )

    result = await db.execute(
        select(config.model).where(
            config.model.id == change.id,
            config.model.household_id == principal.household_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        # The lookup above is household-scoped, so an id belonging to ANOTHER
        # household also lands here as "not found" -- and the create path
        # below would then attempt an insert on an id that already exists,
        # producing a primary-key violation whose response differs from a
        # clean accept. That difference is a working oracle for "does this
        # UUID exist on this instance", and it used to leak the constraint
        # name along with the answer (review S9).
        #
        # Check globally and reject identically to any other rejected change.
        # attachments.py's upload handler already does exactly this for the
        # same reason; this mirrors it.
        collision = await db.execute(select(config.model.id).where(config.model.id == change.id))
        if collision.scalar_one_or_none() is not None:
            return SyncPushResult(
                id=change.id,
                status="rejected",
                reason="id_conflict",
                detail="This id is already in use.",
            )

    if existing is not None and existing.version != change.base_version:
        return SyncPushResult(
            id=change.id,
            status="conflict",
            server_version=existing.version,
            server_data=_serialize_row(change.entity_type, existing),
            client_data=change.data,
        )

    if change.deleted:
        if existing is None:
            # Created and deleted locally before ever reaching the server —
            # nothing to tombstone, and no other device could have seen it
            # exist in the first place.
            return SyncPushResult(
                id=change.id,
                status="accepted",
                new_version=1,
                server_updated_at=utcnow(),
            )
        try:
            async with db.begin_nested():
                existing.deleted_at = utcnow()
                existing.updated_by_device_id = device_id
                existing.version += 1
                existing.updated_at = utcnow()
                await db.flush()
        except SQLAlchemyError:
            logger.exception("sync push failed for %s %s", change.entity_type, change.id)
            return SyncPushResult(
                id=change.id,
                status="rejected",
                reason="database_error",
                detail=_GENERIC_DB_ERROR_DETAIL,
            )
        return SyncPushResult(
            id=change.id,
            status="accepted",
            new_version=existing.version,
            server_updated_at=existing.updated_at,
        )

    try:
        parsed = config.data_model.model_validate(change.data)
    except ValidationError as exc:
        return SyncPushResult(
            id=change.id, status="rejected", reason="validation_error", detail=str(exc)
        )

    for field_name, (ref_model, label) in _REFERENCE_FIELDS.items():
        ref_id = getattr(parsed, field_name, None)
        if ref_id is None:
            continue
        try:
            await verify_owned_reference(db, principal, ref_model, ref_id, label)
        except HTTPException:
            return SyncPushResult(
                id=change.id,
                status="rejected",
                reason="invalid_reference",
                detail=f"{label} not found",
            )

    try:
        # A SAVEPOINT per row, not one giant transaction — an error on one
        # row (e.g. a bad foreign key in its data) rolls back only that
        # row's work, so the rest of the batch still gets processed and
        # committed. See docs/architecture.md Section 3. (Note: a foreign
        # key pointing at a REAL row in another household satisfies the
        # DB's own FK constraint fine — the check above is what actually
        # catches that case; a SQLAlchemyError here is a different kind of
        # bad reference, e.g. a genuinely nonexistent id.)
        async with db.begin_nested():
            if existing is None:
                row = config.model(
                    id=change.id,
                    household_id=principal.household_id,
                    updated_by_device_id=device_id,
                    version=1,
                    **parsed.model_dump(),
                )
                db.add(row)
                await db.flush()
                new_version, server_updated_at = 1, row.updated_at
            else:
                for field, value in parsed.model_dump().items():
                    setattr(existing, field, value)
                existing.updated_by_device_id = device_id
                existing.version += 1
                existing.updated_at = utcnow()
                await db.flush()
                new_version, server_updated_at = existing.version, existing.updated_at
    except SQLAlchemyError:
        logger.exception("sync push failed for %s %s", change.entity_type, change.id)
        return SyncPushResult(
            id=change.id, status="rejected", reason="database_error", detail=_GENERIC_DB_ERROR_DETAIL
        )

    return SyncPushResult(
        id=change.id,
        status="accepted",
        new_version=new_version,
        server_updated_at=server_updated_at,
    )


@router.post("/push", response_model=SyncPushResponse)
async def push(
    payload: SyncPushRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SyncPushResponse:
    device = await _get_active_device(db, principal, payload.device_id)

    results = [
        await _apply_change(db, principal, payload.device_id, change)
        for change in payload.changes
    ]

    device.last_sync_at = utcnow()
    await db.commit()

    return SyncPushResponse(results=results)
