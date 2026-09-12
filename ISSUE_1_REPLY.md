## Branch: `arena/01a08cab-forlawe` — commit `e760486`

One branch, complete, on this repo (`forlawe/forlawe`). The application lives under the **`hositalsuite/`** subdirectory of that branch — that folder is the deploy root, i.e. it is what maps to the root of `Hcarepro2026/hositalsuite`.

**Deploy root:** `hositalsuite/`. That folder is what maps onto the root of `Hcarepro2026/hositalsuite`, and `render.yaml`, `requirements.txt`, `run.py`, `runtime.txt`, `alembic.ini`, `migrations/`, `Dockerfile`, `app/` and `tests/` all sit inside it side by side — so `buildCommand: pip install -r requirements.txt` resolves correctly. Point Render's root directory at `hositalsuite/`. (A root-level `requirements.txt` / `runtime.txt` shim and a root `README.md` were added in this commit so the same command also works if it is typed from the repo root; they are not a second copy of the app.)

### 1. Everything needed to run is present

Checked with `git cat-file -e` against the pushed commit, not by eye:

```
requirements.txt   PRESENT      app/config.py       PRESENT
run.py             PRESENT      migrations/env.py   PRESENT
runtime.txt        PRESENT      .env.example        PRESENT
start.sh           PRESENT      alembic.ini         PRESENT
render.yaml        PRESENT      app/__init__.py     PRESENT
Dockerfile         PRESENT
```

`hositalsuite/` holds **542 files**; nothing from live `main` (2ad087c, 541 files) was removed — the merge is additive (13 modified, 2 new, 0 deleted, before this commit's further work).

`arena/01a08339-forlawe` is a **partial tree** (453 files) and must not be deployed: besides `requirements.txt` it is missing `run.py`, `runtime.txt`, `start.sh`, and the whole `servicepoints_admin.py` / `hospital_structure.py` modules — which is why its own `test_nav_links_resolve` fails on 6 dead admin links. Take the fixes, not that branch.

### 2. All four items — finished, with the evidence

**Booking split** — `portal()` / `portal_fast_track()` via `_portal_render(fast_track)`; both `or True` bugs gone.

**`booking_portal.html` renders `is_fast_track` correctly per route** — and this was tested end to end through a real gunicorn process using `render.yaml`'s exact start command, posting only the fields each page renders and reading the rows back out of the database:

```
/book             17 departments, 'Fast Track' NOT offered
/book/fast-track  18 departments, '⭐ Fast Track' listed, gold box + consent shown

/book                        -> 200, /book/thanks?ref=HOSP-APT-2026-000001
/book/fast-track             -> 200, /book/thanks?ref=HOSP-APT-2026-000002
/book/fast-track, no consent -> 422, "premium service" refusal

  HOSP-APT-2026-000001  Normal Door      is_fast_track=False
  HOSP-APT-2026-000002  Fast Track Door  is_fast_track=True
```

**That test found a bug that reading the code did not.** `Fast Track` was the *first* department in the dropdown on **both** doors, and `is_ft = … or is_fast_track_dept(dept)` makes a booking into that department premium regardless of which door it came through. A patient on the free door could pick the first item in a list and be handed a paid service with no price and no consent box on screen. Fixed three ways in `app/views/bookings.py`:

1. the free door no longer lists the paid lounge;
2. consent now follows the **outcome** — `becomes_fast_track = is_ft_check or is_fast_track_dept(dept)` — so hand-posting that department without consent returns 422 (verified above);
3. the 422 re-render was dropping the `fast_track` flag, silently downgrading the premium door to the plain one after a typo.

**`patient_hub.html`** — the gold card points at `bookings.portal_fast_track`; the plain tile stays on `bookings.portal`. Rendered HTML: `class="lux-card" href="/book/fast-track"`.

**Bug B** — `checked` removed from the Fast Track checkbox, `required` removed from the consent checkbox, server gate `if is_fast` intact.

**Request 3 — finished, not a display flag.** In `app/views/queue.py::join_submit`:

* first-time patient → a real `ReceptionIntake` is opened (they need a paper folder), `ticket.intake_id` and the TV session both point at it, and `tracking.enter(..., "RECEPTION", intake_id=…)` opens a real journey segment. Reception can see them coming.
* returning patient → their folder already exists, so **no duplicate intake is minted**; `tracking.enter(..., "HIMS", patient_id=…)` opens the journey at Records.
* `created_by` stays `NULL` on purpose — the patient did this from a QR code; inventing a staff member would put a false name in the audit trail.
* wrapped like every other tracking call, so a measurement failure can never stop a patient being seen.

### 3. Test results

```
pytest -q   ->   1060 passed, 8 skipped   (16m21s)
```

`tests/test_fasttrack_doors.py` (13 tests) posts what the pages actually render rather than hand-built payloads — that is what caught the premium-department hole. `tests/test_migration_safety.py` grew two tests for a deploy blocker fixed here: `alembic.ini` ships the placeholder `driver://user:pass@localhost/dbname`, which `migrations/env.py` mistook for a caller-supplied URL, so **every CLI migration died** with `NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`. The app never noticed (boot passes the URL explicitly); no operator could migrate by hand. `alembic upgrade head` now works: 51 tables, `current = k28_tenant_usernames`.

### 4. Not verified — stated plainly

No PostgreSQL exists in this workspace (`postgres`, `psql`, `initdb` all absent), so the suite ran on SQLite and the Postgres-only paths — RLS policies, `FORCE ROW LEVEL SECURITY`, `set_config('app.current_org', …, true)` — were **read, not executed**. Before production, run once against a real Supabase database: `TEST_DATABASE_URL=postgresql://… pytest -q` and `alembic upgrade head` via the **session** pooler (not the transaction pooler — DDL and the RLS variable both need a session). No real WhatsApp/SMS/mail sends were made (sandbox mode).

Full detail in `DEPLOY_READY.md` and `CONSULTANT_REPORT_RESPONSE.md` on the same branch.
