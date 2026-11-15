# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""What this server can do, for clients that run against many server versions.

The mobile apps are in the app stores and servers are self-hosted, so any app
version can meet any server version. GET /api/v1/meta lists these
capabilities so an app can show, hide or explain a feature depending on
whether this server supports it, instead of letting an older server silently
drop data it doesn't understand.

Rules (see internal compatibility rules; summarised here for contributors):

* Add a capability in the same change that adds the feature, named after the
  feature, lowercase, dot-separated (``profile.display_name``).
* **Never remove or rename one** while the API is ``/api/v1``: an app that
  checks for it would lose the feature. A breaking change means ``/api/v2``.
* A capability only ever *enables* client behaviour. Clients treat a server
  that has no /api/v1/meta at all (anything before 1.4.0) as "unknown" and
  keep their pre-negotiation behaviour, never as "supports nothing".
"""

# The /api/v1 contract version. Bumped only together with a new /api/vN.
API_VERSION = 1

CAPABILITIES: tuple[str, ...] = (
    # 1.2.0: household members without a web login, keys created for them by
    # an owner, and key reassignment between members.
    "family_members",
    # 1.2.0: assets.sale_price / sale_date, over REST and sync.
    "sale_price",
    # 1.3.0: the web app's refresh token as an HttpOnly cookie, /auth/logout.
    "web_session_cookie",
    # 1.4.0: this endpoint, and logging of X-WrinkleByte-Client.
    "meta",
)
