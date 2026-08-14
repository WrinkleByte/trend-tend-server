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


async def delete_household_data(db: AsyncSession, household_id: uuid.UUID) -> None:
    """Hard-deletes every row belonging to a household, in FK-safe order —
    the one place in the app that does real deletion rather than the
    deleted_at soft-delete every synced entity normally uses elsewhere,
    since the household itself is going away entirely, not just one record
    in it. Attachment blob files are deliberately left in place — same
    accepted storage-leak tradeoff as a normal single attachment delete
    (see attachments.py's delete_attachment) — only metadata rows go here.

    Order matters: children before whatever they reference. Adding a new
    entity type (mirroring fuel_log, per the root CLAUDE.md invariant)
    means adding it here too, or this silently stops covering it.

    Shared by two callers with different authorization: an owner deleting
    their own household (households.py) and an instance admin deleting any
    household (admin.py) — both just need this same cleanup, gated
    differently. Neither commits here; that's left to the caller so it
    stays part of whatever transaction the caller is already managing.
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
    await db.execute(delete(ApiToken).where(ApiToken.household_id == household_id))
    await db.execute(delete(SyncDevice).where(SyncDevice.household_id == household_id))
    await db.execute(delete(HouseholdInvite).where(HouseholdInvite.household_id == household_id))
    await db.execute(delete(HouseholdMembership).where(HouseholdMembership.household_id == household_id))
    await db.execute(delete(Household).where(Household.id == household_id))
