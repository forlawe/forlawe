# Explain VAPID and USSD like you are 10 years old — Hospital Suite

## Founder questions from screenshots 2026-08-30
You asked about two things you saw in Admin:
1. Push Notifications → VAPID per-hospital fields
2. USSD CODE setup confusion

---

## 1. VAPID — Free alarm when app is closed (saves SMS money)

### The problem today
- SMS costs ₦3-4 per message in Nigeria
- If you send 1000 SMS per day = ₦3000-4000 per day = ₦90k-120k per month
- Founder rule: **No SMS for patients inside hospital except serious/emergency**

### What VAPID does — like an alarm clock
Imagine your phone alarm:
- You set alarm at night, close the app, phone sleeps
- In morning, alarm still rings — even though app was closed
- That's what VAPID does for hospital staff

**VAPID = Voluntary Application Server Identification**

Think of it as a secret handshake between:
- Your hospital server (the boss)
- Google/Apple push service (the postman)
- Staff phone (the worker)

When a patient needs attention, instead of SMS (₦4), we send a **free push** that works even when app closed — like alarm.

### How it works in our app (already built, zero extra cost)

**Per-hospital keys** — each hospital has its own keys (multi-hospital design):
- `VAPID_PUBLIC_KEY` — like your house address (public, share with postman)
- `VAPID_PRIVATE_KEY` — like your house key (secret, only server knows)
- `VAPID_SUBJECT` — mailto: contact (e.g. mailto:admin@generalhospitalijede.ng)

**Where to get keys?**
You have 2 free options, pick one:

Option A (Python, on your laptop/server):
```bash
pip install py-vapid
python -m py_vapid --gen
```
It prints:
```
Public: BEl62iUY... (long string)
Private: uDN3rR... (long string)
```

Option B (Node, if you have node):
```bash
npx web-push generate-vapid-keys
```

**Where to put them?**

1. Global (for all hospitals) — in Render environment variables:
```
VAPID_PUBLIC_KEY=BEl62i...
VAPID_PRIVATE_KEY=uDN3rR...
VAPID_SUBJECT=mailto:info@hospital.ng
```

2. Per-hospital (better, each hospital own keys) — in Admin → Push Notifications page you saw in screenshot 09:02:
- Leave empty to use global
- Or paste hospital-specific keys
- We already show this page with 3 fields: Public, Private (Secret), Subject

**What happens after?**
- Staff opens app → sees banner "Enable alarm mode?" (screenshot 07:57)
- Taps Enable → browser asks "Allow notifications?" → Allow
- Now even if app closed, when queue has 3 patients waiting at Lab, phone buzzes FREE
- No SMS cost. Saves ₦90k/month

**Slow internet in Africa?**
- Push uses tiny data (<1KB), works on 2G
- If push fails, we fallback to in-app toast + voice announcement on TV

**All browsers?**
- Chrome Android: yes
- Samsung Internet: yes
- Firefox: yes
- Safari iPhone: yes (iOS 16.4+), needs Add to Home Screen first
- UC Browser: no (we show voice + TV fallback)

---

## 2. USSD CODE — For patients with future phone / not Android / iOS

### The problem you noted
"What provision is on ground for patient with future phone or not Android/iOS phones. (Just note if no provision)"

You are right — not everyone has smartphone.

In Nigeria, many patients have:
- Small Nokia torch (feature phone)
- No data, no WhatsApp
- Can't install app

### What USSD is — like bank *737#

You know GTB *737# or MTN *556# ?
- You dial *code# on any phone, even torch
- Menu appears: 1. Check balance, 2. Buy data
- Works without internet, without smartphone

**For hospital, USSD could be:**
```
*347*123#
Welcome to General Hospital Ijede
1. Check my queue number
2. Where to go next
3. Talk to help desk
```

Patient dials, sees: "You are number 5, 2 people ahead, go to Billing"

### What we have TODAY (provision on ground)

We do NOT have live USSD yet (needs telco partnership, costs money). But we built fallback that works for feature phones TODAY, zero cost:

**1. TV Screens (main provision)**
- Main waiting hall TV shows: Now Serving — your ticket number
- No phone needed at all
- Patient watches TV, hears voice: "Mr Tunde, please go to Room 3"
- Works for everyone, even if phone battery dead
- Screenshot 07:57 shows patient flow TV

**2. Voice Announcements (native voices)**
- Speakers in waiting area announce in English, Yoruba, Hausa, Igbo
- 2 male 2 female voices recycled daily (Ada, Emeka, Folake, Chinedu)
- Patient hears own name (first name only for privacy)
- Works for illiterate patients who can't read TV

**3. Personal TV Link (for those with any phone, even small browser)**
- When patient joins queue, they get a link: /queue/ticket?key=abc123
- This page works on ANY phone browser, even Opera Mini on feature phone
- Shows: Your number, people ahead, estimated wait, what to do next
- Auto-refreshes every 20 sec
- No app install needed
- Private: shows only your journey, not others

**4. Help Desk Phone Numbers**
- Every patient page shows: "Need help? Ask at help desk near reception"
- Shows hospital phone: e.g. 08012345678
- Feature phone user can call help desk

**5. SMS only for emergency (founder rule)**
- We DON'T send SMS for normal queue (saves cost)
- Only if serious complaint or emergency, we send SMS
- This is by design to save ₦3-4 per SMS

### Future USSD (if you want it later)

If hospital wants real *code#, steps:

1. Partner with telco aggregator (e.g. Africa's Talking, Termii, MyStreet, UBA USSD provider)
2. They give you code like *347*XXX#
3. They charge setup ~₦50k-100k + per session ₦2-5
4. We build webhook: when patient dials, aggregator calls our server /api/ussd
5. Our server replies with queue status

**We have already prepared the backend for this:**
- `app/views/personal_tv.py` can serve USSD responses
- Queue logic already has `ahead`, `est`, `now_serving`
- Just need to connect to aggregator

**For now, note in admin:**
- Go to Admin → Hospital Setup → add help desk numbers
- Enable TV screens (we have 5 default: MAIN, DENTAL, OPD, PHARMACY, FASTTRACK)
- Turn on voice announcements in /admin/native-voice (enable native voice)
- Staff should tell feature phone patients: "Watch TV, listen for your name"

---

## Summary for founder — 10 year old version

**VAPID = Free alarm**
- Like alarm clock that rings even when app closed
- Saves SMS money (₦90k/month)
- Each hospital has its own keys (public + private)
- Generate keys free with `python -m py_vapid --gen`
- Paste in Admin → Push Notifications
- Staff tap "Enable alarm mode" → gets free buzz

**USSD = *code# for torch phones**
- Today we DON'T have *code# live (needs telco money)
- But we HAVE: TV + Voice + Personal link + Help desk phone
- So feature phone patient still okay: watches TV, hears voice
- Future: if you want *347#, partner with Africa's Talking, we connect webhook

**Logo upload — FIXED**
- You said no provision — actually we HAD it but it was hidden below scroll
- Now moved to TOP of Hospital Setup page, big green box, shows current logo, preview 192/512
- Works on all browsers: Chrome, Samsung Internet, Firefox, Safari
- Compressed to <100KB for slow internet
- Shows on phone home screen when staff Add to Home Screen

**Other fixes in this release (v1.8.1):**
- Voice recording now saves webm from Android Chrome (was blocking mp3 only)
- Missing Phrases Report table now scrolls sideways on phone (was clipped)
- Pages fit screen: grid cols now 1 column on phone, not 3 squeezed
- 500 errors hardened: dashboard, tracking, inject_globals never crash, show empty state instead
- Private info: TV now shows first name only, not full name + hospital number
