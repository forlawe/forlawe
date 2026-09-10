"""F-065/F-069: stamp every inspection with the criteria wording it used.

Revision ID: l29_criteria_version
Revises: k28_tenant_usernames
Create Date: 2026-09-09

Why
---
The five inspection criteria were reworded/re-ordered on 18 Aug 2026 (v1 -> v2
in app/scoring.py). Before this migration the Inspection table had NO record of
which wording applied to a given inspection, so any trend or "recurring
problem" report that mixed records from before and after the change was
comparing criterion numbers that meant different things (v1 #2 = cleanliness,
v2 #2 = equipment). From now on every inspection stores criteria_version at
write time, drawn from the single constant scoring.CRITERIA_VERSION.

Backfill rule
-------------
Inspections submitted (or started, for never-submitted drafts) strictly before
2026-08-18 00:00:00 local were recorded under the v1 wording and get
criteria_version = 1; everything else gets the current version 2. This is the
best available reconstruction: the founder set v2 on 18 Aug 2026, and the exact
minute is not recorded anywhere.
"""
from alembic import op
import sqlalchemy as sa

revision = 'l29_criteria_version'
down_revision = 'k28_tenant_usernames'
branch_labels = None
depends_on = None

# Single named constant mirroring app/scoring.py at the time this migration was
# written. The model itself reads the live constant; migrations are immutable
# snapshots, so the value is written here on purpose.
_CURRENT_VERSION = 2
_V1_CUTOFF = '2026-08-18 00:00:00'


def _inspection_table_exists(bind) -> bool:
    insp = sa.inspect(bind)
    try:
        return "inspection" in insp.get_table_names()
    except Exception:
        return False


def _column_exists(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return name in {c["name"] for c in insp.get_columns("inspection")}
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Some test/synthetic databases are stamped past the baseline that created
    # the inspection table and never contain one; nothing to stamp there.
    if not _inspection_table_exists(bind):
        return
    # Render can retry a deploy — running twice must be a no-op, not an error.
    if _column_exists(bind, "criteria_version"):
        return

    # nullable=False with server_default so existing rows (and SQLite's
    # ADD COLUMN rules) are satisfied; new rows are stamped by the model with
    # the live CRITERIA_VERSION constant.
    op.add_column(
        "inspection",
        sa.Column("criteria_version", sa.Integer(), nullable=False,
                  server_default=str(_CURRENT_VERSION)),
    )
    # Reconstruct v1 records: submitted (or started) before the v2 wording day.
    ts_expr = "COALESCE(submitted_at, started_at)"
    if is_pg:
        op.execute(
            f"UPDATE inspection SET criteria_version = 1 "
            f"WHERE {ts_expr} IS NOT NULL AND {ts_expr} < "
            f"TIMESTAMP '{_V1_CUTOFF}'"
        )
    else:
        # SQLite stores DateTime lexicographically; a string comparison against
        # the same 'YYYY-MM-DD HH:MM:SS' shape is correct.
        op.execute(
            f"UPDATE inspection SET criteria_version = 1 "
            f"WHERE {ts_expr} IS NOT NULL AND {ts_expr} < '{_V1_CUTOFF}'"
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if _column_exists(bind, "criteria_version"):
            op.drop_column("inspection", "criteria_version")
    else:
        # SQLite: recreating the table is out of scope; downgrades are for
        # local dev only — production never downgrades.
        raise NotImplementedError("SQLite downgrade not supported for l29")
