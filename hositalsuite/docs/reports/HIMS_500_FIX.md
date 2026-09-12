# The HIMS 500 — what broke, and what I did about it

**Reported by:** your screenshot, 16 August 2026, 18:50
**Fixed and live:** `213312b`
**Status now:** `/api/v1/ready` returns `{"ready":true}` against your live database

---

## Thank you for the screenshot

You found a page that was **completely broken in production** — every visit to HIMS returned "500 — Something went wrong on our side." My tests were all green. Your screenshot was worth more than all of them.

Stage B is paused until this was properly closed out. It now is.

---

## What actually went wrong

Two bugs. Both mine.

### Bug 1 — I edited a migration that had already run on your live database

When you told me the app is not an EMR, I removed blood group, genotype and allergies. But I removed them by **editing the instruction file that had already been carried out** in production.

An analogy: the builder already built the house to plan A. I then went back and edited plan A, instead of issuing a change order. The builder looks at his records, sees "plan A — done", and does nothing. The house never changes.

So your live database kept the old columns and **never got the new ones**. The app then asked for a column that wasn't there:

```
column patient.preferred_lang does not exist
```

Every HIMS page died on that line.

### Bug 2 — found while fixing Bug 1: migrations could target the wrong database

While verifying the fix, I noticed the upgrade tool was **ignoring which database you told it to work on** and silently using a different one — while printing a cheerful "Running upgrade…" message.

This is worse than it sounds: it means any check of the form "I ran the upgrade and it worked" was **proving nothing**. Fixed.

---

## How I fixed it

1. **A new migration** (`b3f81a9d5c22`) — the change order the builder will actually read. It adds the three care columns and removes the six medical ones, and is safe whatever state a database is in.
2. **A safety net** — if the migration system is ever skipped, the app now adds those columns itself at start-up.
3. **The upgrade tool** now honours the database you point it at.

Removing the medical columns is also the right thing under **NDPA**: don't keep data you don't need.

---

## How I proved it, rather than hoping

I rebuilt your production database exactly:

| Step | Result |
|---|---|
| Booted the **previously deployed code** against an empty PostgreSQL | Recreated your live schema precisely: `allergies`, `blood_group`, `genotype` |
| Ran the new code over it | **Reproduced your 500** — `no such column: patient.preferred_lang` |
| Applied the fix | Columns appear · medical columns gone · **existing patient folders survive** · query succeeds |

Then confirmed on the real thing: your **live** `/api/v1/ready` now returns `{"ready":true}`.

---

## The part I want to be honest about

I wrote a guard test to catch this class of bug. **It passed against the bug.** It was useless.

The reason: the test suite builds each test database from scratch, which always produces correct columns — so it never exercises the *upgrade* path, which is the only path that broke. My test was checking a scenario that could never fail.

I only found this because I deliberately re-introduced the bug to see whether the test caught it. It didn't.

**The replacement builds a database in the exact shape yours was in**, stamps it at the old version, runs the upgrade the way Render does, and checks the result — including that existing patient folders are not lost. I re-introduced the bug again: this time the suite **fails**, as it should.

Lesson recorded in the code itself, so the next person (or the next me) reads it.

---

## New permanent protection

**`/api/v1/ready` now checks the schema, not just the connection.**

A reachable database is not the same as a usable one — connectivity looked perfect throughout this outage. The app now compares what it expects against what the database actually has, and reports exactly what's missing:

```json
{"ready": false, "reason": "schema drift", "missing": ["patient.preferred_lang"]}
```

**Worth doing:** point UptimeRobot at `/api/v1/ready` as a *second* monitor, alongside your existing `/api/v1/health` one. Health tells you the app is alive; ready tells you it's actually working. Had this existed yesterday, you'd have been alerted instead of discovering it yourself.

---

## Verified

| Check | Result |
|---|---|
| Tests, SQLite | **353 / 353** |
| Tests, real PostgreSQL 17 | **353 / 353** |
| Production upgrade path, reproduced | Fixed, folders preserved |
| Live `/api/v1/ready` | `{"ready":true}` |
| Live `/api/v1/health` | database OK · scheduler alive · backup ran |
| Link checker | Clean |

---

## Please confirm

Sign in and open **HIMS** on your phone again. It should now show the register with the search box, not the 500 page.

If it looks right, say **go** and I'll start Stage B — Triage, scoped as agreed: placement into OPD / SOPD / MOPD / Emergency, waiting counts, calling patients by name out loud, and carrying the wheelchair / seat / language flags forward. **No** symptom scoring, **no** vitals, **no** diagnosis.
