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
    # The backend API's own externally-reachable base URL (e.g.
    # "http://192.168.1.50:8000"), used to build the mobile-pairing QR code
    # on the API Tokens page instead of assuming window.location.origin --
    # that assumption only holds when web and API share an origin (true in
    # the production nginx deployment, per web/nginx.conf's /api/ proxy),
    # not in the docker-compose dev/self-hosted setup where the web dev
    # server and the API are published on different ports with nothing
    # bridging them for a non-browser client. Falls back to
    # window.location.origin when unset, so production behavior is
    # unchanged either way. See config.py's public_api_url for the
    # one-time env-var seed on first creation.
    public_api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
