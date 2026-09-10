"""TV screens - multiple TVs, waiting area shows more, Nigeria voices

Revision ID: h22
Revises: g8h21
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'h22'
down_revision = 'g8h21'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'tv_screen' in insp.get_table_names():
        return
    op.create_table(
        'tv_screen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('location', sa.String(length=120), nullable=True),
        sa.Column('screen_type', sa.String(length=20), nullable=False, server_default='WAITING_MAIN'),
        sa.Column('clinic_code', sa.String(length=20), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('show_full_name', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('show_queue_stats', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('show_reception', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('show_triage', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('show_consulting', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('show_onward', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('voice_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('voice_rotate_daily', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('voice_languages', sa.String(length=20), nullable=True, server_default='en,yo'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'code', name='uq_tv_org_code')
    )
    op.create_index('ix_tv_org_active', 'tv_screen', ['org_id', 'active'])


def downgrade():
    try:
        op.drop_table('tv_screen')
    except Exception:
        pass
