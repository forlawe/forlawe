# Clock and patient places — 24 Aug 2026

Version **1.7.1**. Two phone complaints, both fixed.

Voice reminder stays on. A forgotten wait is now spoken as **“1 hour 30 minutes”**, not “90 minutes”.

---

## 1. Time is a clock, not a pile of minutes

You saw **256m**. That is hard to read.

| Minutes in the system | What the screen now shows | What the voice says |
|---|---|---|
| 45 | 0:45m | 45 minutes |
| 154 | 2:34m | 2 hours 34 minutes |
| 256 | 4:16m | 4 hours 16 minutes |
| 1,465 | 24:25m | 24 hours 25 minutes |

Same clock on:

- the home dashboard
- Patient flow
- queue ticket
- TV
- consulting room, triage, Fast Track desk, cash desk, LAHSMA, department desk

---

## 2. Patients no longer see Laundry, Audit, Store

The “— Select department —” list was the **whole hospital organogram**. A patient cannot join Internal Audit.

| Who | What they see |
|---|---|
| Patient (queue, book, feedback, complaint) | Only places a patient visits. **Fast Track is first.** |
| Staff (desks, admin, satisfaction filter) | Full hospital list, unchanged |

Hidden from patients: Laundry, Internal Audit, Store, Finance, ICT, Planning, Security, Catering, Mortuary, HIMS, Admin / HR, Engineering, Nursing Services.

Shown: Fast Track, Emergency, GOPD, clinics, Lab, Pharmacy, Radiology, and the other clinical places.

**Fast Track is now a real department** (not only a tick-box). Pick it on the list and you are on the gold lane.

---

## 3. How to check on your phone

1. Open **Get a number**.
2. The first place should be **⭐ Fast Track**.
3. Laundry / Audit / Store must not appear.
4. Open any wait screen. A long wait must look like **4:16m**, never **256m**.

---

## 4. Tests

New: clock format + patient places. Tracking, queue, satisfaction, smoke, navigation, roles, hardening still pass.

---

## Still to do (next)

Same list as before. This batch was the two live-site complaints only.
