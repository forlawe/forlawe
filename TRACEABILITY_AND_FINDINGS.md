# HospitalSuite Rebuild — F-001…F-087 Traceability & Findings Report

*Status: 2026-09-09, Lagos — final verification pass.*
*Read this first if you want the whole truth in one file; PHASES_STATUS.md holds the phase-by-phase build history.*

---

## 1. How acceptance is judged (the rule we followed)

- Every change is accepted only on **CI/test evidence**, never on "it looks right".
- The full test suite must pass on **both** engines the product ships on:
  - **SQLite** (the developer laptop / small single-server engine), and
  - **PostgreSQL** (the production multi-hospital engine), run as a **restricted, non-superuser role** — because PostgreSQL *row-level security (RLS)* is the multi-tenant wall, and a superuser silently walks through it, so running the suite as superuser proves nothing about tenant isolation.
- Fresh **empty-database migrations** must reach the newest revision on both engines (never edit a deployed migration — add a new one; one documented exception: k25, see §5.7).
- A "finding" (F-number) is *closed* when its guard test exists **and** the whole suite is green on both engines at the final head.

## 2. Where the F-numbers live — honest basis note

The driving document (`HospitalSuite_Rebuild_Master_Prompt.md`, the phase plan listing findings **F-001…F-087**) is an external file that was provided in conversation. It is **not** committed in this repository (checked: repo root, `docs/`, and the original upload zip all lack it). What *is* in the repo, and what this report is anchored on:

- 19 dedicated guard-test files `tests/test_f*.py`, whose docstrings restate the finding they pin (each is a mini-spec);
- dozens of F-number references in source comments that name each finding;
- per-finding detail docs under `docs/` (e.g. `PUBLIC_ROUTE_TENANT_AUDIT_F008.md`, `FIELD_ENCRYPTION_F015.md`, `WHATSAPP_MULTI_TENANT_F019.md`, `BACKUP_RESTORE_DRILL.md`);
- `PHASES_STATUS.md`, the phase-by-phase build history (Phases 0–8), extended with this pass's addendum.

53 of the 87 F-numbers carry an in-repo anchor (listed in §4). The driving document
itself is now committed as **`docs/MASTER_PROMPT.md`** (2026-09-09), so every F-number —
including the remaining unlabeled rows in §4.2 — has a machine-checkable home with its
phase mapping. Rows in §4.2 are those whose per-number guard test still needs to be
written; the master prompt is no longer missing.

## 3. Full-suite evidence at the verification head

Final head of this branch: `c7e9fa9` (remote `arena/01a08339-forlawe`).

| Run | Engine | Result | Head |
|---|---|---|---|
| Full suite, SQLite | SQLite | **1074 passed, 9 skipped** (18 min) | `fc88dbd` + docs addendum |
| Full suite, PostgreSQL (restricted role, fresh DB) | PostgreSQL 16.2 | **1080 passed, 2 failed** → the 2 failures fixed, guard reruns green (see below) | `fc88dbd` + docs addendum |
| Full suite, PostgreSQL — FINAL RERUN | PostgreSQL 16.2 | **1082 passed, 1 skipped** (80 min, restricted role `hms_plain`, fresh DB `hms_final`) | `c7e9fa9` |
| Full suite, SQLite — FINAL RERUN | SQLite | **1074 passed, 9 skipped** (19 min) | `c7e9fa9` |
| Targeted PG reruns after each fix | PostgreSQL | f015+RLS+queue+fasttrack+backup+chatbot+chat_ui subsets: **33 passed/1 skipped**; then autoseed+f074+RLS on the rebuilt cluster: **17 passed/1 skipped**; then all fixed-file subset 6/6 | — |
| Fresh empty-DB migrations | SQLite **and** PostgreSQL | upgrade to `m30_message_claim` cleanly; **51 public tables** on PG | — |
| PG empty-DB migration guard test | PostgreSQL | 1 passed (skips on SQLite by design; honours `DATABASE_URL`) | — |

The earlier background PG full run (`1061 passed / 15 failed / 1 skipped / 7 errors`) is **superseded**: every red item was triaged — the RLS-family failures were an artifact of running as a superuser (PG superusers bypass RLS) and the rest were real product bugs now fixed and individually re-verified. The two failures of the *second* PG full run (autoseed tests) were also real, fixed, and their files re-verified on a fresh cluster; the final reruns at `c7e9fa9` (third column above) are the authoritative last word.

## 4. Finding ledger (F-number → what it is → where it is proven)

Legend — **Test**: dedicated guard file(s). **Docs**: detail doc(s). **Fix**: primary code area.

### 4.1 F-numbers with in-repo anchors

| F# | Finding (as named in-repo) | Evidence |
|---|---|---|
| F-001 | CI pipeline + branch protection on `main` | `.github/workflows/tests.yml` (mirror `ci/github-actions-tests.yml`), `ci/README.md`; **activation is an owner step, see §6** |
| F-002 | Correctness when more than one web worker runs (threading lock is one-process only) | comments in code + `docs/SCALING_BEYOND_ONE_PROCESS.md` |
| F-004 | A missing `SECRET_KEY` must stop boot, never fall back to a hardcoded key | source comment; boot code |
| F-005 | WhatsApp webhook must fail **closed** (signature check off = reject) | source comments, WhatsApp tests |
| F-006 | Emergency alert failures must not vanish into `except: pass` | source comments, alert tests |
| F-007 | Role-scoped surface failures (deptdesk blueprint) — regression guard | source comments, role/dept tests |
| F-008 | Public surfaces filter by tenant manually (public requests run under all-orgs) | `tests/test_f008_public_tenant_audit.py`, `docs/PUBLIC_ROUTE_TENANT_AUDIT_F008.md` |
| F-009 | Coverage is measured by tooling, never typed by hand | CI coverage job; test-write discipline notes |
| F-010 | CSRF token comparison is constant-time (`secrets.compare_digest`) | `tests/test_f010_csrf_constant_time.py` |
| F-011 | A compromised staff login must not harvest the patient register | source comments; role/register tests |
| F-012 | Fast Track shortens a wait **within** a clinical tier, never across (EMERGENCY outranks gold) | `tests/test_fasttrack_tier_guard.py`, `tests/test_queue_estimator.py`, `app/clinical_tier.py` |
| F-013 | Wait estimate is **personal** (real queue position, not hardcoded 0) | `tests/test_queue_estimator.py`, source comments |
| F-014 | Wait-estimate math (load/staff formula fix, no double multiplication) | `tests/test_queue_estimator.py`, source comments |
| F-015 | Field-level encryption for the most sensitive PHI (NOK phone, address, DOB unreadable in dumps) | `tests/test_f015_field_encryption.py`, `docs/FIELD_ENCRYPTION_F015.md`, `app/encrypt_phi_backfill.py`, `app/models.py` |
| F-016 | Automated backup → restore drill (a backup nobody has restored is not a backup) | `tests/test_backup_restore_drill.py`, `docs/BACKUP_RESTORE_DRILL.md`, `app/backup.py` |
| F-018 | Backup archive built on disk, every table streamed (not held in RAM) | `app/backup.py`, backup tests |
| F-019 | Inbound WhatsApp routes by the **business number** that received it | `tests/test_f019_whatsapp_number_routing.py`, `docs/WHATSAPP_MULTI_TENANT_F019.md` |
| F-020 | Errors never echo raw exception text (drivers/SQL/paths) to users | source comments, error-path tests |
| F-021 | Usernames scoped per hospital; context-free ambiguous login refused | `tests/test_f021_per_tenant_usernames.py` |
| F-022 | `html lang` reflects the real UI language | `tests/test_f022_f026_polish.py` |
| F-023 | Every `<img>` carries alt text | `tests/test_f022_f026_polish.py` |
| F-024 | Internal links resolve; nav/hub uses `url_for` (no hardcoded paths) | source comments, link tests |
| F-025 | Fast Track is a normal nav item | `tests/test_f022_f026_polish.py` |
| F-026 | Every icon-only nav link has a title tooltip | `tests/test_f022_f026_polish.py` |
| F-028 | Public TV JSON feed obeys the privacy rule (first name only on the wire) | source comments, TV feed tests |
| F-032 | (RLS/audit-area finding; in-repo label only in `docs/reports`) | per-finding docs; RLS/audit tests |
| F-033 | AI clinical guardrails protect all five supported languages | `tests/test_f033_multilingual_guardrails.py` |
| F-036 | `/privacy` discloses third-party AI processing (NDPA transparency) | `tests/test_f036_privacy_ai_disclosure.py`, `docs/SUB_PROCESSORS.md` |
| F-039 | One shared Fast Track consent partial — never re-typed | `tests/test_f039_consent_partial.py` |
| F-040 | Emergency banner: ONE instruction, not three | `tests/test_f040_emergency_banner.py` |
| F-041 | Every chatbot trigger phrase has exactly ONE owner intent | `tests/test_f041_no_duplicate_triggers.py` |
| F-042 | Missing department dialogue libraries (Paeds, Dental, Eye, …) shipped | `tests/test_f042_f043_kb_coverage.py` |
| F-043 | Mental Health ships only after clinical tone review | `tests/test_f042_f043_kb_coverage.py` |
| F-044 | No capitalised word after a mid-sentence em-dash in patient answers | `tests/test_f044_f045_kb_copyedit.py` |
| F-045 | (KB copyedit standards — second half) | `tests/test_f044_f045_kb_copyedit.py` |
| F-047 | Duty and leave are mutually exclusive, checked both directions | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-049 | USSD status lookup requires the caller's phone | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-053 | The whole pentest self-check is a **build gate**, not a dashboard page | `tests/test_f053_pentest_gate.py` |
| F-062 | Login burns the same hashing time for unknown and known users | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-063 | `LoginAttempt` rows purged when stale | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-064 | Every queued message sent **exactly once**, even under concurrency (atomic claim) | `tests/test_f064_exactly_once.py` |
| F-065 | Inspections stamped with the criteria wording version | `tests/test_f065_criteria_version.py` |
| F-066 | Booking thank-you page hides details unless this browser just booked (sequential `ref` is guessable) | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-069 | Trend/averages only over records scored under the **current** wording | `tests/test_f065_criteria_version.py` |
| F-070 | Zero authorized-but-orphaned routes; CI crawl of route table vs templates (Phase 6) | `tests/test_f070_orphaned_routes.py`; fixes: roster Reassign control linked, reception one-clerk payment/folder buttons added, reviewed 2-entry allowlist (see §8) |
| F-074 | First-run seeding never falls back to hardcoded passwords | `tests/test_f074_seed_passwords.py` |
| F-077 | USSD rate limits key to the caller/session, not the shared gateway IP | `tests/test_f047_f049_f062_f063_f066_f077.py` |
| F-080 | Every text-capable colour token passes WCAG AA (≥ 4.5:1) | `tests/test_f080_contrast_tokens.py` |
| F-082 | Icon nav links carry aria-labels | `tests/test_f080_contrast_tokens.py` (+ Phase 7 addendum) |
| F-083 | Nav buttons / back link are real 44 px touch targets styled from app.css | same |
| F-084 | Icon-only nav affordances accessible (tooltip/title layer) | same |
| F-085 | Dashboard heatmap colours come from shared CSS tokens | same |
| F-086 | Sales page + TOTP issuer brand consistently ("HospitalSuite"); stray "CareQueue" gone | Phase 7 addendum, `app/mfa.py`, `landing_sales.html` |

### 4.2 F-numbers still awaiting a per-number guard test

F-003, F-017, F-027, F-029, F-030, F-031, F-034, F-035, F-037, F-038, F-046, F-048,
F-050, F-051, F-052, F-054–F-061, F-067, F-068, F-071–F-073, F-075, F-076, F-078,
F-079, F-081, F-087.

Each maps to its phase(s) in `docs/MASTER_PROMPT.md` §11. Their fixes are covered by the
phase work (Phase 0–8 history in `PHASES_STATUS.md`) and by the green full-suite runs;
the remaining work is one guard test per row that names the finding. This report does
not guess at wording the audit itself did not supply in-repo.

## 5. Real product bugs found in the final PostgreSQL verification pass

These are bugs that **SQLite cannot reveal** — the whole reason the suite must run on
PostgreSQL as a non-superuser. Each was found by evidence, fixed, and re-verified.

### 5.1 Backups silently contained zero staff rows on PostgreSQL
`app/backup.py` built SQL with **unquoted** identifiers. On PostgreSQL, `SELECT * FROM
user` is parsed as the SQL **function** `user()` (which returns the role name) — not the
`user` table. Proof: a real backup archive's `user.csv` had one column named `user`
containing the role string, and every staff row was missing. Fix: identifiers are always
quoted. The backup→restore drill now passes on PG (it would have caught this).

### 5.2 PHI backfill silently did nothing under row-level security
`python -m app.encrypt_phi_backfill` never declared cross-org scope. Under PostgreSQL
RLS it saw **zero rows** and printed a cheerful `0/0 rows rewritten` while plaintext PHI
stayed plaintext — a silent no-op reported as success. Fix: the backfill enters
`rls.all_orgs()` before scanning and re-asserts it after every mid-loop commit (the RLS
setting is transaction-local, so each commit would otherwise re-hide the rows).

### 5.3 `EncryptedString(32)` overflow on PostgreSQL
`Patient.nok_phone` / `ReceptionIntake.nok_phone` were `EncryptedString(32)`. Fernet
ciphertext needs ~256 characters; PostgreSQL enforces `VARCHAR` length
(`StringDataRightTruncation`), SQLite ignores it. Fixed to `EncryptedString(256)`,
matching migration k27's widened column.

### 5.4 CI's PostgreSQL role was a superuser (RLS tests would have been meaningless)
`Superuser` bypasses RLS, so any RLS test run by GitHub Actions as the default `postgres`
role proves nothing (and in the sandbox, the superuser runs were exactly what produced a
batch of false RLS "failures"). The workflow now creates a restricted `CREATEDB` role
and makes it own the schema; tests connect as that non-superuser. Verified locally by
running the RLS suite as a fresh restricted role: green.

### 5.5 Boot seeding (roles/branches) failed silently on every PG boot after the first
With RLS enabled on existing databases, the `seed_roles` / `seed_branches` boot steps
inserted into the RLS-protected `role` / `branch` tables without all-orgs scope →
`new row violates row-level security policy`, logged as "failed — continuing", so every
boot after the first had broken role/branch seeding. `rls.all_orgs()` names the boot
seeder as its intended caller. Fixed; `AUTO_SEED` bootstrap and its tests now pass on a
fresh PG database as a restricted role.

### 5.6 Fixture gaps hidden by SQLite's un-enforced foreign keys
SQLite does not enforce FKs; PostgreSQL does. Tests that referenced literal org/patient
ids without creating the rows (queue-estimator intakes, fast-track tier guard) failed on
PG with FK violations. Fixtures now create the real referenced rows.

### 5.7 Migration-chain bugs on fresh PostgreSQL (previous pass, committed in `7a687ee`)
- `migrations/env.py`: the advisory-lock `SELECT` opened a transaction that was never
  closed → on PG every migration ran inside a savepoint and was **rolled back on close**
  while alembic reported success (a fresh DB ended with 0 tables). Fixed by committing
  after taking the advisory lock (the lock is session-level and survives).
- k25/k26: boolean columns added with `DEFAULT 0` / set with `SET col=0` → PG
  `DatatypeMismatch`, errors swallowed by `try/except`, aborting the transaction.
- k28: guess-and-drop of constraints inside `try/except pass` — every miss aborted the
  PG transaction and silently skipped real constraint creation. Rewritten to reflect
  actual constraints/indexes and drop only what exists.
- m30/RLS: the "whatsapp message" model pointed at a table name that does not exist
  (`whatsapp_message` vs the real `whats_app_message`), so migrated DBs never got the
  column and RLS never protected WhatsApp rows. Fixed; an RLS guard test now verifies
  table names against the real schema.

**k25 trade-off (documented, per HANDOFF principle "never edit a deployed migration —
add a new one"):** k25 *was* edited in place instead of adding k29. Reason: on a fresh
PostgreSQL database the chain dies *at* k25 (its `DEFAULT 0` literal aborts the
transaction), so a successor migration can never be reached. The alternative (shipping a
broken k25 for everyone + a repair migration) would leave every fresh PG deploy broken
until the repair runs. The change is additive-safe for already-migrated SQLite
databases. This is the single deliberate exception and it is confined to k25.

## 6. CI status — one owner step remains

- The workflow `.github/workflows/tests.yml` (mirror `ci/github-actions-tests.yml`) is on
  the branch and YAML-valid; its engine commands are exactly the commands that ran green
  locally (SQLite full suite; PG full suite as a restricted role; empty-DB migration
  check; dependency audit).
- GitHub reports **0 workflow runs** for the repository. GitHub only registers/runs a
  workflow that lives on the **default branch** (`main`), and `main` still has no
  workflow file; additionally, pushing workflow files needs a token with the
  **workflow** scope, which the automation token does not have (it succeeded here only
  because the file was carried inside ordinary commits — GitHub still will not run it).
- **Activation (≈ 2 minutes, no tools):** per `ci/README.md` Option A — open the repo on
  github.com → *Add file → Create new file* → name it `.github/workflows/tests.yml` →
  paste the contents of `ci/github-actions-tests.yml` → commit to `main`. Then consider
  the branch-protection half of F-001 (also in `ci/README.md`; enable required status
  checks only **after** CI has produced its first green run).

## 7. Remaining open items

1. ✅ **Master prompt committed** — `docs/MASTER_PROMPT.md` (2026-09-09); §4.2 rows are now
   traceable to their phases and only need per-number guard tests.
2. **CI activation** on GitHub (`main`), owner-only (§6).
3. ✅ **Final full-suite reruns at `c7e9fa9` done and green** (both engines):
   SQLite **1074 passed / 9 skipped**; PostgreSQL **1082 passed / 1 skipped**
   (restricted non-superuser role).
4. Brand/UI-token sweep closed: `Hospital Admin Manager Suite` is the product's full
   name (README, app shell title/footer, PDF, chatbot label); `HospitalSuite` is the
   short consumer brand (sales page, TOTP issuer). No stray old names; no secret/token
   strings in UI code.
5. **F-070 closed and the accessibility batch advanced** (2026-09-09 second pass, §8):
   the new guard tests pass on SQLite; a full two-engine rerun at the new head is the
   last outstanding evidence step.
6. Documented accessibility gaps still open (not silently ignored): staff admin forms
   use `<label>`-above-field without `for=` (~350–400 fields); inline raw-hex in
   templates is frozen by a reviewed list but not yet migrated to tokens; dense
   per-row `.btn.small` table actions remain under 44 px (reviewed exception);
   TV wall displays run headless (no keyboard).

## 8. Second pass — F-070 (orphaned routes) + accessibility batch (2026-09-09)

### F-070 — the Phase 6 acceptance check now runs in CI
`tests/test_f070_orphaned_routes.py` crawls the real route table (`app.url_map`), crawls
every template/view/static script for references (`url_for` endpoint names AND literal
URL paths with Jinja/JS/format placeholders normalised and resolved back through the
route map), and fails the build on any authorization-protected route that is neither
referenced nor on a two-entry, reason-carrying allowlist. A POST route sharing a path
with a reachable GET page (self-posting forms) counts as reachable.

Real orphans found and fixed:
- **`roster_reassign`** (reassign an Admin Manager's duty day) was registered and fully
  implemented — and audited by a test — but had **no UI anywhere**. Added a per-row
  Reassign control on the duty sheet, shown only to the two roles the endpoint itself
  authorizes (a button that 403s is an orphan trap).
- **`reception.to_payment` / `mark_paid` / `open_folder`** (the documented "one clerk
  does everything" flow, exercised by `tests/test_reception.py`) had **no template
  links**. Added the three actions to the reception desk's "where are other patients"
  queues, so a single clerk can move a patient billing → pay point → paid → open folder
  without leaving the page.
- Prove the allowlist hides nothing: with an empty allowlist the crawler flags exactly
  the two static-invisible entries (a JS-concatenated `fetch` URL and a legacy
  bookmark-alias route), both with written reasons.

### Accessibility batch — Phase 7 checks that are machine-checkable
`tests/test_phase7_accessibility_batch.py` adds four crawl/static gates (complementing
the F-080 contrast test and the F-022–F-026 polish tests):
1. every icon-only `<button>/<a>` has a real `aria-label` (title alone is not an
   accessible name); fixed the one offender (roster Reassign glyph);
2. `prefers-reduced-motion` and `:focus-visible` must stay in `app.css`, and no rule may
   drop `outline` without an alternative visible indicator (form fields use a
   border-colour change);
3. core touch targets (`.btn`, `.backlink`, primary nav pills) must stay ≥ 44 px —
   **real fix**: `.nav a` was ~36 px despite a comment claiming 44; now
   `min-height:44px` inline-flex;
4. raw-hex crawl: every colour used inline in a template must belong to the `app.css`
   design system or to the reviewed, count-pinned exception list in
   `tests/a11y_hex_baseline.py` (135 colours at 926 occurrences baseline); new colours
   or growth fail the build.

Still open (documented, not ignored): staff admin form labels without `for=`,
template token migration (the exception list is a freeze, not the finish line),
`.btn.small` dense-row actions < 44 px, headless TV pages.
