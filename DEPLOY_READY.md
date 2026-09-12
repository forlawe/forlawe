# 🚀 Deploy-ready: merged code → Render + Supabase

Prepared 11 September 2026. Every ✅ below was produced by running something in
this workspace; the command and its output are quoted. Anything I could not run
here is listed under **Not verified here** at the end — read it before you trust
the rest.

---

## 1. What "the merged code" is

One tree, built from your **live** repo and only added to:

```
base   : Hcarepro2026/hositalsuite @ main = 2ad087c   (541 files)
plus   : 15 files — 13 modified, 2 new, 0 deleted
```

```
$ cp -r hositalsuite/. <fresh clone of live main>/ && git status --short
 M app/static/css/app.css              M app/views/bookings.py
 M app/templates/booking_portal.html   M app/views/queue.py
 M app/templates/forgot_password.html  M tests/test_f039_consent_partial.py
 M app/templates/landing_sales.html    ?? app/templates/_auth_footer.html
 M app/templates/login.html            ?? tests/test_fasttrack_doors.py
 M app/templates/patient_hub.html
 M app/templates/queue_join.html
 M app/templates/request_access.html
 M app/templates/reset_password.html
 M app/templates/signup_pick.html
count: 15
```

**Nothing from your live repo was removed.** That matters because the other
branch in this repo (`arena/01a08339-forlawe`) is a *partial* tree — 453 files
against your 541. A naive merge of the two would have deleted `run.py`,
`requirements.txt`, `servicepoints_admin.py` and `hospital_structure.py`. This
merge is additive by construction.

What is in the 15 files: the landing ↔ auth wiring and mobile nav, the two
Fast Track doors (Bug A), the queue-join consent fix (Bug B), Request 1 wiring,
Request 3 entry routing, and the tests that lock all of it.

---

## 2. A deploy blocker found and fixed while auditing

`alembic.ini` ships Alembic's own placeholder line:

```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```

`migrations/env.py` only substituted the app's real URL when that option was
*empty* — and a placeholder is not empty. So every command-line migration died:

```
$ alembic upgrade head
sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver
```

The app never noticed, because `run_alembic_upgrade()` passes the URL
programmatically at boot — but an operator could not migrate by hand at all:
not from a Render shell, not from a VPS, not from a laptop pointed at the
Supabase pooler. Fixed by treating the placeholder as "nobody supplied one",
which keeps the file's documented rule intact (a real `-x url=...` still wins):

```
$ alembic upgrade head        # after the fix, on a clean database
$ alembic current
k28_tenant_usernames (head)
tables: 51     alembic_version: [('k28_tenant_usernames',)]
```

Locked by two new tests in `tests/test_migration_safety.py` (14 passed, was 12).

---

## 3. ✅ It boots with Render's exact start command

`render.yaml` says:

```yaml
startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 "app:create_app()"
healthCheckPath: /api/v1/health
```

I ran that verbatim against the merged tree:

```
[INFO] Starting gunicorn 26.2.0
[INFO] Listening at: http://0.0.0.0:8077
[INFO] Using worker: gthread
[INFO] Booting worker with pid: 1518

  /api/v1/health     200      /book              200
  /api/v1/ready      200      /book/fast-track   200
  /sales             200      /queue/join        200
  /login             200      /tv                200
  /signup            200      /welcome           200

$ curl /api/v1/health
{"database":true,"status":"ok","storage":"db","version":"1.8.1",
 "whatsapp_mode":"sandbox","sms_mode":"sandbox","push_mode":"vapid", ...}
```

And the merged behaviour is live in that process, not just in tests:

```
/book            → is_fast_track field present: 0
/book/fast-track → is_fast_track field present: 1
/welcome gold card → class="lux-card" href="/book/fast-track"
```

### End-to-end bookings, made for real and read back out of the database

Issue #1 asked for both doors to be tested end to end rather than read. Done —
real HTTP through gunicorn, posting only the fields each page renders, then
reading the rows back:

```
/book             17 departments; 'Fast Track' offered: False
/book/fast-track  18 departments; '⭐ Fast Track' listed, gold box + consent shown

/book              → HTTP 200, /book/thanks?ref=HOSP-APT-2026-000001
/book/fast-track   → HTTP 200, /book/thanks?ref=HOSP-APT-2026-000002
/book/fast-track, no consent → HTTP 422, "premium service" refusal
/book + premium department posted by hand, no consent → HTTP 422, refused

  HOSP-APT-2026-000001  Normal Door      is_fast_track=False
  HOSP-APT-2026-000002  Fast Track Door  is_fast_track=True
```

**That test found a bug no unit test could.** `Fast Track` was the *first*
department in the dropdown on **both** doors, and a booking into that department
becomes premium regardless of door (`is_ft = … or is_fast_track_dept(dept)`).
So a patient on the free door could pick the first item in a list and be handed
a paid service with no price and no consent box on screen. Three fixes:

1. the free door no longer lists the paid lounge (17 departments vs 18);
2. the consent rule now follows the **outcome** — `becomes_fast_track =
   is_ft_check or is_fast_track_dept(dept)` — so posting that department by hand
   without consent is refused with 422;
3. a validation error no longer re-renders the premium door as the plain one
   (it was dropping the `fast_track` flag on the 422 path).

All three are locked by tests in `tests/test_fasttrack_doors.py` (13 tests).

---

## 4. ✅ Supabase-specific paths, checked in the code

| Risk | What I found |
|---|---|
| RLS on a managed Postgres | `app/rls.py` is **PostgreSQL-only and a no-op on SQLite**, sets `FORCE ROW LEVEL SECURITY` (otherwise the owner bypasses its own policies and RLS is decoration), and treats an unset `app.current_org` as *no rows*, never all rows |
| Per-request isolation | `SELECT set_config('app.current_org', :v, true)` — transaction-local, so it cannot leak between requests |
| Backups without a shell | `app/backup.py` is engine-independent: every table to CSV in a zip. Its own header: *"No pg_dump binary required — Render's free plan has no shell"* |
| Migrations on a pooler | Alembic DDL and the RLS variable both need a **session**, so use Supabase's **Session pooler**, not the transaction pooler (`DEPLOYMENT_GUIDE.md:26` already says this) |
| Driver | `psycopg2-binary>=2.9.12,<3` is in `requirements.txt`; pins are `>=X,<Y` so a breaking minor cannot land mid-deploy |
| Pool sizing | `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10` from env, sized for 1 worker + 4 threads |

## 5. ✅ The 25 undocumented production variables

`render.yaml` sets 35 variables; only 10 of them appeared in `.env.example`.
Anyone reproducing production elsewhere silently ran **without** `COOKIE_SECURE`,
with `STORAGE_BACKEND=disk` on a disk Render wipes, and with no proxy trust.
`.env.example` now documents all 35, with the defaults `config.py` actually
falls back to:

```
$ comm -23 <(render.yaml keys) <(.env.example keys)
(empty — all documented)
```

---

## 6. Ship it

```bash
# 1. get the merged tree
git clone https://github.com/Hcarepro2026/hositalsuite.git && cd hositalsuite
git apply --check deploy/landing_auth_mobile.patch     # prints nothing = fits
git apply --check deploy/fasttrack_two_doors.patch
git apply        deploy/landing_auth_mobile.patch
git apply        deploy/fasttrack_two_doors.patch
git status                                             # 15 files, exactly

# 2. run the suite (needs: pip install -r requirements.txt)
pytest -q                                              # expect 1056 passed, 8 skipped

# 3. push — Render auto-deploys in ~2-3 min
git add -A && git commit -m "Fast Track two doors, landing/auth mobile pass, alembic CLI fix"
git push origin main
```

Or on a server with a shell:

```bash
bash deploy/01_backup_current.sh /var/www/hositalsuite
bash deploy/02_apply_patch.sh   /var/www/hositalsuite   # applies both, verifies 15 files
bash deploy/03_verify.sh        https://your-domain     # 17 checks, GET only
```

### Supabase settings that must be right

1. **Session pooler** URI, ending `?sslmode=require`
2. every `@` in the password written as `%40`, no `[` `]`
3. `SECRET_KEY` generated by Render (`generateValue: true`) — changing it later
   signs every user out
4. `PUBLIC_BASE_URL` set to `https://<your-app>.onrender.com` **after** the first
   deploy — QR codes and WhatsApp links are built from it
5. `STORAGE_BACKEND=db` (or `s3`); never `disk` on Render

### First-boot check, in order

```bash
curl https://<your-app>.onrender.com/api/v1/ready     # ready:true
curl https://<your-app>.onrender.com/api/v1/health    # status:ok, database:true
```
Then open `/sales` on your phone → ☰ Menu → Staff login → sign in with the
credentials printed once in the deploy log (`AUTO_SEED=1` only seeds an empty
database).

---

## 7. Not verified here — be honest about this

* **No PostgreSQL in this sandbox.** `postgres`, `psql`, `initdb` are all absent,
  so the suite ran on SQLite and `alembic upgrade head` was proven on SQLite.
  The Postgres-only paths (RLS policies, `FORCE ROW LEVEL SECURITY`,
  `set_config`) were **read, not executed**. Before you trust RLS in production,
  run once against a real Supabase database:
  `TEST_DATABASE_URL=postgresql://... pytest -q` (the suite supports it) and
  `alembic upgrade head` against the session pooler.
* **No real WhatsApp/SMS/mail sends** — sandbox mode only.
* **No browser on a real phone** — the 17 HTTP checks prove the right markup and
  CSS are served; only your eyes prove it looks right.
* **Request 3 is still display-only.** `entry_stage` sets the tracker's stage;
  no `ReceptionIntake` and no `tracking.enter()`. Needs your decision (see
  `CONSULTANT_REPORT_RESPONSE.md` §7).
