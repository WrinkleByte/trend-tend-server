import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utcnow


class User(Base):
    """Global identity, not household-scoped — a user can belong to multiple
    households (see HouseholdMembership), so this deliberately doesn't use
    SyncedEntityMixin either."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Set once, on whichever user registers first via the setup flow (see
    # auth.py's register()) — an instance-wide (not household-scoped) admin
    # flag, distinct from HouseholdRole.OWNER, since a self-hosted instance
    # can host multiple independent households but has exactly one set of
    # instance settings (SMTP, etc. — see InstanceSettings) to administer.
    is_instance_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Every access/refresh token issued before this instant is treated as
    # invalid (2026-08-19 review, S5). Bumped on password reset, which
    # previously left existing sessions fully usable -- so a user who reset
    # their password *because* they believed they were compromised did not
    # actually evict the attacker, whose refresh token stayed good for up to
    # 30 days.
    #
    # A single timestamp rather than a token denylist: revocation here is
    # always all-or-nothing per user, so there's nothing to gain from
    # tracking individual tokens, and this needs no cleanup job. Compared
    # against the token's `iat` in deps.get_current_principal.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
