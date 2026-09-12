"""Database backup that actually works on PostgreSQL.

THE BUG THIS REPLACES
---------------------
The old `job_nightly_backup` returned immediately unless the database was
SQLite. Production runs PostgreSQL, so the "nightly backup" ran every night and
did nothing, while the docs and the admin UI both claimed backups existed. A
backup you believe in but do not have is worse than no backup.

WHAT THIS DOES
--------------
Engine-independent logical backup: every table is dumped to CSV, zipped with a
manifest, and stored through app.storage (durable, so it survives restarts).
No pg_dump binary required — Render's free plan has no shell and no way to
install one. Restore instructions ship inside every archive.

This is a safety net, NOT a replacement for your managed provider's snapshots.
Supabase's own daily backups remain the primary recovery path; this gives you an
independent copy you can download and keep off-platform.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import zipfile

from sqlalchemy import inspect

from .models import db, now_naive

RESTORE_README = """HOW TO RESTORE THIS BACKUP
==========================

This archive contains one CSV file per database table, plus manifest.json
describing the schema version and row counts at the time of the backup.

To restore into an empty database:

  1. Deploy the application against the new, EMPTY database and let it start
     once. It creates all tables automatically (db.create_all + ensure_schema).
  2. Stop the application.
  3. Load each CSV into the matching table, parents before children
     (organization -> user/department -> everything else). With psql:

       \\copy organization FROM 'organization.csv' WITH (FORMAT csv, HEADER true)

  4. Reset each table's ID sequence, e.g.:

       SELECT setval(pg_get_serial_sequence('complaint','id'),
                     COALESCE((SELECT MAX(id) FROM complaint), 1));

  5. Start the application and sign in.

VERIFY YOUR BACKUPS. An untested backup is not a backup - restore one into a
throwaway database at least once per quarter.
"""


def _tables() -> list[str]:
    return sorted(inspect(db.engine).get_table_names())


def create_backup(app, *, kind: str = "auto") -> tuple[str, int]:
    """Create a backup archive in durable storage. Returns (key, bytes).

    Reads run on a DEDICATED fresh connection, not the ambient session. The
    ambient session can hold an open transaction whose snapshot predates
    just-committed writes — found by the automated restore drill: a patient
    committed seconds earlier was silently MISSING from the archive. Recent
    data must never be absent from a backup, so: commit any pending ambient
    writes first, then open one clean connection, put it in cross-org (RLS
    all_orgs) scope if PostgreSQL, and read every table on that connection.
    """
    from . import storage
    from sqlalchemy import text as _text

    stamp = now_naive().strftime("%Y%m%d-%H%M%S")
    key = f"backups/hospitalsuite-{stamp}.zip"
    manifest = {
        "created_at": now_naive().isoformat(),
        "kind": kind,
        "engine": db.engine.url.get_backend_name(),
        "app_version": "1.2.0",
        "tables": {},
    }

    # Flush the caller's pending writes so they are IN the backup (and end
    # the ambient snapshot so it cannot poison the read connection pool).
    db.session.commit()

    is_pg = db.engine.url.get_backend_name() == "postgresql"

    # F-018: the archive is built on DISK and every table is streamed row by
    # row into it — memory now holds one row + the zip buffer, not every row
    # of every table (and not a second full copy as bytes at the end). On
    # PostgreSQL stream_results keeps the read server-side.
    tmp = tempfile.NamedTemporaryFile(prefix="hms-backup-", suffix=".zip",
                                      delete=False)
    tmp.close()
    zip_path = tmp.name
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            with db.engine.connect().execution_options(
                    stream_results=True) as conn:
                # A backup is deliberately hospital-wide; say so, because RLS
                # would otherwise hand back an empty archive that LOOKS like a
                # success. The GUC is set on THE READING connection (transaction-
                # local), which is the one the SELECTs below actually use.
                if is_pg:
                    from .rls import ORG_VAR, ALL_ORGS
                    # is_local=false: the GUC must survive conn.commit() below —
                    # a transaction-local set_config would be dropped by that
                    # commit and RLS would hand back an EMPTY archive on
                    # PostgreSQL. The connection is dedicated and closed after.
                    conn.execute(_text(
                        f"SELECT set_config('{ORG_VAR}', '{ALL_ORGS}', false)"))
                conn.commit()          # end the set_config txn; start clean reads

                tables = sorted(inspect(db.engine).get_table_names())
                for table in tables:
                    # Large binaries are excluded: they already live in stored_file and
                    # would balloon the archive past what a free host can hold in memory.
                    if table == "stored_file":
                        stmt = _text(
                            f"SELECT id, key, org_id, folder, filename, content_type, size, sha256 "  # noqa: S608
                            f"FROM {table}")
                    else:
                        stmt = _text(f"SELECT * FROM {table}")  # noqa: S608
                    result = conn.execute(stmt)
                    count = 0
                    with zf.open(f"{table}.csv", "w") as raw_fh:
                        text_fh = io.TextIOWrapper(raw_fh, encoding="utf-8",
                                                   newline="")
                        first = True
                        for r in result.mappings():      # row-by-row — never .all()
                            if first:
                                w = csv.DictWriter(text_fh, fieldnames=list(r.keys()))
                                w.writeheader()
                                first = False
                            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
                            count += 1
                        text_fh.flush()
                    manifest["tables"][table] = count
                zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
                zf.writestr("RESTORE.txt", RESTORE_README)
        size = os.path.getsize(zip_path)
        storage.put_file(zip_path, key)   # content-type derived from .zip key
    finally:
        try:
            os.unlink(zip_path)          # the archive lives in storage now
        except OSError:
            pass
    db.session.commit()
    app.logger.info("backup: wrote %s (%d bytes, %d tables)",
                    key, size, len(manifest["tables"]))
    return key, size


def prune_backups(keep: int = 7) -> int:
    """Delete all but the newest `keep` archives."""
    from .models import StoredFile
    rows = (db.session.query(StoredFile)
            .filter(StoredFile.key.like("backups/%"))
            .order_by(StoredFile.created_at.desc()).all())
    removed = 0
    for row in rows[keep:]:
        db.session.delete(row)
        removed += 1
    if removed:
        db.session.commit()
    return removed


def list_backups(limit: int = 30):
    from .models import StoredFile
    return (db.session.query(StoredFile)
            .filter(StoredFile.key.like("backups/%"))
            .order_by(StoredFile.created_at.desc()).limit(limit).all())
