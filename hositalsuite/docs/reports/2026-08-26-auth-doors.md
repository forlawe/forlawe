# Sign-in doors — 1.7.9

Local product is **1.7.9**. GitHub `main` is still **1.7.8** (`4d1b02b`) until you paste a new token. Nothing was pushed this round.

## What you asked for

| You said | What we did |
|---|---|
| Orange items on public login look unprofessional and unsafe | Removed **Request access**, **Finish your staff card**, and **Setting up a new hospital** from Sign in |
| Those doors belong under System Admin | They now live on **Users & Roles** (and **Set up another hospital** was already on the Admin home) |
| Public trio: Sign in / Sign up / Forgot password | That is all a stranger sees |
| Eye icon so a person can check the password | Eye on Sign in, Sign up, Forgot-reset, and Change password |
| Do not build around Ijede | Sign in shows **this hospital’s name and logo**, or “Hospital Suite” if none. No Ijede tagline. No “Inspection · Monitoring · Complaints” on the staff door |

## What a stranger sees now

| Page | What is on it |
|---|---|
| Sign in `/login` | Username, password + eye, **Sign in**. Links: Sign up, Forgot password |
| Sign up `/signup` | Name, username, email, password + eye. Same as the old request-access form, new name |
| Forgot password `/forgot-password` | Username / email / phone. Then New password + eye |
| Staff card `/staff-card` | **Not** on Sign in. Opens only after the person proves their email |
| New hospital `/start` | **Not** on Sign in. Sales page still points here. Admin can open it |

Old address `/request-access` still works (same page as Sign up) so existing links and tests do not break.

## Where the hidden doors live (System Admin)

On **Users & Roles**:

| Door | What the Admin does |
|---|---|
| Sign up | Copy the hospital’s `/signup` link and send it only to people they know — or create the person on this page |
| Staff card | Amber tags = waiting. Admin taps Approve |
| New hospital | Link to **Set up another hospital** (needs a setup code once a hospital already exists) |

Admin home still has **Set up another hospital**.

## Eye icon

Tap the eye beside a password box to show or hide the letters. Same on every password page.

## Checks

| Check | Result |
|---|---|
| Sign in has Sign up + Forgot password + eye | Yes |
| Sign in has no staff-card, no new-hospital | Yes |
| Sign up page opens and has the eye | Yes |
| Old `/request-access` still accepts a form | Yes |
| Forgot / reset / change password still work | Yes |
| Admin can still reset a password | Yes |
| Tests run this round | **23 passed** on the auth / signup / forgot / onboard files. Extra MFA, smoke, hardening, user-admin, founder pages also green after the one Forgot-password wording fix |

## Honest leftover (not this page)

Sign up still joins **the first hospital on this server**. That is the old behaviour. We did **not** hard-code Ijede. A later round can ask “which hospital?” when one server holds many hospitals.

## Not pushed

Need a **new** GitHub token to put 1.7.9 on GitHub. The last token was deleted after 1.7.8.

## Voice reminder

Chrome / Google speech still sounds foreign. We will not build the native phrase bank until you pick it (menu item 6).
