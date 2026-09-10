# Load Test Report — 4,000 requests/minute campaign

**Date:** 2026-08-12 · **Tool:** Locust 2.46 (headless) · **Method:** real HTTP traffic
against the production stack (gunicorn + full app), not mocked endpoints.

> Per spec §39 this is a **tested capacity figure, not a guarantee**. Environment,
> methodology, bottlenecks and scaling path are documented below.

---

## 1. Test environment

| Component | Value |
|---|---|
| Load generator + app host | Same sandbox: **2 vCPU, ~2 GB RAM** |
| App server | gunicorn (production WSGI), threads per config below |
| Databases tested | SQLite (WAL) and **PostgreSQL 17** (Supabase's engine) |
| Rate limiting | Relaxed via `RATE_LIMIT_SCALE` for capacity measurement only (production limits stay on) |

**Traffic mix** (mirrors a real QR-scan surge):
- 80% patient public pages (complaint/booking/feedback portals, queue join/screen, health)
- 10% staff dashboard pages (logged-in)
- 10% **write path**: full complaint + feedback submissions with CSRF + idempotency keys

`constant_pacing` gave precise control: *N* users ≈ *N* requests/sec.

## 2. Results

| Run | Configuration | Demand | **Served** | Failures | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| R1 (pre-fix) | 1 worker × 4 threads, SQLite | ~2,300/min | 2,310/min | **127 (2.75%)** ⚠️ | 53ms | 120ms | 160ms |
| R1 fixed | 1 worker × 4 threads, SQLite | ~2,300/min | 2,325/min | **0%** | 53ms | 120ms | 170ms |
| **R2** | **1 worker × 4 threads, SQLite** | **4,000/min** | **4,482/min** | **0%** | 92ms | 220ms | 290ms |
| **R3** | **1 worker × 8 threads, PostgreSQL 17** | **4,000/min** | **4,462/min** | **0%** | 91ms | 220ms | 310ms |
| R4 overload | 1 worker × 8 threads, PostgreSQL | ~8,800/min | 8,850/min | 0% | 230ms | 550ms | 770ms |

**Write path specifically (R3):** complaint submissions at ~4.4/sec sustained,
p50 = 200ms, p95 = 320ms, **zero failures** — includes audit-chain writes,
SLA computation and notification queuing.

## 3. Verdict vs target

✅ **4,000 requests/minute: PASSED with headroom** on a single free-tier-shaped
instance (1 worker), on both SQLite and PostgreSQL, with 0% errors and
sub-250ms p95 latency.

✅ **Graceful degradation verified (R4):** at more than double the target,
the system absorbed demand by increasing latency (p50 230ms) instead of
erroring — no crashes, no failed submissions.

## 4. Bug found & fixed by this campaign 🐛

**Reference-number race condition** (R1): concurrent complaint submissions
computed the same sequential reference (`count + 1` pattern); the loser hit the
UNIQUE constraint and returned **HTTP 500** — 45% of submissions failed under
concurrent load. Fixed with a collision-retry insert
(`services.insert_with_unique_ref`) applied to complaints, bookings and
inspections; the DB unique constraint remains the arbiter, and an
idempotency-key collision now returns the original record instead of a
duplicate. Covered by 2 new regression tests (including a 12-thread hammer).

## 5. Honest caveats

1. **Local Postgres vs remote Supabase:** the load DB ran on the same machine.
   Remote Supabase adds network round-trips (typically +20–80ms per write
   depending on region). Reads are barely affected; expect write p50 to rise.
   Re-run this campaign against real Supabase after deploying (same scripts).
2. **Rate limiting was relaxed** to measure raw capacity. In production the
   per-IP limits shape traffic — with thousands of *distinct* patient IPs this
   is rarely the bottleneck; it mainly absorbs abuse from single sources.
3. **2 vCPU sandbox:** a production paid instance (2–4 vCPU) will match or beat
   these numbers; the free tier sleeps after inactivity (cold start ~30s).
4. Scheduler ran disabled during tests (documented pattern: one scheduler
   process per deployment, `DISABLE_SCHEDULER=1` on load-balanced web workers).

## 6. Scaling path beyond 4,000/min

1. Horizontal: add web workers/instances with `DISABLE_SCHEDULER=1`
   (scheduler stays single-instance) — architecture already documented.
2. Move uploads/PDFs to object storage (Supabase Storage) when volume grows.
3. Add CDN/static caching for portal assets if bandwidth costs appear.
4. Re-test at each tier with the same locust suite (`loadtest/locustfile.py`).

## 7. Reproduce

```bash
pip install -r requirements.txt locust
python run.py seed                      # or use loadtest DB
RATE_LIMIT_SCALE=100000 SECRET_KEY=x DISABLE_SCHEDULER=1 DATABASE_URL="..." \
  gunicorn --bind 127.0.0.1:8090 --workers 1 --threads 8 "app:create_app()" &
RATE_LIMIT_SCALE=100000 locust -f loadtest/locustfile.py --headless \
  --host http://127.0.0.1:8090 -u 70 -r 20 -t 120s --csv results/run
```
