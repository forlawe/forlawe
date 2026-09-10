"""Patient folder: replace the clinical fields with patient-care fields

WHY THIS EXISTS (a mistake worth recording)
-------------------------------------------
Stage A first shipped with blood_group / genotype / allergies /
chronic_conditions on the patient folder. The founder correctly pointed out
that this app is NOT an EMR, so those were removed from the model.

They were removed by EDITING migration 9c2e5f7a41bb — which had already run in
production. Alembic had recorded that revision as applied, so it never ran
again, and the live database kept the old columns and never gained the new
ones. Every visit to /hims/ then died with:

    (psycopg2.errors.UndefinedColumn) column patient.preferred_lang does not exist

An already-applied migration must be treated as immutable history. The fix is
always a NEW migration, which is this file.

WHAT IT DOES
  * adds preferred_lang / assistance / care_note if missing
  * drops blood_group / genotype / allergies / chronic_conditions /
    marital_status / religion if present

Written to be safe on a database in ANY of the three possible states: never
had the table, has the old columns, or already has the new ones.

Revision ID: b3f81a9d5c22
Revises: 9c2e5f7a41bb
Create Date: 2026-08-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3f81a9d5c22"
down_revision: Union[str, Sequence[str], None] = "9c2e5f7a41bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADD = [
    ("preferred_lang", sa.String(length=4)),
    ("assistance", sa.String(length=200)),
    ("care_note", sa.String(length=200)),
]

# Clinical data this app has no business holding. Dropping them is also the
# right thing under NDPA: do not keep what you do not need.
DROP = ["blood_group", "genotype", "allergies", "chronic_conditions",
        "marital_status", "religion"]


def _columns(bind) -> set:
    insp = sa.inspect(bind)
    if "patient" not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns("patient")}


def upgrade() -> None:
    bind = op.get_bind()
    have = _columns(bind)
    if not have:
        return                                   # table not created yet; nothing to do

    for name, coltype in ADD:
        if name not in have:
            op.add_column("patient", sa.Column(name, coltype, nullable=True))

    # Everyone already on file is assumed to speak English until told otherwise.
    op.execute("UPDATE patient SET preferred_lang = 'en' WHERE preferred_lang IS NULL")

    for name in DROP:
        if name in have:
            with op.batch_alter_table("patient", schema=None) as batch:
                batch.drop_column(name)


def downgrade() -> None:
    bind = op.get_bind()
    have = _columns(bind)
    for name in ("preferred_lang", "assistance", "care_note"):
        if name in have:
            with op.batch_alter_table("patient", schema=None) as batch:
                batch.drop_column(name)
