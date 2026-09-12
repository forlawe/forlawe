"""unified roster: one row per person per day, plus leave

Adds `roster_entry`, the single table behind the merged Roster page. The old
`duty_roster` (Admin Manager, hospital-wide) and `dept_roster_entry` (legacy
two-staff department roster) are left exactly as they are: duty reminders and
the compliance report read `duty_roster`, and the legacy rows are COPIED into
`roster_entry` at boot rather than moved, so nothing can be lost.

Revision ID: 7a1c4b9e2d10
Revises: 246e2fd93e4f
Create Date: 2026-08-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a1c4b9e2d10"
down_revision: Union[str, Sequence[str], None] = "246e2fd93e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    if "roster_entry" in have:
        return
    op.create_table(
        "roster_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("duty_date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("shift", sa.String(length=12), nullable=False),
        sa.Column("leave_type", sa.String(length=16), nullable=True),
        sa.Column("scope", sa.String(length=12), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["section.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "duty_date", "user_id", "shift", "scope",
                            "department_id", "section_id", "unit_id",
                            name="uq_roster_entry_slot"),
    )
    with op.batch_alter_table("roster_entry", schema=None) as b:
        b.create_index("ix_roster_entry_org_date", ["org_id", "duty_date"], unique=False)
        for col in ("org_id", "duty_date", "user_id", "kind", "scope",
                    "department_id", "section_id", "unit_id"):
            b.create_index(b.f(f"ix_roster_entry_{col}"), [col], unique=False)


def downgrade() -> None:
    op.drop_table("roster_entry")
