# Backup Restore Drill — D3 Gap Fix
**Date:** 27 Aug 2026 · **Version:** 1.7.15 · **Gap:** D3 — No evidence restore ever tested

> An untested backup is not a backup — it's a hope.

## What was wrong

- `app/backup.py` now correctly creates CSV+zip backups on both SQLite and Postgres (fixed P0-2)
- Backups stored via `storage.py` (`STORAGE_BACKEND=db`) so they survive Render ephemeral disk
- **But:** No one ever restored one to prove it works. `OPERATIONS.md` says this in bold.

## Drill — Do this quarterly, and before launch

### 1. Create backup now

```bash
# On production host (Render Shell) or locally with prod DATABASE_URL
DATABASE_URL="postgresql://...?sslmode=require" python run.py backup
```

Or Admin → System Health → Backups → Download latest.

You should get `backups/hospitalsuite-20260827-120000.zip` with:
- `organization.csv`, `user.csv`, `patient.csv`, etc.
- `manifest.json`
- `RESTORE.txt`

### 2. Create throwaway database

- Supabase → New project → `hospitalsuite-restore-test` → Free tier → Region same as prod
- Copy its Session Pooler URI + `?sslmode=require`

### 3. Deploy app against empty DB

```bash
DATABASE_URL="postgresql://...restore-test...?sslmode=require" SECRET_KEY=test python run.py dbcheck
# Should say: ✅ Database reachable and schema ready.
```

### 4. Restore CSVs (per RESTORE.txt)

```bash
# With psql
psql "postgresql://...restore-test...?sslmode=require"

# Inside psql, parents before children:
\copy organization FROM 'organization.csv' WITH (FORMAT csv, HEADER true)
\copy branch FROM 'branch.csv' WITH (FORMAT csv, HEADER true)
\copy department FROM 'department.csv' WITH (FORMAT csv, HEADER true)
\copy "user" FROM 'user.csv' WITH (FORMAT csv, HEADER true)
# ... continue for all tables per manifest.json order
# Then reset sequences:
SELECT setval(pg_get_serial_sequence('organization','id'), COALESCE((SELECT MAX(id) FROM organization), 1));
SELECT setval(pg_get_serial_sequence('user','id'), COALESCE((SELECT MAX(id) FROM "user"), 1));
# ... for each table
```

### 5. Verify

```bash
DATABASE_URL="...restore-test..." python run.py
# Open http://localhost:8077 → sign in with restored admin → check dashboard, patient folder, complaint
```

### 6. Document

- Write date, backup file name, restore time, any errors in `reports/restore-drill-2026-08-27.md`
- Delete throwaway project after

## Automate

- Add Render cron job or GitHub Action that monthly:
  1. Downloads latest backup via API
  2. Restores to ephemeral Postgres
  3. Runs `pytest tests/test_smoke.py` against restored DB
  4. Posts result to Slack/email

## Current status

- [ ] First drill done before launch (required)
- [ ] Quarterly drill scheduled
- [ ] Restore instructions tested and updated

---
**Owner:** Founder / DPO  
**Next drill:** Before launch, then 27 Nov 2026

---

## AUTOMATED DRILL (F-016, added 2026-09-04)

`tests/test_backup_restore_drill.py` now runs the full drill in CI on every
push: creates a real backup archive with app code, restores it into a fresh
empty database via the exact RESTORE.txt procedure (schema first, then CSVs
parents-before-children), and verifies every row count, the manifest, and
spot data. If it goes red, backups can no longer be trusted — treat it like
the backup job itself is down.

The QUARTERLY MANUAL DRILL ABOVE IS STILL REQUIRED: it exercises the human
path (real Supabase project, psql, production-scale data) that automation
cannot reach.
