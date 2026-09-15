# Staff-side sweep — fixes applied (2026-09-15)

Follow-up to the consulting sweep of every staff page on the patient journey
(Reception, HIMS, Fast Track, Queue control, Bookings, Complaints, Feedback).
This file records what was **changed**, not just what was found.

Everything below was found by the same rule:

> A fix landed on the **patient-facing** side and was test-pinned there.
> The **staff-facing** page that describes the same behaviour was never
> re-opened, so it kept describing a hospital that no longer exists.

---

## 1. `queue_staff.html` — "all patients start at Reception" ❌ → ✅

**Was**

- pill: `Queue links only to Reception — all patients start at Reception`
- card: `All patients join via Reception (front desk). …`

**Why it was false.** Request 3 (entry routing, `views/queue.py::join_submit`)
sends a patient whose folder is found by phone **straight to HIMS / Records**;
only a first-time patient opens a Reception intake. The patient copy on
`queue_join.html` was updated and pinned by
`test_queue_join_copy_matches_the_new_routing` — the staff page was not.

**Now**

- pill: `New patients → Reception · Returning patients → HIMS / Records`
- card: explains both paths, including that the Reception intake is minted the
  moment a first-time patient joins, so the desk sees them coming.

## 2. `bookings_staff.html` — "All bookings here are Fast Track" ❌ → ✅

**Was** three unconditional gold markers on a list that contains two kinds of
booking (the `/book` door and the `/book/fast-track` door):

- banner: `All bookings here are Fast Track.`
- a `👑` crown on **every** patient name
- a gold `Check in → Reception` button on **every** row

**Now**

- banner explains the two doors and says only Fast Track carries the crown
- crown renders `{% if a.is_fast_track %}`
- button renders `👑 Check in — Fast Track` (gold, Fast Track rows only) or
  `Check in → Queue` (default styling, everything else)

## 3. `views/queue.py::booking_checkin_queue` — "gold lane" for everyone ❌ → ✅

The flash told staff `⭐ … checked in — queue ticket X gold lane.` even for a
standard booking from the normal door. Now only a Fast Track booking says gold
lane.

## 4. Duplicate Reception intake — found in the final pass ❌ → ✅

`to-reception` on both `/queue/<id>` and `/fasttrack/ticket/<id>` minted a
**second** `ReceptionIntake`. Since Request 3, a first-time patient already has
one the moment they join the queue — so tapping the button put the same name on
the Reception desk **twice** and opened two journeys. That is the exact
duplicate the routing work set out to prevent ("their folder already exists, so
NO duplicate intake is minted").

Both handlers now return early with
`"<name> (<code>) is already at Reception as <ref>."` when `t.intake_id` is set.

---

## Final pass — `reception/new.html`, `fasttrack/desk.html`

**`reception/new.html` — clean.** Consistent with the design system, the Fast
Track block is a tick-box (never pre-ticked), and the "ask once, HIMS reuses the
same answers" promise matches what HIMS actually stores. No stale copy, no
design debt.

**`fasttrack/desk.html` — one real bug**, fixed above (item 4: the duplicate
intake behind `👑 Welcome — Take to reception (gold)`). The rest is honest: the
"How Fast Track works" panel describes the real flow, the crown/stats/rows are
all scoped to `is_fast_track`, and every action posts to a route that exists.

## One gap worth a product decision (not fixed here)

`/bookings/<id>/checkin-queue` issues a queue ticket and marks the appointment
`ARRIVED`, but — unlike `/queue/join` — it does **not** create a Personal TV
session or route the patient to Reception vs Records. So a patient who booked
ahead gets no "My Visit" tracker and no entry routing until someone taps
"To Reception" by hand. Fixing that means reusing the entry-routing block from
`join_submit` in the check-in path; it changes behaviour, so it needs your
sign-off rather than a quiet commit.

---

## The process fix, enforced

The report named this a **process gap**, so the gap now has a test. Five
regression tests live at the bottom of `tests/test_fasttrack_doors.py` under
*"staff pages must tell the same story"*:

| Test | Pins |
|---|---|
| `test_queue_staff_copy_matches_the_new_routing` | staff queue copy names both entry routes |
| `test_queue_staff_to_reception_does_not_mint_a_second_intake` | one patient, one folder |
| `test_bookings_staff_banner_does_not_call_every_booking_fast_track` | banner admits two doors |
| `test_bookings_staff_marks_fast_track_per_booking` | crown + gold button are per-row |
| `test_checking_in_a_standard_booking_does_not_claim_the_gold_lane` | no gold lane for standard bookings |

**Checklist item to add to your definition of done:** when a change moves
patients through the hospital, open the staff page that describes it and update
it in the same PR.

## Verification

- `tests/test_fasttrack_doors.py`: 20 passed
- Focused run (doors, queue, booking, reception, hims, gate2): 114 passed
- Full SQLite suite: **1123 passed, 8 skipped**
- CI on PR #10, run 35020274878 — **all three jobs green**:
  - tests (SQLite) — pass, 18m 26s
  - tests (PostgreSQL) — pass, 35m 18s
  - dependency audit — pass, 24s
  The only annotations are pre-existing Node.js 20 deprecation notices from
  `actions/checkout@v4` / `actions/setup-python@v5`, unrelated to this change.
