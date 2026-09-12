"""Doctor consulting sessions — 'I am ready to consult'

WHY THIS EXISTS
---------------
The founder was explicit about when a doctor is available to Triage:

    "Doctor availability: both rostered AND clicked 'ready to consult'"

The roster says who is supposed to be in the building. This table says who is
actually sitting in a consulting room with the door open. Without it, Triage
would send a patient to an empty room because the roster said somebody should
be there — which is precisely the failure the founder was guarding against.

A row is opened when the doctor clicks ready and closed when they stop. Triage
reads only rows that are open AND whose doctor is on today's roster.

New file, never an edit to an applied migration. Safe to re-run: it inspects
before it creates.

Revision ID: d5b03c8a2e41
Revises: c4a92e1f7b30
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5b03c8a2e41"
down_revision: Union[str, Sequence[str], None] = "c4a92e1f7b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "doctor_session"


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
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("duty_date", sa.Date(), nullable=False),
        sa.Column("clinic", sa.String(length=20), nullable=False),
        sa.Column("consulting_room", sa.String(length=20), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False,
                  server_default=sa.text("1" if bind.dialect.name == "sqlite" else "true")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime()),
    )
    op.create_index("ix_doctor_session_org_date", TABLE, ["org_id", "duty_date"])
    op.create_index("ix_doctor_session_doctor", TABLE, ["doctor_id"])
    op.create_index("ix_doctor_session_ready", TABLE, ["ready"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in _tables(bind):
        return
    for ix in ("ix_doctor_session_ready", "ix_doctor_session_doctor",
               "ix_doctor_session_org_date"):
        try:
            op.drop_index(ix, table_name=TABLE)
        except Exception:                        # noqa: BLE001
            pass
    op.drop_table(TABLE)
