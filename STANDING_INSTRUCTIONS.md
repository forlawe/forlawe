# Standing instructions from the owner (recorded 2026-09-13)

These are the owner's standing rules for how work must be delivered in this
repository and workspace. They apply to every task until the owner says
otherwise. Quoted from the owner:

## 1. Reports: always written, always opened, always downloadable

> "you must always write and open up reports in this workspace and they
> must be downloadable without further request"

- Every report or deliverable is written as a real file — in this repo when
  it is project work, so it reaches the PR and GitHub.
- It is opened in the file viewer proactively when finished. The owner
  never has to ask to see it.
- It is downloadable without any further request: the workspace viewer
  download for anything in the sandbox, GitHub for everything in the repo.
  No "I'll share it if you ask" — the download is part of finishing.

## 2. Screenshots are the preferred way to show a problem

> "that is the fastest means to show you exactly where there is problem"

- The owner shows problems via screenshots. Any attached image is read
  immediately, in the same turn it arrives, using
  `hositalsuite/tools/read_screenshot.py` (OCR).
- The text found on the screenshot is quoted back first — errors, URLs,
  values, buttons — so the owner can confirm we are looking at the same
  thing, before any fixing starts.
- Never claim inability to read a screenshot. If an attachment did not
  land in the workspace, say exactly that — "the file didn't arrive,
  please re-attach" — never "I can't see screenshots". (Raw image vision
  is unavailable in some sessions; the OCR tool is the reliable path.)
- Honest limits: OCR reads text, not styling. Handwriting or very low
  quality crops may fail — say so and ask for the text rather than
  guessing.

## 3. Rules that were already in force (unchanged)

- Branch discipline: work lands on `main` via PR from this session's
  branch `arena/01a097c6-forlawe` (the session is platform-pinned to it);
  ordinary merge only, never force-push, never rewrite `main`'s history.
- Deliverables are real files in the repo/PR — no patch files or zips as
  deliverables.
- Communication: plain English.

## 4. Environment notes (why some things "disappear")

The sandbox wipes everything OUTSIDE this repository between messages
(the Python venv, databases, background servers, logs). Consequences:

- Commit and push durable work immediately; the repo (and GitHub) is the
  only permanent storage.
- The test rig (venv + PostgreSQL) is rebuilt per turn when needed.
- Background servers (gunicorn preview, long test runs) only live during
  an active turn. A long run must be allowed to finish without the owner
  sending a new message mid-run, or it is killed.
