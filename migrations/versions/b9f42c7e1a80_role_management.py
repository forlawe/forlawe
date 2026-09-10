"""Role Management: roles, permissions, extra hats, and the teamwork board

WHY
---
A person's job used to be one word in a column. Every question a real hospital
asks about who may do what needed a developer and a redeploy. These four tables
move that decision into the hospital's own hands:

  role             — a named job owned by ONE hospital
  role_permission  — one tick on one role
  user_role        — this person also holds this role, optionally in one place
  work_claim       — "I am on this", so several staff can share one job

NOTHING IS DROPPED AND NOTHING IS ALTERED. The existing `user.role` column is
untouched and remains authoritative; these tables sit alongside it. That is
deliberate: a migration that rewrote every account's role in place would have
no way back if the new logic were wrong.

A NEW FILE, NEVER AN EDIT TO AN APPLIED MIGRATION. Editing a deployed migration
caused a total production outage on 16 Aug 2026.

Safe to re-run: every step inspects before it acts, on both SQLite and
PostgreSQL.

Revision ID: b9f42c7e1a80
Revises: a8e31c4f9b56
Create Date: 2026-08-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9f42c7e1a80"
down_revision: Union[str, Sequence[str], None] = "a8e31c4f9b56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    have = _tables(bind)

    if "role" not in have:
        op.create_table(
            "role",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(),
                      sa.ForeignKey("organization.id"), nullable=False),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=300)),
            sa.Column("scope", sa.String(length=16), nullable=False,
                      server_default="DEPARTMENT"),
            sa.Column("builtin", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("org_id", "code", name="uq_role_org_code"),
        )
        op.create_index("ix_role_org_id", "role", ["org_id"])

    if "role_permission" not in have:
        op.create_table(
            "role_permission",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id"),
                      nullable=False),
            sa.Column("permission", sa.String(length=40), nullable=False),
            sa.Column("allowed", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.UniqueConstraint("role_id", "permission", name="uq_roleperm"),
        )
        op.create_index("ix_role_permission_role_id", "role_permission", ["role_id"])

    if "user_role" not in have:
        op.create_table(
            "user_role",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(),
                      sa.ForeignKey("organization.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"),
                      nullable=False),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id"),
                      nullable=False),
            sa.Column("department_id", sa.Integer(),
                      sa.ForeignKey("department.id")),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("unit.id")),
            sa.Column("active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("granted_by_id", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("granted_at", sa.DateTime()),
            sa.UniqueConstraint("user_id", "role_id", "department_id", "unit_id",
                                name="uq_userrole"),
        )
        op.create_index("ix_user_role_org_id", "user_role", ["org_id"])
        op.create_index("ix_user_role_user_id", "user_role", ["user_id"])
        op.create_index("ix_user_role_role_id", "user_role", ["role_id"])
        op.create_index("ix_user_role_department_id", "user_role", ["department_id"])
        op.create_index("ix_user_role_unit_id", "user_role", ["unit_id"])
        op.create_index("ix_userrole_org_user", "user_role", ["org_id", "user_id"])

    if "work_claim" not in have:
        op.create_table(
            "work_claim",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(),
                      sa.ForeignKey("organization.id"), nullable=False),
            sa.Column("department_id", sa.Integer(),
                      sa.ForeignKey("department.id")),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("unit.id")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"),
                      nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("entity_type", sa.String(length=30)),
            sa.Column("entity_id", sa.Integer()),
            sa.Column("note", sa.String(length=200)),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime()),
            sa.Column("seconds", sa.Integer()),
        )
        op.create_index("ix_work_claim_org_id", "work_claim", ["org_id"])
        op.create_index("ix_work_claim_department_id", "work_claim", ["department_id"])
        op.create_index("ix_work_claim_unit_id", "work_claim", ["unit_id"])
        op.create_index("ix_work_claim_user_id", "work_claim", ["user_id"])
        op.create_index("ix_work_claim_kind", "work_claim", ["kind"])
        op.create_index("ix_work_claim_started_at", "work_claim", ["started_at"])
        op.create_index("ix_work_claim_ended_at", "work_claim", ["ended_at"])
        op.create_index("ix_claim_open", "work_claim", ["org_id", "ended_at"])
        op.create_index("ix_claim_task", "work_claim",
                        ["org_id", "kind", "entity_type", "entity_id"])


def downgrade() -> None:
    bind = op.get_bind()
    have = _tables(bind)
    # Children before parents.
    for table in ("work_claim", "user_role", "role_permission", "role"):
        if table in have:
            op.drop_table(table)
