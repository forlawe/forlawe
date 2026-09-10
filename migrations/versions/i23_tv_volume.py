"""TV volume slider per TV

Revision ID: i23
Revises: h22
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'i23'
down_revision = 'h22'
branch_labels = None
depends_on = None


def upgrade():
    # FIX 2026-09-04: idempotent — check existence before ALTER, avoids
    # "already exists" aborting the transaction and breaking subsequent upgrades
    # (Supabase 424GB egress / InFailedSqlTransaction).
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'tv_screen' not in insp.get_table_names():
        return
    cols = [c['name'] for c in insp.get_columns('tv_screen')]
    if 'voice_volume' not in cols:
        op.add_column('tv_screen', sa.Column('voice_volume', sa.Integer(), nullable=True, server_default='100'))


def downgrade():
    try:
        op.drop_column('tv_screen', 'voice_volume')
    except Exception:
        pass
