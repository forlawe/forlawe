# The Roster — one page for the whole hospital

**Hospital:** GENERAL HOSPITAL IJEDE (The Family Hospital)
**Date:** 16 August 2026
**Live:** https://hospital-suite.onrender.com/roster
**Code version pushed:** `d4082d0`

---

## 1. What you asked for, and what you now have

| # | You asked for | Status | Where it is |
|---|---|---|---|
| — | Merge Admin Roster and Department Roster into one page called "Roster" | ✅ Done | One menu item, "Roster". The old "Dept Roster" menu item is gone. |
| i | Bulk upload for nominal roll, department, unit and section rosters | ✅ Done | "⬆ Upload a roster file" on the Roster page |
| ii | Any date range — a day, 7 days, 2 weeks, 3 weeks, a month | ✅ Done | "Which dates?" drop-down, plus "Choose my own dates" |
| iii | Pick the department, unit or section that owns the roster | ✅ Done | "Who does this roster belong to?" drop-down |
| iv | Single-person and multi-person shifts; 12 hours, 24 hours, and Mon–Fri administrative departments | ✅ Done | Four working patterns; **unlimited** people per shift |
| v | Staff on different types of leave covered in the roster template | ✅ Done | 8 leave types, in the same page and the same upload file |

---

## 2. Answers you gave me, and what I did with them

**"LAHSMA = Lagos State health insurance. Megalex = private payment system that helps all Lagos State hospitals collect revenue."**
Noted and recorded. These are **onward destinations after consultation** — Stage D of the patient flow. Nothing built yet; it is next.

**"Call Room Queue is a queue waiting to see a particular doctor in one of the consulting rooms."**
Understood. That is Stage C: each doctor sees only the patients queued for *their* room. Nothing built yet; it is next.

**"Merge the Admin Roster and department roster into one page called Roster."**
That is what this report is about. Done, tested, deployed.

---

## 3. Honest assessment — what was actually wrong before

I want to be straight with you: the old rosters were **not** good enough for a real hospital. Four things were genuinely broken, not merely missing.

| Problem | What it meant on the ward | Now |
|---|---|---|
| The department roster had exactly **two staff boxes** | A ward with nine nurses on nights **could not be rostered**. There was physically nowhere to put the third person. | Unlimited people per shift |
| **Sections and units could not have a roster** | You can create "Nursing › Female Ward › Side Ward" on the Structure page — but the roster refused to see it | Any department, section or unit can own its roster |
| **Administrative departments were forced into shifts** | Procurement, Internal Audit, Finance & Accounts, ICT and Admin/HR were offered "DAY 07:00–19:00 / NIGHT 19:00–07:00". Nobody believed that roster, so nobody used it | New "Office hours, Monday to Friday" pattern. It also **refuses weekend duty** and tells you why |
| **Leave did not exist** | Nothing stopped anybody rostering a nurse who was away on annual leave. You would only find out when she did not turn up | Leave is on the roster, and the system now **refuses** to place someone on duty during their leave |

I could have patched around these. I did not, because each patch would have left the underlying shape wrong. The roster is now one row per person per day, which is the shape a hospital actually needs.

---

## 4. What the page does now

### Choose what you want to see
- **Who does this roster belong to?** — Admin Manager (hospital-wide), a Department, a Section, or a Unit.
- **Which dates?** — Today · Next 7 days · Next 2 weeks · Next 3 weeks · Next 30 days · This calendar month · **Choose my own dates**.

### Four working patterns per department
| Pattern | Shifts | Suits |
|---|---|---|
| Two 12-hour shifts per day | DAY 07:00–19:00, NIGHT 19:00–07:00 | Wards, Nursing, Emergency |
| One 24-hour duty per day | 24H 07:00–07:00 | Departments that run a single continuous duty |
| Three 8-hour shifts per day | MORNING, AFTERNOON, NIGHT | Larger nursing divisions |
| **Office hours, Monday to Friday** | OFFICE 08:00–16:00 | **Procurement, Internal Audit, Finance & Accounts, ICT, Admin/HR** |

Set it in Admin → Structure, or right on the Roster page. Staff-per-shift now goes up to 20, not 2.

### Eight kinds of leave
Annual · Casual · Sick · Study · Maternity · Compassionate · Examination · Off duty

Type a start and end date once and the system creates every day in between, so *any* day you look at tells you the truth.

### Bulk upload — nothing is saved until you approve it
Columns: **Name, Date, End Date, Shift, Leave Type, Section, Unit, Note.** Only **Name** and **Date** are required.

You upload → the system checks every single line → you see a preview with a verdict per line → **then** you press Save. Rejected lines are never guessed at; each says why in plain English, e.g.:

> *"No active staff account matches **SOMEBODY WHO LEFT**. Add them under Admin → Users first, or correct the spelling."*
> *"PHARM KAREEM is on annual leave on 21 Aug — they cannot be on duty that day."*
> *"Sat 22 Aug is a weekend and this department is set to 'Office hours, Monday to Friday'."*

Names are matched the way spreadsheets are really typed: **"MRS ABATAN L.F"**, **"CNO Ogunleye"** and **"pharm kareem"** all find the right person, titles and capitals ignored.

### Download / print
One button gives you a CSV of exactly what is on screen — hospitals still print rosters and pin them up.

---

## 5. Nothing was lost, and nothing you use broke

| Concern | What I did |
|---|---|
| Old department roster entries | **Copied** into the new roster automatically at start-up. The old table is left completely untouched — if anything had gone wrong, the original data is still sitting there. |
| Duty reminders, overdue-inspection chasing, the AM compliance report | These all read the Admin Manager roster. I did **not** move that table. Everything still works exactly as before. |
| Old `/dept-roster` bookmark or phone shortcut | Still works — it redirects to the new page. Verified live. |

---

## 6. Proof — I do not ask you to take my word for it

| Check | Result |
|---|---|
| Full test suite on SQLite | **302 / 302 pass** |
| Full test suite on real **PostgreSQL 17** | **302 / 302 pass** |
| Link checker (`tools/check_links.py`) | Every link and form on every page points at a real route |
| Real browser, phone-sized screen (390×844) | **21 / 21 checks pass** |
| Live site after deploy | Health OK, database OK, scheduler alive, backup ran today |

The 21 browser checks drive the real page with **your own nominal roll names**, and include:
- four nurses on **one day across two shifts** (impossible in the old design)
- a **five-day leave block** becoming five leave days
- the system **refusing** to put PHARM KAREEM on duty during his annual leave
- Internal Audit **refusing** a Saturday duty
- a **section** owning its own roster
- the CSV export containing real names
- the Save button reachable on a phone screen, nothing pushed off-screen

---

## 7. A mistake in my own earlier work — found and fixed

I have been telling you the tests pass "on both SQLite and PostgreSQL". **That claim was not true, and it was my fault.**

The test setup file hard-coded the database to SQLite. So when I set a PostgreSQL address, it *silently ignored it* and tested SQLite again. Every previous "passes on PostgreSQL" was unproven.

I fixed it, and the very first genuine PostgreSQL run **failed immediately** — a test was issuing a SQLite-only command (`PRAGMA`) that PostgreSQL rejects outright. That test is now engine-aware.

Your production database on Supabase **is** PostgreSQL. So this matters: from now on, "passes on PostgreSQL" means it really was tested on PostgreSQL. Today's 302/302 PostgreSQL run is the first honest one.

---

## 8. Known limits — stated plainly

| Limit | Why | Risk to you |
|---|---|---|
| The Admin Manager roster still allows **one person per day** | Duty reminders and the compliance report are built around "the manager on duty today". Changing it would rewrite three other features. | None — this matches how you work today |
| The old `dept_roster_entry` table still exists (read-only) | Deliberate safety net so nothing is lost | None; it will be retired after a few weeks of live use |
| Upload limit **5,000 rows** per file | Protects the free 512 MB server from a runaway spreadsheet | None realistically — that is months of a large ward |
| Leave is not yet an **approval workflow** | You asked for leave *in the roster*. A request → approve → balance system is a bigger feature. | None today; say the word and I will build it |
| No clash warning **across departments** yet | If the same nurse is rostered by two different HODs on the same night, each sees only their own list | Low, but real. Worth doing — listed below |

---

## 9. What is still outstanding on the whole project

**From your earlier list of 9 upgrades:** 8 delivered. The one still open is **Role Management** — the 8 roles exist with proper labels and permissions, but there is no screen where you can *create your own role* and choose what it may do.

**Still to build:**
1. **Patient flow, Stages A–E** — Booking → HIMS Register → Triage → Consulting Room Queue → onward to LAHSMA / Billing / Megalex / Laboratory / Pharmacy / Emergency
2. **Role Management** — create, edit and delete roles; choose each role's permissions
3. **Leave approval workflow** — request, approve, and leave balances per staff member
4. **Cross-department clash warning** on the roster

---

## 10. Things only YOU can do (please do these)

| # | Action | Why it matters | Time |
|---|---|---|---|
| 1 | **Revoke the GitHub token** `ghp_82Db…` and issue a new one | It has been visible in our chat throughout. Anyone with it can change your code. **This is the most urgent item.** | 2 min |
| 2 | Add `GROQ_API_KEY` in Render | Turns on the smarter patient assistant. Free, no card. | 5 min |
| 3 | Turn on Supabase backups (Database → Backups) | Second safety net beside the app's own nightly backup | 2 min |
| 4 | Enable the automatic test runner (see `ci/README.md`) | Tests then run on every change, not only when I run them | 5 min |
| 5 | Press "Add any missing standard departments" in Admin → Structure | Installs all 31 standard departments | 1 min |
| 6 | **Set the working pattern for each administrative department** to "Office hours, Monday to Friday" | Procurement, Internal Audit, Finance & Accounts, ICT, Admin/HR. Their rosters will then behave correctly. | 5 min |
| 7 | Try the Roster page on your phone and upload one real ward roster | So we find anything I have missed while it is still cheap to fix | 10 min |

---

## 11. What would you like next?

Please pick a number and I will start immediately.

| # | Item | Effort | Value |
|---|---|---|---|
| **1** | **Patient flow Stage A — HIMS Register** (open a folder for a new patient, search the folder of a returning patient). Everything downstream depends on it. | Medium | ⭐⭐⭐⭐⭐ |
| 2 | Patient flow Stages B & C — Triage placing patients into OPD/SOPD/MOPD/Emergency, and the **Call Room Queue** per doctor | Large | ⭐⭐⭐⭐⭐ |
| 3 | Patient flow Stage D — onward routing to **LAHSMA / Billing / Megalex / Laboratory / Pharmacy / Emergency** | Medium | ⭐⭐⭐⭐ |
| 4 | **Role Management** — create your own roles and choose what each may do | Medium | ⭐⭐⭐⭐ |
| 5 | **Leave approval workflow** — staff request leave, you approve, balances tracked | Medium | ⭐⭐⭐ |
| 6 | Cross-department clash warning on the roster | Small | ⭐⭐⭐ |
| 7 | Roster **auto-fill** — "cover the next 30 days with these 6 nurses" and the system builds it fairly | Medium | ⭐⭐⭐ |
| 8 | Something else you have in mind | — | — |

My recommendation: **number 1**, and then straight through 2 and 3. The patient flow is the heart of what you set out to build, and Stage A is the foundation every later stage stands on.
