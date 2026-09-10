# Role Management — built, tested and ready to push

**For:** the founder, General Hospital Ijede (The Family Hospital)
**Date:** 20 August 2026
**Status:** built, all tests passing, checked in a real browser at phone size

---

## 1. The short answer to your question

You asked whether I could still build this without running out. **Yes — and it
is built.** Everything below is finished, tested and working. Nothing is half
done.

---

## 2. What you asked for, and what you got

| You asked for | What was built | Done? |
|---|---|---|
| **i.** Menu access limited to the staff's role in their department/unit/station | Roles are now rows in the database with a tick-list you edit on screen. The menu and the server both read the same list, so what a person sees and what they can reach can never disagree. | ✅ |
| **ii.** HOD and Staff see only things relating to their own department/unit/station | A "My Department" screen, plus complaints and patient-flow figures filtered to their own department. Typing another department's web address returns "not allowed". | ✅ |
| **ii.** Staff efficiency measured against patient flow to the department, daily | Today's arrivals vs. today's handled, with a plain-English verdict. Never a league table — reasons below. | ✅ |
| **iii.** Several staff working at once, same task or different tasks, in one department | A shared "who is on what" noticeboard. Anyone may join anything; everyone sees who else is on it. | ✅ |
| **HOD** sees their department's complaints and can respond **or escalate before it times out** to the MD/CEO or any higher authority | A new "Escalate to higher authority" panel on every complaint, with a countdown, a reason box and a list of real people. Plus a spoken warning to the HOD *before* the clock runs out. | ✅ |
| **Voice reminder** (your standing rule) | Four new spoken announcements: a colleague joining your task, a department falling behind, a complaint escalated to you, and a complaint about to run out of time. | ✅ |

---

## 3. What it looks like on your phone

### For an ordinary member of staff or an HOD

They now see a **My Department** button on the dashboard and in the menu. It
shows four numbers for today:

| Came here today | Dealt with | Still waiting here | Typical time here |
|---|---|---|---|

Then one honest sentence, for example:

> *"2 of 10 handled, 8 still waiting. This department is falling behind the
> flow coming in."*

Below that, the **who is working on what** board, and below that, what each
person carried today.

### For you (the administrator)

**Admin → Roles & permissions**. Every role is listed. Click one and you get a
page of tick boxes in plain English:

- *Work the Reception desk*
- *Open and search patient folders (HIMS)*
- *Escalate a complaint to higher authority*
- *See who in my department is working on what*

Tick, untick, Save. It takes effect immediately. **No developer, no restart,
no new version of the app.** That was the whole point.

You can also **create a brand-new role** — "Pharmacy Technician", "Ward
Clerk", "Security Supervisor" — for a job the hospital has that the software
did not know about.

---

## 4. Three decisions I made, and why

### a) Efficiency is a ratio, never a league table

The obvious thing to build is a ranking: patients per hour, best at the top,
put it on the wall. **I deliberately did not build that**, and I want you to
know why before you ask for it.

The nurse who takes twenty minutes with a frightened elderly patient looks
"slow". The one who rushes them out in four minutes looks "efficient". Put
that on a wall and within a month you have taught the entire department to
rush — and rushing is exactly what patients complain about.

So the measure is always **what arrived vs. what was handled**, for the
department as a whole. Where an individual number is shown at all, it is
labelled *workload* (how much they carried), the list is sorted by **name**,
and there is no winner. Sorting by output turns a list into a ranking whatever
you call it.

If you disagree, tell me — it is your hospital. But I would be doing you a
disservice not to say it plainly first.

### b) Working together is a noticeboard, not a lock

The normal software answer to "two people might touch the same job" is a lock:
first person claims it, everyone else is refused. That is wrong for a hospital.
Two porters really do move one trolley. Three nurses really do clear one queue
together. A second clerk joining a long reception line is help, not a conflict.

So anyone may join anything. What the system guarantees is that you can always
**see who else is on it** — so the same patient is never called twice by two
different people. The one thing it refuses is the same person claiming the same
task twice, which is a double-tap on a phone, not a second worker.

### c) Escalating early is recorded as a decision, not a failure

The old system only escalated automatically, at the deadline, which is a
punishment. An HOD knows within twenty minutes whether "the generator is down
and I have no budget" is theirs to fix.

Now an HOD can send it up **on purpose, early, with a reason in their own
words**. The audit trail records that as a **different action** from an
automatic timeout. That distinction matters enormously: if an HOD who spots a
problem early is scored the same as one who let it lapse, every HOD quickly
learns to sit on problems until the deadline.

**One thing I refused to do:** escalating does **not** extend the deadline. It
is the same promise to the same patient. If escalating bought four more hours,
"escalate" would become the button everybody presses to make the red light go
away.

---

## 5. Bugs I found while building this

Honest list. Every one of these was found by a test or a real browser, not by
guessing.

| Bug | What would have happened | Fixed |
|---|---|---|
| The new voice announcements crashed silently every single time (`name` was being passed twice) | **Not one** of the new voice reminders would have worked, and nothing would have appeared in the logs | ✅ |
| The same bug existed in the escalation code | The MD would never have been told out loud that a complaint was escalated to him | ✅ |
| Escalation audit rows were saved with no hospital attached | The record of who escalated what would have been invisible to your hospital | ✅ |
| Ordinary staff could have stepped a colleague off a task | One tap could wipe a colleague's record of work they actually did | ✅ |
| Three roles quietly changed behaviour when I moved the rules into the database | The Admin Manager would have lost Referrals; the HIMS HOD would have lost Bookings | ✅ |

That last one is worth dwelling on. When I moved the rules from code into the
database, I first wrote a test that asks **both** the old rules and the new
ones the same question for every role, and fails on any difference. It caught
three real changes I had not intended. Without that test I would have shipped
them and you would have found out from a confused member of staff.

**One honest note:** the old rules did *not* give the APEX Nurse complaints,
referrals, corrective actions or reports. That looks like an oversight from a
long time ago rather than a decision. I reproduced it **exactly** so nothing
changes underneath anybody the day this ships — but it is now **one tick** for
you to fix on the Roles screen. Please look at it.

---

## 6. What I did to be sure it works

| Check | Result |
|---|---|
| Full test suite on SQLite | **632 passing** (was 583 — 49 new tests) |
| Full test suite on real PostgreSQL 17 | **632 passing** (36 minutes, 0 failures) |
| The migration run against a real PostgreSQL database, twice | ✅ passes, and safe to re-run if a deploy retries |
| Real Chromium browser at 390px (phone width) | **16 checks passed, 0 failed** |
| Tick boxes big enough for a thumb | ✅ 22×22 pixels |
| Nothing overflows the phone screen sideways | ✅ 0 pixels too wide |
| No JavaScript errors on any new page | ✅ |
| **Mutation testing** — I deliberately broke my own code to prove the tests are real | ✅ see below |

### The mutation tests

A test that passes no matter what you break is worse than no test at all,
because it makes you confident for no reason. So I broke things on purpose:

| What I broke | Did a test catch it? |
|---|---|
| Removed the department filter from the complaints list | ✅ caught |
| Made "join a task" an exclusive lock that refuses the second person | ✅ caught |
| Made escalating secretly reset the deadline to 4 hours | ✅ caught |
| Removed a power from the HOD role | ✅ caught |
| Stopped the migration creating the teamwork table | ✅ caught |

Every one failed the tests, which means the tests are actually doing their job.

---

## 7. Nothing that worked yesterday has changed

This is the part I was most careful about.

- Your existing eight roles are **untouched**. They are seeded as "built-in"
  roles with exactly the powers they always had.
- The `role` column on every staff record is **untouched**. The new tables sit
  alongside it, they do not replace it.
- If the new role tables were ever unreadable, the app **falls back to the old
  rules** rather than showing a blank menu or, far worse, handing somebody the
  administrator's menu. There is a test that deliberately breaks it and proves
  this.
- If you edit a built-in role, a restart will **not** undo your edit. A
  settings screen that quietly reverts is worse than no settings screen.
- The Super Administrator role **cannot** untick its own way back in. Locking
  the only person who can fix a mistake out of the screen that fixes it would
  need a database engineer to undo.

---

## 8. One thing to do after this goes live

There is a new role called **Staff**.

Until now, every account had to be given a management role just to sign in.
That is exactly why HODs kept turning up in menus they had no business seeing —
there was no such thing as an ordinary member of staff.

**Please go through your staff list and change the ordinary workers to
"Staff".** They will then see only their own department's work, which is what
you asked for. Nobody is forced — everyone keeps working exactly as they do
today until you change them.

---

## 9. Still outstanding on your side (unchanged, still important)

| Action | Why it matters |
|---|---|
| **Revoke the GitHub token `ghp_7FM7…`** | It has been shown in this chat. Anyone who sees it can change your hospital's software. Please do this today. |
| **Add `GROQ_API_KEY` in Render** (and **never** `GROQ_MODEL`) | The AI assistant is built and tested but is not actually live without it. |
| Second UptimeRobot monitor on `/api/v1/ready` | Catches a database problem, not just a dead web page. |
| Turn on Supabase backups | Your only protection against losing everything. |
| Test the voice on your phone | Tap the screen once first — Android will not speak until you do. |

---

## 10. Where we are, and what is next

**Everything on the original list of nine is now built.** Role Management was
the last one.

| # | Next thing | My honest view |
|---|---|---|
| **1** | **Run a real pilot and film it** ⭐ | This is now, by a very long way, the most valuable thing you can do. Everything is built. Nothing new will be learned from more building. One morning of real patients will teach you more than another month of features — and gives you something to show the Commissioner. |
| 2 | Leave approval workflow (request → approve → balance) | Leave is recorded but there is no approval chain. |
| 3 | Patient satisfaction linked to journey time | "Did the people who waited longest complain most?" — powerful, and you already hold both halves of the data. |
| 4 | Predicting tomorrow's load from history | Useful, but only after a pilot gives it real history to learn from. |
| 5 | Cross-department roster clash warnings | Small quality-of-life fix. |
| 6 | HIMS fuzzy-spelling search (find "Abatan" when someone typed "Abatun") | Small, and staff would feel it every single day. |

**My recommendation is unchanged and now stronger: number 1.** You have a
complete system and no evidence that it survives contact with real patients.
That, not a missing feature, is the biggest risk to this project.

---

### Note on the PostgreSQL run

The full PostgreSQL 17 run finished: **632 tests, 0 failures, 36 minutes.**
The migration itself was separately verified against real PostgreSQL 17 twice
(including a repeat run, to prove a retried deploy is safe).

Both engines are green. Nothing was pushed until they were.
