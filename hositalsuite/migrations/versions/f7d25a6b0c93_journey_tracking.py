"""Journey tracking — where every patient stood, and for how long

WHY SEGMENTS RATHER THAN EVENT POINTS
-------------------------------------
A row saying "arrived at Triage 09:14" needs the NEXT row to work out how long
Triage took, and the last row of the day can never be measured at all. A
segment carries its own start, end and duration, so "how long does the pharmacy
take?" is a plain average over closed rows — no pairing, no gaps.

An OPEN segment (ended_at IS NULL) is where the patient is standing right now,
which is what the live board reads.

NOT AN EMR: where a patient was and for how long. Never why.

New file, never an edit to an applied migration. Safe to re-run.

Revision ID: f7d25a6b0c93
Revises: e6c14d9f3a72
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7d25a6b0c93"
down_revision: Union[str, Sequence[str], None] = "e6c14d9f3a72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "journey_segment"


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
        sa.Column("intake_id", sa.Integer(), sa.ForeignKey("reception_intake.id")),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("patient_visit.id")),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id")),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("department.id")),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("entered_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("seconds", sa.Integer()),
    )
    for name, cols in (
        ("ix_journey_segment_org", ["org_id"]),
        ("ix_journey_segment_intake", ["intake_id"]),
        ("ix_journey_segment_visit", ["visit_id"]),
        ("ix_journey_segment_patient", ["patient_id"]),
        ("ix_journey_segment_stage", ["stage"]),
        ("ix_journey_segment_dept", ["department_id"]),
        ("ix_journey_segment_staff", ["staff_id"]),
        ("ix_journey_segment_entered", ["entered_at"]),
        ("ix_journey_segment_ended", ["ended_at"]),
        ("ix_journey_org_stage", ["org_id", "stage"]),
        ("ix_journey_org_entered", ["org_id", "entered_at"]),
        ("ix_journey_open", ["org_id", "ended_at"]),
    ):
        op.create_index(name, TABLE, cols)


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in _tables(bind):
        return
    op.drop_table(TABLE)
