# Map pin + honest clock-in — 23 Aug 2026

Build **1.6.0**. Voice reminders stay on. **Voice bank was not built.**

## What you asked for

| You said | What is now on the phone |
|---|---|
| Drag a pin and stretch the circle on a free map | Admin → Sites has an OpenStreetMap map. Drag the pin. Drag the edge of the blue circle. No Google bill. |
| Clock-in that is hard to cheat | Fake-place apps are **refused** when the gate check is Required. Impossible jumps and a phone clock that is ahead are refused. Other odd signs are **marked for review**, not hidden. |
| One grace hour | Counted from **that person’s own roster start**. Default 60 minutes. Admin can change it per hospital (0–240). |
| Lost / spoilt phone, no internet | Offline tap is saved on the phone and sent when the signal returns. HOD / Admin can sign someone in **only with a photo + a reason from a fixed list**. |
| Weekly ratings A–F | `/attendance/week` — each person, each department, whole hospital. |

This is **not** 100% cheat-proof. A determined person with a rooted phone can still lie. The hospital now has a paper trail and a red flag, not a magic lock.

## How to pin the gate (plain steps)

1. Sign in as Super Admin.
2. Open **Admin → Sites**.
3. Stand at the real gate (or tap the map).
4. Drag the pin onto the gate.
5. Drag the **edge of the circle** until it covers the compound (50–2000 m).
6. Tap **Save**.
7. Open **Admin → Settings** → Staff clock-in → set **Must be inside the circle** when you are ready.

Until the pin is saved, staff are never locked out. That is our fault, not the nurse’s.

## Honest clock-in — what happens

| Situation | What the app does |
|---|---|
| Inside the circle | Signed in. Clean. |
| Outside, gate check Required | Refused. “Walk to the gate.” |
| Outside, gate check Optional | Signed in. Marked outside. |
| Phone using a fake place, Required | **Refused.** Ask HOD with a photo. |
| Phone using a fake place, Off | Signed in. **Marked for review.** |
| Jumped many kilometres in a few minutes | Refused. |
| Phone clock is ahead | Refused. Set time to automatic. |
| No internet | Tap is saved on the phone. Sent when back online. |
| After roster start, inside the grace hour | Signed in. Shown as grace, not late. |
| After the grace hour | Signed in. Late minutes kept. Marked for review. |
| Lost / spoilt phone | HOD or Admin takes a **photo of the person at the gate** and picks a reason. No photo = no help. |

Reasons on the list (not free text alone):

- Lost phone
- Spoilt / broken phone
- No internet on the phone
- Official errand
- Phone has no place (GPS)

HOD may only help **their own department**. Admin / HR may help anyone. Every helped punch stores who helped, why, and the photo.

## Weekly grades

| Grade | Score |
|---|---|
| A | 90 and above |
| B | 80–89 |
| C | 70–79 |
| D | 60–69 |
| E | 50–59 |
| F | below 50 |

Marks come off for: missing a rostered day, late after grace, cheat flags, helped clock-ins.

Open **I am here → This week's ratings** (Admin / HR).

## Paid voice clone — what it would cost (2026)

You asked for a likely bill if we later pay a company to clone a native voice that can say **any sentence**.

The honest product on a zero budget is still a **phrase bank**: record the few sentences the TV already says, once, in Yoruba / Hausa / Igbo / Pidgin. That is **₦0**. We did **not** build it this batch.

If you later want any-sentence clone (ElevenLabs-style, 2026 public prices):

| Plan | About (USD / month) | What you get | Rough naira (₦1,600 / $) |
|---|---|---|---|
| Free | $0 | **No clone.** Not for hospital use. | ₦0 |
| Starter | about **$5–6** | Instant clone. ~30 minutes of speech. | about **₦8,000–₦10,000** |
| Creator | about **$22** | Professional clone. ~2 hours. | about **₦35,000** |
| Pro | about **$99** | Volume. ~10 hours. | about **₦160,000** |
| Extra use | about $0.12 per 1,000 characters | After the plan runs out | adds up fast |

A waiting-area TV calling names **all day** will outgrow Creator quickly. You also need **written consent** from the person whose voice is cloned (NDPA). Instant clone is “sounds like them”. Professional clone is closer, and still not a person in the room.

**Recommendation:** stay on the phrase bank until a hospital is paying and has signed consent.

## Checks

| Check | Result |
|---|---|
| Attendance + roles + menu + hardening + MFA/branch | **84 passed** |
| Not an EMR | Still no diagnoses / vitals / results |
| Per hospital, not per server | Mode, circle, pin, grace are tenant settings |
| Voice reminder | Still on |
| Voice bank | Not built |

## What we did **not** do

- Native voice recorder / phrase bank / clone
- Satisfaction dashboard
- Revenue report
- Patient photo
- Design tokens + PWA
- Live database load re-test
- FINAL_DEPLOY_REPORT
