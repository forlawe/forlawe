# Build 3 — New hospital setup walk

**Date:** 23 August 2026  
**Build:** 1.4.0  
**Item closed:** 3 (Onboarding wizard)

Voice reminders stay on. This is still **not an EMR**.

---

## What you get

A founder can open a new hospital from a phone in about five minutes. No developer. No command line.

| Step | What they type | Why |
|------|----------------|-----|
| Welcome | Setup code only if this site already has a hospital | Stops strangers opening a second hospital on Ijede's live site |
| Hospital | Name, short code, phone, address | Code goes on folder numbers (`SUN/2026/00001`) |
| You | Name, sign-in, password, phone | First Super Admin. Password is never stored in the browser cookie |
| Look + sites | Three colours, Main, optional Annex | Colours are **this hospital only** |
| Care | Usual departments + voice language | Booking → Register → Triage → Doctor → next desk |

At the end they are signed in and hear: *Your hospital is ready.*

---

## Safety (checked before push)

| Risk | What we did |
|------|-------------|
| Random extra hospital on the live site | After the first hospital exists, `/start` needs a one-time code from Admin → Security |
| Weak or stolen password in a cookie | Password is only sent on the final save, never kept in the session cookie |
| Duplicate hospital code or `admin` sign-in | Plain English error. Suggests `ijd.admin` because `admin` is often taken |
| Half-created hospital | One save, all-or-nothing. If it fails, nothing is left behind |
| Bad colour code breaking the page | Only `#RRGGBB` is accepted. Anything else falls back to navy |
| Empty site showing a dead page | `/welcome` with no hospital goes to `/start`, not a 503 |
| Too many tries | Six setup attempts per hour per phone |

---

## Where to tap

| Who | Where |
|-----|--------|
| First hospital on a new site | `/start` or **Set up my hospital** on `/sales` |
| Sign-in screen | “Setting up a new hospital?” |
| Another hospital on the same site | Admin → Security → **Make a setup code**. They open `/start` and type it. Code works once, 48 hours. |
| After setup | Dashboard card: add staff, print posters, phone code, patient view |

---

## Checks on this machine

| Suite | Result |
|-------|--------|
| New hospital walk (create, invite, reject weak password, reject taken name) | Pass |
| Phone code, sites, colours | Pass |
| HIMS same-day visit reuse | Pass |
| Security headers | Pass |
| **Total this batch** | **95 passed** |

---

## How to try it after deploy

1. Open `https://hospital-suite.onrender.com/start`  
   Ijede is already there, so you will be asked for a setup code.  
2. Sign in as Super Admin → Admin → Security → **Make a setup code**.  
3. Open `/start` on the phone, type the code, finish the walk.  
4. You should land on “Your hospital is ready” and hear the voice line.  
5. Add one clerk. Print posters.

To set up a brand-new empty site (no hospital yet), `/start` needs no code.

---

## Still to do

1. ~~Security — phone code + headers + self-check~~  
2. ~~Sites + hospital colours~~  
3. ~~Onboarding wizard for a new hospital~~  
4. Attendance geo-fence  
5. Satisfaction dashboard  
6. Revenue report per hospital  
7. Patient photo (optional)  
8. Design tokens + phone home-screen icon  
9. Re-test loading on the live database  
10. Update the final deploy report after the next build  
