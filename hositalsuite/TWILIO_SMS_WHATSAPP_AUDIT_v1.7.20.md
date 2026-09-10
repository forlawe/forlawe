# Twilio SMS & WhatsApp Deep Audit — v1.7.20
Date: 2026-08-28
Version: 1.7.20
Issue: WhatsApp and SMS not sending to user despite env vars set (similar to Brevo fix)

## Current Live State (before fix)
- https://hospital-suite.onrender.com/api/v1/health → `{"whatsapp_mode":"sandbox","mail":"brevo"}`
- Means WHATSAPP_MODE still sandbox, not twilio → no real WhatsApp
- SMS_MODE likely also sandbox (not shown before, now added to health)
- Brevo fixed earlier: mail=brevo OK

## Root Causes Found (deep codebase review)

### 1. Mode Ignored — Provider Selection Bug
**File**: `app/sms.py:get_provider()` and `send_sms()`
- Before: Always tried Termii first even when SMS_MODE=twilio, ignoring user intent. If TERMII_API_KEY empty or invalid, fell through to Twilio, but if TERMII key present and invalid, Twilio fallback happened only after Termii failure. If both missing, returned SandboxSmsProvider which returns fake ID `SBX-SMS-...` and marks SENT, so UI says sent but phone gets nothing.
- Impact: User sets SMS_MODE=twilio + TWILIO creds, but if TERMII_API_KEY accidentally set (even empty string handling) or code path, sandbox wins.
- Fix v1.7.20: Strict mode respect:
  - `disabled` → None
  - `twilio` → Twilio only (no Termii)
  - `termii` → Termii only
  - `sandbox` → sandbox
  - legacy empty → Termii → Twilio → sandbox

### 2. Nigerian Number Format — 080... vs +234...
**Files**: `app/sms.py`, `app/whatsapp.py`, `app/views/bookings.py`, `app/views/queue.py`, `app/models.py` phone fields
- Before: Queueing used raw phone `08012345678` from Appointment/QueueTicket. Twilio API requires E.164 `+2348012345678`. Sending 080... → Twilio error 21211 "not a valid phone number" → marked FAILED after 3 attempts, user sees no SMS.
- Common mistake: `+234080...` (extra 0) also invalid.
- Fix: New `normalize_ng_number()` in both sms.py and whatsapp.py:
  - `08012345678` → `+2348012345678`
  - `080 1234 5678` → `+2348012345678`
  - `+23408012345678` → `+2348012345678` (strip extra 0)
  - `2348012345678` → `+2348012345678`
  - `8012345678` → `+2348012345678`
  - Applied in `queue_sms()`, `send_sms()`, `queue_message()`, `send_message()`, `_send_twilio()` before every API call.

### 3. WhatsApp FROM Format Wrong
**File**: `app/whatsapp.py:_send_twilio()`, `app/config.py`
- Before: `TWILIO_WHATSAPP_FROM` must be `whatsapp:+14155238886` (with prefix). If user set `+14155238886` without `whatsapp:` prefix, Twilio error. If set `TWILIO_FROM=+1415...` for SMS and left `TWILIO_WHATSAPP_FROM` empty, fallback used SMS number without whatsapp: prefix → fails.
- Fix: `ensure_whatsapp_prefix()` auto-adds `whatsapp:` and normalizes inner number. Validates and raises clear error if still wrong: "TWILIO_WHATSAPP_FROM must start with whatsapp: — got X. Example: whatsapp:+14155238886"

### 4. SMS FROM Format Wrong
**File**: `app/sms.py:TwilioSmsProvider`
- Before: No validation. If user set `TWILIO_FROM=whatsapp:+1415...` (WhatsApp number) for SMS, Twilio SMS fails.
- Fix: Raise error if FROM starts with `whatsapp:` for SMS, with message "TWILIO_FROM for SMS must NOT start with whatsapp: — Use +... number for SMS, TWILIO_WHATSAPP_FROM for WhatsApp"

### 5. Trial Account — Verified Numbers Only
- Twilio trial accounts can only send to verified numbers (Console → Verified Caller IDs). If recipient not verified → error 21608.
- Fix: Error messages now include hint: "Trial account: verify recipient number in Twilio console > Phone Numbers > Verified Caller IDs" and "WhatsApp sandbox: recipient must send 'join <code>' to your Twilio WhatsApp number first."

### 6. WhatsApp Sandbox Join Required
- Twilio WhatsApp sandbox requires recipient to first send `join <code>` (e.g., `join bright-hour`) to Twilio sandbox number `+14155238886` on WhatsApp. Without join, every message fails with 63016 or similar.
- Fix: Added info checks in `twilio_diag.py` and error hints in `_send_twilio()`.

### 7. Silent Sandbox Success — Fake SENT
- Sandbox provider returns fake ID and marks SENT, so logs show SENT but no real delivery. If user sets TWILIO creds but leaves SMS_MODE=sandbox, they see SENT but phone gets nothing.
- Fix: Strict mode — if SMS_MODE=twilio but creds missing, still try Twilio provider which will error clearly, then fallback to sandbox only after error logged. Health endpoint now shows `sms_mode` and `twilio_*_set` booleans so founder can see config without exposing secrets.

### 8. Dispatch Delivery — Background Thread
**File**: `app/tasks.py`
- Uses daemon thread. On Render with gunicorn multiple workers, thread may die if worker restarts. Already has SYNC_DELIVERY_FOR_TESTS for tests. Added more logging and fallback: WhatsApp failure now immediately queues SMS fallback in `send_message()` except block, not just via webhook.

### 9. Health Endpoint Missing SMS_MODE
- Before: `/api/v1/health` only showed `whatsapp_mode`, not `sms_mode` or whether Twilio vars set.
- Fix: Now returns `sms_mode`, `twilio_sid_set`, `twilio_from_set`, `twilio_wa_from_set` booleans.

## Code Changes v1.7.20

### app/sms.py
- Added `normalize_ng_number()` — handles 080, +2340, 234, 10-digit
- `get_provider()` now respects SMS_MODE strictly
- `queue_sms()` normalizes to_number before queuing
- `send_sms()` normalizes, respects mode, builds provider list strictly, adds hints for trial, invalid number, permission errors
- `TwilioSmsProvider.send()` validates FROM not whatsapp:, normalizes To, adds hints

### app/whatsapp.py
- Added `normalize_ng_number()` and `ensure_whatsapp_prefix()`
- `mode()` lowercases
- `queue_message()` normalizes
- `_send_twilio()` validates FROM must start whatsapp:, auto-fixes +... to whatsapp:+..., normalizes To, adds hints for unverified, join, invalid number
- `send_message()` normalizes before sending, adds immediate SMS fallback on failure: `sms_engine.queue_sms(..., kind=..._fallback)`

### app/views/api.py
- Health now includes sms_mode and twilio_*_set booleans

### app/config.py / app/__init__.py
- Version bump 1.7.19 → 1.7.20

## How to Fix on Render (Step by Step)

### For Real SMS via Twilio
1. Twilio Console → https://console.twilio.com → Account SID (AC...) + Auth Token
2. Phone Numbers → Buy a number → US number with SMS capability (e.g., +1415...)
3. If trial account: Phone Numbers → Verified Caller IDs → Add your Nigerian number +2348012345678 (must verify via call/SMS)
4. Render Dashboard → hospital-suite → Environment → Add:
   ```
   SMS_MODE=twilio
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_FROM=+1415xxxxxxx  (your Twilio SMS number, NOT whatsapp: prefix)
   ```
5. Save → Wait 2-3 min for restart → Check https://hospital-suite.onrender.com/api/v1/health → should show sms_mode=twilio, twilio_sid_set=true, twilio_from_set=true
6. Test: Login as SUPER_ADMIN → /admin/twilio-check → Test SMS to +2348012345678 (your verified number)

### For Real WhatsApp via Twilio (Sandbox for testing)
1. Twilio Console → Messaging → Try it out → WhatsApp sandbox → Note number `whatsapp:+14155238886` and join code e.g., `join bright-hour`
2. On your phone WhatsApp, send message `join bright-hour` to +14155238886 (you must do this, otherwise sandbox blocks)
3. Render Environment → Add:
   ```
   WHATSAPP_MODE=twilio
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
   Keep SID, TOKEN, FROM from SMS step
4. Save → Wait → Test WhatsApp in /admin/twilio-check
5. For production WhatsApp (not sandbox): Twilio Console → Messaging → WhatsApp senders → Request approval for your own number (takes 1-2 days, needs Facebook Business verification). Then set TWILIO_WHATSAPP_FROM=whatsapp:+234... your approved number

### For Production WhatsApp via Meta Cloud API (cheaper, recommended long-term)
1. Meta Developers → https://developers.facebook.com → Create App → WhatsApp → Get Phone Number ID + Access Token
2. Render:
   ```
   WHATSAPP_MODE=cloud
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_ACCESS_TOKEN=...
   ```
   Keep Twilio as fallback: if cloud fails, code auto-falls back to Twilio WhatsApp if TWILIO creds present
3. Webhook: Set in Meta dashboard to https://hospital-suite.onrender.com/api/v1/whatsapp/webhook + verify token WHATSAPP_VERIFY_TOKEN

### Common Nigeria Mistakes Checklist
- [ ] 080... instead of +234... → Fixed by normalize, but still use +234 in forms
- [ ] +234080... (extra 0) → Fixed
- [ ] Trial account not verified → Verify in Twilio console
- [ ] WhatsApp sandbox not joined → Send join <code> first
- [ ] FROM format: SMS FROM = +1415..., WhatsApp FROM = whatsapp:+1415... → Don't mix
- [ ] SMS_MODE still sandbox → Must set to twilio
- [ ] WHATSAPP_MODE still sandbox → Must set to twilio or cloud
- [ ] Sender ID not approved → Use +... number, not alphanumeric for testing

## Testing

### Local (with .venv)
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Set env vars in .env or export
export SMS_MODE=twilio
export TWILIO_ACCOUNT_SID=AC...
export TWILIO_AUTH_TOKEN=...
export TWILIO_FROM=+1415...
export WHATSAPP_MODE=twilio
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
python3 -c "from app import create_app; app=create_app(); print(app.config['SMS_MODE'], app.config['WHATSAPP_MODE'])"
# Then use /admin/twilio-check test buttons
```

### Live
- After deploy, /api/v1/health should show:
  `{"sms_mode":"twilio","whatsapp_mode":"twilio","twilio_sid_set":true,...}`
  Currently shows sandbox → means env vars not set correctly in Render or not yet deployed
- /admin/twilio-check (SUPER_ADMIN only) shows masked values + checks + recent 5 SMS/WhatsApp logs with status and error

## Why Brevo Fix Worked but Twilio Didn't (Comparison)
- Brevo: Fixed by setting BREVO_API_KEY + MAIL_FROM, and mailer.py now uses Brevo API not SMTP (Render blocks SMTP). Health shows mail=brevo OK.
- Twilio: Needs TWO modes set (SMS_MODE and WHATSAPP_MODE) + FOUR vars (SID, TOKEN, FROM, WA_FROM) + number normalization + trial verification + WhatsApp sandbox join. More steps, easier to miss one.

## Next Steps
1. Deploy v1.7.20 to Render (needs push)
2. Set env vars in Render Dashboard exactly as above
3. Verify recipient number in Twilio console if trial
4. Join WhatsApp sandbox
5. Test via /admin/twilio-check → should see SENT via twilio
6. If still fails, check recent logs in /admin/twilio-check → last_error shows exact Twilio error + hint

## Voice Bank Reminder
- Native voice bank: wait for their pick, phrase bank not clone

## Pending Menu
1. Push v1.7.20
2. Set Render env vars per above, verify
3. Test SMS/WhatsApp to real phone
4. Consider Termii for cheaper Nigeria SMS (accounts.termii.com)
