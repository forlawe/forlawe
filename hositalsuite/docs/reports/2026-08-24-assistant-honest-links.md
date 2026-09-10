# Hospital Assistant — honest answers and live links — 24 Aug 2026

Version **1.7.2**. Voice reminder stays on.

---

## What you asked

| # | You said | What we did |
|---|---|---|
| 1 | Send dynamic links (Booking, Fast Track). Address can change with hosting / domain. | Links are built from **this site, right now**. Change the host or domain and the link changes with it. Never a hard-coded old address. |
| 2 | Do not suggest anything that is not in the answer book. | If the book has no answer, the assistant **stops**. It does not invent. |
| 3 | Follow the conversation. Know when to stop. | “Yes” after a booking offer opens booking. A new question that is not in the book is refused. It will not guess a taxi, a price, or a map. |
| 4 | Audit the preloaded book. Remove offers it cannot keep. | Promises like “I’ll text you the map”, “I’ll check your HMO”, “I’ll grab a slot” are stripped. Only real pages stay. |
| 5 | Same links on WhatsApp. | A WhatsApp message gets the **same answer and the same live link**. |

---

## How the links work

| Patient says | Link they get (on this site) |
|---|---|
| Book / appointment / hours then “yes” | Book a visit `/book` |
| Fast Track | Book Fast Track `/book` + Get a number `/queue/join` |
| Complaint | Make a complaint `/complaint` |
| Where is the hospital | Hospital home `/welcome` |

If you move the hospital to a new web address tomorrow, those links follow it.

---

## What it will no longer say

- I will text you a map
- I will check your HMO
- I will grab you a morning slot
- I will alert A&E that you are coming
- I will guess a price

If it cannot do it, it says so, or it stays quiet.

---

## How to check on your phone

1. Open **Hospital Assistant**.
2. Type **I want Fast Track**. You should see a tap link for this hospital, not an old website name.
3. Type **send me a taxi**. It should say it does **not** have that in the answer book.
4. Send the same Fast Track line on WhatsApp. You should get the same link.

---

## Tests

New honesty + WhatsApp link tests. Chat, accuracy, answer-book precision, and department coverage still pass.
