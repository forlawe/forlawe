# 1.7.4 — Map-picked gate + honest HOD clock-in

**Date:** 24 August 2026  
**Version:** 1.7.4 (not pushed)  
**Voice reminders:** stay on.

This batch only. Map + honest clock-in. No GitHub push.

## What was broken on the live phone

| What you saw | Why |
|---|---|
| Gate check Off, no map on I am here | Pin lived under Admin → Configuration as typed numbers |
| Sites map was a blank box | Page loaded the map skin, never the map engine |
| Super Admin signed in, Who empty | Closed dropdown + no list of names |
| HOD could not open Who is at work | Board needed a hospital-wide tick HOD does not have |
| Needs review had no button | Flag was a label only |

## What you do now

| Who | What to tap |
|---|---|
| System Admin | **I am here → Gate pin** — drop the pin, stretch the circle, pick Off / Record / Must be inside, Save |
| System Admin | Same map also works on **Admin → Sites** and **Admin → Config** |
| HOD / supervisor | **I am here** shows **Who** as a name list (not a hidden box) and **Why** as tappable reasons |
| HOD / supervisor | Photo of the person at the gate is still required |
| HOD / supervisor | **Who is at work today** — own department only |
| HOD / supervisor | **Needs your sign-off** → Accept (with a short note) |

## Anti-connivance (does not change)

- HOD cannot sign someone from another department.
- Free-text story is not enough. Pick a fixed reason + take a photo.
- A fake-place app is refused when the gate is **Must be inside**.
- Flagged punches stay on the board until a supervisor accepts them.

## One job for you on the live hospital

Every staff account must have a **department** set (Admin → Users).

If a nurse has no department, their HOD cannot see them on Who. That is on purpose — it stops a friend in another ward covering for them.

## Tests

20 attendance tests passed, including:

- HOD sees own department board, not Pharmacy
- HOD can help own staff with photo + reason
- HOD cannot help Theatre / cannot sign-off Lab
- Admin pins the gate from I am here
- HOD cannot change the gate
- Supervisor Accept writes `reviewed_at`

## Not in this batch

Messaging paper is still a file only (not pushed).  
Native voice bank still waiting for your pick.  
No deploy.
