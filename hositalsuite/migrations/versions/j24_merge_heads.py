"""Merge heads: role management + TV volume

Revision ID: j24_merge
Revises: b9f42c7e1a80, i23
Create Date: 2026-08-22
This resolves the multiple-heads alembic error that made `alembic upgrade head`
skip and fall back to ensure_schema(), which left tables like `user` missing in
tests and caused OperationalError: no such table: user
"""
from alembic import op
import sqlalchemy as sa

revision = 'j24_merge'
down_revision = ('b9f42c7e1a80', 'i23')
branch_labels = None
depends_on = None

def upgrade():
    # Merge only — both branches already applied their own changes.
    # Ensure tv_screen.voice_volume exists even if one branch was skipped.
    try:
        bind = op.get_bind()
        insp = sa.inspect(bind)
        cols = [c['name'] for c in insp.get_columns('tv_screen')]
        if 'voice_volume' not in cols:
            op.add_column('tv_screen', sa.Column('voice_volume', sa.Integer(), nullable=True, server_default='100'))
    except Exception:
        pass

def downgrade():
    pass
