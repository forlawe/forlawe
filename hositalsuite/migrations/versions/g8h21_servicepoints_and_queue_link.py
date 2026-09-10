"""servicepoints (clinics, 8 rooms, 24 destinations) + queue linkage

Revision ID: g8h21
Revises: f7d25a6b0c93
Create Date: 2026-08-21

Adds:
- service_clinic, consulting_room, service_destination, clinic_destination
- queue_ticket.patient_id, patient_visit_id, intake_id (use_alter for cycle)

HARDENED 2026-09-03: this migration produced the production incident
    relation "service_clinic" already exists → InFailedSqlTransaction
A boot-time create_all() can have made the tables before Alembic runs (covered
by the existence checks below), and two Render instances can boot the SAME
deploy at once — an inspect-then-create race that no amount of pre-checking
closes (env.py now also takes an advisory lock for exactly this). Each create
therefore runs inside a SAVEPOINT and tolerates "already exists" from a
winning concurrent creator, so one lost race can no longer abort the whole
upgrade transaction on every deploy.
"""
from alembic import op
import sqlalchemy as sa

revision = 'g8h21'
down_revision = 'f7d25a6b0c93'
branch_labels = None
depends_on = None


def _table_exists(bind, name) -> bool:
    return name in set(sa.inspect(bind).get_table_names())


def _create_if_absent(bind, name, build) -> None:
    """CREATE TABLE that is safe against both the ordinary cases:
    table already there (create_all ran first) and the concurrent-boot race
    (another instance created it between our inspect and our DDL)."""
    if _table_exists(bind, name):
        return
    try:
        with bind.begin_nested():                 # SAVEPOINT — keeps the outer
            build()                               # transaction alive on failure
    except sa.exc.ProgrammingError as exc:
        if _table_exists(bind, name):
            print(f"alembic g8h21: '{name}' was created concurrently — "
                  f"tolerated ({str(exc)[:120]})", flush=True)
            return
        raise
    except sa.exc.OperationalError as exc:
        if _table_exists(bind, name):
            print(f"alembic g8h21: '{name}' was created concurrently — "
                  f"tolerated ({str(exc)[:120]})", flush=True)
            return
        raise


def _index_if_absent(bind, name, table, cols) -> None:
    if name in {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}:
        return
    try:
        with bind.begin_nested():
            op.create_index(name, table, cols)
    except (sa.exc.ProgrammingError, sa.exc.OperationalError):
        pass                                      # someone else made it first


def upgrade():
    bind = op.get_bind()

    # --- service clinics
    _create_if_absent(bind, 'service_clinic', lambda: op.create_table(
        'service_clinic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'code', name='uq_clinic_org_code')
    ))
    _index_if_absent(bind, 'ix_clinic_org_active', 'service_clinic',
                     ['org_id', 'active'])

    # --- consulting rooms
    _create_if_absent(bind, 'consulting_room', lambda: op.create_table(
        'consulting_room',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['service_clinic.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'code', name='uq_room_org_code')
    ))
    _index_if_absent(bind, 'ix_room_org_active', 'consulting_room',
                     ['org_id', 'active'])

    # --- service destinations
    _create_if_absent(bind, 'service_destination', lambda: op.create_table(
        'service_destination',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('place', sa.String(length=120), nullable=True),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'code', name='uq_dest_org_code')
    ))
    _index_if_absent(bind, 'ix_dest_org_active', 'service_destination',
                     ['org_id', 'active'])

    # --- clinic → destination routing
    _create_if_absent(bind, 'clinic_destination', lambda: op.create_table(
        'clinic_destination',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('clinic_id', sa.Integer(), nullable=False),
        sa.Column('destination_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['service_clinic.id'], ),
        sa.ForeignKeyConstraint(['destination_id'], ['service_destination.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clinic_id', 'destination_id', name='uq_clinic_dest')
    ))
    _index_if_absent(bind, 'ix_clinic_dest_org', 'clinic_destination',
                     ['org_id', 'clinic_id'])

    # --- queue linkage (column may already exist via ensure_schema)
    def _column_if_absent(table, column, coltype, index_name) -> None:
        if not _table_exists(bind, table):
            return
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if column in cols:
            return
        try:
            with bind.begin_nested():
                op.add_column(table, sa.Column(column, coltype, nullable=True))
                op.create_index(index_name, table, [column])
        except (sa.exc.ProgrammingError, sa.exc.OperationalError) as exc:
            # Re-inspect: if the column is there now, a concurrent creator won.
            cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
            if column in cols:
                print(f"alembic g8h21: queue_ticket.{column} added "
                      f"concurrently — tolerated ({str(exc)[:120]})", flush=True)
                return
            raise

    _column_if_absent('queue_ticket', 'patient_id', sa.Integer(),
                      'ix_queue_ticket_patient_id')
    _column_if_absent('queue_ticket', 'patient_visit_id', sa.Integer(),
                      'ix_queue_ticket_patient_visit_id')
    _column_if_absent('queue_ticket', 'intake_id', sa.Integer(),
                      'ix_queue_ticket_intake_id')


def downgrade():
    try:
        op.drop_table('clinic_destination')
    except Exception:
        pass
    try:
        op.drop_table('service_destination')
    except Exception:
        pass
    try:
        op.drop_table('consulting_room')
    except Exception:
        pass
    try:
        op.drop_table('service_clinic')
    except Exception:
        pass
    for col in ('patient_id', 'patient_visit_id', 'intake_id'):
        try:
            op.drop_column('queue_ticket', col)
        except Exception:
            pass
