import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.instance_settings import InstanceSettings


async def get_or_create_instance_settings(db: AsyncSession) -> InstanceSettings:
    """There's exactly one InstanceSettings row for the whole deployment —
    enforced here (get-or-create) rather than a DB constraint, since a
    fresh install has zero rows and the first read/write should just work
    rather than requiring an explicit init step. Shared between the
    settings CRUD endpoint and auth.py's forgot-password flow, which both
    need to read the SMTP config.

    On first creation only, SMTP_* env vars (see config.py) seed the row —
    lets a docker-compose deployment come up with SMTP already working via
    its .env file. Once the row exists, the admin instance-settings UI/API
    is the sole source of truth; env vars are never consulted again, so
    editing them after first boot has no effect without dropping the row —
    unless SMTP_FORCE_ENV is set, in which case they're re-applied on every
    call, overwriting any admin-edited values (effectively making the
    webui's SMTP fields read-only).
    """
    result = await db.execute(select(InstanceSettings).limit(1))
    settings = result.scalar_one_or_none()
    env = get_settings()

    if settings is not None:
        if env.smtp_force_env:
            _apply_env_smtp(settings, env)
            # No-op flush if nothing actually changed from what's already
            # in the DB — SQLAlchemy only emits an UPDATE for columns whose
            # value differs, so this doesn't churn updated_at on every
            # request when the admin hasn't touched the row since.
            await db.commit()
            await db.refresh(settings)
        return settings

    settings = InstanceSettings(id=uuid.uuid4())
    _apply_env_smtp(settings, env)
    settings.public_api_url = env.public_api_url or None
    db.add(settings)
    # Commit, not just flush — callers that only ever read (GET
    # instance-settings, or forgot-password checking whether SMTP is
    # configured) never call db.commit() themselves, so a flush-only insert
    # here would be visible for the rest of this request and then silently
    # discarded once the session closes without a commit — the "singleton"
    # row would never actually persist until something happened to PUT to
    # it first.
    await db.commit()
    await db.refresh(settings)
    return settings


def _apply_env_smtp(settings: InstanceSettings, env) -> None:
    settings.smtp_enabled = env.smtp_enabled
    settings.smtp_host = env.smtp_host or None
    settings.smtp_port = env.smtp_port
    settings.smtp_username = env.smtp_username or None
    settings.smtp_password = env.smtp_password or None
    settings.smtp_use_tls = env.smtp_use_tls
    settings.smtp_from_address = env.smtp_from_address or None
