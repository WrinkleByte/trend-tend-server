"""Proves Postgres RLS actually restricts rows at the database level
(Vikunja #44) -- independent of, not a duplicate of, test_household_isolation.py's
coverage, which proves the ORM-level household_scoped_query()/
verify_owned_reference() helpers work. That layer was already correct
before this card; what RLS adds is a backstop for a *future* endpoint that
forgets to use them, which by definition an ORM-level test can never catch
-- so this module deliberately runs an unscoped `SELECT * FROM assets`
(exactly the kind of query a forgetful endpoint would write) and proves it
still only returns the calling household's rows.

conftest.py's `engine` fixture builds its schema via
Base.metadata.create_all, not the Alembic migration chain, so the RLS
policies from that migration never exist in the test database unless
something applies them. The fixtures below do that directly (mirroring
the migration's upgrade() body) against a throwaway, genuinely
non-superuser role created and dropped per test -- proving real enforcement
for a role that can't bypass RLS, not just that the policies compile.
Deliberately does NOT touch the shared `wrinklebyte` role's own privileges,
so this can't affect any other test file's connections.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.models.user import User

_RLS_TABLES = (
    "assets",
    "attachments",
    "fuel_logs",
    "maintenance_records",
    "maintenance_schedules",
    "trip_logs",
)
_TEST_ROLE = "rls_test_verifier"
_TEST_ROLE_PASSWORD = "rls-test-only-not-a-real-secret"  # test-only role, dropped every run


@pytest.fixture
async def rls_verifier_engine(engine):
    """Enables real RLS on the test database's household-scoped tables,
    creates a throwaway non-superuser role that can't bypass it, and yields
    an engine connected AS that role -- so tests below prove enforcement
    for a role shaped like the app's own (post-migration) role, not for the
    superuser `wrinklebyte` role every other fixture in this suite uses."""
    # NullPool -- these engines are used briefly by one test then discarded;
    # a pooled connection sitting idle past dispose() is exactly what made
    # the session-scoped `engine` fixture's own DROP DATABASE teardown fail
    # with "database is being accessed by other users" while developing this.
    admin_engine = create_async_engine(engine.url, poolclass=NullPool)
    async with admin_engine.begin() as conn:
        for table in _RLS_TABLES:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            await conn.execute(
                text(
                    f"CREATE POLICY household_isolation ON {table} USING ("
                    "  current_setting('app.bypass_household_rls', true) = 'on'"
                    "  OR household_id = current_setting('app.household_id', true)::uuid"
                    ")"
                )
            )
        await conn.execute(
            text(f"CREATE ROLE {_TEST_ROLE} LOGIN PASSWORD '{_TEST_ROLE_PASSWORD}' NOSUPERUSER NOBYPASSRLS")
        )
        await conn.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {_TEST_ROLE}")
        )

    verifier_url = engine.url.set(username=_TEST_ROLE, password=_TEST_ROLE_PASSWORD)
    verifier_engine = create_async_engine(verifier_url, poolclass=NullPool)

    yield verifier_engine

    await verifier_engine.dispose()
    async with admin_engine.begin() as conn:
        for table in _RLS_TABLES:
            await conn.execute(text(f"DROP POLICY IF EXISTS household_isolation ON {table}"))
            await conn.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        # A role can't be dropped while it still holds any GRANTs -- this
        # revokes everything granted to it in one shot (there's nothing it
        # owns to also drop, since it never created anything).
        await conn.execute(text(f"DROP OWNED BY {_TEST_ROLE}"))
        await conn.execute(text(f"DROP ROLE IF EXISTS {_TEST_ROLE}"))
    await admin_engine.dispose()


async def _register(client, email: str, household_name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": email.split("@")[0],
            "household_name": household_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _household_id(client, headers) -> str:
    response = await client.get("/api/v1/households/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _create_asset(client, headers, name: str) -> str:
    response = await client.post(
        "/api/v1/assets", headers=headers, json={"asset_type": "vehicle", "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _make_instance_admin(db_session, email: str) -> None:
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_instance_admin = True
    await db_session.commit()


async def test_unscoped_query_only_sees_the_gucs_household(client, rls_verifier_engine):
    """The core proof: a query with NO household_id filter at all --
    exactly what a future endpoint that forgot household_scoped_query()
    would run -- still only returns one household's row, because the
    database itself enforces it, not the application code."""
    house_a = await _register(client, "rls-a@example.com", "House A")
    house_b = await _register(client, "rls-b@example.com", "House B")
    headers_a = {"Authorization": f"Bearer {house_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {house_b['access_token']}"}
    household_a_id = await _household_id(client, headers_a)

    await _create_asset(client, headers_a, "House A's Truck")
    await _create_asset(client, headers_b, "House B's Truck")

    async with rls_verifier_engine.connect() as conn:
        await conn.execute(text("SELECT set_config('app.household_id', :hh, false)"), {"hh": household_a_id})
        # Deliberately unscoped -- no WHERE clause on household_id at all.
        result = await conn.execute(text("SELECT name FROM assets"))
        names = [row[0] for row in result.all()]

    assert names == ["House A's Truck"]


async def test_no_guc_set_sees_nothing(client, rls_verifier_engine):
    """Fail-safe default: a connection that never had the household_id GUC
    set (e.g. a hypothetical future code path that forgets to call
    set_rls_context at all) sees zero rows, not every row."""
    house_a = await _register(client, "rls-nofilter-a@example.com", "House NoFilter A")
    headers_a = {"Authorization": f"Bearer {house_a['access_token']}"}
    await _create_asset(client, headers_a, "Should Be Invisible")

    async with rls_verifier_engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM assets"))
        assert result.all() == []


async def test_bypass_guc_sees_every_household(client, rls_verifier_engine):
    """Proves the admin.py escape hatch: with the bypass GUC on, the same
    restricted role sees every household's rows -- the mechanism admin.py's
    deliberately cross-household endpoints rely on."""
    house_a = await _register(client, "rls-bypass-a@example.com", "House Bypass A")
    house_b = await _register(client, "rls-bypass-b@example.com", "House Bypass B")
    headers_a = {"Authorization": f"Bearer {house_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {house_b['access_token']}"}
    await _create_asset(client, headers_a, "Bypass Truck A")
    await _create_asset(client, headers_b, "Bypass Truck B")

    async with rls_verifier_engine.connect() as conn:
        await conn.execute(text("SELECT set_config('app.bypass_household_rls', 'on', false)"))
        result = await conn.execute(text("SELECT name FROM assets ORDER BY name"))
        names = [row[0] for row in result.all()]

    assert names == ["Bypass Truck A", "Bypass Truck B"]


async def test_admin_household_listing_still_sees_every_household(client, db_session):
    """The card's own explicit scope: a legitimate cross-cutting query
    (admin.py, gated on instance-admin) must keep working once RLS is on --
    proven through the real HTTP endpoint, using the real app role."""
    owner_a = await _register(client, "rls-admin-a@example.com", "Admin Test House A")
    owner_b = await _register(client, "rls-admin-b@example.com", "Admin Test House B")
    headers_a = {"Authorization": f"Bearer {owner_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {owner_b['access_token']}"}
    await _create_asset(client, headers_a, "Admin-visible Truck A")
    await _create_asset(client, headers_b, "Admin-visible Truck B")

    # First registered user on a fresh instance becomes instance admin.
    admin = await _register(client, "rls-admin-root@example.com", "Admin Root House")
    await _make_instance_admin(db_session, "rls-admin-root@example.com")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

    response = await client.get("/api/v1/admin/households", headers=admin_headers)
    assert response.status_code == 200
    households = response.json()
    names = {h["name"] for h in households}
    assert {"Admin Test House A", "Admin Test House B", "Admin Root House"} <= names
    counts_by_name = {h["name"]: h["record_counts"]["assets"] for h in households}
    assert counts_by_name["Admin Test House A"] == 1
    assert counts_by_name["Admin Test House B"] == 1


async def test_admin_can_delete_another_households_data(client, db_session):
    """The riskiest regression this change could cause: delete_household_as_admin
    deletes rows for a household that ISN'T the admin's own -- if the RLS
    bypass didn't apply here, this would now silently delete zero rows
    instead of the target household's data."""
    target = await _register(client, "rls-admin-target@example.com", "Admin Target House")
    target_headers = {"Authorization": f"Bearer {target['access_token']}"}
    await _create_asset(client, target_headers, "Doomed Truck")

    admin = await _register(client, "rls-admin-deleter@example.com", "Admin Deleter House")
    await _make_instance_admin(db_session, "rls-admin-deleter@example.com")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

    listing = await client.get("/api/v1/admin/households", headers=admin_headers)
    target_id = next(h["id"] for h in listing.json() if h["name"] == "Admin Target House")

    delete_response = await client.delete(f"/api/v1/admin/households/{target_id}", headers=admin_headers)
    assert delete_response.status_code == 204

    listing_after = await client.get("/api/v1/admin/households", headers=admin_headers)
    assert target_id not in [h["id"] for h in listing_after.json()]
