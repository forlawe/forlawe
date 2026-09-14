# Emergency landing page + the three-service dropdown — 2026-09-13

Owner request (four points, plain words):

1. "Anything mark with orange should be remove from affected pages"
2. "Join a queue page should be separated from emergency landing page.
   Emergency landing page carries the same info with Join a queue, booking
   and Fast-Track."
3. "'Which Service Do you Need' should Shows in the drop-down only
   Reception/Front Desk, HIMS/Records, Fast-Track/Premium Service"
4. "'Which Service Do you Need' should be remove from the Emergency landing
   page."

Points 2, 3 and 4 are done and tested. Point 1 needs the screenshots again —
see the last section.

## What changed

### 2 · The emergency landing page is its own page now

| Before | After |
|---|---|
| `/queue/join?emergency=1` rendered the **join-a-queue form** wearing a red hero — service dropdown, Fast-Track gold box, queue explainer, everything | `/emergency` is a **separate page** (`templates/emergency_landing.html`) with emergency content only |
| `/queue/join` switched between a red "emergency" skin and the normal skin | `/queue/join` is the ordinary queue form, always |
| Welcome-page card + emergency banner pointed at `/queue/join?emergency=1` | Both point at `/emergency`; the old address **302-redirects** there so printed posters and old links keep working |

What `/emergency` carries (and nothing more):

- "🚨 Emergency — Go to Accident & Emergency Now" + A&E open 24/7, seen
  immediately, do not wait online.
- One demoted line: call the help desk number · ask for directions · listen.
- **One action**: name + phone → "Get my emergency number". It posts to the
  existing queue engine with the A&E department fixed as a hidden field, so
  the desk and staff screen get the emergency number. No consent box, no
  premium anything.
- "What to do now" — four short lines, all about A&E.
- Help-desk numbers at the bottom (dialable).

It has **no dropdown of any kind, no Fast-Track box, no booking fields and no
queue explainer** — that was exactly the complaint in point 2. A regression
test asserts each of those absences (`tests/test_emergency_landing.py`).

### 3 · The service dropdown shows only three services

"Which service do you need?" (booking) and the same picker on Join-a-queue now
offer exactly, in the owner's order:

1. **Reception / Front Desk**
2. **HIMS / Records**
3. **⭐ Fast-Track / Premium Service**

Implemented in `app/patient_places.py`:

- `service_choices(org_id)` — returns exactly those three departments.
- `ensure_records(org_id)` — reuses whatever the hospital already calls the
  records desk ("Health Information Management (HIMS)", "Medical Records", …)
  and only creates "HIMS / Records" when none exists. Same reuse logic for
  Reception and Fast Track.
- `service_label(dept)` — the owner's wording for each of the three.
- `ensure_emergency_dept(org_id)` — the A&E destination used by `/emergency`,
  reusing the hospital's own A&E name.

One safety rule kept on purpose (it exists because of a real past bug — a
patient picking the paid lounge on the free form with no price and no consent
on screen): on the **free** booking door `/book`, the Fast-Track line is a
*door*, not a value — choosing it walks the patient to `/book/fast-track`
where the price and the premium consent are shown. The free door therefore
still never POSTs the premium department, which is what
`tests/test_fasttrack_doors.py` pins. On `/book/fast-track` and on
`/queue/join` the Fast-Track line is a normal option.

### 4 · No service dropdown on the emergency page

`/emergency` has no `<select>` at all — in an emergency there is nothing to
choose. The A&E department travels as a hidden field. Asserted by
`tests/test_emergency_landing.py::test_emergency_page_is_its_own_page`.

## Files changed

| File | Change |
|---|---|
| `app/views/queue.py` | new `/emergency` route; `/queue/join?emergency=1` redirects; queue dropdown uses the three services |
| `app/views/bookings.py` | `_service_choices()` builds the three-option list for both doors (+ error re-render) |
| `app/patient_places.py` | `service_choices`, `service_label`, `ensure_records`, `ensure_emergency_dept` |
| `app/templates/emergency_landing.html` | **new** — the separate emergency landing page |
| `app/templates/queue_join.html` | emergency skin removed; three-service dropdown |
| `app/templates/booking_portal.html` | three-service dropdown; Fast-Track line on the free door is a door (`data-goto`) |
| `app/templates/patient_hub.html`, `app/templates/_emergency_banner.html` | emergency buttons point at `/emergency` |
| `tests/test_emergency_landing.py` | **new** — 7 regression tests for all of the above |
| `tests/test_f040_emergency_banner.py`, `tests/test_patient_places.py` | repointed at the new page / new three-service rule |

## Checks

- `tests/test_emergency_landing.py` — 7 passed.
- Queue, booking, fast-track doors, patient hub, patient places, F-040 banner
  — all passed after the change.
- Full suite: see the run attached to this branch's pull request.

## Point 1 — the orange marks: the screenshots did not arrive

No image file reached the workspace with this request (checked the workspace
and the repo; the only annotated screenshots in the repo are the 2026-08-30
set that `docs/BUGFIX_2026-08-30.md` already fixed). So nothing orange-marked
could be read or removed this round — **please re-attach the screenshots** and
the marked items will be removed from the affected pages in the same style as
before (quoted back first, then fixed).
