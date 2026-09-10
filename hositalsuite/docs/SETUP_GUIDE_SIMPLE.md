# Switching on AI, SMS and WhatsApp — the simple guide

**GENERAL HOSPITAL IJEDE** · 19 August 2026

---

## First, the idea in one picture

Your app is like a **shop with three locked doors**:

| Door | What is behind it |
|---|---|
| 🤖 **AI** | A clever helper that answers patients' questions |
| 📱 **SMS** | Sending text messages to patients' phones |
| 💬 **WhatsApp** | Sending reports and messages on WhatsApp |

Each door has its own **key**. You get the keys from three websites, then you
hang the keys on a hook inside Render so the app can use them.

**You will not write any code.** You are copying keys and pasting them.

---

## Where you will hang every key (learn this once)

Every single time this guide says *"add this to Render"*, you do this:

1. Open **https://dashboard.render.com**
2. Click **hospital-suite**
3. On the left, click **Environment**
4. Click **Add Environment Variable**
5. Type the **Key** in the first box, the **Value** in the second box
6. When you have added all of them, click **Save Changes**

Render then restarts your app. **It takes 2–3 minutes.** Go and make tea.

> 🔑 **A key is like your ATM PIN.** Never send one in WhatsApp, never send one
> to me, never put one in a photo. If a key ever gets seen by someone else, go
> back to that website and make a new one.

---

# 🤖 PART 1 — The AI helper (10 minutes, free)

This is the **easiest one** and it makes the biggest difference today. Start here.

### Step 1 — Make the account
1. Go to **https://console.groq.com**
2. Click **Sign up**
3. Use your hospital email, then confirm the email they send you

*(It is called **Groq** with a **Q**. Not Grok with a K — that's a different
company.)*

### Step 2 — Make the key
1. Once you are signed in, look on the left for **API Keys**
2. Click **Create API Key**
3. Name it `hospital-suite`
4. Click **Submit**
5. A long code appears starting with `gsk_...`
6. Click **Copy**

> ⚠️ **Copy it now.** Groq shows it **only once**. If you close the window you
> cannot see it again — you just make a new one.

### Step 3 — Hang the key in Render

Add **one** setting (using the 6 steps above):

| Key | Value |
|---|---|
| `GROQ_API_KEY` | *paste the `gsk_...` code* |

**That is all.** Save Changes.

> ❌ **Do NOT add `GROQ_MODEL`.** I know it sounds helpful, but the correct
> model name is already inside the app. If you add it by hand you will
> **overwrite my fix and break the assistant again.** Just leave it alone.

### Step 4 — Check it worked
1. Wait 3 minutes
2. Open **https://hospital-suite.onrender.com/chat**
3. Ask something unusual, like: *"which bus from Ikorodu stops at your gate?"*
4. **Before:** it said *"I don't have an answer for that."*
   **Now:** you should get a proper, helpful reply.

**Cost: ₦0.** Groq is free.

---

# 📱 PART 2 — Termii, for text messages (20 minutes)

Termii is a **Nigerian** company. Prices are in naira and their messages
actually arrive on MTN, Glo, Airtel and 9mobile. That is why we use them.

### Step 1 — Make the account
1. Go to **https://accounts.termii.com/register**
2. Sign up with the hospital email (`info@ghijedestate.gov.ng`)
3. Confirm the email, then sign in

### Step 2 — Get the key
1. On the left, click **Settings** (or the ⚙ picture)
2. Click the **API** tab
3. You will see **API Key** — a long jumble of letters and numbers
4. Click **Copy**

### Step 3 — Ask for your hospital name
This is the name patients see instead of a strange phone number.

1. On the left, find **Sender IDs**
2. Click **Request Sender ID**
3. Fill in:
   - **Sender ID:** `GHIJEDE` *(11 letters maximum, no spaces)*
   - **Use case:** *"Appointment reminders and hospital notifications for
     patients of General Hospital Ijede, a Lagos State government hospital."*
4. Click submit

⏳ **Termii takes 1–3 working days to approve this.** That is normal. You can
carry on and test in the meantime.

### Step 4 — Put money in
1. On the left, click **Top up** or **Wallet**
2. **₦5,000 is plenty to start.** Each message costs about ₦3–4.

### Step 5 — Hang the keys in Render

Add **three** settings:

| Key | Value |
|---|---|
| `SMS_MODE` | `termii` |
| `TERMII_API_KEY` | *paste the key from Step 2* |
| `TERMII_SENDER_ID` | `GHIJEDE` |

Save Changes.

### Step 6 — Check it worked
Book a test appointment **using your own phone number**. You should get a text
message within a minute.

---

# 💬 PART 3 — Twilio, for WhatsApp (30 minutes)

### A quick word first, so this makes sense

There are **two** ways to send WhatsApp:

- **Meta (Facebook)** — free, but they take days or weeks to approve you
- **Twilio** — costs a few naira per message, but **works the same day**

**We are setting up Twilio first**, so you are never stuck waiting. If you later
get Meta approved, the app uses Meta (free) and keeps Twilio quietly in the
background as a spare tyre. If Meta ever fails, **the app switches to Twilio by
itself** — you do nothing.

### Step 1 — Make the account
1. Go to **https://www.twilio.com/try-twilio**
2. Sign up, confirm your email and your phone
3. When it asks what you are building, choose **WhatsApp**

You get about **$15 free credit** — that is thousands of messages.

### Step 2 — Get your two codes
1. On the Twilio home page, scroll down to **Account Info**
2. You will see two things:
   - **Account SID** — starts with `AC...`
   - **Auth Token** — click **Show** to reveal it
3. Copy both somewhere safe

### Step 3 — Get a WhatsApp number

**The fast way — test today:**
1. On the left: **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Twilio shows a number, usually **+1 415 523 8886**, and a code like
   `join happy-tiger`
3. On your own phone, open WhatsApp and **send that exact code to that number**
4. Now Twilio can message you

> This test number only works for people who have sent the join code. Good for
> testing, **not for patients**.

**The real way — for patients (takes a few days):**
1. On the left: **Messaging** → **Senders** → **WhatsApp Senders**
2. Click **Create new sender**
3. Twilio walks you through verifying the hospital with Meta
4. ⚠️ **Use a phone number that is NOT already on WhatsApp.** A fresh SIM is
   easiest. If you use your own number you could lose WhatsApp on your phone.

### Step 4 — Hang the keys in Render

Add **four** settings:

| Key | Value |
|---|---|
| `WHATSAPP_MODE` | `twilio` |
| `TWILIO_ACCOUNT_SID` | *your `AC...` code* |
| `TWILIO_AUTH_TOKEN` | *your token* |
| `TWILIO_WHATSAPP_FROM` | `+14155238886` *(or your real number)* |

Save Changes.

> ➕ **Do not forget the plus sign.** Write `+2348012345678`, **not**
> `08012345678`. The app adds the rest itself.

### Step 5 — Check it worked
Submit a test inspection. The report should arrive on the WhatsApp number you
joined with in Step 3.

---

## ✅ Your complete checklist

Print this. Tick each box as you do it.

**AI — do this one first, it is free and takes 10 minutes**
- [ ] Groq account made
- [ ] `GROQ_API_KEY` added to Render
- [ ] **Did NOT add `GROQ_MODEL`**
- [ ] Asked the chat an odd question and got a real answer

**SMS**
- [ ] Termii account made
- [ ] Sender ID `GHIJEDE` requested (wait 1–3 days)
- [ ] ₦5,000 added to the wallet
- [ ] `SMS_MODE`, `TERMII_API_KEY`, `TERMII_SENDER_ID` added to Render
- [ ] Test SMS arrived on my own phone

**WhatsApp**
- [ ] Twilio account made
- [ ] Joined the test number from my own WhatsApp
- [ ] `WHATSAPP_MODE`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
      `TWILIO_WHATSAPP_FROM` added to Render
- [ ] Test report arrived on WhatsApp

**And the one I keep asking about**
- [ ] **Old GitHub token `ghp_7FM7…` deleted** at github.com/settings/tokens

---

## What it all costs

| | Cost | Notes |
|---|---|---|
| 🤖 AI (Groq) | **Free** | No card needed |
| 📱 SMS (Termii) | ~₦3–4 each | Pay as you go |
| 💬 WhatsApp (Twilio) | ~₦8–30 each | $15 free to start |
| 💬 WhatsApp (Meta) | **Free** | Slow to approve — worth waiting for |

**Roughly ₦10,000 a month** if you send one SMS to each of 100 patients a day.

---

## If something does not work

**Always look here first:**
Render → **hospital-suite** → **Logs** (on the left)

The reason is usually written there in plain English.

| What you see | What it means | What to do |
|---|---|---|
| `termii 401` | The SMS key is wrong | Copy it again — watch for a stray space |
| `Sender ID not approved` | Termii has not approved `GHIJEDE` yet | Wait. It still works with their default name |
| `Twilio error 63007` | That number is not a WhatsApp sender | Use the test number from Step 3 |
| `model_decommissioned` | You added `GROQ_MODEL` by hand | **Delete that setting** |
| Nothing happens at all | The app has not restarted yet | Wait 3 minutes and try again |

**Still stuck?** Copy the red line from the Logs and send it to me. Do **not**
send the keys themselves — just the error line.

---

## The three mistakes to avoid

1. **Never send a key to anybody** — not in WhatsApp, not to me. If one gets
   out, go back to that website and make a new one straight away.
2. **Never add `GROQ_MODEL`.** The right value is already in the app.
3. **Always test with your own phone first**, before you let the system send a
   single message to a real patient.

---

## My honest advice on the order

**Do the AI today.** It is free, it takes ten minutes, and it fixes something
that is broken right now — your assistant currently cannot answer anything
outside its script.

**Do Termii this week.** SMS reaches every patient, even the ones without a
smartphone.

**Do Twilio when you have a spare half hour.** WhatsApp is lovely for reports
to the MD/CEO, but it is not how most of your patients will hear from you.
