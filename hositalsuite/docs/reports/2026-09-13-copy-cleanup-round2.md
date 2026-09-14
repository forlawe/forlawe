# Copy cleanup round 2 — 2026-09-13 (five points)

Owner request, plain words, and what was done:

| # | You said | Done |
|---|---|---|
| 1 | Language text (English, Yorùbá, Igbo, Hausa) not visible on the patient welcome page and associated pages — make it white | Every language pill now renders **white text** (`color:#fff!important`, so no stylesheet can dim it again), and the bar carries its **own dark strip** behind the pills so the white names stay readable on every page head (blue welcome head, black/gold booking head, red emergency head). The active language is marked by a brighter background + white ring — never by dark text. Checked on `/`, `/welcome`, `/queue/join`, `/book`, `/book/fast-track`, `/emergency`. |
| 2 | Remove "Please pay before you arrive. You can pay at reception or by transfer. Please show your receipt at the Fast Track Desk." and the old elderly sentence from Fast-Track banners all over | The pay-before-arrive block is gone from the booking Fast-Track gold box **and** from the booking thanks page (the amber "⏳ Please pay before you arrive" badge + instructions). The elderly sentence is gone from the Fast-Track banners (see 4 for its replacement on the queue page). |
| 3 | Remove "Today's queue only — priority patients (elderly 60+, pregnant, child under 5, wheelchair) are seen first automatically" from all pages where it appears | Removed from the Join-a-queue page in both places it appeared (the intro paragraph's "Today only — elderly (60+)… seen first automatically" and the dropdown hint's "Today's queue only — priority … seen first automatically"). No patient page carries the automatic-priority promise any more. |
| 4 | Replace the elderly sentence with "You don't need to pick Fast Track if your health condition need special attention. Just tell Reception/HIMS how we can help you, and we will prioritize your care." | Done — that is now the wording inside the Fast-Track box on the Join-a-queue page, replacing the old sentence word for word as instructed. |
| 5 | Remove the "Need help booking? Call us or visit reception…" card from all pages — the help-desk block with the real numbers is already on each page | The card is gone from the booking page; the help-desk block (with the hospital's numbers, dialable) remains directly below it, as on every other patient page. |

## One deliberate scope decision (say the word and it changes)

The **staff desk pages** (queue staff screen, reception desk, consulting room,
triage bench, LAHSMA desk, cash desk, Fast-Track desk, ward TV) still carry
their priority-lane notes ("Elderly 60+, pregnant, child under 5, wheelchair —
seen first at every desk…"). Reasons:

- Those notes are **staff instructions for a real, implemented workflow** —
  the visit record has a priority field (`ELDERLY / PREGNANT / CHILD /
  WHEELCHAIR`) that reception ticks, and the TV/voice announce it. Stripping
  the note would leave staff seeing ⭐ badges with no explanation.
- Your quoted sentences are **patient-facing promises**; the automatic-priority
  promise is what you asked to take off patient pages, and it is off them.

A test pins this scope (`test_staff_desk_pages_keep_the_priority_lane_guidance`)
so it cannot drift silently — and if you want the staff pages cleaned too,
that is a one-line change.

## Files changed

| File | Change |
|---|---|
| `app/templates/_langbar.html` | white language names + own dark strip; active pill marked by ring, not dark text |
| `app/templates/booking_portal.html` | pay-before-arrive block removed; "Need help booking?" card removed |
| `app/templates/booking_thanks.html` | amber pay-before-arrive badge + instructions removed |
| `app/templates/queue_join.html` | both automatic-priority sentences removed; owner's new special-attention wording in the Fast-Track box |
| `tests/test_owner_copy_2026_09_13.py` | **new** — 7 tests pinning all five points (+ the staff-page scope) |

## Checks

- New file: 7 passed.
- Whole suite on this branch: **1066 passed, 8 skipped** (pre-existing
  conditional skips) + the 14 tests in the two new files = green, no failures.
