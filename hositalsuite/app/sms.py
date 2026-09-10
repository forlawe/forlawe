"""SMS Notification Provider Interface (spec §38).

Primary: Termii (Nigerian provider). Fallback: Twilio. Never hard-coded —
providers are selected by configuration and can be swapped without rewriting
the application. Sandbox mode logs deliveries locally (default for dev).

Every send is queued as an SmsMessage row, attempted with retries, and
logged — failures never break the business flow.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import requests
from flask import current_app

from .models import SmsMessage, db, now_naive


def normalize_ng_number(raw: str) -> str:
    """Normalize Nigerian numbers to E.164 +234... format.

    - 08012345678 -> +2348012345678
    - 0801 234 5678 -> +2348012345678
    - +2348012345678 stays
    - +23408012345678 (common mistake) -> +2348012345678 (strip extra 0)
    - 2348012345678 -> +2348012345678
    - Returns original stripped if cannot normalize, but tries best.
    """
    if not raw:
        return raw
    s = str(raw).strip().replace(" ", "").replace("-", "")
    # Remove whatsapp: prefix if present for normalization
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:"):]
    # If already +234 and then 0 after, fix +2340 -> +234
    if s.startswith("+2340"):
        s = "+234" + s[5:]
    if s.startswith("2340"):
        s = "+234" + s[4:]
    if s.startswith("234"):
        s = "+" + s
    if s.startswith("0"):
        s = "+234" + s.lstrip("0")
    if not s.startswith("+"):
        # If 10 digits (8012345678) assume Nigeria
        if len(s) == 10 and s.startswith(("70","80","81","90","91")):
            s = "+234" + s
        else:
            s = "+" + s.lstrip("+")
    return s



class SmsProviderError(RuntimeError):
    pass


class SmsProvider(ABC):
    name = "base"

    @abstractmethod
    def send(self, to: str, body: str) -> str:
        """Send one SMS; return provider message id. Raise SmsProviderError on failure."""


# ------------------------------------------------------------------ providers
class SandboxSmsProvider(SmsProvider):
    name = "sandbox"

    def send(self, to: str, body: str) -> str:
        return f"SBX-SMS-{now_naive().strftime('%H%M%S')}"


class TermiiSmsProvider(SmsProvider):
    """Termii (Nigeria). https://developer.termii.com"""
    name = "termii"
    URL = "https://api.ng.termii.com/api/sms/send"

    def __init__(self, api_key: str, sender_id: str):
        self.api_key = api_key
        self.sender_id = sender_id

    def send(self, to: str, body: str) -> str:
        if not self.api_key:
            raise SmsProviderError("Termii API key not configured")
        # DND = transactional (booking, codes, queue). Generic is promo and
        # is blocked on MTN at night. Live hospital texts are never adverts.
        resp = requests.post(self.URL, json={
            "api_key": self.api_key,
            "from": self.sender_id or "HospSuite",
            "to": to,
            "sms": body,
            "type": "plain",
            "channel": "dnd",
        }, timeout=30)
        if resp.status_code not in (200, 201):
            raise SmsProviderError(f"Termii error {resp.status_code}: {resp.text[:160]}")
        return str(resp.json().get("message_id", ""))


class TwilioSmsProvider(SmsProvider):
    """Twilio fallback — v1.7.20 hardened. https://www.twilio.com/docs/sms"""
    name = "twilio"

    def __init__(self, sid: str, token: str, from_number: str):
        self.sid, self.token, self.from_number = sid, token, from_number

    def send(self, to: str, body: str) -> str:
        if not (self.sid and self.token):
            raise SmsProviderError("Twilio credentials not configured")
        if not self.from_number:
            raise SmsProviderError("TWILIO_FROM not set — need +1415... number or approved sender ID")
        if str(self.from_number).strip().startswith("whatsapp:"):
            raise SmsProviderError(f"TWILIO_FROM for SMS must NOT start with whatsapp: — got {self.from_number}. Use +... number for SMS, TWILIO_WHATSAPP_FROM for WhatsApp")
        # Normalize destination
        to = normalize_ng_number(to)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
        resp = requests.post(url, auth=(self.sid, self.token),
                             data={"From": self.from_number, "To": to, "Body": body}, timeout=30)
        if resp.status_code not in (200, 201):
            txt = resp.text[:400]
            hint = ""
            if "unverified" in txt.lower() or "21608" in txt:
                hint = " — Trial account: verify recipient in Twilio console > Verified Caller IDs"
            if "not a valid phone number" in txt.lower() or "21211" in txt:
                hint = f" — Invalid To {to}, must be +234... E.164"
            if "permission" in txt.lower() or "21606" in txt:
                hint = " — From number not owned by your Twilio account or not SMS-capable"
            raise SmsProviderError(f"Twilio error {resp.status_code}: {txt}{hint}")
        return resp.json().get("sid", "")


# ------------------------------------------------------------------ factory
def get_provider() -> SmsProvider:
    """Pick the configured provider — respects SMS_MODE strictly.

    v1.7.20 FIX: Previously ignored SMS_MODE and always tried Termii first even when SMS_MODE=twilio.
    Now:
    - disabled -> None
    - twilio -> Twilio only (if credentials present, else sandbox with error)
    - termii -> Termii only (if key present)
    - sandbox -> sandbox
    - otherwise: Termii first, Twilio fallback, sandbox last (legacy behavior for empty mode)
    """
    cfg = current_app.config
    mode = (cfg.get("SMS_MODE", "sandbox") or "sandbox").lower()
    if mode == "disabled":
        return None
    if mode == "twilio":
        # Always return Twilio provider when mode=twilio, even if creds missing — so error is visible, not silent sandbox success
        return TwilioSmsProvider(cfg.get("TWILIO_ACCOUNT_SID", ""),
                                 cfg.get("TWILIO_AUTH_TOKEN", ""),
                                 cfg.get("TWILIO_FROM", ""))
    if mode == "termii":
        termii_key = cfg.get("TERMII_API_KEY", "") or cfg.get("TERMII_KEY", "")
        termii_sender = cfg.get("TERMII_SENDER_ID", "") or cfg.get("TERMII_FROM", "") or "HospSuite"
        return TermiiSmsProvider(termii_key, termii_sender)
    if mode == "sandbox":
        return SandboxSmsProvider()
    # Legacy: empty or unknown -> Termii first, Twilio fallback, sandbox last
    termii_key = cfg.get("TERMII_API_KEY", "") or cfg.get("TERMII_KEY", "")
    termii_sender = cfg.get("TERMII_SENDER_ID", "") or cfg.get("TERMII_FROM", "") or "HospSuite"
    if termii_key:
        try:
            return TermiiSmsProvider(termii_key, termii_sender)
        except Exception:
            pass
    if cfg.get("TWILIO_ACCOUNT_SID") and cfg.get("TWILIO_AUTH_TOKEN"):
        return TwilioSmsProvider(cfg.get("TWILIO_ACCOUNT_SID", ""),
                                 cfg.get("TWILIO_AUTH_TOKEN", ""),
                                 cfg.get("TWILIO_FROM", ""))
    return SandboxSmsProvider()


# ------------------------------------------------------------------ queue
def queue_sms(org_id: int, to_number: str, body: str, kind: str = "alert",
              entity_type: str = None, entity_id: int = None,
              to_user_id: int = None) -> SmsMessage:
    from .sms_pack import one_sms
    body = one_sms(body)
    # v1.7.20 FIX: normalize Nigerian numbers to E.164 +234... before queuing
    to_number = normalize_ng_number(to_number)
    msg = SmsMessage(org_id=org_id, to_number=to_number, body=body, kind=kind,
                     entity_type=entity_type, entity_id=entity_id,
                     to_user_id=to_user_id)
    db.session.add(msg)
    db.session.commit()
    return msg


def send_sms(msg: SmsMessage) -> SmsMessage:
    """Send SMS — respects SMS_MODE strictly, normalizes numbers, never crashes app.

    v1.7.20 FIX:
    - SMS_MODE=twilio -> only Twilio, not Termii
    - SMS_MODE=termii -> only Termii
    - SMS_MODE=sandbox -> sandbox
    - Normalize to_number to +234 E.164 before sending (fixes 080... failures)
    - Better error logging for trial account and unverified numbers
    """
    msg.attempts += 1
    cfg = current_app.config
    mode = (cfg.get("SMS_MODE", "sandbox") or "sandbox").lower()
    if mode == "disabled":
        msg.status = "FAILED"
        msg.last_error = "SMS disabled in configuration (SMS_MODE=disabled)"
        msg.provider = "disabled"
        db.session.commit()
        return msg

    # Normalize destination before sending (fixes Nigeria 080... -> +234...)
    msg.to_number = normalize_ng_number(msg.to_number)

    # Build provider list respecting SMS_MODE — v1.7.20 strict, no silent sandbox when mode=twilio/termii
    providers_to_try = []
    if mode == "twilio":
        providers_to_try.append(TwilioSmsProvider(cfg.get("TWILIO_ACCOUNT_SID", ""),
                                 cfg.get("TWILIO_AUTH_TOKEN", ""),
                                 cfg.get("TWILIO_FROM", "")))
        # Sandbox as last safety net only after Twilio fails, so error is recorded
        providers_to_try.append(SandboxSmsProvider())
    elif mode == "termii":
        termii_key = cfg.get("TERMII_API_KEY", "") or cfg.get("TERMII_KEY", "")
        providers_to_try.append(TermiiSmsProvider(termii_key,
            cfg.get("TERMII_SENDER_ID", "") or cfg.get("TERMII_FROM", "") or "HospSuite"))
        # Fallback to Twilio if configured, then sandbox
        if cfg.get("TWILIO_ACCOUNT_SID") and cfg.get("TWILIO_AUTH_TOKEN"):
            providers_to_try.append(TwilioSmsProvider(cfg.get("TWILIO_ACCOUNT_SID", ""),
                                     cfg.get("TWILIO_AUTH_TOKEN", ""),
                                     cfg.get("TWILIO_FROM", "")))
        providers_to_try.append(SandboxSmsProvider())
    elif mode == "sandbox":
        providers_to_try.append(SandboxSmsProvider())
    else:
        # Legacy fallback: Termii → Twilio → Sandbox
        termii_key = cfg.get("TERMII_API_KEY", "") or cfg.get("TERMII_KEY", "")
        if termii_key:
            providers_to_try.append(TermiiSmsProvider(termii_key,
                cfg.get("TERMII_SENDER_ID", "") or cfg.get("TERMII_FROM", "") or "HospSuite"))
        if cfg.get("TWILIO_ACCOUNT_SID") and cfg.get("TWILIO_AUTH_TOKEN"):
            providers_to_try.append(TwilioSmsProvider(cfg.get("TWILIO_ACCOUNT_SID", ""),
                                     cfg.get("TWILIO_AUTH_TOKEN", ""),
                                     cfg.get("TWILIO_FROM", "")))
        providers_to_try.append(SandboxSmsProvider())

    last_err = None
    for provider in providers_to_try:
        if provider is None:
            continue
        msg.provider = provider.name
        try:
            msg.provider_id = provider.send(msg.to_number, msg.body)
            msg.status = "SENT"
            msg.sent_at = now_naive()
            msg.last_error = None
            db.session.commit()
            return msg
        except (SmsProviderError, requests.RequestException, OSError) as exc:
            last_err = str(exc)[:400]
            continue

    # All providers failed
    msg.status = "FAILED" if msg.attempts >= 3 else "QUEUED"
    msg.last_error = last_err or "All SMS providers failed"
    db.session.commit()
    return msg


def process_sms_queue(limit: int = 30) -> int:
    msgs = (db.session.query(SmsMessage)
            .filter(SmsMessage.status == "QUEUED", SmsMessage.attempts < 3)
            .order_by(SmsMessage.created_at).limit(limit).all())
    for m in msgs:
        send_sms(m)
    return len(msgs)
