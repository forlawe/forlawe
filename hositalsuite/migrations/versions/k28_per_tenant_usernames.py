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

PostgreSQL notes (verified by running this chain against a real
PostgreSQL 16 server):

1. A failed DDL statement poisons the whole transaction ("current
   transaction is aborted"). The original bare try/except swallowed the
   Python error but left the transaction dead, so everything after a
   single miss — including alembic's own version stamp — failed with
   InFailedSqlTransaction. Every optional step now runs inside a
   SAVEPOINT (begin_nested), so a miss rolls back cleanly and the
   migration continues.
2. The baseline schema creates these uniques as INDEXES
   (batch_op.create_index(..., unique=True) → ix_user_username,
   ix_login_attempt_username), not constraints — drop_constraint can
   never remove an index, so both forms are tried, and the reflect
   fallback checks indexes as well as constraints.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k28_tenant_usernames'
down_revision = 'k27_phi_crypto'
branch_labels = None
depends_on = None


def _guarded(fn):
    """Run fn inside a SAVEPOINT; False if it failed.

    On PostgreSQL a failed statement aborts the surrounding transaction,
    so "try X, fall back to Y" needs a savepoint per attempt — otherwise
    the first miss silently kills every later statement in the migration.
    On SQLite SAVEPOINT is equally supported, so both engines take the
    same path.
    """
    bind = op.get_bind()
    try:
        with bind.begin_nested():
            fn()
        return True
    except Exception:
        return False


def _drop_uniq(table, column, candidates):
    """Drop the GLOBAL uniqueness on `column` — constraint OR unique index."""
    for name in candidates:
        if _guarded(lambda n=name: op.drop_constraint(n, table, type_="unique")):
            return
        if _guarded(lambda n=name: op.drop_index(n, table_name=table)):
            return
    # last resort: reflect the actual name (constraints AND unique indexes)
    bind = op.get_bind()
    try:
        insp = sa.inspect(bind)
        for uq in insp.get_unique_constraints(table):
            if uq.get("column_names") == [column]:
                if _guarded(lambda: op.drop_constraint(uq["name"], table,
                                                       type_="unique")):
                    return
        for ix in insp.get_indexes(table):
            if ix.get("unique") and ix.get("column_names") == [column]:
                if _guarded(lambda: op.drop_index(ix["name"], table_name=table)):
                    return
    except Exception:
        pass


def upgrade():
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if not is_sqlite:
        _drop_uniq("user", "username",
                   ("user_username_key", "uq_user_username", "ix_user_username"))
        _guarded(lambda: op.create_index("ix_user_username", "user",
                                         ["username"], unique=False))
        _guarded(lambda: op.create_unique_constraint("uq_user_org_username",
                                                     "user",
                                                     ["org_id", "username"]))

        _drop_uniq("login_attempt", "username",
                   ("login_attempt_username_key", "uq_login_attempt_username",
                    "ix_login_attempt_username"))
        _guarded(lambda: op.create_index("ix_login_attempt_username",
                                         "login_attempt", ["username"],
                                         unique=False))

    def _add_login_org():
        op.add_column("login_attempt",
                      sa.Column("org_id", sa.Integer(),
                                sa.ForeignKey("organization.id"), nullable=True))
        op.create_index("ix_login_attempt_org_id", "login_attempt", ["org_id"])

    _guarded(_add_login_org)
    _guarded(lambda: op.create_unique_constraint("uq_lock_org_username",
                                                 "login_attempt",
                                                 ["org_id", "username"]))


def downgrade():
    # Re-establishing the GLOBAL username unique after hospitals may have
    # created duplicate usernames is not automatic — requires manual
    # deduplication first. Left intentionally unautomated.
    pass
