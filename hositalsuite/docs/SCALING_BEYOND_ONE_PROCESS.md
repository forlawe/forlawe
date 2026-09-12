# Scaling beyond one web worker (F-002)

The pilot deliberately ran **one gunicorn worker** (`WEB_CONCURRENCY=1`,
`--workers 1` in `render.yaml`) because three pieces of state lived only in
process memory: the scheduler, the rate limiter, and the audit hash chain.
As of this change all three are safe at any worker/dyno count:

| Piece          | Was                                   | Now                                                                  |
|----------------|---------------------------------------|----------------------------------------------------------------------|
| Audit chain    | `threading.Lock` (1 process only)     | + `pg_advisory_xact_lock` — held until the winner's transaction commits, so the next worker chains from the committed tail |
| Scheduler      | every process ran every job           | + `pg_try_advisory_lock` leader election on a dedicated connection; followers sleep. Lock auto-releases if a worker dies → failover within one interval |
| Rate limiter   | in-memory deques                      | already Redis-backed when `REDIS_URL` is set (falls back to memory per worker, which only ever makes limits *looser*, never blocks real users) |

Covered by `tests/test_multiprocess_f002.py` (SQLite paths + mocked
PostgreSQL advisory-lock paths; the real-PG behaviour is standard engine
semantics: xact lock → release at COMMIT, session lock → release at
connection close).

## To lift the ceiling (Render)

1. Provision Redis (Render Key Value service or managed) and set
   `REDIS_URL` / `REDIS_TLS_URL` on the web service. Without it the
   per-worker memory limiter still works, just not fleet-wide.
2. Raise `WEB_CONCURRENCY` (e.g. `2`). Gunicorn `--workers` flag in
   `render.yaml`'s startCommand governs if set there — change it too.
3. Restart. Exactly one worker becomes scheduler leader (watch the log:
   non-leaders simply never log job lines).
4. Verify the audit chain after rollout: Management Console → audit chain
   check (`verify_chain`), which must report OK for every org.

Notes

- Multiple **dynos** (horizontal scale) are covered by the same locks — the
  leader election is per-fleet, not per-dyno.
- The nightly backup already guards itself with `last_backup_day` in
  `Setting`, so even a leader failover mid-night cannot double-back-up.
- Alternative topology (heavier): move the scheduler to a Render
  **Background Worker** running `python -c "from app import create_app,
  scheduler; app=create_app(scheduler=False); scheduler.ensure_running(app)"`
  and keep the web service stateless. The advisory-lock election makes this
  safe even if both keep running.
- Cost note: steps 1–2 add one Redis instance + ~1 extra worker to the
  Render bill; the founder should opt in explicitly.
