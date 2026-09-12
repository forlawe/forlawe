# Phase 8 Build — USSD, Voice, TV Integration + Security Hardening

Date: 2026-08-30 Lagos
Status: DONE — 11 tests passing, 43 total core

## What Was Built

### Security Hardening (Loopholes Closed)
- **api.py USSD org fallback**: Previously if hospital_code missing or unknown, fallback to first org — security loophole cross-hospital data leak. Fixed to 422 hospital_code required, 404 unknown hospital_code, no fallback. Multi-hospital isolation.
- **tv.py _resolve_org fallback**: Same loophole — fallback to first org if current_org None. Fixed to return None and 503 if no org resolved. Caller must handle 503, not leak first org data. Source code check in test ensures `order_by(Organization.id).first()` not present.
- **Phone normalization**: USSD endpoints now call `sms.normalize_ng_number` to convert 080... to +234 E.164, stored normalized, cost saver SMS uses normalized.
- **PersonalTvSession for USSD**: Queue and booking create PersonalTvSession with `is_inside_hospital=False` so SMS allowed as fallback per founder rule (outside hospital). Previously no session, so no push/TV provision. Now creates session, updates via `update_session_from_ticket/appointment`, returns access_key + personal_tv_url `/t/<key>`.
- **TV volume/brightness scoped**: Public but scoped to org via _resolve_org (no fallback), rate_limit 60/min, code required, screen filtered by org_id+code, volume 0-100 clamped, brightness 10-100 clamped, night_mode bool parsing. Cross-org leak test: org1 user cannot update org2 UNIQUE8 TV — returns 404/403 not 200, org2 screen unchanged.

### USSD Aggregator (Africa's Talking / My-OTP)
- **JSON intake** (existing, hardened):
  - POST /api/v1/ussd/queue, /booking, /complaint with USSD_SHARED_SECRET auth, hospital_code required, dept ilike, phone normalized, PersonalTvSession outside, returns ticket/ref + access_key + personal_tv_url.
  - Complaints are serious — SMS allowed even inside per founder rule.
- **Callback for AT** (new):
  - POST /api/v1/ussd/callback accepts form-encoded (AT) sessionId/serviceCode/phoneNumber/text and JSON generic. Stateless via `text.split("*")`, multi-hospital via serviceCode mapping `USSD_SERVICE_CODE_MAP` config or first token hospital_code.
  - Returns text/plain CON/END <160 chars, 2G optimized Africa.
  - Flow:
    - text="" → CON Enter hospital code
    - text="HOSPCODE" → CON Welcome to {org.name} 1. Join Queue 2. Book Appointment 3. Check Status 4. Complaint 5. Help
    - 1 → dept list numbered (limit 8), 1*deptChoice → CON Enter full name, 1*dept*name → create ticket END with ticket code + /t/<key> SMS will update.
    - 2 → dept list, date YYYY-MM-DD validation, time slot list from settings booking_slots, name → create booking END with ref + /t/<key>.
    - 3 → CON Enter ticket code, 3*CODE → lookup QueueTicket, count waiting before, estimate_wait via queue_estimator, END Ticket CODE: pos in line ~wait min.
    - 4 → dept list, category, description → create Complaint END with ref.
    - 5 → Help END with hospital code and TV info.
  - Rate limit 60/min, audit logs, personal TV session created.
  - Feature phone provision: USSD works without smartphone, KaiOS, Nokia, Opera Mini, UC Browser — no app needed.

### Voice per-org 4 Languages
- **native_voice.py**: Already had 16 voices (4 langs x 4 slots) — 2F2M per lang en,yo,ha,ig with Nigerian names Ada/Emeka/Folake/Chinedu + Bimpe/Tunde/Tayo/Femi + Aisha/Musa/Zainab/Ibrahim + Ngozi/Obinna/Chiamaka/Uche.
- **Per-org**: ensure_default_voices(org_id) idempotent, seeds en voices by default, setting NativeVoiceSetting org_id languages en,yo,ha,ig volume 100 enabled False use_native True fallback_to_tts True.
- **Rotation**: voice_for_today(org_id) day_of_year %4 → FEMALE1/MALE1/FEMALE2/MALE2, custom rotation_map JSON in setting, fallback any active.
- **Compose**: compose_announcement(org_id, kind, name, count, place, language) dynamic time greeting via now_naive().hour, speech_name shortens any new name, number_{n} recordings, place_* recordings, connectors, time words, politeness, urgency. Returns text + audio_sequence URLs or fallback TTS.
- **TV**: tv.py voice_rotation_for_today returns slot_name + languages en-NG,yo-NG,ha-NG,ig-NG + labels English/Yorùbá/Hausa/Igbo. Frontend uses Speech API with en-NG voice preferred, falls back to en-GB/en-US, still Nigerian accent premium.
- **Test**: test_voice_per_org_4_langs checks org isolation, 4 langs compose not crash.

### Main TV Privacy-Safe
- **tv.py engine**: ensure_default_screens seeds 5 TVs MAIN/DENTAL/OPD/PHARMACY/FASTTRACK per org, idempotent. tv_feed builds now_serving (IN_CONSULTATION + CALLED queue) + next_up (TRIAGED + WAITING fast-track first) + reception_enriched + onward_enriched deduplicated + stats fast_track_waiting + clinic_counts. Journey estimate try/except. Defensive None handling.
- **Volume/brightness APIs**: POST /api/tv/volume?code=MAIN&volume=75 and /api/tv/brightness?code=MAIN&brightness=80&night_mode=1 public per-tenant, best effort, no auth for TV remote but scoped to org, rate_limit 60/min, clamping, returns ok + volume/brightness. QR poster: _qr_data_uri base64 data URI inline, _tv_base_url prefers PUBLIC_BASE_URL env to avoid Host spoof.
- **Admin CRUD**: /admin/tv list/create/edit/toggle/delete, per-org, code unique, cannot delete MAIN, flash messages, template admin/tv.html with depts/clinics.

### Branding Logo Defensive
- **/branding/logo** endpoints: /branding/logo original, /192 <30KB, /512 <80KB, /maskable 512 white opaque safe zone 20% centered, /apple 180. PIL LANCZOS resize, PNG optimize 9, Cache-Control 86400. Try/except corrupted image fallback to original via storage.send or 404, not 500. Test branding_logo_corrupted_fallback mocks storage.get b"not an image" → 200 or 404 not 500.

### Personal TV Defensive
- **personal_tv.py**: ensure_personal_session now accepts appointment param, handles None created_at, try/except queries, access_key reuse ticket key if not used else generate 24-char secret. update_session_from_ticket handles None created_at, defensive count, fallback wait 5 min. update_session_from_appointment new for USSD booking outside. update_session_from_intake/visit defensive None started_at/created_at, fallback wait. build_personal_feed defensive getattr, live_counts try/except <1KB, timeline safe index check, position_text/wait_text premium.
- **Test**: test_personal_tv_defensive_none_created_at creates ticket with created_at None, ensures no crash.

## Tests

File: tests/test_phase8_ussd_voice_tv.py 11 tests

- test_ussd_org_isolation_no_fallback: 422 no code, 404 unknown, 200 valid, org isolation
- test_ussd_queue_creates_personal_tv_outside: is_inside False, org_id correct
- test_ussd_booking_creates_personal_tv: access_key exists, is_inside False
- test_ussd_complaint_allowed: ref exists
- test_ussd_callback_con_end_flow: CON/END flow join queue, ticket created
- test_ussd_callback_status_check: CON ticket code, END position
- test_voice_per_org_4_langs: ensure_default_voices per org, voice_for_today, 4 langs compose
- test_tv_resolve_org_no_fallback: source check no fallback
- test_tv_volume_brightness_scoped: cross-org leak 404/403, volume update scoped
- test_branding_logo_corrupted_fallback: 404 no logo, corrupted not 500
- test_personal_tv_defensive_none_created_at: None created_at no crash, feed has position_text

All 11 passing in 7.9s, 43 total with phase7+queue+booking+tv.

## Cost Saving

- No SMS inside preserved, USSD outside SMS allowed as fallback only if no push.
- USSD callback uses plain text <160 chars, no SMS cost for USSD itself (aggregator handles).
- Personal TV + Push free, Main TV free, Voice free — 80-90% SMS reduction ₦96k-108k/month per hospital.

## Feature Phone / Future Phone Provision

- **USSD**: *384*xxx# works on any phone, no smartphone, no data, 2G. Returns ticket ref + /t/<key> for tracking when smartphone available.
- **TV**: Main TV shows ticket numbers only (privacy-safe), voice call-out in 4 langs, waiting hall.
- **Voice**: Speech announcements via TV tablets, no phone needed.
- **SMS fallback**: Only outside or emergency/complaint per founder rule, optional for non-smart.
- **Meta refresh**: Personal TV page has meta refresh 30s fallback if no JS, server-rendered first paint.
- **Banner**: Feature phone detected via hmsFeaturePhoneCheck (no fetch/Promise or KaiOS/Nokia/Opera Mini/UC) shows #feature-phone-banner "Feature phone detected — Main TV + Voice + USSD will call you. No app needed".
- **Docs**: Note provision in docs/PREMIUM_V2_FEATURES.md and PHASES_STATUS.

## Multi-Browser

- Push: Chrome, Firefox, Edge, Samsung Internet, Opera, Safari 16.4+ PWA installed, UC fallback TV+voice+USSD.
- getBrowser detects edge/opera/samsung/uc/firefox/safari/chrome, isSupported checks SW+PushManager+Notification, enable(accessKey) per-org VAPID.

## Loading Time & Slow Internet

- USSD callback <160 chars, no JSON, 2G optimized.
- Personal TV feed <1KB JSON position_text/wait_text/timeline, cached 30s live_counts.
- SW offline-first hs-shell-v2-* caches shell, poll visibility-aware, retry queue localStorage hms-sync-queue.
- Logo resize 192 <30KB 512 <80KB, Cache-Control 86400.

## Next: Phase 9 Docs/Demo/Deploy

- Update docs/PREMIUM_V2_FEATURES.md with Phase 8 USSD callback flow, voice 4 langs per-org, TV volume/brightness scoped, security hardening.
- Update BUILD_V2_COMPLETE.md Phase 8 DONE.
- Generate VAPID keys per hospital, set via /admin/settings or env.
- Deploy to Render: STORAGE_BACKEND=db, VAPID, SMS_MODE=sandbox, WHATSAPP_MODE=sandbox, check /health, /ready.
- Founder demo: PWA install with logo, personal TV Domino's, gold fast-track, journey timeline, push closed like alarm, USSD *xxx# join queue, TV volume control.
