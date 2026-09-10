# Supabase egress exhaustion — 424.9 GB / 5 GB (8,499%)

**Cycle:** 11 Aug – 11 Sep 2026 · **DB size:** ~62 MB · **Symptoms:** org-wide
"Services restricted" (HTTP 402 on every request), Render logs full of
`psycopg2.OperationalError: SSL SYSCALL error: EOF detected`,
`InFailedSqlTransaction`, `relation "service_clinic" already exists`, and
repeated `scheduler was not running — restarted it`.

A 62 MB database does not ship 424 GB by existing. Something pulled roughly
**20 GB/day** out of it. The DB size also proves this is NOT a data-volume
problem — it is a transfer problem.

## First: find the offender (5 minutes, in the Supabase dashboard)

1. **Query Performance** → order by *bytes sent* / *rows returned*, window =
   the whole billing cycle. The top rows name the exact query.
2. **Logs → Postgres logs** → filter 402/limit events to see when transfers
   spiked (correlates with deploys, TV usage hours, or a specific date).
3. **Reports → Egress** graph: a flat constant line = a polling loop; spikes
   at 02:00 = the backup; spikes on every page load = a fat endpoint.

Code-side suspects found and fixed in this pass are listed below. If the
dashboard shows something else (e.g. one giant repeated SELECT), that query —
not the theory — is the truth.

## What made it catastrophic for the app

Supabase returned **402** on every connection → each query died mid-flight →
`SSL SYSCALL error: EOF detected`. The migration then failed inside its
transaction (`relation "service_clinic" already exists` from a boot race →
`InFailedSqlTransaction` for everything after), never stamped forward, and
**the identical failure replayed on every deploy** — each retry re-burning
queries against a quota that was already gone. The scheduler thread kept
dying with the database and self-healing on every health ping.

## Code changes in this pass (all tested)

| Change | File | Why it helps egress / stability |
|---|---|---|
| Migration runner takes a PostgreSQL advisory lock; concurrent deploys can no longer race `CREATE TABLE` (`relation … already exists` → aborted transaction → endless retry loop) | `migrations/env.py` | Stops the boot-failure loop that re-ran schema work every deploy |
| `g8h21` (service_clinic etc.): savepoint-wrapped, duplicate-tolerant creates + per-index guards | `migrations/versions/g8h21_servicepoints_and_queue_link.py` | A lost race or a pre-created table can no longer abort the whole upgrade |
| `ensure_schema()`: replaced the nested `except: pass` raw-SQL leave-table bootstrap with `db.metadata.create_all(tables=[…])`, failures logged loudly | `app/migrate.py` | No more silent migration drift; no dialect fork to maintain |
| `/api/v1/ready` schema introspection cached 60s (healthy answer only); `/api/v1/health` backup lookup cached 30s | `app/views/api.py` | Monitoring pinged these 24/7; each `/ready` call introspected 100+ tables. Constant chatter eliminated, drift still surfaces within a minute |
| Fuzzy patient search: scores **light 5-column tuples**, hydrates full Patient rows only for the ≤10 matches (was: 500 full dossiers with phone/NOK PII per failed search) | `app/hims.py` | Less PII in memory; ~100× fewer patient-row bytes shipped per failed search |
| Nightly backup: hard in-memory minimum interval (`MIN_BACKUP_INTERVAL_HOURS`, default 20h) behind the existing per-day Setting guard | `app/scheduler.py`, `app/config.py` | The backup is a full `SELECT *` of every table — the most expensive routine query in the app; a runaway loop can no longer repeat it |
| Migration-chain test generalized (any unresolved fork fails, no hardcoded revision ids) + alembic cross-check | `tests/test_migration_safety.py` | Keeps the deploy-time migration loop from ever coming back |

## Unblocks + what to watch

1. **Immediate unblock:** upgrade the Supabase plan, or wait for the Sep 11
   reset. While restricted, the app boots degraded and serves 503s — that is
   the honest behavior, not a bug.
2. **If it fills up again that fast with the fixes deployed**, the dashboard
   query list from step 1 above is the next suspect — bring the query, not a
   guess. Candidates to check first: TV boards polling more endpoints than
   `/api/tv/feed` (should be ~1 KB JSON every 5s), the personal-TV poll, and
   anything exporting the HIMS register.
3. **Backups:** with `BACKUP_KEEP=7` and one run/day at a 62 MB DB, nightly
   egress is ≤ ~2 GB/month (zips compress well below the raw size). Fine on
   the paid tier; on any free tier, consider disabling the nightly job
   (`DISABLE_SCHEDULER=1` kills it along with reminders — better: rely on
   Supabase's own daily snapshots, which are the primary recovery path).
4. **Render free tier restarts** cause full re-boots (create_all + migration
   check + seeding checks). Each boot is modest, but thousands of cold boots
   add up; if the dashboard shows boot-time queries dominating, a paid always-on
   instance solves both the boots and the wobble.
