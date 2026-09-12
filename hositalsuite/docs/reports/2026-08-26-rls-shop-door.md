# Shop door + mail van — 26 Aug 2026

Version on this computer: **1.7.12**. Not on GitHub. Not live until you deploy.

## 1. Mail van — I cannot finish this from here

| What you asked | What I can do | What only you can do |
|---|---|---|
| Put Brevo on Render and send a test letter | The van code is already written. System Health has the test button. | Open Render → Environment. Add the two lines below. Wait for green. Then tap **Send a test letter**. |

On Render, add **exactly**:

| Name | Value |
|---|---|
| `BREVO_API_KEY` | the secret from Brevo (do not paste it to me or to GitHub) |
| `MAIL_FROM` | `Hospital Suite <hcareproapp@gmail.com>` |

Then send me a new GitHub token if you want 1.7.12 on the live site. I delete the token after use.

I checked earlier: your Brevo key itself works. The live server still does not have it.

## 2. Shop door — staff / settings / departments now have the seatbelt

| Table | Before | Now |
|---|---|---|
| Patients, visits, complaints… | Database refuses a leak | Same |
| **user** (staff names) | Only Python remembered the filter | Database refuses too |
| **setting** (colours, SLA, fence) | Only Python | Database refuses too |
| **department / section / unit** | Only Python | Database refuses too |

Sign-in is still safe: the software first opens the door to find **your** account, then locks the rest of the request to **your** hospital. If we locked `user` without that step, every staff member would be thrown out.

Hospital Sign up from 1.7.11 stays: `/signup/THEIRCODE` joins that hospital. Bare `/signup` does not pick the first hospital when more than one exists.

Sign-in name is still unique on the **whole** software, so two hospitals cannot both use `nurse1` and then nobody knows who is signing in. People can still sign in with **email**.

## How we checked

| Check | Result |
|---|---|
| Protected list includes user, setting, department | Yes |
| Account is loaded only after the door is open | Yes |
| Mail / sign-in / phone-look tests | Passed |
| Real PostgreSQL leak test | Skipped here (this box has SQLite). It will run on the live Postgres at boot. |

## Voice reminder

Native recorded phrase bank is still paused until you pick it.
