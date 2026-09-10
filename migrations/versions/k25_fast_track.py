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
    tables = set(insp.get_table_names())
    # NOTE: server_default must be sa.false(), NOT sa.text('0'). PostgreSQL
    # rejects `DEFAULT 0` on a boolean column (DatatypeMismatch), so this
    # migration could never apply to a fresh PostgreSQL database — the chain
    # died here on every new PG/Supabase deploy. sa.false() compiles to
    # `DEFAULT 0` on SQLite (byte-identical to what already-applied SQLite
    # databases recorded) and `DEFAULT false` on PostgreSQL.
    for table in ('patient_visit', 'reception_intake', 'queue_ticket'):
        if table not in tables:
            continue
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'is_fast_track' not in cols:
            op.add_column(table, sa.Column('is_fast_track', sa.Boolean(), nullable=True, server_default=sa.false()))
        if 'fast_track_reason' not in cols:
            op.add_column(table, sa.Column('fast_track_reason', sa.String(length=40), nullable=True))
    # Ensure boolean defaults are 0/False and not null for new rows.
    # Bound as a real Python bool: PostgreSQL rejects both `DEFAULT 0` AND
    # `SET col = 0` for a boolean column (DatatypeMismatch), so no text('0')
    # anywhere here. SQLAlchemy binds False as 0 on SQLite and as a proper
    # boolean on PostgreSQL.
    for tbl in ('patient_visit', 'reception_intake', 'queue_ticket'):
        if tbl not in tables:
            continue
        t = sa.table(tbl, sa.column('is_fast_track'))
        op.execute(t.update().where(t.c.is_fast_track.is_(None))
                   .values(is_fast_track=False))
        # NOTE: do NOT wrap this in try/except. A swallowed database error
        # leaves a PostgreSQL transaction aborted, so every later statement
        # (including alembic's own version UPDATE) fails with
        # InFailedSqlTransaction and the migration can never complete. If the
        # UPDATE cannot run, the migration must fail loudly instead.

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
