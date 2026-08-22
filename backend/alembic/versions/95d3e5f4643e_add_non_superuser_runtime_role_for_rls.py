"""add non-superuser runtime role for RLS enforcement (Vikunja #44)

f3d8a5c1e9b7 laid down RLS policies on the household-scoped tables but
couldn't make them actually enforce anything: it tried to strip
SUPERUSER/BYPASSRLS from `wrinklebyte`, the role docker-compose.yml's
POSTGRES_USER bootstraps -- and Postgres unconditionally refuses to ever
remove SUPERUSER from a cluster's *bootstrap* role. That ALTER ROLE
crashed the backend on every startup when first applied (permission
denied to alter role ... "The bootstrap user must have the SUPERUSER
attribute"); f3d8a5c1e9b7 was patched afterward to drop that step, which
restored the backend but left RLS dormant -- `wrinklebyte` is still a
superuser, and a superuser silently bypasses RLS no matter how many
policies exist.

This migration creates a SEPARATE, genuinely non-superuser role
(`wrinklebyte_app`) for the app's runtime queries -- migrations keep
running as `wrinklebyte`, which is fine, since DDL isn't tenant-scoped.
Grants exactly the DML the app needs (no CREATEDB/CREATEROLE/REPLICATION),
plus default privileges so tables created by future migrations
automatically grant to it without a repeat of this migration.

**Opt-in, not required**: if the APP_DB_PASSWORD environment variable
isn't set, this migration does nothing (not even create the role) rather
than fail -- an instance that hasn't configured the separate role yet
keeps working exactly as before (RLS still dormant), instead of the
backend crash-looping the way f3d8a5c1e9b7 did on its first attempt. Set
APP_DB_PASSWORD (and app/config.py's RUNTIME_DATABASE_URL to a connection
string using it) to actually turn enforcement on.

Revision ID: 95d3e5f4643e
Revises: f3d8a5c1e9b7
Create Date: 2026-08-22 11:30:00.000000

"""
import os
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '95d3e5f4643e'
down_revision: str | None = 'f3d8a5c1e9b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RUNTIME_ROLE = "wrinklebyte_app"
_MIGRATION_ROLE = "wrinklebyte"
_DATABASE_NAME = "wrinklebyte"


def upgrade() -> None:
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        return

    # Postgres DDL can't bind parameters the way DML can (same reason
    # app/db/rls.py uses set_config() instead of parameterized SET LOCAL
    # for GUCs) -- escape the literal by doubling embedded single quotes,
    # the standard SQL-string-literal escape, rather than string-format it
    # unescaped.
    escaped_password = password.replace("'", "''")

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{_RUNTIME_ROLE}') THEN
                CREATE ROLE {_RUNTIME_ROLE} LOGIN PASSWORD '{escaped_password}'
                    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
            ELSE
                ALTER ROLE {_RUNTIME_ROLE} LOGIN PASSWORD '{escaped_password}'
                    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT CONNECT ON DATABASE {_DATABASE_NAME} TO {_RUNTIME_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_RUNTIME_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {_RUNTIME_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_RUNTIME_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {_MIGRATION_ROLE} IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_RUNTIME_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {_MIGRATION_ROLE} IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {_RUNTIME_ROLE}"
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{_RUNTIME_ROLE}') THEN
                ALTER DEFAULT PRIVILEGES FOR ROLE {_MIGRATION_ROLE} IN SCHEMA public
                    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {_RUNTIME_ROLE};
                ALTER DEFAULT PRIVILEGES FOR ROLE {_MIGRATION_ROLE} IN SCHEMA public
                    REVOKE USAGE, SELECT ON SEQUENCES FROM {_RUNTIME_ROLE};
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {_RUNTIME_ROLE};
                REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {_RUNTIME_ROLE};
                REVOKE USAGE ON SCHEMA public FROM {_RUNTIME_ROLE};
                REVOKE CONNECT ON DATABASE {_DATABASE_NAME} FROM {_RUNTIME_ROLE};
                DROP OWNED BY {_RUNTIME_ROLE};
                DROP ROLE {_RUNTIME_ROLE};
            END IF;
        END
        $$;
        """
    )
