# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""add row-level security for tenant isolation (Vikunja #44)

Tenant isolation today is entirely structural: every household-scoped
query is supposed to go through household_scoped_query()/
verify_owned_reference() (app/api/deps.py), which is correct everywhere
as of the #32 fix -- but nothing at the database level would catch a
future endpoint that forgets. This adds that as defense-in-depth: a
Postgres RLS policy per household-scoped table, enforced even against a
query that never mentions household_id at all.

Scope is deliberately the six tables household_scoped_query() actually
covers (assets, attachments, fuel_logs, maintenance_records,
maintenance_schedules, trip_logs) -- NOT api_tokens/sync_devices/
household_memberships/household_invites/refresh_tokens. Those are
auth/session bootstrap tables looked up by token hash, user_id, or invite
token before a household_id is even known (get_current_principal's own
ApiToken lookup has to run *before* it can discover which household a
token belongs to), so RLS-gating them on household_id would make
authentication itself impossible to bootstrap.

**Not yet enforced**: this migration lays down the RLS policies below but
does NOT flip the app's DB role to non-superuser. Postgres refuses to
strip SUPERUSER from a cluster's *bootstrap* role under any circumstances,
and POSTGRES_USER in docker-compose.yml makes `wrinklebyte` exactly that
role -- so `ALTER ROLE wrinklebyte NOSUPERUSER` fails outright on every
deployment of this stack (self-hosted ones included), and a Postgres
superuser silently bypasses RLS regardless of policies. Real enforcement
needs a second, non-superuser role for runtime queries -- tracked as a
follow-up; this migration is written so that follow-up only needs to add
the role and repoint the app's connection, not touch the policies here.

Revision ID: f3d8a5c1e9b7
Revises: a1c3d8f6b2e4
Create Date: 2026-08-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3d8a5c1e9b7'
down_revision: Union[str, None] = 'a1c3d8f6b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HOUSEHOLD_SCOPED_TABLES = (
    "assets",
    "attachments",
    "fuel_logs",
    "maintenance_records",
    "maintenance_schedules",
    "trip_logs",
)

_POLICY_NAME = "household_isolation"


def upgrade() -> None:
    # NOTE: this migration deliberately does NOT strip SUPERUSER/BYPASSRLS
    # from _APP_ROLE anymore -- Postgres unconditionally refuses to remove
    # SUPERUSER from the cluster's *bootstrap* role ("permission denied to
    # alter role ... The bootstrap user must have the SUPERUSER attribute"),
    # and POSTGRES_USER in docker-compose.yml makes wrinklebyte exactly
    # that role on every fresh deployment of this stack, self-hosted ones
    # included. Real enforcement needs a second, non-superuser role for
    # runtime queries (tracked as a follow-up); this migration still lays
    # down the policies below so that follow-up has nothing left to do but
    # add the role and repoint the app's connection.
    for table in _HOUSEHOLD_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE is required in addition to ENABLE: Postgres exempts a
        # table's own OWNER from RLS by default even with policies
        # defined, and this role owns every table here (it ran every
        # earlier migration that created them). Without FORCE, the app's
        # own queries would still bypass RLS even after losing superuser.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {_POLICY_NAME} ON {table} "
            "USING ("
            "  current_setting('app.bypass_household_rls', true) = 'on'"
            "  OR household_id = current_setting('app.household_id', true)::uuid"
            ")"
        )


def downgrade() -> None:
    for table in _HOUSEHOLD_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_POLICY_NAME} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
