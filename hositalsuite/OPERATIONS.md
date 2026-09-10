# Operations Runbook — plain English

This is the "something is wrong, what do I do" guide. No jargon. If you only read
one section, read **§1 Backups**.

---

## 1. Backups — the most important thing in this document

**Where they are:** Admin → Backups. One is made automatically every night at 2 a.m.

**What you must do — 15 minutes a month:**

1. Go to Admin → Backups.
2. Click **Download** on the newest one.
3. Save it somewhere that is NOT this server — Google Drive, a laptop, a USB stick.
4. Write the date in a notebook.

**Once every three months**, do a *restore drill*: ask a technical person to load the
backup into a spare database and confirm the data appears. This takes an hour and it is
the only way to know your backup actually works. Instructions are inside every backup
file (`RESTORE.txt`).

> An untested backup is not a backup. Hospitals have lost years of records to a backup
> that turned out to be empty.

**Also turn on your database provider's own backups** (Supabase → Database → Backups).
Two independent copies is the standard; this app's backup is the second one, not the first.

---

## 2. "The site is slow the first time I open it"

On the free hosting plan the app goes to sleep after 15 minutes of no visitors. The next
person to open it waits **around 20 seconds** while it wakes up.

A patient standing at the hospital gate scanning a QR code will not wait 20 seconds.

**Fix:** upgrade the Render plan to Starter (about $7/month). This is the single most
valuable money you can spend on this system. Nothing in the code needs to change.

---

## 3. "A staff member is locked out"

After 10 wrong passwords an account locks for 15 minutes. This is deliberate — it stops
someone guessing their way into patient data.

**What they should do:** wait 15 minutes, or use **Forgot password** on the login page
(it sends a code to their phone). No admin action needed.

If they are still stuck, a Super Admin can reset the password in Admin → Users.

---

## 4. "Is the system healthy?"

Open: `https://your-site.onrender.com/api/v1/health`

You will see something like:

```json
{"status": "ok", "database": true, "scheduler": true,
 "last_backup": "2026-08-15T02:00:11", "storage": "db"}
```

| Field | Good value | If it's wrong |
|---|---|---|
| `status` | `ok` | anything else = something below is broken |
| `database` | `true` | the database is unreachable — check Supabase is up |
| `scheduler` | `true` | **reminders and complaint escalations have STOPPED** — restart the app |
| `last_backup` | within the last ~24h | backups are not running — check the logs |

`scheduler: false` is the quiet killer: the site looks fine, but nobody gets duty
reminders and overdue complaints never escalate to the MD. Restarting the app fixes it.

---

## 5. "A patient asked us to delete their data"

They can do it themselves: the **Privacy** link at the bottom of every page →
"Make a data request".

You will see it in **Admin → Patient Data Requests**. Open it, and:

1. **Verify who they are first** — call the number back, or ask them at reception for a
   complaint reference only they would know. Do not skip this. Someone could otherwise
   erase another patient's complaint.
2. Click **Erase** (or **Give them their copy** for an access request).

Erasing replaces the name, phone and description with `[erased]`. Ratings and dates stay,
so your statistics stay correct. **It cannot be undone.**

The law gives you **30 days** to respond. Requests older than 21 days are flagged in red.

---

## 6. "Someone complained anonymously — can we call them back?"

No, and that is the point. Anonymous complaints store no phone number at all. Staff
conduct issues are the most valuable complaints you will ever receive and patients will
not file them if they can be identified.

They still get a reference number and can check the status themselves.

---

## 7. Deploying a change

1. Push to `main` on GitHub.
2. GitHub Actions runs all 142 tests automatically (see the Actions tab — green tick = safe).
3. Render deploys automatically.
4. Database changes apply themselves at startup. You do not need a shell.
5. Check `/api/v1/health` afterwards.

**If a deploy fails:** Render keeps the previous version running. Nothing is lost. Read the
deploy log, fix, push again.

---

## 8. Where the files are

Uploaded photos, generated PDFs and backups are stored **inside the database**, not on the
server's disk. This is deliberate: the hosting disk is erased on every restart, and files
stored there disappear (this happened to the hospital logo before it was fixed).

Never change `STORAGE_BACKEND` away from `db` unless someone has attached a real
persistent disk and understands the consequences.

---

## 9. Security settings you should not change

| Setting | Value | Why |
|---|---|---|
| `COOKIE_SECURE` | `1` | stops login sessions leaking over plain HTTP |
| `TRUSTED_PROXY_COUNT` | `1` | without it, one visitor's bad behaviour blocks everyone |
| `STORAGE_BACKEND` | `db` | files survive restarts |
| `RATE_LIMIT_SCALE` | `1` | only ever raised for load testing — never in production |
| workers | `1` | the scheduler must run exactly once, or reminders send twice |

---

## 10. Emergency contacts checklist

Fill this in and print it:

- Hosting (Render) login: ____________________
- Database (Supabase) login: ____________________
- Domain registrar: ____________________
- SMS provider (Termii) account: ____________________
- Who to call if the site is down: ____________________
- Where the latest downloaded backup is kept: ____________________
