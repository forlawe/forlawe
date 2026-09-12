# Response to the consultant report — verified line by line

Date: 11 September 2026. Every claim below comes from a command run in this
workspace; the command and its output are quoted. Where the report is right I say
so; where it is wrong I show the evidence.

---

## 1. The most important finding: the report reviewed a *different branch*

The report says *"I pulled all four relevant files fresh from the live branch."*
It was not your live repo, and it was not this branch. There are three copies of
this codebase in play:

| Codebase | `or True` in `bookings.py` | `/book/fast-track` route | `entry_stage` in `queue.py` |
|---|---|---|---|
| **Your live repo** `Hcarepro2026/hositalsuite` — `main` (2ad087c) | **2** (bug live) | absent | absent |
| …its branch `arena/01a073f2-hositalsuite` (69a4315) | **2** | absent | absent |
| …its branch `arena/01a06e4b-hositalsuite` (eaf70cb) | **2** | absent | absent |
| **This branch** `forlawe/arena/01a08cab-forlawe` (14ed938) | **2** (bug live) | absent | absent |
| **`forlawe/arena/01a08339-forlawe`** (ad7ed40) | **0** | `bookings.py:36` `@bp.get("/book/fast-track")`, `:38 def portal_fast_track()` | `queue.py:165` |

```
$ git show origin/arena/01a08339-forlawe:app/views/bookings.py | grep -n "book/fast-track\|def portal_fast_track"
36:@bp.get("/book/fast-track")
38:def portal_fast_track():
```

So the work the report reviews exists **only** on `arena/01a08339-forlawe`, a
different Arena session's branch. Nothing from it had reached your live repo or
this branch. That matters for the "send it back" instruction: there was nothing
here to send back — it had to be ported first (§4).

---

## 2. ⚠️ That branch must not be deployed as it stands

I compared its file list against your live repo:

```
sibling branch : 453 files
your live repo : 541 files
missing        : 102
```

Among the 102 missing files:

* **`run.py`** — the app's entry point
* **`requirements.txt`** — the dependency list
* `runtime.txt`, `start.sh`, `push.sh`, `.env.example`, `.gitignore`, `ci/`, `loadtest/`, all of `rosters/`, ~40 `docs/reports/*`
* **`app/views/servicepoints_admin.py`** and **`app/views/hospital_structure.py`** — two whole admin modules (559 + 365 lines), which is why `app/__init__.py` there no longer registers `svcpts_bp` / `hospstruct_bp`

And its own test suite fails on that account — 6 admin links point at routes that
no longer exist:

```
$ pytest -q tests/test_nav_links_resolve.py          # on that branch, my edits stashed
FAILED tests/test_nav_links_resolve.py::test_every_hardcoded_template_href_resolves_to_a_real_route
E   admin/overview.html: /admin/servicepoints
E   admin/overview.html: /admin/hospital-structure
E   admin/clinic_shortlist.html: /admin/servicepoints#clinics
E   admin/hospital_structure.html: /admin/servicepoints
E   admin/hospital_structure.html: /admin/servicepoints/clinics/{{ c.id }}/shortlist
E   admin/servicepoints.html: /admin/servicepoints/clinics/{{ c.id }}/shortlist
```

I confirmed this failure is **pre-existing there**, not caused by anything I did:
it fails identically with my edits stashed. **Take the four fixes from that
branch; do not push the branch.**

---

## 3. The report's ✅ for Bug A is wrong — proven by running the code

The report is right that both `or True` lines are gone and that consent is gated
on `is_ft_check`. But the end-to-end behaviour is broken, in the opposite
direction. On that branch:

* `booking_portal.html` replaced the Fast Track hidden field with
  `<input type="hidden" name="mode" value="…">` — so the form **no longer posts
  `is_fast_track` at all**;
* `bookings.py` **never reads `mode`** (`grep '"mode"' app/views/bookings.py` → no
  match), it still reads `request.form.get("is_fast_track")` at lines 122 and 150.

I ran it rather than reasoning about it:

```
--- fields the Fast Track page actually renders ---
  has name="is_fast_track" : False
  has name="mode"          : True
--- what the server stored ---
  appointment created : True
  apt.is_fast_track   : False          ← gold card tapped, consent ticked
```

and, without ticking consent at all:

```
  HTTP: 200
  consent error shown to patient : False
  appointment created anyway     : True
  apt.is_fast_track              : False
```

So on that branch a patient who taps **"👑 Fast Track — Be Seen Fast"**, fills the
gold form and ticks the premium consent gets **a normal booking**, and the
server-side consent check is dead code. Bug A was not fixed — it was inverted.

Why the existing tests did not catch it: `tests/test_booking.py::_book()` posts
`is_fast_track: "1"` by hand, so it tests the server against a payload no page
produces.

---

## 4. What the report got right

| Claim | Verdict |
|---|---|
| Both `or True` bugs removed on that branch | ✅ correct (`grep -c "or True"` → 0) |
| Two routes `portal()` / `portal_fast_track()` exist | ✅ correct |
| Consent gated on `if is_ft_check` | ✅ correct as written — but unreachable, see §3 |
| Bug B fixed: no `checked` on Fast Track, no `required` on consent, gate `if is_fast` | ✅ correct — `queue_join.html:86,97`, `queue.py:121` |
| Request 1 frontend not wired: both tiles point at `bookings.portal` | ✅ correct — `patient_hub.html:84` |
| Request 3 core line matches the founder's definition | ✅ correct — `queue.py:165` |
| Request 3 is display-only, no `ReceptionIntake`, no `tracking.enter()` | ✅ correct — `join_submit()` spans lines 102–189; every `ReceptionIntake` reference is in `ticket_page()` (192+) or `to_reception()` (464+) |
| The three copy spots in `queue_join.html` | ✅ all three find-blocks matched exactly once |
| `url_for()` would raise `BuildError` if the endpoint were wrong | ✅ correct — which is precisely why this fix cannot go on a branch without the route |

---

## 5. What I did

Ported the four items onto the **complete** codebase in this branch (541 files),
fixing the §3 bug on the way:

| File | Change |
|---|---|
| `app/views/bookings.py` | route split `portal()` / `portal_fast_track()` via `_portal_render(fast_track)`; both `or True` removed |
| `app/templates/booking_portal.html` | Fast Track gold box, consent and gold button only on the Fast Track door; **`is_fast_track` / `fast_track_reason` kept and gated** — that is the §3 fix |
| `app/templates/patient_hub.html` | gold card → `bookings.portal_fast_track` (Request 1) |
| `app/views/queue.py` | `entry_stage = "HIMS" if patient_id else "RECEPTION"` (Request 3) |
| `app/templates/queue_join.html` | Bug B (no `checked`, no `required`) + all three copy spots |
| `tests/test_fasttrack_doors.py` | **new**, 9 tests that post what the page actually renders |
| `tests/test_f039_consent_partial.py` | its `/book` URLs were stale — that page no longer sells Fast Track. Retargeted to `/book/fast-track` **and** added a test that `/book` must *not* advertise a paid service |

Note on the last line: I changed a test. The reason is above and it is a
behaviour change you approved (two doors), not a way to make red go green — the
replacement test is stricter than the original, it locks both directions.

---

## 6. Verification

| Check | Result |
|---|---|
| New tests here (`pytest -q tests/test_fasttrack_doors.py`) | **9 passed** |
| The same 9 tests run against that branch's code | **2 failed** — `test_fast_track_door_renders_the_flag_and_stores_it`, `test_fast_track_consent_still_enforced_server_side` (i.e. they catch exactly the §3 bug) |
| Focused tests after the port (`test_f039 + fasttrack_doors + booking`) | **23 passed** |
| Full suite, first pass after the port | 1051 passed, **2 failed** — both `test_f039_consent_partial` (the stale `/book` expectation), now fixed |
| Full suite, second pass | 1053 passed, 8 skipped, **1 error** — `test_patient_hub.py::test_hub_has_an_emergency_notice` raised a fixture `SystemError`, not an assertion failure |
| That error investigated | the file passes **16/16** alone and the single test passes twice alone → environment flake, not my change |
| Full suite, third pass (decisive) | **1054 passed, 8 skipped** in 17m04s — no failures, no errors |
| Baseline for comparison | 1044 passed before this work; +9 new Fast Track tests +1 new F-039 test = **1054**, which reconciles exactly |
| Both patches dry-run against a **fresh clone of your live `main`** | `landing_auth_mobile.patch` fits, `fasttrack_two_doors.patch` fits |
| Both patches applied to that clone, tests run there | **45 passed** (fasttrack doors, booking, queue, patient hub, F-039) and **120 passed** on the wider selection (adds nav links, navigation, a11y, phone look, Fast Track tier guard, tracking) |

---

## 7. Still open — unchanged, and it needs your decision

**Request 3 is still display-only.** `entry_stage` sets `current_stage` on the
Personal TV session; no `ReceptionIntake` is created for a first-time patient and
no `tracking.enter()` opens a real journey segment for either path. A returning
patient's tracker can therefore say **HIMS** before any HIMS record exists.

I deliberately did **not** add that. Creating real clinical records as a
side-effect of a patient tapping "join queue" is a workflow decision — who owns
the folder, what happens if Records is closed, what the TV should say in the gap
— and it is yours to make, not mine to guess. The copy now says "we'll take you
straight to Records", which describes the intent accurately but is not yet backed
by a record. Say the word and I will wire it properly.

---

## 8. Shipping it

Two independent patches in `deploy/`, both verified against a fresh clone of your
live `main`:

```
deploy/landing_auth_mobile.patch    8 files   landing ↔ auth wiring + mobile nav
deploy/fasttrack_two_doors.patch    7 files   Bug A, Bug B, Request 1, Request 3 + tests
```

```bash
git clone https://github.com/Hcarepro2026/hositalsuite.git && cd hositalsuite
git apply --check deploy/landing_auth_mobile.patch    # prints nothing = fits
git apply --check deploy/fasttrack_two_doors.patch
git apply        deploy/landing_auth_mobile.patch
git apply        deploy/fasttrack_two_doors.patch
git status                                            # 15 files, exactly
pytest -q tests/test_fasttrack_doors.py               # 9 passed
git add -A && git commit -m "Fast Track: two honest doors; landing/auth mobile pass" && git push origin main
```
