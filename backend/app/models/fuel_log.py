# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class FuelLog(SyncedEntityMixin, Base):
    """Mirrors the mobile shared module's `fuelLog` table field-for-field
    (see WrinkleByte.sq in the companion mobile repo) — fuel fill-up entries
    used for MPG/fuel-economy tracking, syncable the same as any other
    entity via SYNC_REGISTRY (see app/api/v1/sync.py)."""

    __tablename__ = "fuel_logs"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    performed_at: Mapped[date] = mapped_column(Date, nullable=False)
    odometer_reading: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Nullable: an entry can be jotted down with only a date and filled in
    # later, so "volume not recorded" has to be representable. Distinct from
    # 0, which would mean a genuine zero-gallon fill-up and would drag the
    # MPG average down -- consumers skip null rather than treating it as 0.
    gallons: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    cost_per_gallon: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    is_fill_up: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mpg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    octane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cetane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gas_brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Vikunja #100 (mobile): the fill-up's real-world coordinates, captured
    # automatically at save time on mobile -- no map picker, no station
    # search. Independent of `location` above, which stays free text.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    additive: Mapped[str | None] = mapped_column(String(100), nullable=True)


class FuelLogAttachment(Base):
    """Join table linking a FuelLog to N Attachments — mirrors
    RecordAttachment (app/models/maintenance_record.py)."""

    __tablename__ = "fuel_log_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fuel_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fuel_logs.id"), nullable=False, index=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False, index=True
    )
