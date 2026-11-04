# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.security_headers import security_headers_middleware

# Without this, the root logger's default WARNING level silently drops our
# app.* loggers' INFO calls (e.g. core/email.py's "SMTP not configured —
# skipping send") before they reach a handler — uvicorn only configures its
# own uvicorn.*/uvicorn.access loggers, not root or ours.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# No CORSMiddleware -- deliberate, not an oversight (Vikunja #213). Every
# supported deployment topology serves the web app and this API from the
# same origin: the bundled docker-compose dev stack proxies /api/* through
# Vite (web/vite.config.ts) to the backend container, and a self-hosted
# production instance is expected to do the same via its own reverse proxy
# (see security_headers.py's docstring for the same assumption). Browsers
# already block cross-origin requests by default with no CORS headers
# present at all, so leaving this middleware out *is* the deny-by-default
# policy, not an accidental gap. If a future deployment shape genuinely
# needs the web app served from a different origin than the API, add
# CORSMiddleware with an explicit, narrow allowed-origins list then --
# don't add it speculatively now for a topology nothing actually uses.
try:
    # pyproject.toml is the one place the version is set; the release
    # images, the OpenAPI doc and /health all read it from there.
    APP_VERSION = version("wrinklebyte-backend")
except PackageNotFoundError:  # running from a source tree that was never pip-installed
    APP_VERSION = "0.0.0+source"

app = FastAPI(title="WrinkleByte API", version=APP_VERSION)
app.middleware("http")(security_headers_middleware)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    # The version lets a self-hoster (or support) confirm which release is
    # actually running after an upgrade, without shelling into a container.
    return {"status": "ok", "version": APP_VERSION}
