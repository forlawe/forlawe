# What I understood — gate map, honest clock-in, native voices

**Date:** 23 August 2026  
**Status:** Understanding only. Nothing new has been built yet.

Voice reminders stay on after you sign in.

This hospital is still **not an EMR**. No diagnoses, vitals, prescriptions, or results belong here.

---

## 1. The gate on a map (not typed numbers)

You do **not** want to type 6.5244, 3.3792.

You want to **see the compound on a map**, drop the pin at the gate, and **stretch a circle** until it covers the whole hospital (wards, annex road, car park) and stops at the street.

| What you do | What the app keeps |
|-------------|--------------------|
| Drag the pin | The centre of the circle (the gate) |
| Drag the edge of the circle | The radius in metres |
| Save | That pin + radius for **this site** of **this hospital** |

Main and Annex each get their own circle. Hospital B never sees Hospital A’s map.

No paid map. The map will be the free street map (the same kind Google shows, without a Google bill).

---

## 2. Staff who try to cheat

Some staff will install a “fake GPS” app and clock in from home.

I will make that **hard**, and I will **mark** anything that looks wrong. I will not pretend a phone browser can be 100% cheat-proof — only a police-grade device lock can be. What we *can* do without money:

| Check | What it catches |
|-------|-----------------|
| Jump too far too fast | Clock-in in Ikeja, then “at the gate” 2 minutes later |
| Place too perfect (0 m error every time) | Typical fake-GPS apps |
| Phone says “this place is mocked” (when Android tells us) | Mock-location apps |
| Clock-in only counts when it later **syncs from that phone** | Typing a location by hand |
| Too many “help me clock in” in one week | Supervisor covering for a friend |

Anything suspicious is still saved, but it is stamped **Flagged** on the weekly report. It is not silently accepted as “inside”.

---

## 3. Real life: late, spoilt phone, no network

The roster says 07:00. Life is not 07:00.

| Situation | What should happen |
|-----------|--------------------|
| **Grace hour** | Arrive by 08:00 after a 07:00 start → **Present, late**. After 08:00 → **Late / absent** until someone accepts it with evidence. |
| **Spoilt or lost phone** | The person cannot use **I am here**. HOD / supervisor clocks them in **with evidence** (see below). |
| **No internet** | The phone still takes the tap and the place, keeps it on the phone, and sends it when the network returns. The time used is the time they tapped, not the time the network came back. |
| **Phone off / left at home** | Same path as lost phone. Not a free “just type my name”. |

Grace is counted from **that person’s roster start that day**, not from a single hospital-wide 7 o’clock, so night duty is fair.

---

## 4. HOD / supervisor may help — but not as a wink

You were clear: if the HOD can type “phone spoilt” with no proof, the HOD and the staff can cover for each other.

So a helped clock-in is **not** a sentence in a box. It is a **file**:

| Must be filled | Why |
|----------------|-----|
| Who is being signed in | Named person, not “a nurse” |
| Which reason (fixed list) | Lost phone / spoilt phone / no network / official errand / other |
| **Evidence** | A photo (smashed screen, police extract, duty note) **or** a second person who is **not** in the same department (HR / Admin Manager) also accepts |
| Limit | More than a set number of helped clock-ins in a week → the weekly report marks that person **and** that HOD |

A helped clock-in never looks the same as “I stood at the gate and tapped”. The weekly rating treats it as weaker than a clean gate tap.

---

## 5. Weekly attendance report with a rating

One week, three layers. Tables, not a speech.

| Layer | What you see |
|-------|----------------|
| **Each person** | Days present, days late (inside grace), days absent against the roster, times outside the circle, helped clock-ins, **rating** |
| **Each department** | Same numbers rolled up. A ward that is always “helped in” stands out. |
| **Whole hospital** | One score for the week. |

A simple rating (example — we can change the bands with you):

| Rating | Meaning |
|--------|---------|
| A | On time, inside the circle, almost no help |
| B | A few lates inside grace |
| C | Repeated late or several helped clock-ins |
| D | Often absent or often outside the circle |
| F | Pattern that needs a conversation |

This is **time and place**, not clinical work. No diagnoses.

---

## 6. Voices that sound like us — not Google

I hear you. Chrome / Google voices sound American or British. Patients and staff in Lagos hear that they are foreign.

**What you asked:** record real people in the app, keep those recordings as the **voice of the hospital**, and use them for later talking (clock-in, queue, TV, reminders).

**What that can honestly mean without paying for a voice-clone company:**

| I can build | I cannot honestly promise |
|-------------|---------------------------|
| An in-app **recorder** (one tap, hear it back, keep or delete) | “Record Auntie once, then the app can say any new sentence in her voice” — that is paid voice-cloning |
| A **library of lines** per hospital: “You are signed in.” “You are signed out.” “Now serving.” “Please come to Room 1.” | Free stitching of any patient name in that exact voice, perfectly |
| Several speakers (e.g. 2 women, 2 men), pick who speaks today | Google/Chrome suddenly sounding Yoruba-native |
| Consent tick + name of the speaker, so a voice is never used without permission | Using someone’s voice after they leave the hospital unless you keep the consent |

So the plan is a **native voice bank**, not a magic copier:

1. You pick a person (staff, presenter, radio voice).  
2. They tick “I agree my voice is used in this hospital’s app.”  
3. They read a short list of lines, one by one, on the phone.  
4. The app plays **their** recording for that line — clock-in, TV call, reminder — instead of the foreign computer voice.  
5. If a line has no recording yet, we fall back to the old voice rather than going silent.

If later you have budget for true voice-cloning (any sentence), that can sit on top of the same bank. It is not this step.

---

## What I will not do in the next build

- Start coding until you confirm the three choices on the next screen.  
- Put a paid Google Map or a paid voice-clone in a zero-budget hospital.  
- Pretend a browser can catch every fake-GPS app.  
- Let an HOD type a reason with no photo and no second person.  
- Store diagnoses, vitals, or prescriptions.

---

## What I need you to pick (so I build the right thing once)

See the three questions next to this note:

1. Voices = record ready-made lines (honest, works now).  
2. Helped clock-in = photo, or photo **plus** a second person outside the department.  
3. Grace = one hour after **that person’s** roster start that day.
