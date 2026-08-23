from sqlalchemy import delete, select

from app.models.household import HouseholdMembership
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


async def test_admin_delete_household_requires_instance_admin(client):
    alice = await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")

    households = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    bob_household_id = next(h["id"] for h in households if h["name"] == "Bob's House")

    response = await client.delete(f"/api/v1/admin/households/{bob_household_id}", headers=_headers(bob))
    assert response.status_code == 403


async def test_admin_can_delete_any_household(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")
    await client.post("/api/v1/assets", headers=_headers(bob), json={"asset_type": "equipment", "name": "Mower"})

    households = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    bob_household_id = next(h["id"] for h in households if h["name"] == "Bob's House")

    response = await client.delete(f"/api/v1/admin/households/{bob_household_id}", headers=_headers(alice))
    assert response.status_code == 204

    remaining = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    assert [h["name"] for h in remaining] == ["Alice's House"]

    # bob's own session is dead now — his household is gone.
    bob_check = await client.get("/api/v1/assets", headers=_headers(bob))
    assert bob_check.status_code == 403


async def test_admin_delete_unknown_household_404s(client):
    alice = await _register(client, "alice@example.com", "Alice's House")

    response = await client.delete(
        "/api/v1/admin/households/00000000-0000-0000-0000-000000000000", headers=_headers(alice)
    )
    assert response.status_code == 404


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


async def test_list_users_requires_instance_admin(client):
    await _register(client, "alice@example.com", "Alice's House")
    bob = await _register(client, "bob@example.com", "Bob's House")

    response = await client.get("/api/v1/admin/users", headers=_headers(bob))
    assert response.status_code == 403


async def test_list_users_includes_orphaned_users_with_no_memberships(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()
    # Orphan bob directly at the DB layer -- the same state a stuck
    # accept-invite flow leaves a real account in (Vikunja #101), without
    # needing to reproduce that broken flow itself here.
    await db_session.execute(delete(HouseholdMembership).where(HouseholdMembership.user_id == bob_id))
    await db_session.commit()

    response = await client.get("/api/v1/admin/users", headers=_headers(alice))
    assert response.status_code == 200
    users_by_email = {u["email"]: u for u in response.json()}
    assert users_by_email["bob@example.com"]["memberships"] == []
    assert len(users_by_email["alice@example.com"]["memberships"]) == 1


async def _invite_and_join(client, owner_tokens: dict, invited_email: str, invited_password: str = "a very good password") -> dict:
    """Registers `invited_email` as a plain MEMBER of the owner's household
    via the real invite+register flow, distinct from _register (which
    always creates a brand-new household the caller OWNS) -- needed
    wherever a test wants a non-owner member to exercise purge/remove-
    membership's owner-safety checks against."""
    invite = await client.post(
        "/api/v1/households/invites", headers=_headers(owner_tokens), json={"invited_email": invited_email, "role": "member"}
    )
    assert invite.status_code == 201
    token = invite.json()["token"]
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": invited_email,
            "password": invited_password,
            "display_name": invited_email.split("@")[0],
            "invite_token": token,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_admin_can_purge_a_user(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _invite_and_join(client, alice, "bob@example.com")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()

    response = await client.delete(f"/api/v1/admin/users/{bob_id}", headers=_headers(alice))
    assert response.status_code == 204

    remaining = (await db_session.execute(select(User).where(User.id == bob_id))).scalar_one_or_none()
    assert remaining is None


async def test_purge_refuses_to_delete_yourself(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    alice_id = (await db_session.execute(select(User.id).where(User.email == "alice@example.com"))).scalar_one()

    response = await client.delete(f"/api/v1/admin/users/{alice_id}", headers=_headers(alice))
    assert response.status_code == 400


async def test_purge_refuses_a_household_owner(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _register(client, "carol@example.com", "Carol's House")
    carol_id = (await db_session.execute(select(User.id).where(User.email == "carol@example.com"))).scalar_one()

    # carol owns her own household, so alice (a different instance admin)
    # purging carol would leave that household's owner_user_id dangling --
    # refused with a clear reason instead.
    response = await client.delete(f"/api/v1/admin/users/{carol_id}", headers=_headers(alice))
    assert response.status_code == 409
    assert "Carol's House" in response.json()["detail"]


async def test_admin_can_reset_an_orphaned_user_by_adding_a_membership(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _register(client, "bob@example.com", "Bob's House")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()
    await db_session.execute(delete(HouseholdMembership).where(HouseholdMembership.user_id == bob_id))
    await db_session.commit()

    households = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    alice_household_id = next(h["id"] for h in households if h["name"] == "Alice's House")

    response = await client.post(
        f"/api/v1/admin/users/{bob_id}/memberships",
        headers=_headers(alice),
        json={"household_id": alice_household_id, "role": "member"},
    )
    assert response.status_code == 200
    assert response.json()["memberships"] == [
        {"household_id": alice_household_id, "household_name": "Alice's House", "role": "member"}
    ]

    # bob can log in again now that he has somewhere to go.
    login = await client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "a very good password"})
    assert login.status_code == 200


async def test_admin_can_remove_a_membership(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    await _invite_and_join(client, alice, "bob@example.com")
    bob_id = (await db_session.execute(select(User.id).where(User.email == "bob@example.com"))).scalar_one()

    households = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    alice_household_id = next(h["id"] for h in households if h["name"] == "Alice's House")

    response = await client.delete(
        f"/api/v1/admin/users/{bob_id}/memberships/{alice_household_id}", headers=_headers(alice)
    )
    assert response.status_code == 204

    login = await client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "a very good password"})
    assert login.status_code == 403  # no memberships left


async def test_remove_membership_refuses_to_strip_a_households_last_owner(client, db_session):
    alice = await _register(client, "alice@example.com", "Alice's House")
    alice_id = (await db_session.execute(select(User.id).where(User.email == "alice@example.com"))).scalar_one()

    households = (await client.get("/api/v1/admin/households", headers=_headers(alice))).json()
    alice_household_id = households[0]["id"]

    response = await client.delete(
        f"/api/v1/admin/users/{alice_id}/memberships/{alice_household_id}", headers=_headers(alice)
    )
    assert response.status_code == 400
