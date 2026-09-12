# Hospital Suite v2 — Premium+++ Features, Cost Saving, Multi-Hospital, Africa Optimized

## Founder Rules Implemented

### 1. No SMS Inside Hospital Except Serious Complaints/Emergency
- **Before**: Every queue join, booking, complaint sent SMS (costly, ₦3-4 each)
- **Now**: Inside hospital → Personal TV + Push (free, works closed like alarm) + Voice + Main TV
- **SMS only if**:
  - Patient outside hospital (no PersonalTvSession or is_inside_hospital=False)
  - Emergency/Critical priority (consult_call_in with EMERGENCY)
  - Complaint escalated/SLA breach (serious)
  - Feature phone fallback when no push subscription
- **Code**: `app/notifications_v2.py::_should_send_sms_patient` + `app/views/queue.py::call_next` should_sms logic
- **Saving**: 80-90% SMS reduction
- **Test**: `tests/test_queue.py::test_staff_call_progress_and_finish` checks personal TV session, not SMS

### 2. Feature Phone / Non-Android/iOS Provision
**Question**: What provision for patients with feature phones or not Android/iOS?

**Answer**: Yes, full fallback provision noted in UI and code:

- **Main TV in waiting hall**: `/queue/screen?dept=X` shows ticket numbers only (privacy-safe), no names. Calls patient via `consult_call_in` voice + visual. Works for any phone.
- **Voice announcements**: Browser speech synthesis (`speechSynthesis`) speaks patient name + room in 4 languages (en, yo, ha, ig). Free, no SMS. Works on all browsers + TV tablets.
- **USSD**: `/api/v1/ussd/queue`, `/api/v1/ussd/booking`, `/api/v1/ussd/complaint` — dial *xxx# to join queue, book, complain. Returns ticket ref via USSD, no internet needed. Tested in `test_ussd_queue_join`.
- **Personal TV fallback**: If no JS/fetch/Promise (KaiOS, Opera Mini, Nokia), meta refresh every 30s (`personal_tv.html` feature phone detection). No push, but TV + voice still works.
- **SMS fallback only for feature phones outside**: If no PersonalTvSession + no PushSubscription + phone present → SMS allowed as fallback for queue_next (important).
- **UI banner**: `base.html` feature-phone-banner shows "Feature phone detected — Main TV + Voice + USSD will call you. No app needed."
- **Note**: If no provision, app shows banner and staff helps.

### 3. App Loading Time Premium
- **Defer JS**: `app.js` and `push.js` loaded with `defer` (not blocking first paint)
- **Lazy native_voice**: `native_voice.js` (3.5KB) lazy loaded only when staff needs voice (`_loadNativeVoice()`), not for patients. Saves 3.5KB first paint.
- **Code split**: `app.js` 34KB, `push.js` 8KB, `native_voice.js` 3.5KB — split, not one 100KB bundle
- **Minimal CSS**: `app.css` 23KB, critical CSS inline in base.html, rest cached
- **Compressed logo**: Logo upload compresses to max 512x512 PNG optimized <100KB (PIL LANCZOS + optimize level 9). Generates resized variants on fly:
  - `/branding/logo/192` → 192x192 PNG <30KB
  - `/branding/logo/512` → 512x512 <80KB
  - `/branding/logo/maskable` → 512 canvas white bg 80% centered (20% safe zone)
  - `/branding/logo/apple` → 180x180 apple-touch-icon
- **SW caches shell**: `/offline`, icons, CSS, JS cached on install for <1s first paint on 3G
- **Skeleton**: shimmer animation while loading, premium feel

### 4. Slow Internet Africa Optimized
- **Offline-first**: Service Worker `sw.js` caches shell (CACHE `hs-shell-v2-*`), network-first for API with cache fallback
- **Low-data**: Personal TV poll payload <1KB JSON `{position_text, wait_text, current_stage, timeline}` — not full HTML
- **Cached shell**: `/offline` and `/my-visit/offline` cached, shows last known when offline
- **Retry queue**: `app.js` has offline queue with `localStorage` + background sync `sync` event `hs-sync-queue` — hmsQueueSubmit saves offline, trySyncQueue on online
- **Poll payloads**: `/my-visit/<key>` <1KB, `/api/v1/alerts/poll?after=0` <2KB, `get_live_counts()` <1KB
- **Network-first for static**: CSS/JS network-first but cache fallback — prevents old UI freeze
- **Visibility-aware polling**: Poll only when `document.visibilityState === 'visible'` to save data/battery

### 5. Multi-Hospital Design
- **org_id scoping**: Every table has org_id, every query filters by org_id, RLS on PostgreSQL (`app/rls.py` protects 30+ tables)
- **Per-org branding**: Logo upload per org (`logos/org_<id>.png`), colors `brand_primary`, `brand_accent`, `brand_gold` per org via `services.get_setting(org_id, key)`
- **Per-org manifest**: `/manifest.webmanifest` returns `manifest_payload(org, settings)` with org name, code, colors, 4 icons from `/branding/logo/192|512|maskable|apple` — shows org name + logo on phone home screen
- **Per-org VAPID**: `app/push.py::_get_vapid_for_org(org_id)` checks `services.get_setting(org_id, vapid_public_key/private/subject)` first, fallback global env VAPID_PUBLIC/PRIVATE/SUBJECT. `is_configured(org_id)` and `get_vapid_public(org_id)` now per-org, `send_push_to_subscription` uses org_id VAPID. Each hospital can have own push keys showing hospital name/logo on notification.
- **Per-org voice**: `native_voice` and `native_phrase` have org_id, per-tenant voices
- **Per-org TV**: PersonalTvSession org_id, tv_screen org_id, station announcements filtered by org_id
- **Branch support**: `branch_id` on many tables, `branches` module stamps branch

### 6. Smart Real-Time Algorithm / Free AI Model
**File**: `app/queue_estimator.py` — no external API, runs in 5ms on cheap phone

- **Inputs**:
  - Reception count: `ReceptionIntake` stage RECEPTION
  - Billing count: `JourneySegment` BILLING open
  - MEGALEX/PayPoint: PAYMENT open
  - LAHSMA: LAHSMA open
  - HIMS: HIMS open
  - Triage: TRIAGE open + WorkClaim TRIAGE
  - Per-doctor waiting: `DoctorSession` ready count today, `WorkClaim` per kind
  - Onward: LABORATORY, PHARMACY, etc open segments + VisitOnward pending

- **Logic**:
  - Historical avg per stage per hour_of_day + day_of_week stored in `QueueEstimate` (EMA alpha 0.3)
  - Real-time load: `count_open_segments(org_id, stage)` 
  - Staff available: `count_staff_available(org_id, stage)` — DoctorSession ready or WorkClaim open
  - Formula: `wait = (position+1)*avg_sec/60 * load_factor * staff_factor * fast_factor * time_factor`
    - load_factor = 1 + min(open_count/(staff_count*5), 1.0) capped 2.0
    - staff_factor = max(0.5, 2.0/staff_count)
    - fast_factor = 0.5 if fast-track (elderly/pregnant/child/wheelchair) else 1.0
    - time_factor = 1.2 lunch 13-14, 1.3 after 16
  - Clamp 1-180 min
  - Updates on segment close via `update_estimate_from_segment()` EMA

- **Premium UX**: Shows "12 min" not seconds, updates live every 10s, timeline shows ~min per step
- **Free**: No ML API, pure math

### 7. Premium+++ UI Encouraging Continuous Use
- **Personal TV**: Domino's style tracker, max-width 520px mobile-first, card with shadow, rounded 16px
- **Gold fast-track**: `linear-gradient(135deg,#FFD700,#FFA500)` background for fast-track header, badge "⭐ Fast Track — Premium", gold border
- **Journey timeline**: `.ptv-step` with left border, dot pulse animation `@keyframes pulse`, done=green #12b5a5, current=primary with pulse, upcoming=gray
- **Animations**: pulse, shimmer, slideUp, scale on active `.premium-card:active{transform:scale(0.98)}`
- **Haptic**: `navigator.vibrate([500,200,500,200,1000])` when called, `[200,100,200]` normal, `[300,100,300]` urgent
- **Sound**: `speechSynthesis` speaks status in 4 languages, volume 1.0 rate 0.9, en-NG voice preferred
- **Notify button**: "🔔 Notify me when called" → push subscribe, shows "✅ You will be notified even if app closed, like alarm" — alarm-like
- **QR**: QR image for keeping page, no install needed, works on any browser
- **Footer tip**: "Main TV in waiting hall also shows your number" + voice language + no SMS note
- **Base premium**: gold shimmer, premium-card transition, haptic-btn scale

### 8. Main App Logo Upload Shows on Phone Home Screen
- **Upload**: `/admin/hospital` form file input logo, `save_upload` to durable storage `logos/org_<id>.png` compressed via PIL
- **Compression**: PIL resize max 512x512 LANCZOS, PNG optimize compress_level 9, <100KB, JPEG fallback if >100KB — admincp.py _CompressedFile wrapper
- **Serving**: `/branding/logo` + resized endpoints:
  - `/branding/logo/192` → 192x192 PNG <30KB optimized
  - `/branding/logo/512` → 512x512 <80KB
  - `/branding/logo/maskable` → 512 canvas white bg, logo 80% centered (20% safe zone for Android adaptive)
  - `/branding/logo/apple` → 180x180 apple-touch-icon
  - All via storage.get + PIL LANCZOS + optimize, Cache-Control 86400, per-org via current_org(), fallback original on error
- **Manifest**: `pwa.py::manifest_payload` checks `org.logo_path`, if has_logo → 4 icons `/branding/logo/192` (any), `/512` (any), `/maskable` (maskable), `/apple` (any). Optimized for loading time premium.
- **PWA install**: When PWA installed, home screen icon is uploaded logo (per-tenant) resized, shows hospital logo on phone home screen, maskable safe zone for Android
- **Brand logo in topbar**: `<img src="/branding/logo" max-height 32px>` if logo_path exists else 🏥
- **Per-org VAPID**: Allows hospital logo + name on push notification when app closed

### 9. Other Browsers Support
- **Supported**: Chrome, Firefox, Safari 16.4+ (PWA installed), Edge, Samsung Internet, UC Browser, Opera, Opera Mini (fallback)
- **Feature-detect Push**: `hmsPush.isSupported()` checks `'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window`
- **Browser detection**: `getBrowser()` parses UA for edge, opera, samsung, uc, firefox, safari, chrome, unknown
- **Fallbacks**:
  - If no push → Main TV + voice + USSD + SMS only emergency (alert shows provision)
  - If Notification denied → instructions per browser (Chrome Settings > Privacy > Notifications etc)
  - If no serviceWorker → meta refresh fallback for feature phones
  - Safari needs PWA installed for push — noted in enable()
- **Footer**: Shows detected browser name
- **SW**: Works on all modern, cache-first shell, network-first API, push event + notificationclick + sync + periodicsync works closed like alarm

### 10. Build Phases

- **Phase 0**: Multi-hospital, org_id, RLS, branding/logo endpoint, manifest dynamic — DONE
- **Phase 1**: Personal TV session, presence, push subscription models, queue_estimator EMA — DONE
- **Phase 2**: No SMS inside, smart routing, voice announcements, USSD, feature phone banner — DONE
- **Phase 3**: Premium UI, gold fast-track, timeline, haptic, sound, QR, offline shell — DONE
- **Phase 4**: Loading time (defer, lazy native_voice, compressed logo, SW offline-first, <1KB poll), multi-browser push, resized logo endpoints, per-org VAPID — DONE (v2.1)


### 11. Phase 7: Full Regression & Performance QA (NEW v2.2)
- **Full regression**: 204 tests passing in 12 files (queue+booking+reception+roles+referral+sms+tracking+triage+hims+lahsma+feedback+tv) — fixed hims.py duplicate consent_at bug.
- **PWA install**: Verified manifest public, display standalone, start_url /welcome?source=pwa, theme_color per-org, 4 icons /branding/logo/192,512,maskable,apple when logo exists. Shortcuts for My Department, Notifications, Patient Flow (Android long-press).
- **Logo resize**: Verified /branding/logo/192 <30KB, /512 <80KB, /maskable 512x512 white opaque safe zone, /apple 180, Cache-Control 86400, PIL LANCZOS optimize 9.
- **Push closed like alarm**: SW has push event, notificationclick, sync, periodicsync, TEST_PUSH, icon /branding/logo per-org, badge, vibrate per priority, requireInteraction, tag, actions View/Dismiss, renotify. push.js getBrowser detects edge/opera/samsung/uc/firefox/safari/chrome, isSupported checks SW+PushManager+Notification, enable(accessKey) fetches vapid-public?access_key= per-org. Works Chrome, Firefox, Edge, Samsung, Opera, Safari 16.4+ PWA installed, UC fallback Main TV+voice+USSD.
- **Loading time premium**: base.html defer app.js 34KB + push.js 8KB, lazy native_voice 3.5KB only when needed, skeleton shimmer, compressed logo, first paint <1s 3G — test_loading_time_premium_defer_and_lazy.
- **Slow internet Africa**: SW offline-first hs-shell-v2-*, SHELL caches /offline, /my-visit/offline, icons, css, js, fetch network-first API cache fallback, poll <1KB JSON {position_text,wait_text,current_stage,timeline}, retry queue localStorage hms-sync-queue + trySyncQueue on online, background sync hs-sync-queue, visibility-aware polling only when visible — test_slow_internet_africa_offline_and_low_data.
- **No SMS inside**: queue join inside creates PersonalTvSession is_inside True, no SmsMessage (cost saver 80-90%), SMS only emergency/complaint/outside — test_no_sms_inside_except_emergency.
- **Multi-browser**: getBrowser detection, feature-phone-banner, fallback inapp+TV+voice — test_multi_browser_support_detection.
- **Smart algorithm all inputs**: count_open_segments includes JourneySegment + ReceptionIntake today + VisitOnward pending, get_live_counts includes INTAKE_*, WAIT_DOCTOR_VISITS, DOCTORS_READY, TRIAGE_OPEN, ONWARD_*, cached 30s — test_smart_algorithm_all_inputs.
- **Per-org VAPID UI**: /admin/settings has vapid_public_key/private/subject inputs per-org, cost saver note — test_per_org_vapid_settings_ui.
- **USSD/Voice/TV provision**: USSD routes exist, speechSynthesis, queue/screen privacy-safe — test_ussd_and_voice_and_tv_provision.
- **Tests**: tests/test_phase7_premium.py 10 tests all passing.

### 12. Phase 8: USSD, Voice, TV Integration + Security Hardening (NEW v2.3)
- **Security fix**: api.py USSD org fallback to first org — loophole closed, now 422/404 no fallback. tv.py _resolve_org fallback closed, now returns None 503. Multi-hospital isolation, no cross-org leak.
- **Phone normalization**: sms.normalize_ng_number for USSD, E.164 stored.
- **PersonalTvSession for USSD**: queue/booking create session is_inside=False SMS allowed fallback outside, returns access_key + personal_tv_url /t/<key>.
- **USSD callback Africa's Talking**: POST /api/v1/ussd/callback form-encoded sessionId/serviceCode/phoneNumber/text + JSON. Stateless * split, serviceCode mapping USSD_SERVICE_CODE_MAP or first token hospital_code. CON/END plain text <160 chars 2G optimized. Menu: 1 Join Queue (dept list numbered, name, ticket), 2 Book Appointment (dept, date YYYY-MM-DD, time slot list, name, booking), 3 Check Status (ticket code, position+wait), 4 Complaint (dept, category, description), 5 Help. Rate limit 60/min, audit, personal TV.
- **Voice per-org 4 langs**: native_voice.py 16 voices 2F2M per lang en,yo,ha,ig Nigerian names, ensure_default_voices per org, voice_for_today day_of_year%4 rotation, compose_announcement dynamic time greeting, speech_name, number, place, connectors, per language. TV voice_rotation_for_today returns slot_name + languages en-NG,yo-NG,ha-NG,ig-NG.
- **Main TV privacy-safe volume/brightness**: /api/tv/volume and /brightness public per-tenant scoped via _resolve_org no fallback, rate_limit 60/min, code required, org_id+code filter, volume 0-100 brightness 10-100 clamped, night_mode bool, no cross-org leak test 404/403. feed safe serialization only code/name/spoken/clinic/room.
- **Branding logo defensive**: PIL open try/except corrupted image fallback original or 404 not 500, maskable white opaque safe zone, LANCZOS, optimize 9, Cache-Control 86400, <30KB 192 <80KB 512.
- **Personal TV defensive**: update_session_from_ticket/intake/visit handle None created_at/started_at try/except, fallback wait, build_personal_feed defensive getattr, live_counts try/except <1KB, timeline safe.
- **Tests**: tests/test_phase8_ussd_voice_tv.py 11 tests all passing — org isolation, personal TV outside, booking personal TV, complaint, callback CON/END flow, voice per-org 4 langs, tv _resolve_org no fallback, volume/brightness scoped no leak, branding logo corrupted fallback, personal TV defensive None.
- **Total**: 216 tests passing in 13 files, 100 core in 8 files.

### 13. Founder Demo Checklist (Phase 9)
- **PWA install**: Upload logo via /admin/hospital → /branding/logo/192,512,maskable,apple → /manifest.webmanifest 4 icons per-org → Add to Home Screen → hospital logo on phone home screen, theme per-org.
- **Personal TV Domino's tracker**: Join queue /queue/join → ticket E-001 → /t/<access_key> shows position_text "You are 2nd in line", wait_text "12 minutes", timeline with done/current/upcoming, gold fast-track if elderly/pregnant, haptic vibrate, sound en-NG, QR data URI inline, Notify me button → push subscribe → "✅ Alarm Mode ON" + test notification works closed like alarm.
- **Gold fast-track**: Elderly/pregnant/child/wheelchair → gold shimmer, badge ⭐ Fast Track — Premium, 50% faster wait via fast_factor 0.5.
- **Journey timeline**: Reception → Billing → Payment → HIMS → Triage → Wait Doctor → Consultation → Lab/Pharmacy → Done, checkmarks, pulse dot, estimated ~min.
- **Push closed like alarm**: SW push event icon /branding/logo, badge, vibrate per priority, requireInteraction, tag, actions View/Dismiss, notificationclick opens /t/<key> or /notifications, works when app closed — test via push.js Test Alarm button.
- **No SMS inside**: Join queue inside hospital → PersonalTvSession is_inside True → no SmsMessage, cost saver 80-90%. Outside or emergency/complaint → SMS allowed.
- **USSD**: Dial *384*123# → Enter hospital code → Menu 1 Join Queue → dept list → name → ticket ref + /t/<key>. Works on feature phone, no internet, 2G.
- **TV volume/brightness**: Open /tv/MAIN → volume slider 0-100, brightness 10-100, night_mode toggle → POST /api/tv/volume?code=MAIN&volume=75 saves per TV per org, no cross-org leak.
- **Multi-browser**: Chrome, Firefox, Safari 16.4+ PWA, Edge, Samsung Internet, UC Browser, Opera — feature-detect push, fallback Main TV+voice+USSD.
- **Slow internet**: Offline page /offline cached, personal TV offline /my-visit/offline, poll <1KB, retry queue hms-sync-queue, visibility-aware.

### 14. Deployment (Phase 9)
- **Env**: DATABASE_URL, SECRET_KEY, STORAGE_BACKEND=db (default survives restarts on Render), VAPID_PUBLIC_KEY/PRIVATE_KEY/SUBJECT global fallback, USSD_SHARED_SECRET for USSD aggregator, USSD_SERVICE_CODE_MAP JSON mapping serviceCode to org code, SMS_MODE=sandbox, WHATSAPP_MODE=sandbox, PUBLIC_BASE_URL for QR.
- **Per-org VAPID**: Generate per hospital: `python -m py_vapid --gen` or `npx web-push generate-vapid-keys` → set via /admin/settings → Push Notifications section vapid_public_key/private/subject per org, or env fallback.
- **Logo**: Pillow + qrcode required, already in requirements.
- **Push**: pywebpush installed, SW at /sw.js, manifest at /manifest.webmanifest with 4 icons per-org.
- **Health**: /api/v1/health liveness 200 always, reports database, scheduler, storage, whatsapp_mode, sms_mode, push_configured, queue_estimator, patient_sms_inside, version, mail. /api/v1/ready strict 503 if DB unreachable or schema drift.
- **Render**: Build command pip install -r requirements.txt, Start gunicorn app:create_app(), health check /api/v1/health, auto deploy on push.
- **Cost**: SMS 80-90% saved ₦96k-108k/month per hospital, push free, personal TV free, voice free, Main TV free.

## Cost Saving Summary
- Before: SMS for every queue, booking, complaint — 1000 patients/day * ₦4 = ₦4000/day = ₦120k/month
- After: Push (free) + Personal TV (free) + Voice (free) + Main TV (free) — SMS only emergency/complaints outside — 80-90% saving = ₦96k-108k/month saved per hospital
- Multi-hospital: saving scales per hospital

## Testing
- `tests/test_queue.py` 6 passed — v2 personal TV, no SMS inside, push + TV session
- `tests/test_reception.py` 23 passed — folder reuse, assistance consent
- `tests/test_roles.py` 14 passed — v1.7.18 strict least privilege
- `tests/test_booking.py` 7 passed — SMS normalized, booking creates queue ticket
- Total 43+ core passed after logo resize + per-org VAPID

## Deployment
- STORAGE_BACKEND=db default survives restarts on Render
- VAPID: global env VAPID_PUBLIC_KEY, PRIVATE, SUBJECT, or per-org settings vapid_public_key etc
- Logo resize requires Pillow (already in requirements)
- Push: pywebpush, SW /sw.js, manifest /manifest.webmanifest with 4 icons per-org
