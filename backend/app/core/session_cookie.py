# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""The web app's refresh token lives in an HttpOnly cookie (Vikunja #93).

Before this, the web app kept both tokens in localStorage, where any script
on the page could read them: one XSS bug and the 30-day refresh token walks
off with the user's session, surviving even "Log out". In cookie mode:

* the refresh token is set as an HttpOnly cookie scoped to the auth
  endpoints, and is **never** returned in a response body, so page script
  cannot read it;
* the access token (15 minutes) is returned in the body and kept in memory
  only, so a page reload restores the session by calling /auth/refresh.

A client opts in with the `X-WrinkleByte-Session: cookie` request header,
which the web app sends on every request. Everything else (scripts, older
clients) keeps the original contract: both tokens in the body, refresh
token posted back in the body. The mobile apps are unaffected either way:
they sync with API keys, not these tokens.

CSRF: the cookie is SameSite=Strict and only ever sent to /api/v1/auth/*,
where the worst a forged cross-site request could do is rotate the token
(its response is unreadable cross-origin) or log the user out.
"""

from __future__ import annotations

from fastapi import Request, Response

from app.config import get_settings

COOKIE_NAME = "wb_refresh"
COOKIE_PATH = "/api/v1/auth"
SESSION_HEADER = "x-wrinklebyte-session"


def wants_cookie(request: Request) -> bool:
    return request.headers.get(SESSION_HEADER, "").lower() == "cookie"


def cookie_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME) or None


def _secure() -> bool:
    """Mark the cookie Secure when the site is served over HTTPS.

    Decided from the configured public URL rather than the request: inside
    the single-container image nginx overwrites X-Forwarded-Proto with its
    own scheme, so behind a TLS-terminating proxy every request looks like
    plain http. REFRESH_COOKIE_SECURE=true|false overrides. A Secure cookie
    on a plain-http LAN install would never be sent back, so that case must
    stay unsecured; SameSite and HttpOnly still apply.
    """
    settings = get_settings()
    override = (settings.refresh_cookie_secure or "").strip().lower()
    if override in ("true", "1", "yes"):
        return True
    if override in ("false", "0", "no"):
        return False
    return settings.frontend_url.lower().startswith("https://")


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=get_settings().jwt_refresh_token_ttl_days * 86400,
        path=COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        samesite="strict",
    )
