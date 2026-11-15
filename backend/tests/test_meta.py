# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""GET /api/v1/meta and the X-WrinkleByte-Client header (capability
negotiation between independently-updated apps and servers)."""

import logging
import re

from app.core import client_version
from app.core.capabilities import API_VERSION, CAPABILITIES
from app.core.version import APP_VERSION

# Capabilities that clients in the field may already check for. Removing or
# renaming any of these breaks those clients, so this list only ever grows.
# If this test fails because you removed one: don't; that needs /api/v2.
SHIPPED_CAPABILITIES = {
    "family_members",
    "sale_price",
    "web_session_cookie",
    "meta",
    "profile_display_name",
}


async def test_meta_needs_no_sign_in_and_describes_the_server(client):
    response = await client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "server_version": APP_VERSION,
        "api_version": API_VERSION,
        "capabilities": list(CAPABILITIES),
    }
    assert body["api_version"] == 1


async def test_shipped_capabilities_are_never_removed():
    assert SHIPPED_CAPABILITIES <= set(CAPABILITIES)


async def test_capability_names_are_unique_and_well_formed():
    assert len(CAPABILITIES) == len(set(CAPABILITIES))
    for name in CAPABILITIES:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", name), name


async def test_client_header_is_logged_once_and_never_rejected(
    client, caplog, auth_headers
):
    client_version._seen.clear()
    caplog.set_level(logging.INFO, logger="app.core.client_version")
    headers = {**auth_headers, "X-WrinkleByte-Client": "ios/1.3.0 (11)"}
    for _ in range(3):
        assert (
            await client.get("/api/v1/households/me", headers=headers)
        ).status_code == 200
    assert [r.getMessage() for r in caplog.records].count(
        "client seen: 'ios/1.3.0 (11)'"
    ) == 1


async def test_odd_client_headers_are_harmless(client, auth_headers):
    client_version._seen.clear()
    # (CR/LF and non-ASCII can't be tested here: httpx refuses to send them.)
    for value in ["", "x" * 5000, "android/1.2.0 (7); extra", "not/a version at all"]:
        response = await client.get(
            "/api/v1/households/me",
            headers={**auth_headers, "X-WrinkleByte-Client": value},
        )
        assert response.status_code == 200
    assert all(len(v) <= 100 for v in client_version._seen)


async def test_requests_without_the_header_work_exactly_as_before(client, auth_headers):
    assert (
        await client.get("/api/v1/households/me", headers=auth_headers)
    ).status_code == 200
    assert (await client.get("/health")).json()["version"] == APP_VERSION
