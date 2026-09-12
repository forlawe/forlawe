# Staff sign-in — 1.7.6

Date: 26 August 2026

What you asked for is now in the product. Existing staff at Ijede can still
sign in with the password they already use. Nobody is locked out by this
update.

## How a new person gets in

| Step | Who | What happens |
|------|-----|----------------|
| 1 | The staff member | They pick their own password. The system refuses easy ones. |
| 2 | The staff member | They give a real email (Gmail, Yahoo, Outlook, iCloud, government or hospital mail). Fake / temporary mail is refused. |
| 3 | The staff member | They type the 6-digit code sent to that email. That proves they own it. |
| 4 | System Admin | For people who asked for access themselves: tap **Approve**. For people you created: you already said yes. If the email never arrives, tap **Mark email seen** after you have spoken to them. |

They cannot use the app until every required step is done.

## Password rule (hard to guess)

| Must have | Example that fails | Example that passes |
|-----------|--------------------|---------------------|
| 10 or more characters | `SunPass1!` (9) | `QuietLake#4` |
| One CAPITAL letter | `quietlake#4` | `QuietLake#4` |
| One small letter | `QUIETLAKE#4` | `QuietLake#4` |
| One number | `QuietLake#!` | `QuietLake#4` |
| One symbol (`! @ # $ %` …) | `QuietLake14` | `QuietLake#4` |
| Not a common word | `Password1!` | `BlueGate#19` |
| Not their username or email name | username `jane` + `NurseJane1!` | `BlueGate#19` |

Phone-code lock is still **off**. Sign-in is username (or email) + password only.

## Emails we accept

| Allowed | Not allowed |
|---------|-------------|
| Gmail, Yahoo, Outlook / Hotmail, iCloud | Temporary boxes (Mailinator, Yopmail, …) |
| Proton, Zoho, AOL | Random shops (`ada@randomshop.xyz`) |
| `.gov.ng` `.edu.ng` `.mil.ng` `.org.ng` | A blank email on a **new** account |
| The hospital’s own domain (whatever is on the hospital profile) | |

## What each kind of account does

| How the account is made | Email activated? | Admin Approve? | Can sign in? |
|-------------------------|------------------|----------------|--------------|
| Already working staff (Ijede today) | Treated as yes (so nobody is locked out) | Already yes | Yes |
| You create them in Users | They must activate (or you tap Mark email seen) | Already yes | After email |
| They tap **Request access** | They must activate | You must tap Approve | After both |
| Bulk upload from Excel | No | You must tap Approve | After both, and they must set a real email |
| First admin of a new hospital (`/start`) | Yes (they just typed it) | Yes | Yes |

## Holes closed

| Hole | What we did |
|------|-------------|
| Easy password (`password`, name + 123) | Refused everywhere: request, create, reset, change |
| Fake email | Refused |
| New person walking in without Admin | Blocked until Approve |
| New person who never proved the mailbox | Blocked until the 6-digit code (or Mark email seen) |
| Guessing usernames | Request-access and forgot-password still do not say whether a name exists |
| Guessing the 6-digit code | 5 tries, then a new code. Code dies in 15 minutes. |
| Super Admin skipping the email rule | Closed. Only the first hospital admin (setup walk) is pre-activated. |
| Deploy locking Ijede out | Old accounts keep `email verified = yes` |

If the activation mail never arrives (no mail server on the free host), the
System Admin taps **Mark email seen** after speaking to the person. Do not tap
it for a stranger.

## What to tap on the phone

1. Sign in as System Admin.
2. **Users**. Amber tags = still waiting.
3. New staff: **Request access** on the sign-in page, or you create them with a Gmail / work mail.
4. After they activate: **Approve** (only if they asked themselves).

## Not in this batch

- Phone-code lock is still paused.
- Live booking SMS is still longer than 160 characters (menu 7).
- This is **not** on GitHub until you paste a new token.

Voice reminder stays on.
