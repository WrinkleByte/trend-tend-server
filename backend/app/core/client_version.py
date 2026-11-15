# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Note which app versions talk to this server.

The mobile apps (from 1.3) send ``X-WrinkleByte-Client: ios/1.3.0 (11)``. This
logs each distinct value once per process, so an operator can see which app
versions are in use before changing anything they might rely on. It never
rejects a request: an absent, unknown or malformed header is fine.
"""

import logging

from fastapi import Request

logger = logging.getLogger(__name__)

HEADER = "x-wrinklebyte-client"
_MAX_LEN = 100
_MAX_REMEMBERED = 200
_seen: set[str] = set()


async def client_version_middleware(request: Request, call_next):
    value = request.headers.get(HEADER)
    if value:
        value = value.strip()[:_MAX_LEN]
        if value not in _seen and len(_seen) < _MAX_REMEMBERED:
            _seen.add(value)
            # repr() so control characters in a hostile header can't forge log lines.
            logger.info("client seen: %r", value)
    return await call_next(request)
