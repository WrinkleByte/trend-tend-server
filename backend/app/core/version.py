# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from importlib.metadata import PackageNotFoundError, version

try:
    # pyproject.toml is the one place the version is set; the release
    # images, the OpenAPI doc, /health and /api/v1/meta all read it from here.
    APP_VERSION = version("wrinklebyte-backend")
except PackageNotFoundError:  # running from a source tree that was never pip-installed
    APP_VERSION = "0.0.0+source"
