import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.rate_limit import reset_all_rate_limiters
from app.db.base import Base
from app.db.rls import set_rls_context
from app.db.session import get_db
from app.main import app

settings = get_settings()


@pytest.fixture(scope="session")
async def engine():
    # Uses a dedicated database on the same Postgres server as dev, so test
    # runs never touch dev data. Created/dropped fresh every test session.
    admin_engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    test_db_name = f"wrinklebyte_test_{uuid.uuid4().hex[:8]}"
    async with admin_engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text(f'CREATE DATABASE "{test_db_name}"'))
    await admin_engine.dispose()

    test_url = settings.database_url.rsplit("/", 1)[0] + f"/{test_db_name}"
    test_engine = create_async_engine(test_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    await test_engine.dispose()
    admin_engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
    await admin_engine.dispose()


@pytest.fixture(autouse=True)
def _neutralise_smtp_env():
    """Stop the host's SMTP_* environment leaking into tests.

    get_settings() is lru_cache'd, so there is one Settings object shared by
    the whole session, seeded from the real environment. On a machine whose
    .env configures SMTP (the docker-compose dev stack does), a
    freshly-created instance_settings row comes up with smtp_enabled=True --
    and with SMTP_FORCE_ENV set, gets re-seeded on every read, overwriting
    whatever a test just wrote.

    That made test_instance_admin_can_read_and_write_smtp_settings fail on
    this machine while passing on one without SMTP configured: a test
    outcome that depended on the developer's environment rather than the
    code. Pinning the SMTP-related settings to their defaults for the
    duration of each test removes that dependency.
    """
    settings = get_settings()
    saved = {
        field: getattr(settings, field)
        for field in (
            "smtp_enabled",
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "smtp_use_tls",
            "smtp_from_address",
            "smtp_force_env",
        )
    }
    settings.smtp_enabled = False
    settings.smtp_host = ""
    settings.smtp_port = None
    settings.smtp_username = ""
    settings.smtp_password = ""
    settings.smtp_use_tls = True
    settings.smtp_from_address = ""
    settings.smtp_force_env = False
    yield
    for field, value in saved.items():
        setattr(settings, field, value)


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    # The `app` instance (and therefore every RateLimiter's in-memory hit
    # dict) is shared across the whole test session, and httpx's
    # ASGITransport gives every test the same synthetic client IP — without
    # this, unrelated tests hammering /auth/register or /auth/login via the
    # registered_user/auth_headers fixtures would trip the real limiter and
    # cause spurious 429s well before any dedicated rate-limit test gets to
    # run its own assertions.
    reset_all_rate_limiters()
    yield
    reset_all_rate_limiters()


@pytest.fixture(autouse=True)
async def _clean_tables(engine):
    # `engine` (and the Postgres database behind it) is session-scoped for
    # speed — without this, data from one test (e.g. a registered user)
    # would leak into the next and cause spurious 409s. TRUNCATE ... CASCADE
    # handles FK ordering for us regardless of table dependency direction.
    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db_session(engine) -> AsyncSession:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        # This fixture is for direct test assertions/setup across whatever
        # households a test happens to have created, not a stand-in for a
        # real request -- same rationale as admin.py's legitimate
        # cross-household bypass (see app/db/rls.py). Without this, every
        # existing test reading rows back via db_session would silently see
        # nothing once RLS is enabled, since no Principal (and therefore no
        # household_id GUC) is ever involved here.
        await set_rls_context(session, household_id=None, bypass=True)
        yield session


@pytest.fixture
async def client(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db_override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def registered_user(client):
    payload = {
        "email": "alice@example.com",
        "password": "correct horse battery staple",
        "display_name": "Alice",
        "household_name": "Alice's House",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['access_token']}"}
