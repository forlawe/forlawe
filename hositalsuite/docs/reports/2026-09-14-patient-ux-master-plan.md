# Patient pages — UX plan, RESCOPED after consultant review (2026-09-14)

The original 12-step vision is kept below as the **backlog** (nothing is
discarded). The **build plan** is now the consultant's gated sequence,
because the foundation comes first: nothing decorative gets built on top
of anything that can still 500.

Owner rule adopted verbatim: *"not yet, and not all at once. Fix what's
broken, unify what's inconsistent, then earn the right to build the nicer
things on top of something that actually works."*

---

## THE BUILD PLAN (gated — each gate must pass before the next starts)

### Gate 0 — Foundation: Issues #4 and #6 closed and re-verified

- **#4 (boot-transaction poisoning)** — code fixes confirmed in this branch
  and now pinned by tests:
  - every boot step runs through `app/boot.py:run_boot_step()` — its own
    transaction, rollback on failure, next step starts clean
      (test: `test_run_boot_step_rolls_back_and_keeps_the_session_usable`);
  - `seed_roles` / `seed_branches` declare the cross-hospital RLS scope
    (`all_orgs()`) before writing protected tables;
  - a restart against an existing database re-uses the seeded hospital,
    departments and passwords — no re-seed, no new random password
      (test: `test_restart_does_not_reseed_or_mint_new_passwords`);
  - live probe 2026-09-14: `GET /book`, `/queue/join` on the test deploy
    return 200 with full forms; `/api/v1/health` = `status:ok`,
    `database:true`, `scheduler:true`, `last_backup:2026-09-14T02:00`.
- **#6 bug 1 (login double-submit 500)** — fixed in this branch:
  `_lock_row()` catches the unique-index collision, rolls back and takes
  the row the other request created (tests:
  `test_lock_row_survives_a_double_submit_race`,
  `test_lock_row_still_creates_a_fresh_row_when_there_is_no_race`).
- **#6 bug 2 (scheduler app context)** — already fixed in this codebase
  (`tick()` pushes app context + `background_all_orgs()`); the live probe's
  02:00 backup is the evidence it runs.
- **Gate passes when:** the consultant re-verifies #4 and #6 directly on a
  fresh deploy of `main` after this branch merges (restart twice, login
  twice fast, watch /book /queue/join /complaint and the scheduler log).

### Gate 1 — Design-system unification (vision Step 3)

Already largely landed (`.pp-*` system, token-based, gold hero only on the
gold door). Finish the four missing shared states — waiting shimmer,
empty, error, success — as reusable blocks, then forbid page-local
styling again. Low risk, touches every page, everything else builds on it.
**Gate passes when:** no patient page defines its own hero/input/step
styling and the four states exist and are used.

### Gate 2 — One page at a time, smallest first, starting with Queue /
My Visit Journey

Apply vision Steps 4, 5, 6 and 11 (thumb-first, feedback-on-tap, forgiving
forms, calm honest copy) to ONE page. Verify. Show the owner. Then the next
page (booking → emergency → complaint/feedback → status/thanks).
Never two pages in parallel.
**Gate passes per page:** the page's tests green + owner says "yes, next".

### Gate 3 — Only now the deferred items, each its own small project

- **Step 1, honest version:** a 3–5 person usability test on the TEST site
  once it is stable and has a working journey — not "watch real patients"
  on traffic that doesn't exist yet.
- **Step 7:** voice everywhere (four languages) — extend what exists
  (speaker buttons already on key pages) page by page.
- **Step 9:** deep offline / low-bandwidth work (offline status checks,
  slow-connection banner).
- **Step 12:** analytics for the four numbers (time-to-book, taps-to-book,
  give-ups, confused calls) — a SEPARATE engineering task with its own
  design, not a byproduct of redesigning pages. Until it exists we do not
  claim to "watch four numbers forever".

---

## THE VISION BACKLOG (the original 12 steps, unchanged as goals)

1. Watch real users first (now: 3–5 person test once stable — Gate 3).
2. One page, one job (the room rule).
3. One box of LEGO for every page (Gate 1).
4. Thumb-first layout (Gate 2).
5. The page always answers back (Gate 2).
6. Forms that hold your hand (Gate 2).
7. Every page can talk and listen (Gate 3).
8. A human is always one tap away (already true — keep it).
9. Kind to slow internet and old phones (Gate 3).
10. Remember me kindly (Gate 2 copy + Gate 3).
11. Calm, honest, trustworthy (Gate 2).
12. The grandma test + small safe steps (the acceptance bar for every gate).

## What changed versus the first version of this plan

- Sequencing: foundation → unification → one page → deferred extras.
- Step 1 reworded from aspirational to achievable.
- Step 12's metrics declared a separate project, deferred, not promised.
- Everything else kept; nothing discarded.
