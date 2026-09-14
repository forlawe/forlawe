# Patient-interface copy pass — short, clear, premium (2026-09-14)

Owner: *"Upgrade and enhance the patient hub/patient interface pages by
removing repetition of instruction/direction, make each page's instruction
presentation short but still meaningful with clear tone and premium
presentation style."*

## The rule applied to every page

**Say each thing once.** If a promise appears in the hero, it does not appear
again in a hint, a box, and the footer. Orientation ("what happens next") is
shown as **premium numbered step chips** (`.pp-steps`, added to the shared
design system in `app.css`) instead of four-line prose boxes.

## Page by page

| Page | Repetition removed | New short presentation |
|---|---|---|
| **Welcome hub** | Lux card pitch was three sentences + a three-part badge; emergency card was three sentences | Sub: "Book ahead — walk straight to our quiet executive lounge." Badge: "⭐ PREMIUM • EXECUTIVE LOUNGE • SEEN FAST". Emergency card: one sentence — "Go straight to Accident & Emergency (open 24/7) — tell reception it's an emergency and you will be seen immediately." |
| **Join-a-queue** | Privacy promise appeared 3× (hero, under-button hint, footer); routing explained 2×; "What happens next?" 4-line box repeated the tracker promise | Hero: "A private live tracker for every stage of your visit. Your number shows on TV — never your name." Routing hint: "New here? Reception / Front Desk. Already have a folder? HIMS / Records. Short on time? ⭐ Fast-Track." Gold box: one line. Steps chips: 1 Number + private tracker · 2 Watch the TV · 3 Come forward when called. Footer no longer repeats the privacy line. |
| **Booking (both doors)** | "How it works" paragraph + phone hint + under-button hint all repeated the reference/WhatsApp/15-min-early story; time hint added nothing | Steps chips: 1 Book a day & time · 2 Get your reference · 3 Arrive 15 min early · 4 Show it at reception. Phone hint carries the channel once: "Your reference and updates arrive here — WhatsApp first, then SMS." Service hint: "Reception / Front Desk · HIMS / Records · ⭐ Fast-Track (premium)." |
| **Emergency** | Hero, form note and "What to do now" box each restated go-to-A&E/seen-immediately | Hero: one sentence. Steps chips (red): 1 Go to A&E · 2 Tell reception it's an emergency · 3 Show your number. Form note: "Your emergency number shows at the desk and on the staff screen — never your name." |
| **Complaint** | Hero was two sentences repeating the privacy note | Hero: "Every complaint is read and acted on. Track yours privately with a reference." |
| **Feedback** | Privacy note repeated the hero verbatim | Hero keeps the pitch; note is now the standard one-line privacy token line. |

## Still meaningful (short ≠ silent) — all pinned by tests

- Privacy promise on the queue page (once), premium consent wording
  untouched (F-039 single legal sentence), owner's special-attention sentence
  untouched, help-desk numbers on every page, routing hint matches the real
  routing (the pin in `test_fasttrack_doors.py` was re-worded to the new
  copy, same promise).
- "quiet, private lounge" now appears exactly **once** per premium page —
  in the legal consent line, not duplicated by marketing copy.

## Files

`app/static/css/app.css` (+`.pp-steps` chips), `app/templates/{queue_join,
booking_portal, emergency_landing, patient_hub, complaint_portal,
feedback_portal}.html`, `tests/test_patient_copy_premium_pass.py` (new,
6 tests), `tests/test_fasttrack_doors.py` (pin re-worded).

## Checks

New tests + every patient-page suite green; **full suite: 1096 passed,
8 pre-existing skips**.
