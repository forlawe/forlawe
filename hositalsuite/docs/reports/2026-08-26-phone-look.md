# Phone look + hospital Sign up — 26 Aug 2026

Version on this computer: **1.7.11**. Not on GitHub yet. Not on the live site until you deploy.

## What was actually wrong

I did **not** take the screenshots at face value. I opened the pictures and the code.

| What the phone showed | What I first thought | What is true |
|---|---|---|
| Giant QR on Sign in | Logo upload is broken | They uploaded a **QR as the hospital logo**. The old phone stylesheet never limited the size, so the picture filled the screen. |
| Eye sitting under the box | The eye code is missing | Live HTML already had the eye. The **old stylesheet** on the phone had no “sit on the box” rule. |
| Card split blue / white | Layout is broken | Same old stylesheet. The new look never reached the phone. |
| Staff menu jammed in one line | Destinations are too many | True, **and** the bar is a desktop strip. Phones need a **Menu** button. |
| TV half empty | TV is landscape-only | The board already stacks on a narrow screen. Empty = no patient on the board. |

Root cause in the software: the phone **saves the old look** (service worker `hs-shell-v1`, cache-first on `/static/`). New pages arrived. Old paint stayed.

## What I changed

| Item | What you will see |
|---|---|
| Fresh look on phones | Stylesheet now has `?v=1.7.11`. Phone cache name is now `hs-shell-1-7-11`. CSS/JS load from the network first. |
| Logo size | Hard cap **64 × 64**. A QR uploaded as a logo cannot blow the card open. |
| Eye on password | Stays on the box. |
| Staff menu on a phone | A **Menu** button. Tap to open the list. Tap **Close** to hide it. |
| Logo upload hint | “a square picture of the hospital — not a QR code”. |
| Hospital Sign up | Each hospital has its own link: `/signup/TEST` (example). With more than one hospital, bare `/signup` does **not** drop a stranger into the first hospital. |

## How to check on the phone (after deploy)

1. Open the site in Chrome.
2. Menu (three dots) → **Settings** → **Privacy** → **Clear browsing data** → Cached images (this site only), **or** visit the site in a new Chrome tab that is **not** the installed app.
3. If you added the app to the home screen: delete the icon, open the site in Chrome, add it again. That is the only sure way to drop the old saved look.
4. Sign in should show a **small** hospital mark, the eye **on** the password box, and no giant QR.
5. After sign in, the top should say **Menu**, not a long jammed strip.

## What I did **not** change

- **Sign-in name is still unique on the whole software**, not per hospital. That way two hospitals cannot both use `nurse1` and then nobody knows who is signing in. People can still sign in with **email**.
- Mail van is still waiting on Render (`BREVO_API_KEY` + `MAIL_FROM`). That is on you.
- Nothing was pushed to GitHub. I have no new token.

## Tests I ran

18 checks on phone look, doors, and sign-in. All passed.
