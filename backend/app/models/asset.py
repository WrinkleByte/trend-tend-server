# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class AssetType(StrEnum):
    VEHICLE = "vehicle"
    EQUIPMENT = "equipment"
    PROPERTY = "property"
    HOME_SYSTEM = "home_system"
    VALUABLE = "valuable"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISPOSED = "disposed"


class Asset(SyncedEntityMixin, Base):
    """Polymorphic base row shared by every asset type. Type-specific fields
    live in the 1:1 side tables below rather than as nullable columns here, so
    the base table stays narrow for list/sync/reminder queries. Adding a new
    asset_type later doesn't require migrating this table."""

    __tablename__ = "assets"

    asset_type: Mapped[AssetType] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    status: Mapped[AssetStatus] = mapped_column(String(20), default=AssetStatus.ACTIVE, nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Whose asset this is, within the household. A view filter only, NOT a
    # permission: every member can still see and edit every asset, and the
    # household remains the sole tenant boundary (no RLS or
    # household_scoped_query change). Clients use it to offer an "only show
    # my stuff" toggle for people who share an instance but don't care about
    # each other's cars.
    #
    # Null means unassigned, which is both the pre-existing state of every
    # row and the state an asset returns to when its owner is deleted — an
    # unassigned asset is visible under every filter rather than becoming
    # invisible to everyone.
    #
    # Unlike updated_by_user_id (SyncedEntityMixin), this one IS legitimately
    # client-settable, so every write path has to check the id actually
    # belongs to a member of this household — see sync.py's _apply_change.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )


class VehicleDetails(Base):
    """1:1 detail table for Asset rows where asset_type=vehicle. Not
    independently synced/versioned — always read/written alongside the parent
    Asset row, so it carries no sync envelope of its own."""

    __tablename__ = "vehicle_details"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True
    )
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(nullable=True)
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_mileage: Mapped[int | None] = mapped_column(nullable=True)
    mileage_unit: Mapped[str] = mapped_column(String(10), default="mi", nullable=False)
    fuel_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Per-vehicle overrides of the mobile app's device-global cosmetic/unit
    # settings -- null means "inherit the household default, or the device's
    # own local override of it" (see tendfida-mobile's AppSettings.swift /
    # AndroidAppSettings.kt for the 4-tier resolution this feeds). Values
    # mirror the mobile CarDisplayTheme raw cases and
    # UnitFormatter.unitSystem(key)'s "imperial"/"metric" keys exactly, no
    # new vocabulary invented server-side.
    car_display_theme: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stylized_plate_enabled: Mapped[bool | None] = mapped_column(nullable=True)
    unit_system_override: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Vikunja #103: which stylized plate design to draw when
    # stylized_plate_enabled resolves true -- plain per-vehicle attribute
    # (not a device/household-resolved override like the two fields
    # above), values are the mobile PlateStyle enum's raw cases (defined
    # per-platform, no shared vocabulary to mirror here). NULL means the
    # plain "generic" style.
    plate_style: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Vikunja #92: this vehicle's remembered service specs -- the mobile
    # app prefills a new maintenance record's matching structured field
    # (see MaintenanceRecord above) from these when the user hasn't
    # already typed a value in for that record, editable per-record if it
    # differs that time. Front/rear differential get separate defaults
    # since some vehicles genuinely spec a different fluid for each, even
    # though a single differential-service *record* only ever needs one
    # fluid_type (its own category already says which side).
    default_oil_viscosity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_oil_formulation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    default_oil_meets_dexos: Mapped[bool | None] = mapped_column(nullable=True)
    default_oil_filter_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_air_filter_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_transmission_fluid_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_coolant_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_differential_front_fluid_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_differential_rear_fluid_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Follow-up to the above: capacities, plus the transmission filter part #
    # (reuses default_oil_filter_part_number's sibling concept, its own
    # column since a vehicle needs to remember all three filter part #s at
    # once, unlike a single MaintenanceRecord which only ever needs one).
    default_oil_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_transmission_filter_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_transmission_fluid_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_differential_front_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_differential_rear_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)


class EquipmentDetails(Base):
    """1:1 detail table for Asset rows where asset_type=equipment (mowers,
    snow blowers, generators, and similar home equipment)."""

    __tablename__ = "equipment_details"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    warranty_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    # See VehicleDetails' matching fields above -- same per-asset-override
    # concept, no stylized_plate_enabled here since equipment has no plate.
    car_display_theme: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_system_override: Mapped[str | None] = mapped_column(String(10), nullable=True)


class PropertyDetails(Base):
    """1:1 detail table for Asset rows where asset_type=property or
    home_system (e.g. an HVAC unit that belongs to a property, via
    parent_asset_id)."""

    __tablename__ = "property_details"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )
    install_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ValuableDetails(Base):
    """1:1 detail table for Asset rows where asset_type=valuable -- large
    one-off purchases (TVs, grills, appliances, and similar) that aren't
    engine/power-driven the way `equipment` is (no hour-meter field here)
    and aren't the home/land itself the way `property` is.

    linked_property_asset_id is a deliberately separate concept from
    PropertyDetails.parent_asset_id above: parent_asset_id nests a
    property/home_system asset under a parent property, wired specifically
    for that in AssetRepository/SyncEngine on the client. This field just
    says "this valuable is located at that property" -- optional, and not
    restricted at the DB level to property-typed assets (validated at the
    API layer instead, same as every other cross-asset reference here)."""

    __tablename__ = "valuable_details"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    warranty_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Where it was bought (store name, e.g. "Best Buy", "Costco") -- distinct
    # from linked_property_asset_id below, which is *where it lives now*.
    purchase_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linked_property_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )


class AssetAttachment(Base):
    """Join table linking an Asset to N Attachments (extra photos, PDF
    service manuals, etc.) -- distinct from Asset.photo_attachment_id, which
    stays the single 1:1 primary-photo column. Not a SyncedEntityMixin
    table, same as RecordAttachment/FuelLogAttachment/TripLogAttachment:
    plain server-side join-table bookkeeping, not part of the sync wire
    protocol."""

    __tablename__ = "asset_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False, index=True
    )
