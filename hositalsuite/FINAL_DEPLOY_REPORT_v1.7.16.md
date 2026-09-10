# Final Deploy Report v1.7.16 — Native Voice Phrase Bank (Phrase, Not Clone)

**Date:** 2026-08-28 12:55 UTC (Africa/Lagos)
**Version:** 1.7.16
**Commit:** 08ee8e2 (Hcarepro2026/hositalsuite main)
**Previous:** 08ee758 v1.7.15 (Brevo live, Redis, S3, NDPA G1-G6)
**Live URL:** https://hospital-suite.onrender.com
**Repo:** https://github.com/Hcarepro2026/hositalsuite
**Token used:** gh***REDACTED*** — cleaned from remote, must be revoked in GitHub Settings → Developer settings → Personal access tokens → Delete. Token expires 2026-09-04 per GitHub API header.

---

## What was built (per explicit request)

> "Build native phrase bank waits for your pick, phrase bank not clone, be mindful of changes of time, changes of names, just be dynamic in coding, design and approach. Then push with token"

### Core idea: phrase, not clone
- Chrome/Google TTS sounds foreign (en-US robot). Solution: real humans record real phrases, stitched.
- Not AI voice clone. Real staff voices (Ada, Emeka, Folake, Chinedu, Aisha, Musa, Ngozi, Obinna) — names dynamic, any new name works.
- Storage: via `storage.py` (S3 or db), survives Render ephemeral disk.

### Tables (per-tenant, multi-tenant ready)
1. **native_voice** (org_id, code FEMALE1/MALE1/FEMALE2/MALE2, name, gender female/male, language en/yo/ha/ig/en-NG, sample_key, active, is_default, created_at)
2. **native_phrase** (org_id, voice_id FK, key e.g. queue_waiting, language, text_template with {name}{count}{place}{room}{time}, audio_key, duration_ms, active, created_at)
3. **native_voice_setting** (org_id PK, enabled, use_native, fallback_to_tts, languages csv, volume 0-100, rotation_map JSON)

All added to `rls.py` PROTECTED_TABLES → Row-Level Security enforces org_id.

### Dynamic handling (not hardcoded)

**Time changes:**
- `greeting_key_for_now()` uses `now_naive().hour` with TIMEZONE Africa/Lagos from models.py
- 05-11 → greeting_morning, 12-16 → greeting_afternoon, 17-23 → greeting_evening, else greeting_night
- Not hardcoded string; changes every request

**Name changes:**
- `speech_name(full)` → title + first name, e.g. "Dr. Tunde Okonkwo" → "Dr. Tunde", "Mrs. Aisha Bello" → "Mrs. Aisha"
- Works for any new staff/patient, not hardcoded list
- In compose, {name} replaced dynamically

**Count changes:**
- Keys: number_0 .. number_20, number_30/40/50/100, number_many, number_plural
- Per language recordings, fallback to TTS `plural()`
- Dynamic count via `count` param in API

**Place changes:**
- Keys: place_laboratory, place_pharmacy, place_billing, place_payment, place_triage, place_reception, place_hims, place_dental, place_opd, place_emergency, place_ward, place_theater, place_consulting_room
- Per language, plus dynamic `ServiceDestination.place` field per-tenant (any new place)
- In compose, {place} replaced via lookup

**Voice rotation:**
- `voice_for_today(org_id, screen_id)` → day_of_year %4 → FEMALE1/MALE1/FEMALE2/MALE2
- 2 male 2 female recycled daily, per org, not hardcoded to one voice
- Optional `rotation_map` JSON override per tenant setting

**Languages:**
- en (Nigerian English), yo (Yorùbá), ha (Hausa), ig (Igbo) per tenant setting `languages` csv
- Per TV screen language param

### Engine: app/native_voice.py (280+ lines)
- DEFAULT_VOICES: 8 voices (Ada, Emeka, Folake, Chinedu, Aisha, Musa, Ngozi, Obinna) across en/yo/ha/ig
- BASE_PHRASE_KEYS: 60+ keys covering greetings, PATIENT_ALERTS (30 kinds), numbers, places, connectors, time words
- `ensure_default_voices(org_id)` idempotent per org
- `get_phrase_audio(org_id, key, language, voice_id)` via storage.exists()
- `compose_announcement(org_id, kind, name, count, place, patient, room, detail, language)` → returns {text, fallback_text, audio_sequence [{key, language, voice_id, audio_key, audio_url}], use_native bool, voice_today, greeting}
- `upload_phrase_audio()` validates mp3/wav/ogg/m4a 10MB max via storage.put() S3 first
- Fallback to TTS `announce.phrase()` if native missing and fallback_to_tts true

### API
- `GET /api/v1/voice/audio/<phrase_id>` — serves audio via storage.send(), public for TV (RLS all_orgs)
- `GET /api/v1/voice/compose?kind=queue_waiting&name=Mr Tunde&count=3&place=Laboratory&lang=en&org=IJD` — dynamic query, any name/place/count
- `GET /api/v1/voice/next?screen=MAIN&lang=en&org=IJD` — for TV polling, returns now_serving + voice composition

### Admin UI
- `GET /admin/native-voice` — list voices, phrases grouped by key, settings, test compose with auto-play sequence
- `POST /admin/native-voice/settings` — enabled, use_native, fallback_to_tts, languages, volume, rotation_map JSON
- `POST /admin/native-voice/voice/add` — add voice code/name/gender/language
- `POST /admin/native-voice/voice/<id>/upload` — upload sample audio via storage
- `POST /admin/native-voice/phrase/upload` — upload phrase audio per voice/key/language
- Template: app/templates/admin/native_voice.html with audio controls, test compose JS
- Card added to /admin overview: 🎙 Native Voice Bank — Phrase, Not Clone

### Frontend
- app/static/js/native_voice.js — NativeVoice.speak(kind, opts), playSequence(), playOne() via Audio element, speakTTS() fallback with en-NG voice prefer, pollAndPlay(screenCode, lang) for TV
- base.html includes native_voice.js after app.js

### Version
- config.py APP_VERSION 1.7.16, __init__.py fallback 1.7.16

---

## Verification

- [x] `python -m py_compile` all new files ok
- [x] `create_app(scheduler=False)` boots, version 1.7.16
- [x] Tables created via db.create_all() at boot (no migration needed, but alembic head)
- [x] RLS protected
- [x] Git push to Hcarepro2026/hositalsuite main: 08ee758..08ee8e2 success after redacting token from report (push protection triggered, fixed)
- [x] Remote cleaned to https without token
- [x] No full current token in workspace (grep)
- [ ] Live Render deploy: waiting for auto-deploy (~2 min). Check https://hospital-suite.onrender.com/api/v1/health and footer version v1.7.16

Previous v1.7.15 live verified:
- /api/v1/health: {"database":true,"mail":"brevo","storage":"db","whatsapp_mode":"sandbox","status":"ok"}
- /api/v1/ready: {"ready":true}

---

## Security & Compliance

- Token gh***REDACTED*** used for push, cleaned, must be revoked NOW: GitHub → Settings → Developer settings → Tokens → Delete token expiring 2026-09-04. Do not paste new token in chat.
- Push protection blocked secret leak in FINAL_DEPLOY_REPORT_v1.7.15.md line 88 — fixed by redacting and amending commit.
- No Brevo/API secrets in GitHub.
- RLS added for new tables.

---

## Next Steps (Pending Menu)

1. **Upload real human recordings** — Admin → Native Voice Bank → upload sample for each voice + phrase per language (en,yo,ha,ig). Start with 10 critical phrases: greeting_morning/afternoon/evening, queue_waiting, consult_call_in, go_to_billing, go_to_laboratory, go_to_pharmacy, thank_you, please_wait, number_1..10, place_laboratory/pharmacy/billing.
2. **Test on TV** — /tv?screen=MAIN&lang=en, enable native voice in settings, verify audio sequence plays, fallback TTS works.
3. **Revoke PAT** — GitHub Settings → delete token gh***REDACTED***, issue new one if needed with repo scope only, never paste in chat.
4. **Monitor Render** — Ensure v1.7.16 live, check /admin/health version, UptimeRobot ready endpoint.
5. **Consider S3** — For audio storage, set S3_BUCKET + keys in Render env, currently fallback to db (works but S3 cheaper for large audio).
6. **5k rps education** — Current 4000 req/min ≠ 4000 rps. For true 5k rps need load balancer + multiple gunicorn workers + read replicas, not single Render starter. Document in RENDER_DB_MIGRATION.md already.

---

## Voice Reminder

> This build uses native phrase bank, not clone. Time changes via Africa/Lagos hour, names via speech_name() for any new name, counts via number_* recordings, places via place_* per language + ServiceDestination.place per-tenant. 2M2F recycled daily via day_of_year %4. 4 languages en,yo,ha,ig per tenant. Fallback to TTS if native missing.

**End of report — v1.7.16 pushed, remote cleaned, token redacted, ready for real recordings.**
