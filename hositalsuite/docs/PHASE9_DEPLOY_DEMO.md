# Phase 9 — Deployment, Founder Demo, Docs Finalization

Date: 2026-08-30 Lagos
Status: IN PROGRESS → DONE after deploy check

## Deployment Checklist

### Env Vars (Render / Docker)
```
DATABASE_URL=postgresql://... (Supabase) or sqlite:///...
SECRET_KEY=long-random-32+
STORAGE_BACKEND=db  # default survives restarts, no S3 needed for MVP
VAPID_PUBLIC_KEY=... (global fallback)
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:admin@hospital.com
USSD_SHARED_SECRET=ussd-secret-123 (for JSON intake /ussd/queue|booking|complaint)
USSD_SERVICE_CODE_MAP={"*384*123#":"HOSP","*384*124#":"HOSP2"}  # JSON mapping serviceCode→org code for callback
SMS_MODE=sandbox  # or live when Twilio FROM set
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+234...
WHATSAPP_MODE=sandbox
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_APP_SECRET=...
PUBLIC_BASE_URL=https://hospital-suite.onrender.com  # for QR data URI base, avoids Host spoof
APP_VERSION=1.8.0
TIMEZONE=Africa/Lagos
```

### Per-Org VAPID (Multi-Hospital)
Each hospital can have own push keys showing hospital name/logo on notification when app closed like alarm.

Generate:
```bash
python -m py_vapid --gen
# or
npx web-push generate-vapid-keys
```

Set via UI:
- Login as SUPER_ADMIN → /admin/settings → Push Notifications section
- Inputs: vapid_public_key, vapid_private_key, vapid_subject per org
- Saved via services.set_setting(org_id, key, value)
- Code: app/push.py::_get_vapid_for_org checks per-org setting first, fallback global env

Test:
- /api/v1/health reports push_configured true, push_mode vapid
- Personal TV page /t/<key> → "🔔 Notify me when called" → enable → fetches /api/v1/push/vapid-public?access_key=<key> per-org → subscribes → test notification "✅ Alarm Mode ON" → close app → send push via /api/v1/alerts/poll or admin → notification appears with hospital logo /branding/logo

### Logo Upload → Home Screen
- /admin/hospital → upload logo PNG/JPG → save_upload compressed PIL max 512 LANCZOS PNG optimize 9 <100KB → logos/org_<id>.png via storage.put
- Endpoints:
  - /branding/logo → original optimized max 512
  - /branding/logo/192 → 192x192 <30KB
  - /branding/logo/512 → 512x512 <80KB
  - /branding/logo/maskable → 512 canvas white opaque 20% safe zone 80% centered
  - /branding/logo/apple → 180x180 apple-touch-icon
  - Cache-Control 86400
- Manifest: /manifest.webmanifest returns 4 icons per-tenant if has_logo else fallback static icons, name=org.name, short_name=org.code, theme per-org brand_primary
- PWA install: Chrome/Edge/Samsung → Add to Home Screen → icon is uploaded logo, maskable safe zone for Android adaptive
- Topbar: /branding/logo max-height 32px
- Push icon: /branding/logo used as notification icon when closed

### USSD
- JSON intake (aggregator → our API):
  - POST /api/v1/ussd/queue {secret, hospital_code, department, name, phone} → {ticket, access_key, personal_tv_url}
  - POST /api/v1/ussd/booking {secret, hospital_code, department, name, phone, date YYYY-MM-DD, time HH:MM} → {ref, access_key, personal_tv_url}
  - POST /api/v1/ussd/complaint {secret, hospital_code, department, category, description, phone} → {ref}
  - Auth: USSD_SHARED_SECRET, hospital_code required no fallback, phone normalized E.164, PersonalTvSession is_inside=False SMS allowed fallback outside
- Callback (Africa's Talking):
  - POST /api/v1/ussd/callback form-encoded sessionId/serviceCode/phoneNumber/text
  - Returns text/plain CON/END <160 chars
  - Flow: hospital code → menu 1 Join Queue 2 Book 3 Status 4 Complaint 5 Help
  - Dept list numbered, name, ticket creation, status check, complaint
  - Config: USSD_SERVICE_CODE_MAP mapping serviceCode→org code
  - Rate limit 60/min

### TV
- Engine: app/tv.py ensure_default_screens seeds 5 TVs MAIN/DENTAL/OPD/PHARMACY/FASTTRACK per org
- Feed: tv_feed builds now_serving (IN_CONSULTATION + CALLED) + next_up (TRIAGED + WAITING fast-track first) + reception_enriched + onward_enriched deduped + stats fast_track_waiting + clinic_counts, journey estimate try/except
- Pages: /tv and /tv/<code> public, per-tenant via _resolve_org no fallback, 503 if no org
- APIs: POST /api/tv/volume?code=MAIN&volume=75 and /api/tv/brightness?code=MAIN&brightness=80&night_mode=1 public per-tenant scoped, rate_limit 60/min, clamped, no cross-org leak
- QR: /admin/tv/posters shows QR data URI inline base64 PNG, _tv_base_url prefers PUBLIC_BASE_URL

### Health Checks
- /api/v1/health liveness 200 always, reports database, scheduler, storage, whatsapp_mode, sms_mode, twilio, push_configured, push_mode, queue_estimator, patient_sms_inside, version, mail
- /api/v1/ready strict 503 if DB unreachable or schema drift (missing table/column), used for alerting not platform health check

### Render
- Build: pip install -r requirements.txt
- Start: gunicorn 'app:create_app()' or python wsgi.py
- Health check: /api/v1/health
- Auto deploy on push
- Storage: db backend default survives restarts, no need S3 for MVP

## Founder Demo Script (5 min)

1. **Logo Home Screen (30s)**
   - Show /admin/hospital upload logo → save → /branding/logo/192 shows resized <30KB
   - Open /manifest.webmanifest → 4 icons /branding/logo/192,512,maskable,apple per-org, name Hospital Suite Test
   - On phone Chrome → Add to Home Screen → icon is uploaded logo, theme per-org

2. **Personal TV Domino's Tracker (1m)**
   - Join queue /queue/join → name Bola Ajao → ticket G-001 → redirect /t/<access_key>
   - Show /t/<key> page: max-width 520px mobile-first, card shadow rounded 16px, header gold gradient if fast-track, badge ⭐ Fast Track — Premium, position_text "You are 2nd in line", wait_text "12 minutes", timeline Reception→Billing→Payment→HIMS→Triage→Wait Doctor→Consultation→Lab/Pharmacy→Done with done/current/upcoming, dot pulse, checkmarks, estimated ~min, haptic vibrate button, sound en-NG, QR data URI inline, Notify me button
   - Click Notify me → push.js getBrowser detects chrome, isSupported true, enable(accessKey) fetches vapid-public?access_key= per-org → subscribes → "✅ Alarm Mode ON" + test notification works closed like alarm

3. **Gold Fast-Track (30s)**
   - Join queue as elderly/pregnant/child/wheelchair → is_fast_track True → gold shimmer animation, gold border, badge, 50% faster wait via fast_factor 0.5 in queue_estimator.py, journey timeline gold

4. **No SMS Inside (30s)**
   - Show queue join inside hospital → PersonalTvSession is_inside True → no SmsMessage (cost saver 80-90% ₦96k-108k/month), only Personal TV + Push + Voice + Main TV free
   - Outside or emergency/complaint → SMS allowed, show SmsMessage table

5. **USSD Feature Phone (1m)**
   - Dial *384*123# → Enter hospital code TEST → Menu 1 Join Queue 2 Book 3 Status 4 Complaint 5 Help → 1 → dept list 1. Emergency 2. General → 1 → Enter name → John Doe → END You are in Emergency queue. Your number is E-002. Track: /t/<key> SMS will update you.
   - Works on feature phone, no smartphone, no data, 2G, KaiOS, Nokia, Opera Mini, UC Browser

6. **TV Volume/Brightness (30s)**
   - Open /tv/MAIN → waiting hall Main TV shows now_serving + next_up + stats + clinic_counts, voice call-out in 4 langs en,yo,ha,ig, rotation day_of_year%4 Female1 Ada etc
   - Volume slider 0-100 → POST /api/tv/volume?code=MAIN&volume=75 saves per TV per org, brightness 10-100, night_mode toggle, no cross-org leak

7. **Multi-Browser + Slow Internet (30s)**
   - Show Chrome, Firefox, Edge, Samsung Internet, Opera, Safari 16.4+ PWA, UC Browser fallback Main TV+voice+USSD, feature-phone-banner detection
   - Show offline page /offline cached, personal TV offline /my-visit/offline, poll <1KB JSON, retry queue localStorage hms-sync-queue, visibility-aware polling, cached shell hs-shell-v2-*

8. **Smart Algorithm (30s)**
   - Show queue_estimator.py get_live_counts <1KB JSON includes INTAKE_RECEPTION, BILLING, PAYMENT, HIMS, TRIAGE, DOCTORS_READY, WAIT_DOCTOR_VISITS, ONWARD_LABORATORY, PHARMACY, etc cached 30s Africa optimized
   - Formula wait = (pos+1)*avg/60 * load_factor * staff_factor * fast_factor * time_factor, EMA alpha 0.3 per org/stage/hour/dow

9. **Cost Saving (30s)**
   - Before: 1000 patients/day * ₦4 SMS = ₦4000/day = ₦120k/month
   - After: Push free + Personal TV free + Voice free + Main TV free → SMS only emergency/complaint/outside → 80-90% saving = ₦96k-108k/month per hospital, scales multi-hospital

## Docs Updated
- PHASES_STATUS.md Phase 8 DONE, 216 tests passing
- BUILD_V2_COMPLETE.md v2.3 Phase 8 DONE, 11 tests, security hardened
- PHASE7_BUILD.md Phase 7 DONE 204 tests
- PHASE8_BUILD.md Phase 8 DONE 11 tests, security, USSD callback, voice 4 langs, TV volume/brightness scoped
- PREMIUM_V2_FEATURES.md updated with Phase 7+8 + demo checklist + deployment
- This file PHASE9_DEPLOY_DEMO.md deployment + demo script

## Pending After Deploy
- Generate VAPID per hospital via /admin/settings
- Set USSD_SERVICE_CODE_MAP per hospital
- Test PWA install on real Android + iPhone Safari 16.4+
- Test USSD callback with Africa's Talking simulator
- Test TV in waiting hall with real tablet
- Monitor /api/v1/health and /api/v1/ready
- Train staff on My Department, Notifications, Patient Flow shortcuts (PWA long-press)
