# Stage A — HIMS Register (patient folders)

**Hospital:** GENERAL HOSPITAL IJEDE (The Family Hospital)
**Date:** 16 August 2026
**Live:** https://hospital-suite.onrender.com/hims/
**Version pushed:** `506e8c6`

---

## 1. What you asked for

> **2. HIMS - Register**
> **i. open folder for new/first visit patient**
> **ii. Search for the folder of returning patient**

Both are built, tested and live. There is a new **HIMS** button in your menu.

---

## 2. The honest picture: what was missing before

Your suite had **no patient**. That sounds dramatic, so let me be precise.

A booking stored a name as text. A queue ticket stored another name as text. Nothing joined them. If Mrs Abatan booked in March and came back in August, that was **two unrelated rows of text** — not one person with a history.

This meant the system could not answer any of these:

- Has this patient been here before?
- What is her hospital number?
- Is she LAHSMA, Megalex or paying cash?
- Is she allergic to anything?
- Who do we call if she collapses?

Every later stage — Triage, the Call Room Queue, sending patients on to LAHSMA / Billing / Megalex / Laboratory / Pharmacy — needs one thing to exist first: **a folder with a number on it.** That is what Stage A creates.

---

## 3. How the desk works now

### Step ① — Always search first
One box. Type **any** of these and it finds them:
- the hospital number — `IJD/2026/00042`
- the phone number — `08059826879`, or even just `2801586`
- the surname — `abatan`
- the first name — `Lekan`
- both together — `abatan lekan` **or** `lekan abatan`

If nothing is found it says so plainly and offers to open a new folder — carrying whatever you typed into the form, so you don't type it twice.

### Step ② — Open a folder for a first-visit patient
The form is in five plain sections:

| Section | What it holds |
|---|---|
| **Who is the patient?** | Surname, first name, other names, sex, date of birth **or age**, marital status, occupation |
| **How do we reach them?** | Phone, second phone, address, LGA (defaults to Ikorodu), State (defaults to Lagos) |
| **Next of kin** | Name, relationship, phone, address — **required** |
| **How are they paying?** | LAHSMA · Megalex · Self-paying · NHIS · Private HMO · Exempt, plus the scheme number |
| **Clinical basics** | Category, blood group, genotype, allergies, chronic conditions |

Then: *"Start today's visit? Yes — the patient is here now, send them to Triage."*

The hospital number is assigned automatically — **IJD/2026/00001**, then 00002, and so on.

---

## 4. The five decisions I made, and why

**1. Search before create — the system stops you making a duplicate.**
If you try to open a folder for someone who looks like an existing patient, it **stops** and shows you the matching folders with a button *"That's them — open it"*. Only if you tick a box saying you've checked and it really is a different person will it proceed. Two folders for one patient means half her history in each — that is the classic way a HIMS desk fails, and it is very hard to undo later.

**2. Never invent a birthday.**
Many of your patients genuinely do not know their date of birth. Forcing a date means clerks type `01/01/1980` for everyone and the data becomes a lie. So: enter a **date of birth if you have one, or just the age**. The folder records honestly which one it is.

**3. Next of kin is compulsory.**
If a patient collapses, somebody must be reachable. The form will not save without a next-of-kin name and phone.

**4. Insurance without a number is refused.**
A LAHSMA, NHIS or HMO patient with no scheme number means **Billing cannot claim** — the hospital does the work and loses the money. The form now refuses it and says why.

**5. Age corrects the category.**
If a clerk leaves the category on "General adult" but enters age 6, the system files them as **CHILD**; age 72 becomes **ELDERLY**. Triage decisions in Stage B depend on this being right, so it is not left to a busy clerk on a rushed morning. An *explicit* choice like "Antenatal" is always respected.

---

## 5. What the doctor sees

Open a folder and anything dangerous is at the top **in red**:

> **⚠ Important — do not miss:**
> Allergic to: penicillin
> Genotype SS — sickle cell
> hypertension

Below that: contact, next of kin, payment route, clinical details, and the full **attendance history** — every visit, its date, the reason, and its status.

---

## 6. Payment routes — using your own answers

You told me: *"LAHSMA — Lagos state owned health insurance"* and *"Megalex — a private payment system that help all Lagos state owned hospitals to collect revenue."*

Both are built in as payment routes on the folder, alongside self-paying, NHIS, private HMO and approved exemption. The route is **copied onto every visit**, so when Stage D sends a patient onward to Billing or Megalex, the route travels with them instead of being asked again.

---

## 7. Proof — I do not ask you to take my word

| Check | Result |
|---|---|
| Full test suite, SQLite | **336 / 336 pass** (34 new, for Stage A) |
| Full test suite, real **PostgreSQL 17** | **336 / 336 pass** |
| Link checker | Every link and form points at a real route |
| Real browser, phone screen (390×844) | **17 / 17 checks pass** |
| Live site after deploy | Health OK · database OK · scheduler alive · backup ran today · Roster and patient hub unaffected |

### I also tested my own tests
Passing tests can be worthless. So I deliberately **broke the code three times** and confirmed the tests caught it each time:

| I broke… | Tests caught it? |
|---|---|
| The duplicate-folder check | ✅ 2 tests failed |
| The next-of-kin requirement | ✅ 1 test failed |
| The age → category rule | ✅ 1 test failed |

If they had still passed, the tests would have been decoration.

### The browser check found a real bug
The register showed the surname as **ABATAN** but the downloaded CSV said **Abatan** — the screen and the file disagreed about the same patient. Small, but it is exactly the kind of thing that makes two systems fail to match later. Surnames are now stored uppercase the way they are on a paper folder, search still works whatever case you type, and I added a test so it cannot come back.

---

## 8. Known limits — stated plainly

| Limit | Why | Risk |
|---|---|---|
| Existing bookings and queue tickets are **not yet linked** to folders | They keep their own name/phone. Linking them is Stage B's job, when Triage picks a patient up. | None today — nothing changed behaviour |
| **No photograph** on the folder | You did not ask for it, and photos are heavy on a free server | Low — say the word |
| **No bulk import** of an existing paper register | Every folder is opened at the desk. If you have thousands on paper we should discuss it. | Depends on your backlog |
| Folder numbering uses your org code — currently **`IJE/2026/00001`** | Taken from the hospital's short code in the system | Tell me if you want a different format |
| Search does not yet cope with **misspellings** (`Abatam` won't find `Abatan`) | Exact and partial matching only, for now | Low — phone number always finds them |

---

## 9. Still outstanding on the whole project

**Patient flow:** Stage A ✅ done. Stages B, C, D, E remain.
**From your earlier list of 9 upgrades:** 8 delivered; **Role Management** still open.
**Also open:** leave approval workflow, cross-department roster clash warning.

---

## 10. Things only YOU can do

| # | Action | Why | Time |
|---|---|---|---|
| 1 | **Revoke the GitHub token** `ghp_82Db…` | Still live, still visible throughout our chat. Most urgent item. | 2 min |
| 2 | **Open one real folder on your phone** at `/hims/` | So we catch anything I've missed while it's cheap to fix | 5 min |
| 3 | Add `GROQ_API_KEY` in Render | Smarter patient assistant, free | 5 min |
| 4 | Turn on Supabase backups | Second safety net | 2 min |
| 5 | Set administrative departments to "Office hours, Mon–Fri" in Admin → Structure | Their rosters then behave correctly | 5 min |
| 6 | Enable the test runner (`ci/README.md`) | Tests run on every change | 5 min |

---

## 11. What next?

| # | Item | Effort | Value |
|---|---|---|---|
| **1** | **Stage B — Triage.** Place patients into OPD / SOPD / MOPD / Emergency by need, category, day of the week, clinic of the day and available doctors. | Medium | ⭐⭐⭐⭐⭐ |
| 2 | **Stage C — Call Room Queue.** Doctor is rostered **and** clicks "ready to consult"; Triage assigns patients to Consulting Room 1/2/3/4 or Emergency; each doctor sees only their own room's queue. | Large | ⭐⭐⭐⭐⭐ |
| 3 | **Stage D — Onward routing** to LAHSMA / Billing / Megalex / Laboratory / Pharmacy / Emergency | Medium | ⭐⭐⭐⭐ |
| 4 | **Stage E — Voice** wired through every step, calling patients and staff by name | Small | ⭐⭐⭐⭐ |
| 5 | Link existing bookings and queue tickets to folders | Small | ⭐⭐⭐ |
| 6 | Role Management — create your own roles | Medium | ⭐⭐⭐⭐ |
| 7 | Something else you have in mind | — | — |

My recommendation: **Stage B**, straight on. The folder now exists; Triage is what gives it somewhere to go.
