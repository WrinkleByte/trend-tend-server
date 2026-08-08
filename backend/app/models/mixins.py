import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class SyncedEntityMixin:
    """Sync envelope shared by every entity that syncs to mobile/web clients.

    `version` drives optimistic-concurrency conflict *detection* (the client's
    base_version vs. this row's current version); `updated_at` drives the
    last-write-wins *resolution* policy. See docs/architecture.md Section 3.
    Applied to Asset, MaintenanceRecord, MaintenanceSchedule, Attachment —
    entities that flow through the generic sync protocol. Household/User/
    memberships/invites/tokens are managed via dedicated endpoints instead.
    """

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    @declared_attr
    def household_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    @declared_attr
    def updated_by_device_id(cls):
        return mapped_column(UUID(as_uuid=True), ForeignKey("sync_devices.id"), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
