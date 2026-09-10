# Look + PWA, and short SMS — 1.7.8

Date: 26 August 2026

Local product is **1.7.8**. GitHub `main` is still **1.7.7** (`42d4c72`) until you paste a new token.

Phone-code lock stays off. Voice reminder stays on. Existing staff still sign in as before.

## 3. Look + PWA — what you can do on the phone

| Step | What to tap |
|------|-------------|
| 1 | Open the hospital site in **Chrome** on Android |
| 2 | A bar appears: **Put this hospital on your phone** → **Add** |
| 3 | If Chrome does not offer Add: menu (three dots) → **Add to Home screen** |
| 4 | The hospital icon sits with WhatsApp. Tap it. No address bar. |

| What it is | What it is not |
|------------|----------------|
| Same hospital, with an icon | A second app in the Play Store |
| Colours and name from **this** hospital | One look for every hospital |
| Last screens stay if the signal drops | Full work with no internet forever |

Set the hospital name and colours under **Admin → Hospital**. That is what the icon is called.

## 7. Live SMS is now one text (160)

| Before | Now |
|--------|-----|
| Booking named the building, price and gold lane — two SMS, emoji (⭐) | One line: date, time, ref, “come 15 min early”, hospital phone |
| Termii sent as **Generic** (promo; blocked at night on MTN) | Termii sent as **DND** (transactional) |
| Thank-you had Yoruba accents (splits to 70-char unicode) | Plain English only |
| Easy to go over 160 | A test **fails the build** if any queued SMS is longer than 160 |

Set the first word on every text under **Admin → Hospital → Name on SMS** (3–11 letters, e.g. `GHIJEDE`). Each hospital keeps its own.

| When | What the patient sees (example) |
|------|----------------------------------|
| They book | `GHIJEDE: Fast Track booked Mon 24 Aug 09:00. Ref …. Pay at Reception gold lane. Call 0803…` |
| They are next | `GHIJEDE: You are next. Ticket E-014, OPD. Please walk to the desk now.` |
| They send a report | `GHIJEDE received your complaint. Ref …. We are looking into it.` |
| Visit finished | `GHIJEDE: Thank you for coming today. Please rate us: …` |
| Staff code | `GHIJEDE: Your sign-in code is 847291. It dies in 10 minutes.` |

No diagnosis. No tablet names. No ₦. No emoji.

Paper for Termii is still `docs/reports/2026-08-24-sms-templates.md`.

## Checked

| Check | Result |
|-------|--------|
| Template links | All point at a real page |
| Booking / queue / complaint / login tests | Passed |
| SMS pack + clip + manifest / icons | Passed |
| Visitor still cannot open Admin | Passed |

Gaps closed before this push: SMS name now actually saves; queue join, booking cancel and Fast Track paid use the same 160 pack; the phone now registers the installer on every page, not only the welcome screen.

Voice reminder stays on.
