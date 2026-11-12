# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""App-only family members, and pairing keys an owner or instance admin
issues for someone else (Vikunja #165). A device paired with such a key must
act as the member it was issued to, never as the person who issued it."""

from app.core.api_token_issuing import APP_ONLY_EMAIL_DOMAIN


async def _register(client, email: str, household_name: str, name: str = "User") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": name,
            "household_name": household_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _add_member(client, owner_headers, **body) -> dict:
    response = await client.post("/api/v1/households/members", headers=owner_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _member_key(client, owner_headers, user_id: str, name: str = "Kate's iPhone") -> dict:
    response = await client.post(
        f"/api/v1/households/members/{user_id}/api-tokens", headers=owner_headers, json={"name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_owner_adds_app_only_member_without_email(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    assert kate["display_name"] == "Kate"
    assert kate["role"] == "member"
    assert kate["email"] == ""  # the placeholder address is never shown
    assert kate["has_login"] is False

    members = (await client.get("/api/v1/households/members", headers=auth_headers)).json()
    by_name = {m["display_name"]: m for m in members}
    assert by_name["Kate"]["has_login"] is False
    assert by_name["Alice"]["has_login"] is True


async def test_app_only_member_cannot_sign_in(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    placeholder = f"member-{kate['user_id'].replace('-', '')}@{APP_ONLY_EMAIL_DOMAIN}"
    response = await client.post("/api/v1/auth/login", json={"email": placeholder, "password": ""})
    assert response.status_code in (401, 422)


async def test_member_with_real_email_keeps_it(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate", email="kate@example.com")
    assert kate["email"] == "kate@example.com"
    assert kate["has_login"] is False


async def test_adding_member_with_an_existing_accounts_email_is_refused(client, auth_headers):
    await _register(client, "bob@example.com", "Bob's House", "Bob")
    response = await client.post(
        "/api/v1/households/members",
        headers=auth_headers,
        json={"display_name": "Bob", "email": "bob@example.com"},
    )
    assert response.status_code == 409


async def test_member_key_acts_as_the_member_not_the_owner(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    key = await _member_key(client, auth_headers, kate["user_id"])
    assert key["token"]

    me = await client.get("/api/v1/households/me", headers=_headers(key["token"]))
    assert me.status_code == 200
    assert me.json()["my_user_id"] == kate["user_id"]
    assert me.json()["my_role"] == "member"


async def test_member_sees_who_made_their_key(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    key = await _member_key(client, auth_headers, kate["user_id"])

    own_list = (await client.get("/api/v1/api-tokens", headers=_headers(key["token"]))).json()
    assert len(own_list) == 1
    assert own_list[0]["created_by_name"] == "Alice"
    assert own_list[0]["created_by_user_id"] is not None

    owner_view = (
        await client.get(f"/api/v1/households/members/{kate['user_id']}/api-tokens", headers=auth_headers)
    ).json()
    assert [t["id"] for t in owner_view] == [key["id"]]


async def test_own_keys_have_no_creator(client, auth_headers):
    await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "My phone"})
    listed = (await client.get("/api/v1/api-tokens", headers=auth_headers)).json()
    assert listed[0]["created_by_user_id"] is None
    assert listed[0]["created_by_name"] is None


async def test_owner_revokes_member_key(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    key = await _member_key(client, auth_headers, kate["user_id"])

    revoke = await client.delete(
        f"/api/v1/households/members/{kate['user_id']}/api-tokens/{key['id']}", headers=auth_headers
    )
    assert revoke.status_code == 204
    again = await client.delete(
        f"/api/v1/households/members/{kate['user_id']}/api-tokens/{key['id']}", headers=auth_headers
    )
    assert again.status_code == 204  # idempotent

    response = await client.get("/api/v1/households/me", headers=_headers(key["token"]))
    assert response.status_code == 401


async def test_non_owner_cannot_issue_keys_or_add_members(client, auth_headers, registered_user):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    kate_key = (await _member_key(client, auth_headers, kate["user_id"]))["token"]
    owner_id = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["my_user_id"]

    response = await client.post(
        f"/api/v1/households/members/{owner_id}/api-tokens", headers=_headers(kate_key), json={"name": "x"}
    )
    assert response.status_code == 403
    response = await client.post(
        "/api/v1/households/members", headers=_headers(kate_key), json={"display_name": "Sneaky"}
    )
    assert response.status_code == 403


async def test_owner_cannot_issue_key_for_someone_outside_the_household(client, auth_headers):
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_id = (await client.get("/api/v1/households/me", headers=_headers(bob["access_token"]))).json()[
        "my_user_id"
    ]
    response = await client.post(
        f"/api/v1/households/members/{bob_id}/api-tokens", headers=auth_headers, json={"name": "x"}
    )
    assert response.status_code == 404
    response = await client.get(f"/api/v1/households/members/{bob_id}/api-tokens", headers=auth_headers)
    assert response.status_code == 404


async def test_owner_cannot_revoke_another_households_key(client, auth_headers):
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_headers = _headers(bob["access_token"])
    bob_id = (await client.get("/api/v1/households/me", headers=bob_headers)).json()["my_user_id"]
    bob_key = (await client.post("/api/v1/api-tokens", headers=bob_headers, json={"name": "phone"})).json()

    response = await client.delete(
        f"/api/v1/households/members/{bob_id}/api-tokens/{bob_key['id']}", headers=auth_headers
    )
    assert response.status_code == 404
    still_works = await client.get("/api/v1/households/me", headers=_headers(bob_key["token"]))
    assert still_works.status_code == 200


async def test_instance_admin_issues_key_in_any_household(client, auth_headers):
    # Alice registered first, so she's the instance admin; Bob's household is
    # one she isn't in.
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_headers = _headers(bob["access_token"])
    bob_me = (await client.get("/api/v1/households/me", headers=bob_headers)).json()

    response = await client.post(
        f"/api/v1/admin/users/{bob_me['my_user_id']}/api-tokens",
        headers=auth_headers,
        json={"name": "Bob's tablet", "household_id": bob_me["id"]},
    )
    assert response.status_code == 201, response.text
    key = response.json()

    me = await client.get("/api/v1/households/me", headers=_headers(key["token"]))
    assert me.json()["my_user_id"] == bob_me["my_user_id"]

    listed = (await client.get(f"/api/v1/admin/users/{bob_me['my_user_id']}/api-tokens", headers=auth_headers)).json()
    assert listed[0]["household_id"] == bob_me["id"]
    assert listed[0]["created_by_name"] == "Alice"

    revoke = await client.delete(
        f"/api/v1/admin/users/{bob_me['my_user_id']}/api-tokens/{key['id']}", headers=auth_headers
    )
    assert revoke.status_code == 204
    assert (await client.get("/api/v1/households/me", headers=_headers(key["token"]))).status_code == 401


async def test_admin_key_needs_a_real_membership(client, auth_headers):
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_id = (await client.get("/api/v1/households/me", headers=_headers(bob["access_token"]))).json()[
        "my_user_id"
    ]
    alice_household = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["id"]

    response = await client.post(
        f"/api/v1/admin/users/{bob_id}/api-tokens",
        headers=auth_headers,
        json={"name": "x", "household_id": alice_household},
    )
    assert response.status_code == 404


async def test_only_instance_admins_use_the_admin_key_endpoint(client, auth_headers):
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_headers = _headers(bob["access_token"])
    bob_me = (await client.get("/api/v1/households/me", headers=bob_headers)).json()
    response = await client.post(
        f"/api/v1/admin/users/{bob_me['my_user_id']}/api-tokens",
        headers=bob_headers,
        json={"name": "x", "household_id": bob_me["id"]},
    )
    assert response.status_code == 403


async def test_owner_assigns_own_key_to_member(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    key = (await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPad"})).json()

    response = await client.patch(
        f"/api/v1/api-tokens/{key['id']}", headers=auth_headers, json={"user_id": kate["user_id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["created_by_name"] == "Alice"

    # The same raw key now acts as Kate, no re-pairing.
    me = (await client.get("/api/v1/households/me", headers=_headers(key["token"]))).json()
    assert me["my_user_id"] == kate["user_id"]

    mine = (await client.get("/api/v1/api-tokens", headers=auth_headers)).json()
    assert key["id"] not in [t["id"] for t in mine]
    hers = (
        await client.get(f"/api/v1/households/members/{kate['user_id']}/api-tokens", headers=auth_headers)
    ).json()
    assert [t["id"] for t in hers] == [key["id"]]


async def test_assigning_back_to_the_owner_clears_created_by(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    owner_id = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["my_user_id"]
    key = await _member_key(client, auth_headers, kate["user_id"])

    response = await client.patch(f"/api/v1/api-tokens/{key['id']}", headers=auth_headers, json={"user_id": owner_id})
    assert response.status_code == 200
    assert response.json()["created_by_user_id"] is None


async def test_member_cannot_assign_keys(client, auth_headers):
    kate = await _add_member(client, auth_headers, display_name="Kate")
    owner_id = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["my_user_id"]
    kate_key = await _member_key(client, auth_headers, kate["user_id"])
    response = await client.patch(
        f"/api/v1/api-tokens/{kate_key['id']}", headers=_headers(kate_key["token"]), json={"user_id": owner_id}
    )
    assert response.status_code == 403


async def test_cannot_assign_to_a_non_member_or_a_revoked_or_foreign_key(client, auth_headers):
    bob = await _register(client, "bob@example.com", "Bob's House", "Bob")
    bob_headers = _headers(bob["access_token"])
    bob_id = (await client.get("/api/v1/households/me", headers=bob_headers)).json()["my_user_id"]
    kate = await _add_member(client, auth_headers, display_name="Kate")
    key = (await client.post("/api/v1/api-tokens", headers=auth_headers, json={"name": "iPad"})).json()

    to_outsider = await client.patch(f"/api/v1/api-tokens/{key['id']}", headers=auth_headers, json={"user_id": bob_id})
    assert to_outsider.status_code == 404

    bob_key = (await client.post("/api/v1/api-tokens", headers=bob_headers, json={"name": "phone"})).json()
    foreign = await client.patch(
        f"/api/v1/api-tokens/{bob_key['id']}", headers=auth_headers, json={"user_id": kate["user_id"]}
    )
    assert foreign.status_code == 404

    await client.delete(f"/api/v1/api-tokens/{key['id']}", headers=auth_headers)
    revoked = await client.patch(
        f"/api/v1/api-tokens/{key['id']}", headers=auth_headers, json={"user_id": kate["user_id"]}
    )
    assert revoked.status_code == 409
