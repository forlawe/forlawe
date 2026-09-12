# TV Display + Nigeria Native Voices — Understanding Your Demand

**Your words:** "connect with queue and doctors call for patients can be display on Monitor (TV) with app voice enable. NIGERIA NATIVE VOICES TO BE USED. IF POSSIBLE TWO MALE AND TWO FEMALE THAT CAN BE AUTOMATICALLY CHANGE OR RECYCLED VERY DAY. MULTIPLE TV BUT THE IN WAITING AREA SHOULD SHOW MORE. SHOW FULL NAME AND QUEUE STATISTIC TOO. SHOW MORE THAN DOCTOR CALLS. SPEAK ENGLISH AND YORUBA. DESIGN THE TV SHOWS TO BE FRIENDLY AND ATTRACTIVE"

### I understand you want 5 things — here is how I will do it

#### 1. Multiple TVs, but waiting area main TV shows MORE

| TV | Where | What it shows | Why |
|---|---|---|---|
| **Waiting Area Main TV** `/tv/MAIN` | General waiting hall | **EVERYTHING**: Queue waiting (code + full name), Reception/Billing/PayPoint/HIMS/Triage/Doctor Now Serving/Next/Lab/Pharmacy/Wards/LAHSMA, 8 live stats, per-clinic counts today, doctors ready | This is the big TV everyone sees. Must show more so patient knows where they are in whole journey, not just doctor call |
| **Clinic TV** `/tv/DENTAL`, `/tv/OPD`, `/tv/ANC`, `/tv/OG`, `/tv/EYE` | Each clinic waiting area | **Filtered to that clinic only**: Now serving in Dental, Next in Dental, stats for Dental | So Dental patients don't see OPD noise. Admin chooses clinic filter |
| **Department/Ward TV** `/tv/PHARMACY`, `/tv/MALE_WARD` | Pharmacy, Lab, Wards | **Filtered to that desk**: Only patients sent to Pharmacy waiting | So Pharmacy staff sees their own queue |

**How it works with zero budget:**
- Any Android phone + HDMI cable to TV, or Android TV browser
- Open `/tv/MAIN` on phone, tap "Enable Voice" once, cast to TV
- Phone stays plugged to power, auto-refreshes every 5 sec, pings every 30 sec to stay awake
- No new hardware, no server cost

**Admin control:** Admin → 📺 TV Display Screens → Add TV → choose code (MAIN, DENTAL, OPD, ANC, THEATER, MALE_WARD...), type (WAITING_MAIN shows MORE, CLINIC filtered, DEPARTMENT filtered), clinic/department filter, location name. Per-tenant, active/suspend/delete.

#### 2. Show FULL NAME and QUEUE STATISTIC

**Before:** `/queue/screen` showed code only `E-014` for privacy (spec §6). Good for general queue, but doctor call needs name.

**Now:**
- TV shows **full name** `ABATAN Folake` + **hospital number** `IJD/2026/00099` + **ticket code** `D-012` + **room** `Room 3` + **doctor** `Dr. Ade` + **clinic** `Dental Clinic`
- Also shows **queue statistics** big:
  - Queue Waiting: 8
  - Triage Placed: 5
  - With Doctor: 3
  - Lab/Pharm/Wards Pending: 12
  - Reception Waiting: 4
  - Doctors Ready: 3
  - Done Today: 42
  - Total Today: 67
  - Per clinic breakdown: DENTAL 12, OPD 20, ANC 8...

This is **NOT EMR** — only name, code, place, counts. No diagnosis, no test result.

#### 3. Show MORE than doctor calls

| What TV shows | Source | Example |
|---|---|---|
| Queue join | `QueueTicket` WAITING | `D-012 Emeka Ojo — Dental — waiting 5m` |
| Queue called | `QueueTicket` CALLED | `NOW: D-012 Emeka → Dental` + voice |
| Reception/Billing/PayPoint | `ReceptionIntake` stage | `Folake — At Billing` |
| HIMS registered | `PatientVisit` REGISTERED | `Folake — Folder opened` |
| Triage placed | `PatientVisit` TRIAGED | `Folake → Dental Clinic, Room 3` |
| Doctor call-in | `PatientVisit` IN_CONSULTATION | **BIG GREEN: NOW SERVING Folake Abatan → Room 3** |
| Onward — Lab/Pharmacy/Wards/Theater | `VisitOnward` PENDING | `Folake → Laboratory, then Pharmacy — waiting 12m` |
| LAHSMA clearance | `VisitOnward` LAHSMA | `Folake — LAHSMA desk` |

Waiting area Main TV shows all 8 stages. Clinic TV shows only its clinic's rows.

#### 4. Speak ENGLISH and YORUBA — Bilingual

Every call speaks twice:

**English (en-NG):** "Folake Abatan, please go to Room 3, Dental Clinic"
**Yorùbá (yo-NG):** "Folake Abatan, ẹ jọwọ lọ sí Room 3, Dental Clinic"

How:
- Fixed phrases translated via existing `i18n` (we already have en, yo, ha, ig)
- Patient name stays same, room/clinic name stays same
- Voice speaks English first, waits 3.5 sec, then Yoruba
- Admin can set `voice_languages = en,yo` per TV — can also be `en` only or `en,yo,ha`

#### 5. Nigeria Native Voices — 2 Male + 2 Female recycled daily

**Problem:** Browser voices depend on phone. Not every phone has Yoruba voice installed. Some Androids have only Google US English.

**Solution — 2M2F recycled daily (zero budget, uses built-in voices):**

| Day | Slot | Name we show | How we pick actual voice |
|---|---|---|---|
| Monday | Female 1 | Ada (Nigerian) | Find voices with `en-NG` + female hint (female, Ada, Folake, Samantha). If none, use best `en` female |
| Tuesday | Male 1 | Emeka (Nigerian) | Find `en-NG` + male hint (male, Emeka, Chinedu, David). Fallback to best `en` male |
| Wednesday | Female 2 | Folake (Nigerian) | Same as Female 1 but second voice in list |
| Thursday | Male 2 | Chinedu (Nigerian) | Same as Male 1 but second voice |
| Friday → Monday repeats | Auto | - | `day_of_year % 4` — same voice for whole hospital that day, changes tomorrow automatically, no admin action |

**Implementation in `app/static/js/app.js` + TV template:**
- `speechSynthesis.getVoices()` loads all voices on TV device
- `hmsTv.pickVoice(lang)` filters by lang `en-NG` → `yo-NG` → `en-GB` → `en-US` → any
- Gender detection from voice name (contains "female"/"male" or known Nigerian names)
- Daily slot from server `rotation.slot` (so all TVs in same hospital speak same voice that day)
- If no Nigerian voice installed, still rotates 4 English voices — still sounds Nigerian-friendly because we use `en-NG` lang tag and slower rate `0.92`

**User sees on TV:** Top pill shows "Female Voice 1 - Ada (Nigerian) · EN + YO" and voice bar says "Tap to enable voice — 2 Male + 2 Female recycled daily"

#### 6. Friendly and Attractive Design

**Design choices for premium++:**

- **Background:** Deep navy gradient `#0f172a → #1e293b → #0f4c75` — calm, hospital, not harsh white that hurts eyes on TV
- **Now Serving card:** Bright green gradient `#10b981 → #059669`, pulsing animation, shimmer effect, very big font `3rem` (2rem on phone), rounded 20px, shadow — you can see from 10 meters
- **Next list:** White glass cards `rgba(255,255,255,0.06)` with slide-in animation, code + clinic + type pill
- **Stats:** 8 small glass cards with big numbers `1.8rem`, uppercase labels — like airport dashboard, friendly
- **Icons:** Emojis 📣 ⏭ 📊 🩺 🧪 — no external images needed, works offline
- **Yoruba line:** Italic, slightly transparent, under English name — respectful bilingual
- **Voice bar:** Amber→red gradient when voice OFF (needs tap), green when ON — clear
- **Clock:** Live `en-NG` time, tabular numbers
- **Animations:** Pulse for now serving, shimmer, slide-in — makes TV feel alive, not static
- **No clutter:** Main TV shows 1 NOW + 8 NEXT + 8 stats + doctors ready. Clinic TV shows 1 NOW + 6 NEXT + 3 stats. Keeps it readable from far.

**Offline friendly:** If internet cuts, TV keeps last data + footer "Last update: 14:32" + offline banner (existing `app.js` offline detection).

### How Queue + Doctor Call Connects to TV — Flow

```
Patient scans QR → QueueTicket WAITING → TV shows in "Queue Waiting" + stats + voice "2 waiting in Dental"
Staff clicks "To Reception" → ReceptionIntake → TV shows "Folake — At Reception" + voice
Reception → Billing → PayPoint → HIMS → PatientVisit REGISTERED → TV shows "Folder opened"
Triage places in DENTAL Room3 → PatientVisit TRIAGED → TV shows in "Next" + voice "Folake → Dental Clinic"
Doctor clicks "Call this patient in" → PatientVisit IN_CONSULTATION → TV BIG GREEN "NOW SERVING Folake Abatan → Room 3" + voice EN + YO (Ada voice today)
Doctor finishes → pushes to Lab + Pharmacy → VisitOnward PENDING → TV shows "Folake → Laboratory, then Pharmacy" + voice
Lab completes → VisitOnward DONE → if last step, TV shows "Folake — finished, thank you" + voice
```

All stages already call `announce.to_station()` — TV polls `/api/tv/feed?code=MAIN` every 5 sec and speaks when `now_serving` key changes.

### Admin Setup — Per-tenant, No Code Change

1. Admin → TV Display Screens → See 4 defaults: MAIN, DENTAL, OPD, PHARMACY
2. Add new: Code `ANC`, Name `ANC Clinic TV`, Location `ANC Hall`, Type `CLINIC`, Clinic filter `ANC`, Voice `en,yo`, 2M2F daily ON
3. Open on TV: `https://your-hospital.com/tv/ANC` — QR code shown for quick open
4. Tap "Enable Voice" once — done

### What I Will NOT Do

- No EMR columns on TV (no diagnosis, no test result, no prescription) — guard test will fail build if added
- No new server cost — uses browser built-in TTS, no external API
- No tracking of voice gender — only name hint detection, no personal data

### Ready to Build?

I have already built the backend (models, tv.py engine, /tv routes, admin CRUD, API, migrations) and frontend templates (friendly attractive main + clinic) with Nigeria voices logic and EN+YO bilingual. Tests: 6 TV tests green.

If you say "Build", I will:
1. Finish wiring voice rotation into main `app.js` (already in TV templates)
2. Add TV link to main navigation
3. Run full test suite again
4. Commit

Tell me "Build TV now" or any change to design.

Pending features menu:
1. Patient photo (optional, consent)
2. Estimated total journey time on TV + ticket
3. Fast-track flag for Elderly/Pregnant/Child
4. Merge Department vs Clinic
5. Thank-you SMS after visit
6. Full DB-driven voice places
7. Backup restore test guide
8. Referral QR with clinic pre-select
9. TV voice volume per screen setting
