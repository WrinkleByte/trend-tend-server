# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# The Trend & Tend Server image (wrinklebyte/trend-tend-server): the API and
# the web app (nginx) in one container, plus a built-in PostgreSQL for
# self-hosters who want a single `docker run`:
#
#   docker run -d --name trend-tend -p 8080:8080 \
#     -e FRONTEND_URL=http://<your-host>:8080 \
#     -v trend-tend:/data wrinklebyte/trend-tend-server
#
# Set DATABASE_URL and it uses that PostgreSQL instead and starts none of
# its own; docker-compose.prod.yml runs it that way next to the official
# postgres image. Everything else persistent lives in /data: attachments,
# generated secrets, and (built-in mode) the database. See
# aio/entrypoint.sh and the README's Self-hosting section.
#
# Build from the REPO ROOT (it needs both backend/ and web/):
#   docker build -f aio/Dockerfile -t trend-tend-server:dev .

# Postgres major version, pinned. The data directory is tied to it: the
# entrypoint refuses to start on a mismatch rather than let a newer server
# touch an older cluster. Changing this needs an upgrade path (aio/README.md).
ARG PG_MAJOR=16


FROM node:20-slim AS web
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build


# Built on the runtime base itself, so the virtualenv's interpreter path
# (/usr/bin/python3.11) exists in the final image. Debian bookworm's
# python3 is 3.11, matching backend/pyproject.toml's floor.
FROM postgres:${PG_MAJOR}-bookworm AS api
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /src
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .


FROM postgres:${PG_MAJOR}-bookworm AS runtime
ARG PG_MAJOR

ARG VERSION=dev
LABEL org.opencontainers.image.title="Trend & Tend Server" \
      org.opencontainers.image.description="Trend & Tend self-hosted server: the sync API and web app, with a built-in PostgreSQL or your own." \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.vendor="WrinkleByte LLC" \
      org.opencontainers.image.url="https://wrinklebyte.com" \
      org.opencontainers.image.source="https://github.com/wrinklebyte/trend-tend-server" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

# tini as PID 1 (started by the entrypoint after dropping root): reaps
# zombies and forwards signals to the entrypoint, which then stops nginx,
# the API and Postgres in order.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 nginx-light tini \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/*.conf \
    && mkdir -p /data /var/lib/nginx /var/log/nginx \
    && chown -R postgres:postgres /data /var/lib/nginx /var/log/nginx

ENV PATH="/opt/venv/bin:/usr/lib/postgresql/${PG_MAJOR}/bin:$PATH" \
    PG_MAJOR=${PG_MAJOR} \
    PGDATA=/data/postgres \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=api /opt/venv /opt/venv
WORKDIR /app
COPY --chown=postgres:postgres backend/alembic.ini ./
COPY --chown=postgres:postgres backend/alembic ./alembic
COPY --chown=postgres:postgres backend/app ./app
COPY --chown=postgres:postgres backend/scripts/__init__.py backend/scripts/reset_password.py ./scripts/
COPY --from=web /app/dist /usr/share/nginx/html

# The web image's server block, unchanged except that the API is on
# localhost instead of the Compose service name. The grep fails the build if
# the substitution ever stops matching, rather than shipping a proxy that
# points nowhere.
COPY web/nginx.conf /etc/nginx/trend-tend-site.conf
RUN sed -i 's#proxy_pass http://backend:8000;#proxy_pass http://127.0.0.1:8000;#' /etc/nginx/trend-tend-site.conf \
    && grep -q 'proxy_pass http://127.0.0.1:8000;' /etc/nginx/trend-tend-site.conf
COPY aio/nginx.conf /etc/nginx/nginx.conf
COPY --chmod=755 aio/entrypoint.sh /usr/local/bin/trend-tend-entrypoint
COPY --chmod=755 aio/reset-password.sh /usr/local/bin/trend-tend-reset-password

# The entrypoint starts as root only to fix ownership under /data, then
# drops to the image's unprivileged postgres user (uid 999) via gosu for
# everything it runs: Postgres refuses root anyway, nginx listens on 8080,
# and /data ends up owned by one predictable uid.
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python3", "-c", "import urllib.request,sys; ok=all(urllib.request.urlopen(u, timeout=4).status == 200 for u in ('http://127.0.0.1:8000/health','http://127.0.0.1:8080/')); sys.exit(0 if ok else 1)"]

ENTRYPOINT ["trend-tend-entrypoint"]
