# Sample SMS for Termii and Twilio

**Date:** 24 August 2026  
**Hospital name on the text:** `GHIJEDE` (11 letters — Termii limit)  
**Rule:** every line is **one SMS**. Longest sample here is **113** characters. Limit is **160**.

Voice reminders in the app stay on. These texts are only for the phone.

---

## How to use this paper

### Termii (main door)

1. Sign in at **https://accounts.termii.com**
2. Ask support to **open the DND route** (needed for booking, codes, and complaints).
3. When they ask for **sample templates**, copy the **Sample text** column below. Do not change the words except the blanks.
4. Sender ID: **`GHIJEDE`**

Use the **DND** route for every line marked DND.  
Use **Generic** only for the rare “clinic closed” notice.

### Twilio (spare key)

1. Twilio → **Messaging** → **Content Template Builder** (or just keep the words in a notebook).
2. Paste the same **Sample text**.
3. Type: **Transactional** (not Marketing), except P21.

### Hard rules (or the text splits / fails)

| Do | Do not |
|---|---|
| Plain English letters and numbers | Emoji (star, tick, flag) |
| Full stop , colon : hyphen - | Naira sign ₦, Yoruba accents (ẹ ọ) |
| One visit, one fact | Diagnosis, tablet names, test results |
| Hospital phone at the end | Long website stories |

If you add a smiley or ₦, one SMS becomes **70** characters and you pay twice.

---

## Blanks you will swap

| Blank | Example | Meaning |
|---|---|---|
| `{DATE}` | Mon 24 Aug | Day of the visit |
| `{TIME}` | 09:00 | Clock time |
| `{DEPT}` | OPD | Clinic or desk |
| `{REF}` | BK24082401 | Booking or complaint number |
| `{TICKET}` | E-014 | Queue number |
| `{CODE}` | 847291 | Staff sign-in code |
| `{PHONE}` | 08031234567 | Hospital desk phone |
| `{NAME}` | Ada Admin | Staff name only |
| `{HRS}` | 24 | Hours left to reply |
| `{SHIFT}` | Day | Roster shift |

---

# A. Patient texts (register these first)

Copy the **Sample text** as-is into Termii.

| # | Name for Termii | When to send | Route | Chars | Sample text |
|---|---|---|---|---|---|
| P1 | `visit_booked` | They just booked | DND | 99 | GHIJEDE: Visit booked Mon 24 Aug at 09:00, OPD. Ref BK24082401. Come 15 min early. Call 08031234567 |
| P2 | `visit_remind_1d` | Day before | DND | 106 | GHIJEDE: Reminder. Your visit is tomorrow 24 Aug at 09:00, OPD. Ref BK24082401. Call 08031234567 to change |
| P3 | `visit_remind_today` | Morning of visit | DND | 91 | GHIJEDE: Your visit is TODAY at 09:00, OPD. Ref BK24082401. Come 15 min early to Reception. |
| P4 | `fasttrack_booked` | Fast Track booked | DND | 113 | GHIJEDE: Fast Track booked Mon 24 Aug 09:00. Ref FT24082401. Pay at Reception for the gold lane. Call 08031234567 |
| P5 | `fasttrack_paid` | Payment marked paid | DND | 91 | GHIJEDE: Fast Track PAID. Ref FT24082401. Go to Reception gold lane on Mon 24 Aug at 09:00. |
| P6 | `visit_cancelled` | Booking cancelled | DND | 98 | GHIJEDE: Your visit Ref BK24082401 on 24 Aug at 09:00 is cancelled. Book again or call 08031234567 |
| P7 | `queue_number` | They take a number | DND | 91 | GHIJEDE: Your number is E-014 at OPD. Keep this SMS. We will text you when it is your turn. |
| P8 | `queue_next` | They are next | DND | 70 | GHIJEDE: You are next. Ticket E-014, OPD. Please walk to the desk now. |
| P9 | `report_received` | Complaint received | DND | 104 | GHIJEDE received your report. Ref CP24082401. We are looking into it. Keep this number. Call 08031234567 |
| P10 | `report_seen` | HOD has seen it | DND | 83 | GHIJEDE: We have seen your report CP24082401. Our team is working on it. Thank you. |
| P11 | `report_done` | Complaint closed | DND | 98 | GHIJEDE: Your report CP24082401 is resolved. Thank you for telling us. Call 08031234567 if needed. |
| P12 | `report_urgent` | Sent to MD | DND | 85 | GHIJEDE: Your report CP24082401 has gone to hospital management for urgent attention. |
| P13 | `thank_you` | Visit finished | DND | 89 | GHIJEDE: Thank you for coming today. Please rate us: hospital-suite.onrender.com/feedback |
| P14 | `go_lahsma` | Sent to LAHSMA | DND | 94 | GHIJEDE: Please go to the LAHSMA desk now with your card and this visit slip. Call 08031234567 |
| P15 | `go_pay` | Sent to pay | DND | 95 | GHIJEDE: Please go to Billing, then the Paying Point. Keep your slip. Call 08031234567 if lost. |
| P16 | `go_lab` | Sent to Laboratory | DND | 86 | GHIJEDE: Please go to the Laboratory now. Take your card. We will call you when ready. |
| P17 | `go_pharmacy` | Sent to Pharmacy | DND | 96 | GHIJEDE: Please go to the Pharmacy now. Take your card. Collect your items and keep the receipt. |
| P18 | `return_visit` | Come back another day | DND | 103 | GHIJEDE: Please return on Mon 24 Aug at 09:00, OPD. Ref BK24082401. Come 15 min early. Call 08031234567 |
| P19 | `missed_visit` | They did not come | DND | 91 | GHIJEDE: We missed you at 09:00 today. Call 08031234567 to book another day. Ref BK24082401 |
| P20 | `running_late` | Desk is behind | DND | 85 | GHIJEDE: We are about 20 min behind. Please wait. Your visit still stands. Thank you. |
| P21 | `clinic_closed` | Rare closure | Generic | 90 | GHIJEDE: The clinic is closed today. Your visit is moved. Call 08031234567 for a new time. |

P16 and P17 say **where** to walk. They never say what test or what medicine. That is on purpose.

---

# B. Staff texts

| # | Name for Termii | Who | When | Route | Chars | Sample text |
|---|---|---|---|---|---|---|
| S1 | `duty_tomorrow` | Admin Manager | Night before | DND | 102 | GHIJEDE: You are on duty TOMORROW Mon 24 Aug. Please prepare the daily walk-round. Sign in: I am here. |
| S2 | `duty_today` | Admin Manager | That morning | DND | 96 | GHIJEDE: You are on duty TODAY Mon 24 Aug. Please finish today's walk-round before the deadline. |
| S3 | `walkround_late` | AM + MD | Inspection late | DND | 85 | GHIJEDE: Today's walk-round is late. Duty officer: Ada Admin. Please complete it now. |
| S4 | `report_new_hod` | HOD | New complaint | DND | 102 | GHIJEDE: New patient report CP24082401, Emergency. Reply within 24 hrs. Open Complaints on your phone. |
| S5 | `report_hurry` | HOD | Time almost up | DND | 93 | GHIJEDE: Report CP24082401 must be closed in 4 hrs or it goes to the MD. Open Complaints now. |
| S6 | `report_to_md` | MD / DMD | Escalated | DND | 92 | GHIJEDE: Report CP24082401 (Emergency) missed its time and is now with you. Open Complaints. |
| S7 | `signin_code` | Any staff | Forgot password | DND | 93 | GHIJEDE: Your sign-in code is 847291. It dies in 10 minutes. If you did not ask, ignore this. |
| S8 | `fix_assigned` | Named owner | Corrective action | DND | 94 | GHIJEDE: A fix is assigned to you. Deadline Mon 24 Aug. Open Corrective Actions on your phone. |
| S9 | `walkround_alert` | MD + AM | Critical finding | DND | 82 | GHIJEDE ALERT: Walk-round IN24082401 at Emergency has a critical finding. Act now. |
| S10 | `new_booking_desk` | Front desk | Optional | DND | 79 | GHIJEDE: New visit booked. Ref BK24082401, OPD, Mon 24 Aug 09:00. See Bookings. |
| S11 | `roster_tomorrow` | Rostered staff | Night before | DND | 95 | GHIJEDE: You are rostered tomorrow Mon 24 Aug, Day shift. Sign in on I am here when you arrive. |

S7 is the only one with a secret code. Never put that code on WhatsApp or in a photo.

---

# C. What to type in Termii’s “template” box (with blanks)

If they ask for a pattern, use these. Keep the same length when you fill the blanks.

```
GHIJEDE: Visit booked {DATE} at {TIME}, {DEPT}. Ref {REF}. Come 15 min early. Call {PHONE}
GHIJEDE: Reminder. Your visit is tomorrow {DATE} at {TIME}, {DEPT}. Ref {REF}. Call {PHONE} to change
GHIJEDE: Your visit is TODAY at {TIME}, {DEPT}. Ref {REF}. Come 15 min early to Reception.
GHIJEDE: Fast Track booked {DATE} {TIME}. Ref {REF}. Pay at Reception for the gold lane. Call {PHONE}
GHIJEDE: Fast Track PAID. Ref {REF}. Go to Reception gold lane on {DATE} at {TIME}.
GHIJEDE: Your visit Ref {REF} on {DATE} at {TIME} is cancelled. Book again or call {PHONE}
GHIJEDE: Your number is {TICKET} at {DEPT}. Keep this SMS. We will text you when it is your turn.
GHIJEDE: You are next. Ticket {TICKET}, {DEPT}. Please walk to the desk now.
GHIJEDE received your report. Ref {REF}. We are looking into it. Keep this number. Call {PHONE}
GHIJEDE: We have seen your report {REF}. Our team is working on it. Thank you.
GHIJEDE: Your report {REF} is resolved. Thank you for telling us. Call {PHONE} if needed.
GHIJEDE: Your report {REF} has gone to hospital management for urgent attention.
GHIJEDE: Thank you for coming today. Please rate us: hospital-suite.onrender.com/feedback
GHIJEDE: Please go to the LAHSMA desk now with your card and this visit slip. Call {PHONE}
GHIJEDE: Please go to Billing, then the Paying Point. Keep your slip. Call {PHONE} if lost.
GHIJEDE: Please go to the Laboratory now. Take your card. We will call you when ready.
GHIJEDE: Please go to the Pharmacy now. Take your card. Collect your items and keep the receipt.
GHIJEDE: Your sign-in code is {CODE}. It dies in 10 minutes. If you did not ask, ignore this.
```

---

# D. What Termii will ask you

Write this in the “why” box:

> These are transactional hospital notices: visit time, queue turn, complaint reference, and staff sign-in codes for General Hospital Ijede. Not adverts. Not marketing.

Tick list:

- [ ] Sender ID `GHIJEDE` requested
- [ ] DND route asked for
- [ ] Patient pack P1–P13 sent as samples
- [ ] Staff pack S1–S7 sent as samples
- [ ] Desk phone `{PHONE}` is the real hospital number
- [ ] No ₦, no emoji, no Yoruba accents on SMS

---

# E. Live app (from 1.7.8)

The live booking, queue, complaint, thank-you and sign-in texts now use this same short pack. A test fails the build if any queued SMS is longer than 160 characters. Termii is sent on the **DND** (transactional) route, not Generic. The name at the start of each text is set per hospital under **Admin → Hospital → Name on SMS**.

---

# F. Print this starter set (8 is enough to open the door)

If they only accept a few at first, send these eight:

1. P1 visit booked  
2. P2 day-before reminder  
3. P8 you are next  
4. P9 complaint received  
5. P13 thank you  
6. S1 duty tomorrow  
7. S4 new report for HOD  
8. S7 sign-in code  
