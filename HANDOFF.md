# HANDOFF — Hospital Admin Manager Suite ("Patient Experience OS")

**GENERAL HOSPITAL IJEDE (The Family Hospital)**
Last updated: **18 August 2026** · Code at: **`191872d`** (local, NOT pushed) · Status: **live and healthy**

> **Paste this whole file into a new chat as your first message.** It contains
> everything needed to carry on without repeating work.

---

## 0. READ THIS FIRST (for the next assistant)

### What this app IS
A **patient-experience system**. It exists so that a visit to the hospital
feels calm, quick, respectful and well-organised — for the patient, and for
the staff looking after them.

### What this app IS NOT
**It is NOT an EMR / medical record.** No diagnoses, no vital signs, no
prescriptions, no test results, no blood group, no genotype, no allergies.

> The founder had to correct me on this once already, and he was right.
> I had added blood group, genotype and allergies to the patient folder with a
> red "⚠ do not miss" banner for doctors. All removed. There is now a test —
> `test_the_folder_holds_no_medical_record` — that **fails the build** if any
> EMR column reappears. Do not weaken it.

### The founder
- **Zero technical background. Solo. Zero budget.** Explain everything in plain
  English, use tables, never jargon. Reports are written for him, not engineers.
- He tests on an **Android phone via Render screenshots**. Design mobile-first.
- Standing instructions, in his own words:
  - *"help me analyse and evaluate with honesty. Recommend or make suggestion where necessary."*
  - *"Check every built and make sure there are free from bug, gap, crash etc. Don't move to next item until the one you are working on is completely fix or resolved."*
  - *"don't forget voice reminder"* — voice is a **standing requirement of every feature**, not an extra.
  - He asked for **"premium plus plus quality and standard"** and an MVP-SaaS mindset (per-tenant settings, never per-deploy).
- **Always end a work batch with a numbered menu of pending features** so he can choose what's next.
- Present a `.md` report via `present_file` at the end of each batch.

### Working rules that have repeatedly proved their worth
1. **Verify, never assume.** Prove every fix with real evidence: tests, live
   `curl`, headless-browser assertions.
2. **Mutation-test your own tests.** Deliberately break the code and confirm the
   test fails. This has caught a *useless* test twice — see §7.
3. **Full suite must pass on BOTH SQLite AND real PostgreSQL 17 before every push.**
4. **Never edit a migration that has already been deployed.** This caused a
   total production outage on 16 Aug. Always add a NEW migration.
5. Round up cleanly when context runs low — leave things pushed and working.

---

## 1. Live system

| Thing | Value |
|---|---|
| Live site | https://hospital-suite.onrender.com |
| Repo | https://github.com/Hcarepro2026/hositalsuite (branch `main`) |
| Current HEAD | `5828bae` |
| Health (always 200) | `/api/v1/health` |
| Readiness (503 on trouble) | `/api/v1/ready` — now also detects **schema drift** |
| Host | Render free tier (auto-deploys on push, ~2–3 min) |
| Database | Supabase PostgreSQL, project ref `YOURPROJECTREF` |
| Monitoring | UptimeRobot on `/api/v1/health` (98%+ uptime) |
| Hospital phone | `09154967034`, alt `09154967041` |
| Referral link format | `https://hospital-suite.onrender.com/r/E9D1042F` |

**Push command** (token has `repo` scope only — **no `workflow` scope**, so
`.github/workflows/` cannot be created; CI lives at `ci/github-actions-tests.yml`
with `ci/README.md` explaining 5-minute manual activation):

```
git push https://Hcarepro2026:<TOKEN>@github.com/Hcarepro2026/hositalsuite.git main
```

> ⚠️ **The token `ghp_82Db…` has been exposed in chat repeatedly and the founder
> has been asked several times to revoke it. Ask again. If he has rotated it,
> get the new one before attempting a push.**

---

## 2. Environment setup (sandbox wipes these between sessions)

```bash
cd /home/user/hs
pip3 install -q -r requirements.txt

# PostgreSQL 17 (REQUIRED before pushing)
sudo apt-get install -y -q postgresql
(sudo service postgresql start || sudo pg_ctlcluster 17 main start)
sudo -u postgres psql -q \
  -c "DROP ROLE IF EXISTS hms;" \
  -c "CREATE ROLE hms LOGIN PASSWORD 'hms_test_pw';" \
  -c "DROP DATABASE IF EXISTS hms_test;" \
  -c "CREATE DATABASE hms_test OWNER hms;"

# Playwright (for browser checks)
pip install -q playwright && python -m playwright install --with-deps chromium
```

**Run the suite on both engines:**
```bash
python3 -m pytest -q                                    # SQLite
TEST_DATABASE_URL='postgresql://hms:hms_test_pw@127.0.0.1:5432/hms_test' python3 -m pytest -q
python3 tools/check_links.py                            # every link/form resolves
python3 tools/hims_browser_check.py                     # 20 checks
python3 tools/roster_browser_check.py                   # 21 checks
```

**Sandbox quirks (all learned the hard way):**
- Only `/home/user` persists. Working clone is `/home/user/hs`.
- pip packages, PostgreSQL and Playwright are **wiped between messages**.
- Heredocs via `bash` sometimes fail to write files — use the `write_file` tool.
- Single quotes in commit messages break `-m`; write to `/tmp/mN.txt`, use `git commit -F`.
- Git identity is not set: use `git -c user.email=... -c user.name=... commit`.
- `git worktree prune` before re-adding a wiped path.
- Supabase direct `db.` host is IPv6-unreachable from Render — **must** use the
  Session pooler URL; the password contains `@` which must be encoded `%40`.

---

## 3. CURRENT STATE: 353 tests, green on both engines

| Metric | Value |
|---|---|
| Tests | **583 passing** on SQLite **and** real PostgreSQL 17 |
| Test files | 34 in `tests/` |
| Migrations | 9 in `migrations/versions/` (head = `a8e31c4f9b56`) |
| Browser checks | HIMS 20/20 · Roster 21/21 |
| Link checker | Clean |

---

## 4. WHAT HAS BEEN BUILT ✅

### Patient-facing
- **Patient hub** (`/`, `/welcome`) — six numbered colour-coded tiles: Book,
  Queue, Assistant, Complaint, Feedback, Share. Native share sheet + WhatsApp
  fallback. `?loc=` / `?ref=` carried through. **EN / Yorùbá / Hausa / Igbo.**
- **Booking** (online + physical), **Queue tickets**, **Feedback**, **Complaints**
  (incl. anonymous), **Referral links** with tracking.
- **AI patient assistant** — 458 intents / 7,559 triggers, 31/31 department
  coverage, English + Pidgin. AI ladder **Groq → Gemini → OpenRouter** (all
  free tier, no card). Guardrails before *and* after the model. Per-tenant daily
  cap (400) and metering.
- **NDPA compliance** — consent capture, privacy page, data-subject requests,
  retention purge, anonymisation.

### Stage A — HIMS Register ✅ (`/hims/`)
The patient folder — the thing every later stage hangs on.
- **Search first**, always: by hospital number, phone, surname, first name, or
  "surname firstname" in either order.
- **Open a folder**: identity · contact · next of kin (**required**) · payment
  route · how to look after them.
- **Hospital numbers** auto-assigned per tenant: `IJE/2026/00001`.
- **Duplicate prevention** — shows likely existing folders and forces a tick-box
  override before creating a second one.
- **Never invents a birthday** — accepts a stated age honestly.
- **Payment routes**: LAHSMA (Lagos State insurance) · **Megalex** (Lagos State
  revenue system) · Self-pay · NHIS · HMO · Exempt. LAHSMA/NHIS/HMO **must**
  have a scheme number or Billing cannot claim.
- **Patient-experience fields** (NOT medical): preferred language (EN/YO/HA/IG),
  assistance needed (wheelchair, offer a seat, hard of hearing, poor sight,
  walks with difficulty, carer, interpreter), free-text care note.
- **Visits** — `PatientVisit` moves REGISTERED → TRIAGED → IN_CONSULTATION →
  ONWARD → CLOSED. Columns for clinic / consulting room / doctor **already
  exist and are unused**, so Stages B–D add behaviour, not another migration.
- Age auto-corrects category: under 12 → CHILD, 65+ → ELDERLY (Triage needs this).
- Folder retire (hides, never deletes), edit, CSV export.

### Voice ✅ (`app/announce.py`)
Previously **totally silent** — four independent causes found and fixed.
Now speaks. Real captured sentences:
- *"Team, Abatan has been registered and is waiting for Triage."*
- *"Mr Tunde, 3 patients are waiting at the drug dispensary. Please attend to them."*
- **URGENT:** *"Team, Abatan at the reception desk needs help. Needs a wheelchair; Prefers Yorùbá — greet them in it; travels from Ikorodu"*
- *"…is back with us at reception. Please welcome them."*

Design: assistance needs get their **own urgent call**; registering ahead of
time announces nothing (so voice never becomes ignorable noise). Goes to both
personal devices and shared station screens. Audio-unlock banner handles the
browser rule that blocks sound until first tap.

### Roster ✅ (`/roster`) — merged into ONE page
Previously two pages that couldn't see each other.
- Scope: **Admin Manager (hospital-wide) · Department · Section · Unit**
- Date ranges: today · 7 days · 2 weeks · 3 weeks · 30 days · this month · custom
- **4 working patterns**: two 12h shifts · one 24h duty · three 8h shifts ·
  **office hours Mon–Fri** (for Procurement, Audit, Finance, ICT, Admin/HR)
- **Unlimited staff per shift** (was hard-capped at 2)
- **8 leave types** — annual, casual, sick, study, maternity, compassionate,
  exam, off duty. A date range expands to one row per day.
- **Leave blocks duty** — refuses to roster someone who is on leave, and says which leave.
- Office departments **refuse weekend duty**.
- Bulk upload with per-row preview and plain-English rejection reasons; CSV export.
- Legacy rows **copied** (not moved) into the unified table at boot; old
  `/dept-roster` URL redirects so bookmarks still work.

### Staff & admin
- **8 roles**: SUPER_ADMIN, MD_CEO, DMD, DCST, APEX_NURSE, HEAD_ADMIN_HR,
  ADMIN_MANAGER, HOD.
- **Bulk staff upload** — parses the founder's real nominal roll (`MEDICAL`,
  `PUB AFF OFF`, `FIN/ACCTS`, `NUTRIT&DIET`), generates usernames, random
  one-time passwords shown once, accounts start unapproved + must-change-password.
- **31 standard departments**, idempotent installer button.
- Departments with HOD name + phone (mandatory), sections, units.
- Admin Manager daily inspections, scoring, corrective actions, SLA escalation,
  reports centre with PDF + verification codes, audit log with hash chain.

### Production hardening
- Durable DB-backed storage (Render's disk is ephemeral and was wiping uploads).
- Real backups (engine-independent CSV-in-zip, restore drill performed).
- Secure cookies, HSTS, CSP, ProxyFix, per-IP + per-username login lockout.
- `connect_timeout=5`, degraded-mode boot, health always 200, self-healing scheduler.
- Alembic migrations auto-apply at boot.
- **`/api/v1/ready` now detects schema drift** and reports exactly which columns are missing.

---

## 5. WHAT IS PENDING ⬜

### The patient flow — the founder's own words
> 1. Booking — i. Online booking, ii. Physical Booking
> 2. HIMS Register — i. open folder for new/first visit patient, ii. Search for the folder of returning patient
> 3. Triage — Place patient to the OPD/SOPD/MOPD/EMERGENCY according to available doctors, patients needs, Patients Categories, Day of the week, Clinics of the day etc
> 4. The TRIAGE Assign Patients on the QUEUE to doctors in the consulting room 1, 2, 3, 4, or Emergency
> 5. The Doctors — The doctors on duty and also ready to work by clicking to consult would see patients assigned to them from TRIAGE (the Call Room Queue)
> 6. The Doctor after attending to the patient would now push the patient to one, two or three out of the following (LAHSMA/Billing/Megalek/Laboratory/Pharmacy/Emergency)

| Stage | Status |
|---|---|
| Booking | ✅ built |
| **Reception (front door)** | ✅ **built 18 Aug** — details, special needs, insurance, then Billing → Pay-Point |
| **Billing Point** (`/billing`) | ✅ **built 18 Aug** — its own screen, its own queue |
| **Megalex / Pay-Point** (`/paypoint`) | ✅ **built 18 Aug** — separation of duties: the cashier records the money, not the receptionist |
| **A — HIMS Register** | ✅ built (special needs moved OUT to Reception) |
| **B — Triage** | ✅ **built 18 Aug** — OPD/SOPD/MOPD/EMERGENCY, doctor rooms, blood sugar step |
| **⚠ Rule** | A doctor's queue shows patients named to them **AND** unassigned patients in **their own clinic**. Triage may place with no doctor; if the queue only matched `doctor_id == me` those patients are stranded in nobody's room. Guarded by `test_a_doctor_sees_unassigned_patients_waiting_in_their_clinic`. |
| **C — Call Room Queue** | ✅ **built 18 Aug** — `/consulting-room`: call a patient in, finish the consultation |
| **D — Onward routing** | ✅ **built 18 Aug** — `/onward`: Lab / Pharmacy / Billing / Megalex / LAHSMA / Emergency, one two or three at a time |
| **E — Voice throughout** | ✅ the FULL journey speaks: front door → "safe journey home" (14 call-outs, all free) |

**Monitoring engine (`/tracking`)** measures every stage: door-to-door time,
per-department efficiency, live "who is waiting where", week-on-week trend,
busiest hours, and plain-English allocation advice. Two rules to respect:
1. **Tracking may NEVER break care.** Every write is guarded twice and wrapped
   in a SAVEPOINT (PostgreSQL aborts a whole transaction on any failed
   statement — without the savepoint a tracking fault killed the patient work
   that came after it). Guarded by
   `test_a_broken_tracking_engine_never_stops_a_patient_being_seen` and
   `test_a_failed_tracking_write_does_not_poison_the_transaction`.
2. **The engine SPEAKS** (voice is a standing requirement): `job_patient_flow`
   in the scheduler closes abandoned stretches and announces a forgotten
   patient or a bottleneck department. Deliberately quiet otherwise — an alert
   that fires constantly is ignored within a week.
3. **Never roll back inside tracking** — the caller's un-committed patient work
   shares that session and would be silently discarded.

**The patient journey is now unbroken end to end.** Verified live: one patient
walked Reception → Billing → Pay-Point → HIMS → Triage → Room 2 → Lab →
Pharmacy → Billing → home, and the visit closed itself only after the third
desk finished.

**Name rule:** `Patient.full_name` is register order (`ABATAN Folake`) for
folders and lists. **`Patient.spoken_name` (`Folake Abatan`) is what every
voice call-out must use** — otherwise Reception says "Folake" and the doctor
says "Abatan" about the same woman. Guarded by
`test_a_patient_is_called_the_SAME_name_at_every_step`.

**AI assistant:** Groq was DEAD (retired model + a KB that never fell through
to it). Fixed 17 Aug — see `docs/reports/`. Pinned to `openai/gpt-oss-120b`
(PRODUCTION tier). Do **not** set `GROQ_MODEL` in Render; the tested default
lives in the code.

### ⬅ START HERE: Stage B — Triage (scope agreed with founder, awaiting his "go")

**Founder's clarifications (verbatim):**
- *"LAHSMA — Lagos state owned health insurance and Megalex — is a private payment system that help all Lagos state owned hospitals to collect revenue"*
- *"Call Room Queue is a queue waiting to see a particular doctor in one of the consulting rooms"*
- Doctor availability: **both rostered AND clicked "ready to consult"**
- Who hears voice: **both personal devices and station screens**

| ✅ DO build | ❌ Do NOT build |
|---|---|
| Place patient into **OPD / SOPD / MOPD / Emergency** | Any symptom or clinical scoring |
| Use category, day of week, clinic of the day, available doctors | Vital signs, temperature, blood pressure |
| Show **and speak** waiting counts and wait times | Any diagnosis or clinical notes |
| **Announce patients by name** when it's their turn | |
| Carry wheelchair / seat / language flags forward from the folder | |

`PatientVisit` already has `clinic`, `consulting_room`, `doctor_id`,
`triaged_at`, `seen_at` — **use them; no new migration should be needed.**
`app/announce.py` already defines `triage_backlog`, `consult_ready`,
`queue_assigned`, `emergency_arrival`, `patient_waiting_long`.

### Other outstanding items
| # | Item | Notes |
|---|---|---|
| 1 | **Role Management** | Requirement #1 of the original 9 — the only one not delivered. Roles are a fixed tuple; there is **no `Role`/`Permission` table** and no UI to create/edit roles or change permissions. |
| 2 | **Leave approval workflow** | Leave is *recorded* in the roster; there is no request → approve → balance system. |
| 3 | Cross-department roster clash warning | Same nurse rostered by two HODs on the same night — each only sees their own list. |
| 4 | Link existing bookings & queue tickets to patient folders | They still hold loose name/phone. Natural fit with Stage B. |
| 5 | Roster auto-fill | "Cover the next 30 days with these 6 nurses", fairly. |
| 6 | CSP still uses `'unsafe-inline'` | Templates carry inline `<style>`/`<script>`. Deliberate; future work. |
| 7 | `admincp.py` ~883 lines, ~57% coverage | Least-tested, most-privileged file. P2 refactor. |
| 8 | Load-test figures (4,000 req/min) never re-verified | Not re-run against real Supabase over the network. |
| 9 | Patient folder has no photograph | Not requested; free-tier storage cost. |
| 10 | HIMS search doesn't handle misspellings | `Abatam` won't find `Abatan`. Phone number always works. |
| 11 | No bulk import of an existing paper patient register | Every folder is opened at the desk. Ask if there's a backlog. |

---

## 6. FOUNDER'S OUTSTANDING ACTIONS (chase these)

| # | Action | Why it matters | Time |
|---|---|---|---|
| 1 | **Revoke GitHub token `ghp_82Db…`, issue a new one with `repo` AND `workflow`** | Exposed in chat many times. Anyone with it can push code that auto-deploys to patients. **Most urgent.** Adding `workflow` also unlocks CI. | 2 min |
| 2 | **Confirm HIMS now loads** (it was 500-ing; fixed in `48b0de1`) | Needs his eyes on a real phone | 2 min |
| 3 | Add a **second UptimeRobot monitor on `/api/v1/ready`** | Health says "alive"; ready says "actually working". Would have caught the 500 automatically. | 3 min |
| 4 | Add `GROQ_API_KEY` in Render | Turns on the smarter assistant. Free, no card. | 5 min |
| 5 | Enable Supabase backups (Database → Backups) | Second safety net | 2 min |
| 6 | Enable CI per `ci/README.md` | Tests run on every change | 5 min |
| 7 | Press "Add any missing standard departments" (Admin → Structure) | Installs all 31 | 1 min |
| 8 | Set admin departments to **"Office hours, Mon–Fri"** | Procurement, Audit, Finance, ICT, Admin/HR rosters then behave correctly | 5 min |
| 9 | Test the **voice** on his phone (tap screen once to unlock audio) | Browsers block sound until first touch | 3 min |

---

## 7. HARD-WON LESSONS — do not repeat these

### The production outage (15 Aug) — 5 causes, all fixed
Unbounded DB connect (no timeout → 130s boot → health check killed every
container) · disk-rescue retried per file · every boot step retried a dead DB ·
**my own bug: `/api/v1/health` returned 503 when the DB was down, and
`render.yaml` used it as `healthCheckPath`, so Render read it as "deploy failed"
and killed every deploy for hours** · scheduler thread died with no recovery.
Result: 130s+ hang → 5.6s boot with a black-holed DB.

### The HIMS 500 (16 Aug) — the migration lesson
I removed EMR columns by **editing a migration that had already run in
production**. Alembic saw the revision as applied and skipped it, so the live
database never gained the new columns. Every `/hims/` request died with
`column patient.preferred_lang does not exist`.

**Rule: an applied migration is immutable history. Fixes go in a NEW migration.**

Found while fixing it: **`migrations/env.py` was silently overwriting the
caller's database URL**, so `alembic upgrade head` against a chosen database
migrated a *different* one while logging "Running upgrade…". Any verification
done that way proved nothing. Fixed.

### Tests that pass but prove nothing — **the most important lesson here**
Twice now, a guard test **passed against the very bug it was written to catch**:
- The migration guard passed because the suite builds every database with
  `create_all()`, which always produces correct columns — so it never exercised
  the *upgrade* path, the only path that broke.
- `tests/conftest.py` **hard-coded `DATABASE_URL` to SQLite**, so every previous
  claim of "passes on PostgreSQL" was false. The first genuine PostgreSQL run
  immediately failed a test issuing a SQLite `PRAGMA`.

**Always mutation-test: break the code deliberately and confirm the test fails.**
`tests/test_migration_safety.py` now builds a database in the exact shape
production was in, stamps it at the old revision, and runs the real upgrade.

### Other bugs worth remembering
- Voice was **totally silent** for 4 independent reasons (no patient event was
  speakable; `speak()` called a function on the wrong object; quiet hours
  defaulted to 22:00–07:00 silencing night shift; browsers block audio until a tap).
- **Ephemeral disk** wiped every upload/PDF/logo on restart → `app/storage.py`.
- **Backups silently did nothing on PostgreSQL** → `app/backup.py`.
- **Rate limits were global** (no ProxyFix) — 8 bad logins locked out everyone.
- **Bulk upload role bug**: "Deputy Medical Director" matched `md` inside
  "MEDical" → would have granted a deputy the MD's authority.
- **Chat gave wrong answers** — substring matching fired `"are you"` inside
  "what **are you**r opening hours".
- **KB sync never updated existing intents** — improved wording was dead on
  arrival in production.
- **Open redirect** via `startswith("/")` allowing `//evil.com`.
- **404s from template/route mismatches** → built `tools/check_links.py`; run it every time.

### The September 2026 independent review — three lessons, all fixed
1. **A secret typed into a report is committed.** The VAPID *private* key was
   written into `HOSPITAL_ASSISTANT_WORLD_CLASS_REPORT.md` in the same
   patchset that added `vapid_keys.json` to `.gitignore` — the ignore rule
   protects runtime files, not prose. Removed; `tests/test_secrets_hygiene.py`
   now fails the build if it (or any PEM/VAPID-shaped key) reappears. The key
   itself must still be **rotated** — see
   `docs/SECURITY_INCIDENT_2026-09-03_VAPID_KEY_ROTATION.md`.
2. **Self-graded "✅ DONE" is not status.** The same session graded its own
   keyword filter "Prompt Injection Security DONE"; an external reviewer
   called it security theater and was right. The guardrail is now layered
   (phrase + intent regex + typo probe + separator/homoglyph squashing) with
   an adversarial suite — `tests/test_chatbot_guardrails_adversarial.py` —
   that pins BOTH catch-rate and a benign corpus. **Claims must point at
   tests, not at themselves.**
3. **Concurrent deploys race migrations.** Two Render instances ran
   `alembic upgrade` at once → `relation "service_clinic" already exists` →
   aborted transaction → the same failure every deploy, forever.
   `migrations/env.py` now takes a PostgreSQL advisory lock, and `g8h21`
   tolerates duplicate creates inside savepoints.

Related: the **Supabase egress blowout (424 GB / 5 GB)** that made all of the
above visible at once — runbook in `docs/SUPABASE_EGRESS_INCIDENT_2026-09.md`.

---

## 8. Key files

**Core:** `app/models.py` · `app/__init__.py` (boot steps, ProxyFix, error
handlers) · `app/config.py` · `app/security.py` · `app/migrate.py`

**Feature engines:** `app/hims.py` (Stage A) · `app/rosterdata.py` (roster) ·
`app/announce.py` (**voice — read this before Stage B**) · `app/storage.py` ·
`app/backup.py` · `app/bulkusers.py` · `app/standard_departments.py` ·
`app/chatbot/` (`engine.py`, `ai.py`, `seed_kb.py`, `kb_departments_full.py`)

**Views:** `app/views/hims.py` · `roster.py` · `api.py` (health/ready/alerts) ·
`admincp.py` · `main.py` · `queue.py` · `bookings.py` · `chat.py` · plus others

**Templates:** `app/templates/hims/{desk,register,folder}.html` ·
`roster.html` · `roster_upload_preview.html` · `patient_hub.html` · `base.html`

**Tools:** `tools/check_links.py` · `tools/hims_browser_check.py` ·
`tools/roster_browser_check.py`

**Key tests:** `test_hims.py` (43) · `test_migration_safety.py` (8) ·
`test_upgrade.py` (roster) · `test_voice_alerts.py` · `test_system.py` · `test_smoke.py`

**Docs:** `docs/reports/` (16 reports incl. `HIMS_500_FIX.md`,
`STAGE_A_CORRECTION.md`, `ROSTER_MERGE_REPORT.md`) · `OPERATIONS.md` ·
`AI_SETUP.md` · `ci/README.md`

---

## 9. Config reference

`STORAGE_BACKEND=db` · `COOKIE_SECURE=1` · `TRUSTED_PROXY_COUNT=1` ·
`LOGIN_MAX_FAILURES=10` · `LOGIN_LOCKOUT_MINUTES=15` · `LOG_LEVEL=INFO` ·
`MAX_CONTENT_LENGTH=8MB` · `DB_CONNECT_TIMEOUT=5` · `AI_FALLBACK=1` ·
`AI_TIMEOUT=8` · `AUTO_SEED=1` (seeds only an empty DB)

AI keys: `GROQ_API_KEY` / `GROQ_MODEL` (llama-3.3-70b-versatile) ·
`GEMINI_API_KEY` / `GEMINI_MODEL` (gemini-2.0-flash) · `OPENROUTER_API_KEY` ·
`AI_PROVIDER` · per-tenant `ai_fallback_enabled`, `ai_daily_cap` (400).

Free-tier limits: Groq 30 req/min · Gemini 15 req/min, 1,500/day · OpenRouter 50/day.

---

## 10. Suggested opening message for the new chat

> Continuing the Hospital Admin Manager Suite for GENERAL HOSPITAL IJEDE.
> Read HANDOFF.md in the repo first — it has full context.
>
> Code is at `5828bae`, 353 tests green on SQLite and PostgreSQL 17, site live
> and healthy. Stage A (HIMS Register) is done. **Next is Stage B — Triage**,
> scope already agreed in §5.
>
> Remember: this is a **patient-experience app, NOT an EMR**. Voice reminders
> are required in every feature. Explain everything in plain English.
