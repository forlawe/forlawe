"""F-016: an automated backup→restore drill, because a backup never restored
is a hope, not a backup.

The manual drill (docs/BACKUP_RESTORE_DRILL.md) needs a human, a Supabase
project and psql — so it happens rarely. This test runs the WHOLE drill in CI:
create a real backup archive with app code, then restore it into a fresh
empty database exactly the way RESTORE.txt instructs (create schema first,
load CSVs parents-before-children), and verify what came back.

If this test breaks, backups are still being WRITTEN but can no longer be
trusted to restore — that is precisely the failure the nightly job's green
log line hides.
"""
import csv
import io
import json
import zipfile

import pytest
from sqlalchemy import create_engine, text

from app.backup import create_backup
from app.models import db


@pytest.fixture()
def drill_app(app):
    return app


def _fk_sorted_tables(manifest_tables, metadata):
    """'Parents before children' (RESTORE.txt step 3), derived from the real
    FK graph via SQLAlchemy's topological sort, limited to tables in the
    archive."""
    wanted = set(manifest_tables)
    return [t.name for t in metadata.sorted_tables if t.name in wanted]


def test_backup_archive_is_complete_and_restorable(drill_app, seeded):
    from app.models import Organization, Patient

    # ---- arrange: a hospital with a user and a patient folder
    with drill_app.app_context():
        org = db.session.get(Organization, seeded["org"])
        org_name = org.name
        db.session.add(Patient(org_id=org.id,
                               hospital_number="DRILL/2026/00001",
                               surname="RESTORE", first_name="Drill", sex="F",
                               age_years=44, payer_type="SELF",
                               category="GENERAL"))
        db.session.commit()

    # Production runs the nightly backup in ITS OWN app context (scheduler
    # thread) with a fresh session — mirror that here, so the drill proves
    # what production does: committed data, read through a clean connection.
    db.session.remove()

    with drill_app.app_context():
        key, size = create_backup(drill_app, kind="drill")
        assert size > 0 and key.startswith("backups/")

        # ---- act: read the archive back out of durable storage
        from app import storage
        blob = storage.get(key)
        assert blob, "backup could not be read back from storage"

    zf = zipfile.ZipFile(io.BytesIO(blob))
    names = set(zf.namelist())
    manifest = json.loads(zf.read("manifest.json"))
    assert "RESTORE.txt" in names, "restore instructions missing from archive"

    # every table with rows must have a CSV in the archive
    with_rows = {t for t, n in manifest["tables"].items() if n > 0}
    missing = {f"{t}.csv" for t in with_rows} - names
    assert not missing, f"archive is missing CSVs for: {sorted(missing)}"
    # the drill patient must actually BE in the archive
    patient_csv = zf.read("patient.csv").decode("utf-8")
    assert "DRILL/2026/00001" in patient_csv, (
        "committed patient row missing from the backup archive — backups are "
        "silently incomplete")

    # ---- restore into a FRESH database (the drill's whole point)
    fresh = create_engine("sqlite://")          # in-memory throwaway
    metadata = db.metadata
    metadata.create_all(fresh)

    order = _fk_sorted_tables(manifest["tables"], metadata)
    restored_counts = {}
    with fresh.begin() as conn:
        for table in order:
            raw = zf.read(f"{table}.csv").decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(raw)))
            if not rows:
                restored_counts[table] = 0
                continue
            cols = list(rows[0].keys())
            quoted = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            payload = [{k: (None if v == "" else v) for k, v in r.items()}
                       for r in rows]
            conn.execute(text(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'),
                payload)
            restored_counts[table] = len(rows)

    # ---- verify: every row came back, and the data is really the data
    for table, expected in manifest["tables"].items():
        if table not in restored_counts:
            continue
        assert restored_counts[table] == expected, (
            f"{table}: manifest says {expected} rows, restore produced "
            f"{restored_counts[table]} — the backup cannot be trusted")

    with fresh.connect() as conn:
        got_name = conn.execute(text(
            'SELECT name FROM organization WHERE code = :c'),
            {"c": "TEST"}).scalar()
        assert got_name == org_name, "organization row did not survive restore"
        got_patient = conn.execute(text(
            "SELECT surname, hospital_number FROM patient "
            "WHERE hospital_number = 'DRILL/2026/00001'")).first()
        assert got_patient == ("RESTORE", "DRILL/2026/00001"), (
            "patient folder did not survive restore")


def test_backup_excludes_stored_file_binaries_but_keeps_metadata(drill_app, seeded):
    """The archive deliberately excludes binary blobs (they would balloon past
    what a free host can hold in memory) — but the stored_file INDEX must
    still be recorded so operators can see what lived there."""
    from app import storage
    from app.models import db as _db

    with drill_app.app_context():
        key = storage.put("drill/proof.txt", b"hello drill",
                          org_id=seeded["org"], content_type="text/plain")
        _db.session.commit()

    db.session.remove()          # fresh session like the production scheduler
    with drill_app.app_context():
        _bkey, _size = create_backup(drill_app, kind="drill")
        blob = storage.get(_bkey)

    zf = zipfile.ZipFile(io.BytesIO(blob))
    assert "stored_file.csv" in zf.namelist()
    rows = list(csv.DictReader(io.StringIO(zf.read("stored_file.csv").decode())))
    assert any(r["key"] == key for r in rows), (
        "stored_file metadata missing from backup — restore would lose track "
        "of what files existed")
