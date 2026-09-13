# Live go-live issues — 2026-09-13 (Render: hospital-suite-forlawe.onrender.com)

Reported by the owner after the Render go-live, diagnosed and fixed the same
day. All three were verified against a local rig running **real PostgreSQL
16.2 + gunicorn + AUTO_SEED** — the same stack Render runs.

## Issue 1 — every tab/card on the patient welcome page returns the same error page

**Live evidence** (fetched 2026-09-13):

```
GET https://hospital-suite-forlawe.onrender.com/book
→ "Something went wrong on our side. The technical team has been notified."
```

**Root cause**: the live deployment runs `main`, which does not yet contain
the PostgreSQL/RLS fixes (POSTGRES_VERIFICATION.md finding 2.7). On
PostgreSQL, a mid-request commit drops the transaction-local tenant scope,
so the next org-scoped query on a patient page returns nothing / raises —
every patient door 500s. SQLite (the test engine) never showed it.

**Fix**: already in this branch (per-transaction tenant re-stamping,
`app/rls.py`). Verified on the rig — every hub destination now returns 200:

```
GET /welcome -> 200      /book -> 200        /book/fast-track -> 200
/book/status -> 200      /chat -> 200        /complaint -> 200
/complaint/status -> 200 /feedback -> 200    /queue/join -> 200
```

## Issue 2 — no hospital phone number on the page; emergency link goes nowhere

**Live evidence**: the welcome page's emergency card shows only
"📞 Help desk numbers below", and the help desk section says
"Please ask at the hospital reception desk" — **no numbers anywhere**.

**Root cause**: two layers.

1. `AUTO_SEED` created the hospital with `phone = NULL`
   (`Organization(code=…, name=…)`) — and the emergency card only shows a
   call link when `hospital.phone` exists, so every number silently
   vanished from the page.
2. The emergency card had no place where the number is **visible as text**
   attached to the emergency button (owner requirement).

**Fixes** (this branch):

- `app/templates/patient_hub.html` — the emergency card now shows
  **"📞 Call now: {number}"** and the alternate number as red call buttons
  directly beside the "🚑 I'm coming to A&E — register me now" button, with
  the actual digits visible. The help-desk block at the bottom keeps both
  numbers as `tel:` links (tapping dials).
- `app/seeddata.py` — `AUTO_SEED` now takes the hospital's numbers from the
  environment: set `SEED_HOSPITAL_PHONE` (and optionally
  `SEED_HOSPITAL_PHONE_ALT`) on Render before the first boot.
- For an **already-seeded** live database (this case): once login works,
  set the numbers in **Admin CP → hospital settings → phone / phone_alt**.

**Verified on the rig** (seeded with `SEED_HOSPITAL_PHONE="0803 123 4567"`,
`SEED_HOSPITAL_PHONE_ALT="0803 765 4321"`):

```
GET /welcome -> 200
  Call now: 0803 123 4567          ← visible on the emergency card
  href="tel:…" × 5                 ← both numbers dialable
  0803 123 4567 / 0803 765 4321    ← both visible as text
```

Regression tests added in `tests/test_fasttrack_doors.py` (numbers visible
+ dialable when set; graceful reception fallback when not) and
`tests/test_autoseed.py` (env-seeded phone lands on the org). All pass on
PostgreSQL and SQLite.

## Issue 3 — /login refuses the first-boot random password

**Root cause**: the live deployment runs pre-fix code, where the login
lookup is blinded by row-level security on PostgreSQL (same class as
issue 1). Additionally, the random passwords are printed **once**, in the
**Render service log of the very first boot** ("FIRST-RUN SETUP COMPLETE")
— a password from any other environment's log will never work.

**Fixes**:

- The branch's RLS fixes make login work on PostgreSQL. Verified on the
  rig with the printed first-boot password:

```
POST /login (admin + first-boot password) -> 302 -> /change-password
GET  /change-password                     -> 200   (forced first-login change)
```

- New `tools/reset_password.py` — the founder's way back in if the log is
  gone: from the Render dashboard open the service **Shell** and run

```
python tools/reset_password.py admin
```

  which prints a new strong password (or pass your own as the second
  argument). It runs under the cross-hospital RLS scope and clears any
  brute-force lockout on the account.

## What the owner needs to do

1. **Merge this PR** — Render will redeploy `main` with all fixes.
2. Find the first-boot passwords: Render dashboard → the service →
   **Logs** → search `FIRST-RUN SETUP COMPLETE`. (Or use
   `tools/reset_password.py` in the Shell.)
3. Log in as `admin`, set a new password when asked.
4. **Admin CP → hospital settings**: enter the real emergency numbers
   (phone + phone_alt). They appear on the welcome page immediately.

## Also fixed in this branch (from the PostgreSQL verification milestone)

The 11 findings in `POSTGRES_VERIFICATION.md` — migrations that silently
rolled back, RLS gaps, the scheduler that never ticked on PostgreSQL,
backups that silently lost every user account, field encryption that would
crash registration, and more. The live deployment currently has **all** of
them.
