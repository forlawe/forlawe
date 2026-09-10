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

REWRITE NOTE (found by running the chain on an empty PostgreSQL database,
the path CI checks and SQLite can never show): the original used
guess-and-drop inside try/except. Every missed DROP is an error on
PostgreSQL, and an error inside a migration transaction aborts it — so the
migration could never complete on a fresh PG database, and the swallowed
errors also silently skipped the real constraint creation. This version
reflects the database first and drops/creates exactly what exists/is
missing, with no swallowing. Behaviour for already-migrated databases is
unchanged: they never re-run this file.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k28_tenant_usernames'
down_revision = 'k27_phi_crypto'
branch_labels = None
depends_on = None


def _names(_insp, _table):
    """Names of unique constraints AND unique indexes on the given column."""
    uq = {u["name"] for u in _insp.get_unique_constraints(_table)
          if (u.get("column_names") or []) == ["username"]}
    ix = {i["name"] for i in _insp.get_indexes(_table)
          if i.get("unique") and (i.get("column_names") or []) == ["username"]}
    return uq, ix


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    if "user" not in {t for t in insp.get_table_names()}:
        return
    tables = set(insp.get_table_names())

    # ------------------------------------------------------------------ drop
    for table in ("user", "login_attempt"):
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "username" not in cols:
            continue            # synthetic/legacy table shape: nothing to convert
        uq, ix = _names(insp, table)
        # Real UNIQUE CONSTRAINTs first (PostgreSQL create_all): dropping the
        # constraint removes its backing index too.
        for name in uq:
            if is_pg:
                op.drop_constraint(name, table, type_="unique")
            else:
                # SQLite has no constraint objects — uniqueness lives in
                # indexes, and reflection reports the same name in both sets.
                op.drop_index(name, table_name=table)
        # Bare UNIQUE INDEXes (the baseline migration used unique indexes).
        for name in ix - uq:
            op.drop_index(name, table_name=table)

    # ------------------------------------------------- login_attempt.org_id
    if "login_attempt" in tables:
        cols = {c["name"] for c in insp.get_columns("login_attempt")}
        if "org_id" not in cols:
            if is_pg:
                op.add_column("login_attempt",
                              sa.Column("org_id", sa.Integer(),
                                        sa.ForeignKey("organization.id"),
                                        nullable=True))
            else:
                # SQLite cannot ALTER-ADD a foreign key as a separate step
                # (alembic emits ADD COLUMN then ADD CONSTRAINT, and the second
                # is unsupported outside batch mode). A single raw ALTER with
                # an inline REFERENCES is the dialect-native way to add a
                # nullable FK column.
                op.execute("ALTER TABLE login_attempt ADD COLUMN org_id "
                           "INTEGER REFERENCES organization (id)")

    # ----------------------------------------------------------------- create
    for table in ("user", "login_attempt"):
        if table not in tables:
            continue
        insp = sa.inspect(bind)          # re-reflect after the drops above
        cols = {c["name"] for c in insp.get_columns(table)}
        if "username" not in cols or "org_id" not in cols:
            continue            # synthetic/legacy table shape: nothing to convert
        uq_names = {u["name"] for u in insp.get_unique_constraints(table)}
        ix_names = {i["name"] for i in insp.get_indexes(table)}
        uniq_name = ("uq_user_org_username" if table == "user"
                     else "uq_lock_org_username")
        plain_ix = f"ix_{table}_username"
        # plain (non-unique) username index for lookups inside one hospital
        if plain_ix not in ix_names and plain_ix not in uq_names:
            op.create_index(plain_ix, table, ["username"], unique=False)
        # the new per-hospital uniqueness
        if uniq_name not in uq_names and uniq_name not in ix_names:
            if is_pg:
                op.create_unique_constraint(uniq_name, table,
                                            ["org_id", "username"])
            else:
                # SQLite enforces uniqueness through indexes; a named unique
                # index is the drop-able equivalent of the model's constraint.
                op.create_index(uniq_name, table, ["org_id", "username"],
                                unique=True)

    # login_attempt.org_id lookup index
    if "login_attempt" in tables:
        insp = sa.inspect(bind)
        cols = {c["name"] for c in insp.get_columns("login_attempt")}
        if "org_id" in cols:
            have = {i["name"] for i in insp.get_indexes("login_attempt")}
            if "ix_login_attempt_org_id" not in have:
                op.create_index("ix_login_attempt_org_id", "login_attempt",
                                ["org_id"])


def downgrade():
    # Re-establishing the GLOBAL username unique after hospitals may have
    # created duplicate usernames is not automatic — requires manual
    # deduplication first. Left intentionally unautomated.
    pass
