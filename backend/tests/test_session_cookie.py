# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""The web app's refresh token lives in an HttpOnly cookie, never in a
response body it could read (Vikunja #93). See app/core/session_cookie.py."""

from app.config import get_settings
from app.core.session_cookie import COOKIE_NAME, COOKIE_PATH

COOKIE_MODE = {"X-WrinkleByte-Session": "cookie"}
ALICE = {"email": "alice@example.com", "password": "correct horse battery staple"}


def _set_cookie_header(response) -> str:
    headers = [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]
    assert len(headers) == 1, headers
    return headers[0]


async def _login_cookie_mode(client):
    response = await client.post("/api/v1/auth/login", json=ALICE, headers=COOKIE_MODE)
    assert response.status_code == 200
    return response


async def test_cookie_mode_login_sets_httponly_cookie_and_hides_refresh_token(client, registered_user):
    response = await _login_cookie_mode(client)

    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"] is None, "the refresh token must never reach page script"
    cookie = _set_cookie_header(response).lower()
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert f"path={COOKIE_PATH}" in cookie
    assert "max-age=" in cookie
    # FRONTEND_URL is plain http in tests, so no Secure flag (a Secure cookie
    # would never come back over http).
    assert "secure" not in cookie.replace("samesite", "")


async def test_cookie_is_secure_when_the_site_is_https(client, registered_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "frontend_url", "https://tend.example.com")
    response = await _login_cookie_mode(client)
    assert "; secure" in _set_cookie_header(response).lower()


async def test_secure_flag_can_be_forced_off_behind_odd_proxies(client, registered_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "frontend_url", "https://tend.example.com")
    monkeypatch.setattr(get_settings(), "refresh_cookie_secure", "false")
    response = await _login_cookie_mode(client)
    assert "; secure" not in _set_cookie_header(response).lower()


async def test_refresh_from_cookie_rotates_it_and_never_returns_it_in_the_body(client, registered_user):
    await _login_cookie_mode(client)
    first = client.cookies.get(COOKIE_NAME)

    # No body at all, and no cookie-mode header either: a token that came from
    # the cookie is still only ever answered in cookie form.
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert response.json()["refresh_token"] is None
    rotated = client.cookies.get(COOKIE_NAME)
    assert rotated and rotated != first

    me = await client.get(
        "/api/v1/households/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.status_code == 200


async def test_replaying_an_old_cookie_still_revokes_the_family(client, registered_user):
    await _login_cookie_mode(client)
    first = client.cookies.get(COOKIE_NAME)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    # The thief replays the token they copied before it rotated.
    client.cookies.set(COOKIE_NAME, first, path=COOKIE_PATH)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    # ...which burns the whole family, including the real user's newer token.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_refresh_without_any_token_is_401(client):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_the_session_and_clears_the_cookie(client, registered_user):
    await _login_cookie_mode(client)
    stolen = client.cookies.get(COOKIE_NAME)

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert f'{COOKIE_NAME}=""' in _set_cookie_header(response) or "max-age=0" in _set_cookie_header(response).lower()

    # A copy taken before logout is dead too: logout ends the session on the
    # server, not just in the browser.
    client.cookies.set(COOKIE_NAME, stolen, path=COOKIE_PATH)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_with_no_or_garbage_token_is_still_204(client):
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set(COOKIE_NAME, "not-a-jwt", path=COOKIE_PATH)
    assert (await client.post("/api/v1/auth/logout")).status_code == 204


async def test_body_token_clients_keep_the_original_contract(client, registered_user):
    """Scripts and other non-browser clients: tokens in the body, no cookie."""
    login = await client.post("/api/v1/auth/login", json=ALICE)
    assert login.status_code == 200
    assert login.json()["refresh_token"]
    assert "set-cookie" not in {k.lower() for k in login.headers}

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"]


async def test_body_token_logout_revokes_it(client, registered_user):
    login = await client.post("/api/v1/auth/login", json=ALICE)
    token = login.json()["refresh_token"]
    assert (await client.post("/api/v1/auth/logout", json={"refresh_token": token})).status_code == 204
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": token})).status_code == 401


async def test_migrating_a_localstorage_token_moves_it_into_the_cookie(client, registered_user):
    """The web app's one-time upgrade: it posts the refresh token it used to
    keep in localStorage, in cookie mode, and from then on holds only the
    cookie."""
    legacy = registered_user["refresh_token"]
    assert legacy

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": legacy}, headers=COOKIE_MODE)
    assert response.status_code == 200
    assert response.json()["refresh_token"] is None
    assert client.cookies.get(COOKIE_NAME)

    # The localStorage copy is spent; only the cookie works now.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200


async def test_accepting_an_invite_in_cookie_mode_uses_a_tracked_cookie(client, auth_headers):
    invite = await client.post(
        "/api/v1/households/invites", headers=auth_headers, json={"invited_email": "bob@example.com"}
    )
    assert invite.status_code == 201
    bob = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": "another long passphrase",
            "display_name": "Bob",
            "household_name": "Bob's House",
        },
    )
    bob_access = bob.json()["access_token"]

    accepted = await client.post(
        "/api/v1/households/invites/accept",
        headers={"Authorization": f"Bearer {bob_access}", **COOKIE_MODE},
        json={"token": invite.json()["token"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["refresh_token"] is None
    issued = client.cookies.get(COOKIE_NAME)
    assert issued

    # Tracked (it has a jti), so logout can revoke it.
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set(COOKIE_NAME, issued, path=COOKIE_PATH)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
