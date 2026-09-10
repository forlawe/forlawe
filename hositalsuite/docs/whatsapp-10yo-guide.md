# WhatsApp First, Twilio Fallback — Setup Guide for a 10-Year-Old Founder

> If you can use Facebook, you can do this. No coding. Just click, copy, paste.

---

## What You Are Building

| What | Means |
|------|-------|
| WhatsApp Business | Your hospital sends messages on WhatsApp — booking confirmation, complaint update, SLA alert |
| WhatsApp First | System tries WhatsApp first — it's free and everyone in Lagos uses it |
| Twilio Fallback | If WhatsApp fails (blocked, not approved, internet down), Twilio sends same message as SMS |
| Voice Reminder | Every important alert also speaks out loud on the staff's phone/computer |

---

## Big Picture — 3 Steps

| Step | What You Do | Time |
|------|-------------|------|
| 1 | Create Meta Business Manager + WhatsApp Business account | 15 min |
| 2 | Get phone number + access token + webhook | 15 min |
| 3 | Put keys in Render + test on your Android phone | 10 min |

---

## STEP 1: Meta Business Manager (Your Hospital's Facebook Business)

Think of this as "Facebook for your hospital company".

| # | Click | What to type |
|---|-------|--------------|
| 1 | Go to https://business.facebook.com |  |
| 2 | Click Create Business | Business name = your hospital name, e.g. "General Hospital Ijede" |
| 3 | Enter your email | Use your hospital email, not personal |
| 4 | Click Submit | You now have Business Manager |

**Why needed:** Meta only lets businesses send WhatsApp. Not personal accounts.

---

## STEP 2: WhatsApp Business Platform

| # | Click | What to type |
|---|-------|--------------|
| 1 | Go to https://developers.facebook.com | Log in with same Facebook that owns Business Manager |
| 2 | My Apps → Create App → Business → Next | App name = "Hospital WhatsApp", contact email = yours |
| 3 | Add Product → WhatsApp → Set Up |  |
| 4 | In left menu: WhatsApp → API Setup | You will see a test phone number + test token |
| 5 | Add your own phone number: WhatsApp → Phone Numbers → Add Phone Number | Enter hospital WhatsApp number (must be able to receive SMS call) |
| 6 | Verify number | Meta will call/SMS you a code — enter it |

You now have:
- Phone Number ID (looks like 123456789012345)
- WhatsApp Business Account ID

---

## STEP 3: Access Token (The Key That Lets Your App Send Messages)

| Type | What It Is | When to Use |
|------|------------|-------------|
| Temporary token | Lasts 24 hours, shown in API Setup page | Only for testing today |
| Permanent token | Lasts forever until you delete it | For live hospital use |

**To get permanent token:**

| # | Click |
|---|-------|
| 1 | Business Settings → Users → System Users → Add → Admin |
| 2 | Assign Assets → Apps → Your App → Full Control |
| 3 | Generate New Token → Select App → Permissions: whatsapp_business_messaging, whatsapp_business_management |
| 4 | Copy token — starts with EAA... — save it safe, you see it only once |

---

## STEP 4: Webhook (So You Know If Message Was Delivered or Failed)

Webhook = Meta tells your hospital app "message delivered" or "message failed".

| # | Click | What to type |
|---|-------|--------------|
| 1 | WhatsApp → Configuration → Webhook → Edit | Callback URL = https://YOUR-APP.onrender.com/api/v1/whatsapp/webhook |
| 2 | Verify Token | Type any secret word, e.g. hospital123verify — remember it, you put same in Render |
| 3 | Subscribe to messages, message_status | Tick both |

**If Meta says "verification failed":** Your Render app must be live first. Deploy, then try again.

---

## STEP 5: Message Templates (Meta Requires Pre-Approved Messages)

You cannot send any random text on WhatsApp Business unless user messaged you first. For hospital alerts, you need templates.

| Template | Example Text | Category |
|----------|--------------|----------|
| booking_confirmation | Your visit at {{1}} is booked for {{2}} at {{3}}. Ref: {{4}}. Fast Track {{5}} — {{6}} | Utility |
| complaint_update | {{1}}: Your complaint {{2}} update: {{3}} | Utility |
| sla_alert | Complaint {{1}} for {{2}} needs action in {{3}} hours | Utility |
| fast_track_payment | Fast Track booking {{1}} — Price {{2}} {{3}}. Building {{4}}. Pay before arrival | Utility |

| # | Click |
|---|-------|
| 1 | WhatsApp → Message Templates → Create Template |
| 2 | Name lowercase no spaces, e.g. booking_confirmation |
| 3 | Category Utility, Language English |
| 4 | Body = your message with {{1}} {{2}} placeholders |
| 5 | Submit → Wait 5 min to 2 hours for approval |

**Sandbox vs Live:**
- Sandbox = test mode, only you and 5 numbers you add can receive. Templates auto-approved. Good for testing today.
- Live = real patients receive. Needs business verification (upload CAC certificate). Takes 1-3 days.

---

## STEP 6: Render Environment Variables — Where You Paste Keys

Go to Render Dashboard → Your Service → Environment

| Variable | Where to Get | Example | What It Does |
|----------|--------------|---------|--------------|
| WHATSAPP_MODE | You type | cloud | cloud = Meta API, twilio = Twilio WhatsApp, sandbox = test, disabled = off |
| WHATSAPP_PHONE_NUMBER_ID | API Setup page | 123456789012345 | Your WhatsApp number ID |
| WHATSAPP_ACCESS_TOKEN | System User token | EAAK... | Key to send messages |
| WHATSAPP_VERIFY_TOKEN | You invented in webhook step | hospital123verify | Proves webhook is yours |
| WHATSAPP_FROM | Your WhatsApp number | +2348012345678 | Your hospital WhatsApp number |
| WHATSAPP_APP_SECRET | App Dashboard → App Secret | abc123... | Security, optional |
| SMS_MODE | You type | twilio | twilio = Twilio SMS fallback, termii = Nigerian SMS, sandbox = test |
| TWILIO_ACCOUNT_SID | Twilio Console | AC... | Twilio account ID |
| TWILIO_AUTH_TOKEN | Twilio Console | 123... | Twilio secret |
| TWILIO_FROM | Twilio Console → Phone Numbers | +1234567890 | Your Twilio SMS number |
| TWILIO_WHATSAPP_FROM | Twilio Console | whatsapp:+14155238886 | Twilio WhatsApp sandbox or approved number |

**Important for you (from screenshot):**
You have 3 TWILIO vars set. You need 4th: TWILIO_WHATSAPP_FROM. Also set SMS_MODE=twilio and WHATSAPP_MODE=cloud (or twilio if you want Twilio for WhatsApp too).

| Setting | Value to Use Now (Testing) | Value for Live Hospital |
|---------|----------------------------|-------------------------|
| WHATSAPP_MODE | sandbox | cloud |
| SMS_MODE | twilio | twilio |
| TWILIO_WHATSAPP_FROM | whatsapp:+14155238886 (Twilio sandbox) | whatsapp:+234... your approved number |

---

## STEP 7: Test on Your Android Phone

| # | Do This | What Should Happen |
|---|---------|-------------------|
| 1 | On Render, set WHATSAPP_MODE=sandbox, SMS_MODE=sandbox |  |
| 2 | Go to your hospital app /book → Book a Fast Track appointment with your phone number |  |
| 3 | Check /admin/whatsapp (or AppNotification page) | Message status QUEUED → SENT → DELIVERED |
| 4 | Set WHATSAPP_MODE=twilio, add Twilio keys, send test booking | You get WhatsApp message on your phone |
| 5 | Turn off internet for WhatsApp number, book again | System auto-falls back to SMS — you still get SMS via Twilio |

**Sandbox join:** If using Twilio WhatsApp sandbox, you must first send "join <your-code>" from your phone to Twilio's sandbox number. Code shown in Twilio Console → Messaging → Try it out → WhatsApp sandbox.

---

## How WhatsApp-First + Twilio Fallback Works (Plain English)

```
Patient books Fast Track
        ↓
System queues WhatsApp message first (free, rich)
        ↓
Try send via Meta Cloud API
        ↓
    Success? → Patient gets WhatsApp → Done
        ↓ Failed
Try Twilio WhatsApp
        ↓
    Success? → Patient gets WhatsApp via Twilio → Done
        ↓ Failed
Send SMS via Twilio (costs small money but always works)
        ↓
Patient gets SMS — never misses booking confirmation
```

Every complaint SLA breach also does:

```
SLA about to breach (4 hours left)
        ↓
WhatsApp to HOD: "Complaint ABC running out"
        ↓
Voice announcement on HOD's browser: speaks out loud
        ↓
If HOD no act and SLA breaches
        ↓
WhatsApp + Voice to MD/CEO: "Complaint escalated — immediate action"
        ↓
If WhatsApp fails → Twilio SMS to MD/CEO
```

---

## Cost — Zero Budget Friendly

| Service | Cost |
|---------|------|
| Meta WhatsApp Cloud API | Free for first 1000 conversations/month, then ~$0.02 per conversation (Nigeria) |
| Twilio WhatsApp sandbox | Free for testing |
| Twilio SMS Nigeria | ~$0.05 per SMS |
| Twilio WhatsApp live | ~$0.01 per message + WhatsApp fee |
| Browser voice (Web Speech API) | Free forever — uses phone's own speaker |

**For your hospital starting:** Use sandbox for 2 weeks, then apply for Meta live + keep Twilio as fallback. Monthly cost under ₦5,000 for 500 patients if you use WhatsApp mostly.

---

## Troubleshooting — Common Problems

| Problem | Cause | Fix |
|---------|-------|-----|
| "WhatsApp disabled" in logs | WHATSAPP_MODE=disabled or not set | Set WHATSAPP_MODE=cloud or sandbox in Render |
| Message stays QUEUED | Scheduler not running | Check Render logs for "hms-scheduler" — should tick every 30 sec |
| Twilio error 21211 | Invalid phone format | Phone must be +234... not 080... — system adds + automatically but check |
| Twilio error 21608 | Number not verified (trial account) | Twilio Console → Verified Caller IDs → Add your number |
| Meta webhook verification fails | Render app sleeping | Render free sleeps — open your app URL first to wake it, then verify |
| Template not approved | Text sounds like marketing | Use Utility category, no "buy now", keep formal hospital language |
| Voice not speaking | Browser blocked autoplay | Staff must click "Enable Voice" button once — then voice works |

---

## What You Have Now — Features Live

| Feature | What It Does | Where to See |
|---------|--------------|--------------|
| Fast Track Building Billing | Premium price per tenant, show on Reception/FastTrack desk/booking | Settings → Fast Track, Booking page, Reception desk |
| Fast Track Booking Payment Upfront | Patient pays before arrival, staff marks PAID, gate at check-in | /bookings → Mark PAID button, /book → price shown |
| TV per-screen Fast Track filter | Executive TV shows only gold lane, regular TV shows regular first | /admin/tv → ⭐ FAST ONLY toggle, /tv/FASTTRACK |
| Role Scope Audit | HOD sees only own dept, violation logged as SCOPE_BLOCKED | /complaints?dept= — try access other dept → 403 + audit |
| Complaints SLA WhatsApp Voice | SLA breach → WhatsApp + voice to HOD + MD/CEO | Complaints → watch for warning voice + WhatsApp |

All per-tenant, premium++, no crash, voice kept.

---

## Quick Start — Do This Today (10 minutes)

1. Render → Environment → Add WHATSAPP_MODE=sandbox, SMS_MODE=sandbox → Save (auto redeploys)
2. Book a test appointment with your phone → Check it shows ⭐ Fast Track price
3. Go to /admin/tv → Add TV → Code FASTTRACK, check ⭐ FAST ONLY + Executive → Save → Open /tv/FASTTRACK → Should show gold only
4. Go to /bookings → Find your booking → Click Mark PAID → Check in → Should allow
5. Go to /complaints → Open a complaint → Leave it 4 hours (or set SLA to 1 hour in Settings for test) → You should get WhatsApp + voice warning

Done. Your hospital now has WhatsApp-first premium Fast Track.
