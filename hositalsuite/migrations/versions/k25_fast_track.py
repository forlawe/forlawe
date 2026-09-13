"""Fast-track Elderly/Pregnant/Child + journey time

Revision ID: k25_fasttrack
Revises: j24_merge
Create Date: 2026-08-22
Adds is_fast_track + fast_track_reason to patient_visit, reception_intake, queue_ticket
Per-tenant, no EMR, premium patient care.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k25_fasttrack'
down_revision = 'j24_merge'
branch_labels = None
depends_on = None

def upgrade():
    # FIX 2026-09-04: idempotent via inspector — avoids InFailedSqlTransaction
    # where "already exists" aborts the whole transaction and later tables
    # (e.g. service_clinic) then fail with "relation already exists" noise.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    # Boolean defaults: SQLite wants 0/1, PostgreSQL wants false/true. An
    # integer literal is REJECTED by PostgreSQL ("column is of type boolean
    # but default expression is of type integer") — found by running this
    # chain against a real PostgreSQL 16 server, where it aborted the whole
    # migration. Same idiom as c4a92e1f7b30 / d5b03c8a2e41.
    _sqlite = bind.dialect.name == "sqlite"
    _false = "0" if _sqlite else "false"
    tables = set(insp.get_table_names())
    for table in ('patient_visit', 'reception_intake', 'queue_ticket'):
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'is_fast_track' not in cols:
            op.add_column(table, sa.Column('is_fast_track', sa.Boolean(), nullable=True, server_default=sa.text(_false)))
        if 'fast_track_reason' not in cols:
            op.add_column(table, sa.Column('fast_track_reason', sa.String(length=40), nullable=True))
    # Ensure boolean defaults are False and not null for new rows
    for tbl in ('patient_visit', 'reception_intake', 'queue_ticket'):
        if tbl not in tables:
            continue
        try:
            op.execute(f"UPDATE {tbl} SET is_fast_track={_false} WHERE is_fast_track IS NULL")
        except Exception:
            pass

def downgrade():
    for table in ('patient_visit', 'reception_intake', 'queue_ticket'):
        try:
            op.drop_column(table, 'is_fast_track')
        except Exception:
            pass
        try:
            op.drop_column(table, 'fast_track_reason')
        except Exception:
            pass
