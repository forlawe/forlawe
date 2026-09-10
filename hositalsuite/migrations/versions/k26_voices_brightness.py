"""Hausa+Igbo voice + brightness/night mode

Revision ID: k26_voices
Revises: k25_fasttrack
Create Date: 2026-08-22
Adds ha,ig to voice, brightness + night_mode to tv_screen
Per-tenant, no EMR, premium patient care.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k26_voices'
down_revision = 'k25_fasttrack'
branch_labels = None
depends_on = None

def upgrade():
    # FIX 2026-09-04: idempotent via inspector — avoids InFailedSqlTransaction.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'tv_screen' not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns('tv_screen')}
    for col, typ, default in [
        ('brightness', sa.Integer(), '100'),
        ('night_mode', sa.Boolean(), '0'),
    ]:
        if col not in cols:
            op.add_column('tv_screen', sa.Column(col, typ, nullable=True, server_default=sa.text(default)))
    # Update existing rows: set voice_languages to 4 languages if old value was en,yo
    try:
        op.execute("UPDATE tv_screen SET voice_languages='en,yo,ha,ig' WHERE voice_languages='en,yo' OR voice_languages IS NULL OR voice_languages=''")
    except Exception:
        pass
    for col, _typ, _default in [('brightness', sa.Integer(), '100'), ('night_mode', sa.Boolean(), '0')]:
        try:
            if col == 'brightness':
                op.execute("UPDATE tv_screen SET brightness=100 WHERE brightness IS NULL")
            else:
                op.execute("UPDATE tv_screen SET night_mode=0 WHERE night_mode IS NULL")
        except Exception:
            pass

def downgrade():
    for col in ('brightness', 'night_mode'):
        try:
            op.drop_column('tv_screen', col)
        except Exception:
            pass
