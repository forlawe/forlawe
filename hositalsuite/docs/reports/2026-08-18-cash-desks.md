# Build Report — Billing & Pay-Point Desks
**GENERAL HOSPITAL IJEDE (The Family Hospital)** · 18 August 2026

## ✅ LIVE

```
/api/v1/health  → 200   database:true · scheduler:true · backup ran 17:57
/api/v1/ready   → 200   ready:true
/billing        → 302   (exists, requires login)
/paypoint       → 302   (exists, requires login)
```

**483 tests passing on SQLite AND real PostgreSQL 17.**

---

## 🔴 Still outstanding: revoke the token

`ghp_7FM7…` is visible in this chat. **Please delete it at
github.com/settings/tokens.** It has done its job.

---

## Billing and Pay-Point now have their own screens

You were right that a cashier wants their own screen. But looking closely, the
bigger problem wasn't convenience — it was **who is accountable for the money.**

### The real issue: separation of duties

Before today, the **same receptionist** who took a patient's details was also
the only record that their money had arrived. For a hospital collecting Lagos
State revenue through Megalex, that's a control weakness. Whoever handles cash
should not also be the sole record that the cash came in.

Each desk now records its own step **under its own name**. Verified live with
three different people walking one patient through:

| Action | Recorded by |
|---|---|
| Details taken | **am.funke** (receptionist) |
| Sent to Billing | **am.funke** |
| **Bill raised** | **hod.lab** (billing clerk) |
| **Payment received** | **hod.pharmacy** (cashier) |
| Folder opened | **am.funke** |

If money ever goes missing, that trail names the person at each step.

### What each desk gives the cashier

- **One screen, their own queue** — oldest waiting first, not the whole
  hospital's reception list
- Patient name, payment route, LAHSMA/NHIS number, and what they're paying for
- **Wheelchair and language flags carried through**, so the cashier knows
  before the patient reaches the window
- A minutes-waiting badge that turns red past 20 minutes
- The bill number carried automatically from Billing to the Pay-Point

**Reception keeps its own buttons.** A small hospital where one clerk does
everything must still work — taking that away would break the very users this
was built for.

---

## Two real bugs this uncovered

**1. Billing was measuring the wrong thing.** The existing code stamped
`billed_at` when a patient was *sent to* Billing, and **silently discarded any
bill number** the clerk entered on the way out. So "how long does Billing take?"
was measuring the walk to the desk, not the work done at it. Now stamped when
the bill is actually raised, and the reference is kept.

**2. The screenshot caught what the tests didn't.** The bill-number box rendered
as the literal word **"None"** — a cashier would have typed the real number
after it, producing "None BILL-2026-001". Every test passed; the screen was
simply wrong. That's the third time this session that *looking* found something
*testing* missed.

---

## Deliberately NOT built: an accounting system

The desks record that a bill was raised and that a receipt reference was
entered. **No amounts, no prices, no ledger.**

Megalex is your revenue system and must stay the single source of financial
truth. Storing amounts here would create a second set of books that nobody
reconciles — worse than storing none at all. A test fails the build if a money
column ever appears.

---

## How I verified

| Check | Result |
|---|---|
| Full suite, SQLite | ✅ 483 passing |
| Full suite, real PostgreSQL 17 | ✅ passing |
| Mutation tests | ✅ 6 applied, 6 caught |
| Live walk-through, 3 different staff | ✅ audit trail names each one |
| Voice at each desk | ✅ patient called by name |
| Journey tracking per desk | ✅ each step measured separately |
| Another hospital's patient | ✅ 404 |
| Logged-out access | ✅ blocked |
| Live site after deploy | ✅ healthy |

One mutation initially produced **no output** because my patch had broken the
file's syntax rather than the guard it was aimed at. I spotted that and re-ran
it against the real target before trusting it.

---

## What's genuinely left

| # | Item | Note |
|---|---|---|
| **1** | **A real pilot** | ⭐ Everything is built. What's missing is one morning of real patients |
| 2 | **Role Management** | The last unbuilt item from your original nine — roles are still a fixed list in code |
| 3 | Leave approval workflow | Leave is recorded; no request → approve → balance |
| 4 | CSP still uses `unsafe-inline` | Deliberate, documented |
| 5 | `admincp.py` ~1,245 lines, ~57% covered | Most privileged, least tested file |

---

## Your actions

| # | Action | Time |
|---|---|---|
| 1 | **Revoke `ghp_7FM7…`** | 2 min |
| 2 | Add **`GROQ_API_KEY`** in Render (never `GROQ_MODEL`) | 5 min |
| 3 | Give your cashier a login, open `/paypoint` on their phone | 5 min |
| 4 | Walk one patient front door → home with sound on | 10 min |

---

## One last thing

Three times this session, **looking at the screen found something a passing
test could not**: patients frozen at HIMS, a patient blocked after paying, and
today a box pre-filled with the word "None".

Your tests tell you the code does what you asked. Only your eyes tell you
whether a tired cashier at 8am will get it right.
