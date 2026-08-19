import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utcnow


class RefreshToken(Base):
    """One issued refresh token, for rotation with reuse detection.

    A refresh token lives 30 days against an access token's 15 minutes, so
    it's the credential actually worth stealing. Previously /auth/refresh
    minted a new one and left the presented one valid, with no record of
    either -- a stolen token was simply good for its full 30 days, and its
    use was indistinguishable from the real user's.

    Rotation makes theft *detectable*: each token is single-use, and every
    token minted from another shares its `family_id`. If a token that has
    already been used shows up again, either the attacker or the legitimate
    user is replaying it -- we can't tell which, and it doesn't matter,
    because in both readings the family is compromised. So the whole family
    is revoked and both parties have to log in again.

    Not household-scoped and no SyncedEntityMixin: this is auth
    infrastructure, not user data, and never syncs anywhere.
    """

    __tablename__ = "refresh_tokens"

    # Doubles as the JWT's `jti` claim -- the token itself carries this id,
    # so nothing here stores the token string. A leaked dump of this table
    # grants nothing on its own.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set the first time this token is exchanged. Seeing it set again is the
    # reuse signal.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set on every token in a family when reuse is detected there.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
