# Getting SMS and WhatsApp working — step by step

**GENERAL HOSPITAL IJEDE** · written for a non-technical founder

You do not need to touch any code. Everything here is done on three websites
and then typed into Render.

---

## Part 1 — Termii, for SMS (about 20 minutes)

Termii is a Nigerian company. Prices are in naira and their numbers work
properly with Nigerian networks, which is why it is the first choice.

### Step 1 — Create the account
1. Go to **https://accounts.termii.com/register**
2. Sign up with the hospital email (`info@ghijedestate.gov.ng`)
3. Confirm the email they send you
4. Sign in at **https://accounts.termii.com**

### Step 2 — Get your API key
1. On the left menu click **Settings** (or the ⚙ icon)
2. Click the **API** tab
3. You will see **API Key** — a long string of letters and numbers
4. Click **Copy**

> ⚠️ Treat this like a bank PIN. Anyone with it can send messages and spend
> your money. Never put it in a WhatsApp chat or an email.

### Step 3 — Register your Sender ID
This is the name patients see instead of a phone number.

1. Left menu → **Sender IDs** (sometimes under *Messaging*)
2. Click **Request Sender ID**
3. Fill in:
   - **Sender ID:** `GHIJEDE` (max 11 characters, no spaces)
   - **Usecase:** *"Appointment reminders and hospital notifications to patients
     of General Hospital Ijede, a Lagos State government hospital."*
   - **Company:** General Hospital Ijede
4. Submit

**Approval takes 1–3 working days.** Until it is approved you can still test —
Termii lets you send using their generic sender ID.

### Step 4 — Put money in
1. Left menu → **Top up** / **Wallet**
2. ₦5,000 is plenty to start (roughly ₦3–4 per SMS)

### Step 5 — Add it to Render
1. Go to **https://dashboard.render.com**
2. Click your **hospital-suite** service
3. Left menu → **Environment**
4. Click **Add Environment Variable** three times:

| Key | Value |
|---|---|
| `SMS_MODE` | `termii` |
| `TERMII_API_KEY` | *the key you copied in Step 2* |
| `TERMII_SENDER_ID` | `GHIJEDE` |

5. Click **Save Changes** — Render restarts automatically (2–3 minutes)

### Step 6 — Check it worked
Sign in to the app, book a test appointment with your own phone number. You
should get an SMS. If not, look at **Render → Logs** and search for `termii`.

---

## Part 2 — WhatsApp

You need **two** things set up. Meta is free but slow to approve; Twilio costs
a little but works the same day. **Set up Twilio first** so you are never stuck.

### Part 2A — Twilio, the fallback (about 30 minutes)

#### Step 1 — Create the account
1. Go to **https://www.twilio.com/try-twilio**
2. Sign up with the hospital email, verify your email and phone
3. When it asks what you are building, choose **WhatsApp** → **With code**

You get about **$15 free credit**, which is thousands of messages.

#### Step 2 — Get your Account SID and Auth Token
1. On the Twilio **Console** home page, scroll to **Account Info**
2. You will see:
   - **Account SID** — starts with `AC...`
   - **Auth Token** — click **Show** to reveal it
3. Copy both

#### Step 3 — Get a WhatsApp number

**The quick way (test immediately, today):**
1. Left menu → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Twilio shows a sandbox number, usually `+1 415 523 8886`, and a join code
   like `join happy-tiger`
3. On your own phone, WhatsApp that exact code to that number
4. You can now send to any phone that has joined the same way

> The sandbox is for testing only. Each person must send the join code first,
> so it is not usable for patients — but it proves everything works.

**The real way (for patients, takes a few days):**
1. Left menu → **Messaging** → **Senders** → **WhatsApp Senders**
2. Click **Create new sender**
3. Twilio walks you through connecting a phone number and verifying the
   hospital with Meta. **Use a number that is NOT already on WhatsApp** —
   a fresh SIM is easiest.
4. Business verification usually takes 2–5 working days

#### Step 4 — Add it to Render
Same place as before: **Environment** → **Add Environment Variable**

| Key | Value |
|---|---|
| `WHATSAPP_MODE` | `twilio` |
| `TWILIO_ACCOUNT_SID` | *your `AC...` SID* |
| `TWILIO_AUTH_TOKEN` | *your auth token* |
| `TWILIO_WHATSAPP_FROM` | `+14155238886` *(or your real number)* |

Save Changes and wait for the restart.

> **Note the `+`.** Write the number as `+2348012345678`, not `08012345678`.
> The app adds the `whatsapp:` part itself.

---

### Part 2B — Meta WhatsApp Cloud, the free primary (a few days)

Once this is approved it is **free** for the messages you send, so it becomes
the main route and Twilio sits behind it as the safety net.

#### Step 1 — Facebook Business account
1. Go to **https://business.facebook.com**
2. Create a business account for **General Hospital Ijede**
3. You will need: the hospital's official name, address, phone and website

#### Step 2 — Create the app
1. Go to **https://developers.facebook.com/apps**
2. **Create App** → choose **Business** → name it `Hospital Suite`
3. On the dashboard find **WhatsApp** → click **Set up**

#### Step 3 — Get your details
On the **WhatsApp → API Setup** page you will see:
- **Temporary access token** (expires in 24 hours — fine for testing)
- **Phone number ID** — a long number
- **WhatsApp Business Account ID**

Copy all three.

#### Step 4 — Get a permanent token
The temporary one dies overnight, so:
1. **business.facebook.com** → **Settings** → **Users** → **System Users**
2. **Add** → name it `hospital-suite` → role **Admin**
3. Click **Generate New Token** → select your app
4. Tick **whatsapp_business_messaging** and **whatsapp_business_management**
5. Copy the token — **it is shown only once**

#### Step 5 — Add it to Render

| Key | Value |
|---|---|
| `WHATSAPP_MODE` | `cloud` |
| `WHATSAPP_TOKEN` | *your permanent token* |
| `WHATSAPP_PHONE_ID` | *the phone number ID* |

Keep the Twilio values in place. **If Meta ever fails, the app sends through
Twilio automatically** — you do not have to do anything.

---

## What to check afterwards

| Check | Where |
|---|---|
| Messages actually sending | App → **Admin → Health** |
| Errors | Render → **Logs**, search `termii`, `twilio` or `whatsapp` |
| Money left | Termii wallet / Twilio console balance |

---

## Costs, honestly

| | Cost | Notes |
|---|---|---|
| **Termii SMS** | ~₦3–4 per message | Pay as you go |
| **Twilio WhatsApp** | ~$0.005–0.02 per message | $15 free to start |
| **Meta WhatsApp Cloud** | **Free** for your messages | Slow approval; worth the wait |

For 100 patients a day at one message each, budget roughly **₦10,000/month**
on SMS. WhatsApp on Meta Cloud is effectively free.

---

## Three mistakes to avoid

1. **Never paste a key into a chat window** — including to me. If one is
   exposed, go straight back to the website and regenerate it.
2. **Do not use a number already on WhatsApp** for the Twilio sender. It cannot
   be registered twice, and you may lose the number on your phone.
3. **Test with your own phone first.** Send yourself one message before you let
   the system send to a single patient.

---

## If it does not work

1. **Render → Logs** — the error is almost always there in plain English
2. Common ones:
   - `termii 401` → the API key is wrong or has a stray space
   - `Twilio error 63007` → the `From` number is not a WhatsApp sender
   - `Sender ID not approved` → still waiting on Termii; use their generic one
3. Send me the log line and I will tell you exactly what it means.
