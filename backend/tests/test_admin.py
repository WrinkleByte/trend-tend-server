from sqlalchemy import select

from app.models.user import User


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
    assert response.status_code == 201
    return response.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_admin_households_requires_auth(client):
    response = await client.get("/api/v1/admin/households")
    assert response.status_code == 401


async def test_admin_households_requires_instance_admin(client):
    await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")

    response = await client.get("/api/v1/admin/households", headers=_headers(bob))
    assert response.status_code == 403


async def test_admin_can_list_all_households_with_members_and_counts(client):
    alice = await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")

    await client.post("/api/v1/assets", headers=_headers(alice), json={"asset_type": "vehicle", "name": "Van"})
    await client.post("/api/v1/assets", headers=_headers(bob), json={"asset_type": "equipment", "name": "Mower"})
    await client.post("/api/v1/assets", headers=_headers(bob), json={"asset_type": "equipment", "name": "Blower"})

    response = await client.get("/api/v1/admin/households", headers=_headers(alice))
    assert response.status_code == 200
    households = {h["name"]: h for h in response.json()}

    assert set(households) == {"Alice's House", "Bob's House"}

    alice_house = households["Alice's House"]
    assert alice_house["record_counts"]["assets"] == 1
    assert [m["email"] for m in alice_house["members"]] == ["alice@example.com"]
    assert alice_house["members"][0]["role"] == "owner"
    assert alice_house["members"][0]["is_instance_admin"] is True

    bob_house = households["Bob's House"]
    assert bob_house["record_counts"]["assets"] == 2
    assert [m["email"] for m in bob_house["members"]] == ["bob@example.com"]
    assert bob_house["members"][0]["is_instance_admin"] is False


async def test_admin_household_counts_exclude_soft_deleted_records(client):
    alice = await _register(client, "alice@example.com", "Alice's House")

    create_response = await client.post(
        "/api/v1/assets", headers=_headers(alice), json={"asset_type": "vehicle", "name": "Van"}
    )
    asset_id = create_response.json()["id"]
    await client.delete(f"/api/v1/assets/{asset_id}", headers=_headers(alice))

    response = await client.get("/api/v1/admin/households", headers=_headers(alice))
    household = response.json()[0]
    assert household["record_counts"]["assets"] == 0


async def test_promote_user_requires_instance_admin(client, db_session):
    await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()

    response = await client.post(f"/api/v1/admin/users/{bob_id}/promote", headers=_headers(bob))
    assert response.status_code == 403


async def test_admin_can_promote_another_user(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()

    response = await client.post(f"/api/v1/admin/users/{bob_id}/promote", headers=_headers(alice))
    assert response.status_code == 200
    assert response.json()["is_instance_admin"] is True

    result = await db_session.execute(select(User).where(User.email == "bob@example.com"))
    assert result.scalar_one().is_instance_admin is True


async def test_promote_unknown_user_404s(client):
    alice = await _register(client, "alice@example.com", "Alice's House")

    response = await client.post(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/promote", headers=_headers(alice)
    )
    assert response.status_code == 404


async def test_demote_user_requires_instance_admin(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    carol = await _register(client, "carol@example.com", "Carol's House")
    await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()
    await client.post(f"/api/v1/admin/users/{bob_id}/promote", headers=_headers(alice))

    # carol is neither bob nor an instance admin herself — shouldn't be able
    # to demote anyone.
    response = await client.post(f"/api/v1/admin/users/{bob_id}/demote", headers=_headers(carol))
    assert response.status_code == 403


async def test_admin_can_demote_another_admin(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()
    await client.post(f"/api/v1/admin/users/{bob_id}/promote", headers=_headers(alice))

    response = await client.post(f"/api/v1/admin/users/{bob_id}/demote", headers=_headers(alice))
    assert response.status_code == 200
    assert response.json()["is_instance_admin"] is False

    result = await db_session.execute(select(User).where(User.email == "bob@example.com"))
    assert result.scalar_one().is_instance_admin is False


async def test_cannot_demote_the_last_instance_admin(client):
    alice = await _register(client, "alice@example.com", "Alice's House")
    result = await client.get("/api/v1/admin/households", headers=_headers(alice))
    alice_id = result.json()[0]["members"][0]["user_id"]

    response = await client.post(f"/api/v1/admin/users/{alice_id}/demote", headers=_headers(alice))
    assert response.status_code == 400


async def test_demote_unknown_user_404s(client):
    alice = await _register(client, "alice@example.com", "Alice's House")

    response = await client.post(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/demote", headers=_headers(alice)
    )
    assert response.status_code == 404
