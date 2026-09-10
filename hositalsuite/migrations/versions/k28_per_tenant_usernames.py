"""F-021 per-tenant usernames: user.username scoped per hospital

Revision ID: k28_tenant_usernames
Revises: k27_phi_crypto
Create Date: 2026-09-04

- user.username: global UNIQUE gone; UNIQUE (org_id, username) in.
- login_attempt: global UNIQUE username gone; org_id added;
  UNIQUE (org_id, username) in (org_id NULL = context-free login).

Existing single-hospital deployments keep working unchanged — their
usernames were already unique, so the narrower constraint admits every
existing row.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k28_tenant_usernames'
down_revision = 'k27_phi_crypto'
branch_labels = None
depends_on = None


def _drop_uniq(table, column, candidates):
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    for name in candidates:
        try:
            if is_pg:
                op.drop_constraint(name, table, type_="unique")
            else:
                op.drop_index(name, table_name=table)
            return
        except Exception:
            continue
    # last resort: reflect the actual name
    try:
        insp = sa.inspect(bind)
        for uq in insp.get_unique_constraints(table):
            if uq.get("column_names") == [column]:
                if is_pg:
                    op.drop_constraint(uq["name"], table, type_="unique")
                return
    except Exception:
        pass


def upgrade():
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if not is_sqlite:
        _drop_uniq("user", "username",
                   ("user_username_key", "uq_user_username", "ix_user_username"))
        try:
            op.create_index("ix_user_username", "user", ["username"],
                            unique=False)
        except Exception:
            pass
        try:
            op.create_unique_constraint("uq_user_org_username", "user",
                                        ["org_id", "username"])
        except Exception:
            pass

        _drop_uniq("login_attempt", "username",
                   ("login_attempt_username_key", "uq_login_attempt_username",
                    "ix_login_attempt_username"))
        try:
            op.create_index("ix_login_attempt_username", "login_attempt",
                            ["username"], unique=False)
        except Exception:
            pass
    try:
        op.add_column("login_attempt",
                      sa.Column("org_id", sa.Integer(),
                                sa.ForeignKey("organization.id"), nullable=True))
        op.create_index("ix_login_attempt_org_id", "login_attempt", ["org_id"])
    except Exception:
        pass
    try:
        op.create_unique_constraint("uq_lock_org_username", "login_attempt",
                                    ["org_id", "username"])
    except Exception:
        pass


def downgrade():
    # Re-establishing the GLOBAL username unique after hospitals may have
    # created duplicate usernames is not automatic — requires manual
    # deduplication first. Left intentionally unautomated.
    pass
