"""add valuable_details and asset_attachments

Revision ID: c1a7e3f92b48
Revises: d848a7618446
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a7e3f92b48'
down_revision: Union[str, None] = 'd848a7618446'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('valuable_details',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('manufacturer', sa.String(length=100), nullable=True),
    sa.Column('model_number', sa.String(length=100), nullable=True),
    sa.Column('serial_number', sa.String(length=100), nullable=True),
    sa.Column('warranty_expiration', sa.Date(), nullable=True),
    sa.Column('linked_property_asset_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['linked_property_asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('asset_attachments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('attachment_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_asset_attachments_asset_id'), 'asset_attachments', ['asset_id'], unique=False)
    op.create_index(op.f('ix_asset_attachments_attachment_id'), 'asset_attachments', ['attachment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_asset_attachments_attachment_id'), table_name='asset_attachments')
    op.drop_index(op.f('ix_asset_attachments_asset_id'), table_name='asset_attachments')
    op.drop_table('asset_attachments')
    op.drop_table('valuable_details')
