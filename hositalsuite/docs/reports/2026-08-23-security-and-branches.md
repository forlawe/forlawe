# Security + hospital sites — finished

**Date:** 23 August 2026  
**Build:** 1.3.0  
**Items closed:** 1 (Security) and 2 (Sites + colours)

This hospital is still **not an EMR**. No diagnoses, vitals, prescriptions, results, blood group, genotype, or allergies were added.

Voice reminders stay on. After sign-in the browser still speaks alerts so nobody has to stare at the screen.

---

## What you asked for

| # | Job | Result |
|---|-----|--------|
| Live bug | Clerk could not start a second same-day visit — red error, patient stuck | **Fixed.** Today's visit is reused. Clerk is told the visit is already open and can send the person to Triage. |
| 1 | Phone-code sign-in, security headers, self-check | **Done.** |
| 2 | Main building + annex, staff assigned to a site, hospital colours | **Done.** |

---

## 1. Security — in plain English

| What | Where | What a person does |
|------|--------|--------------------|
| Phone code (optional) | Admin → **Security** | Tick which jobs must use a phone code. Those people scan a picture on next sign-in. |
| Own phone code | Menu 🔐 | Anyone can turn it on for themselves even if their job is not forced. |
| Backup codes | After setup | Eight one-use codes. Keep them on paper. |
| Self-check | Admin → **Security** | Green / amber / red list: headers, secret key, phone-code coverage. |
| Door locks (headers) | Every page | Browser is told: do not let another site put this hospital in a frame, do not guess file types, send a short address bar only. |

**Default:** nobody is forced to use a phone code until you tick jobs on the Security page. Existing sign-in still works.

---

## 2. Sites (branches) + colours

| What | Where | What a person does |
|------|--------|--------------------|
| Main site | Created automatically | Every hospital gets a site called **Main**. Yesterday's work still works if nobody is assigned. |
| Extra site | Admin → **Sites** | Add Annex (or any name). Code like `ANNEX`. |
| Assign staff | Admin → **Users** | Pick the site on create or edit. |
| Site on new work | Reception + HIMS | New intake, folder, and visit take the clerk's site. |
| Site queues | Reception + HIMS lists | Annex staff see annex work. Super Admin / MD / Admin Manager see every site. |
| Colours | Admin → **Hospital** | Three colour boxes. Saved **per hospital**, not for the whole product. Login and staff pages pick them up. |
| Site name in the top bar | Every signed-in page | If the person belongs to a site, the bar shows `Hospital · Annex`. |

---

## Same-day visit (the circled live error)

| Before | After |
|--------|--------|
| Second tap on “Start a visit” flashed a red error. Clerk stuck. Patient never reached Triage. | Same tap **keeps today's visit**. Banner: visit already open. Button becomes **Continue to Triage**. Still only one visit for that person that day. |

---

## Checks run on this machine

| Suite | Result |
|-------|--------|
| Phone code, sites, colours, header self-check | Pass |
| HIMS (including same-day visit reuse) | Pass |
| Hardening headers | Pass |
| Reception walk | Pass |
| **Total** | **111 passed** |

---

## How to try it after deploy

1. Sign in as Super Admin.  
2. Admin → **Security** — tick Super Admin if you want a phone code. Sign out, sign in, scan the picture.  
3. Admin → **Sites** — add Annex.  
4. Admin → **Users** — put one clerk on Annex.  
5. Admin → **Hospital** — change the navy colour. Open the home page: the bar should match.  
6. Open a folder and tap **Start a visit** twice. Second tap must **not** go red.

---

## Not started (next jobs)

Do not start these until you say so. One item at a time.

1. ~~Security~~  
2. ~~Sites + colours~~  
3. Onboarding wizard for a new hospital  
4. Attendance geo-fence  
5. Satisfaction dashboard  
6. Revenue report per hospital  
7. Patient photo (optional)  
8. Design tokens + phone home-screen icon (PWA)  
9. Re-test loading on the live database  
10. Update the final deploy report after the next build  
