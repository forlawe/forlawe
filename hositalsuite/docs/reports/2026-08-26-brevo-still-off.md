# Brevo is not broken — the live server has an empty key drawer

**Date:** 26 Aug 2026. Software on the live site is **1.7.12**. A small honesty upgrade (**1.7.13**) is on this computer only until you send a **new** GitHub token.

## What the screenshot really says

I opened the picture myself. I also asked the live site.

| What it looks like | What is true |
|---|---|
| “Brevo is not working after the new deploy” | The new software **is** live. Database is connected. |
| Red banner | `Mail van is not set up (no Resend / Brevo / SendGrid / SMTP key)` |
| Live `/api/v1/health` | `"mail": "off"` |

That sentence is only printed when the running program **cannot see any key at all**. Brevo was **never called**. This is not a failed letter. This is an empty van.

Seeing the **name** `BREVO_API_KEY` on Render is not the same as pasting the **secret**. The blueprint already creates the empty name.

## What you do (5 minutes)

1. Open [Render](https://dashboard.render.com).
2. Open the service that is actually live: **hospital-suite** (the one whose address is `hospital-suite.onrender.com`).
3. Click **Environment**.
4. Click the row **BREVO_API_KEY**. If the value box is blank, that is the whole problem.
5. Paste the real Brevo secret (starts with `xkeysib-`). No spaces. No quotes.
6. Click **MAIL_FROM**. Set exactly:

```
Hospital Suite <hcareproapp@gmail.com>
```

7. Click **Save Changes**. Wait until the deploy is **green**.
8. System Health → **Send a test letter**.
9. The page must say **on — brevo**. Then open Gmail **and Spam**.

Do **not** put the secret in GitHub or in this chat.

## What I changed in 1.7.13 (not live yet)

| Change | Why |
|---|---|
| Read the key from the live process, and trim spaces | A leftover space would hide a real key |
| Prefer Brevo first | You asked for only Brevo |
| System Health shows **yes / empty** for the key and for MAIL_FROM | You can see what the server actually has |
| Shows software version | So we know which deploy you are looking at |

## Round check (first built → last built)

I did not take “Brevo is broken” as the only job. I walked the doors we already built.

| Door | Status | Crash / gap |
|---|---|---|
| Sign in / Sign up / Forgot / eye | Live | Works. Forgot-password uses the same mail van. |
| Activation code | Live, honest | Will not leave until the key drawer is filled. Admin can still tap **Confirm email**. |
| Staff card after email | Code is correct | Session is set after a good code. |
| Phone look 1.7.11 | Live | Old home-screen icon can still show the old paint until you delete it. Logo still a QR until you upload a square picture. |
| Hospital Sign up link | Live | `/signup/CODE` binds a hospital. |
| RLS on staff / settings / departments | Live 1.7.12 | Seatbelt on. |
| Mail van | Live code, **empty key** | This page. |
| WhatsApp | sandbox | Not a crash. Letters are the van you asked for. |
| Username unique per hospital | Not done | Sign-in name is still unique on the whole software so people can sign in without picking a hospital. |
| Revenue / Photo / live load / final report / voice | Not started | Waiting. Voice waits for your pick. |

No 500 on System Health. The red box is the software telling the truth.

## Token

I will not use the old GitHub key again. If you want 1.7.13 live, make a **new** token, send it once, I push, you delete it.

## Voice reminder

Native recorded phrase bank is still paused until you pick it.
