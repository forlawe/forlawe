# SECURITY INCIDENT — VAPID private key exposed in a repository document

**Date discovered / remediated:** 2026-09-03
**Severity:** HIGH (push-channel private key in plaintext, in a committed file)
**Status:** key removed from the working tree — **ROTATION IS STILL REQUIRED** (manual step, needs Render dashboard access)

---

## What happened

`HOSPITAL_ASSISTANT_WORLD_CLASS_REPORT.md` (written as part of the chatbot/PWA
build) recorded the generated VAPID keypair in plaintext, including the
**private** key. The same patchset added `instance/`, `vapid_keys.json`,
`*.pem`, `*.key` to `.gitignore` — so the runtime file was protected, but the
markdown report itself was committed, which defeats the point. An independent
review caught this.

A VAPID **private** key signs every web-push request. Anyone who has it can
send push notifications to this hospital's subscribers **as this hospital**
(phishing a patient into a fake "your appointment changed" page is the obvious
attack). Treat any key that has ever been in a commit as compromised.

## What has already been fixed (code)

| Fix | Where |
|---|---|
| Private + public key redacted from the report, replaced with placeholders | `HOSPITAL_ASSISTANT_WORLD_CLASS_REPORT.md` |
| Push sender now deactivates subscriptions rejected with **403/404**, not only 410 — this is what makes a key rotation self-heal (old subscriptions die on first send; browsers re-subscribe with the new key on next visit) | `app/push.py::send_push_to_subscription` |
| Regression test scanning every tracked file for the leaked key material and for plaintext PEM private keys / hardcoded-length secrets in docs | `tests/test_secrets_hygiene.py` |
| Guardrail honesty fix (same review): the chatbot privacy/injection filter is now layered + adversarially tested, and docs no longer claim it is more than a best-effort prefilter | `app/chatbot/engine.py`, `tests/test_chatbot_guardrails_adversarial.py`, `PHASES_STATUS.md` |

## What YOU must do (no code can do this for you)

### 1. Rotate the VAPID keypair

The old key is in git history and possibly cloned by others. Do not reuse it.

1. On any machine with Python: `python -c "from pywebpush import webpush; ..."` is overkill — the app can do it: temporarily clear the env vars and boot once with the `instance/` folder writable; the auto-generator in `app/push.py::_ensure_global_vapid` prints and saves a fresh pair. **Simplest reliable path:** run the bundled generator locally:
   ```bash
   python -c "from app.push import generate_vapid_keys; pub, priv = generate_vapid_keys(); print('VAPID_PUBLIC_KEY=' + pub); print('VAPID_PRIVATE_KEY=' + priv)"
   ```
2. Render → your service → Environment → set:
   - `VAPID_PUBLIC_KEY` = new public key
   - `VAPID_PRIVATE_KEY` = new private key
3. If any per-org VAPID was configured in `/admin/settings` **and** matches the old key, update it the same way.
4. Redeploy. Push subscriptions made under the old key will fail once with 403
   and are deactivated automatically; each browser re-subscribes the next time
   the user opens the app. No patient action needed.

### 2. Scrub git history (recommended)

Removing the key from the latest commit does **not** remove it from history.

- Preferred: rotate (step 1) makes the leaked value worthless, then history
  rewriting is optional hygiene.
- If you still want it gone: use `git filter-repo` (or BFG) to purge the file
  content, force-push, and have all clones re-clone. GitHub Support can also
  clear cached views. Coordinate with anyone holding a clone first.

### 3. Verify

- `pytest tests/test_secrets_hygiene.py` must pass (it fails if the key text or
  any PEM private key reappears in a tracked file).
- After redeploy: `/api/v1/health` shows `"push_configured": true, "push_mode": "vapid"`.
- Send one test push from the admin panel and confirm it arrives.

## Prevention (what made this possible)

The root process failure: **one giant self-graded patchset** spanning auth,
migrations, features and its own "100% complete ✅" reports. That is exactly
where a secret slips into prose and nobody notices. Going forward:

- Secrets live **only** in the platform's secret store (Render env). Never in
  any file — reports included. Docs reference env var **names**, never values.
- Before every push: `pytest tests/test_secrets_hygiene.py` (or wire it into CI).
- Keep PRs small and reviewed by someone other than the author.
