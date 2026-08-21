import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.asset import AssetStatus, AssetType
from app.models.attachment import StorageBackendType
from app.models.maintenance_schedule import IntervalType
from app.models.sync_device import ConflictResolutionMode, Platform


class SyncDeviceRegister(BaseModel):
    platform: Platform
    device_name: str
    conflict_resolution_mode: ConflictResolutionMode = ConflictResolutionMode.LAST_WRITE_WINS


class SyncDeviceResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    platform: Platform
    device_name: str
    conflict_resolution_mode: ConflictResolutionMode
    last_sync_at: datetime | None
    created_at: datetime
    # Exposed so a client can show which of a household's devices are still
    # live -- you cannot sensibly decide what to revoke without seeing it
    # (Vikunja #36).
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Per-entity payload shapes for sync push/pull's opaque `data` field ---
#
# Deliberately cover only each entity's own SyncedEntityMixin table — not the
# 1:1 asset detail side tables (vehicle_details/equipment_details/
# property_details), which mirrors the mobile plan's precedent of not
# independently syncing non-enveloped child rows. Editing those still goes
# through the regular REST endpoints (see app/api/v1/assets.py). Extending
# sync to cover them is a documented follow-up, not silently unsupported.
#
# Full-row semantics: every push replaces the entity's entire syncable field
# set (not a partial patch) — simpler and avoids stale-field merge bugs
# across a batch of devices with different partial views of a row.


class AssetSyncData(BaseModel):
    asset_type: AssetType
    name: str
    notes: str | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None


class MaintenanceRecordSyncData(BaseModel):
    asset_id: uuid.UUID
    performed_at: date
    performed_by: str | None = None
    category: str
    custom_category: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    currency: str = "USD"
    odometer_reading: int | None = None
    schedule_id: uuid.UUID | None = None


class FuelLogSyncData(BaseModel):
    asset_id: uuid.UUID
    performed_at: date
    odometer_reading: int | None = None
    gallons: Decimal
    cost_per_gallon: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "USD"
    is_fill_up: bool = True
    mpg: Decimal | None = None
    octane: int | None = None
    cetane: int | None = None
    gas_brand: str | None = None
    location: str | None = None
    notes: str | None = None
    additive: str | None = None


class TripLogSyncData(BaseModel):
    asset_id: uuid.UUID
    performed_at: datetime
    purpose: str
    custom_purpose: str | None = None
    start_odometer: Decimal | None = None
    end_odometer: Decimal
    distance: Decimal
    notes: str | None = None


class MaintenanceScheduleSyncData(BaseModel):
    asset_id: uuid.UUID
    name: str
    interval_type: IntervalType
    interval_days: int | None = None
    interval_usage_amount: int | None = None
    usage_field: str | None = None
    anchor_date: date | None = None
    anchor_usage_value: int | None = None
    active: bool = True
    dismissed_at: datetime | None = None


class AttachmentSyncData(BaseModel):
    # storage_backend/storage_key are set by whichever path actually put the
    # blob bytes in place — today that's the multipart POST /attachments
    # endpoint. A client that creates an attachment row locally-only (no
    # blob uploaded yet) has nothing meaningful to push here until a
    # dedicated blob-upload-by-key endpoint exists (see Section 3 of
    # docs/architecture.md — "Attachment blobs sync separately"), which is
    # not yet implemented. Metadata sync itself works today regardless.
    original_filename: str
    content_type: str
    size_bytes: int
    storage_backend: StorageBackendType
    storage_key: str
    sha256: str
    thumbnail_storage_key: str | None = None
    captured_at: datetime | None = None


class SyncPullRequest(BaseModel):
    cursor: str | None = None
    device_id: uuid.UUID


class SyncChangeOut(BaseModel):
    entity_type: str
    id: uuid.UUID
    version: int
    updated_at: datetime
    deleted: bool
    data: dict


class SyncPullResponse(BaseModel):
    changes: list[SyncChangeOut]
    next_cursor: str | None
    has_more: bool


class SyncChangeIn(BaseModel):
    entity_type: str
    id: uuid.UUID
    base_version: int
    data: dict
    client_updated_at: datetime
    # Soft-deletes push through the same endpoint as edits — `data` is
    # ignored entirely when this is true (deleting doesn't require valid
    # field values), matching pull's `deleted` flag on the way back down.
    deleted: bool = False


class SyncPushRequest(BaseModel):
    device_id: uuid.UUID
    changes: list[SyncChangeIn]


class SyncPushResult(BaseModel):
    id: uuid.UUID
    status: str  # "accepted" | "conflict" | "rejected"
    new_version: int | None = None
    server_updated_at: datetime | None = None
    server_version: int | None = None
    server_data: dict | None = None
    client_data: dict | None = None
    reason: str | None = None
    detail: str | None = None


class SyncPushResponse(BaseModel):
    results: list[SyncPushResult]
