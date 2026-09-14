# Consultant round-2 diff sheet — applied 2026-09-14

The consultant's "Patient Journey — Round 2 Fixes (Developer Diff Sheet)"
(verified against `main`) was reviewed item by item against this branch.
Three of the six items were **already implemented in earlier rounds of this
branch** (and are pinned by tests); the rest are applied here, plus the
design-system unification. Owner's copy where the two disagree (see 5b).

| # | Consultant item | Status on this branch |
|---|---|---|
| 1 | HIMS direct registration / desk-started visit doesn't auto-queue | **Applied now** — `views/hims.py` `register_save()` and `start_visit()` enter the journey tracker at the HIMS stage via `tracking.safely(tracking.enter, …, staff_id=current_user.id)`, exactly the consultant's replacement. The "already has an open visit today" branch correctly gets no new segment (already tracked). Pinned by `tests/test_consultant_round2.py` (3 tests). |
| 2 | Rename the hub tile to "My Visit Journey" | **Applied now** — `patient_hub.html`: 📺 icon, title "My Visit Journey", description "Live tracker with your position, wait time, and voice updates." Pinned. |
| 3 | Separate Emergency from Join-Queue | **Already done** (round 1, commit `eb17f93`): dedicated `/emergency` page with its own template, no dropdown, A&E fixed as a hidden field, old `?emergency=1` links 302-redirect, hub card + banner repointed, `is_emergency` branches removed from `queue_join.html`. **Enhanced now**: emergency registrations are tagged `source="emergency"` on the ticket (consultant's snippet created its own ticket path; ours reuses the full queue engine — personal TV session, intake, announcements — and now tags the source too). Pinned in `test_emergency_landing.py` + `test_consultant_round2.py`. |
| 4 | Dropdown = Reception / Records / Fast-Track only | **Already done** (round 1): `patient_places.service_choices()` returns exactly those three (owner's order and labels), stronger than the keyword filter proposed — it also guarantees the departments exist and reuses the hospital's own HIMS/Records name. Pinned in `test_patient_places.py` + `test_emergency_landing.py`. |
| 5 | Text removals / replacement | **Already done** (round 2, commit `bb04170`): pay-before-arrive gone from booking gold box + thanks page; "Today's queue only…" gone from patient pages; "Need help booking?" card gone. **One deliberate deviation**: the replacement sentence uses the OWNER's wording ("…if your health condition need special attention. Just tell Reception/HIMS…"), not the consultant's ("needs … Reception/Records") — the owner's instruction wins. Staff pages keep the priority-lane note (owner-approved scope, pinned). |
| 6 | Premium design-system unification | **Applied now** — see below. |

## Item 6 — one shared patient-portal design system

- `app/static/css/app.css`: appended the shared `.pp-*` system (`.pp-hero` +
  gold/emergency variants, `.pp-step-label`, `.pp-input`, `.pp-hint`,
  `.pp-gold-box`, `.pp-btn` primary/gold/emergency, `.pp-badge-gold`), built
  entirely on the existing `:root` tokens (`--primary`, `--ink`, `--ink-2`,
  `--muted`, `--line`, `--line-soft`, `--primary-light`, `--primary-glow`,
  `--red`) so the F-080 contrast fixes and any future palette change
  propagate to every patient page at once.
- Migrated off hand-rolled hex blocks:
  - `booking_portal.html` — local `<style>` deleted; **gold hero now renders
    only on the gold door** (`/book/fast-track`); the free door gets the
    standard `.pp-hero`. This closes the "gold hero on the normal door" bug
    the consultant found.
  - `queue_join.html`, `emergency_landing.html` — local `<style>` deleted,
    everything on `.pp-*`.
  - `complaint_portal.html`, `feedback_portal.html` — the two "bare form"
    pages now open with a `.pp-hero` and use `.pp-step-label` / `.pp-input` /
    `.pp-btn`, so a complaint filed two minutes after a booking looks like
    the same product. (Feedback keeps only its star-widget style, which is
    already token-based.)
  - `patient_hub.html` — hard-coded hexes in its style block swapped to
    tokens (`--ink`, `--muted`, `--line`, `--faint`, `--line-soft`,
    `--primary-light`); the intentional gold luxury gradient is untouched.
- Pinned by 5 tests in `tests/test_consultant_round2.py`: tokens exist and
  are token-based; gold hero only on the gold door; every patient page uses
  `.pp-input/.pp-step-label/.pp-btn` and none of the old local classes
  (`input-big`, `step-label`, `hero-gold`); no page-local hero style blocks
  remain; complaint/feedback carry the shared hero.

## Files changed this round

`app/views/hims.py`, `app/views/queue.py` (emergency source tag),
`app/models.py` (source comment), `app/static/css/app.css`,
`app/templates/{patient_hub,booking_portal,queue_join,emergency_landing,complaint_portal,feedback_portal}.html`,
`tests/test_consultant_round2.py` (new, 10 tests).

## Checks

New file + hims + hub + emergency + booking + queue + feedback + complaints +
a11y + founder-ux suites green (see PR comment); full suite run attached.
