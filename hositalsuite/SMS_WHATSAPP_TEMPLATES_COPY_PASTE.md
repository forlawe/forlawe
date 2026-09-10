# SMS & WhatsApp Templates — Copy & Paste Ready (Termii & Twilio)
Version: 1.7.21
Date: 2026-08-29

All templates are **ONE SMS** max 160 GSM chars, no emoji, no ₦, per-tenant tag.

---

## 1. Where are they in codebase?

- `app/sms_pack.py` — All SMS bodies (patient + staff), GSM cleaned, 160 max, DND channel
- `app/notifications.py:TEMPLATES` — Email/WhatsApp long versions
- `app/announce.py:phrase()` — Voice spoken versions
- `app/whatsapp.py` — WhatsApp send (text + document PDF)
- `app/views/twilio_diag.py` — Test SMS/WhatsApp buttons

---

## 2. Patient SMS Templates (Termii DND + Twilio SMS) — Copy & Paste

**Sender Tag**: Set via `sms_sender_tag` setting per hospital, or org code, e.g., `GHIJEDE` (3-11 chars, alphanumeric only, uppercase). Must be approved in Termii as Sender ID.

**Use DND channel for Termii** (transactional, not promo, works on MTN at night).

### Booking
```
GHIJEDE: Visit booked Mon 24 Aug at 09:00, OPD. Ref BK24082401. Come 15 min early. Call 08031234567
```
Code: `visit_booked(org, day=day, time="09:00", dept="OPD", ref="BK24082401")`

Fast Track Booking (premium):
```
GHIJEDE: Fast Track booked Mon 24 Aug 09:00. Ref FT24082401. Pay at Reception gold lane. Call 08031234567
```
Fast Track Paid:
```
GHIJEDE: Fast Track PAID. Ref FT24082401. Go to Reception gold lane on Mon 24 Aug at 09:00.
```

### Queue
Queue Number (after join):
```
GHIJEDE: Your number is E-014 at OPD. Keep this SMS. We will text you when it is your turn.
```
Queue Next (call):
```
GHIJEDE: You are next. Ticket E-014, OPD. Please walk to the desk now.
```

### Complaint
Received:
```
GHIJEDE received your complaint. Ref CP24082401. We are looking into it. Keep this number. Call 08031234567
```
Acknowledged:
```
GHIJEDE: We have seen your complaint CP24082401. Our team is working on it. Thank you.
```
Resolved:
```
GHIJEDE: Your complaint CP24082401 has been resolved. Thank you. Call 08031234567
```
Escalated:
```
GHIJEDE: Your complaint CP24082401 has gone to hospital management for urgent attention.
```

### Feedback / Thank You
```
GHIJEDE: Thank you for coming today. Please rate us: hospital-suite.onrender.com/feedback
```

### Sign-in Code (OTP)
```
GHIJEDE: Your sign-in code is 847291. It dies in 10 minutes. If you did not ask, ignore this.
```
Code: `signin_code(org, otp="847291", minutes=10)` — 6-digit code

### Cancellation
```
GHIJEDE: Your visit Ref BK24082401 on Mon 24 Aug at 09:00 is cancelled. Book again or call 08031234567
```

---

## 3. Staff SMS Templates (Termii DND + Twilio SMS) — Copy & Paste

These go to staff phones (Admin Manager on duty, HOD, MD/CEO).

Duty Reminder Day Before:
```
GHIJEDE: You are on duty TOMORROW Mon 28 Aug. Please prepare the daily walk-round.
```

Duty Today:
```
GHIJEDE: You are on duty TODAY Mon 28 Aug. Please finish today's walk-round.
```

Inspection Overdue:
```
GHIJEDE: Today's walk-round is late. Duty officer: Miss Okusanya. Please complete it now.
```

New Complaint for HOD:
```
GHIJEDE: New patient report CP20260801, Lab. Reply within 24 hrs. Open Complaints.
```

New Complaint for Admin Manager:
```
GHIJEDE: New patient report CP20260801, Lab. See Complaints on your phone.
```

Complaint Escalated to MD/CEO:
```
GHIJEDE: Report CP20260801 (Lab) missed its time and is now with you. Open Complaints.
```

SLA Warning (4 hrs left):
```
GHIJEDE: Report CP20260801 must be closed in 4 hrs or it goes to the MD. Open Complaints now.
```

Corrective Action Assigned:
```
GHIJEDE: A fix is assigned to you. Deadline Mon 28 Aug. Open Corrective Actions on your phone.
```

Overdue CA:
```
GHIJEDE: A fix is overdue (deadline Mon 28 Aug). Open Corrective Actions now.
```

Critical Inspection Score:
```
GHIJEDE ALERT: Walk-round INSP20260801 at Lab has a critical finding. Act now.
```

New Booking:
```
GHIJEDE: New visit booked. Ref BK20260801, OPD. See Bookings.
```

Inspection Submitted:
```
GHIJEDE: Walk-round INSP20260801 for Lab submitted. See Reports.
```

---

## 4. WhatsApp Templates (Twilio WhatsApp + Meta Cloud API) — Copy & Paste

WhatsApp can be longer (4000 chars), can include PDF document.

**Twilio WhatsApp FROM must be**: `whatsapp:+14155238886` (sandbox) or `whatsapp:+234...` approved.
**To must be**: `+2348012345678` normalized, code auto adds `whatsapp:` prefix.

### Test WhatsApp (for /admin/twilio-check)
```
Test WhatsApp from Hospital Suite — mode twilio — your Twilio is working! To: 08012345678
```

### Patient WhatsApp (same as SMS but can be longer, no 160 limit)
Booking:
```
GHIJEDE: Visit booked Mon 24 Aug at 09:00, OPD. Ref BK24082401. Come 15 min early. Call 08031234567

General Hospital Ijede
Address: ...
Phone: 08031234567
```
(For WhatsApp, you can add extra lines, location, map link)

Complaint:
```
GHIJEDE received your complaint. Ref CP24082401. We are looking into it. Keep this number.

You can check status at: https://hospital-suite.onrender.com/r/CP24082401?phone=YOUR_PHONE

Call 08031234567
```

### Staff WhatsApp (long version from notifications.py)

Duty Reminder:
```
Dear Miss Okusanya, you are scheduled as the Admin Manager on duty tomorrow (Mon 28 Aug) at General Hospital Ijede. Please prepare for your daily hospital inspection.
```

Inspection Submitted (with PDF):
```
Daily inspection report INSP20260801 for Laboratory has been submitted by Miss Okusanya. Overall rating: GOOD (20/25).

[PDF attached: reports/INSP20260801.pdf]
Verify at: https://hospital-suite.onrender.com/verify/ABC123
```

Complaint New:
```
A new patient complaint (CP20260801) concerning Laboratory (Equipment) requires your attention within 24 hours. Sign in to review and acknowledge.

Link: https://hospital-suite.onrender.com/complaints/CP20260801
```

Escalated:
```
Complaint CP20260801 (Laboratory) was not resolved within the SLA and has been escalated to the MD/CEO. Details are available in the system.
```

### Meta Cloud API Approved Template Example (if you use WHATSAPP_MODE=cloud)

You need to create template in Meta Business Manager → WhatsApp Manager → Message Templates.

**Template Name**: `inspection_report`
**Language**: en
**Category**: Utility
**Body**:
```
Daily Inspection Report
{{1}}
Ref: {{2}}
Dept: {{3}}
Date: {{4}}
By: {{5}}
Total: {{6}}/25 ({{7}}%)
Rating: {{8}}

Verify: {{9}}
```
Variables: {{1}}=hospital name, {{2}}=ref, {{3}}=dept, {{4}}=date, {{5}}=inspector, {{6}}=total, {{7}}=percent, {{8}}=rating, {{9}}=verify_url

**Template Name**: `complaint_received`
**Body**:
```
{{1}} received your complaint. Ref {{2}}. We are looking into it. Keep this number.

Check status: {{3}}
```

**Template Name**: `booking_confirmation`
**Body**:
```
{{1}}: Visit booked {{2}} at {{3}}, {{4}}. Ref {{5}}. Come 15 min early.

Call {{6}}
```

For Meta, you must submit template for approval (24 hrs). For Twilio WhatsApp sandbox, no approval needed for testing.

---

## 5. Termii Specific — How to Setup

Termii is Nigerian, cheaper than Twilio for Nigeria SMS, DND channel works on MTN at night.

**Steps:**
1. Go to https://accounts.termii.com → Sign up → Verify
2. Get API Key: Dashboard → API → API Key → Copy (starts with `TL...`)
3. Request Sender ID: Dashboard → Sender ID → Request Sender ID → e.g., `GHIJEDE` or `GeneralHosp` (3-11 chars, alphanumeric, must be approved, takes few hours)
4. In Render, set:
```
SMS_MODE=termii
TERMII_API_KEY=TLxxxxxxxxxxxxxxxxxxxx
TERMII_SENDER_ID=GHIJEDE
```
5. In code, `TermiiSmsProvider` uses:
```json
{
  "api_key": "TL...",
  "from": "GHIJEDE",
  "to": "+2348012345678",
  "sms": "GHIJEDE: Visit booked ...",
  "type": "plain",
  "channel": "dnd"
}
```
- `channel: dnd` = transactional (booking, codes, queue) — not blocked on MTN
- `channel: generic` = promo (would be blocked at night) — we never use generic

**Sample Termii Request (copy-paste for testing via curl):**
```bash
curl -X POST https://api.ng.termii.com/api/sms/send \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "TLyourkey",
    "from": "GHIJEDE",
    "to": "+2348012345678",
    "sms": "GHIJEDE: Your sign-in code is 847291. It dies in 10 minutes.",
    "type": "plain",
    "channel": "dnd"
  }'
```

---

## 6. Twilio Specific — How to Setup

**SMS:**
- Buy number: Twilio Console → Phone Numbers → Buy → US number e.g., +12125551234 (SMS-capable)
- Trial: Must verify recipient numbers in Verified Caller IDs
- From must be `+1...` not `whatsapp:+...`
- To must be `+234...` E.164

**Sample Twilio SMS Request (copy-paste):**
```bash
curl -X POST https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/Messages.json \
  -u ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx:your_auth_token \
  --data-urlencode "From=+12125551234" \
  --data-urlencode "To=+2348012345678" \
  --data-urlencode "Body=GHIJEDE: Your sign-in code is 847291. It dies in 10 minutes."
```

**WhatsApp Sandbox:**
- Twilio Console → Messaging → Try it out → WhatsApp sandbox → shows `whatsapp:+14155238886` + join code `join bright-hour`
- Recipient must send `join bright-hour` to +14155238886 on WhatsApp first
- From: `whatsapp:+14155238886`
- To: `whatsapp:+2348012345678`

**Sample Twilio WhatsApp Request:**
```bash
curl -X POST https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json \
  -u ACxxx:auth_token \
  --data-urlencode "From=whatsapp:+14155238886" \
  --data-urlencode "To=whatsapp:+2348012345678" \
  --data-urlencode "Body=GHIJEDE: Visit booked Mon 24 Aug at 09:00, OPD. Ref BK24082401. Come 15 min early."
```

---

## 7. How to Make It Accessible in App

- **Admin UI**: `/admin/twilio-check` (SUPER_ADMIN) → Shows masked config, ✅/❌ checks, recent 5 logs, Test SMS/WhatsApp buttons
- **Health**: `/api/v1/health` → JSON with `sms_mode`, `whatsapp_mode`, `twilio_sid_set`, `twilio_from_set`, `twilio_wa_from_set`
- **Logs**: `SmsMessage` and `WhatsAppMessage` tables → status QUEUED/SENT/FAILED, last_error shows exact Twilio/Termii error + hint
- **Templates**: This file `SMS_WHATSAPP_TEMPLATES_COPY_PASTE.md` + `app/sms_pack.py:samples()` + `app/templates/admin/twilio_check.html`

---

## 8. Copy-Paste ENV List (Final)

For **Twilio SMS + Twilio WhatsApp Sandbox** (testing):
```
SMS_MODE=twilio
WHATSAPP_MODE=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM=+14155238886
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

For **Termii (Nigeria cheap) + Twilio WhatsApp**:
```
SMS_MODE=termii
WHATSAPP_MODE=twilio
TERMII_API_KEY=TLxxxxxxxxxxxxxxxxxxxx
TERMII_SENDER_ID=GHIJEDE
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM=+12125551234
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

For **Production Meta Cloud API + Twilio fallback**:
```
SMS_MODE=twilio
WHATSAPP_MODE=cloud
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxx
WHATSAPP_VERIFY_TOKEN=your_verify_token
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM=+12125551234
TWILIO_WHATSAPP_FROM=whatsapp:+2348012345678
```

After setting, wait 2-3 min, check `/api/v1/health` → should be `twilio` not `sandbox`, and all `*_set: true`.

---

## 9. Voice Bank Note

Native voice bank is separate from SMS/WhatsApp — it's for TV screens and station announcements, not phone SMS.
- Phrase bank, not clone — real human recordings
- 16 voices 2M2F x 4 langs (en, yo, ha, ig)
- Wait for their pick — staff audition and pick
- See `NATIVE_VOICE_EXPERT_GUIDE.md` and `/admin/native-voice/`
