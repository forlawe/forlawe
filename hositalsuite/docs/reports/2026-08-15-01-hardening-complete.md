# Hardening Pass Complete — v1.2.0

**Date:** 2026-08-15 · **Commit:** `d3bcb32` (pushed to `main`)
**Tests:** 116 → **142 passing** (verified on a fresh clone from GitHub)

---

## ⚠️ ONE THING YOU MUST DO — 30 seconds

**Render is not auto-deploying.** The code is on GitHub and verified, but the live site is
still running the old version. Go to your Render dashboard → `hospital-suite` →
**Manual Deploy** → *Deploy latest commit*.

Then confirm it worked by opening:
`https://hospital-suite.onrender.com/api/v1/health`

You should see `"scheduler"` and `"last_backup"` in the response. If you only see
`{"database":true,"status":"ok","whatsapp_mode":"sandbox"}`, the old version is still live.

**Also still outstanding (I cannot do these for you):**
- **Revoke the GitHub token** you pasted in chat — github.com/settings/tokens
- **Enable CI** — see `ci/README.md` (5-minute copy-paste; the token I had lacked the scope to do it)
- **Turn on Supabase backups** — Supabase → Database → Backups
- **Upgrade Render to Starter ($7/mo)** — kills the 21-second cold start

---

## P0 — fixed

### 1. Your files were being deleted on every restart
Uploads, generated PDFs, the hospital logo and "backups" were written to Render's ephemeral
disk. **This was already causing damage:** `/branding/logo` returned 404 in production
because your uploaded logo had been wiped.

Everything now goes through `app/storage.py` and lives in the database. A boot-time sweep
rescues any files still sitting on disk. *(27 files were rescued on the first local run.)*

### 2. You had no backups at all
`job_nightly_backup()` returned immediately unless the database was SQLite. Production is
PostgreSQL, so the nightly job ran every night and did nothing — while the admin screen and
the docs both said backups existed.

New `app/backup.py` works on any engine: every table exported to CSV, zipped with a manifest
and restore instructions, retained and downloadable. **I ran a real restore drill** and
confirmed the archive contains genuine, reloadable data.

### 3. Missing transport security
Added `Secure` session cookies, HSTS (HTTPS only), and a full Content-Security-Policy.

### 4. Rate limits were global, audit IPs were useless
Behind Render/Cloudflare every visitor shared the proxy's IP. I confirmed live that 8 bad
logins from me returned 429 — which would have locked out the entire hospital.

Added ProxyFix + `security.client_ip()`, plus a **per-username lockout** (10 failures →
15 minutes). Verified with a simulated distributed attack: **10 attempts from 10 different
IPs**, where the IP limiter never fired but the account correctly locked.

---

## P1 — fixed

| # | Item | What changed |
|---|---|---|
| 1 | NDPA consent | Consent checkboxes on complaint/booking/feedback, enforced server-side |
| 2 | Retention | `retention_days` finally enforced by a purge job that anonymises (statistics survive) |
| 3 | Anonymous complaints | New option; stores no phone, sends no messages — the highest-value complaints |
| 4 | Migrations | Alembic, auto-applied at boot; baseline is safe on your existing database |
| 5 | Cold start | Documented; needs the $7/mo upgrade (your call) |
| 6 | Multi-tenancy | Public portals resolve their own hospital instead of always serving the first |
| 7 | Cookie jars | 7 files with real session cookies removed; `.gitignore` widened |
| 8 | Token | Advice corrected; **you still need to revoke it** |

Plus: `/privacy` notice, `/privacy/request` data-rights flow, and a staff screen to fulfil
access/erasure requests with real erasure and identity-verification warnings.

---

## Crash-proofing (your "prevent all crashes" requirement)

- **Global exception handler** — no traceback ever reaches a patient; the DB session is
  rolled back so one bad request can't poison the next.
- **Guarded boot** — a failing seed or knowledge-base step can no longer take the site down.
- **Scheduler survives anything** — catches `BaseException` with backoff. It runs SLA
  escalation; silent death meant complaints stopped escalating with nobody noticing.
- **Health endpoint** now reports database, **scheduler liveness**, and last backup time.
- **Memory limits** — `MAX_CONTENT_LENGTH` and a 2,000-row import cap, so an oversized
  upload can't OOM a 512 MB instance.
- **Verified**: crawled all 61 routes as admin, MD and anonymous — **zero 5xx errors**.

### Two additional bugs I found while working

1. **WhatsApp report delivery was silently broken.** It required an absolute filesystem path,
   so once PDFs moved to storage every MD/CEO inspection report would have quietly downgraded
   to text-only. Caught by writing the test first.
2. **Audit logs recorded the proxy IP.** Fixed to use the real client IP, restoring the
   forensic value of your tamper-evident trail.

---

## Honest notes

- **CSP uses `'unsafe-inline'`.** The templates contain inline `<style>`/`<script>` blocks.
  Removing that needs a refactor I judged too risky to bundle here. Still a large improvement
  over no CSP; worth tightening later.
- **`admincp.py` is still 883 lines at ~57% coverage.** I added tests for the new data-request
  code but did not split the file — that's a P2 refactor, not a safety fix.
- **Load-test numbers are still unverified against real Supabase.** Re-run before quoting them.
- **`ensure_schema()` still runs after Alembic** as a deliberate belt-and-braces fallback.
  Once you trust the migrations, it can go.

---

## Where you stand

You can now answer the three questions that were blocking a pilot:

- *"Where is our data?"* → In PostgreSQL, with files stored durably, not on a disk that gets wiped.
- *"What if it's lost?"* → Nightly backups that actually run, downloadable, with a tested restore path.
- *"Are we NDPA compliant?"* → Consent, privacy notice, retention enforcement, and a working
  data-rights process. *(Have a lawyer review the privacy notice before signing anything.)*

Read **`OPERATIONS.md`** — it's the plain-English runbook: what to do monthly, how to read the
health check, how to handle a deletion request.
