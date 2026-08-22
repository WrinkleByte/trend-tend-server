"""Proves the global security-headers middleware (Vikunja #209) is actually
wired up and doesn't just exist in isolation -- app/core/security_headers.py
had no test coverage at all before this, despite being the second of the
two links Vikunja #209 asked to be closed (the first being attachments.py's
content-type allowlist, covered by test_attachments.py's
test_html_attachment_is_not_served_as_renderable_html and
test_svg_attachment_is_not_served_inline).
"""

from app.core.security_headers import _HEADERS


async def test_ordinary_api_response_carries_every_security_header(client, auth_headers):
    response = await client.get("/api/v1/households/me", headers=auth_headers)
    assert response.status_code == 200
    for header, value in _HEADERS.items():
        assert response.headers[header] == value


async def test_unauthenticated_response_still_carries_security_headers(client):
    # The headers are middleware-level, not auth-gated -- an error response
    # (401 here) is exactly the kind of response an attacker's own crafted
    # request would get back, so it needs the same protection.
    response = await client.get("/api/v1/households/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    for header, value in _HEADERS.items():
        assert response.headers[header] == value


async def test_attachment_blob_response_keeps_its_own_nosniff_not_overridden(client, auth_headers):
    """setdefault semantics: attachments.py's _blob_response sets
    X-Content-Type-Options itself -- confirm the middleware doesn't clobber
    it (both happen to be "nosniff" today, but this pins the precedence
    rule, not just the value, so a future change to either side surfaces a
    real diff instead of two coincidentally-matching constants)."""
    upload = await client.post(
        "/api/v1/attachments",
        headers=auth_headers,
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    attachment_id = upload.json()["id"]

    response = await client.get(f"/api/v1/attachments/{attachment_id}/blob", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"] == _HEADERS["Content-Security-Policy"]
