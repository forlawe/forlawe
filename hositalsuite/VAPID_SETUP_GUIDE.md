# VAPID Setup — Permanent Keys for Production (Push Cost Saver 90%)

## Why Permanent?

- Auto-generated keys in `instance/vapid_keys.json` work out-of-box but break on Render redeploy (instance folder deleted).
- Permanent keys in Render env survive redeploys — patients stay subscribed, no need to tap "Enable alarm" again.

## Where to Generate (One Time, 30 seconds)

On your laptop or server:

```bash
python -m py_vapid --gen --applicationServerKey
```

Or use cryptography:

```python
from cryptography.hazmat.primitives.asymmetric import ec
import base64
def b64url(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')
k = ec.generate_private_key(ec.SECP256R1())
priv = b64url(k.private_numbers().private_value.to_bytes(32,'big'))
pub = b64url(b'\x04' + k.public_key().public_numbers().x.to_bytes(32,'big') + k.public_key().public_numbers().y.to_bytes(32,'big'))
print(pub, priv)
```

You get:
- PUBLIC: starts with `B...` (safe to share, goes to browser)
- PRIVATE: small letters (SECRET, never share, never commit to GitHub, never put in frontend)

## Where to Paste in Render (Production)

1. Open https://dashboard.render.com → Your service `hositalsuite` → Environment
2. Add 3 variables:
   - `VAPID_PUBLIC_KEY` = your PUBLIC key (B...)
   - `VAPID_PRIVATE_KEY` = your PRIVATE key (secret)
   - `VAPID_SUBJECT` = `mailto:your-hospital@email.com` (your contact)
3. Save → Render auto redeploys → Push now permanent

## Per-Hospital Branding (Premium)

Each hospital can have own keys showing its logo/name on phone:

1. Login as SUPER_ADMIN → Admin → Settings → Push Notifications
2. Paste:
   - VAPID Public Key
   - VAPID Private Key
   - VAPID Subject
3. Save

Now push notification shows that hospital's logo, not global.

## Security Checklist (MUST)

- ✅ PRIVATE key only in Render env + Admin Settings DB (backend)
- ❌ NEVER in frontend JS `push.js`, `personal_tv.html`
- ❌ NEVER in GitHub, `.env` committed, `manifest.json`
- ✅ PUBLIC key only via `/api/v1/push/vapid-public` API (safe)
- ✅ `instance/` and `*.pem` and `*.key` in `.gitignore` — never committed
- ✅ If leak, generate new pair immediately, update env, users re-enable

## What Happens If You Don't Set Permanent?

App still works via auto-generation in `app/push.py` `_ensure_global_vapid()`:
- Generates keys on first boot
- Saves to `instance/vapid_keys.json` (backend only)
- Sets `current_app.config`
- Logs warning to set env for persistence
- Push works until next Render deploy, then old subscriptions break

## Test That Push Works Closed Like Alarm

1. Open your app on Android Chrome → Join queue → Tap "Notify me when called" → Allow
2. You see "✅ You will be notified even if app closed, like alarm"
3. Close app completely, lock phone (sleep)
4. In another browser, as staff, call next ticket
5. Phone should vibrate `[500,200,500,200,1000]`, show notification with hospital logo, stay until you tap (requireInteraction)
6. Tap → opens `/t/<key>` personal TV

If no notification:
- Check Render env set?
- Check browser permission allowed?
- Check `instance/vapid_keys.json` exists on server?
- Check `/api/v1/push/vapid-public` returns public key?
- Fallback: Main TV + voice still calls patient inside hospital (push is secondary, not only)

## Cost Saving

- Before: SMS ₦4 × 1000 patients = ₦4000/day
- After: Push FREE + TV + Voice FREE, SMS only outside/emergency ~100/day = ₦400/day
- Saving 90%

## Your Current Production Keys (Generated 2026-09-01)

**DO NOT COMMIT PRIVATE KEY TO GITHUB — Set in Render env only**

Example format (replace with your real keys from secure chat):

- PUBLIC: `B...` (87 chars, starts with B, safe to share)
- PRIVATE: `...` (43 chars, SECRET — paste in Render env only, never in GitHub or frontend)
- SUBJECT: `mailto:your-hospital@email.com`

**Real keys for this deployment were shown in secure chat and saved to `instance/vapid_keys.json` (gitignored, not committed). After pasting in Render, delete any file containing private key.**

To generate new ones anytime: `python -m py_vapid --gen`

## Files Changed

- `app/push.py` — auto-generation fallback
- `.gitignore` — added `instance/`, `vapid_keys.json`, `*.pem`, `*.key`
- `instance/vapid_keys.json` — local dev only, not committed, contains same keys for testing
