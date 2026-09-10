"""The rest of the hospital's paper admission form

WHY
---
The founder sent a photograph of the real paper form used at the desk. It asks
for several things the system did not hold: marital status, religion, state of
origin, date of birth, town, tribe and ethnic group.

These are IDENTITY and DEMOGRAPHIC details, not clinical ones, so they belong
here and do not breach the "this is not an EMR" rule. They are on the paper
form for practical reasons: dietary needs, burial rites, and finding an
interpreter who actually speaks the patient's language.

Added to BOTH the Reception intake and the patient folder, so a detail the
patient gives once at the front door is still there in their folder.

New file, never an edit to an applied migration. Safe to re-run: it inspects
before it adds, and it works whether or not the tables already exist.

Revision ID: a8e31c4f9b56
Revises: f7d25a6b0c93
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8e31c4f9b56"
down_revision: Union[str, Sequence[str], None] = "f7d25a6b0c93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (column, type) — applied to both tables where missing.
SHARED = [
    ("marital_status", sa.String(length=16)),
    ("religion", sa.String(length=40)),
    ("state_of_origin", sa.String(length=60)),
    ("town", sa.String(length=80)),
    ("tribe", sa.String(length=60)),
    ("ethnic_group", sa.String(length=60)),
]
# The intake had no birthday at all; the patient folder already has one.
INTAKE_ONLY = [("date_of_birth", sa.Date())]


def _columns(bind, table) -> set:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add(bind, table, columns) -> None:
    have = _columns(bind, table)
    if not have:
        return                      # table not created yet; models.py covers it
    for name, coltype in columns:
        if name not in have:
            op.add_column(table, sa.Column(name, coltype, nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    _add(bind, "reception_intake", SHARED + INTAKE_ONLY)
    _add(bind, "patient", SHARED)


def downgrade() -> None:
    bind = op.get_bind()
    for table, columns in (("reception_intake", SHARED + INTAKE_ONLY),
                           ("patient", SHARED)):
        have = _columns(bind, table)
        for name, _ in columns:
            if name in have:
                with op.batch_alter_table(table, schema=None) as batch:
                    batch.drop_column(name)
