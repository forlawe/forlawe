# The reviewer was right about the big thing — it is now fixed

**For:** the founder, General Hospital Ijede
**Date:** 20 August 2026

---

## 1. Short version

The reviewer's headline point — *"62 manual org_id filters and ZERO RLS…
you are exactly one missed filter away from a catastrophic data leak"* — was
**correct**, and it was the single most important thing anyone has said about
this system.

**It is now fixed and tested.** The database itself refuses to hand one
hospital's data to another.

Two of their other three recommendations I have **not** done, and I will
explain honestly why. Doing all four just because a confident reviewer listed
them would have cost you money and added things you do not need.

---

## 2. I proved the danger before fixing it

I do not act on a review without checking. So I wrote the exact bug a tired
developer would write — a query with the hospital filter missing — and ran it
against a real PostgreSQL database with two hospitals in it:

```
Rows a forgotten filter returns: ['ABATAN', 'SECRET']
LEAK
```

`ABATAN` is Ijede's patient. `SECRET` belongs to the other hospital. **One
missing line, and a patient list crosses hospitals.** The reviewer was not
being dramatic.

After the fix, the identical query:

```
BEFORE RLS this returned: ['ABATAN', 'SECRET']
NOW returns             : ['ABATAN']
RESULT: CONTAINED — database refused
```

---

## 3. Where the reviewer was wrong (in your favour — and against it)

I checked their numbers. Two were off.

| Their claim | Reality | Effect |
|---|---|---|
| "62 manual org_id filters" | **244** in real query code. The 62 was a miscount — they counted column definitions, not filters | **Worse than they said.** 244 places to forget, not 62. Strengthens their argument |
| "The 1 monolithic JS file… will hit 2,000+ lines" | It is **749 lines** | Fair warning, not yet a problem |

I would rather tell you the number is worse than let a comforting figure stand.

---

## 4. What I built: the seatbelt

PostgreSQL is now told, table by table: *"only ever return rows belonging to
the hospital named on this connection."* **28 tables** are protected — patients,
visits, complaints, folders, the audit log, uploaded files, everything.

The 244 existing filters **stay exactly where they are**. They are now a second
layer, not the only thing standing between two hospitals. Defence in depth: the
app asks for the right rows *and* the database refuses to hand over the wrong
ones.

### Four decisions that made it real rather than decorative

**a) The owner must not bypass it.** PostgreSQL exempts a table's owner from its
own rules by default — and Supabase connects as the owner. Without one extra
command (`FORCE ROW LEVEL SECURITY`), this entire feature would look correct in
every test and protect **nothing** in production. This is the most common way
RLS is got wrong. There is a test that reads PostgreSQL's own catalogue to
prove FORCE is on.

**b) Unset means "see nothing", never "see everything".** If the hospital is
somehow not set on a connection, the database returns zero rows. The opposite
default is how RLS rollouts leak: one forgotten code path silently gets
god-mode.

**c) The hospital is taken from the signed-in session, never from the browser.**
If it could be set by a web address or a header, an attacker would simply say
"I am hospital 2" — handing them the exact switch this removes. There is a test
that reads the source and fails if that ever changes.

**d) Background jobs declare themselves.** The scheduler and nightly backup
genuinely work across all hospitals. They now say so explicitly in the code. I
had to fix these as part of this work — without it, **SLA escalation would have
silently stopped and your nightly backup would have written an empty file that
looked like a success.** That is a worse failure than a crash, because nobody
notices for months.

---

## 5. I broke it on purpose, three times

A security test that passes no matter what you break is worse than no test —
it makes you confident for no reason.

| What I sabotaged | Caught? |
|---|---|
| Removed `FORCE` (the classic fake-RLS bug) | ✅ **5 tests failed** |
| Made "unset" mean "see everything" | ✅ caught |
| Made the hospital readable from a browser header | ✅ caught |

The first one matters most: it is the mistake that produces security theatre,
and the tests catch it loudly.

---

## 6. The two recommendations I did NOT follow

### ❌ "Move session storage to Redis so you can horizontally scale"

**Not needed, and it would cost you money.**

Your sessions are **signed cookies**, not server-stored sessions. There is
nothing on the server to share, so you could run ten copies of the app tomorrow
and nobody would be logged out. The reviewer assumed server-side session
storage; your app does not use it.

Redis would be **a new paid service, a new thing to run, and a new thing to
break** — solving a problem you do not have.

*(There is a real reason you run one worker — the scheduler must run exactly
once, or every reminder sends twice. That is documented, deliberate, and
unrelated to sessions.)*

### ⚠️ "Abstract the org filter into `get_org_scope()`"

**Good idea. Deliberately not now.**

This means changing all 244 filters at once. Every one is a chance to introduce
the exact bug we just closed. With RLS in place the urgency is gone — the
database now catches a forgotten filter.

The right time is gradually, as each file is touched anyway. Doing it in one
sweep, today, on a system with no pilot behind it, is how you turn a fixed
problem back into a broken one.

### ⏸️ "Profile the heaviest 5 Jinja templates"

Reasonable, but premature. Your load test recorded **4,000 requests per minute
with 0% failures** on one worker — far beyond one hospital. Optimising before a
real pilot means guessing which pages are slow. Let the pilot tell us.

---

## 7. On their verdict

> *"Who this is dangerous for: any SOC2/HIPAA compliant app, or any app storing
> sensitive PII across competing businesses."*

Fair before today. This is a Nigerian government hospital, so HIPAA and SOC2 do
not apply — but **NDPA** (Nigeria Data Protection Act) does, and the principle
is identical: patient data must not cross between organisations.

That was the genuine gap. It is now closed at the database level, which is the
only place it can be closed properly.

> *"You built a racecar with no seatbelts."*

Accurate, and fairly put. **The seatbelt is now fitted and crash-tested.**

---

## 8. Evidence

| Check | Result |
|---|---|
| Leak reproduced before the fix | ✅ returned another hospital's patient |
| Same query after the fix | ✅ returns only your own |
| Tables protected | **28** |
| RLS tests on real PostgreSQL 17 | **11 passed, 1 skipped** |
| Three deliberate sabotages | ✅ all caught |
| Full suite on SQLite | **644 passed, 0 failures** |
| Full suite on real PostgreSQL 17 | **651 passed, 0 failures** (38 min) |

**Nothing for you to do on Render.** No new setting, no new service, no cost.
It switches itself on at startup and logs `row-level security active on 28
table(s)`.

---

## 9. What I would do next

| # | Item | My view |
|---|---|---|
| **1** | **Run a real pilot and film it** ⭐ | Unchanged, and now stronger. Everything is built and the biggest security hole is closed. What you do not have is one morning of real patients. |
| 2 | Gradual `get_org_scope()` tidy-up | Do it file by file, not in one sweep |
| 3 | Leave approval workflow | Leave is recorded; no approval chain |
| 4 | Patient satisfaction vs journey time | You already hold both halves of the data |
| 5 | Split the JS file | At 749 lines, not yet. Revisit near 1,500 |

---

### Note on the PostgreSQL run

Finished: **651 tests, 0 failures, 38 minutes** on real PostgreSQL 17 — the 11
RLS tests run for real there (they skip on SQLite, which has no such feature).
SQLite: 644 passed. **Both engines green before anything was pushed.**

*(One thing worth noting: partway through, an earlier run reported "disk I/O
error" failures. I checked before assuming the worst — it was an orphaned test
process from an interrupted run fighting over the same file, not a fault in the
code. Cleaned up, re-run, green. Worth mentioning because a scary error message
is not always a scary problem.)*
