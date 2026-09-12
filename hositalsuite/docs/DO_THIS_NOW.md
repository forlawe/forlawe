# Do these 4 things — click-by-click

**For:** the founder, General Hospital Ijede
**Date:** 20 August 2026
**Time needed:** about 15 minutes total
**You need:** your phone or laptop, and your Supabase, GitHub and Render logins

Do them **in this order**. Task 1 and 2 must be done back-to-back — there is a
short window between them where the website will show an error, and that is
normal.

---

## ⚠️ Read this first (30 seconds)

Your hospital's **database password was visible on the public internet**. I
found it while answering your question about making GitHub private. It was
written into a guide file as an example, and that file was public.

**Deleting the file is not enough.** Anyone who copied the password still has
it. The only thing that actually protects you is **changing the password**.
That is Task 1, and it is the most important thing on this page.

There is no evidence anybody copied it (the repository had 0 forks and 0
watchers). But "no evidence" is not "safe", so we change it anyway.

---

# TASK 1 — Change your database password 🔴 MOST IMPORTANT

### 👉 Direct link
```
https://supabase.com/dashboard/project/zhhdhfllypkzvmukilwt/settings/database
```

### What to do

1. Click the link. Sign in to Supabase if it asks.
2. Look for a section called **Database password**.
3. Click the **Reset database password** button.
4. Supabase will offer to **generate a password** — click that. Let it make one
   for you; it will be far stronger than one you invent.
5. **COPY THE PASSWORD AND PASTE IT SOMEWHERE SAFE RIGHT NOW.**
   Supabase shows it **once**. If you close the page without copying it, you
   must reset it again.
   - Put it in your phone's Notes app for the next five minutes.
   - Delete it from Notes once Task 2 is finished.
6. Click **Reset password** to confirm.

### ⚠️ Expect this
The moment you do this, **your website will stop working**. That is correct and
expected — the app is still using the old password. Task 2 fixes it. Go
straight there.

---

# TASK 2 — Tell the website the new password 🔴 DO IMMEDIATELY AFTER TASK 1

### 👉 Direct link
```
https://dashboard.render.com/
```

Click your service named **hospital-suite**, then **Environment** in the left menu.

### What to do

1. Find the row called **`DATABASE_URL`**.
2. Click **Edit** (a pencil icon).
3. You will see a long line of text. It looks like this:

```
postgresql://postgres.zhhdhfllypkzvmukilwt:OLDPASSWORD@aws-0-XXXX.pooler.supabase.com:5432/postgres?sslmode=require
```

4. You are changing **only the password part** — the bit between the `:` after
   your project reference and the `@`. Leave everything else exactly as it is.

### ⚠️ THE ONE THING THAT CATCHES PEOPLE OUT

If your new password contains any of these characters, you must replace them:

| If the password has | Type this instead |
|---|---|
| `@` | `%40` |
| `#` | `%23` |
| `$` | `%24` |
| `&` | `%26` |
| `/` | `%2F` |
| `?` | `%3F` |
| `+` | `%2B` |
| a space | delete it |
| `[` or `]` | delete it |

**Example:** if Supabase gives you `Kx7@mP2q`, you type `Kx7%40mP2q`.

If the password is only letters and numbers, type it exactly as it is.

5. Click **Save Changes**. Render will restart the site automatically.
6. **Wait 2–3 minutes**, then open your site and check it loads:
   ```
   https://hospital-suite.onrender.com
   ```

### ✅ How to know it worked
Open this link. It should say `"ready":true`
```
https://hospital-suite.onrender.com/api/v1/ready
```

If it still shows an error after 5 minutes, the password almost certainly has a
special character that needs the code from the table above. Tell me and I will
check it for you.

7. **Now delete the password from your phone's Notes app.**

---

# TASK 3 — Delete the exposed GitHub token 🟠

### 👉 Direct link
```
https://github.com/settings/tokens
```

### What to do

1. Click the link. Sign in to GitHub if it asks.
2. You will see a list of tokens. Find the one starting with **`ghp_7FM7`**.
   (It may be named something like "hospital suite" or "render".)
3. Click **Delete** next to it.
4. Confirm.

**Why:** this token was shown in our chat. Anybody who has it can change your
hospital's software. It is like a spare key you left on a table.

### Do you need to make a new one?
**Probably not.** Render deploys your site by itself — it does not use this
token. The token was only for me pushing code.

If I need to push again, I will tell you, and you can make a fresh one here:
```
https://github.com/settings/tokens/new
```
- **Note:** type `hospital-suite-push`
- **Expiration:** choose **30 days** (not "No expiration")
- **Tick only:** the box marked **`repo`**
- Click **Generate token**, copy it, and paste it to me

⚠️ **Never** tick "No expiration". A token that expires limits the damage if it
ever leaks again.

---

# TASK 4 — Make your code private 🟠

### 👉 Direct link
```
https://github.com/Hcarepro2026/hositalsuite/settings
```

### What to do

1. Click the link.
2. Scroll all the way to the **bottom** of the page, to a red section called
   **Danger Zone**.
3. Find **Change repository visibility** and click **Change visibility**.
4. Choose **Make private**.
5. It will ask you to type the repository name to confirm. Type exactly:
   ```
   Hcarepro2026/hositalsuite
   ```
6. Click the confirm button.

### ✅ Nothing will break
I checked this before recommending it:
- **Render will keep deploying normally** — it connects through its own GitHub
  permission, not the token.
- **My pushes will keep working** — the token has the right permission level
  for private repositories.

### One thing to know
Once private, nobody can see your code without you inviting them. If you ever
hire a developer, you would add them here:
```
https://github.com/Hcarepro2026/hositalsuite/settings/access
```

---

# ✅ Your checklist

Tick these off as you go:

- [ ] **Task 1** — Database password changed in Supabase *(most important)*
- [ ] **Task 2** — New password saved in Render, site loads again
- [ ] **Task 3** — Token `ghp_7FM7…` deleted from GitHub
- [ ] **Task 4** — Repository switched to private
- [ ] Password deleted from my phone's Notes app

---

# Still to do later (not urgent today)

These are worth doing this week, but nothing is at risk if you wait.

### Turn on database backups
```
https://supabase.com/dashboard/project/zhhdhfllypkzvmukilwt/database/backups
```
Your only protection against losing everything. The app already makes its own
nightly backup, but Supabase's own backup is a second, independent copy.

### Add a second uptime monitor
```
https://uptimerobot.com/dashboard
```
Add a monitor pointing at:
```
https://hospital-suite.onrender.com/api/v1/ready
```
You already monitor the front page. This one also catches a **database**
problem, which the front page can hide.

### Switch on the AI assistant
```
https://console.groq.com/keys
```
Create a key, then add it in Render → hospital-suite → Environment as
**`GROQ_API_KEY`**.

⚠️ **Do not** add a setting called `GROQ_MODEL`. The correct model is already
chosen and tested in the code; setting that would override it and could break
the assistant.

---

# If anything goes wrong

**The site shows an error after Task 2** — nine times out of ten this is a
special character in the password. Check the table in Task 2. Tell me and I
will check the exact text with you.

**You closed the page before copying the password** — no harm done. Just do
Task 1 again and get a new one.

**You are unsure about any step** — stop and ask me. Nothing here is urgent to
the minute, and a wrong guess on Task 2 takes the website down until it is
fixed. There are no silly questions.
