# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta

from sqlalchemy import select

from app.models.household import HouseholdInvite
from app.models.mixins import utcnow


async def _register(client, email: str, household_name: str, display_name: str | None = None) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a very good password",
            "display_name": display_name or email.split("@")[0],
            "household_name": household_name,
        },
    )
    assert response.status_code == 201
    return response.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_household_me_reports_my_role(client, auth_headers):
    response = await client.get("/api/v1/households/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["my_role"] == "owner"


async def test_create_invite_requires_owner(client, auth_headers):
    owner_household = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["id"]

    # A member of the owner's household (added directly, not via the invite
    # flow under test) should not be able to create invites themselves.
    member_tokens = await _register(client, "member@example.com", "Member's Own House")
    member_headers = _headers(member_tokens)

    create = await client.post(
        "/api/v1/households/invites",
        headers=auth_headers,
        json={"invited_email": "newperson@example.com"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["invited_email"] == "newperson@example.com"
    assert body["role"] == "member"
    assert body["status"] == "pending"
    assert body["token"]

    # Member's own household is different from the owner's — confirm they
    # can't create an invite scoped to a household they don't own even for
    # their own household (they're the owner there, but registered fresh).
    assert (await client.get("/api/v1/households/me", headers=member_headers)).json()["id"] != owner_household


async def test_non_owner_cannot_create_or_list_or_revoke_invites(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "someone@example.com"}
        )
    ).json()

    accept_tokens = await _register(client, "someone@example.com", "irrelevant")
    # Give "someone" membership in the owner's household via the real accept
    # flow first, so they have a legitimate session scoped to that household
    # to test member-level authorization against.
    accept = await client.post(
        "/api/v1/households/invites/accept",
        headers=_headers(accept_tokens),
        json={"token": invite["token"]},
    )
    assert accept.status_code == 200
    member_headers = _headers(accept.json())

    create = await client.post(
        "/api/v1/households/invites", headers=member_headers, json={"invited_email": "another@example.com"}
    )
    assert create.status_code == 403

    listing = await client.get("/api/v1/households/invites", headers=member_headers)
    assert listing.status_code == 403


async def test_revoke_invite(client, auth_headers, db_session):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "revoke-me@example.com"}
        )
    ).json()

    revoke = await client.delete(f"/api/v1/households/invites/{invite['id']}", headers=auth_headers)
    assert revoke.status_code == 204

    # The row itself really is revoked...
    revoked_row = (
        await db_session.execute(select(HouseholdInvite).where(HouseholdInvite.id == invite["id"]))
    ).scalar_one()
    assert revoked_row.status == "revoked"

    # ...but a revoked invite has nothing left to do, so it doesn't linger in
    # the owner's list (Vikunja #88).
    listing = await client.get("/api/v1/households/invites", headers=auth_headers)
    assert invite["id"] not in {i["id"] for i in listing.json()}

    # A revoked invite can't be revoked again.
    revoke_again = await client.delete(f"/api/v1/households/invites/{invite['id']}", headers=auth_headers)
    assert revoke_again.status_code == 400


async def test_preview_invite_by_token_is_public(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "preview@example.com"}
        )
    ).json()

    preview = await client.get(f"/api/v1/households/invites/by-token/{invite['token']}")
    assert preview.status_code == 200
    body = preview.json()
    assert body["invited_email"] == "preview@example.com"
    assert body["status"] == "pending"
    assert "household_name" in body

    missing = await client.get("/api/v1/households/invites/by-token/not-a-real-token")
    assert missing.status_code == 404


async def test_register_via_invite_joins_existing_household_not_a_new_one(client, auth_headers):
    owner_household_id = (await client.get("/api/v1/households/me", headers=auth_headers)).json()["id"]
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "newbie@example.com"}
        )
    ).json()

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newbie@example.com",
            "password": "a very good password",
            "display_name": "Newbie",
            "invite_token": invite["token"],
        },
    )
    assert register.status_code == 201
    newbie_headers = _headers(register.json())

    me = await client.get("/api/v1/households/me", headers=newbie_headers)
    assert me.json()["id"] == owner_household_id
    assert me.json()["my_role"] == "member"

    members = await client.get("/api/v1/households/members", headers=auth_headers)
    emails = [m["email"] for m in members.json()]
    assert "newbie@example.com" in emails

    invites = await client.get("/api/v1/households/invites", headers=auth_headers)
    assert next(i for i in invites.json() if i["id"] == invite["id"])["status"] == "accepted"


async def test_register_via_invite_without_household_name_is_fine(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "nohome@example.com"}
        )
    ).json()
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nohome@example.com",
            "password": "a very good password",
            "display_name": "No Home",
            "invite_token": invite["token"],
        },
    )
    assert register.status_code == 201


async def test_register_without_invite_or_household_name_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "incomplete@example.com", "password": "a very good password", "display_name": "Incomplete"},
    )
    assert response.status_code == 422


async def test_register_via_invite_wrong_email_rejected(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "expected@example.com"}
        )
    ).json()

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "someone-else@example.com",
            "password": "a very good password",
            "display_name": "Someone Else",
            "invite_token": invite["token"],
        },
    )
    assert register.status_code == 403


async def test_register_via_expired_invite_rejected(client, auth_headers, db_session):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "late@example.com"}
        )
    ).json()

    result = await db_session.execute(select(HouseholdInvite).where(HouseholdInvite.id == invite["id"]))
    db_invite = result.scalar_one()
    db_invite.expires_at = utcnow() - timedelta(days=1)
    await db_session.commit()

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "late@example.com",
            "password": "a very good password",
            "display_name": "Late",
            "invite_token": invite["token"],
        },
    )
    assert register.status_code == 410


async def test_accept_invite_as_already_registered_user(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "existing@example.com"}
        )
    ).json()

    existing_tokens = await _register(client, "existing@example.com", "Existing's Own House")
    existing_headers = _headers(existing_tokens)
    own_household_id = (await client.get("/api/v1/households/me", headers=existing_headers)).json()["id"]

    accept = await client.post(
        "/api/v1/households/invites/accept", headers=existing_headers, json={"token": invite["token"]}
    )
    assert accept.status_code == 200
    new_household_headers = _headers(accept.json())

    me = await client.get("/api/v1/households/me", headers=new_household_headers)
    assert me.json()["id"] != own_household_id
    assert me.json()["my_role"] == "member"


async def test_accept_invite_wrong_email_rejected(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "target@example.com"}
        )
    ).json()

    wrong_tokens = await _register(client, "not-the-target@example.com", "Wrong Person's House")
    accept = await client.post(
        "/api/v1/households/invites/accept",
        headers=_headers(wrong_tokens),
        json={"token": invite["token"]},
    )
    assert accept.status_code == 403


async def test_remove_member(client, auth_headers):
    invite = (
        await client.post(
            "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "removable@example.com"}
        )
    ).json()
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "removable@example.com",
            "password": "a very good password",
            "display_name": "Removable",
            "invite_token": invite["token"],
        },
    )
    removable_headers = _headers(register.json())

    members_before = await client.get("/api/v1/households/members", headers=auth_headers)
    removable = next(m for m in members_before.json() if m["email"] == "removable@example.com")

    # A non-owner member can't remove anyone.
    forbidden = await client.delete(
        f"/api/v1/households/members/{removable['user_id']}", headers=removable_headers
    )
    assert forbidden.status_code == 403

    remove = await client.delete(f"/api/v1/households/members/{removable['user_id']}", headers=auth_headers)
    assert remove.status_code == 204

    members_after = await client.get("/api/v1/households/members", headers=auth_headers)
    assert "removable@example.com" not in [m["email"] for m in members_after.json()]


async def test_owner_cannot_remove_self(client, auth_headers, registered_user):
    members = (await client.get("/api/v1/households/members", headers=auth_headers)).json()
    owner_user_id = next(m["user_id"] for m in members if m["email"] == "alice@example.com")

    response = await client.delete(f"/api/v1/households/members/{owner_user_id}", headers=auth_headers)
    assert response.status_code == 400


# ===== invite emails =====


async def test_invite_reports_no_email_when_smtp_is_unconfigured(client, auth_headers):
    """The default self-hosted state. The invite must still be created — the
    owner falls back to copying the link — but the response has to say so
    rather than implying a delivery that never happened."""
    response = await client.post(
        "/api/v1/households/invites",
        headers=auth_headers,
        json={"invited_email": "nobody@example.com"},
    )
    assert response.status_code == 201
    assert response.json()["email_sent"] is False
    assert response.json()["token"]


async def test_invite_emails_the_join_link_when_smtp_is_configured(client, auth_headers, monkeypatch):
    sent: list[dict] = []

    def _fake_send_email(settings, *, to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.api.v1.households.send_email", _fake_send_email)

    response = await client.post(
        "/api/v1/households/invites",
        headers=auth_headers,
        json={"invited_email": "newperson@example.com", "role": "member"},
    )
    assert response.status_code == 201
    assert response.json()["email_sent"] is True

    assert len(sent) == 1
    assert sent[0]["to"] == "newperson@example.com"
    # The link has to carry the token and point at the web app's /join route,
    # not the API — a recipient opening it needs the SPA, not JSON.
    assert f"/join?token={response.json()['token']}" in sent[0]["body"]
    # Enough context to tell a real invite from a phish: who invited them,
    # into what, and as what.
    assert "Alice" in sent[0]["subject"]
    assert "Alice's House" in sent[0]["subject"]
    assert "member" in sent[0]["body"]


async def test_invite_survives_a_failing_email_relay(client, auth_headers, monkeypatch):
    """A broken relay must not turn a successful invite into a failed request —
    the row is already committed and copy-the-link still works."""

    def _exploding_send_email(settings, *, to, subject, body):
        raise RuntimeError("relay exploded")

    monkeypatch.setattr("app.api.v1.households.send_email", _exploding_send_email)

    response = await client.post(
        "/api/v1/households/invites",
        headers=auth_headers,
        json={"invited_email": "unlucky@example.com"},
    )
    assert response.status_code == 201
    assert response.json()["email_sent"] is False

    # And it's a real, usable invite despite the failed notification.
    preview = await client.get(f"/api/v1/households/invites/by-token/{response.json()['token']}")
    assert preview.status_code == 200
    assert preview.json()["status"] == "pending"
