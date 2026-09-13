# 🐘 PostgreSQL verification — the milestone the consultant flagged

Prepared 13 September 2026. This is the follow-up the consultant asked for on
issue #1:

> One open item, not blocking: PostgreSQL/RLS paths still need to be exercised
> against real Postgres (not just SQLite) before this is trusted for
> production traffic — flagging for the next milestone, not this one.

Every ✅ below was produced by running something against a **real PostgreSQL
16.2 server** in this workspace; the command and its output are quoted. It
found **eleven real bugs** — ten fixed and locked with tests, one turned
into a loud warning — every one of them invisible on SQLite, which is
exactly why this milestone was worth doing before trusting production
traffic.

---

## 1. The rig

| production (Supabase + Render) | this verification |
| --- | --- |
| PostgreSQL | **PostgreSQL 16.2** (from the `pgserver` distribution — genuine server binaries), UTF8 encoding |
| `postgres` role: **not** a superuser, owns the schema | role **`hms_app`**: `NOSUPERUSER NOBYPASSRLS CREATEDB`, owns every table |
| TCP with `connect_timeout`/keepalives | TCP on 127.0.0.1:54329, same driver (`psycopg2` 2.9.13) |
| gunicorn start command from `render.yaml` | **the exact command**: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 "app:create_app()"` |
| `STORAGE_BACKEND=db` | same |

Two rig-only notes, for honesty: (1) the test-suite run uses a server tuned
with `fsync=off`/`synchronous_commit=off` — a throwaway database whose only
job is to make 1072 × drop-and-recreate-64-tables affordable; it changes
nothing about query or RLS semantics, and every other result in this document
was produced **before** that tuning was applied. (2) The gunicorn rig sets
`COOKIE_SECURE=0` because the driver speaks plain `http://` — that is the
documented setting for plain-HTTP local development; production keeps
`Secure` cookies.

## 2. What was broken — and is now fixed

### 2.1 ❌→✅ The migration chain died on real Postgres (`DEFAULT 0`)

```
$ alembic upgrade head                     # on a clean PostgreSQL database
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DatatypeMismatch)
column "is_fast_track" is of type boolean but default expression is of type integer
[SQL: ALTER TABLE patient_visit ADD COLUMN is_fast_track BOOLEAN DEFAULT 0]
```

SQLite accepts `0` as a boolean default; PostgreSQL refuses. The same disease
was in `k26_voices` (`night_mode`). Fixed with the dialect-aware idiom the
chain already used elsewhere (`"0" if sqlite else "false"`). Locked by
`test_no_integer_literal_server_defaults_in_migrations`.

### 2.2 ❌→✅ Migrations never COMMITTED on PostgreSQL — silently

The nastiest one. `migrations/env.py` takes a session-level advisory lock
before migrating (the Render double-boot race fix). Executing that lock
statement auto-begins a transaction, and Alembic then treats the connection
as externally managed: it **neither begins nor commits** anything. Every
migration ran… and was rolled back when the connection closed. Proof, with
statement logging enabled:

```
LOG:  statement: CREATE TABLE referral (…)
…
LOG:  statement: INSERT INTO alembic_version (version_num) VALUES ('246e2fd93e4f')
LOG:  statement: ROLLBACK          ← a fully successful run, thrown away
$ echo $?                                  # alembic upgrade head
0                                    ← and it claims success
```

On SQLite this cannot happen (the lock is skipped there), which is why the
earlier sandbox verification saw nothing. This affected **both** the CLI and
the app's boot migration path. Fixed by ending the lock's transaction
(`connection.commit()`) before `context.configure()` — the lock itself is
session-scoped and survives it. Locked by
`test_env_py_hands_alembic_a_clean_transaction`.

### 2.3 ❌→✅ k28's name-probing poisoned the transaction

`k28_per_tenant_usernames` tries candidate names when dropping the old global
username uniqueness, swallowing misses with `try/except`. On PostgreSQL a
missed DDL statement **aborts the whole transaction** — everything after it
fails with `InFailedSqlTransaction` until the version stamp finally raises.
Additionally, those uniques are INDEXES (`ix_user_username`,
`ix_login_attempt_username`), not constraints, so `drop_constraint` could
never remove them. Fixed with a SAVEPOINT per attempt (`begin_nested`) plus
index-aware reflection. Locked by `test_k28_probes_uniqueness_inside_savepoints`.

**Result** — the chain now completes on a clean database:

```
$ alembic upgrade head && alembic current
k28_tenant_usernames (head)
$ psql -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
51
```

### 2.4 ⚠️ RLS is invisible to superusers — now it says so

Connected as the cluster's default `postgres` (a superuser), **every RLS
enforcement test failed** — `CATASTROPHIC: a query with no org filter
returned another hospital's patients` — while the boot log cheerfully
reported `row-level security active on 43 table(s)`. PostgreSQL exempts
superusers and `BYPASSRLS` roles from every policy; `FORCE ROW LEVEL
SECURITY` only stops the table *owner*. Supabase's `postgres` role is not a
superuser, which is why production is safe — but a self-hosted deployment
using a default superuser account would have RLS that looks active and
protects nothing. `rls.enable()` now detects this and logs a loud warning
(`_bypassing_role()`), in the spirit of the module's own docstring. Locked by
`test_enable_warns_when_the_connection_role_can_bypass_every_policy`.

### 2.5 ❌→✅ The WhatsApp table had NO row-level security at all

`PROTECTED_TABLES` listed `whatsapp_message` — but the model class
`WhatsAppMessage` maps to a table Flask-SQLAlchemy names `whats_app_message`.
The list entry protected a table that does not exist; the real one, full of
patient phone numbers and message bodies, had no policy. Found by auditing
the list against `db.metadata`; fixed to the real name, and the must-cover
test now includes it.

### 2.6 ❌→✅ The boot silently seeded no roles and no branches

```
INFO [app] row-level security active on 44 table(s)
ERROR [app] boot step 'seed_roles' failed — continuing
psycopg2.errors.InsufficientPrivilege: new row violates row-level security policy for table "role"
```

`seed_roles` and `seed_branches` run **after** RLS is armed and write to
protected tables without declaring the cross-hospital intent the RLS module
prescribes for boot seeders (`all_orgs()`). The boot swallows the error, so
on a real production boot every hospital would come up without its built-in
roles (permission checks then fall back to the legacy hard-coded paths —
silently). Fixed: both steps now declare `all_orgs()`. Proof after the fix:

```
orgs=1  departments=32  users=10  roles=9  role_permissions=159  branches=1
```

### 2.7 ❌→✅ The patient doors were 500 on PostgreSQL

`/book`, `/book/fast-track` and `/queue/join` all returned **500** on
PostgreSQL while being 200 on SQLite:

```
sqlalchemy.orm.exc.ObjectDeletedError: Instance '<Department …>' has been deleted,
or its row is otherwise not present.
```

Mechanism: those views `db.session.commit()` between loading departments and
rendering (referral tracking). The commit (a) ends the transaction, and with
it the transaction-local tenant setting, and (b) expires the loaded objects.
The next attribute touch re-SELECTs the row in a **new, tenant-less**
transaction — and RLS, correctly, hides it. The tenant is now remembered once
per request (from the signed-in user) and **re-stamped onto every transaction
as it begins** (SQLAlchemy `after_begin` event), so no present or future
mid-request commit can reproduce this. The same fix covers the scheduler's
queue jobs, which crashed identically (`job_whatsapp_queue`,
`process_sms_queue`) once the scheduler itself was repaired (2.8) — via a new
greppable `rls.background_all_orgs()` declaration that also survives commits.
After the fix:

```
200  /api/v1/health        200  /book                200  /queue/join
200  /api/v1/ready         200  /book/fast-track     200  /tv
200  /sales /login /signup /welcome
```

### 2.8 ❌→✅ The scheduler never ticked — on any engine

```
ERROR [app] scheduler loop error (3 in a row): Working outside of application context.
File "app/scheduler.py", line 460, in _loop
    if db.engine.url.get_backend_name() == "postgresql":
RuntimeError: Working outside of application context.
```

The loop's leader-election preamble calls `db.engine` — which Flask-SQLAlchemy
3.x only allows inside an app context — at the top of every iteration. The
loop's defensive `except` swallowed it, so the thread stayed "alive" while
**no tick ever completed**: no reminders, no SLA escalations, no nightly
backups — on SQLite too. (`/api/v1/health` still said `scheduler: true`
because that flag is configuration, not liveness.) The engine is now resolved
once, inside a context, before the loop starts. Proof of life after the fix:

```
SELECT … FROM pg_locks WHERE locktype='advisory';
  pid  | objid      | application_name  | state
  4396 | 736559103  | hospital-suite    | idle in transaction   ← leader lock held
whats_app_message: confirmation|DELIVERED|2      ← the queues actually drain
sms_message: SENT|2
```

### 2.9 ❌→✅ Every PostgreSQL backup silently lost the user accounts

The automated backup→restore drill (`test_backup_restore_drill.py`) failed
on restore with a baffling `table user has no column named user` — because
`user.csv` in the archive did not contain users at all:

```
user.csv contents (before the fix):
user
hms_app
```

One column, named `user`, holding the connection role. `user` is a reserved
word in PostgreSQL: the backup's unquoted `SELECT * FROM user` does not name
the table — it is the `CURRENT_USER` construct. The backup "succeeded", the
manifest even recorded `user: 1` (one "row"), and a restore would have
rebuilt a hospital with **no user accounts whatsoever**. Humbling detail:
my own manual spot-check of the archive had probed five other tables and
called the backup verified — it took the automated drill to catch it, which
is precisely what it is for. Fixed by quoting the identifier
(`SELECT * FROM "{table}"` — valid on SQLite too). After the fix:

```
user.csv: 10 data rows; header=['id', 'org_id', 'username', 'name', 'email']
role.csv: 9 data rows;  zip entries: 66
```

### 2.10 ❌→✅ Field encryption crashed patient registration (model/migration split)

The full suite on PostgreSQL failed every `test_f015_field_encryption` test
with:

```
psycopg2.errors.StringDataRightTruncation: value too long for type character varying(32)
```

`Patient.nok_phone` was declared `EncryptedString(32)` in the models while
migration k27 had already widened the column to 256 **in the migration
chain** — a model/migration split. Any database built by `create_all`
(the test rig, the `ensure_schema` boot path) still had `varchar(32)`.
SQLite accepts an over-long value silently; PostgreSQL rejects the INSERT.
In production terms: **the moment a hospital on PostgreSQL set
`FIELD_ENCRYPTION_KEY`, every patient registration with a next-of-kin
phone would crash.** Fixed by aligning the model (`EncryptedString(256)`
on `patient.nok_phone` and `reception_intake.nok_phone`); no new migration
is needed because k27 already widened migration-built databases — the fix
corrects what `create_all` emits. Verified: all 6 f015 tests pass on
PostgreSQL (they fail on the pre-fix code).

### 2.11 ❌→✅ The PHI backfill CLI silently did nothing under RLS

`python -m app.encrypt_phi_backfill` boots its own app — and that boot
arms row-level security. Its rewrite loop then queried `Patient` /
`ReceptionIntake` in a bare app context, which **fails closed**: the CLI
saw zero rows, rewrote nothing, printed `Patient: 0/0 rows rewritten` and
exited 0. An operator following the deploy runbook would believe their
legacy plaintext PHI had been encrypted when none of it had. (This was
listed as a suspected open item in §6; the full suite on real PostgreSQL
promoted it to a confirmed bug.) Fixed by wrapping the rewrite loop in
`rls.background_all_orgs()` — the backfill is inherently cross-hospital.
Verified on PostgreSQL:

```
Patient: 1/1 rows rewritten
ReceptionIntake: 0/0 rows rewritten
```

### 2.12 Test hardening: SQLite never enforced the foreign keys

Three test files had been quietly relying on SQLite *not* enforcing
foreign keys (and, in one case, column lengths):

- `test_fasttrack_tier_guard.py` inserted patients with a hardcoded
  `org_id=1` that no `Organization` row ever had — PostgreSQL refused
  every INSERT with `ForeignKeyViolation: Key (org_id)=(1) is not present
  in "organization"`. Fixed: the fixture and the one non-fixture test now
  create the org.
- `test_queue_estimator.py` passed made-up patient ids (1, 2, 9, 11, 12)
  into `ReceptionIntake` rows. Fixed: real `Patient` rows are created and
  their ids used.
- `test_f015_field_encryption.py`'s raw-column helper read through a bare
  `db.engine.connect()`, which bypasses the RLS listener entirely; it now
  reads through the session (still raw SQL, so it still bypasses ORM
  decryption — that is its purpose), and the backfill test declares
  `background_all_orgs()` because the CLI's boot re-arms RLS on the test
  rig's tables.

None of these change application behavior; they make the tests tell the
truth on a database that actually enforces its own constraints.

## 3. Row-level security — proven, not just read

`tools/verify_postgres_rls.py` (new, committed, re-runnable) creates its own
throwaway database, boots the app into it exactly like production, then
attacks with raw SQL — no ORM, no app in between:

```
$ python tools/verify_postgres_rls.py postgresql://hms_app:…@127.0.0.1:54329/postgres

  [PASS] connection role is not superuser and holds no BYPASSRLS
  [PASS] all 43 protected tables … have ENABLE + FORCE ROW LEVEL SECURITY
         and the org_isolation policy
  [PASS] a query with NO org filter returns only this hospital's patients
  [PASS] an unset tenant sees NOTHING (fail closed)
  [PASS] the background-job sentinel (-1) sees all hospitals
  [PASS] INSERT into another hospital is refused
  [PASS] UPDATE re-homing a row into another hospital is refused
  [PASS] DELETE aimed at another hospital's rows deletes nothing
  [PASS] the tenant setting dies with its transaction (pooled-connection safety)
  [PASS] a scoped connection does not leak its tenant onto other connections
  [PASS] a garbage tenant value never opens the door

ALL 11 CHECKS PASSED — row-level security is real on this server, for this role
```

The RLS unit tests (which skip on SQLite by design) all run and pass on
PostgreSQL:

```
$ TEST_DATABASE_URL=postgresql+psycopg2://… pytest tests/test_rls.py tests/test_migration_safety.py -q
29 passed, 1 skipped in 113.00s          # PostgreSQL
$ pytest tests/test_rls.py tests/test_migration_safety.py -q
22 passed, 8 skipped in 12.59s           # SQLite — unchanged, no regression
```

## 4. End to end, the way issue #1 asked for it

Real gunicorn, real PostgreSQL, `COOKIE_SECURE=0` for the plain-HTTP rig, then
the same booking-doors driver the earlier verification used — now able to
read its rows back out of PostgreSQL:

```
$ python tools/e2e_booking_doors.py http://127.0.0.1:8077 \
      postgresql://hms_app:…@127.0.0.1:54329/hospital --clear

  /book                17 departments; 'Fast Track' lounge listed: False
  /book/fast-track     18 departments; 'Fast Track' lounge listed: True
  /book              → 200, /book/thanks?ref=HOSP-APT-2026-000001
  /book/fast-track   → 200, /book/thanks?ref=HOSP-APT-2026-000002
  no consent          → 422, "premium service" refusal
  sneaky premium dept → 422, refused

  HOSP-APT-2026-000001  Normal Door      is_fast_track=False status=BOOKED
  HOSP-APT-2026-000002  Fast Track Door  is_fast_track=True  status=BOOKED

ALL CHECKS PASSED
```

Backup (the "engine-independent, no pg_dump" claim), read back out of the
database it was stored in (`STORAGE_BACKEND=db`) — after fix 2.9, verified
**including `user.csv` this time**:

```
backup: wrote backups/hospitalsuite-20260913-012010.zip (129687 bytes, 64 tables)
zip entries: 66
  user.csv: 10 data rows (header id, org_id, username, name, email)
  organization.csv: 1 data rows      department.csv: 33 data rows
  role.csv: 9 data rows              appointment.csv: 2 data rows
  whats_app_message.csv: 2 data rows
```

## 5. Full test suite against PostgreSQL

```
$ TEST_DATABASE_URL=postgresql+psycopg2://… pytest -q
<!-- SUITE RESULT -->
```

<!-- SUITE_PLACEHOLDER: to be replaced with the final tally when the run
     completes; see the PR for the live log. -->

## 6. Open items — decisions for the consultant, not silently patched

1. **Five more org-carrying tables are not RLS-protected**: `knowledge_article`,
   `leave_balance`, `leave_request`, `referral_event`, and `login_attempt`
   (the last has legitimate NULL-org rows for context-free login attempts, so
   protecting it needs a deliberate policy design, not a one-line add). The
   module's own rule is that adding tables is a reviewed decision — so here
   they are, listed.
2. **The migration chain builds 51 tables; the models define more.** Six
   (`whatsapp`-era `whats_app_message`, `staff_attendance`, `branch`,
   `native_voice`, `native_phrase`, `native_voice_setting`) are only created
   by the boot fallback `ensure_schema()` (create_all). A purely
   alembic-migrated database is therefore incomplete until first boot. Works,
   but the chain should eventually catch up with the models.
3. ~~**`python -m app.encrypt_phi_backfill`** (the PHI encryption backfill CLI)
   runs outside requests; it may need a `background_all_orgs()` declaration
   like the scheduler jobs.~~ **Confirmed and fixed** — see finding 2.11: the
   full suite on real PostgreSQL proved the CLI silently saw zero rows under
   RLS; its rewrite loop now declares `background_all_orgs()`.

## 7. How to re-run all of this

```bash
pip install -r requirements.txt pgserver        # pgserver ships real PG 16 binaries

# any PostgreSQL you like; the role must NOT be superuser:
python - <<'EOF'
import pgserver
print(pgserver.get_server('./pgdata').get_uri())
EOF

# 1. the migration chain, from scratch
DATABASE_URL="postgresql+psycopg2://user:pw@host:port/fresh_db" alembic upgrade head
DATABASE_URL="postgresql+psycopg2://user:pw@host:port/fresh_db" alembic current   # k28_tenant_usernames (head)

# 2. RLS, attacked with raw SQL (creates + drops its own throwaway database)
python tools/verify_postgres_rls.py postgresql://user:pw@host:port/postgres

# 3. the suite (conftest has supported TEST_DATABASE_URL from day one)
TEST_DATABASE_URL=postgresql+psycopg2://user:pw@host:port/test_db python -m pytest -q

# 4. the doors, end to end through real gunicorn (COOKIE_SECURE=0 for plain http)
SECRET_KEY=x COOKIE_SECURE=0 DATABASE_URL="postgresql+psycopg2://…" \
    gunicorn --bind 0.0.0.0:8077 --workers 1 --threads 4 --timeout 120 "app:create_app()"
python tools/e2e_booking_doors.py http://127.0.0.1:8077 postgresql://user:pw@host:port/db --clear
```

## 8. Not verified here — be honest about this

* **Not Supabase itself.** Direct TCP to a vanilla PostgreSQL 16.2, not
  Supabase's session pooler. The pooler multiplexes but speaks PostgreSQL;
  the app already sizes its pool and uses `pool_pre_ping`/`pool_recycle` for
  it. The remaining pooler-specific risk (driver-level edge cases under
  PgBouncer-style multiplexing) is unchanged by this work.
* **No real WhatsApp/SMS/mail sends** — sandbox mode, as before.
* **Single gunicorn worker** (as `render.yaml` specifies). The scheduler's
  leader election was verified by observing its advisory lock, not by racing
  two instances.
* The superuser warning is **log-only** — a superuser connection still boots
  and serves. That is deliberate (a hospital must boot), but it means log
  monitoring matters on self-hosted deployments.
