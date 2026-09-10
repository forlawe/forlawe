"""Alembic environment — wired to the application's own config and models.

The database URL is never hardcoded: it comes from the same DATABASE_URL the app
uses, so `alembic upgrade head` always targets the environment you are in.
"""
from __future__ import annotations

import os
import sys
import time

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# make the application importable when alembic runs from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Config          # noqa: E402
from app.models import db              # noqa: E402

config = context.config

# Use the URL the CALLER supplied, if there is one, and only fall back to the
# application's configured database otherwise.
#
# This used to unconditionally overwrite the caller's URL with
# Config.SQLALCHEMY_DATABASE_URI. That meant `alembic upgrade head -x
# url=...`, a programmatic Config with an explicit url, or a test harness
# pointing at a scratch database all SILENTLY MIGRATED THE WRONG DATABASE:
# Alembic reported "Running upgrade ..." while the intended database was never
# touched. Anything verifying an upgrade this way was proving nothing.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url",
                           Config.SQLALCHEMY_DATABASE_URI.replace("%", "%%"))

target_metadata = db.metadata

# ---------------------------------------------------------------------------
# One migrator at a time.
#
# Render deploys start the new instance BEFORE the old one exits, and the app
# runs `alembic upgrade` at boot — so two instances can and did race: both
# inspected the same missing table, both ran CREATE TABLE, the loser died with
# `relation "service_clinic" already exists`, its transaction aborted, and
# every later statement in that transaction failed with InFailedSqlTransaction.
# The migration never stamped forward, so the SAME failure replayed on every
# deploy. A session-level advisory lock (PostgreSQL only) serializes boots;
# the loser acquires the lock after the winner committed, re-reads a fresh
# alembic_version, and no-ops. On SQLite the app is the only writer (WAL), so
# no lock is needed.
_ADVISORY_KEY = 736559101          # arbitrary constant, unique to this app


def _take_migration_lock(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    deadline = time.monotonic() + 120.0          # never hang a boot forever
    while True:
        got = connection.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_KEY}
        ).scalar()
        if got:
            return
        if time.monotonic() > deadline:
            # Proceed anyway: per-migration existence guards are the second
            # line of defence, and a hung boot is worse than a logged risk.
            print("alembic: WARNING — another instance held the migration "
                  "lock past 120s; proceeding unsynchronized", flush=True)
            return
        time.sleep(2.0)


def _release_migration_lock(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    try:
        connection.execute(text("SELECT pg_advisory_unlock(:k)"),
                           {"k": _ADVISORY_KEY})
    except Exception:                            # noqa: BLE001
        pass                                     # connection is closing anyway


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata,
                      literal_binds=True,
                      render_as_batch=True,
                      compare_type=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.",
                                     poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _take_migration_lock(connection)
        try:
            context.configure(connection=connection,
                              target_metadata=target_metadata,
                              # batch mode lets SQLite do ALTERs it cannot do natively
                              render_as_batch=True,
                              compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            _release_migration_lock(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
