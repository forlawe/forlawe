# Independent Technical Audit — Hospital Admin Manager Suite
**Auditor:** senior engineer / PM review · **Date:** 2026-08-14
**Scope:** repo `Hcarepro2026/hositalsuite` @ `452cf73`, live app `hospital-suite.onrender.com`

---

## 0. Verdict in one paragraph

This is a genuinely good build — far above what "vibe-coded solo founder project" usually means.
116/116 tests pass on a clean clone, 80% line coverage, the live site is up and correct,
security fundamentals (CSRF, RBAC, rate limits, hash-chained audit, magic-byte upload checks,
scrypt hashing, forced password change) are actually implemented, not just claimed.
**But it is not yet safe to run a real hospital's data on.** There are 4 blocking issues —
two of them *data-loss / legal* class — and a set of production gaps that will bite the moment
a real patient uses it. Fix the P0 list (≈1–2 days of work) before any pilot with real patients.

**Scores (honest):**

| Area | Score | Note |
|---|---|---|
| Feature completeness vs spec | 9/10 | Genuinely broad; MVP definition-of-done is basically met |
| Code quality / structure | 8/10 | Clean Flask monolith, right call for this context |
| Test discipline | 8/10 | 116 tests, 80% cov, real HTTP-level tests |
| Security | 6/10 | Good primitives, 3 real holes (below) |
| Production readiness / ops | 4/10 | **This is the weak leg.** Ephemeral disk, no real backup, no migrations tool |
| Legal / data protection (NDPA) | 3/10 | No consent, no privacy policy, no retention job, no DPO/DSR path |
| Docs / handover | 9/10 | HANDOFF/ROADMAP/DEPLOYMENT are unusually good |

---

## 1. 🔴 P0 — Fix before ANY real patient data

### P0-1. Uploads, PDFs and backups live on Render's ephemeral disk → they disappear
`Config.UPLOAD_DIR`, `REPORT_DIR`, `BACKUP_DIR` all resolve to `data/` inside the container.
`render.yaml` declares **no disk**. Every deploy or restart (Render free spins down after
15 min idle) **permanently deletes**: complaint photo evidence, inspection evidence photos,
hospital logo, every generated PDF, and every "nightly backup".

Confirmed live: `GET /branding/logo` → **404** even though the login page renders the `<img>` —
the founder already uploaded a logo and the file is already gone. That's the symptom, in production, today.

**Fix (pick one):**
- Cheapest correct: store uploads/PDFs as bytes in Postgres (`BYTEA`) — you already have Supabase.
- Better: Supabase Storage (free tier, S3-compatible) behind a small `storage.py` interface.
- Stopgap: regenerate PDFs on demand instead of persisting them (they're deterministic).

### P0-2. "Nightly backup" is a no-op in production
`job_nightly_backup()` returns immediately if the URI isn't SQLite. Production is Postgres.
So **there is no backup at all** — and the code/docs say there is. That's the most dangerous
kind of gap: a false sense of safety.

**Fix:** enable Supabase's own daily backups (free tier = 7 days, verify on your plan) AND add a
weekly `pg_dump` → off-site copy. Change the docs to stop claiming backups work. Test a *restore*
once — an untested backup is not a backup.

### P0-3. Session cookie is not marked Secure; no HSTS; no CSP
`SESSION_COOKIE_SECURE` is never set. Over HTTPS-only Render it's low-risk today, but any
http:// hop leaks a live session. No `Strict-Transport-Security`, no `Content-Security-Policy`.

**Fix (10 lines in `config.py` / `security.py`):**
```python
SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"   # 0 for local dev
# in security_headers():
resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
resp.headers.setdefault("Content-Security-Policy",
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
```

### P0-4. Rate limiting is per-`remote_addr`, but there's no ProxyFix → every user looks like one IP
Behind Render/Cloudflare, `request.remote_addr` is the **proxy**, not the patient. Two consequences:
1. Audit-log IPs are useless (all identical) — weakens the tamper-evident trail's forensic value.
2. Rate limits are effectively **global**: I confirmed live that 8 failed logins from me returned
   `429` for everyone after that. One bad actor (or one busy hospital Wi-Fi) locks out the whole
   hospital from `/login`, `/complaint`, `/book`.

**Fix:**
```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```
…and prefer `CF-Connecting-IP` when present. Also add a per-*username* login throttle
(currently only per-IP; and there is **no account lockout** — brute force is only IP-limited).

---

## 2. 🟠 P1 — Fix before charging money / signing a hospital

| # | Issue | Why it matters | Fix |
|---|---|---|---|
| P1-1 | **No NDPA/NDPR consent checkbox** on `/complaint`, `/book`, `/feedback`, `/chat`. No privacy policy page, no data-subject-request path, no named DPO. | Nigeria's NDPA 2023 applies. Health data is sensitive-category. A hospital's legal officer will stop the deal here. | Add a consent checkbox + `/privacy` page + a "delete my data" request route. Half a day. |
| P1-2 | **`retention_days` setting exists but nothing enforces it.** No purge job. | You promise 6-year retention; in reality you keep forever. Contradiction in an audit. | Add `job_retention_purge` to the scheduler (soft-delete + anonymise, audit-logged). |
| P1-3 | **No anonymous complaint option.** Every complaint is attributable. | Staff-related complaints (the highest-value signal) won't be filed if the patient must identify themselves. | Add an "submit anonymously" toggle; keep the ref number so they can still track it. |
| P1-4 | **`db.create_all()` + a hand-rolled `migrate.py`** as the migration strategy. | It works today (13 hardcoded columns). It will silently break on the first column *type* change or rename, on live patient data. | Adopt Alembic now while the DB is small. One afternoon. |
| P1-5 | **Single point of failure: Render free plan.** Cold start measured at **21.5 seconds** on my first request. | A patient scanning a QR at the hospital gate waits 21s and leaves. Render also states free is not for production. | $7/mo Starter kills cold starts and gives you a persistent disk. This is the single highest-ROI ₦ you can spend. |
| P1-6 | **Multi-tenancy is app-layer only; public portals resolve org via `Organization.order_by(id).first()`** (`feedback.py:29`, `bookings.py:23`, `main.py:108`). | The moment you onboard hospital #2, every public patient page serves hospital #1's branding/departments. The "multi-tenant" claim is currently false for public routes. | Resolve tenant from subdomain / `?h=<org_code>` / QR-location code before any second tenant. |
| P1-7 | **7 stray cookie files committed to the repo** (`t.txt`, `u.txt`, `adm3.txt`, `fin.txt`, `pub.txt`, `md2.txt`, `lang.txt`) containing **real signed Flask session cookies**. | They're localhost-scoped and expired-ish, so low real risk — but it's exactly the habit that leaks a production cookie later. `.gitignore` even tries to exclude two of them *after* they were committed. | `git rm` all 7, keep the .gitignore rules. |
| P1-8 | **The GitHub PAT you pasted in chat (`ghp_…` (the one pasted in chat)) is now burned.** | Anyone with that message has push access to your repo. | **Revoke it right now** at github.com/settings/tokens. Never paste a token into a chat again — create a fresh 7-day one when needed. I used it read-only and pushed nothing. |

---

## 3. 🟡 P2 — Quality / maintainability (do at leisure)

- **`admincp.py` is 883 lines, 57% covered** — the least-tested, most-privileged file in the app.
  Split into `admin/users.py`, `admin/structure.py`, `admin/settings.py` and add tests for the
  destructive paths (delete department, suspend user, change role).
- **`whatsapp.py` 54% / `seeddata.py` 58% / `scheduler.py` 62% coverage.** The scheduler is the
  thing that runs unattended at 2am; it deserves the *most* tests, not the fewest.
- **21 `print()` calls vs 5 logger calls.** On Render, `print` works but is unstructured. Move to
  `app.logger` with JSON-ish formatting so you can actually grep an incident.
- **Chatbot retrieval is naive substring keyword matching** (`engine.py::_score`). It works because
  you brute-forced 1,059 triggers, but it's O(articles × keywords) per message and will mis-fire on
  paraphrase. When you have budget: swap `_articles_for` + `_score` for Postgres full-text
  (`tsvector`/`ts_rank`) — zero new infra, big accuracy jump. Keep the clinical guardrail exactly as is;
  that part is well done.
- **No dependency pinning** (`Flask>=3.0` etc.). A breaking upstream release will break a deploy at
  the worst moment. `pip freeze > requirements.lock` and install from the lock.
- **No CI.** You have 116 good tests that only run when someone remembers. Add a 15-line GitHub
  Actions workflow — free, and it's the cheapest quality upgrade available.
- **Load-test numbers are honest but not representative**: 4,000 req/min was measured with the
  load generator *on the same box* and rate limits disabled, against SQLite/local PG. Real Supabase
  over the network will be slower. Re-run against production before quoting the figure to a customer.

---

## 4. What is genuinely strong (don't let anyone rewrite this)

- **The architecture choice is right.** Server-rendered Flask monolith, no SPA, ~17KB CSS — correct
  for Nigerian mobile networks. Resist any advice to "rewrite in React".
- **Hash-chained audit log with a verify endpoint and a thread lock** — that's real engineering,
  and it's the feature a hospital board will actually care about.
- **`insert_with_unique_ref` + DB-level partial unique indexes for idempotency** — you found a real
  race under load and fixed it properly at the database layer. Well done.
- **Clinical guardrail in the chatbot** with a Pidgin variant — legally and ethically the single most
  important line of code in the product.
- **Forced password change + AUTO_SEED bootstrap** as a workaround for Render free having no shell —
  pragmatic and correct.
- **Documentation and handover quality** is better than most funded startups I've reviewed.

---

## 5. Recommended order of work (my call as PM)

**This week (P0 — ~2 days):**
1. Revoke the GitHub token. (5 min)
2. ProxyFix + Secure cookie + HSTS + CSP + per-username login throttle. (2 h)
3. Move uploads/logo/PDFs off the ephemeral disk (Supabase Storage or Postgres BYTEA). (1 day)
4. Turn on Supabase backups, do one restore drill, delete the false backup claims from docs. (2 h)
5. `git rm` the 7 cookie files. (5 min)

**Next week (P1 — ~3 days):**
6. Consent checkbox + `/privacy` + data-deletion request route + retention purge job.
7. Alembic migrations.
8. Upgrade Render to Starter ($7/mo) — kills the 21s cold start.
9. Tenant resolution for public portals (before hospital #2).
10. GitHub Actions CI running the 116 tests.

**Then, and only then**, pick from the pending feature menu. Adding AI service-recovery or
attendance geo-fencing on top of an app that loses its uploaded files on every restart is
building the second floor before the foundation is poured.

**Strategic note:** you are one paying pilot away from validating this. The fastest path to that
pilot is *not* more features — it's being able to answer a hospital administrator's three questions:
"Where is our data stored?", "What happens if it's lost?", and "Are we compliant with NDPA?"
Right now the honest answers are "on a disk that gets wiped", "it's gone", and "not yet".
Fix those three and you have something sellable.
