# Microphone on your phone — fixed

**For:** the founder, General Hospital Ijede (The Family Hospital)
**Date:** 20 August 2026
**You reported:** *"the microphone (speech to text) is working perfectly on my
laptop but repeating words when I used my phone… it's not applying or sensitive
to comma, full-stop etc."*

Both faults were real. Both are fixed. Here is exactly what was wrong.

---

## 1. Why the laptop worked and the phone did not

This was the important clue in your message, and it pointed straight at the bug.

When you dictate, the browser hands the app your words in numbered pieces —
piece 0, piece 1, piece 2. The app was filing each piece **by its number**.

| | What the browser does | What happened |
|---|---|---|
| **Laptop** | Keeps listening in one long stretch. Numbers keep counting up: 0, 1, 2, 3… | Everything filed in the right place. **Worked perfectly.** |
| **Phone (Android)** | Gives up after about 5 seconds of silence. The app restarts it — and **the numbering starts again at 0.** | The new phrase was filed at number 0, **on top of a phrase you had already said**. Words were lost, and Android's habit of re-sending its last phrase duplicated others. |

So the same code was correct on a laptop and wrong on a phone. It only broke
when you paused — which is exactly what people do when they are thinking about
a complaint.

### I reproduced your bug exactly

Dictating **"the patient / is waiting / at the pharmacy / please attend"** with
natural pauses:

| | Result |
|---|---|
| Laptop | `The patient is waiting at the pharmacy please attend` ✅ |
| **Phone, before the fix** | **`Please attend is waiting`** ❌ |
| Phone, after the fix | `The patient is waiting at the pharmacy please attend` ✅ |

Words lost *and* repeated, just as you described.

### The fix

Each stretch of speech is now **written down permanently the instant the phone
pauses**, before the microphone restarts. Once a phrase is written down, a new
piece of speech can no longer land on top of it.

I also added a check for Android re-sending its last phrase — but deliberately
a **strict** one. If somebody genuinely says *"no, no, I did not agree"*, both
"no"s are kept. Swallowing real speech would be a worse bug than the one I was
fixing, so there is a test that specifically protects it.

---

## 2. Punctuation — you were right, and here is my honest reasoning

Android's speech engine **never** adds punctuation. It only returns bare words.
(Desktop Chrome sometimes adds it, which is why your laptop again looked fine.)

I had a choice, and I want to be straight with you about it:

**Option A — guess where sentences end.** The app looks for pauses and inserts
full stops. I rejected this. It puts full stops in the wrong places, splits
sentences mid-thought, and on a complaint that a manager will act on, wrong
punctuation can change the meaning. Wrong punctuation is worse than none.

**Option B — let the person say it.** This is how professional dictation has
always worked, and it keeps the person speaking in control of their own words.
**This is what I built.**

### What you can now say

| Say this out loud | You get |
|---|---|
| "comma" | , |
| "full stop" *(or "period")* | . |
| "question mark" | ? |
| "exclamation mark" | ! |
| "colon" / "semicolon" | : / ; |
| "open bracket" / "close bracket" | ( ) |
| "dash" | - |
| "new line" | starts a new line |
| "new paragraph" | leaves a blank line |

**Try saying:** *"I waited three hours comma nobody told me why full stop"*

**You get:** `I waited three hours, nobody told me why.`

Notice it also **capitalised the "I"** and the start of the sentence. Android
returns everything in lower case, and "i waited three hours" looks careless on
a complaint a manager is going to read. The app now fixes the capital letter at
the start of every sentence, and the standalone word "I", automatically.

### Nobody would ever guess this

So the app now **tells them**. The moment the microphone starts, a small blue
tip appears under the button:

> *Tip: say "comma", "full stop", "question mark" or "new line" and they will
> be typed for you.*

It disappears when the microphone stops. It is not a pop-up, because a dialog
in the middle of dictation would interrupt the very thing it is explaining.

**One detail worth mentioning:** "full stop" has to be matched *before* "stop",
or the sentence *"tell them to stop"* would become *"tell them to."* — which
would have been an embarrassing new bug. There is a test that specifically
proves this ordering is right.

---

## 3. Why this was never caught before

Honestly: **because it could not be.** Every test in this system is a Python
test, and Python tests never run the browser code. The fault lived entirely in
how Chrome on Android restarts its microphone. No test I had could have seen it.

So as part of this fix I built something new: a test harness that loads **the
real file that runs on your phone** and drives it with a **fake Android** that
misbehaves exactly the way yours does — ending on silence, resetting the
numbering, replaying its last phrase.

**That gap is now closed permanently.** These browser tests run every time the
normal test suite runs, so nobody can break dictation again without the build
failing.

---

## 4. How I proved it

| Check | Result |
|---|---|
| Browser dictation tests (fake Android) | **12 passed, 0 failed** |
| Real Chromium on the real complaint page, at phone width | **10 passed, 0 failed** |
| Full test suite on SQLite | **640 passing** (was 632 — 8 new) |
| Full test suite on real PostgreSQL 17 | **640 passing** (36 minutes, 0 failures) |
| Page still fits a 390px phone | ✅ 0 pixels too wide |
| No JavaScript errors | ✅ |

### I broke my own code on purpose to check the tests are real

A test that passes no matter what you break is worse than no test, because it
makes you confident for no reason. So I deliberately broke four things:

| What I broke | Caught? |
|---|---|
| Removed the "write it down before restarting" fix | ✅ — and it reproduced **`"Please attend is waiting"`**, your exact bug |
| Removed the Android-replay check | ✅ caught (phrase appeared twice) |
| Removed punctuation conversion entirely | ✅ caught (11 tests failed) |
| Matched "stop" before "full stop" | ✅ caught (*"Tell them to. Full."*) |

The first one is the one that matters: breaking the fix brings your bug
straight back, which proves the test is watching the right thing.

---

## 5. What to do on your phone

1. Open any page with a 🎤 button — the complaint page is the easiest to try.
2. Tap the microphone. **Allow microphone access** if Android asks.
3. Speak normally. **Pause as much as you like** — that is the thing that used
   to break it.
4. Say **"comma"** and **"full stop"** where you want them.
5. Tap the button again to stop.

Please test it and tell me how it goes. If any word still comes out doubled, I
want the exact sentence you said — that detail is what let me find this one.

---

## 6. Nothing else was touched

This change only affects speech-to-text. The spoken **announcements** (the
voice that calls patients and alerts staff) are a completely separate part of
the code and were not modified. All 640 tests confirm it.

---

## 7. Still outstanding on your side

| Action | Why it matters |
|---|---|
| **Revoke the GitHub token `ghp_7FM7…`** | Still not confirmed. It is visible in this chat; anyone who sees it can change your hospital's software. **Please do this today.** |
| **Add `GROQ_API_KEY` in Render** (never `GROQ_MODEL`) | The AI assistant is built and tested but is not live without it. |
| Second UptimeRobot monitor on `/api/v1/ready` | Catches a database fault, not just a dead page. |
| Turn on Supabase backups | Your only protection against losing everything. |

---

## 8. Where we are

| # | Next | My view |
|---|---|---|
| **1** | **Run a real pilot and film it** ⭐ | Still, by a long way, the most valuable thing you can do. This bug is a good example of why: it survived every test I had and was found by **you, on a real phone, in thirty seconds**. Real use finds what testing cannot. |
| 2 | Leave approval workflow | Leave is recorded; no approval chain exists |
| 3 | Patient satisfaction linked to journey time | You already hold both halves of the data |
| 4 | Predicting tomorrow's load from history | Worth doing after a pilot supplies real history |
| 5 | Cross-department roster clash warnings | Small |
| 6 | HIMS fuzzy-spelling search | Small, but staff would feel it daily |

---

### Note on the PostgreSQL run

The full PostgreSQL 17 run finished: **640 tests, 0 failures, 36 minutes.**
Both engines are green. Nothing was pushed until they were.

This change is JavaScript and CSS only — no database columns, no migration —
so there is nothing for you to do on Render beyond letting the deploy finish.
