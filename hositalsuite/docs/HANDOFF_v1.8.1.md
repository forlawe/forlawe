# HANDOFF — Hospital Admin Manager Suite v1.8.1

**Date:** 2026-08-30 Africa/Lagos  
**Repo:** https://github.com/Hcarepro2026/hositalsuite  
**Branch:** main  
**Live:** https://hospital-suite.onrender.com  
**Commit pushed:** 2312041 (v1.8.1 FIX: logo top, voice webm, responsive, 500 hardening, privacy, VAPID/USSD guide)  
**Previous HEAD:** eb25195  
**Token used:** ***REVOKED*** — **REVOKE THIS TOKEN NOW** at https://github.com/settings/tokens  
**Status:** Live, 6 link checks pass, privacy hardened, voice fixed for Android Chrome

---

## What was just pushed (v1.8.1)

### From 7 screenshots dated 2026-08-30 (Android Chrome)
1. **10:38 Hospital Setup no logo visible** → Fixed: logo now at TOP in green box, 96px preview, 192/512/maskable/apple links, explanation square 512 <100KB for slow internet, multi-hospital per-org, all browsers
2. **Private info leak** → Fixed: TV main + clinic now first name only (Folake not Folake Abatan), not full_name + hospital_number. Reception/lab lists display_name first name only. Staff pages mask_phone: 080****5678. Filters added: mask_phone, first_name, privacy_initials in app/timefmt.py + app/__init__.py
3. **Voice recording not saving/playing 00:10 + Save circled** → Fixed: MediaRecorder on Android Chrome produces webm/opus, backend now allows webm/opus, detects mimetype, returns JSON for fetch, frontend rewrite detects mimeType, shows status, disables button, troubleshooting
4. **Pages not fitting screen** → Fixed: app/static/css/app.css grid cols min(min(200px,100%),1fr), phone ≤600px 1fr, KPI 2 cols, table-wrap overflow-x auto, alarm banner bottom 16px centered max 480px + body padding 90px so not covering
5. **500 error "Something went wrong"** → Fixed: inject_globals ultimate fallback never crashes, tracking dashboard try/except per call, dashboard outer fallback minimal, branding_logo defensive
6. **VAPID per-hospital** → Explained in docs/ELI10_VAPID_USSD_GUIDE.md like 10yo: free alarm saves SMS ₦3-4 (₦90k/month), generate via python -m py_vapid --gen or npx web-push generate-vapid-keys, paste in Render env global OR per-hospital Admin → Push Notifications page
7. **USSD CODE confusion + feature phone provision** → Explained same guide: TODAY we HAVE TV + Voice (4 langs 2M2F) + Personal TV link /t/<key> works on Opera Mini + Help desk phone, NO SMS inside except emergency by design. Future USSD via Africa's Talking webhook ready.

### Files changed in this push
- app/__init__.py — inject_globals hardened ultimate fallback + filters hm, sayhm, mask_phone, first_name, privacy_initials
- app/config.py — APP_VERSION 1.8.0 → 1.8.1
- app/native_voice.py — allow webm/opus, mimetype detection, size checks
- app/views/native_voice.py — upload_voice_sample + upload_phrase allow webm, JSON for fetch, bulk-upload allows webm
- app/templates/admin/hospital.html — rewrite logo top green box
- app/templates/admin/native_voice.html — full rewrite fixed for Android Chrome
- app/templates/admin/native_voice_missing.html — rewrite table-wrap responsive
- app/templates/admin/overview.html — link fix trailing slash + note v1.8.1 webm fixed
- app/templates/alert_settings.html — link /admin/branding → /admin/hospital
- app/templates/base.html — alarm banner not covering, paddingBottom
- app/templates/bookings_staff.html — mask_phone
- app/templates/queue_staff.html — mask_phone + first_name
- app/templates/tv/main.html — display_name first name only, ref truncated, hospital_number removed
- app/static/css/app.css — responsive grids, table-wrap, btn small, KPI 2 cols mobile
- app/timefmt.py — added mask_phone, first_name_only, privacy_initials
- app/tv.py — now_serving/next_up first name only, reception_enriched display_name, onward_enriched display_name
- app/views/main.py — dashboard hardened outer try/except fallback
- app/views/tracking.py — dashboard hardened per call try/except
- docs/BUGFIX_2026-08-30.md — detailed 7-issue report
- docs/ELI10_VAPID_USSD_GUIDE.md — 10yo guide for VAPID free alarm + USSD feature phone provision
- docs/screenshots/*_small.jpg — 7 recovered viewable screenshots (PIL LOAD_TRUNCATED_IMAGES)
- docs/logos/ — logo concepts

### Push command used
```
git remote set-url origin https://***REVOKED***@github.com/Hcarepro2026/hositalsuite.git
git push origin HEAD:main
# → eb25195..2312041 HEAD -> main
git remote set-url origin https://github.com/Hcarepro2026/hositalsuite.git
```

Token removed from config after push. **You must revoke it now** — anyone with token has push access.

---

## Live system health

- /api/v1/health — always 200, shows database true, mail brevo, scheduler true, sms_mode sandbox
- /api/v1/ready — ready true, now also detects schema drift
- Render auto-deploys on push ~2-3 min, free tier
- DB Supabase PostgreSQL
- PWA: /manifest.webmanifest uses /branding/logo for per-hospital icons 192,512,maskable,apple — each hospital own logo on home screen

---

## Privacy audit — done in this push, more needed

**Public pages (no login) checked:**
- patient_hub.html — no PII
- queue_join.html — input only
- queue_ticket.html — code only, no name, says "Your number only shows on TV — not your name. Private and safe."
- queue_screen.html — ticket numbers only, never names (privacy-safe per spec §6)
- tv/main.html + tv/clinic.html — NOW first name only + code, not full_name + hospital_number + phone (fixed)
- personal_tv.html — first name only (Hi {{ feed.patient_name or 'there' }})
- booking_portal.html, complaint_portal.html, feedback_portal.html — input only
- booking_status.html, complaint_status.html — require phone verification, show own ref only

**Staff pages (require_role) — should show PII but masked:**
- queue_staff.html — NOW mask_phone + first_name for called list, filtered by visible_department_ids
- bookings_staff.html — NOW mask_phone, filtered by visible_department_ids (HOD sees own dept only)
- reception/desk.html — shows phone · needs masking (TODO)
- hims/desk.html — shows phone · needs masking (TODO)
- triage/bench.html — no phone shown, okay
- complaint_detail.html — shows complainant phone (prefers contact_method) — okay for complaint handlers (HOD, ADMIN_MANAGER) but should mask for junior (TODO: add mask_phone for non-SUPER_ADMIN)
- feedbacks_staff.html — check
- tracking/dashboard.html — live board shows {{ x.name }} — this is staff-only (VIEWERS = SUPER_ADMIN, MD_CEO, DMD, DCST, APEX_NURSE, HEAD_ADMIN_HR, ADMIN_MANAGER, HOD) — okay but should be first name only for extra privacy (TODO)

**Next privacy TODO (for next chat):**
- Apply mask_phone filter to all remaining staff templates: reception/desk.html, hims/desk.html, cashdesk/desk.html, lahsma/desk.html, complaint_detail.html (mask unless SUPER_ADMIN), feedbacks_staff.html, referrals_staff.html, tracking/dashboard.html live board first_name only
- Ensure all staff list queries filter by visible_department_ids (already done for queue, bookings, tracking, but check reception, triage, consulting, cashdesk, lahsma, hims)
- Add audit: ensure patient cannot see other patients via ?key= guessing — access_key is token_urlsafe 12 (72 bits) → safe, but should rate limit ticket_page (TODO)
- Ensure personal TV access_key is also masked in logs

---

## English rewrite — 1000% human, patient care oriented, short clear simple standard English nice tone — PARTIAL

**Done:**
- hospital.html — rewritten to human: "Main App Logo — Shows on Phone Home Screen" + nice tone + tip white background + slow internet note
- native_voice.html — rewritten: "Voice Studio — Record Directly (Browser) — FIXED for Android Chrome" + troubleshooting human tone
- native_voice_missing.html — rewritten: "Table scrolls sideways on phone — swipe left/right" + how to fix quickly on phone
- base.html alarm banner — rewritten short clear: "Enable alarm mode? Get notified even when app closed, like alarm — free, saves SMS cost"
- BUGFIX + ELI10 guides — written in simple human English

**TODO for next chat (user requested rewrite ALL in App conversations, instructions, directions):**
- patient_hub.html tiles: Book a visit, Join the queue, Ask us anything, Tell us a problem, How was your visit, Invite a friend — already human but can be even shorter clearer: "Book a visit — Choose a day and time that works for you." → keep, good. Need to check all other templates for grammar.
- queue_join.html — needs rewrite: "Get a number and track your turn live." → good but check form labels, errors
- booking_portal.html — check
- complaint_portal.html — check
- feedback_portal.html — check
- chat.html — check
- personal_tv.html — check
- reception/new.html — check
- triage/bench.html, consulting/room.html, cashdesk/desk.html, lahsma/desk.html, hims/register.html, etc. — all need rewrite to short clear simple standard English nice tone, patient care oriented, correct grammar like English expert
- Create script to batch rewrite: find all muted, hint, label, h1, h2, p and rewrite to human tone — need English expert pass

**How to do it:**
- For each template, replace jargon with plain English, contractions allowed, warm confident empathetic, ends with soft call-to-action, never diagnoses
- Example: "Please choose a department and enter your name." → "Please choose where you need to go and tell us your name. We're here to help you."
- Use contractions: you're, we're, it's
- Short sentences, active voice

---

## AI worker — make very knowledgeable about entire app — PARTIAL

**Current KB:**
- app/chatbot/kb_core.py — greetings, appointments, bills, hours, first visit, services, complaints, emergency, admission, visiting hours, discharge, aftercare, followup — warm tone, English + Pidgin + Yoruba/Hausa/Igbo on core
- kb_departments_full.py — 31 departments, 459 intents / 7559 triggers
- kb_extended.py, kb_depts.py, etc. — more intents
- engine.py — BM25-style scoring, clinical guardrail (refuses diagnosis/prescription), teaching detection, agreement/refusal, followup_for bare yes
- ai.py — ladder Groq → Gemini → OpenRouter, free tier, guardrails before and after model, daily cap 400 per tenant, metering

**TODO to make AI smarter than founder/MD/CEO/staff combined:**
- Create app/chatbot/kb_app_master.py — comprehensive intents covering:
  - Entire app function: patient hub 6 tiles, booking online + physical, queue join + ticket + screen, complaint + status + anonymous, feedback, referrals, share links, QR posters, TV screens (MAIN, DENTAL, OPD, PHARMACY, FASTTRACK executive gold), personal TV /t/<key> works closed like alarm, push VAPID per-hospital free alarm, voice bank 2M2F 16 voices 4 langs, audition & pick, recording studio MediaRecorder webm, missing phrases report, bulk zip, hospital setup logo top + colours + SMS sender tag, branches/sites gate pin, attendance I am here clock-in/out, roster 4 patterns + 8 leave types + bulk upload, HIMS folder search + open folder + duplicate prevention + payment routes LAHSMA/Megalex/NHIS/HMO, Reception front door special needs insurance Billing → PayPoint, Triage OPD/SOPD/MOPD/EMERGENCY doctor rooms blood sugar, Call Room Queue /consulting-room call in finish, Onward routing Lab/Pharmacy/Billing/Megalex/LAHSMA/Emergency 1-3 at a time, tracking door-to-door time per-department live who is waiting week-on-week busiest hours allocation advice, reports archive PDF verification codes, audit logs hash-chained, admin users roles permissions, security phone codes headers self-check, notifications WhatsApp logs retries, data requests NDPA access erasure, system health backups engine-independent CSV-in-zip restore drill, offline-first SW caches shell, slow internet Africa optimized payload <1KB poll when visible, multi-browser Chrome Firefox Edge Samsung Opera Safari iPhone Add to Home Screen UC Opera Mini fallback TV+Voice, feature phone provision TV+Voice+Personal link+Help desk phone, no SMS inside except emergency founder rule, fast track gold lane premium pay more get fast executive lounge quiet calm private, payment upfront gate, SMS/WhatsApp Termii Twilio templates copy-ready curl samples, USSD Africa's Talking CON/END callback, queue estimator per-org cache smart real-time algorithm adjusting queue time based on patients at reception, billing, Megalex, LAHSMA, HIMS, Triage, waiting to see doctors, on ward locations
  - Instructions/directions/procedures/operations: how to book, how to join queue, how to check status, how to complain, how to give feedback, how to use personal TV, how to enable alarm mode, how to add logo, how to set VAPID keys, how to record voice, how to manage roster, how to open folder, how to triage, how to call patient, how to route onward, how to view tracking, how to create backup, how to manage users, how to assign roles, etc.
  - All in short clear simple standard English nice tone, patient care oriented, correct grammar, 1000% human
  - Then seed via seed_global_kb at boot

**Implementation sketch for next chat:**
```python
# app/chatbot/kb_app_master.py
KB = [
  dict(cat="app_overview", intent="app_what_is", kw=["what is this app","what does app do","explain app"], en="This is your hospital care system. It makes a visit calm, quick and respectful. You can book, join queue, track your turn live on your phone, ask questions, tell us a problem, share feedback, and watch TV for your number. For staff, it guides every step from reception to doctor to lab to home.", ...),
  dict(cat="app_overview", intent="how_to_book", kw=["how to book","book appointment steps"], en="To book: Open Book a visit, choose Fast Track if you want to be seen faster, pick department, pick date and time, enter your name and phone, tap Book. You get a reference instantly. You can check it anytime with Check a booking.", ...),
  # ... 100+ more covering every procedure
]
```

---

## How to continue in next chat

**Opening message for new chat:**
> Continuing Hospital Suite v1.8.1 for General Hospital Ijede. Repo https://github.com/Hcarepro2026/hositalsuite branch main, commit 2312041 just pushed, live https://hospital-suite.onrender.com. Read docs/HANDOFF_v1.8.1.md + docs/BUGFIX_2026-08-30.md + docs/ELI10_VAPID_USSD_GUIDE.md. Token ***REVOKED*** has been used and must be revoked — ask for new token. Next tasks: 1) Complete privacy audit mask_phone everywhere + visible_department_ids, 2) Rewrite ALL templates to 1000% human patient care short clear simple standard English nice tone correct grammar like English expert, 3) Make AI worker very knowledgeable kb_app_master.py covering entire app function instructions directions procedures operations smarter than founder/MD/CEO/staff combined.

**Environment setup (sandbox wipes each message):**
```bash
cd /home/user/work/hositalsuite
pip install -q -r requirements.txt
sudo apt-get install -y -q postgresql
(sudo service postgresql start || sudo pg_ctlcluster 17 main start)
sudo -u postgres psql -q -c "DROP ROLE IF EXISTS hms;" -c "CREATE ROLE hms LOGIN PASSWORD 'hms_test_pw';" -c "DROP DATABASE IF EXISTS hms_test;" -c "CREATE DATABASE hms_test OWNER hms;"
pip install -q playwright && python -m playwright install --with-deps chromium
python -m pytest -q
TEST_DATABASE_URL='postgresql://hms:hms_test_pw@127.0.0.1:5432/hms_test' python -m pytest -q
python tools/check_links.py
```

---

## Security reminder

- Token ***REVOKED*** was pasted in chat, used to push, removed from .git/config, but still in chat history — **revoke immediately** at https://github.com/settings/tokens
- Never paste token in chat again — create 7-day token when needed
- After revoke, create new token with repo scope only (no workflow needed unless CI)

---

## End of handoff v1.8.1 — push done, hands-off ready
