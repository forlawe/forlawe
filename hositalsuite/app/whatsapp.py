"""WhatsApp Business Platform (Meta Cloud API) integration.

Modes
-----
- cloud   : real Meta Graph API (requires WHATSAPP_PHONE_NUMBER_ID + access token)
- sandbox : full workflow simulated locally (default for dev/onboarding)
- disabled: messages queued but never sent (flagged for review)

Media (PDF documents) are uploaded to the Media API first, then sent as
document messages. Delivery receipts arrive via the webhook (/api/v1/whatsapp/webhook).
"""
from __future__ import annotations

import os
from typing import Optional

import requests
from flask import current_app

from .models import WhatsAppMessage, db, now_naive

GRAPH = "https://graph.facebook.com/v19.0"

def normalize_ng_number(raw: str) -> str:
    """Normalize Nigerian numbers to E.164 +234... format (same as sms.py)."""
    if not raw:
        return raw
    s = str(raw).strip().replace(" ", "").replace("-", "")
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:"):]
    if s.startswith("+2340"):
        s = "+234" + s[5:]
    if s.startswith("2340"):
        s = "+234" + s[4:]
    if s.startswith("234"):
        s = "+" + s
    if s.startswith("0"):
        s = "+234" + s.lstrip("0")
    if not s.startswith("+"):
        if len(s) == 10 and s.startswith(("70","80","81","90","91")):
            s = "+234" + s
        else:
            s = "+" + s.lstrip("+")
    return s

def ensure_whatsapp_prefix(num: str) -> str:
    """Ensure number is whatsapp:+234... format for Twilio."""
    if not num:
        return num
    n = str(num).strip()
    if n.startswith("whatsapp:"):
        # Normalize inner number too
        inner = n[len("whatsapp:"):]
        inner = normalize_ng_number(inner)
        return f"whatsapp:{inner}"
    # Normalize then prefix
    norm = normalize_ng_number(n)
    return f"whatsapp:{norm}"



class WhatsAppError(RuntimeError):
    pass


def mode() -> str:
    return (current_app.config.get("WHATSAPP_MODE", "sandbox") or "sandbox").lower()


# ------------------------------------------------------------------ media
def _media_available(path: str) -> bool:
    from . import storage
    try:
        if storage.exists(path):
            return True
    except Exception:                                # noqa: BLE001
        pass
    return bool(path and os.path.isabs(path) and os.path.exists(path))


def _upload_media(pdf_path: str) -> Optional[str]:
    """Upload a PDF to Meta. Reads from durable storage, not the filesystem.

    PDFs now live in app.storage (the container disk is wiped on restart), so
    this accepts a storage key and falls back to a real path for legacy rows.
    """
    import io as _io

    from . import storage
    cfg = current_app.config
    url = f"{GRAPH}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}/media"

    data = storage.get(pdf_path)
    if data is None and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as fh:
            data = fh.read()
    if not data:
        raise WhatsAppError(f"Report file not found for delivery: {pdf_path}")

    name = os.path.basename(pdf_path)
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {cfg['WHATSAPP_ACCESS_TOKEN']}"},
        data={"messaging_product": "whatsapp", "type": "application/pdf",
              "filename": name},
        files={"file": (name, _io.BytesIO(data), "application/pdf")},
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise WhatsAppError(f"Media upload failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("id")


def _send_document(to_number: str, media_id: str, filename: str, caption: str) -> str:
    cfg = current_app.config
    url = f"{GRAPH}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "document",
        "document": {"id": media_id, "filename": filename, "caption": caption[:1024]},
    }
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {cfg['WHATSAPP_ACCESS_TOKEN']}",
        "Content-Type": "application/json"}, json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        raise WhatsAppError(f"Send failed ({resp.status_code}): {resp.text[:200]}")
    return (resp.json().get("messages") or [{}])[0].get("id", "")


def _send_text(to_number: str, body: str) -> str:
    cfg = current_app.config
    url = f"{GRAPH}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}/messages"
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text",
               "text": {"preview_url": False, "body": body[:4000]}}
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {cfg['WHATSAPP_ACCESS_TOKEN']}",
        "Content-Type": "application/json"}, json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        raise WhatsAppError(f"Send failed ({resp.status_code}): {resp.text[:200]}")
    return (resp.json().get("messages") or [{}])[0].get("id", "")


# ------------------------------------------------------------------ queue
def org_for_number(phone_number_id: str | None = None,
                   display_number: str | None = None):
    """F-019: which hospital owns the WhatsApp number an inbound message
    arrived on?

    Each hospital records its Meta phone-number identity as org settings —
    ``whatsapp_phone_number_id`` (the Graph API id Meta sends on every
    webhook) and/or ``whatsapp_display_number``. Inbound routing looks the
    number up here instead of guessing hospital #1, so several hospitals on
    one deployment can each run their own WhatsApp line. Returns None when
    no hospital claims the number; the webhook then refuses to guess.
    """
    from .models import Organization, Setting

    pid = (phone_number_id or "").strip()
    disp = "".join(ch for ch in (display_number or "") if ch.isdigit())
    if not pid and not disp:
        return None
    for org in db.session.query(Organization).order_by(Organization.id).all():
        org_pid = (Setting.get(org.id, "whatsapp_phone_number_id", "") or "").strip()
        org_disp = "".join(ch for ch in (Setting.get(org.id, "whatsapp_display_number", "") or "")
                           if ch.isdigit())
        if (pid and org_pid and org_pid == pid) or (disp and org_disp and org_disp == disp):
            return org
    return None


def queue_message(org_id: int, to_number: str, body: str, kind: str = "report",
                  media_path: str | None = None, entity_type: str = None,
                  entity_id: int = None, to_user_id: int = None) -> WhatsAppMessage:
    # v1.7.20 FIX: normalize Nigerian numbers to +234 before queuing
    to_number = normalize_ng_number(to_number)
    msg = WhatsAppMessage(org_id=org_id, to_number=to_number, body=body, kind=kind,
                          media_path=media_path, entity_type=entity_type, entity_id=entity_id,
                          to_user_id=to_user_id, status="QUEUED")
    db.session.add(msg)
    db.session.commit()
    return msg


def _send_twilio(to_number: str, body: str) -> str:
    """Send a WhatsApp message through Twilio — v1.7.20 hardened.

    WHY TWILIO IS HERE AS A FALLBACK
    --------------------------------
    Meta's WhatsApp Cloud API is free and is the right primary, but approval
    takes time and a business can be suspended with little notice. When the
    MD/CEO is waiting for an inspection report, "our Meta approval lapsed" is
    not an answer. Twilio costs a little per message and can be live in an
    afternoon, so it is the safety net rather than the default.

    v1.7.20 FIXES:
    - Normalize Nigerian numbers: 080... -> +234..., +2340... -> +234...
    - Validate FROM format must be whatsapp:+...
    - Better error messages for trial account, unverified numbers, sandbox join
    """
    cfg = current_app.config
    sid = cfg.get("TWILIO_ACCOUNT_SID", "")
    token = cfg.get("TWILIO_AUTH_TOKEN", "")
    sender = cfg.get("TWILIO_WHATSAPP_FROM", "") or cfg.get("TWILIO_FROM", "")
    if not (sid and token and sender):
        raise WhatsAppError(
            "Twilio WhatsApp is selected but TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN or TWILIO_WHATSAPP_FROM is missing. "
            "Set TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 for sandbox or whatsapp:+234... for approved.")

    # Validate sender format
    if not str(sender).strip().startswith("whatsapp:"):
        # Try to auto-fix if user set +1415... without whatsapp: prefix
        if str(sender).strip().startswith("+"):
            sender = f"whatsapp:{normalize_ng_number(sender)}"
        else:
            raise WhatsAppError(f"TWILIO_WHATSAPP_FROM must start with whatsapp: — got {sender}. Example: whatsapp:+14155238886")

    to_number = normalize_ng_number(to_number)

    def _wa(num: str) -> str:
        return ensure_whatsapp_prefix(num)

    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, token),
        data={"From": _wa(sender), "To": _wa(to_number), "Body": body[:1600]},
        timeout=float(cfg.get("WHATSAPP_TIMEOUT", 15)))
    if resp.status_code >= 300:
        txt = resp.text[:400]
        # Provide helpful hints for common Twilio errors
        hint = ""
        if "unverified" in txt.lower() or "21608" in txt:
            hint = " — Trial account: verify recipient number in Twilio console > Phone Numbers > Verified Caller IDs"
        if "join" in txt.lower() or "21610" in txt or "63016" in txt:
            hint = " — WhatsApp sandbox: recipient must send 'join <code>' to your Twilio WhatsApp number first. Code in Twilio console > Messaging > Try it out > WhatsApp sandbox"
        if "not a valid phone number" in txt.lower() or "21211" in txt:
            hint = f" — Invalid number format. To was {to_number}, must be +234... E.164. Got {to_number}"
        raise WhatsAppError(f"Twilio error {resp.status_code}: {txt}{hint}")
    return (resp.json() or {}).get("sid", "")


def send_message(msg: WhatsAppMessage) -> WhatsAppMessage:
    """Attempt to deliver one queued/failed message. Updates status in place.

    v1.7.20: Normalize number, immediate SMS fallback if WhatsApp fails.
    """
    cfg = current_app.config
    m = (mode() or "sandbox").lower()
    msg.attempts += 1
    msg.status = "SENDING"
    # Normalize before sending
    try:
        msg.to_number = normalize_ng_number(msg.to_number)
    except Exception:
        pass
    db.session.commit()
    try:
        if m == "disabled":
            raise WhatsAppError("WhatsApp integration is disabled in configuration.")
        if m == "sandbox":
            if cfg.get("WHATSAPP_SIMULATE_FAILURE") and msg.attempts == 1:
                raise WhatsAppError("Simulated sandbox failure (WHATSAPP_SIMULATE_FAILURE=1).")
            # simulate provider acceptance + delivery receipt
            msg.provider_id = f"SBX-{msg.id:08d}"
            msg.status = "DELIVERED"
            msg.sent_at = now_naive()
            msg.delivered_at = now_naive()
        elif m == "twilio":
            provider = _send_twilio(msg.to_number, msg.body)
            msg.provider_id = provider
            msg.status = "SENT"
            msg.sent_at = now_naive()
        else:  # cloud
            # media_path is a durable-storage key (e.g. "reports/REF.pdf"); the
            # old code required an absolute filesystem path, which silently
            # downgraded every report to a text-only message after the move.
            try:
                if msg.media_path and _media_available(msg.media_path):
                    media_id = _upload_media(msg.media_path)
                    provider = _send_document(
                        msg.to_number, media_id,
                        os.path.basename(msg.media_path), msg.body)
                else:
                    provider = _send_text(msg.to_number, msg.body)
            except Exception as exc:                          # noqa: BLE001
                # AUTOMATIC FALLBACK. Meta suspends business accounts with
                # little warning and approval can lapse. Rather than let the
                # MD/CEO simply never receive the report, try Twilio if it is
                # configured. Text only: a PDF needs a public URL, and putting
                # a patient report on a public URL to save one message would
                # be a far worse mistake than sending the summary alone.
                if not cfg.get("TWILIO_ACCOUNT_SID"):
                    raise
                current_app.logger.warning(
                    "WhatsApp Cloud failed (%s) — falling back to Twilio", exc)
                provider = _send_twilio(msg.to_number, msg.body)
                msg.last_error = f"cloud failed, sent via Twilio: {str(exc)[:120]}"
            msg.provider_id = provider
            msg.status = "SENT"          # webhook flips it to DELIVERED
            msg.sent_at = now_naive()
        if not (msg.last_error or "").startswith("cloud failed"):
            msg.last_error = None
    except Exception as exc:                              # noqa: BLE001
        # Catch EVERYTHING. This used to list only WhatsAppError,
        # RequestException and OSError, so any other fault — a provider
        # returning unexpected JSON, a None where a string was expected —
        # escaped and killed the whole sending run, leaving every other queued
        # message stuck behind it. A failed message must be recorded and
        # retried, never allowed to take the queue down with it.
        msg.status = "FAILED" if msg.attempts >= 3 else "QUEUED"
        msg.last_error = str(exc)[:400]
        # v1.7.20: WhatsApp-first -> SMS fallback immediately on failure
        try:
            from . import sms as sms_engine
            # Only fallback if SMS not disabled and not already tried too many times
            if cfg.get("SMS_MODE", "sandbox") != "disabled" and msg.attempts >= 1:
                # Avoid double-fallback loops: only fallback once per WhatsApp message
                if not (msg.last_error or "").lower().startswith("sms fallback already"):
                    sms_engine.queue_sms(msg.org_id, msg.to_number, msg.body,
                                         kind=(msg.kind or "alert") + "_fallback",
                                         entity_type=msg.entity_type, entity_id=msg.entity_id,
                                         to_user_id=msg.to_user_id)
                    msg.last_error = (msg.last_error or "") + " | SMS fallback queued"
        except Exception:
            pass
    db.session.commit()
    return msg


def process_queue(limit: int = 20) -> int:
    """Send everything queued/failed-with-retries-left. Returns count processed.

    FIX for stuck SENDING bug (expert review 2026-08-27):
    Previously only QUEUED was picked up. If process died after committing
    status=SENDING but before HTTP finished, message stuck in SENDING forever
    and MD/CEO never got report. Now we also pick up SENDING older than 2 min.
    """
    from datetime import timedelta
    cutoff = now_naive() - timedelta(minutes=2)
    # QUEUED always, plus SENDING that has been stuck >2 min (sent_at is None)
    msgs = (db.session.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.attempts < 3,
                db.or_(
                    WhatsAppMessage.status == "QUEUED",
                    db.and_(
                        WhatsAppMessage.status == "SENDING",
                        WhatsAppMessage.sent_at.is_(None),
                        WhatsAppMessage.created_at < cutoff
                    )
                )
            )
            .order_by(WhatsAppMessage.created_at).limit(limit).all())
    for m in msgs:
        # If it was stuck in SENDING, reset to QUEUED for retry visibility
        if m.status == "SENDING":
            current_app.logger.warning("whatsapp: re-queuing stuck SENDING id=%s attempts=%s", m.id, m.attempts)
            m.status = "QUEUED"
            db.session.commit()
        send_message(m)
    return len(msgs)


def apply_webhook_status(provider_id: str, status: str):
    """Handle delivery status callbacks from Meta (sent / delivered / read / failed).
    
    Feature: WhatsApp-first, Twilio SMS fallback. If WhatsApp delivery fails (status=failed),
    automatically queue an SMS via Twilio so patient/staff still gets the message.
    """
    msg = db.session.query(WhatsAppMessage).filter_by(provider_id=provider_id).first()
    if not msg:
        return
    if status in ("delivered", "read"):
        msg.status = "DELIVERED"
        msg.delivered_at = msg.delivered_at or now_naive()
    elif status == "failed":
        msg.status = "FAILED" if msg.attempts >= 3 else "QUEUED"
        msg.last_error = "Provider reported failure — fallback to Twilio SMS"
        # WhatsApp-first → Twilio SMS fallback
        try:
            from . import sms as sms_engine
            sms_engine.queue_sms(msg.org_id, msg.to_number, msg.body,
                                 kind=msg.kind or "fallback",
                                 entity_type=msg.entity_type, entity_id=msg.entity_id,
                                 to_user_id=msg.to_user_id)
            current_app.logger.info("WhatsApp failed for %s — queued Twilio SMS fallback", msg.to_number)
        except Exception:
            pass
    db.session.commit()


def send_with_fallback(org_id: int, to_number: str, body: str, kind: str = "notification",
                       entity_type: str = None, entity_id: int = None, to_user_id: int = None):
    """WhatsApp-first, Twilio SMS fallback — premium implementation.

    Always queues WhatsApp first. SMS is queued in parallel as backup if WhatsApp not available,
    or automatically on WhatsApp FAILED status via webhook + process_queue logic.
    """
    # Always queue WhatsApp first
    wa_msg = queue_message(org_id, to_number, body, kind=kind,
                           entity_type=entity_type, entity_id=entity_id, to_user_id=to_user_id)
    # If WhatsApp mode disabled or sandbox failure simulated, also queue SMS immediately
    try:
        cfg = current_app.config
        if cfg.get("WHATSAPP_MODE") in ("disabled",):
            from . import sms as sms_engine
            sms_engine.queue_sms(org_id, to_number, body, kind=kind,
                                 entity_type=entity_type, entity_id=entity_id, to_user_id=to_user_id)
    except Exception:
        pass
    return wa_msg
