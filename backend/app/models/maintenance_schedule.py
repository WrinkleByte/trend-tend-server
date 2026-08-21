import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class IntervalType(StrEnum):
    TIME = "time"
    USAGE = "usage"
    BOTH = "both"


class MaintenanceSchedule(SyncedEntityMixin, Base):
    """A recurring reminder rule for an asset. next_due_date/next_due_usage/
    is_overdue are deliberately NOT stored — they're computed by
    app.core.recurrence from anchor + interval vs. now/current usage, mirrored
    1:1 by the mobile shared module's Kotlin RecurrenceEngine."""

    __tablename__ = "maintenance_schedules"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    interval_type: Mapped[IntervalType] = mapped_column(String(10), nullable=False)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_usage_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    anchor_usage_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_completed_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_records.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Set when a user taps "Ignore" on a due/overdue alert on any device;
    # cleared when the schedule is next marked performed. Mirrors the mobile
    # shared module's maintenanceSchedule.dismissedAt column 1:1 so the
    # generic sync protocol (MaintenanceScheduleSyncData) can propagate a
    # dismissal across every paired device in the household, not just the
    # one it was dismissed on (Vikunja #42).
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
