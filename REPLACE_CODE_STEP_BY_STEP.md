# 📲 Step by step — feel it here, then put it on your hospital suite

Written 10 September 2026. Everything below was **run and verified in this
workspace**, not described from memory. Where a command produced a number, the
number is printed next to it.

---

## 0. First, an honest correction — what was actually true

You asked me to confirm that the sign-up/login page was connected to the landing
page and that everything was mobile-optimised. I checked the workspace before
claiming anything:

| What I checked | Command | Result |
|---|---|---|
| How many commits exist here | `git log --all --oneline \| wc -l` | **1** |
| What files exist in the repo | `find . -mindepth 1 -maxdepth 2 -not -path './.git*'` | **only `hositalsuite-main (2).zip`** |

So: **nothing had been built in this workspace before this turn.** There was no
edited landing page, no edited login page — just the zip you uploaded. I was
wrong to let that stand as if the work existed. What I did instead, this turn:

1. Unpacked your zip into `hositalsuite/` (581 files, 8.5 MB).
2. Installed the dependencies and ran **your own test suite**: `1044 passed,
   8 skipped` in 16m42s — so the baseline you uploaded is green.
3. Audited the landing ↔ auth wiring and the mobile CSS by reading the real
   files and the running app, and **fixed the four real gaps** (§2).
4. Started the app so you can feel it right now (§1).
5. Cut a patch + scripts so you can move exactly those fixes onto your live
   hospital suite (§3–§6).

---

## 1. Feel it yourself, right now

The app is **running in this workspace** as a live preview on port 8077.

Open the preview and go to:

| Page | URL path | What to look at |
|---|---|---|
| Sales landing | `/sales` | Resize to phone width (or open on your phone) → tap **☰ Menu** |
| Staff login | `/login` | The new row under the card: *← CareQueue home · Patient view* |
| Staff sign up | `/signup` | Same footer; the form itself is unchanged |
| Patient hub | `/welcome` | What a patient sees (no login needed) |
| Health | `/api/v1/health` | `{"status":"ok"...}` — what Render pings |

**Demo logins** (seeded with `python run.py demo`, printed by the seeder):

| Role | Username | Password |
|---|---|---|
| System Admin | `admin` | `Admin#2026!` |
| MD / CEO | `md` | `Mdceo#2026!` |
| HOD Medicine | `hod.medicine` | `Hodmed#2026!` |
| HOD Pharmacy | `hod.pharmacy` | `Hodpharm#2026!` |

First login forces a password change (that is the app behaving correctly — it
redirects to `/change-password`; I confirmed the redirect: `POST /login → 302
→ /change-password`).

<details>
<summary>If the preview is not running, start it again with these exact commands</summary>

```bash
cd /home/user/forlawe

# 1. dependencies (the .venv folder is not kept between sessions here)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r hositalsuite/requirements.txt

# 2. demo data — prints the logins above (already done once; safe to skip)
cd hositalsuite
SECRET_KEY="workspace-preview-key" DATABASE_URL="sqlite:///data/app.db" \
  ../.venv/bin/python run.py demo

# 3. run it (binds 0.0.0.0:8077 so the preview proxy can reach it)
SECRET_KEY="workspace-preview-key" DATABASE_URL="sqlite:///data/app.db" \
PORT=8077 DISABLE_SCHEDULER=1 ../.venv/bin/python -u run.py
```
</details>

### Phone test script — 6 taps, 2 minutes

1. `/sales` on your phone → the top bar shows **CareQueue · Set up · ☰ Menu**
   (before this fix the menu links simply vanished under 900px).
2. Tap **☰ Menu** → the drawer drops down: Features, How it works, Why CareQueue,
   Pricing, FAQ, then **Set up my hospital / Staff login / Staff sign up /
   Patient view**. Every row is ≥46px tall (thumb-sized).
3. Tap **Staff login** → the login card, with *← CareQueue home* beneath it.
4. Tap **← CareQueue home** → you are back on `/sales`. This link did not exist
   before; the browser Back button was the only way out.
5. Go back to `/login`, tap **Sign up** → sign-up form.
6. Pinch-zoom: the gold buttons at the bottom of `/sales` are now full width and
   stack — no half-width buttons, no sideways scrolling.

---

## 2. What was actually wrong, and what I changed

Audited by reading the real files (line numbers are from your uploaded copy):

| # | Problem found | Where | Fix |
|---|---|---|---|
| 1 | `@media(max-width:900px){.nav-links{display:none}}` — on a phone the whole menu disappeared with **no hamburger to replace it** | `landing_sales.html:73` | Real `<button class="nav-toggle">` + `#nav-drawer`, with `aria-expanded`/`aria-controls`, Esc-to-close, auto-close on resize, 46px targets |
| 2 | `.nav-cta` (Patient view + Set up hospital) was never adjusted for small screens; with `body{overflow-x:hidden}` it was **clipped off the right edge** on a 360px phone | `landing_sales.html:71` | Compact always-visible **Set up** button next to the hamburger; the full CTA set lives in the drawer |
| 3 | The landing page linked to `/login` and `/start` but **never to staff sign-up** | footer line 504 | `Staff sign up → /signup` added to the drawer **and** the footer *Hospitals* column |
| 4 | From `/login`, `/signup`, `/forgot-password`, `/reset-password` there was **no way back to the landing page** | 5 auth templates | New shared partial `_auth_footer.html` (uses `url_for()`, so a rename fails loudly instead of rotting into a 404) |
| 5 | Notched phones: `viewport-fit=cover` was requested but no `env(safe-area-inset-*)` padding anywhere on these pages | landing + auth | Safe-area padding on the sticky nav, the footer and `.login-wrap` |
| 6 | CTA buttons stayed half-width on phones | `.cta .btns`, `.ctas` | Stack full-width under 600px, 50px tall |

**Files changed: 7 modified + 1 new = 8 files, +139 / −5 lines.** No Python
changed → no database migration, no `.env` change, no restart of anything but
the web process.

```
 app/static/css/app.css             |  15 +++++
 app/templates/_auth_footer.html    |  10 ++++   (new)
 app/templates/landing_sales.html   | 114 ++++++++++++++++++++++++++++++---
 app/templates/login.html           |   1 +
 app/templates/request_access.html  |   1 +
 app/templates/signup_pick.html     |   1 +
 app/templates/forgot_password.html |   1 +
 app/templates/reset_password.html  |   1 +
```

**What was already correct and I deliberately left alone:** `/login ⇄ /signup ⇄
/forgot-password` were already cross-linked; the dashboard/`base.html` already
had a hamburger (`.nav-toggle` at `app.css:367`); the login card was already
phone-safe (`max-width:min(410px,calc(100vw - 32px))`); the landing page already
had 12 responsive breakpoints and `clamp()` typography.

---

## 3. The three ways to get this onto your hospital suite

Pick **one**. Route A is the one your setup is built for.

| Route | Use it if | Time | Risk |
|---|---|---|---|
| **A — GitHub → Render** | Your live app is `Hcarepro2026/hositalsuite` on Render (it is) | 5 min | Lowest. Render keeps the previous deploy for one-click rollback |
| **B — patch script on a VPS** | You run it yourself on a server with a shell | 5 min | Low. `01_backup` first, `git apply --check` before writing |
| **C — copy the 8 files by hand** | No git, no shell — e.g. cPanel/FTP | 10 min | Medium. Easy to miss one file |

Everything lives in **`/home/user/forlawe/deploy/`**:

```
deploy/landing_auth_mobile.patch   the 8-file change, as a git patch
deploy/01_backup_current.sh        code + database backup
deploy/02_apply_patch.sh           dry-run, then apply, then confirm
deploy/03_verify.sh                17 live checks, safe on production (GET only)
```

---

### Route A — GitHub → Render (recommended)

```bash
# --- on your computer, in a folder where you keep the code ---
git clone https://github.com/Hcarepro2026/hositalsuite.git
cd hositalsuite
git checkout main && git pull

# copy the patch file from this workspace into the repo folder, then:
git apply --check deploy/landing_auth_mobile.patch   # must print nothing
git apply        deploy/landing_auth_mobile.patch
git status                                            # exactly 8 files listed

# run the tests locally if you can (optional but wise)
pip install -r requirements.txt && pytest -q        # expect: 1044 passed, 8 skipped

git add -A
git commit -m "Landing page: mobile nav drawer, staff sign-up links, auth pages link back"
git push origin main          # Render auto-deploys in ~2-3 min
```

Or use your existing one-command helper (it takes a token as an argument and
does not store it): `bash push.sh <YOUR_NEW_TOKEN>`.

**Then verify the deploy:**

```bash
bash deploy/03_verify.sh https://hospital-suite.onrender.com
```

Expect `passed: 17  failed: 0`. If `/api/v1/ready` is not 200, check the Render
log before doing anything else.

---

### Route B — patch script on a VPS / your own server

```bash
# 0. get the deploy/ folder and hositalsuite/ folder from this workspace onto
#    the server (scp, or git pull if you pushed them)

# 1. BACK UP — never skip this
bash deploy/01_backup_current.sh /var/www/hositalsuite
#    → writes ~/hospital-suite-backups/<timestamp>/{code.tar.gz,app.db,.env}

# 2. REPLACE — dry-runs first, refuses to write if the patch does not fit
bash deploy/02_apply_patch.sh /var/www/hositalsuite

# 3. RESTART the web process (templates are read per request; app.css is
#    cache-busted by ?v=app_version, so restart to be safe)
sudo systemctl restart hospital-suite      # or:  kill -HUP <gunicorn master pid>

# 4. PROVE IT
bash deploy/03_verify.sh https://your-domain.example
```

**Rollback (30 seconds):**

```bash
tar -xzf ~/hospital-suite-backups/<timestamp>/code.tar.gz -C /var/www/hositalsuite
sudo systemctl restart hospital-suite
```

---

### Route C — copy the 8 files by hand

From **`hositalsuite/`** in this workspace, copy these to the same paths on your
server (overwrite):

```
app/static/css/app.css
app/templates/_auth_footer.html          ← NEW FILE, easy to forget
app/templates/landing_sales.html
app/templates/login.html
app/templates/request_access.html
app/templates/signup_pick.html
app/templates/forgot_password.html
app/templates/reset_password.html
```

Then:

```bash
# on the server — confirm the new file really arrived
grep -c nav-toggle   app/templates/landing_sales.html   # must be > 0
grep -c auth-footer  app/templates/login.html           # must be 1
ls -l              app/templates/_auth_footer.html     # must exist
# restart, then
bash deploy/03_verify.sh https://your-domain.example
```

---

## 4. ⛔ What you must NOT copy

These are **your live data and secrets**, not code. Copying them over
production loses real patient records or logs everyone out.

| Never copy | Why |
|---|---|
| `data/` (app.db, uploads/, backups/) | Patient records, evidence photos, logos |
| `.env`, `.secret_key` | DATABASE_URL, SECRET_KEY, Twilio/Termii/Meta keys. A new SECRET_KEY signs out every user and invalidates sessions |
| `vapid_keys.json`, `*.pem` | Web-push keys — replacing them silently kills push notifications |
| `cookies.txt`, `adm*.txt`, `*.cookies` | Old signed session cookies (your `.gitignore` already blocks these) |
| `.venv/`, `__pycache__/` | Rebuilt per host |
| Anything in this workspace's `hositalsuite/data/` | **Demo data** — `Lagos City Teaching Hospital` and the `admin / Admin#2026!` accounts. Must never reach production |

The patch in `deploy/` cannot touch any of these — it contains only the 8 files
above. `02_apply_patch.sh` runs `git apply --check` first and aborts if your
files have drifted.

---

## 5. Proof it works — what I actually ran

| Check | Command | Result |
|---|---|---|
| Your test suite, **before** my edits | `pytest -q` | **1044 passed, 8 skipped** (16m42s) |
| Your test suite, **after** my edits | `pytest -q` (full suite, background) | **1044 passed, 8 skipped** (17m19s) — identical, nothing broken |
| Tests covering the files I touched | `pytest -q tests/test_nav_links_resolve.py tests/test_navigation.py tests/test_a11y_pass.py tests/test_founder_ux.py tests/test_smoke.py tests/test_phone_look.py tests/test_patient_hub.py tests/test_onboard.py tests/test_accounts_login.py` | **74 passed** |
| Patch fits a pristine copy of your zip | `git apply --check` then `git apply`, then `diff -q` | applied cleanly; result **byte-identical** to this workspace |
| Live page checks | `bash deploy/03_verify.sh http://127.0.0.1:8077` | **passed: 17, failed: 0** |
| Real login round trip | `curl -c jar /login` → POST with CSRF → follow | `POST /login → 302 /change-password` (correct first-login behaviour) |
| Pages return 200 | `curl -o /dev/null -w %{http_code}` on `/sales /login /signup /welcome /api/v1/health /api/v1/ready` | all **200** |

Not verified here, and you should check it on the real deploy:
- PostgreSQL behaviour (this sandbox ran on SQLite; `TEST_DATABASE_URL` runs the
  suite against Postgres if you want that before you push).
- Real WhatsApp/SMS/Termii/Twilio sends — sandbox mode only here.
- How it looks on **your** actual phone. The 17 checks prove the markup and CSS
  are served; only your eyes prove it looks right.

---

## 6. If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Page still looks old | Cached file | Hard-refresh / private window; `grep -c nav-toggle app/templates/landing_sales.html` on the server; restart the service |
| `git apply` refuses | Your copy drifted from the zip this patch was cut against | Stop. Send me `diff -u app/templates/landing_sales.html …` and I will re-cut the patch |
| Menu button does nothing | Inline JS blocked | The script carries `nonce="{{ csp_nonce }}"` — confirm the template was copied whole, not pasted in fragments |
| 500 on every page | SECRET_KEY / DATABASE_URL overwritten | Restore `.env` from the backup folder, restart |
| Render deploy red | Unrelated build failure | Render → Deploys → **Rollback** to the previous deploy; the change is 8 template/CSS files, it cannot break the build |

---

## 7. What I would do next (not done yet)

1. `POST /signup` end-to-end on the real domain (needs SMTP/Resend configured to
   send the 6-digit code).
2. Move the landing page's inline `<style>` (~230 lines) into a cached static
   file — one less thing to re-download on a slow hospital connection.
3. Add `/signup` to `test_nav_links_resolve.py`'s strict `url_for()` list so the
   landing nav can never regress to a raw string.
4. Lighthouse run on a real phone at 3G, once it is on the live domain.
