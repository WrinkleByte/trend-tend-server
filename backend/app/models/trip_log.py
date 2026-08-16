import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class TripLog(SyncedEntityMixin, Base):
    """Mirrors the mobile shared module's `tripLog` table field-for-field
    (see WrinkleByte.sq in the companion mobile repo) — mileage-tracking trip
    entries with a required odometer photo (via the generic attachment
    system), syncable the same as any other entity via SYNC_REGISTRY (see
    app/api/v1/sync.py)."""

    __tablename__ = "trip_logs"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    custom_purpose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_odometer: Mapped[Decimal | None] = mapped_column(Numeric(10, 1), nullable=True)
    end_odometer: Mapped[Decimal] = mapped_column(Numeric(10, 1), nullable=False)
    distance: Mapped[Decimal] = mapped_column(Numeric(10, 1), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TripLogAttachment(Base):
    """Join table linking a TripLog to N Attachments — mirrors
    RecordAttachment (app/models/maintenance_record.py). Backs the
    "required odometer photo" mentioned in TripLog's docstring above."""

    __tablename__ = "trip_log_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_logs.id"), nullable=False, index=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False, index=True
    )
