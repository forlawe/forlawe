"""Twilio diagnostic — why SMS/WhatsApp not working, premium check."""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request, flash, redirect, url_for
from flask_login import current_user
from ..security import require_role

bp = Blueprint("twilio_diag", __name__)

SUPER = ("SUPER_ADMIN",)

def _mask(val: str) -> str:
    if not val:
        return "❌ NOT SET"
    if len(val) <= 8:
        return val[:2] + "***" + val[-2:]
    return val[:4] + "***" + val[-4:] + f" (len {len(val)})"

@bp.get("/admin/twilio-check")
@require_role(*SUPER)
def check():
    cfg = current_app.config
    # Current values
    data = {
        "SMS_MODE": cfg.get("SMS_MODE", ""),
        "WHATSAPP_MODE": cfg.get("WHATSAPP_MODE", ""),
        "TWILIO_ACCOUNT_SID": cfg.get("TWILIO_ACCOUNT_SID", ""),
        "TWILIO_AUTH_TOKEN": cfg.get("TWILIO_AUTH_TOKEN", ""),
        "TWILIO_FROM": cfg.get("TWILIO_FROM", ""),
        "TWILIO_WHATSAPP_FROM": cfg.get("TWILIO_WHATSAPP_FROM", ""),
        "TERMII_API_KEY": cfg.get("TERMII_API_KEY", ""),
        "TERMII_SENDER_ID": cfg.get("TERMII_SENDER_ID", ""),
        "WHATSAPP_PHONE_NUMBER_ID": cfg.get("WHATSAPP_PHONE_NUMBER_ID", ""),
        "WHATSAPP_ACCESS_TOKEN": cfg.get("WHATSAPP_ACCESS_TOKEN", ""),
    }

    checks = []

    # SMS_MODE
    sms_mode = data["SMS_MODE"]
    if sms_mode == "sandbox":
        checks.append(("SMS_MODE = sandbox", "⚠️ You are in sandbox — no real SMS sent. Set SMS_MODE=twilio in Render Environment to send real SMS via Twilio.", "warn"))
    elif sms_mode == "twilio":
        checks.append(("SMS_MODE = twilio", "✅ Correct for Twilio SMS", "ok"))
    elif sms_mode == "termii":
        checks.append(("SMS_MODE = termii", "ℹ️ Termii primary, Twilio fallback if Termii key missing", "ok"))
    elif sms_mode == "disabled":
        checks.append(("SMS_MODE = disabled", "❌ SMS disabled — no messages will ever send", "fail"))
    else:
        checks.append((f"SMS_MODE = {sms_mode}", "❓ Unknown mode — should be sandbox, twilio, termii, or disabled", "fail"))

    # WHATSAPP_MODE
    wa_mode = data["WHATSAPP_MODE"]
    if wa_mode == "sandbox":
        checks.append(("WHATSAPP_MODE = sandbox", "⚠️ Sandbox — WhatsApp simulated, not real. Set WHATSAPP_MODE=twilio for Twilio WhatsApp, or cloud for Meta Cloud API.", "warn"))
    elif wa_mode == "twilio":
        checks.append(("WHATSAPP_MODE = twilio", "✅ Correct for Twilio WhatsApp", "ok"))
    elif wa_mode == "cloud":
        checks.append(("WHATSAPP_MODE = cloud", "✅ Meta Cloud API — needs WHATSAPP_PHONE_NUMBER_ID + WHATSAPP_ACCESS_TOKEN", "ok"))
    else:
        checks.append((f"WHATSAPP_MODE = {wa_mode}", "❓ Should be sandbox, twilio, cloud, or disabled", "fail"))

    # TWILIO_ACCOUNT_SID
    sid = data["TWILIO_ACCOUNT_SID"]
    if not sid:
        checks.append(("TWILIO_ACCOUNT_SID missing", "❌ Not set — Twilio cannot work without it. Get it from twilio.com/console", "fail"))
    elif not sid.startswith("AC"):
        checks.append((f"TWILIO_ACCOUNT_SID = {_mask(sid)}", "❌ Should start with AC — you may have pasted Auth Token in SID field", "fail"))
    else:
        checks.append((f"TWILIO_ACCOUNT_SID = {_mask(sid)}", "✅ Looks like valid SID format (starts with AC)", "ok"))

    # AUTH TOKEN
    if not data["TWILIO_AUTH_TOKEN"]:
        checks.append(("TWILIO_AUTH_TOKEN missing", "❌ Not set — needed for Twilio", "fail"))
    else:
        checks.append((f"TWILIO_AUTH_TOKEN = {_mask(data['TWILIO_AUTH_TOKEN'])}", "✅ Set (masked)", "ok"))

    # FROM
    tw_from = data["TWILIO_FROM"]
    if not tw_from:
        checks.append(("TWILIO_FROM missing", "❌ Not set — Twilio needs a From number you own, e.g. +1415... or approved sender ID", "fail"))
    else:
        if tw_from.startswith("whatsapp:"):
            checks.append((f"TWILIO_FROM = {tw_from}", "⚠️ For SMS, FROM should NOT start with whatsapp: — that's for WhatsApp. Use +1415... number for SMS, and TWILIO_WHATSAPP_FROM for WhatsApp", "warn"))
        elif not tw_from.startswith("+") and not tw_from.isalnum():
            checks.append((f"TWILIO_FROM = {tw_from}", "⚠️ Should be E.164 +... or alphanumeric sender ID", "warn"))
        else:
            checks.append((f"TWILIO_FROM = {tw_from}", "✅ Set", "ok"))

    # WHATSAPP FROM
    wa_from = data["TWILIO_WHATSAPP_FROM"]
    if data["WHATSAPP_MODE"] == "twilio" and not wa_from:
        # fallback to TWILIO_FROM allowed but not ideal
        if tw_from and tw_from.startswith("+"):
            checks.append(("TWILIO_WHATSAPP_FROM missing but TWILIO_FROM present", "⚠️ Will fallback to TWILIO_FROM, but better set TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 (sandbox) or your approved WhatsApp number", "warn"))
        else:
            checks.append(("TWILIO_WHATSAPP_FROM missing", "❌ For Twilio WhatsApp you need whatsapp:+14155238886 (sandbox) or your approved number", "fail"))
    elif wa_from:
        if not wa_from.startswith("whatsapp:"):
            checks.append((f"TWILIO_WHATSAPP_FROM = {wa_from}", "❌ Must start with whatsapp: — e.g. whatsapp:+14155238886", "fail"))
        else:
            checks.append((f"TWILIO_WHATSAPP_FROM = {wa_from}", "✅ Correct format (whatsapp:+...)", "ok"))

    # Common Nigeria mistakes
    checks.append(("Nigeria number format", "ℹ️ To numbers must be +234... not 080... and not +2340... Example: 08012345678 → +2348012345678", "info"))
    checks.append(("Twilio trial account", "ℹ️ Trial accounts can only send to verified numbers. Verify your phone in Twilio console > Verified Caller IDs", "info"))
    checks.append(("WhatsApp sandbox join", "ℹ️ For Twilio WhatsApp sandbox, recipient must first send 'join <code>' to your Twilio WhatsApp number (e.g. join bright-hour). Code shown in Twilio console > Messaging > Try it out > WhatsApp sandbox", "info"))
    checks.append(("Render env vars", "ℹ️ On Render, set env vars in Dashboard > hospital-suite > Environment > Add. After Save, wait 2-3 min for restart", "info"))

    # Recent failures
    recent_sms = []
    recent_wa = []
    try:
        from ..models import SmsMessage, WhatsAppMessage
        recent_sms = (WhatsAppMessage.__table__  # dummy to avoid unused
                      and __import__('app.models', fromlist=['SmsMessage']).SmsMessage)
        from ..models import SmsMessage, WhatsAppMessage, db
        recent_sms = (db.session.query(SmsMessage).filter_by(org_id=current_user.org_id)
                      .order_by(SmsMessage.created_at.desc()).limit(5).all())
        recent_wa = (db.session.query(WhatsAppMessage).filter_by(org_id=current_user.org_id)
                     .order_by(WhatsAppMessage.created_at.desc()).limit(5).all())
    except Exception:
        recent_sms = []
        recent_wa = []

    return render_template("admin/twilio_check.html", data=data, checks=checks,
                           recent_sms=recent_sms, recent_wa=recent_wa, mask=_mask)

@bp.get("/admin/twilio-templates")
@require_role(*SUPER)
def templates_page():
    """Copy-paste ready templates for Termii & Twilio — accessible"""
    from .. import sms_pack
    from pathlib import Path
    # Load markdown file if exists
    md_path = Path(__file__).parent.parent.parent / "SMS_WHATSAPP_TEMPLATES_COPY_PASTE.md"
    md_content = ""
    try:
        md_content = md_path.read_text(encoding="utf-8")
    except Exception:
        md_content = "Templates file not found — see app/sms_pack.py"
    # Get samples
    try:
        samples = sms_pack.samples(tag="GHIJEDE", phone="08031234567")
    except Exception:
        samples = []
    return render_template("admin/twilio_templates.html", md_content=md_content, samples=samples)


@bp.post("/admin/twilio-check/test-sms")
@require_role(*SUPER)
def test_sms():
    to = (request.form.get("to") or "").strip()
    if not to:
        flash("Enter destination number, e.g. +2348012345678", "error")
        return redirect(url_for("twilio_diag.check"))
    # Normalize Nigeria 080 -> +234
    orig = to
    if to.startswith("0"):
        to = "+234" + to.lstrip("0")
    if not to.startswith("+"):
        to = "+" + to.lstrip("+")
    try:
        from .. import sms as sms_engine
        from ..models import db
        cfg = current_app.config
        # Force Twilio for this test if SID present, else use configured provider
        provider = sms_engine.get_provider()
        if provider is None:
            flash(f"SMS disabled (SMS_MODE={cfg.get('SMS_MODE')}). Set SMS_MODE=twilio in Render.", "error")
            return redirect(url_for("twilio_diag.check"))
        # Queue and send immediately
        msg = sms_engine.queue_sms(current_user.org_id, to,
                                   f"Test SMS from Hospital Suite — your Twilio is working! To: {orig}",
                                   kind="test")
        result = sms_engine.send_sms(msg)
        if result.status == "SENT":
            flash(f"✅ SMS SENT via {result.provider} to {to} — ID {result.provider_id}. Check your phone.", "success")
        else:
            flash(f"❌ SMS FAILED via {result.provider}: {result.last_error}. Check Twilio console logs.", "error")
    except Exception as exc:
        flash(f"❌ Exception: {exc}", "error")
    return redirect(url_for("twilio_diag.check"))

@bp.post("/admin/twilio-check/test-whatsapp")
@require_role(*SUPER)
def test_wa():
    to = (request.form.get("to") or "").strip()
    if not to:
        flash("Enter destination number, e.g. +2348012345678", "error")
        return redirect(url_for("twilio_diag.check"))
    orig = to
    if to.startswith("0"):
        to = "+234" + to.lstrip("0")
    if not to.startswith("+"):
        to = "+" + to.lstrip("+")
    try:
        from .. import whatsapp as wa_engine
        cfg = current_app.config
        mode = cfg.get("WHATSAPP_MODE", "sandbox")
        msg = wa_engine.queue_message(current_user.org_id, to,
                                      f"Test WhatsApp from Hospital Suite — mode {mode} — your Twilio is working! To: {orig}",
                                      kind="test")
        result = wa_engine.send_message(msg)
        if result.status in ("SENT", "DELIVERED"):
            flash(f"✅ WhatsApp {result.status} via {mode} to {to} — ID {result.provider_id}. If sandbox, check you joined: send 'join <code>' to Twilio WhatsApp number first.", "success")
        else:
            flash(f"❌ WhatsApp FAILED: {result.last_error}. Mode={mode}. Check TWILIO_WHATSAPP_FROM format whatsapp:+..., and verified numbers if trial.", "error")
    except Exception as exc:
        flash(f"❌ Exception: {exc}", "error")
    return redirect(url_for("twilio_diag.check"))
