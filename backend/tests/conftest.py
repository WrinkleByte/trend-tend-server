import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

settings = get_settings()


@pytest.fixture(scope="session")
async def engine():
    # Uses a dedicated database on the same Postgres server as dev, so test
    # runs never touch dev data. Created/dropped fresh every test session.
    admin_engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    test_db_name = f"maintainit_test_{uuid.uuid4().hex[:8]}"
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
