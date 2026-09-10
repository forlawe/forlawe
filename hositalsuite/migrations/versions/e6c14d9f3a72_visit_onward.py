"""Onward routing — where the doctor sends the patient next (Stage D)

WHY A TABLE AND NOT A COLUMN
----------------------------
The founder was explicit that it can be more than one place:

    "The Doctor after attending to the patient would now push the patient to
     one, two or three out of the following
     (LAHSMA/Billing/Megalek/Laboratory/Pharmacy/Emergency)"

A single destination column could not hold "laboratory AND pharmacy AND
billing", and each desk finishes at its own pace — the lab can be done while
the pharmacy is still waiting. One row per destination handles both, and the
visit closes only when every row is done.

NOT AN EMR: records WHERE the patient was sent and whether they arrived. Never
what the test was for or what was prescribed.

New file, never an edit to an applied migration. Safe to re-run.

Revision ID: e6c14d9f3a72
Revises: d5b03c8a2e41
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6c14d9f3a72"
down_revision: Union[str, Sequence[str], None] = "d5b03c8a2e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "visit_onward"


def _tables(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in _tables(bind):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("patient_visit.id"), nullable=False),
        sa.Column("destination", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="PENDING"),
        sa.Column("note", sa.String(length=200)),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("sent_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("user.id")),
        # The same patient cannot be sent to the same desk twice on one visit.
        sa.UniqueConstraint("visit_id", "destination", name="uq_visit_onward_dest"),
    )
    op.create_index("ix_visit_onward_org", TABLE, ["org_id"])
    op.create_index("ix_visit_onward_visit", TABLE, ["visit_id"])
    op.create_index("ix_visit_onward_dest", TABLE, ["destination"])
    op.create_index("ix_visit_onward_status", TABLE, ["status"])
    op.create_index("ix_visit_onward_org_status", TABLE, ["org_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in _tables(bind):
        return
    for ix in ("ix_visit_onward_org_status", "ix_visit_onward_status",
               "ix_visit_onward_dest", "ix_visit_onward_visit",
               "ix_visit_onward_org"):
        try:
            op.drop_index(ix, table_name=TABLE)
        except Exception:                        # noqa: BLE001
            pass
    op.drop_table(TABLE)
