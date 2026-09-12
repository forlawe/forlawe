# Staff card after email — 1.7.7

Date: 26 August 2026

Local product is **1.7.7**. Now also on GitHub `main` as **`42d4c72`**.
The push token was used once and removed from this machine.

Existing Ijede staff still sign in with the password they already use.
Nobody is locked out.

## How a new person gets in now

| Step | Who | What happens |
|------|-----|----------------|
| 1 | The staff member | They pick a hard password and a real email. |
| 2 | The staff member | They type the 6-digit code from that email. |
| 3 | The staff member | The app opens **Your staff card** (`/staff-card`). Full name, department, section, unit, cadre, job they are asking for, optional special responsibility. |
| 4 | System Admin | On **Users**, they see what was asked. They pick the real job (or keep the request) and tap **Approve**. |

They cannot use the app until every step is done. Sending the staff card
does **not** let them in.

## What they may ask to be

| They may ask | They may **not** ask |
|--------------|----------------------|
| Staff, HOD, Admin Manager, Apex Nurse | Super Admin (the form refuses it) |
| Head Admin / HR, DCST, DMD, MD / CEO | |

The account stays **Staff** until you Approve. You can accept or change
the job on the Approve tap.

## What each kind of account does

| How the account is made | Email | Staff card | Approve | Can sign in? |
|-------------------------|-------|------------|---------|--------------|
| Already working staff | Treated as yes | Treated as yes | Already yes | Yes |
| They tap **Request access** | They must activate | They must send the card | You tap Approve | After all three |
| You create them in Users | They must activate | They must send the card | You tap Approve | After all three |
| Bulk upload from Excel | No | They fill their own card | You tap Approve | After all three |
| First admin of a new hospital (`/start`) | Yes | Yes | Yes | Yes |

## Who can open what (checked)

| Who | Sign-in, book, join queue, complaint, chat | Dashboard / wards | Users, Settings, Security, TV, branches |
|-----|--------------------------------------------|-------------------|-----------------------------------------|
| Visitor / patient | Open | Sent to sign-in | Sent to sign-in |
| Ordinary staff (after Approve) | Open | Open | **Blocked (403)** |
| System Admin | Open | Open | Open |

`python tools/check_links.py` — every template link and form points at a real page.

Tests run this batch: **190 passed** (login, staff card, access gates, Users,
onboard, roles, bulk, hardening, MFA, navigation, smoke). Full `tests/`
folder is longer than the time box; `test_roles.py` still has an old
attendance-table drop warning that is not from this work.

## What to tap on the phone

1. New person: **Request access** on the sign-in page.
2. They activate email → fill **Your staff card** → wait.
3. You: **Users**. Amber tags = still waiting. Read the job they asked for.
4. Pick the job (or keep theirs) → **Approve**.
5. They sign in with the password they chose.

If the activation mail never arrives, tap **Mark email seen** after you
have spoken to them. Then they still fill the staff card. Do not tap it
for a stranger.

Phone-code lock is still **off**. Sign-in is username (or email) + password only.

## Not in this batch

- On GitHub as of 26 August 2026 (`42d4c72`). Token deleted after the push.
- Phone-code lock stays paused.
- Live booking SMS is still longer than 160 characters (menu 7).
- Native voice bank is waiting for your pick (menu 6).

Voice reminder stays on.
