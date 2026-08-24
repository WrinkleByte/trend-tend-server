"""add row-level security for maintenance_categories

Mirrors f3d8a5c1e9b7_add_row_level_security_for_tenant_isolation.py's
policy exactly, for the new table added in e7c4b91a2f3d -- RLS enablement
is not automatic when a table is created, only the wrinklebyte_app
runtime role's DML grant is (via 95d3e5f4643e's ALTER DEFAULT PRIVILEGES).

Revision ID: b58f0d3e6a1c
Revises: e7c4b91a2f3d
Create Date: 2026-08-24 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b58f0d3e6a1c'
down_revision: Union[str, None] = 'e7c4b91a2f3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "maintenance_categories"
_POLICY_NAME = "household_isolation"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_POLICY_NAME} ON {_TABLE} "
        "USING ("
        "  current_setting('app.bypass_household_rls', true) = 'on'"
        "  OR household_id = current_setting('app.household_id', true)::uuid"
        ")"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY_NAME} ON {_TABLE}")
    op.execute(f"ALTER TABLE {_TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} DISABLE ROW LEVEL SECURITY")
