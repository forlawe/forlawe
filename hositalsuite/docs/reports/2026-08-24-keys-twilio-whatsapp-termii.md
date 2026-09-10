# How to switch on SMS and WhatsApp

Written for the founder. **No coding.** If you can copy a number and paste it, you can do this.

Think of the hospital app as a shop with **locked doors**.

| Door | What is behind it | Who holds the key |
|---|---|---|
| Practice door | Pretend messages. Safe. Nothing leaves the building. | Already open. You do nothing. |
| Text-message door | Real SMS to a phone | Termii (Nigeria). Twilio is the spare key. |
| WhatsApp door | Real WhatsApp | Facebook / Meta. Twilio is the spare key. |

A **key** is a long secret code. Treat it like an ATM PIN.

- Never send a key on WhatsApp.
- Never send a key to me.
- Never put a key in a photo.
- If anyone sees a key, go back to that website and make a new one.

---

## The hook where every key hangs

Every time this paper says **“put it on Render”**, do only this.

1. Open **https://dashboard.render.com** on your phone or computer.
2. Tap **hospital-suite**.
3. On the left, tap **Environment**.
4. Tap **Add Environment Variable**.
5. First box = the **name** (copy it exactly).
6. Second box = the **value** (paste what the other website gave you).
7. When all the new lines are in, tap **Save Changes**.
8. Wait **3 minutes**. Make tea. The shop is restarting.

If a name is already there, tap it and change the value. Do not add a second copy.

---

## What you should do, in this order

| Day | Do this | Why |
|---|---|---|
| Today | Leave practice on. Check the hospital phone in the app. | Safe. Patients already get the assistant. |
| This week | Termii SMS | Texts reach every Nigerian number, even a small phone. |
| Same week | Twilio account | Spare tyre. Works if Termii or WhatsApp fails. |
| Later | Twilio WhatsApp test on **your** phone only | Proves WhatsApp works. |
| Last | Facebook / Meta WhatsApp for real patients | Free, but they take days to approve. |

Do **not** start with Facebook. It is slow. The hospital can run without it.

---

# Part 0 — Practice (already on)

The shop is already in practice mode.

| Name on Render | Value to leave |
|---|---|
| `WHATSAPP_MODE` | `sandbox` |
| `SMS_MODE` | `sandbox` |

**What this means:** the app writes “I sent a message” in its own book. Nobody’s phone rings. Good for learning. Not good for real patients.

Also do this **inside the hospital app** (not Render):

1. Sign in.
2. Open **Admin → hospital details** (or Settings).
3. Put the **hospital desk phone**.
4. Save.

The assistant reads that number when it hands a person to a human.

---

# Part 1 — Termii (real SMS)

Termii is a Nigerian company. Prices are in naira. Messages reach MTN, Glo, Airtel and 9mobile.

### 1. Open the account

1. Go to **https://accounts.termii.com/register**
2. Use the **hospital email**, not a personal one.
3. Open the email they send. Tap the confirm link.
4. Sign in at **https://accounts.termii.com**

### 2. Copy the secret key

1. Left side → **Settings** (or the gear).
2. Open the **API** page.
3. You will see a long jumble. That is the key.
4. Tap **Copy**.
5. Paste it into a paper notebook or a locked notes app. Not WhatsApp.

### 3. Ask for the hospital name on the text

Patients should see **GHIJEDE**, not a random number.

1. Left side → **Sender IDs**.
2. Tap **Request Sender ID**.
3. Fill in:

| Box | What to type |
|---|---|
| Sender ID | `GHIJEDE` (11 letters max, no space) |
| Use | Appointment reminders and hospital notices for patients of General Hospital Ijede |
| Company | General Hospital Ijede |

4. Submit.

Wait **1–3 working days**. That is normal. You can still test before they say yes.

### 4. Put a little money in

1. Left side → **Wallet** or **Top up**.
2. Start with **₦5,000**.
3. One SMS is about **₦3–4**.

### 5. Hang the keys on Render

| Name | Value |
|---|---|
| `SMS_MODE` | `termii` |
| `TERMII_API_KEY` | the long jumble you copied |
| `TERMII_SENDER_ID` | `GHIJEDE` |

Save. Wait 3 minutes.

### 6. Test with **your** phone

1. Book a visit in the hospital app.
2. Use **your** number, not a patient’s.
3. You should get a text in about a minute.

| If this happens | Do this |
|---|---|
| No text | Wait 3 more minutes. Try again. |
| Still nothing | Render → **Logs**. Search `termii`. Copy the red line only. Send me the red line, not the key. |
| `401` | The key has a space or is wrong. Copy it again. |
| Sender ID not approved | Wait. Termii can still send with their own name. |

---

# Part 2 — Twilio (spare key)

Twilio is a foreign company. They cost a little, but they work the same day.

You need Twilio for two jobs later:

- spare **SMS** if Termii is down
- spare **WhatsApp** if Facebook is down

### 1. Open the account

1. Go to **https://www.twilio.com/try-twilio**
2. Sign up with the hospital email.
3. Confirm email and phone.
4. When they ask what you are building, pick **SMS** or **WhatsApp**. Either is fine.

They give about **$15 free**. That is many messages.

### 2. Copy two codes

On the Twilio home page, look for **Account Info**.

| What you see | Looks like | Name on Render |
|---|---|---|
| Account SID | starts with `AC` | `TWILIO_ACCOUNT_SID` |
| Auth Token | tap **Show** | `TWILIO_AUTH_TOKEN` |

Copy both. Same rule: not WhatsApp, not a photo.

### 3. Get a number for SMS (the spare text door)

1. Left side → **Phone Numbers** → **Buy a number** (or **Get a number**).
2. Pick one that can send SMS.
3. Copy it **with the plus**, like `+14155551234`.

Hang on Render:

| Name | Value |
|---|---|
| `TWILIO_ACCOUNT_SID` | the `AC…` code |
| `TWILIO_AUTH_TOKEN` | the hidden token |
| `TWILIO_FROM` | `+14155551234` (your Twilio SMS number) |

Leave `SMS_MODE` as `termii`. The app tries Termii first. Twilio is only the spare.

**Trial account rule:** Twilio will only text numbers you have verified. Add **your** phone under **Verified Caller IDs** before you test.

### 4. WhatsApp test on your phone only (not for patients)

1. Left side → **Messaging** → **Try it out** → **Send a WhatsApp message**.
2. Twilio shows a number, often `+1 415 523 8886`, and a join sentence like `join happy-tiger`.
3. On **your** WhatsApp, send that exact sentence to that number.
4. Twilio replies. You are now on the practice WhatsApp.

Hang on Render:

| Name | Value |
|---|---|
| `TWILIO_WHATSAPP_FROM` | `+14155238886` |

Then, **only when you want to test WhatsApp today**:

| Name | Value |
|---|---|
| `WHATSAPP_MODE` | `twilio` |

Save. Wait 3 minutes. Book a test visit with **your** number. You should get WhatsApp.

This practice WhatsApp **cannot** message patients until each person also sends the join sentence. So it is a classroom, not the real ward.

When you finish testing, you can put `WHATSAPP_MODE` back to `sandbox` until Facebook is ready.

### 5. Real Twilio WhatsApp for patients (later)

1. Buy a **new SIM** that is **not** already on WhatsApp.
2. Twilio → **Messaging** → **Senders** → **WhatsApp Senders** → **Create**.
3. Follow their steps. They talk to Facebook for you.
4. Wait 2–5 working days.
5. When they give you the new number, change `TWILIO_WHATSAPP_FROM` to that number **with the plus**.

Never register a number that is already on WhatsApp on your own phone. You can lose WhatsApp on that phone.

---

# Part 3 — Facebook / Meta WhatsApp (the free main door)

Do this **last**. It is free, but slow.

### 1. Make the hospital’s Facebook business

1. Go to **https://business.facebook.com**
2. Create a business. Name = **General Hospital Ijede**.
3. Use the hospital email.

### 2. Make the app

1. Go to **https://developers.facebook.com/apps**
2. **Create App** → **Business**.
3. Name it `Hospital Suite`.
4. Find **WhatsApp** → **Set up**.

### 3. Copy two numbers from **WhatsApp → API Setup**

| What you see | Name on Render |
|---|---|
| Phone number ID (long digits) | `WHATSAPP_PHONE_NUMBER_ID` |
| Access token (starts with `EAA`) | `WHATSAPP_ACCESS_TOKEN` |

The token on that page **dies in 24 hours**. Fine for a one-day test. For real hospital use you need a lasting token:

1. business.facebook.com → **Settings** → **Users** → **System Users**.
2. **Add** → name `hospital-suite` → role **Admin**.
3. **Generate New Token** → pick your app.
4. Tick **whatsapp_business_messaging** and **whatsapp_business_management**.
5. Copy it once. It will not be shown again.

### 4. The doorbell (webhook)

Facebook knocks on your shop to say “delivered” or “failed”.

1. WhatsApp → **Configuration** → **Webhook**.
2. Callback URL:

`https://hospital-suite.onrender.com/api/v1/whatsapp/webhook`

3. Verify token = invent a secret word, e.g. `ijede-desk-7`. Remember it.
4. Tick **messages**.

Hang on Render:

| Name | Value |
|---|---|
| `WHATSAPP_MODE` | `cloud` |
| `WHATSAPP_PHONE_NUMBER_ID` | the long digits |
| `WHATSAPP_ACCESS_TOKEN` | the `EAA…` token |
| `WHATSAPP_VERIFY_TOKEN` | the same secret word you typed in Facebook |

**The shop must be awake** when Facebook checks the doorbell. Open https://hospital-suite.onrender.com first, then tap Verify.

Keep all Twilio lines in place. If Facebook fails, the app tries Twilio by itself.

### 5. Message templates (for live patients)

Facebook will not let you send any words you like to a patient who has not written first. You must ask them to approve a few hospital sentences (Utility, not adverts). Do this after the number is live. Ask me then and I will write the exact sentences.

---

# Other switches (only these)

These already belong on Render. Do **not** invent extra names.

| Name | What it is | What you should have |
|---|---|---|
| `PUBLIC_BASE_URL` | The shop’s public address | `https://hospital-suite.onrender.com` |
| `TIMEZONE` | The clock | `Africa/Lagos` |
| `SECRET_KEY` | The shop’s own lock | Leave the one Render made. Do not change it. |
| `DATABASE_URL` | Where folders live | Leave it. Do not touch. |
| `STORAGE_BACKEND` | Where photos live | `db` |
| `SMS_MODE` | Which SMS door | `sandbox` now, then `termii` |
| `WHATSAPP_MODE` | Which WhatsApp door | `sandbox` now, then `twilio` to test, then `cloud` when Facebook is ready |

**Do not add** `GROQ_MODEL`.  
**Do not add** `WHATSAPP_TOKEN` or `WHATSAPP_PHONE_ID` — those old names are wrong. Use the names in the tables above.

Email (`SMTP_…`) can wait. USSD can wait.

---

# The finished picture

```
Patient books a visit
        ↓
App tries WhatsApp first
        ↓
  Works?  →  patient sees WhatsApp. Done.
        ↓  fails
Twilio WhatsApp (if you set it)
        ↓  fails
Termii SMS  (Nigeria, cheap)
        ↓  fails
Twilio SMS  (spare)
        ↓
Somebody still hears. The visit is not lost.
```

---

# Tick list (print this)

**Safe first**
- [ ] Render still has `WHATSAPP_MODE=sandbox` until I am ready
- [ ] Hospital desk phone saved inside the app
- [ ] I will only test with **my** phone

**SMS this week**
- [ ] Termii account
- [ ] Sender ID `GHIJEDE` requested
- [ ] ₦5,000 in the wallet
- [ ] `SMS_MODE`, `TERMII_API_KEY`, `TERMII_SENDER_ID` on Render
- [ ] Test SMS arrived on my phone

**Spare key**
- [ ] Twilio account
- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` on Render
- [ ] My phone added as a verified number on Twilio

**WhatsApp later**
- [ ] I joined the Twilio practice WhatsApp from **my** phone
- [ ] `TWILIO_WHATSAPP_FROM` on Render
- [ ] Facebook business + lasting token (when I am ready)
- [ ] Doorbell URL saved, same verify word on Render

**Never**
- [ ] I did not send any key in a chat
- [ ] I revoked old GitHub tokens after a push

---

# Money, honestly

| Door | Cost | Notes |
|---|---|---|
| Practice | ₦0 | Already on |
| Termii SMS | about ₦3–4 each | Pay as you go |
| Twilio SMS | a few naira each | $15 free to start |
| Twilio WhatsApp practice | ₦0 | Your phone only |
| Facebook WhatsApp | free for your own messages, then a small fee | Slow to approve |

For about 100 texts a day, budget roughly **₦10,000 a month** on SMS. WhatsApp is cheaper once Facebook says yes.

---

# Three mistakes that break the shop

1. Pasting a key into WhatsApp or a photo.
2. Using a phone number that is **already** on WhatsApp as the hospital sender.
3. Adding extra names that are not in this paper.

---

# If you get stuck

1. Open the hospital site first (wake it up).
2. Render → **Logs**.
3. Search `termii` or `twilio` or `whatsapp`.
4. Send me **only the red line**. Never the key.

That is the whole blueprint. One door at a time. Start with Termii this week.
