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
    # NOTE: night_mode must use sa.false(), not sa.text('0'): PostgreSQL
    # rejects `DEFAULT 0` on a boolean column (DatatypeMismatch), so this
    # migration could never apply on a fresh PostgreSQL database. sa.false()
    # compiles to `DEFAULT 0` on SQLite and `DEFAULT false` on PostgreSQL.
    if 'brightness' not in cols:
        op.add_column('tv_screen', sa.Column('brightness', sa.Integer(),
                                             nullable=True,
                                             server_default=sa.text('100')))
    if 'night_mode' not in cols:
        op.add_column('tv_screen', sa.Column('night_mode', sa.Boolean(),
                                             nullable=True,
                                             server_default=sa.false()))
    # Update existing rows: set voice_languages to 4 languages if old value was
    # en,yo. Guarded by the column check above — no try/except: a swallowed
    # database error aborts the PostgreSQL transaction and the migration can
    # never complete.
    if 'voice_languages' in cols:
        op.execute("UPDATE tv_screen SET voice_languages='en,yo,ha,ig' "
                   "WHERE voice_languages='en,yo' OR voice_languages IS NULL "
                   "OR voice_languages=''")
    # Normalise NULLs. Values are bound (100 as int, False as bool): assigning
    # the literal `0` to a boolean column is a DatatypeMismatch on PostgreSQL.
    tv = sa.table('tv_screen', sa.column('brightness', sa.Integer()),
                  sa.column('night_mode', sa.Boolean()))
    op.execute(tv.update().where(tv.c.brightness.is_(None))
               .values(brightness=100))
    op.execute(tv.update().where(tv.c.night_mode.is_(None))
               .values(night_mode=False))

def downgrade():
    for col in ('brightness', 'night_mode'):
        try:
            op.drop_column('tv_screen', col)
        except Exception:
            pass
