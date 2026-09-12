# Satisfaction dashboard — 24 Aug 2026

Build **1.7.0**. Voice reminders stay on. This is **not** a medical record.

## What you asked for

How patients rated the visit, on one screen a matron can read on a cheap phone.

## Where to open it

| Who | Tap |
|---|---|
| Anyone who already sees Complaints | Menu → **Satisfaction** |
| From the home numbers | Tap the **Satisfaction /5** tile |
| From Reports | **How patients rated the visit** |

## What the board shows

| Box | Meaning |
|---|---|
| Average /5 | All stars in the period, added up and shared |
| Ratings this period | How many people tapped a score |
| Happy % | Share who gave 4 or 5 stars |
| Low scores | How many gave 1 or 2 stars |
| Word | Excellent / Good / Fair / Poor / Critical |
| Up or down | Compared with the same number of days before |
| Stars given | Table of 5★ down to 1★ |
| Each department | Average, word, how many, how many low |
| Last 14 days | Day by day |
| Latest comments | Same list as before. A 1–2 star still opens a **recovery ticket** |

Pick **7 / 30 / 90 days**. Pick one department. **Download table** gives a spreadsheet (no phone numbers).

The phone **speaks** the headline when the page opens.

## Who sees what

| Person | What they see |
|---|---|
| MD / Admin / HR | The whole hospital |
| HOD | **Only their own department** |
| Another hospital | Nothing from yours |

A 1 or 2 star still becomes a recovery ticket while the patient can still be helped. That did not change.

## What we did **not** put on this board

- Diagnoses, medicines, results, blood group
- Patient photos
- Money (that is the next revenue report)

## Checks

| Check | Result |
|---|---|
| Feedback + smoke + menu | **30 passed** |
| Roles + security headers | **passed** |
| Not an EMR | No clinical columns |
| Per hospital | Yes |
| Voice reminder | Still on |

## How to try it on the phone

1. Open the public page **Feedback** (or a wall poster).
2. Leave a 5 star and a 1 star, with a department.
3. Sign in as MD.
4. Tap **Satisfaction**.
5. You should see the average, both comments, and a recovery ticket on the low score.
6. Sign in as the HOD of that department — they see their own ratings only.
