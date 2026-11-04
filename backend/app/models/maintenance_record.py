# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class MaintenanceRecord(SyncedEntityMixin, Base):
    __tablename__ = "maintenance_records"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    performed_at: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    custom_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Vikunja: comma-joined category keys beyond the primary `category`
    # above, for a record that covers more than one thing (e.g. an oil
    # change done alongside a tire rotation). `category` stays the single
    # value every existing display site reads; this is additive, consulted
    # only by category-matching call sites (schedule auto-clear, dashboard
    # gauges, filters) that need to know every category a record touches.
    additional_categories: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    odometer_reading: Mapped[int | None] = mapped_column(nullable=True)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_schedules.id"), nullable=True
    )

    # Vikunja #92: structured fields, meaningful only for certain
    # categories -- a record only ever has one `category`, so
    # filter_part_number/fluid_type/capacity are safely reused across
    # categories (filter_part_number: oil filter on "oil_change", air
    # filter on "air_filter", transmission filter on "transmission_fluid";
    # fluid_type: "transmission_fluid"/"coolant"/"differential_front"/
    # "differential_rear"; capacity: "oil_change"/"transmission_fluid"/
    # "differential_front"/"differential_rear") rather than each getting
    # their own near-duplicate column.
    oil_viscosity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oil_formulation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    oil_meets_dexos: Mapped[bool | None] = mapped_column(nullable=True)
    filter_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fluid_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)


class RecordAttachment(Base):
    """Join table linking a MaintenanceRecord to N Attachments."""

    __tablename__ = "record_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_records.id"), nullable=False, index=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False, index=True
    )
