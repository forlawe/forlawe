# Gate 1 — Design-system unification: DONE (2026-09-14)

The consultant's gate, in their words: finish the design system first —
the four missing shared states as reusable blocks, then forbid page-local
styling again. Gate passes when **no patient page defines its own
hero/input/step styling and the four states exist and are used.**

Both conditions are now true, and pinned by tests so they cannot rot.

## 1. The four shared states now exist — one way to say each thing

New reusable blocks, styled once in `static/css/app.css` (`.pp-state*`)
and rendered through Jinja macros in `templates/_pp_states.html`:

| State | Says | Look | Where it is used |
|---|---|---|---|
| `pp_state_waiting` | "hold on" | soft blue, pulsing icon, shimmering band | live queue ticket (WAITING) |
| `pp_state_empty` | "nothing here yet" | quiet dashed box, no blame | complaint status — "No messages yet" |
| `pp_state_error` | "that went wrong" | honest red, `role="alert"` | booking status, complaint status, the 404/403/429/500 error page |
| `pp_state_success` | "all done" | warm green, `role="status"` | booking thanks, complaint thanks, feedback thanks, ticket DONE |

Each has a compact inline variant (`pp_state_inline`) for one-line states
inside cards, plus a standalone shimmer bar (`pp_shimmer`).

## 2. Page-local styling is gone from every patient page

Before: 4 patient templates carried private `<style>` blocks (hub ~60
rules, queue ticket ~45, feedback stars, emergency banner keyframes) and
the pages held ~150 inline `style="..."` attributes between them.

After — all moved into the shared system in `app.css`:
- **Hub**: tiles, luxury Fast-Track card, share box, emergency card, footer.
- **Queue ticket ("My Visit Journey")**: the whole page design, renamed to
  prefixed `tk-*` components (top band, code, KPIs, live-now box, journey
  timeline, voice bar, called panel, help bar, privacy foot) so nothing can
  collide with the rest of the app.
- **Shared emergency components** (`emerg-*`) now used identically by the
  hub card, the emergency landing page and the banner include.
- **Langbar** (owner's white-text rule kept with `!important`, now in CSS),
  **star picker**, **consent check-lines** (plain + gold), **portal head
  doors** (gold/red), **reference boxes**, tiny layout utilities
  (`w-560`, `mt-sm`, `btn-block`, …).
- JS visibility toggles moved from inline `style.display` to the `hidden`
  attribute (hub share box, copy-done note, emergency banner).

Audit result: **0** `<style>` blocks and **0** inline `style="` attributes
across all 19 patient templates (pages + shared includes).

## 3. Nothing was lost

- Every owner-dictated sentence survives verbatim (special-attention
  sentence, "quiet, private lounge" exactly once per premium page,
  "WhatsApp first, then SMS" exactly once, hub premium badge, F-040 one
  primary action, emergency pins, help-desk block everywhere).
- Two tests pinned the OLD mechanism (inline style strings) rather than
  the owner's intent; they were updated to pin the same intent through the
  new mechanism (the colour rule now asserted in `app.css` + the primary
  button class counted in markup). Intent unchanged, wording unchanged.

## 4. Evidence

- New suite `tests/test_gate1_design_system.py` — 11 pins: states exist in
  CSS + macros; no template carries private styling; standalone pages
  render with no `<style>` at all; components live in `app.css`; success /
  waiting+shimmer / called / done / error / empty states all verified on
  REAL rendered pages (booked visit, submitted complaint, joined queue,
  bad reference, 404); pinned owner copy survives.
- Full suite: **1111 passed, 8 skipped** (one unrelated interpreter flake
  in `test_smoke.py::test_am_crawl` under parallel run — passes standalone).

## 5. What Gate 1 deliberately did NOT do

No copy changes, no layout redesigns, no new features — Gate 2 (one page
at a time, Queue first) owns those. The foundation is now one box of LEGO:
every patient page pulls its hero, inputs, steps, buttons and states from
the same shelf.

**Next gate:** Gate 2 — Queue / My Visit Journey page pass (thumb-first,
feedback-on-tap, forgiving forms, calm honest copy), only after the
consultant re-verifies Gate 0 (#4/#6) on a fresh deploy of main.
