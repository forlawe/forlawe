"""Send real email. Render blocks ordinary SMTP, so we prefer a web API.

WHY THE OLD PATH FAILED
-----------------------
The app only knew how to talk SMTP (port 587). On Render's free web box that
port is usually blocked, and SMTP_HOST was never set, so every activation
mail returned \"SMTP not configured\" and the person saw nothing.

WHAT THIS DOES
--------------
Tries, in order: Resend → Brevo → SendGrid → SMTP.
All of the first three use ordinary HTTPS (not blocked).
Returns (ok, detail). Never raises. Never logs the 6-digit code.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


def _cfg() -> dict:
    from flask import current_app
    return current_app.config


def _secret(name: str) -> str:
    """Read a key NOW, not the copy taken when the app first started.

    Render can show the *name* of a setting while the *value* is still
    blank. We also strip spaces/newlines people paste by accident.
    """
    env = (os.environ.get(name) or "").strip().strip('"').strip("'")
    if env:
        return env
    try:
        return str(_cfg().get(name) or "").strip().strip('"').strip("'")
    except Exception:  # noqa: BLE001
        return ""


def from_address() -> str:
    raw = _secret("MAIL_FROM") or _secret("SMTP_FROM")
    if raw.endswith("@localhost"):
        return ""
    return raw


def active_provider() -> str:
    """Which van will carry the letter. 'off' means nothing is set up.

    Brevo first: that is the van this hospital already paid for.
    """
    if _secret("BREVO_API_KEY"):
        return "brevo"
    if _secret("RESEND_API_KEY"):
        return "resend"
    if _secret("SENDGRID_API_KEY"):
        return "sendgrid"
    if _secret("SMTP_HOST"):
        return "smtp"
    return "off"


def is_configured() -> bool:
    if active_provider() == "off":
        return False
    addr = from_address()
    if active_provider() != "smtp" and (not addr or addr.endswith("@localhost")):
        return False
    return True


def _brevo_key_shape() -> str:
    """Does the stored secret look like a real Brevo API key? Never returns the key."""
    k = _secret("BREVO_API_KEY")
    if not k:
        return "empty"
    if k.startswith("xkeysib-") and len(k) >= 40:
        return "ok"
    if k.startswith("xkeysib-"):
        return "short"
    return "wrong_kind"


def status() -> dict[str, Any]:
    provider = active_provider()
    return {
        "provider": provider,
        "configured": is_configured(),
        "from": from_address() or None,
        "seen": {
            "brevo": bool(_secret("BREVO_API_KEY")),
            "resend": bool(_secret("RESEND_API_KEY")),
            "sendgrid": bool(_secret("SENDGRID_API_KEY")),
            "smtp": bool(_secret("SMTP_HOST")),
            "mail_from": bool(from_address()),
        },
        "brevo_key_shape": _brevo_key_shape(),
    }


def _html_wrap(subject: str, text: str) -> str:
    # Keep the 6-digit code big. No remote images (many inboxes block them).
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    paragraphs = "".join(f"<p style=\"margin:0 0 12px;line-height:1.45\">{p}</p>"
                         for p in safe.split("\n") if p.strip())
    return (
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;"
        "background:#f2f5f8;padding:24px\">"
        "<div style=\"max-width:480px;margin:0 auto;background:#fff;"
        "border-radius:12px;padding:24px;color:#152433\">"
        f"<h1 style=\"font-size:18px;margin:0 0 16px\">{subject}</h1>"
        f"{paragraphs}"
        "<p style=\"margin:20px 0 0;color:#5b6b7c;font-size:13px\">"
        "If you did not ask for this, ignore it.</p>"
        "</div></body></html>"
    )


def _emphasize_code(text: str) -> str:
    """If the body has a 6-digit code, print it huge in the HTML."""
    import re
    html = _html_wrap("Your hospital code", text)
    m = re.search(r"\b(\d{6})\b", text or "")
    if m:
        code = m.group(1)
        banner = (
            f"<div style=\"font-size:32px;letter-spacing:8px;font-weight:800;"
            f"text-align:center;padding:16px 0;color:#0e5a8a\">{code}</div>"
        )
        html = html.replace("</h1>", "</h1>" + banner, 1)
    return html


def send_mail(to: str, subject: str, text: str, *, html: str | None = None) -> tuple[bool, str]:
    """Send one letter. (True, 'resend') or (False, 'plain reason')."""
    to = (to or "").strip()
    if not to or "@" not in to:
        return False, "No email address"
    provider = active_provider()
    if provider == "off":
        return False, "Mail van is not set up (no Resend / Brevo / SendGrid / SMTP key)"
    sender = from_address()
    if provider != "smtp" and (not sender or sender.endswith("@localhost")):
        return False, "MAIL_FROM is missing. Put the address you verified with the mail company."
    body_html = html or _emphasize_code(text)
    try:
        if provider == "resend":
            return _via_resend(sender, to, subject, text, body_html)
        if provider == "brevo":
            return _via_brevo(sender, to, subject, text, body_html)
        if provider == "sendgrid":
            return _via_sendgrid(sender, to, subject, text, body_html)
        return _via_smtp(sender, to, subject, text, body_html)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:240]


def _via_resend(sender, to, subject, text, html) -> tuple[bool, str]:
    import requests
    key = _secret("RESEND_API_KEY")
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"from": sender, "to": [to], "subject": subject, "text": text, "html": html},
        timeout=20,
    )
    if r.status_code in (200, 201):
        return True, "resend"
    return False, f"Resend said {r.status_code}: {(r.text or '')[:180]}"


def _via_brevo(sender, to, subject, text, html) -> tuple[bool, str]:
    import requests
    key = _secret("BREVO_API_KEY")
    name, email = _split_from(sender)
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": key, "Content-Type": "application/json"},
        json={
            "sender": {"email": email, "name": name or "Hospital"},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": text,
            "htmlContent": html,
        },
        timeout=20,
    )
    if r.status_code in (200, 201, 202):
        return True, "brevo"
    body = (r.text or "")[:180]
    if r.status_code in (401, 403) and "key not found" in body.lower():
        return False, (
            "Brevo does not recognise this key. On Brevo open SMTP & API → "
            "API keys & MCP (not the SMTP tab) → Generate API key → copy the "
            "long line that starts with xkeysib- from the popup (only shown "
            "once). Paste that whole line into Render BREVO_API_KEY. Do not "
            "copy the dots of an old key. Do not tap Activate for API keys."
        )
    return False, f"Brevo said {r.status_code}: {body}"


def _via_sendgrid(sender, to, subject, text, html) -> tuple[bool, str]:
    import requests
    key = _secret("SENDGRID_API_KEY")
    name, email = _split_from(sender)
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": email, "name": name or "Hospital"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text},
                {"type": "text/html", "value": html},
            ],
        },
        timeout=20,
    )
    if r.status_code in (200, 201, 202):
        return True, "sendgrid"
    return False, f"SendGrid said {r.status_code}: {(r.text or '')[:180]}"


def _via_smtp(sender, to, subject, text, html) -> tuple[bool, str]:
    cfg = _cfg()
    host = cfg.get("SMTP_HOST")
    port = int(cfg.get("SMTP_PORT") or 587)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as s:
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD") or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo()
            if cfg.get("SMTP_TLS", True):
                s.starttls()
                s.ehlo()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD") or "")
            s.send_message(msg)
    return True, "smtp"


def _split_from(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if "<" in raw and ">" in raw:
        name = raw.split("<", 1)[0].strip().strip('"')
        email = raw.split("<", 1)[1].split(">", 1)[0].strip()
        return name, email
    return "", raw
