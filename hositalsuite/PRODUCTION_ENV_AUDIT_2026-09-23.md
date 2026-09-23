# Production Environment Audit — 2026‑09‑23

Checked directly against the live Render account and both GitHub repos —
not against any prior written report. This is a handoff document for
whoever has developer/Render-dashboard access; it also updates
`render.yaml` in this repo (see the companion commit) with declarations
that were previously missing.

---

## 0. BLOCKER — both Render services are suspended for billing

This is the actual, sole reason nothing is currently serving traffic. No
code change, environment variable, or Claude action fixes this — it
requires the Render account owner to act in the Render dashboard.

| Service | Repo | Plan | Status | Last changed |
|---|---|---|---|---|
| `hospital-suite` (`srv-d9u8b37avr4c73enll5g`) | `Hcarepro2026/hositalsuite` (live production) | **free** | **SUSPENDED — billing** | 2026‑09‑22T20:30:57Z |
| `hospital-suite-forlawe` (`srv-daiq4vp5efls73eh9o60`) | `forlawe/forlawe` (dev target) | **free** | **SUSPENDED — billing** | 2026‑09‑22T20:30:56Z |

**Action required (human, Render dashboard only):**
1. Go to **Render Dashboard → Billing** and resolve whatever payment issue
   triggered the suspension (expired card, failed charge, etc.).
2. Once resolved, both services should auto-resume. If not, open each
   service and click **Resume**.
3. **Separately from the suspension:** both services are on the **free**
   plan, not **starter**, even though `render.yaml` has said `plan: starter`
   since 2026‑08‑27. A blueprint's `plan:` line is only applied when Render
   creates a *new* service from the blueprint — it does not retroactively
   change a service that already exists. Free-tier services sleep after 15
   minutes of inactivity (30‑second cold start on the next request) and are
   explicitly documented in this repo's own comments as the cause of the
   15 Aug outage. **Manually change Plan → Starter (or higher) on both
   services** in the Render dashboard, or delete and recreate them from the
   blueprint.
4. Attempting to change environment variables via the Render API while a
   service is suspended fails outright (`400: cannot deploy suspended
   service`) — confirmed directly. Nothing below can take effect until
   step 1 is done.

---

## 1. What was fixed in this commit (`render.yaml`)

Declarations added for five groups of environment variables that the app
code (`app/push.py`, `app/chatbot/ai.py`, `app/whatsapp.py`) fully
supports, but which had no slot in the blueprint at all — meaning a
fresh deploy from this blueprint would silently run without them, with no
error, just quietly degraded features:

- **VAPID (push/alarm)** — `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`
- **AI chatbot fallback** — `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `AI_FALLBACK`
- **WhatsApp Cloud API** — `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`
- **USSD** — `USSD_SHARED_SECRET`

### New finding, not previously in the F‑001..F‑087 list: silent VAPID rotation on every redeploy

`app/push.py::_ensure_global_vapid()` auto-generates a VAPID keypair the
first time it's needed if none is configured, and saves it to
`instance/vapid_keys.json` for reuse. **Render's local disk is wiped on
every deploy** (documented elsewhere in this same codebase, e.g.
`STORAGE_BACKEND` comments) — so every redeploy silently generates a
*new* keypair, and every existing push subscription in every patient's and
staff member's browser is now bound to the *old* public key and will fail
permanently (`403 Unauthorized` from the push service). Nothing logs this
as an error the way the app is currently wired — it just stops working.
Since "alarm when app closed" is a compulsory feature, this should be
tracked and fixed (set `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` as real env
vars, which the code already checks first and prefers).

---

## 2. Ready-to-use generated values

Generated locally with the same method `app/push.py::_generate_vapid_keys()`
uses (SECP256R1, uncompressed point, base64url, no padding) — these are
real, valid keypairs, not placeholders. **Each service needs its own
distinct keypair** — never reuse one across both services, since a
subscription registered against one service's public key can only be
decrypted by that same service's private key.

### For `hospital-suite` (live production — Hcarepro2026/hositalsuite)
```
VAPID_PUBLIC_KEY=BAxrJb3UQbiDLYwVA4lxKpRTvAxw0hc2m5TJBOx4gWiqxqEfIANtZdMGEAcBq5F6pR9lsj0kfLDpatVqPuQRL9o
VAPID_PRIVATE_KEY=voenmsmMXaS4gUvqIKJG0KifRd3dV04lNBcQJfz3kh4
VAPID_SUBJECT=mailto:founder@ghijede.gov.ng
```

### For `hospital-suite-forlawe` (dev target — forlawe/forlawe)
```
VAPID_PUBLIC_KEY=BFHiCvRgEXCjUk6-TsgEQao_BjIUwvWDyJJxjpsl5cBz5wicpUogGnIKbir_KLYlQdyZ6WfvHMpzS_Wv2ROVHT0
VAPID_PRIVATE_KEY=dZZaELUMaCWXjmd4Gc7Zm8jiZEwTwLfpGMEZRExJHts
VAPID_SUBJECT=mailto:admin@hospital-suite-forlawe.onrender.com
```

**I could not set these directly** — the Render API rejected the update
with `cannot deploy suspended service` (see §0). Once billing is resolved,
paste these into each service's Environment tab in the Render dashboard
(or ask me to set them via the API at that point — I can do that part
without any push/bash from you).

Treat `VAPID_PRIVATE_KEY` above as a secret from this point on — it's now
committed to this markdown file, which is fine as a one-time handoff, but
don't regenerate around it casually once it's live: rotating it will break
every existing push subscription exactly like an accidental redeploy
would, until users revisit the site and re-subscribe.

---

## 3. Still needs real credentials from you (cannot be generated)

These require signing up with the actual provider — nothing to compute:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase project → Settings → Database → Connection string (append `?sslmode=require`) |
| `GROQ_API_KEY` | console.groq.com — free tier, recommended primary AI provider |
| `GEMINI_API_KEY` | aistudio.google.com — free tier, recommended secondary |
| `TERMII_API_KEY` / `TERMII_SENDER_ID` | accounts.termii.com — sender ID needs Termii approval first |
| `RESEND_API_KEY` / `MAIL_FROM` | resend.com — verify your sending domain first |
| `WHATSAPP_PHONE_NUMBER_ID` / `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_VERIFY_TOKEN` / `WHATSAPP_APP_SECRET` | Meta Business → WhatsApp → API Setup (only needed to move off `WHATSAPP_MODE=sandbox`) |

---

## 4. Compulsory-feature status (spot-checked against live code, not reports)

| Feature | Code present | Config gap found |
|---|---|---|
| Voice reminder/alarm | ✅ `native_voice.py`, `push.py` | VAPID env vars missing (fixed above); silent rotation bug (§1) |
| Department/patient TV | ✅ `tv.py`, `personal_tv.py` | none found in this pass |
| PWA | ✅ `pwa.py` | none found in this pass |
| Fast-Track | ✅ `views/fasttrack.py`, `cashdesk.py` | none found in this pass |
| Admin Manager | ✅ `views/admincp.py`, `inspections.py`, `rolesadmin.py` — F‑046 escalation guard confirmed live | none found in this pass |

---

## 5. Verified fixes already live (confirmed by reading current code, 2026‑09‑23)

- **F‑046** (critical role-escalation vulnerability) — confirmed fixed in
  `app/views/rolesadmin.py`: `save()` and `assign()` both reject
  granting/assigning any permission the acting user doesn't already hold.
- **F‑033** (AI clinical guardrail English-only) — confirmed fixed in
  `app/chatbot/ai.py`: `_CLINICAL_LEAK` now includes Pidgin, Yoruba, Hausa,
  and Igbo phrases.

Not every one of the 87 findings from the audit was re-verified in this
pass — flagging that honestly rather than implying a full re-audit.
