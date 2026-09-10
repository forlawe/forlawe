# ✅ Day 2 done — Bulk staff upload is live

**275 tests passing** on both databases · Live on your site

---

## What it does

Instead of typing 200 forms, you upload the spreadsheet you already have.

**Admin → Users → 📋 Bulk upload staff**

1. **Download a template** — nominal roll, departmental list, or unit/section list.
   (Or skip it and upload your own file — we read most column headings.)
2. **Upload** your CSV or Excel file.
3. **Preview** — see every row before anything is saved: the username we'll create, the
   department we matched, the role, and the exact reason for any problem.
4. **Confirm** — accounts are created and the temporary passwords are shown **once**.

---

## I tested it with YOUR actual duty roster

I typed in the roster you photographed — all 22 staff, with your real abbreviations — and ran
it through. **Every single row imported correctly:**

| Your spreadsheet said | We matched it to |
|---|---|
| `MEDICAL` | Internal Medicine |
| `PUB AFF OFF` | Public Affairs |
| `ADMIN/HR` | Administration & Human Resources |
| `FIN/ACCTS` | Finance & Accounts |
| `NUTRIT&DIET` | Nutrition & Dietetics |
| `HIMS` | Health Information Management (HIMS) |
| `INT AUDIT` | Internal Audit |
| `NURSING` | Nursing Services |
| `ENVIRONMENTAL` | Environmental Health |

And the names became sensible usernames automatically:

| Name on the roster | Username created |
|---|---|
| `MRS ODEBE IDEHAI` | `odebe.idehai` |
| `DR ADENIYI` | `adeniyi` |
| `PHARM UKPE AUGUSTINE` | `ukpe.augustine` |
| `CNO OGUNLEYE` | `ogunleye` |

Titles (Mr, Mrs, Dr, Pharm, CNO, ADNS…) are stripped. If two people would get the same
username, the second becomes `name2`.

**Your extra columns — S/N, DATE, DAYS — are simply ignored.** You don't need to reformat
anything.

---

## Safe by default

Every imported account:

- Gets a **random temporary password** — shown once, never stored in readable form
- **Must change it** at first sign-in
- Starts **awaiting your approval** and *cannot sign in* until you approve it

That last one matters: a spreadsheet must never be able to hand out access to your hospital
system. You approve each person in **Admin → Users**.

Unrecognised job titles become **HOD** (department level), never an admin role.

---

## Two bugs my tests caught while building this

**1. "Deputy Medical Director" was being read as MD/CEO.** The word `md` matched inside
`MEDical`. That would have silently given a deputy the Medical Director's full authority —
exactly the kind of mistake nobody notices until it matters. Specific titles are now checked
first, and short abbreviations only match as whole words.

**2. A bad phone number vanished silently.** Something like `not-a-number` was stripped to
nothing and dropped with no warning — you'd never know the number hadn't been saved. It now
warns you on the preview screen.

**3. A design flaw I avoided:** the existing roster import stores its preview in the browser
session, which holds about 4KB — roughly **24 rows**. Your nominal roll would have silently
overflowed it. I measured this before building (200 rows = 33KB) and stored previews properly
instead. Tested with 400 rows.

---

## How to use it with your real staff list

1. Open your existing staff spreadsheet (or download our template).
2. Make sure there's a header row with at least a **Name** column.
3. Admin → Users → **📋 Bulk upload staff** → choose the file → **Preview**.
4. Check the preview. Rows with problems are highlighted in red and skipped — the rest import.
5. **Confirm**, then **copy or print the passwords immediately** (there's a Copy all button).
6. Go to **Users** and approve the people you recognise.

---

## Where things stand

| | |
|---|---|
| Tests | **275 passing** — SQLite and PostgreSQL 17 |
| Every link and form | verified to resolve |
| Upgrade path | tested against the previous release's database |
| Live site | `status: ok`, database ✅, scheduler ✅, backup ✅ |

---

## Your remaining list

- ⬜ **Revoke the GitHub token** you pasted in chat — github.com/settings/tokens
- ⬜ **Add `GROQ_API_KEY`** to Render for the AI assistant (3 min, free — see `AI_SETUP.md`)
- ⬜ **Supabase backups** — Database → Backups
- ⬜ **Press "Add any missing standard departments"** in Admin → Structure
- ⬜ **Then:** Days 3–4 — unified roster with leave management, and role permissions
