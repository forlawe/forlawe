# Put the mail van on Render — like teaching a 10-year-old

I **cannot** open your Render page from here. Render is a locked cupboard. Only you have the key. I checked your Brevo key: **it works**. I also sent one test letter to **hcareproapp@gmail.com**. Open that Gmail (and Spam) now.

Your Brevo mailbox that is allowed to send: **hcareproapp@gmail.com**  
Free plan: **300 letters a day**.

What you pasted is the **Brevo secret**. It is **not** something I can plug into Render myself. Never put that secret in GitHub. Only in Render.

---

## Picture in your head

The hospital app is a boy.  
Gmail is grandma’s house.  
Render is the street.  
Brevo is the **post office**.

The boy already knows how to walk to the post office (we built that).  
You must pin **two notes** on Render’s fridge:

1. The post-office secret (`BREVO_API_KEY`)
2. The return address (`MAIL_FROM`)

If either note is missing, grandma gets nothing.

You said the secret is already on Render. Then the missing note is almost always **MAIL_FROM**.

---

## Part A — Brevo on Render (do this first)

Do these steps slowly. One finger. One box.

### 1. Open Render
1. On your phone or computer, go to **https://dashboard.render.com**
2. Sign in.
3. Tap your app. The name is like **hospital-suite**.

### 2. Open the fridge (Environment)
1. On the left (or the tabs), tap **Environment**.
2. You will see a list of names and secret values.

### 3. Note 1 — the secret (skip if you already added it)
1. Tap **Add Environment Variable**.
2. In **Key**, type exactly:

```
BREVO_API_KEY
```

3. In **Value**, paste the long secret that starts with `xkeysib-`  
   (the one inside the Brevo MCP paper — not the whole base64 blob).
4. Save that row.

If you already have `BREVO_API_KEY`, do **not** add a second one. Just check the name is spelled exactly like that. No space. No small letters mixed wrong.

### 4. Note 2 — the return address (this is the one people forget)
1. Tap **Add Environment Variable** again.
2. In **Key**, type exactly:

```
MAIL_FROM
```

3. In **Value**, type exactly:

```
Hospital Suite <hcareproapp@gmail.com>
```

4. Save that row.

That address **must** be the one Brevo already approved. Yours is `hcareproapp@gmail.com`. If you type a different Gmail, Brevo will throw the letter in the bin.

### 5. Let the app wake up
1. After you save, Render **restarts** the app. Wait **2–3 minutes**.  
   A yellow “deploying” bar means “still putting on shoes.”
2. When it is green / live, go on.

### 6. Prove it
1. Open your hospital site.
2. Sign in as **System Admin**.
3. Open **System Health**.
4. You should see **Mail van: on — brevo**.
5. Tap **Send a test letter to my email**.
6. Open **hcareproapp@gmail.com** on your phone. Look in **Inbox** and **Spam**.

If the test letter is there, Sign-up codes will arrive too.

---

## If it still fails — a tiny checklist

| You see | Meaning | What to do |
|---|---|---|
| Mail van: **off** | Render does not have the two notes, or the app is an old version | Check both names. Wait for deploy. We need **1.7.10** on GitHub first |
| Mail van on, test letter **error** | Secret or return address is wrong | Copy `MAIL_FROM` again. No extra space |
| Test letter sent, Gmail empty | It is in **Spam** or Promotions | Open Spam. Star the letter so Gmail learns |
| Site still on old version | New mail code is only on this computer until you give a GitHub token | Paste a new GitHub token and ask me to push **1.7.10** |

---

## Part B — Resend (only if you want a spare post office)

You do **not** need Resend if Brevo works. One post office is enough.

If you still want it later:

1. Go to **https://resend.com** and make an account.
2. They will give a key that starts with `re_`.
3. On Render → Environment, add:

```
RESEND_API_KEY
```

and paste the `re_` key.

4. `MAIL_FROM` must then be an address **Resend** verified (not automatically the Gmail Brevo uses).
5. The app tries Resend **first** if that key is present. So if both keys are set, Resend wins.  
   For you today: **only put Brevo**, so the van you already opened is the one that drives.

---

## What I did with your secret

| Did I… | Answer |
|---|---|
| Check the secret with Brevo? | Yes. It is a real key. Account **hcareproapp@gmail.com**. |
| Send one test letter to that Gmail? | Yes. Subject: **Test: your hospital mail van works**. |
| Put the secret in GitHub or the code? | **No.** |
| Type it into Render for you? | **No. I cannot open Render.** |

That secret is now in this chat. Do not paste it into GitHub, WhatsApp groups, or a screenshot. If many people saw this chat, make a **new** key in Brevo later and throw the old one away.

---

## Voice reminder

Chrome / Google speech still sounds foreign. Native phrase bank waits for your pick.
