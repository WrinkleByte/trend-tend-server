# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken
from app.models.asset import Asset, EquipmentDetails, PropertyDetails, VehicleDetails
from app.models.attachment import Attachment
from app.models.fuel_log import FuelLog, FuelLogAttachment
from app.models.household import Household, HouseholdInvite, HouseholdMembership
from app.models.maintenance_record import MaintenanceRecord, RecordAttachment
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.mixins import utcnow
from app.models.sync_device import SyncDevice
from app.models.trip_log import TripLog, TripLogAttachment

# Every SyncedEntityMixin table a household can hold. Adding a new entity
# type (mirroring fuel_log, per the root CLAUDE.md invariant) means adding
# it here too, or both wipe and delete silently stop covering it.
_SYNCED_ENTITY_MODELS = (MaintenanceRecord, MaintenanceSchedule, FuelLog, TripLog, Asset, Attachment)


async def _delete_non_synced_children(db: AsyncSession, household_id: uuid.UUID) -> None:
    """Hard-deletes join/detail rows that aren't independently synced —
    RecordAttachment/FuelLogAttachment/TripLogAttachment and the per-asset-
    type detail tables are always read/written alongside their parent row,
    never synced on their own, so it's safe to remove them immediately
    regardless of whether the parent ends up soft-deleted (wipe) or hard-
    deleted (full household delete). Without this, deleting/wiping a
    household with any fuel/trip log that has a photo attachment hit a real
    FK violation (Vikunja #89) — FuelLogAttachment/TripLogAttachment were
    missing here even though RecordAttachment was already handled."""
    record_ids = select(MaintenanceRecord.id).where(MaintenanceRecord.household_id == household_id)
    fuel_log_ids = select(FuelLog.id).where(FuelLog.household_id == household_id)
    trip_log_ids = select(TripLog.id).where(TripLog.household_id == household_id)
    asset_ids = select(Asset.id).where(Asset.household_id == household_id)

    await db.execute(delete(RecordAttachment).where(RecordAttachment.record_id.in_(record_ids)))
    await db.execute(delete(FuelLogAttachment).where(FuelLogAttachment.fuel_log_id.in_(fuel_log_ids)))
    await db.execute(delete(TripLogAttachment).where(TripLogAttachment.trip_log_id.in_(trip_log_ids)))
    await db.execute(delete(VehicleDetails).where(VehicleDetails.asset_id.in_(asset_ids)))
    await db.execute(delete(EquipmentDetails).where(EquipmentDetails.asset_id.in_(asset_ids)))
    await db.execute(delete(PropertyDetails).where(PropertyDetails.asset_id.in_(asset_ids)))


async def wipe_household_data(db: AsyncSession, household_id: uuid.UUID, device_id: uuid.UUID | None = None) -> None:
    """Clears every *data* row in a household — assets and their
    type-specific detail rows, fuel/trip logs, maintenance records and
    schedules, attachment metadata — but leaves the household itself, its
    memberships/invites, API tokens, and sync devices untouched: this is
    the "start over with a clean slate" reset (Vikunja #27), not household
    deletion. See delete_household_data below for that.

    Unlike delete_household_data, this soft-deletes the synced-entity rows
    (sets deleted_at, bumps version) instead of hard-deleting them. The
    household keeps existing and mobile devices stay paired to it, so a
    hard delete here would be invisible to them — sync only ever tells a
    client about a deletion via the deleted_at tombstone on a row it can
    still see; a row that's just gone from the table teaches it nothing,
    and a paired phone would keep showing the wiped data indefinitely. See
    tendfida-mobile's TASKS.md Design Notes for the full tombstone
    propagation walkthrough this depends on.

    Attachment blob files are left in place — same accepted storage-leak
    tradeoff as a normal single attachment delete (see attachments.py's
    delete_attachment) — only metadata rows go here.

    device_id is optional (None for a request with no device context, e.g.
    an API-key-authenticated call) and is stamped onto updated_by_device_id
    the same way a normal single-row edit would. Doesn't commit — that's
    left to the caller.
    """
    await _delete_non_synced_children(db, household_id)

    now = utcnow()
    for model in _SYNCED_ENTITY_MODELS:
        await db.execute(
            update(model)
            .where(model.household_id == household_id, model.deleted_at.is_(None))
            .values(deleted_at=now, updated_by_device_id=device_id, version=model.version + 1)
        )


async def delete_household_data(db: AsyncSession, household_id: uuid.UUID) -> None:
    """Hard-deletes an entire household: every row wipe_household_data
    would soft-delete, plus the household's own membership/invite/token/
    device rows and the household row itself. The one place in the app
    that does real deletion rather than the deleted_at soft-delete every
    synced entity normally uses elsewhere — appropriate here specifically
    because the household ceases to exist, so no device will ever sync
    against this household_id again to see a tombstone; leaving soft-
    deleted rows behind forever would just be dead weight.

    Shared by two callers with different authorization: an owner deleting
    their own household (households.py) and an instance admin deleting any
    household (admin.py) — both just need this same cleanup, gated
    differently. Neither commits here; that's left to the caller so it
    stays part of whatever transaction the caller is already managing.
    """
    await _delete_non_synced_children(db, household_id)

    for model in _SYNCED_ENTITY_MODELS:
        await db.execute(delete(model).where(model.household_id == household_id))

    await db.execute(delete(ApiToken).where(ApiToken.household_id == household_id))
    await db.execute(delete(SyncDevice).where(SyncDevice.household_id == household_id))
    await db.execute(delete(HouseholdInvite).where(HouseholdInvite.household_id == household_id))
    await db.execute(delete(HouseholdMembership).where(HouseholdMembership.household_id == household_id))
    await db.execute(delete(Household).where(Household.id == household_id))
