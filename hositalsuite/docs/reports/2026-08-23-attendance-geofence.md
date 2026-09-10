# Attendance geo-fence — finished

**Date:** 23 August 2026  
**Build:** 1.5.0  
**Item closed:** Attendance geo-fence

This hospital is still **not an EMR**. No diagnoses, vitals, prescriptions, results, blood group, genotype, or allergies were added.

Voice reminders stay on. After sign-in the browser still speaks alerts so nobody has to stare at the screen. The clock-in button also speaks “Signing you in.”

---

## What you asked for

Staff must be able to prove they are at the hospital, on a cheap Android phone, without jargon. The rule must belong to **this hospital**, not to the whole product.

| # | Job | Result |
|---|-----|--------|
| Gate pin | Mark the front gate of each site | **Done.** Admin → Sites → “Use this phone to mark the gate” |
| How strict | Off / record only / must be inside | **Done.** Admin → Config. Default is **Off** so nobody is locked out |
| Staff button | One tap on arrival, one tap on leaving | **Done.** Menu → **I am here** |
| Who is here | A list for the people who run the hospital | **Done.** **Who is at work today** |
| Phone has no GPS | A human can still accept the clock-in | **Done.** Reason is kept on the record |

---

## How it works, in one table

| What | Where | What a person does |
|------|--------|--------------------|
| Pin the gate | Admin → **Sites** | Stand at the gate. Tap **Use this phone to mark the gate**. Save. |
| How strict | Admin → **Config** | Off (default) · Record place but still allow · Must be inside the circle |
| Circle size | Same page, or per site | Default **200 metres**. 50–2000 allowed. |
| Sign in | Menu → **I am here** | Tap **I am here**. Allow the phone to share its place. |
| Sign out | Same page | Tap **I am leaving**. |
| Today’s list | **Who is at work today** | Green = inside. Red = outside. “Accepted” = a manager overrode. |
| Accept without GPS | Bottom of that list | Pick the person. Write why. |

The circle is measured from the pin you saved. A person 90 m from the gate is inside a 200 m circle. A person several kilometres away is not.

---

## Safety rules (so the hospital is never locked out)

| Rule | Why |
|------|-----|
| Default is **Off** | A new hospital can still sign people in before anybody pins the gate |
| No pin + “Must be inside” | Still allows the clock-in. Missing pin is our fault, not the nurse’s |
| Fuzzy GPS | If the phone is very unsure, we ask them to step outside and try again |
| Leaving is always allowed | We record whether they were still inside. We never trap them |
| Per hospital, per site | Main and Annex can have different pins. Hospital B cannot see Hospital A |

---

## How to try it after deploy

1. Sign in as Super Admin.  
2. Admin → **Sites**. Open Main. Stand at the gate. Tap **Use this phone to mark the gate**. Save.  
3. Admin → **Config**. Set clock-in to **Must be inside the circle**. Save.  
4. Menu → **I am here**. Tap the button. You should hear “Signing you in.”  
5. Walk far from the hospital and try again (or type a far-away pin in a test). It must refuse.  
6. Open **Who is at work today**. Your name should be there, marked Inside.

---

## Checks run on this machine

| Suite | Result |
|-------|--------|
| Attendance geo-fence | Pass |
| Roles / menu | Pass |
| Sites + phone-code | Pass |
| **Total this batch** | **51 passed** |

---

## Not started (next jobs)

1. Satisfaction dashboard  
2. Revenue report  
3. Patient photo  
4. Design tokens + PWA  
5. Live DB load re-test  
6. Update FINAL_DEPLOY_REPORT  
