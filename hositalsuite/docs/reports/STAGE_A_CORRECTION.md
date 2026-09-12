# Stage A corrected — patient experience, not EMR + the voice

**Date:** 16 August 2026 · **Version:** `1dcd973` · **Live:** https://hospital-suite.onrender.com/hims/

---

## You were right on both counts

> *"the App is not EMR. The App is to make patient feel satisfy, have great and sweet experience while visiting the hospital and beyond. So keep it simple and don't forget voice reminder"*

**I drifted.** I built blood group, genotype, allergies, chronic conditions and a red *"⚠ do not miss"* clinical banner aimed at doctors. That is a medical record. You never asked for it — I added it because it *felt* thorough. Thorough in the wrong direction is just wrong.

**And I gave Stage A no voice at all**, even though you had already told me voice is a standing requirement.

Both are now fixed.

---

## 1. What I took out

| Removed | Why |
|---|---|
| Blood group, genotype, allergies, chronic conditions | This is the hospital's clinical record, not yours. Holding medical data you have no business holding is also a **liability under NDPA** |
| The red *"⚠ Important — do not miss"* banner | Written for doctors. Wrong audience, wrong app |
| Marital status, religion | Nobody's experience improves because we recorded it |

**I also added a guard so it cannot come back.** A test now fails if anyone — including me in a later session — adds a `blood_group`, `genotype`, `allergies`, `diagnosis`, `prescription` or `vital_signs` column to a patient folder.

---

## 2. What I put in instead — how to treat the person at the door

| Field | What it does |
|---|---|
| **Language they're comfortable in** | English · Yorùbá · Hausa · Igbo — so they're greeted in their own language |
| **Help they need** | Wheelchair · Elderly, offer a seat · Pregnant, offer a seat · Hard of hearing · Poor sight · Walks with difficulty · Comes with a carer · Needs an interpreter |
| **Anything else the desk should know** | e.g. *"travels from Ikorodu — try not to keep them waiting"* |

The folder banner is no longer a red medical warning. It is now:

> **💛 Looking after Lekan:**
> Needs a wheelchair
> Prefers Yorùbá — greet them in it
> travels from Ikorodu

Same idea, but it's about **courtesy**, not medicine.

---

## 3. The voice — the part that was missing

Four new announcements, spoken aloud at the desk the moment a patient arrives. These are the **real sentences** captured from the live test:

| When | What is actually said |
|---|---|
| Patient registered | *"Team, Abatan has been registered and is waiting for Triage."* |
| People waiting | *"Mr Tunde, 3 patients are waiting at the drug dispensary. Please attend to them."* |
| **Needs help — URGENT** | *"Team, Abatan at the reception desk needs help. Needs a wheelchair; Prefers Yorùbá — greet them in it; travels from Ikorodu"* |
| Regular returns | *"…is back with us at reception. Please welcome them."* |

Two deliberate decisions:

- **A wheelchair request gets its own URGENT call.** Somebody who cannot stand should not be left standing while a message sits unnoticed on a screen.
- **Registering ahead of time announces nothing.** The desk is only told when a patient is genuinely at the door — otherwise the voice becomes noise people learn to ignore.

---

## 4. Proof

| Check | Result |
|---|---|
| Tests on SQLite | **345 / 345** (43 for Stage A) |
| Tests on real **PostgreSQL 17** | **345 / 345** |
| Browser checks on a phone | **20 / 20** |
| Link checker | Clean |
| Live site | Healthy · database OK · scheduler alive · backup ran |

**Mutation-tested the voice** — I deleted the assistance announcement (1 test failed) and then all arrival voice (3 tests failed). The tests genuinely bite; they aren't decoration.

The browser check now also asserts the downloaded register contains **no** medical data.

---

## 5. Please check on your phone

Open `/hims/`, register a test patient, tick **"Needs a wheelchair"**, and confirm you *hear* the announcement. If the phone is silent, tap the screen once first — browsers block audio until you touch the page, and the app shows an "enable sound" banner for exactly this.

---

## 6. Next: Stage B — Triage, kept simple

Given your correction, here's how I'd now scope Triage — please confirm before I build:

| I **will** build | I will **not** build |
|---|---|
| Place the patient in OPD / SOPD / MOPD / Emergency | Any symptom or clinical scoring |
| Use category, day of week, clinic of the day, available doctors | Vital signs, temperature, blood pressure |
| Show and speak the waiting count and the wait time | Any diagnosis or notes about what is wrong |
| Announce by name when it's their turn | |
| Carry the wheelchair / seat / language flags through to the next desk | |

Say **go** and I'll build exactly that — or tell me what to change first.
