# Hospital Suite — Notification System v2
## World-Class, Smart, Cost-Saving, Premium++++ — Works Even When App is Closed Like Alarm

**Date:** 2026-08-29
**Version:** Plan for v1.8.0
**Goal:** Cut SMS/WhatsApp cost by 80-90% by making IN-APP the primary channel using TEXT + VOICE + PERSONAL TV, while keeping patient access EASY (no forced app install), and making notifications work 100% even when app is closed — like an alarm.

---

### PART 1: AUDIT — What We Have Today (Honest)

**Good — Keep:**
1. `AppNotification` table — multi-tenant, user_id, channel (inapp/email/whatsapp/sms/station), template_key, entity_type, audit trail. Solid.
2. `announce.py` — 30+ speakable events, speech_name() shortens "MRS TAYO ADEYEMI" → "Mrs Tayo", plural() never says "1 patients". Premium phrasing.
3. `tv.py` + `TvScreen` — MAIN waiting hall + CLINIC + DEPARTMENT + FASTTRACK executive TVs, per-tenant, brightness, volume, night mode, 4 languages en,yo,ha,ig, voice rotation day%4.
4. `native_voice.py` — 16 voices 2M2F x 4 langs, 157 phrase keys, phrase bank not clone, audition & pick, MediaRecorder studio, bulk zip.
5. `pwa.py` — manifest per-hospital (name, short_name, brand_primary), icons 192/512/maskable, `sw.js` with shell cache, offline page.
6. `app.js` — `hmsVoice` (speechSynthesis + bell chime + audio unlock banner), `hmsAlerts` polling `/api/v1/alerts/poll?after=id` every 30s, toasts, browser Notification, quiet hours OFF by default (good for night shift).
7. `scheduler.py` — tick every 30s, idempotent, duty reminders, overdue, SLA escalation, WhatsApp queue + SMS queue, flow bottleneck detection, forgotten patient voice.
8. `notifications.py` — TEMPLATES dict, WhatsApp-first then SMS fallback, staff() SMS ≤160 GSM-7, DND channel.

**Gaps — Why It Still Costs Money & Fails When Closed:**
1. **Polling only when open:** `hmsAlerts.start()` only runs when page open and user authenticated. If nurse closes phone, no alerts. That's why SLA breached.
2. **Service Worker v1 is cache-only:** No `push` event, no `notificationclick`, no background sync, no periodic sync. So can't wake up like alarm.
3. **No Web Push subscriptions:** No VAPID keys, no `PushSubscription` table, no `/api/v1/push/subscribe`. So can't send from server when closed.
4. **No Personal TV for patient:** Main TV shows everyone (privacy risk if full name). No individual screen like Domino's tracker: "You are 3rd, 12 min, Room 3". So we forced SMS to tell patient "you are next" — costs money.
5. **No smart routing / cost saver:** Code queues WhatsApp + SMS for every event, even when patient is sitting in waiting hall looking at TV. Should be IN-APP first, SMS only if offline > X min or critical.
6. **Notifications page is list only:** `notifications.html` — plain list, no filters, no priority, no actions, no voice replay, no TV link.
7. **Patient easy access preserved but not leveraged:** Patient uses QR/link, no login — good. But that page doesn't subscribe to push without install. So we send SMS because we have no other way to reach them after they leave desk.
8. **Voice needs interaction:** `speechSynthesis` blocked until user taps. We have unlock banner, but if staff never taps, voice silent. Needs persistent audio unlock + SW-driven notification with sound.
9. **No alarm semantics:** Alarm works when closed because OS keeps it. Our notifications don't use `requireInteraction`, `vibrate`, `renotify`, `actions`, or `Notification Triggers` API.

**Cost Impact Today:**
- Every queue_next = 1 SMS (Termii ₦3-4) or Twilio $0.06
- 500 patients/day x 2 SMS = 1000 SMS/day = ₦3000/day = ₦90k/month/hospital
- WhatsApp similar cost + template approval pain
- If we move 80% to in-app, save ₦72k/month/hospital, 10 hospitals = ₦720k/month

---

### PART 2: DESIGN PRINCIPLES — Non-Negotiable

1. **Patient easy access stays:** No forced install, no signup to get care. QR → /welcome → /t/<code> → personal tracker. Install is OPTIONAL upgrade for premium experience.
2. **In-app is primary, SMS/WhatsApp is fallback:** Rule: Try TEXT+VOICE+TV first. Only if user offline > threshold or event = EMERGENCY/ESCALATED, then SMS.
3. **Works closed like alarm:** Use Web Push + Service Worker + VAPID + Background Sync + Periodic Sync + Notification Triggers. Staff PWA installed = alarm-grade.
4. **Premium++++ UX:** Every notification has TEXT (read), VOICE (heard), VISUAL (TV/personal screen), HAPTIC (vibrate). Not just text.
5. **No EMR in notifications:** Only name, place, counts, time — never diagnosis, drugs.
6. **Multi-tenant, per-hospital settings:** Notification preferences per org, not per deploy.
7. **Battery & data friendly:** Batching, quiet hours per user (optional), low-data mode, no spam.

---

### PART 3: NEW ARCHITECTURE — 5 Layers, 1 Hub

```
                    ┌─────────────────────────────────┐
                    │   UNIFIED NOTIFICATION HUB      │
                    │   (Single Source of Truth)      │
                    │   AppNotification + New Tables  │
                    └──────┬──────────────────┬───────┘
                           │                  │
        ┌──────────────────┼──────────────────┼──────────────────┐
        │                  │                  │                  │
   TEXT LAYER         VOICE LAYER       VISUAL LAYER        PUSH LAYER
   (read)             (heard)           (seen)              (closed)
        │                  │                  │                  │
   - In-app bell     - Native voice     - Main TV          - Web Push VAPID
   - Toast           - Browser TTS      - Clinic TV        - SW push event
   - List            - Chime            - Dept desk        - Background Sync
   - Badge count     - Audio unlock     - PERSONAL TV      - Periodic Sync
   - Actions         - Volume per TV    - My Visit Tracker - Alarm triggers
```

#### Layer 1: TEXT — Unified Hub (Keep + Upgrade)

**Current:** AppNotification with channel inapp
**New:**
- New table `PushSubscription` (user_id nullable for patient anonymous, endpoint, p256dh, auth, org_id, created_at, device_info, is_active)
- New table `NotificationPreference` (user_id, org_id, channel_enabled: inapp=true, voice=true, push=true, sms_fallback=false, whatsapp_fallback=false, quiet_start, quiet_end, language)
- New table `PersonalTvSession` (id, org_id, patient_id or intake_id or ticket_id, access_key, org_code, current_stage, position, estimated_wait, is_fast_track, last_seen_at, push_sub_id nullable)
- New table `NotificationBatch` (to avoid spam: group 3 queue events into 1)
- Upgrade `AppNotification`: add `priority` (LOW/NORMAL/HIGH/CRITICAL), `category` (queue/booking/complaint/flow/roster), `actions` JSON (e.g., [{"action":"view","title":"View"},{"action":"dismiss"}]), `personal_tv_url`, `voice_key`, `require_interaction` bool, `vibrate` pattern, `ttl` seconds.

**Smart Routing Logic (Cost Saver):**
```python
def should_send_sms(org_id, user, event_urgency, last_seen_seconds):
    if event_urgency == "EMERGENCY": return True  # always SMS for emergency
    if last_seen_seconds < 300: return False  # user online in last 5 min, in-app enough
    if user_pref.sms_fallback == False: return False
    if event_urgency == "CRITICAL" and last_seen_seconds > 900: return True
    return False  # default no SMS

# For patient: if personal TV session active and push subscribed, NO SMS
```

#### Layer 2: VOICE — TEXT + VOICE Fusion (Keep + Upgrade)

**Keep:** announce.py phrase(), speech_name(), native_voice phrase bank
**New:**
- `VoiceQueue` — priority queue per device: emergency interrupts standard
- Volume ducking: when voice speaks, lower TV video volume
- Per-TV voice: each TvScreen can pick own voice (Ada vs Emeka) from /admin/native-voice/
- Patient personal voice: when personal TV calls "Folake, please go to Room 3", use patient's preferred_lang (yo/ha/ig/en) + their chosen voice from native bank, not browser default
- Audio unlock v2: On first login, show modal "🔔 Enable voice like alarm? [Enable]" — calls `unlockAudio(true)` + requests Notification permission + registers push. Remember in localStorage.
- Chime before voice: 0.9 gain, 2 tones for standard, 3 for urgent, 5 for emergency — already done, keep.

#### Layer 3: VISUAL — TV Evolution (Biggest Innovation for Cost Saving)

**Today:** Main TV shows all, clinic TV filtered.
**New:**

**A. Main TV — stays, but privacy improved:**
- Show ticket code + first name only: "E-014 — Folake" not "Folake Abatan". Full name only on personal TV.
- Add "Next 3" ticker with estimated wait: "E-014 (2 min) → E-015 (8 min) → E-016 (15 min)"
- Add QR to personal tracker: each ticket row has mini QR to /t/<access_key> — patient scans to get personal screen on own phone.

**B. Personal Patient TV — NEW, Award-Winner Core:**
- URL: `/t/<access_key>` (from queue ticket) or `/my-visit/<visit_no>` or `/intake/<ref>` — no login, access_key is secret (like boarding pass)
- What it shows (premium Domino's-style tracker):
  ```
  ┌─────────────────────────────────┐
  │  GHIJEDE — Your Visit           │
  │  Ticket: E-014  Fast Track ⭐   │
  │  ━━━━━━━━━━━━━━━━━━━━━━         │
  │  ● Reception ✓ 2 min            │
  │  ● Billing ✓ 5 min              │
  │  ● HIMS ✓ 1 min                 │
  │  ◉ Triage — You are here        │
  │     Position: 3rd in line       │
  │     Est wait: 12 minutes        │
  │     Doctor: Dr Emeka, Room 3    │
  │  ○ Consulting — Next            │
  │  ○ Pharmacy — After             │
  │  ━━━━━━━━━━━━━━━━━━━━━━         │
  │  [🔔 Notify me] [🔊 Voice]      │
  │  QR to keep this page           │
  └─────────────────────────────────┘
  ```
- Features:
  - Live position from `tv_feed` + `tracking` JourneySegment
  - Estimated wait from `tracking_engine.estimate_wait_minutes()`
  - Voice button: speaks personal call in their language
  - Notify me button: subscribes to push WITHOUT installing app (browser push works without PWA install on Android/Chrome)
  - Works offline: cached shell, shows last known position + "offline, will update when back"
  - Vibrate + sound when status changes to CALLED — even if phone locked (via push)
  - No SMS needed if user has this open — save cost

**C. Staff Department Desk — Upgrade:**
- At /my-department, show live voice announcements + who is on what task (WorkClaim noticeboard)
- Add "🔔 Enable alarm mode" — installs PWA + subscribes push + shows test voice.

#### Layer 4: PUSH — Works When Closed Like Alarm (The Magic)

**How alarm works:** OS keeps alarm service alive. Web equivalent: Service Worker + Push API.

**Service Worker v2 — New Code:**

```javascript
// sw.js v2 — Works closed like alarm
const CACHE = "hs-v2-__VERSION__";
const SHELL = ["/offline","/static/icons/icon-192.png","/static/icons/icon-512.png","/my-visit/offline"];

self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())); });

// 1. PUSH EVENT — server sends push, SW wakes up even when app closed
self.addEventListener("push", event => {
  let data = {};
  try { data = event.data.json(); } catch(e) { data = {title:"Hospital", body:event.data.text()}; }
  const options = {
    body: data.body,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    vibrate: data.vibrate || [200,100,200],
    data: {url: data.url || "/", id: data.id},
    requireInteraction: data.requireInteraction || data.urgency==="emergency", // stays like alarm
    renotify: true,
    tag: data.tag || "hs-"+data.category,
    actions: data.actions || [{action:"view", title:"View"}, {action:"dismiss", title:"Dismiss"}],
    silent: false
  };
  // Play chime + voice if possible (via audio worklet) — best effort
  event.waitUntil(self.registration.showNotification(data.title, options));
});

// 2. CLICK — open personal TV or dashboard
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const url = event.notification.data.url || "/";
  event.waitUntil(clients.matchAll({type:"window"}).then(wins=>{
    for(let w of wins){ if(w.url.includes(url) && "focus" in w) return w.focus(); }
    return clients.openWindow(url);
  }));
});

// 3. BACKGROUND SYNC — when offline queue syncs
self.addEventListener("sync", event => {
  if(event.tag==="hs-sync-queue"){ event.waitUntil(syncQueue()); }
});

// 4. PERIODIC SYNC — check for new alerts every 15 min even closed (Android)
self.addEventListener("periodicsync", event => {
  if(event.tag==="hs-periodic"){ event.waitUntil(fetchAlertsAndNotify()); }
});

async function fetchAlertsAndNotify(){
  // fetch /api/v1/alerts/poll and show notification if new
}
```

**Backend Push — VAPID:**

- Generate VAPID keys: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT=mailto:admin@hospital`
- New env: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`
- New endpoint: `POST /api/v1/push/subscribe` {endpoint, keys: {p256dh, auth}, device_info} → save PushSubscription
- New endpoint: `POST /api/v1/push/unsubscribe`
- New service `app/push.py`: `send_push(subscription, payload)` using `pywebpush`
- Scheduler job `job_push_queue` — process pending push like WhatsApp queue
- When new AppNotification created, also try push if subscription exists

**Alarm-like Persistence:**

- For CRITICAL (complaint escalated, emergency arrival): `requireInteraction:true` — notification stays on screen until user acts, like alarm
- `vibrate: [500,200,500,200,1000]` — long pattern
- `renotify:true` + `tag` — if same patient called again, re-alert with sound
- On Android, if PWA installed + notification permission granted, it shows even when app closed, even after reboot (if user enables "run in background")
- For iOS: iOS 16.4+ supports Web Push if PWA installed to home screen. We will show iOS install guide in /install.

**No Forced Install — How Patient Gets Push Without Install:**

- Chrome Android: `PushManager.subscribe()` works even without PWA install, just needs HTTPS + user gesture. So patient on /t/<code> taps "🔔 Notify me" → browser asks "Allow notifications?" → if yes, we save subscription linked to that ticket access_key, no account needed.
- Patient never forced to install, but if they DO install, experience upgrades to full alarm mode (periodic sync, offline tracker).

#### Layer 5: COST SAVER — Smart Routing Engine

**Rule Engine:**

```
Event → Priority → Check Presence → Route

LOW (queue waiting, returning patient):
  → In-app + Personal TV only
  → NO SMS/WhatsApp

NORMAL (reception arrival, patient registered, ready_for_folder):
  → In-app + Station + Personal TV
  → NO SMS unless offline >15 min

HIGH (consult_ready, go_to_billing, go_to_triage, queue_assigned, triage_backlog):
  → In-app + Voice + Personal TV + Push (alarm if subscribed)
  → SMS only if push failed AND offline >5 min

CRITICAL (emergency_arrival, complaint_escalated, critical_score, patient_forgotten, flow_bottleneck):
  → In-app + Voice + Push (requireInteraction) + Station + Main TV
  → SMS + WhatsApp as fallback after 2 min if not acknowledged

EMERGENCY (complaint_escalated_voice, SLA breach):
  → ALL channels immediately
```

**Presence Detection:**

- `last_seen_at` from `/api/v1/alerts/poll` — update User.last_login_at or new `UserPresence` table
- For patient: `PersonalTvSession.last_seen_at` updated on each poll of /t/<code>
- If last_seen <5 min → user online → no SMS
- If last_seen >15 min → user away → consider SMS for HIGH+

**Batching:**

- If 3 queue_waiting events in 2 min for same department, batch into 1: "Nurse Tayo, 3 patients waiting at Reception" not 3 separate toasts.

---

### PART 4: DATA MODEL CHANGES (New Tables)

```sql
PushSubscription
- id, org_id, user_id nullable, patient_access_key nullable, endpoint (unique), p256dh, auth, device_info, is_active, created_at, last_used_at

NotificationPreference
- org_id, user_id (PK), inapp_enabled bool default true, voice_enabled bool default true, push_enabled bool default false, sms_fallback bool default false, whatsapp_fallback bool default false, quiet_start, quiet_end, language default en, created_at

PersonalTvSession
- id, org_id, access_key unique, ticket_id nullable, intake_id nullable, visit_id nullable, patient_id nullable, current_stage, position int, estimated_wait int, is_fast_track bool, last_seen_at, push_sub_id nullable, created_at

NotificationBatch
- id, org_id, user_id, category, count, first_at, last_at, is_sent bool

PushQueue (like SmsMessage/WhatsAppMessage)
- id, org_id, subscription_id, payload JSON, status QUEUED/SENT/FAILED, attempts, last_error, created_at, sent_at
```

No breaking changes to existing tables.

---

### PART 5: API CHANGES

```
POST /api/v1/push/subscribe
  Body: {endpoint, keys:{p256dh, auth}, device_info, access_key?}
  Auth: optional (patient anonymous allowed if access_key valid)
  Returns: {ok, subscription_id}

POST /api/v1/push/unsubscribe
  Body: {endpoint}

GET /api/v1/push/vapid-public
  Returns: {public_key}

GET /api/v1/alerts/poll?after=id  (existing, upgrade)
  Now also returns: personal_tv_url, voice_key, priority, actions, requireInteraction

GET /api/v1/my-visit/<access_key>
  Public, no auth, returns JSON feed for personal TV (position, wait, journey, next steps)

POST /api/v1/my-visit/<access_key>/seen
  Update last_seen_at for presence detection

GET /t/<access_key>  (new page)
  Public personal TV page — premium tracker, no login, PWA-capable

GET /my-visit/offline
  Offline shell for personal TV
```

---

### PART 6: FRONTEND — Premium UX

**Staff:**
- Bell icon in topbar shows unread count badge (from AppNotification status != READ)
- Click bell → notification center: tabs ALL / QUEUE / COMPLAINTS / ROSTER / FLOW, each with voice replay button, action buttons, link to personal TV or dept desk
- Each toast has 🔊 replay voice + View action
- /alert-settings upgraded: toggles for voice, push, sms fallback, quiet hours, language, test alarm button that triggers real push when closed (to prove it works)

**Patient:**
- /t/<code> page:
  - Top: hospital name, ticket, fast track gold if applicable
  - Middle: vertical timeline with checkmarks, current stage highlighted, position, est wait, doctor name/room
  - Bottom: 2 big buttons: "🔔 Notify me when called (works even if you close app)" and "🔊 Speak my status"
  - QR code to keep page
  - If push subscribed: show "✅ You will be notified even if app closed, like alarm"
  - Offline banner if offline
  - Voice: when status changes to CALLED, auto speak in patient's lang + vibrate + push notification with requireInteraction

**TV:**
- Main TV footer: "Scan QR for personal tracker — no app needed"
- Clinic TV: shows "Now serving: E-014 — Folake (Room 3)" + personal QR

---

### PART 7: HOW IT WORKS WHEN CLOSED 100% — Like Alarm, Explained Simple

1. **User taps "Enable alarm mode" once** — we ask for Notification permission + register push subscription + save VAPID keys. This is one-time.
2. **Service Worker stays alive in OS** — even if user closes Chrome, Android keeps SW registered. Like alarm app registered with OS.
3. **Server has push subscription** — when new event happens (e.g., "You are next"), scheduler calls `push.py:send_push()` → sends to Google FCM / Mozilla autopush → wakes up SW on user's phone even if app closed.
4. **SW shows notification with sound + vibrate + requireInteraction** — stays on screen like alarm until user taps View or Dismiss.
5. **Tap View opens personal TV** — even if app was closed, it opens browser to /t/<code> showing "Please go to Room 3 now"
6. **Periodic sync (Android)** — every 15 min, SW wakes itself to check for missed alerts, even without push (fallback if push fails)
7. **iOS:** Needs PWA installed to home screen (iOS 16.4+). We show guide: "iPhone: tap Share → Add to Home Screen → then enable notifications". Once installed, same alarm behavior.

**Why it doesn't need SMS:** Because push is free, works closed, and is instant. SMS only as last resort if push fails 3 times or user never allowed notifications.

---

### PART 8: KEEPING EASY ACCESS — No Forced Install

- Patient journey today: Scan QR at gate → /welcome → enter phone → get ticket → wait. No install needed. **We keep this 100%.**
- New journey: Same, but ticket page now shows personal tracker /t/<code> with live position. No login.
- Upgrade path (optional): On /t/<code>, small banner: "Want alarm when it's your turn? Tap 🔔 Notify me — no app install needed". If they tap, we get push permission, no install. If they want full alarm after reboot, we suggest "Add to Home Screen" — optional.
- If patient says no to notifications, they still see personal TV when they keep page open, and Main TV calls them. No SMS cost if they are in waiting hall looking at TV — we detect presence via last_seen_at.
- For patients who leave hospital (e.g., go to buy drugs outside), if they enabled push, they get notified when called back, no SMS. If they didn't enable, then after 10 min offline we fallback to SMS — cost only for those who opted out.

---

### PART 9: COST SAVING PROJECTION

- Today: 100% queue events → SMS
- v2: 
  - 60% patients in waiting hall with personal TV open or Main TV visible → 0 SMS
  - 20% patients enabled push (no install) → 0 SMS, push free
  - 10% staff online (last_seen <5 min) → 0 SMS, in-app only
  - 10% fallback (offline, no push, critical) → SMS/WhatsApp
- Saving: 80-90% SMS/WhatsApp cost
- Example: 1000 SMS/day → 100 SMS/day = save 900/day = 27k/month/hospital

---

### PART 10: IMPLEMENTATION PHASES (After Approval)

**Phase 0 — Foundation (1 day):**
- Add tables PushSubscription, NotificationPreference, PersonalTvSession, PushQueue
- Generate VAPID keys, add env VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT
- New file app/push.py (send_push via pywebpush)
- Endpoints /api/v1/push/subscribe, /api/v1/push/vapid-public, /api/v1/my-visit/<key>

**Phase 1 — Service Worker v2 (1 day):**
- Rewrite sw.js to handle push, notificationclick, sync, periodicsync
- Update pwa.py manifest to include gcm_sender_id, handle periodic sync
- Update pwa.js to request notification permission + subscribe

**Phase 2 — Personal Patient TV (2 days):**
- New page /t/<access_key> — premium tracker UI, timeline, position, est wait, voice button, notify me button
- Backend tv_feed personal version
- QR on Main TV linking to personal tracker
- Offline shell

**Phase 3 — Unified Hub + Smart Routing (2 days):**
- Upgrade AppNotification with priority, category, actions, personal_tv_url
- New NotificationPreference UI at /alert-settings
- Smart routing engine in notifications.py — in-app first, SMS only if needed
- Batching logic
- Notification center redesign /notifications with tabs, voice replay, actions

**Phase 4 — Alarm Mode + Testing (1 day):**
- Staff "Enable alarm mode" flow
- Test push when closed (real device)
- iOS install guide
- Load test 5000 users/sec (push queue)

**Total: ~7 days, no breaking changes, backward compatible.**

---

### PART 11: PREMIUM UX TOUCHES — Award-Winner Details

- **Haptic:** Different vibrate patterns: standard [200,100,200], urgent [300,100,300,100,300], emergency [500,200,500,200,1000]
- **Sound:** Chime before voice, volume per TV, ducking
- **Language:** Patient hears in their preferred_lang (yo/ha/ig/en) — not just English
- **Fast Track Gold:** Personal TV shows gold theme if fast_track, with "⭐ Premium" badge
- **Estimated wait:** Live from tracking engine, not static
- **QR everywhere:** Main TV, ticket print, personal TV — scan to keep
- **Dark mode / Night mode:** TV respects brightness + night_mode setting
- **Accessibility:** All notifications have aria-live, high contrast, large tap targets
- **No spam:** Batching, quiet hours optional, user can mute category

---

### PART 12: SECURITY & PRIVACY

- Push endpoint is secret, never logged
- Patient access_key is 24-char random, not guessable, like boarding pass
- Personal TV shows first name + ticket code only, not full surname + hospital number (privacy)
- No clinical data in push payload — only "You are next, go to Room 3" — not diagnosis
- VAPID keys per deploy, not per tenant (standard)
- Push payload encrypted via Web Push protocol (p256dh)
- NDPA: patient can request erasure, we delete PushSubscription + PersonalTvSession

---

### PART 13: SUCCESS METRICS

- SMS/WhatsApp volume down 80%+ (measure via SmsMessage count)
- Push subscription rate: >60% staff, >30% patients
- Notification delivery <2 sec (push) vs 10-30 sec SMS
- Staff SLA breach down (because alerts work closed)
- Patient satisfaction up (personal TV reduces anxiety)
- App install rate optional, not forced — measure but not require

---

### PART 14: WHAT WE NEED FROM YOU TO BUILD

1. Approve this plan
2. Confirm: Keep patient no-install easy access? (We say YES, keep)
3. Confirm: SMS fallback allowed for critical only? (We propose YES)
4. VAPID keys: Generate via `python -m pywebpush --gen-keys` — we will add env
5. Test devices: Android Chrome + iPhone for alarm test

---

**End of Plan — Ready for your approval before build.**

If approved, we build v1.8.0 with world-class notification system that saves cost, works closed like alarm, and gives premium++++ experience.
