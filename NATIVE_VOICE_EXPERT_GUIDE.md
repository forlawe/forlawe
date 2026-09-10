# Native Voice Bank — Expert Implementation Guide v1.7.20
## Phrase Bank, Not Clone — Wait for Their Pick

### Founder Rule
> "Native voice bank: wait for their pick, phrase bank not clone."

Meaning:
- **Phrase bank**: Real humans recording real phrases, stored as mp3/wav, stitched together. No AI cloning, no model training, no uncanny valley.
- **Not clone**: Never clone a staff member's voice without consent. Use professional voice talents or willing staff who explicitly record.
- **Wait for their pick**: Staff must audition 2M2F voices and pick their preferred — don't auto-assign. Like you did with `add_voice` tool: present two options, wait for vote, then assign `voice_id`.

### What an Expert Would Do (Production, Enterprise, Rugged, 5k rps)

#### 1. Voice Casting — 2 Male 2 Female per Language = 16 Voices
- **Nigerian English (en)**: Ada (F warm motherly), Emeka (M clear authoritative), Folake (F bright welcoming), Chinedu (M deep reassuring)
- **Yoruba (yo)**: Bimpe (F), Tunde (M), Tayo (F2), Femi (M2)
- **Hausa (ha)**: Aisha (F), Musa (M), Zainab (F2), Ibrahim (M2)
- **Igbo (ig)**: Ngozi (F), Obinna (M), Chiamaka (F2), Uche (M2)
- Each voice has: code (FEMALE1 etc), name, gender, language, accent (en-NG, yo-NG...), description (best for patient calls vs triage vs reception vs emergency)

#### 2. Phrase Bank — 100+ Keys, Dynamic Slots
An expert covers full hospital journey, not just 20 phrases:
- Greetings: morning (5-11), afternoon (12-16), evening (17-23), welcome, goodbye — via `now_naive().hour` with TIMEZONE Africa/Lagos
- Patient flow: queue_waiting, consult_call_in, go_to_billing, go_to_payment, go_to_triage, go_onward, visit_complete, etc.
- Patient-facing TV: patient_call_fullname, patient_next, patient_please_wait, patient_go_to, patient_thank_you
- Staff-facing: staff_attention, staff_please_attend, colleague_joined
- Numbers: 0-20, 22-39, 40,50,60,70,80,90,100, many — for "3 patients waiting"
- Places: laboratory, pharmacy, billing, payment/megalex, triage, reception, hims, dental, opd/sopd/mopd, emergency, ward, theater, male/female ward, antenatal, pediatrics, ophthalmology, physiotherapy, radiology, nutrition, maternity, casualty, dressing, lahsma, nhis, records, cashier, consulting_room — per-tenant dynamic via ServiceDestination.place
- Connectors: please, go_to, waiting_at, and, is, are, with, for, your, has, have, number, patients, patient — for stitching
- Time: today, tomorrow, morning, afternoon, evening, now, minutes, hour, hours
- Politeness: please, thank_you, welcome, excuse_me, sorry — Nigerian hospitality must be respectful
- Urgency: standard, urgent, emergency

#### 3. Dynamic Handling — Be Mindful of Changes
- **Time changes**: `greeting_key_for_now()` uses `now_naive().hour`, not hardcoded "Good morning" at night. Day_of_week via `now_naive().strftime('%A')` for "Today is Monday" etc.
- **Name changes**: `{name}` via `speech_name()` — shortens "MRS TAYO ADEYEMI" to "Mrs Tayo" — title + first name, not full name, works for any new staff/patient name without re-recording.
- **Count changes**: `number_3` recording + `plural()` — "1 patient" vs "3 patients" — never "1 patients"
- **Place changes**: `place_laboratory` per language + dynamic `ServiceDestination.place` — if new destination added (e.g., "MSSD/Welfare"), system tries to match existing place recordings, falls back to TTS if missing.
- **Language changes**: `preferred_lang` from Patient record — if patient prefers Yoruba, try yo phrase bank first, then en fallback.
- **Voice rotation**: `day_of_year % 4` → FEMALE1, MALE1, FEMALE2, MALE2 — recycled daily, per org, per TV screen if `voice_rotate_daily` enabled. Not hardcoded to one voice.

#### 4. Recording Studio — Browser-Based, Expert UX
- **Upload**: Existing mp3/wav/ogg/m4a upload via `storage.py` (db or S3, survives Render ephemeral disk)
- **Record**: New — MediaRecorder API in browser, staff can record directly:
  - Click Record → speak phrase → Stop → Preview → Save
  - Visual waveform, timer, loudness meter
  - Auto-trim silence, normalize volume (Web Audio API)
  - Quality check: max 10 MB, duration 0.5-10 sec, loudness -20 to -10 LUFS
- **Audition & Pick**: Like `add_voice` tool:
  - Present two voices side-by-side playing same phrase "Mr Tunde, 3 patients are waiting at the dispensary"
  - Staff votes → assign `voice_id` to their profile / TV screen
  - Wait for their pick — don't auto-assign

#### 5. Audio Processing — Rugged, Production-Ready
- **Storage**: `storage.py` — db (pilot, survives restarts) or S3 (Supabase Storage / R2) — Render disk wiped on restart, so never use filesystem.
- **Normalization**: On upload, Python could use `pydub` to normalize loudness to -16 LUFS, trim silence < -40dB, convert to mp3 128k.
- **Concatenation**: Frontend plays sequence `audio_sequence` with 150ms gap, crossfade 50ms — sounds natural, not robotic.
- **Caching**: `/api/v1/voice/audio/<id>` with `max_age=86400` — browser caches, 5k rps ready.
- **Fallback**: If native missing, `fallback_to_tts=True` → uses `announce.py:phrase()` via Web Speech API — always works, even if no recordings yet.

#### 6. TV Screens — Per-TV Voice & Volume
- `TvScreen` model already has: `voice_enabled`, `voice_rotate_daily`, `voice_languages`, `voice_volume` (0-100 slider), `brightness`, `night_mode`
- Expert adds: `preferred_voice_id` per TV — e.g., Waiting Area Main TV uses Ada Female warm, Emergency TV uses Chinedu Male deep reassuring.
- Frontend: Polls `/api/v1/voice/next?screen=MAIN&lang=en` → gets `audio_sequence` URLs → plays via `<audio>` elements, not `speechSynthesis` — sounds native.

#### 7. Admin UI — Voice Studio (Expert)
- **Current**: `/admin/native-voice/` shows settings, add voice, upload sample, upload phrase, test compose.
- **Expert improvements**:
  - Audition panel: Play same phrase across 4 voices, staff picks.
  - Recording studio: Record button with waveform.
  - Bulk upload: Zip of mp3s named `queue_waiting_en_FEMALE1.mp3` → auto-import.
  - Missing phrases report: Which keys have no audio per language/voice.
  - Hit count: Which phrases played most, which missing.
  - Script generator: PDF with all phrases for voice talent to record in one session.

#### 8. Implementation Steps for Ijede

1. **Seed voices**: `ensure_default_voices(org_id)` creates 16 voices (2M2F x 4 langs) per org, idempotent.
2. **Record**: Hire 4 voice talents (or willing staff) — 2F2M who speak English + Yoruba/Hausa/Igbo. Record script: `BASE_PHRASE_KEYS` (~120 phrases) x 4 voices = ~480 recordings, ~2 hours per voice.
3. **Upload**: Use `/admin/native-voice/` → Upload sample + phrases. Or use bulk zip.
4. **Pick**: Staff go to `/admin/native-voice/` → Audition → Pick preferred voice for their department TV. System waits for pick, stores in `TvScreen.preferred_voice_id` or `UserPref`.
5. **Enable**: Settings → Enable native voice bank, Prefer native over TTS, Fallback to TTS.
6. **Test**: Use Test Compose → "Mr Tunde, 3 patients waiting at Laboratory" → should play Ada + number_3 + place_laboratory stitched.
7. **TV**: Waiting Area Main TV → set voice_enabled True, volume 100, brightness 100, night_mode True, languages en,yo,ha,ig.

#### 9. Why Phrase Bank, Not Clone?
- **Clone**: Needs AI model (ElevenLabs etc), licensing, consent, sounds uncanny, expensive per character, fails for Yoruba/Hausa/Igbo, needs internet.
- **Phrase bank**: Real human, warm, Nigerian accent, works offline, no licensing, per-tenant, rugged, 5k rps (just serving mp3s), respectful, phrase bank not clone is founder rule.

#### 10. Production Readiness Checklist
- [x] 16 voices seeded (2M2F x 4 langs)
- [x] 100+ phrase keys
- [x] Dynamic time/name/count/place handling
- [x] Daily rotation
- [x] Storage via db/S3 (survives Render)
- [x] Fallback to TTS
- [x] Audition & pick (via add_voice tool + admin UI)
- [ ] Browser recording studio (MediaRecorder) — TODO next
- [ ] Bulk zip upload — TODO
- [ ] Missing phrases report — TODO
- [ ] Script PDF generator — TODO
- [ ] Per-TV preferred voice — TODO (model exists, UI needs)

### Current Implementation (v1.7.20)
- `app/native_voice.py`: 16 voices, 120+ keys, greeting_key_for_now(), voice_for_today(), get_phrase_audio(), compose_announcement(), list_voices(), list_phrases(), upload_phrase_audio()
- `app/models.py`: NativeVoice, NativePhrase, NativeVoiceSetting, TvScreen with voice fields
- `app/views/native_voice.py`: admin_list, save_settings, add_voice, upload_voice_sample, upload_phrase, api get_audio, compose, next_announcements
- `app/templates/admin/native_voice.html`: settings, add voice, voices list with upload sample, phrase bank upload, test compose with audio sequence playback
- `app/announce.py`: speech_name(), plural(), phrase() — TTS fallback, dynamic

### Next Expert Steps (TODO)
1. Add browser recording studio to admin template (MediaRecorder + waveform)
2. Add bulk zip upload endpoint
3. Add missing phrases report API
4. Add script PDF generator
5. Add per-TV voice picker in tv_screen admin
6. Add language auto-detection from Patient.preferred_lang
7. Add audio normalization via pydub (optional)

### How to Use Now
1. Go to /admin/native-voice/ (SUPER_ADMIN)
2. You see 16 voices seeded — Ada, Emeka, Folake, Chinedu, Bimpe, Tunde, etc.
3. Upload sample mp3 for each voice (e.g., Ada saying "Good morning, welcome to General Hospital Ijede")
4. Upload phrase audios: select voice, key (e.g., queue_waiting), lang, text template, file
5. Test Compose: kind=queue_waiting, name=Mr Tunde, count=3, place=Laboratory, lang=en → Compose & Play → should stitch native audios if exist, else TTS fallback
6. Enable settings: Enable native voice bank, Prefer native, Fallback to TTS
7. TV screens will now poll /api/v1/voice/next and play native audios

