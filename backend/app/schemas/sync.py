# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.asset import AssetStatus, AssetType, ServiceDefaults
from app.models.attachment import StorageBackendType
from app.models.maintenance_schedule import IntervalType
from app.models.sync_device import ConflictResolutionMode, Platform
from app.schemas.asset import ServiceDefaultsIn


class SyncDeviceRegister(BaseModel):
    platform: Platform
    device_name: str
    conflict_resolution_mode: ConflictResolutionMode = ConflictResolutionMode.LAST_WRITE_WINS
    # The client side of the handshake (Vikunja #828): what app this is, and which field
    # families it understands, named in the server's own vocabulary. Both optional, and
    # an app that predates the key simply omits it -- which the server reads as a legacy
    # superset client, not as a client that can do nothing.
    client_version: str | None = None
    capabilities: list[str] | None = None


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
    # ... and which of them have ever negotiated at all (Vikunja #828). A household with one
    # phone that declared capabilities and one that never did is a household where the two
    # halves are storing different amounts of the same row, and nothing else in the API
    # makes that visible.
    client_version: str | None = None
    capabilities: list[str] | None = None
    capabilities_reported_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Per-entity payload shapes for sync push/pull's opaque `data` field ---
#
# Full-row semantics: every push replaces the entity's entire syncable field
# set (not a partial patch) — simpler and avoids stale-field merge bugs
# across a batch of devices with different partial views of a row.


class AttributedSyncData(BaseModel):
    """Base for every top-level entity payload, carrying the "who last touched
    this" attribution that SyncedEntityMixin adds to all synced tables.

    Declared once here rather than repeated on all seven schemas so a new
    syncable entity can't quietly ship without it.

    **Outbound only.** Full-row semantics (above) mean push takes whatever the
    client sends as the row's new field set, so a client could otherwise
    attribute its own edit to another household member. sync.py's
    _apply_change strips this field from the incoming payload and sets it from
    the authenticated Principal instead — it is present here purely so
    _serialize_row includes it on pull, since that function derives the wire
    shape from these same schemas (the allowlist invariant in
    docs/development.md). Nested detail payloads (VehicleDetailsSyncData and
    friends) deliberately don't inherit it: they have no sync envelope of
    their own and ride along inside their parent asset.
    """

    updated_by_user_id: uuid.UUID | None = None


class VehicleDetailsSyncData(BaseModel):
    vin: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    current_mileage: int | None = None
    mileage_unit: str = "mi"
    fuel_type: str | None = None
    car_display_theme: str | None = None
    stylized_plate_enabled: bool | None = None
    unit_system_override: str | None = None
    plate_style: str | None = None
    default_oil_viscosity: str | None = None
    default_oil_formulation: str | None = None
    default_oil_meets_dexos: bool | None = None
    default_oil_filter_part_number: str | None = None
    default_air_filter_part_number: str | None = None
    default_transmission_fluid_type: str | None = None
    default_coolant_type: str | None = None
    default_differential_front_fluid_type: str | None = None
    default_differential_rear_fluid_type: str | None = None
    default_oil_capacity: str | None = None
    default_transmission_filter_part_number: str | None = None
    default_transmission_fluid_capacity: str | None = None
    default_differential_front_capacity: str | None = None
    default_differential_rear_capacity: str | None = None
    # Not legacy vehicle columns: see VEHICLE_SIDE_NEW_FIELDS in app/schemas/service_defaults.py.
    # Declared here because the shipped mobile build sends the brand preferences its 21.sqm
    # added inside vehicle_details, and an undeclared key is discarded at parse -- before any
    # handler can route it -- while the push is still reported to the client as accepted.
    default_motor_oil_brand: str | None = None
    default_oil_filter_brand: str | None = None
    default_air_filter_brand: str | None = None


class EquipmentDetailsSyncData(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None
    car_display_theme: str | None = None
    unit_system_override: str | None = None


class PropertyDetailsSyncData(BaseModel):
    address: str | None = None
    parent_asset_id: uuid.UUID | None = None
    install_date: date | None = None


class ValuableDetailsSyncData(BaseModel):
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    warranty_expiration: date | None = None
    purchase_location: str | None = None
    linked_property_asset_id: uuid.UUID | None = None


class ServiceDefaultsSyncData(ServiceDefaultsIn):
    """Wire shape for the asset-level service defaults, declared as its own class so
    the pull/push allowlist invariant keeps naming it explicitly (docs/development.md),
    and inheriting the field list from the REST schema because the two are meant to be
    identical -- a spec the REST API can store is a spec sync must be able to carry.

    The same names VehicleDetailsSyncData still declares for its fourteen legacy specs.
    Both halves are required: a pre-move client writes and reads through the legacy
    fields, a current client through these. See app/schemas/service_defaults.py.
    """


class AssetSyncData(AttributedSyncData):
    """The base `assets` row plus, nested, whichever 1:1 detail side table
    matches asset_type — the 1:1 tables carry no sync envelope of their own
    (see VehicleDetails' doc comment in app/models/asset.py) so they ride
    along inside the parent asset's change instead of getting their own
    SYNC_REGISTRY entry. sync.py's _apply_change/_serialize_row special-case
    entity_type=="asset" to upsert/nest whichever of these four is present
    — every other entity type ignores these fields entirely (StrEnum-typed
    asset_type is the discriminator, mirroring the asset.assetType-based
    discriminator the mobile client now also uses instead of "which detail
    object is non-null", for the same correctness reason)."""

    asset_type: AssetType
    name: str
    notes: str | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    # Added in 1.2. Clients older than that don't send these keys at all, so
    # _apply_change only writes them when they are present in the payload
    # (model_fields_set) -- an old app saving an asset must not wipe a sale
    # price a newer one recorded. Newer clients always send both, null
    # included, so clearing one still syncs.
    sale_price: Decimal | None = Field(default=None, ge=0)
    sale_date: date | None = None
    # Client-settable, unlike the inherited updated_by_user_id — assigning an
    # asset to a household member is a normal edit. _apply_change verifies the
    # id names an actual member of the pushing household before storing it.
    owner_user_id: uuid.UUID | None = None
    vehicle_details: VehicleDetailsSyncData | None = None
    equipment_details: EquipmentDetailsSyncData | None = None
    property_details: PropertyDetailsSyncData | None = None
    valuable_details: ValuableDetailsSyncData | None = None
    service_defaults: ServiceDefaultsSyncData | None = None


class MaintenanceRecordSyncData(AttributedSyncData):
    asset_id: uuid.UUID
    performed_at: date
    performed_by: str | None = None
    category: str
    custom_category: str | None = None
    additional_categories: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    currency: str = "USD"
    odometer_reading: int | None = None
    schedule_id: uuid.UUID | None = None
    oil_viscosity: str | None = None
    oil_formulation: str | None = None
    oil_meets_dexos: bool | None = None
    filter_part_number: str | None = None
    fluid_type: str | None = None
    capacity: str | None = None
    # Sent by the shipped mobile app on every record push. Declared here and backed by
    # maintenance_records.brand (migration a4f6c1d8b2e5): declaring it without the column
    # is the exact silent-loss shape tests/test_sync_contract.py exists to catch.
    brand: str | None = None


class FuelLogSyncData(AttributedSyncData):
    asset_id: uuid.UUID
    performed_at: date
    odometer_reading: int | None = None
    gallons: Decimal | None = None
    cost_per_gallon: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "USD"
    is_fill_up: bool = True
    mpg: Decimal | None = None
    octane: int | None = None
    cetane: int | None = None
    gas_brand: str | None = None
    location: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    additive: str | None = None


class TripLogSyncData(AttributedSyncData):
    asset_id: uuid.UUID
    performed_at: datetime
    purpose: str
    custom_purpose: str | None = None
    start_odometer: Decimal | None = None
    end_odometer: Decimal
    distance: Decimal
    notes: str | None = None


class MaintenanceScheduleSyncData(AttributedSyncData):
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


class MaintenanceCategorySyncData(AttributedSyncData):
    name: str


class AttachmentSyncData(AttributedSyncData):
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


# --- Saying out loud what this server can store (Vikunja #828) -----------------
#
# A capability tag means exactly one thing: the fields the tag names are accepted on
# push, stored, and sent back on pull. The tags below are DERIVED from the payload
# schemas just above rather than written out as a constant, because a tag advertised for
# a field the server would silently drop is worse than no tag at all: a client builds a
# form on it, someone types their oil filter brand into it, and the value vanishes. That
# is precisely the bug this whole card exists to prevent (comment 2204 on #823 -- build 16
# was already sending brands, the schema did not declare them, Pydantic dropped them, and
# the push still said "accepted"). If a field is added to a schema and a capability is
# not raised for it, the capability list cannot lie about it.
_SYNC_NESTED_MODELS: dict[str, type[BaseModel]] = {
    "vehicle_details": VehicleDetailsSyncData,
    "equipment_details": EquipmentDetailsSyncData,
    "property_details": PropertyDetailsSyncData,
    "valuable_details": ValuableDetailsSyncData,
    "service_defaults": ServiceDefaultsSyncData,
}


# Field names as the DATABASE sees them, read off the ORM table instead of off the
# payload classes. The two are not the same guarantee: a wire schema can declare a field
# the migration never gave a column, and a capability advertised on top of that is the
# exact bug this card exists to stop.
_STORED_SERVICE_DEFAULT_FIELDS: frozenset[str] = frozenset(
    column.name for column in ServiceDefaults.__table__.columns
)


def _stores(*names: str) -> bool:
    return set(names) <= _STORED_SERVICE_DEFAULT_FIELDS


def server_capabilities() -> list[str]:
    """Every field family this server can actually carry, as tags a client can gate on.

    A tag is advertised only while BOTH halves hold: the wire schema declares the field, so
    a client can send it, AND the table has a column for it, so it survives. Wire with no
    column is the silent-loss bug; a column the wire cannot reach is merely a field this
    build cannot be asked for. Neither one earns a tag on its own.
    """
    asset = AssetSyncData.model_fields
    vehicle = VehicleDetailsSyncData.model_fields
    carries_defaults = "service_defaults" in asset
    brands = {
        "default_motor_oil_brand",
        "default_oil_filter_brand",
        "default_air_filter_brand",
    }

    capabilities: list[str] = []
    if {"vehicle_details", "equipment_details", "property_details", "valuable_details"} <= set(asset):
        capabilities.append("assetDetails")
    if carries_defaults and _stores("default_oil_viscosity"):
        capabilities.append("serviceDefaults")
    # Both halves of the brand contract, legacy side included: build 16 sends brands
    # *inside* vehicle_details, so advertising brands is only honest while that shape is
    # still accepted. Drop either side and this tag has to fall with it.
    if brands <= set(vehicle) and _stores(*brands):
        capabilities.append("serviceDefaultsBrands")
    if carries_defaults and _stores("default_hydraulic_fluid_type", "default_hydraulic_fluid_capacity"):
        capabilities.append("equipmentServiceDefaults")
    if carries_defaults and _stores("default_hvac_filter_size", "default_water_filter_cartridge"):
        capabilities.append("propertyServiceDefaults")
    return capabilities


def unsupported_sync_fields(data_model: type[BaseModel], data: dict) -> list[str]:
    """Keys this push carried that the server has nowhere to store them.

    Pydantic drops these in silence today -- that is the mechanism, not a bug in
    Pydantic. Dot-separated so a client can point at the exact field it sent, and so a
    nested key cannot hide behind the name of the object that carried it.
    """
    fields = data_model.model_fields
    unsupported: list[str] = []
    for key, value in data.items():
        if key not in fields:
            unsupported.append(key)
            continue
        nested = _SYNC_NESTED_MODELS.get(key)
        if nested is not None and isinstance(value, dict):
            unsupported.extend(f"{key}.{k}" for k in value if k not in nested.model_fields)
    return unsupported


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
    # On every pull, whether or not the client asked (server_capabilities() above). An
    # app that has never heard of this key ignores it -- Android parses with
    # ignoreUnknownKeys = true, iOS Codable ignores unknown keys -- so advertising costs
    # an old client nothing and gives a new one something to check before it offers a
    # field the server would throw away.
    server_capabilities: list[str] = Field(default_factory=server_capabilities)
    # What THIS device last declared, echoed back so a client can tell "the server forgot
    # me" from "I never said". None means never declared -- deliberately not an empty list.
    device_capabilities: list[str] | None = None
    device_client_version: str | None = None


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
    # Optional refresh of what this device can do, carried on an ordinary push so an app
    # that upgrades mid-life doesn't need a second round trip to tell the server. Absent
    # means "nothing changed", never "clear what you have" (same rule as every other
    # optional field on this branch).
    client_version: str | None = None
    capabilities: list[str] | None = None


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
    # Fields this push carried that the server cannot store (unsupported_sync_fields
    # above). The row is STILL accepted -- refusing a whole change because of one key the
    # server has never heard of is how an old phone stops syncing at all. Loudness, not
    # rejection: the client keeps its local value instead of learning about the loss
    # later, on another device, where the field comes back empty.
    unsupported_fields: list[str] = []


class SyncPushResponse(BaseModel):
    results: list[SyncPushResult]
