import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instance_settings import InstanceSettings


async def get_or_create_instance_settings(db: AsyncSession) -> InstanceSettings:
    """There's exactly one InstanceSettings row for the whole deployment —
    enforced here (get-or-create) rather than a DB constraint, since a
    fresh install has zero rows and the first read/write should just work
    rather than requiring an explicit init step. Shared between the
    settings CRUD endpoint and auth.py's forgot-password flow, which both
    need to read the SMTP config."""
    result = await db.execute(select(InstanceSettings).limit(1))
    settings = result.scalar_one_or_none()
    if settings is not None:
        return settings

    settings = InstanceSettings(id=uuid.uuid4())
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
