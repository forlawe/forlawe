# Render Postgres Migration Guide — Answer to "Is it professional and cost efficient?"
**Date:** 27 Aug 2026 · **Version:** 1.7.15

## Your Question

> Is it possible to put the database on Render? Is it professional and cost efficient?

**Answer: YES possible, YES professional, cost is similar to Supabase Pro, but with trade-offs. For launch, stay on Supabase Pro. For single-vendor simplicity, move to Render Postgres Standard.**

---

## Comparison (2026 pricing)

| Factor | Supabase (Current) | Render Postgres |
|---|---|---|
| **Possible?** | Yes, you already use Session Pooler `postgresql://...pooler.supabase.com:5432/postgres?sslmode=require` | Yes — Render dashboard → New → PostgreSQL → choose plan → get Internal DATABASE_URL |
| **Professional?** | Yes, enterprise-grade, dashboard, auth, storage, realtime, pooler, backups, PITR | Yes, managed, automated backups, HA option, private networking, same region as app |
| **Latency** | App Frankfurt → Supabase maybe EU-West (Ireland) = +20-80ms per query | App + DB both Frankfurt + private network = 5-10ms, faster, more secure (no public internet) |
| **Free tier** | Free: 500 MB DB, 2 GB bandwidth, pauses after 7 days idle — **caused 15 Aug outage** | No free DB — Basic $7/mo minimum, no pausing |
| **Paid** | Pro $25/mo: 8 GB DB, 100 GB bandwidth, daily backups, PITR, no pausing, pooler included | Starter $7: 1 GB storage, 1 GB RAM, 1 vCPU, 7-day backups. Standard $20: 4 GB, 2 GB RAM, 1 vCPU, 7-day backups, HA $7 extra. Pro $65: 16 GB, 4 GB RAM, 2 vCPU |
| **Connection pooling** | Supavisor pooler built-in — critical for >1 worker | **NOT included** — you must add PgBouncer yourself or use external pooler before >1 web instance |
| **Dashboard** | Supabase Studio — SQL editor, table view, auth, storage UI | Render dashboard — basic metrics, logs, no table UI — you use psql or external tool |
| **Backups** | Daily physical + PITR (Pro), plus your own CSV backup in `stored_file` | Daily automated, 7-day retention (Starter/Standard), PITR on Pro, plus your CSV backup |
| **Storage for files** | Supabase Storage (S3-compatible) — 1 GB free, then $0.021/GB | No built-in object storage — use R2/S3 or keep `STORAGE_BACKEND=db` (not recommended at scale) |
| **Single vendor benefit** | Two vendors, two bills, two dashboards | One vendor, one bill, one region, private network free — simpler for solo founder |
| **Lock-in / migration** | Easy — pg_dump → psql | Easy — pg_dump → psql |

---

## When to stay on Supabase

- You already have it working, team knows Studio UI
- You want built-in Storage for files (move from `STORAGE_BACKEND=db` to Supabase Storage)
- You want pooler included (no extra work for >1 worker)
- Cost: Pro $25 is good value for 8 GB + bandwidth + tooling

**Action if staying:** Upgrade Free → Pro TODAY, enable PITR, set `DATABASE_URL` to Session Pooler (you already do), set `DATA_RESIDENCY` env.

---

## When to move to Render Postgres

- You want **lowest latency** (5-10ms) and **private networking** (DB not exposed to public internet)
- You want **single vendor** — one dashboard, one bill, simpler ops
- You are willing to add PgBouncer or keep 1 worker for now
- Cost: Standard $20 + HA $7 = $27/mo — similar to Supabase Pro $25, but faster

**Action if moving:**

### Migration steps (30 min)

1. **Create Render Postgres:**
   - Render dashboard → New → PostgreSQL → Name `hospital-suite-db` → Region Frankfurt → Plan Basic ($7) or Standard ($20) → Create
   - Wait 2-3 min, copy **Internal Database URL** (starts with `postgres://...` or `postgresql://...`)

2. **Backup from Supabase:**
   ```bash
   # On your local machine with psql installed
   pg_dump "postgresql://postgres.YOURREF:PASSWORD@aws-0-XXXX.pooler.supabase.com:5432/postgres?sslmode=require" --no-owner --no-acl -f backup.sql
   ```

3. **Restore to Render:**
   ```bash
   psql "postgresql://user:password@dpg-xxx.frankfurt-postgres.render.com:5432/dbname?sslmode=require" -f backup.sql
   ```

4. **Test:**
   ```bash
   DATABASE_URL="postgresql://...render...?sslmode=require" python run.py dbcheck
   # Should say: ✅ Database reachable and schema ready.
   ```

5. **Update Render env:**
   - Render → hospital-suite service → Environment → `DATABASE_URL` → paste Render Internal URL → Save → Redeploy

6. **Verify:**
   - `https://your-app.onrender.com/api/v1/health` → `database: true`
   - `https://your-app.onrender.com/api/v1/ready` → `ready: true`
   - Sign in, check dashboard, create test complaint

7. **Enable backups on Render:**
   - Render → Postgres → Backups → Enable daily, 7-day retention

8. **Add pooler before scaling:**
   - When you go to >1 web instance, add PgBouncer:
     - Render → New → Private Service → Docker image `edoburu/pgbouncer` → set `DATABASE_URL` → expose as `DATABASE_URL` for web
     - Or use Supabase pooler even with Render DB (possible but adds cross-provider hop)
     - Or set `DB_POOL_SIZE=5` and `DB_MAX_OVERFLOW=10` per instance and ensure total connections < Postgres max (100)

---

## Cost efficiency — honest math

**For 1 hospital (pilot):**
- Supabase Free + Render Free = $0 but **NOT production** (sleeps, no backup, cold start) — caused outage
- Supabase Pro $25 + Render Starter $7 = $32/mo — **recommended, production, profitable if you charge hospital ₦150k/mo**
- Render Postgres Basic $7 + Render Starter $7 = $14/mo — cheaper, but 1 GB DB fills fast with `stored_file` bloat — you'll need Standard $20 soon

**For 10 hospitals (500 rps target):**
- Supabase Pro $25 + Render Standard $25 × 2 instances = $75/mo + Redis $10 = $85/mo
- Render Postgres Standard $20 + HA $7 + Web Standard $25 × 2 + Redis $10 = $87/mo — similar

**For 5,000 concurrent users (50-150 rps peak, 30 hospitals):**
- Either option ~$150-250/mo with 3-4 web instances + Redis + S3

**For 5,000 req/sec (Twitter-scale):**
- ~$400/mo+ with 10 instances + Pro DB + Redis + CDN — don't build now

---

## My recommendation for YOU

1. **This week (launch Ijede):** **Stay on Supabase, but upgrade to Pro $25**. You already have it working, you need no pausing, daily backups, PITR. Change Render plan Free→Starter $7. Total $32/mo.

2. **Next month (when you have 2nd hospital):** Decide:
   - If you want single vendor + lower latency → migrate to Render Postgres Standard $20 + HA $7 (total $27 DB) — use guide above.
   - If you want built-in Storage + pooler + Studio UI → stay Supabase Pro and add Supabase Storage for files (move from `STORAGE_BACKEND=db`).

3. **Before >1 web worker:** Add PgBouncer or ensure Supabase pooler is used. Set `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` env vars (now in `render.yaml`).

**Bottom line:** Yes, Render Postgres Basic ~$7/mo is sound and cheap, and consolidating removes Supabase-sleeps bug. Caveat: no pooler, so add one before >1 worker. For now, upgrade Supabase to Pro is equally professional and more cost-efficient because you get pooler + dashboard + 8 GB.

---
**Next:** See `docs/SUB_PROCESSORS.md` for vendor list, `DATA_RESIDENCY.md` for residency statement
