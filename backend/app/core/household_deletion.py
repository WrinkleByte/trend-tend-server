import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken
from app.models.asset import Asset, EquipmentDetails, PropertyDetails, VehicleDetails
from app.models.attachment import Attachment
from app.models.fuel_log import FuelLog
from app.models.household import Household, HouseholdInvite, HouseholdMembership
from app.models.maintenance_record import MaintenanceRecord, RecordAttachment
from app.models.maintenance_schedule import MaintenanceSchedule
from app.models.sync_device import SyncDevice
from app.models.trip_log import TripLog


async def wipe_household_data(db: AsyncSession, household_id: uuid.UUID) -> None:
    """Hard-deletes every *data* row belonging to a household — assets and
    their type-specific detail rows, fuel/trip logs, maintenance records
    and schedules, attachment metadata — in FK-safe order (children before
    whatever they reference). Deliberately leaves the household itself,
    its memberships/invites, API tokens, and sync devices untouched: this
    is the "start over with a clean slate" reset, not household deletion.
    See delete_household_data below for the full-household version, which
    is this function plus a few more steps.

    Attachment blob files are left in place — same accepted storage-leak
    tradeoff as a normal single attachment delete (see attachments.py's
    delete_attachment) — only metadata rows go here.

    Adding a new entity type (mirroring fuel_log, per the root CLAUDE.md
    invariant) means adding it here too, or this silently stops covering
    it. Doesn't commit — that's left to the caller.
    """
    record_ids = select(MaintenanceRecord.id).where(MaintenanceRecord.household_id == household_id)
    asset_ids = select(Asset.id).where(Asset.household_id == household_id)

    await db.execute(delete(RecordAttachment).where(RecordAttachment.record_id.in_(record_ids)))
    await db.execute(delete(VehicleDetails).where(VehicleDetails.asset_id.in_(asset_ids)))
    await db.execute(delete(EquipmentDetails).where(EquipmentDetails.asset_id.in_(asset_ids)))
    await db.execute(delete(PropertyDetails).where(PropertyDetails.asset_id.in_(asset_ids)))
    await db.execute(delete(MaintenanceRecord).where(MaintenanceRecord.household_id == household_id))
    await db.execute(delete(MaintenanceSchedule).where(MaintenanceSchedule.household_id == household_id))
    await db.execute(delete(FuelLog).where(FuelLog.household_id == household_id))
    await db.execute(delete(TripLog).where(TripLog.household_id == household_id))
    await db.execute(delete(Asset).where(Asset.household_id == household_id))
    await db.execute(delete(Attachment).where(Attachment.household_id == household_id))


async def delete_household_data(db: AsyncSession, household_id: uuid.UUID) -> None:
    """Hard-deletes an entire household: everything wipe_household_data
    covers, plus the household's own membership/invite/token/device rows
    and the household row itself. The one place in the app that does real
    deletion rather than the deleted_at soft-delete every synced entity
    normally uses elsewhere.

    Shared by two callers with different authorization: an owner deleting
    their own household (households.py) and an instance admin deleting any
    household (admin.py) — both just need this same cleanup, gated
    differently. Neither commits here; that's left to the caller so it
    stays part of whatever transaction the caller is already managing.
    """
    await wipe_household_data(db, household_id)

    await db.execute(delete(ApiToken).where(ApiToken.household_id == household_id))
    await db.execute(delete(SyncDevice).where(SyncDevice.household_id == household_id))
    await db.execute(delete(HouseholdInvite).where(HouseholdInvite.household_id == household_id))
    await db.execute(delete(HouseholdMembership).where(HouseholdMembership.household_id == household_id))
    await db.execute(delete(Household).where(Household.id == household_id))
