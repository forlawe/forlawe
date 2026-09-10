# Accessibility pass — report §15 item 5

Date: 2026-09-04 · Method: systematic static sweep of every template
(81 root + 34 admin) plus rendered-HTML checks of every public page, followed
by fixes and pinned tests (`tests/test_a11y_pass.py`).

## Verdicts — checked and already sound

| Check | Verdict |
|---|---|
| `<img>` alt text | **All** images across every template carry `alt` (decorative ones use `alt=""`). Pinned by test. |
| Document language | `<html lang>` set from the real page language (F-022 work). |
| Landmarks | `base.html` has `<nav>` and `<main>`; every portal page has `<main>`. |
| Flash messages | Text + category class, not colour-only. |
| Icon-only controls | Header icon links carry `title` + the nav is text; chat mic/back/call buttons carry `aria-label`. |
| Chat live region | `#msgs` is `aria-live="polite"`; composer input labeled. |
| Login / change-password / chat forms | Already fully labeled. |
| Client-side validation | Uses `required`/`min`/`max` attributes (native, announced). |

## Fixed by this pass

1. **Skip link** — `base.html`, `chat.html`, `booking_portal.html`,
   `complaint_portal.html`, `feedback_portal.html` now start with a
   keyboard-only "Skip to main content" link targeting `#main-content`.
   `/login` is deliberately exempt: a single sign-in card is the first and
   only content — there is nothing to skip past.
2. **`aria-current="page"`** — all 27 nav links in `base.html` now mark the
   active page server-side (works without JavaScript).
3. **Programmatic labels** — the visible labels on the booking portal (5
   fields), complaint portal (6), feedback portal (3), and both status
   lookup pages (2 each) were not associated with their fields; a screen
   reader announced bare "combobox/edit text". All now use `for=`/`id=`;
   the complaint contact-method select (which had no label at all) got an
   `aria-label`.
4. **Keyboard-hostile toggle** — the TV night-mode control was an `onclick`
   `<div>`: untabbable, unnamed, invisible to assistive tech. Both TV
   templates (`clinic`, `main`) now render a real `<button>` with
   `aria-pressed`, and the brightness range input is labelled. Pinned by
   source test.

## Known gaps (documented, not silently ignored)

- **Staff-side admin forms** use a `<label>` *above* the field without
  `for=` in many admin templates (~350–400 fields by heuristic count).
  Screen-reader users tabbing get an unnamed field. The pattern is uniform,
  so a mechanical `for=`/`id=` pass is possible but is a large diff across
  every admin screen; it should be done template-by-template with visual
  review rather than in one sweep. The patient-facing set (above) is done.
- **Colour contrast** cannot be verified statically here; recommend one
  browser-DevTools pass over `app.css` tokens (gold-on-black Fast Track
  badge is the main risk) before launch.
- TV wall-display pages run headless in normal operation (no keyboard),
  which is why their remaining inline `onclick` buttons are acceptable;
  the night toggle was still fixed as a matter of principle.
