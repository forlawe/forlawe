"""Reception intake — the front desk, ahead of the HIMS folder

WHY THIS EXISTS
---------------
The founder set out the real walk a new patient makes:

    Reception (details, special needs, insurance)
      -> Billing Unit (bill for folder + blood sugar test)
      -> Megalex / Pay-Point (pay)
      -> HIMS (open the folder)
      -> Triage (blood sugar test, then a ready doctor's room)

Reception happens BEFORE a folder exists, so it cannot live on the patient
table. Somebody who is quoted a fee and walks out must not consume a hospital
number or sit in the permanent register as a patient.

NOT AN EMR
----------
No symptom, no observation, no result. "Blood sugar test" is a billing line and
a Triage instruction; this table never stores a reading.

Written to be safe on a database in any state: it inspects before it creates,
so a fresh database, an existing production database and a re-run all behave.
An applied migration is immutable history — this is a NEW file, never an edit.

Revision ID: c4a92e1f7b30
Revises: b3f81a9d5c22
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a92e1f7b30"
down_revision: Union[str, Sequence[str], None] = "b3f81a9d5c22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "reception_intake"


def _tables(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in _tables(bind):
        return                                   # already there; nothing to do

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("ref", sa.String(length=40), nullable=False),

        sa.Column("surname", sa.String(length=80), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("other_names", sa.String(length=80)),
        sa.Column("sex", sa.String(length=1)),
        sa.Column("age_years", sa.Integer()),
        sa.Column("occupation", sa.String(length=80)),

        sa.Column("phone", sa.String(length=32)),
        sa.Column("address", sa.String(length=300)),

        sa.Column("nok_name", sa.String(length=120)),
        sa.Column("nok_phone", sa.String(length=32)),
        sa.Column("nok_relationship", sa.String(length=40)),

        sa.Column("payer_type", sa.String(length=16), nullable=False, server_default="SELF"),
        sa.Column("payer_number", sa.String(length=60)),
        sa.Column("payer_name", sa.String(length=120)),

        sa.Column("preferred_lang", sa.String(length=4), server_default="en"),
        sa.Column("assistance", sa.String(length=200)),
        sa.Column("care_note", sa.String(length=200)),

        sa.Column("stage", sa.String(length=12), nullable=False, server_default="RECEPTION"),
        sa.Column("bill_ref", sa.String(length=40)),
        sa.Column("payment_ref", sa.String(length=40)),
        sa.Column("needs_blood_sugar", sa.Boolean(), nullable=False,
                  server_default=sa.text("1" if bind.dialect.name == "sqlite" else "true")),

        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id")),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("patient_visit.id")),

        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("billed_at", sa.DateTime()),
        sa.Column("paid_at", sa.DateTime()),
        sa.Column("registered_at", sa.DateTime()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.UniqueConstraint("ref", name="uq_reception_intake_ref"),
    )
    op.create_index("ix_reception_intake_org", TABLE, ["org_id"])
    op.create_index("ix_reception_intake_stage", TABLE, ["stage"])
    op.create_index("ix_reception_intake_created", TABLE, ["created_at"])
    op.create_index("ix_reception_intake_phone", TABLE, ["phone"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in _tables(bind):
        return
    for ix in ("ix_reception_intake_phone", "ix_reception_intake_created",
               "ix_reception_intake_stage", "ix_reception_intake_org"):
        try:
            op.drop_index(ix, table_name=TABLE)
        except Exception:                        # noqa: BLE001 - index may not exist
            pass
    op.drop_table(TABLE)
