"""
initial: payments and outbox tables

Revision ID: 0001
Revises:
Create Date: 2026-06-22 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('webhook_url', sa.String(length=2048), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_payments_idempotency_key'),
    )
    op.create_index('ix_payments_status', 'payments', ['status'])
    op.create_index(
        'ix_payments_idempotency_key', 'payments', ['idempotency_key'],
    )

    op.create_table(
        'outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('routing_key', sa.String(length=255), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_outbox_unpublished', 'outbox', ['published_at', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_outbox_unpublished', table_name='outbox')
    op.drop_table('outbox')
    op.drop_index('ix_payments_idempotency_key', table_name='payments')
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_table('payments')
