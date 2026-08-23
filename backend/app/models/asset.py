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
