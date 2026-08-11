import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utcnow


class InstanceSettings(Base):
    """Singleton row (exactly one, enforced by the application layer, not a
    DB constraint — see api/v1/instance_settings.py's get-or-create helper)
    holding settings for the whole self-hosted instance rather than any one
    household, since things like an SMTP relay are configured once per
    deployment. SMTP fields are all optional; forgot-password degrades to a
    logged no-op (see core/email.py) until smtp_enabled is turned on."""

    __tablename__ = "instance_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    smtp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    smtp_from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
