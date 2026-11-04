# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Baseline security response headers (2026-08-19 review, S7).

Defence-in-depth, not the primary control for anything: the attachment
content-type handling in api/v1/attachments.py is what actually stops an
uploaded file executing on our origin. These headers are the second line, so
that a miss elsewhere doesn't immediately become a working exploit.

Deliberately set here in the app rather than only at a reverse proxy — this
is self-hosted software, and a self-hoster's proxy config isn't something the
project can rely on. A proxy that sets its own values will simply override.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

# This API serves JSON and attachment blobs — never HTML documents, never
# scripts of its own. So the policy can be close to "deny everything": there
# is no legitimate script, style, or frame for a browser to load from this
# origin. It applies to attachment blobs, which is precisely where it
# matters (see attachments.py's _blob_response).
#
# NOTE: this covers responses from the API only. The web PWA is served
# separately (Vite in dev, see web/Dockerfile) and needs its own, much less
# restrictive policy — it legitimately loads scripts and a service worker.
# Do not copy this policy there.
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_HEADERS = {
    "Content-Security-Policy": _CSP,
    # Belt-and-braces with frame-ancestors above, for anything that predates
    # CSP support.
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # Deployments are expected behind TLS. Kept modest (1 year, no preload,
    # no includeSubDomains) since a self-hoster may well be running other
    # things on sibling subdomains that we shouldn't unilaterally opt in.
    "Strict-Transport-Security": "max-age=31536000",
}


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for header, value in _HEADERS.items():
        # setdefault semantics: a handler that deliberately set its own value
        # (attachments.py sets Content-Disposition/nosniff per-blob) wins.
        if header not in response.headers:
            response.headers[header] = value
    return response
