"""initial schema

Revision ID: e4ef24ae4574
Revises:
Create Date: 2026-08-03 12:47:26.082268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4ef24ae4574'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table order below is a manual topological sort — autogenerate's default
    # ordering doesn't respect FK dependencies once a circular pair (see the
    # maintenance_records <-> maintenance_schedules note below) is involved,
    # so it must be hand-verified rather than trusted as-is.

    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=True),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table('households',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('owner_user_id', sa.UUID(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('sync_devices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(length=20), nullable=False),
    sa.Column('device_name', sa.String(length=200), nullable=False),
    sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_sync_cursor', sa.String(length=500), nullable=True),
    sa.Column('conflict_resolution_mode', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sync_devices_household_id'), 'sync_devices', ['household_id'], unique=False)

    op.create_table('attachments',
    sa.Column('original_filename', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('storage_backend', sa.String(length=20), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('thumbnail_storage_key', sa.String(length=500), nullable=True),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('updated_by_device_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['updated_by_device_id'], ['sync_devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_household_id'), 'attachments', ['household_id'], unique=False)
    op.create_index(op.f('ix_attachments_sha256'), 'attachments', ['sha256'], unique=False)

    op.create_table('assets',
    sa.Column('asset_type', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('photo_attachment_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('purchase_date', sa.Date(), nullable=True),
    sa.Column('purchase_cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('updated_by_device_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['photo_attachment_id'], ['attachments.id'], ),
    sa.ForeignKeyConstraint(['updated_by_device_id'], ['sync_devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assets_asset_type'), 'assets', ['asset_type'], unique=False)
    op.create_index(op.f('ix_assets_household_id'), 'assets', ['household_id'], unique=False)

    op.create_table('maintenance_records',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('performed_at', sa.Date(), nullable=False),
    sa.Column('performed_by', sa.String(length=200), nullable=True),
    sa.Column('performed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('custom_category', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('odometer_reading', sa.Integer(), nullable=True),
    sa.Column('schedule_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('updated_by_device_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['performed_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by_device_id'], ['sync_devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # NOTE: schedule_id -> maintenance_schedules.id FK is added further below
    # via op.create_foreign_key, once that table exists — maintenance_records
    # and maintenance_schedules reference each other, so this can't be
    # expressed inline on either CREATE TABLE (see docs/architecture.md
    # Section 1).
    op.create_index(op.f('ix_maintenance_records_asset_id'), 'maintenance_records', ['asset_id'], unique=False)
    op.create_index(op.f('ix_maintenance_records_household_id'), 'maintenance_records', ['household_id'], unique=False)

    op.create_table('maintenance_schedules',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('interval_type', sa.String(length=10), nullable=False),
    sa.Column('interval_days', sa.Integer(), nullable=True),
    sa.Column('interval_usage_amount', sa.Integer(), nullable=True),
    sa.Column('usage_field', sa.String(length=50), nullable=True),
    sa.Column('anchor_date', sa.Date(), nullable=True),
    sa.Column('anchor_usage_value', sa.Integer(), nullable=True),
    sa.Column('last_completed_record_id', sa.UUID(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('updated_by_device_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['last_completed_record_id'], ['maintenance_records.id'], ),
    sa.ForeignKeyConstraint(['updated_by_device_id'], ['sync_devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_maintenance_schedules_asset_id'), 'maintenance_schedules', ['asset_id'], unique=False)
    op.create_index(op.f('ix_maintenance_schedules_household_id'), 'maintenance_schedules', ['household_id'], unique=False)

    op.create_foreign_key(
        'fk_maintenance_records_schedule_id',
        'maintenance_records', 'maintenance_schedules',
        ['schedule_id'], ['id'],
    )

    op.create_table('api_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('token_hash', sa.String(length=200), nullable=False),
    sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_tokens_household_id'), 'api_tokens', ['household_id'], unique=False)
    op.create_index(op.f('ix_api_tokens_token_hash'), 'api_tokens', ['token_hash'], unique=True)

    op.create_table('household_invites',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('invited_email', sa.String(length=320), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('token', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_household_invites_household_id'), 'household_invites', ['household_id'], unique=False)
    op.create_index(op.f('ix_household_invites_token'), 'household_invites', ['token'], unique=True)

    op.create_table('household_memberships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('household_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('invited_by_user_id', sa.UUID(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ),
    sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_household_memberships_household_id'), 'household_memberships', ['household_id'], unique=False)
    op.create_index(op.f('ix_household_memberships_user_id'), 'household_memberships', ['user_id'], unique=False)

    op.create_table('record_attachments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('record_id', sa.UUID(), nullable=False),
    sa.Column('attachment_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ),
    sa.ForeignKeyConstraint(['record_id'], ['maintenance_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_record_attachments_attachment_id'), 'record_attachments', ['attachment_id'], unique=False)
    op.create_index(op.f('ix_record_attachments_record_id'), 'record_attachments', ['record_id'], unique=False)

    op.create_table('equipment_details',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('manufacturer', sa.String(length=100), nullable=True),
    sa.Column('model_number', sa.String(length=100), nullable=True),
    sa.Column('serial_number', sa.String(length=100), nullable=True),
    sa.Column('warranty_expiration', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('asset_id')
    )

    op.create_table('property_details',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('parent_asset_id', sa.UUID(), nullable=True),
    sa.Column('install_date', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['parent_asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('asset_id')
    )

    op.create_table('vehicle_details',
    sa.Column('asset_id', sa.UUID(), nullable=False),
    sa.Column('vin', sa.String(length=17), nullable=True),
    sa.Column('make', sa.String(length=100), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('license_plate', sa.String(length=20), nullable=True),
    sa.Column('current_mileage', sa.Integer(), nullable=True),
    sa.Column('mileage_unit', sa.String(length=10), nullable=False),
    sa.Column('fuel_type', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('asset_id')
    )


def downgrade() -> None:
    op.drop_table('vehicle_details')
    op.drop_table('property_details')
    op.drop_table('equipment_details')
    op.drop_index(op.f('ix_record_attachments_record_id'), table_name='record_attachments')
    op.drop_index(op.f('ix_record_attachments_attachment_id'), table_name='record_attachments')
    op.drop_table('record_attachments')
    op.drop_index(op.f('ix_household_memberships_user_id'), table_name='household_memberships')
    op.drop_index(op.f('ix_household_memberships_household_id'), table_name='household_memberships')
    op.drop_table('household_memberships')
    op.drop_index(op.f('ix_household_invites_token'), table_name='household_invites')
    op.drop_index(op.f('ix_household_invites_household_id'), table_name='household_invites')
    op.drop_table('household_invites')
    op.drop_index(op.f('ix_api_tokens_token_hash'), table_name='api_tokens')
    op.drop_index(op.f('ix_api_tokens_household_id'), table_name='api_tokens')
    op.drop_table('api_tokens')
    op.drop_constraint('fk_maintenance_records_schedule_id', 'maintenance_records', type_='foreignkey')
    op.drop_index(op.f('ix_maintenance_schedules_household_id'), table_name='maintenance_schedules')
    op.drop_index(op.f('ix_maintenance_schedules_asset_id'), table_name='maintenance_schedules')
    op.drop_table('maintenance_schedules')
    op.drop_index(op.f('ix_maintenance_records_household_id'), table_name='maintenance_records')
    op.drop_index(op.f('ix_maintenance_records_asset_id'), table_name='maintenance_records')
    op.drop_table('maintenance_records')
    op.drop_index(op.f('ix_assets_household_id'), table_name='assets')
    op.drop_index(op.f('ix_assets_asset_type'), table_name='assets')
    op.drop_table('assets')
    op.drop_index(op.f('ix_attachments_sha256'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_household_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_index(op.f('ix_sync_devices_household_id'), table_name='sync_devices')
    op.drop_table('sync_devices')
    op.drop_table('households')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
