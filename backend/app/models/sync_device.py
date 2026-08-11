import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utcnow


class Platform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class ConflictResolutionMode(StrEnum):
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"


class SyncDevice(Base):
    """A device paired to a household's backend. Referenced by
    SyncedEntityMixin.updated_by_device_id on every syncable entity, so this
    model deliberately doesn't use that mixin itself (no circular self-FK)."""

    __tablename__ = "sync_devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(String(20), nullable=False)
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_cursor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conflict_resolution_mode: Mapped[ConflictResolutionMode] = mapped_column(
        String(20), default=ConflictResolutionMode.LAST_WRITE_WINS, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
