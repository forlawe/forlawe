"""Centralized notification engine: in-app, email, WhatsApp (+SMS hook).

Every notification is templated, logged (AppNotification) and channel
failures never break the business flow.
"""
from __future__ import annotations

from flask import current_app

from . import services, whatsapp
from .models import AppNotification, User, db

# Templates: (subject, body). Placeholders: {name},{hospital},{date},{ref},{dept},{time},{details}
TEMPLATES = {
    "duty_reminder_day_before": (
        "Duty reminder — tomorrow",
        "Dear {name}, you are scheduled as the Admin Manager on duty tomorrow "
        "({date}) at {hospital}. Please prepare for your daily hospital inspection."),
    "duty_reminder_day_of": (
        "Duty reminder — today",
        "Dear {name}, you are the Admin Manager on duty today ({date}) at {hospital}. "
        "Please complete today's departmental inspection."),
    "inspection_overdue": (
        "Inspection overdue",
        "Today's inspection at {hospital} is overdue. Admin Manager on duty: {name}. "
        "Deadline was {time}."),
    "inspection_submitted": (
        "Daily inspection report",
        "Daily inspection report {ref} for {dept} has been submitted by {name}. "
        "Overall rating: {rating} ({total}/25)."),
    "complaint_new_hod": (
        "New patient complaint",
        "A new patient complaint ({ref}) concerning {dept} ({category}) requires your "
        "attention within {sla} hours. Sign in to review and acknowledge."),
    "complaint_new_admin": (
        "New patient complaint on your duty day",
        "A new patient complaint ({ref}) concerning {dept} ({category}) has been received."),
    "complaint_escalated": (
        "Complaint ESCALATED — SLA breached",
        "Complaint {ref} ({dept}) was not resolved within the SLA and has been "
        "escalated to the MD/CEO. Details are available in the system."),
    "complaint_sla_warning": (
        "Complaint SLA warning",
        "Complaint {ref} ({dept}) must be resolved within the next {hours} hours to "
        "avoid escalation."),
    "ca_assigned": (
        "Corrective action assigned",
        "A corrective action has been assigned to you: {details}. Deadline: {date}."),
    "ca_overdue": (
        "Corrective action overdue",
        "Corrective action '{details}' is overdue (deadline {date})."),
    "critical_score": (
        "ALERT: Critical inspection finding",
        "Inspection {ref} at {dept} recorded a critical finding. Immediate intervention required."),
    "booking_new": (
        "New patient booking",
        "New booking {ref}: {dept}. Please see the Bookings screen for details."),
}


def render(template_key: str, ctx: dict) -> tuple[str, str]:
    subject_t, body_t = TEMPLATES[template_key]
    ctx.setdefault("hospital", "the hospital")
    return subject_t.format(**ctx), body_t.format(**ctx)


def _send_email(user: User, subject: str, body: str) -> str | None:
    """None if the letter left. Else a plain-English reason. Never raises."""
    if not user or not getattr(user, "email", None):
        return "No user email"
    from . import mailer
    ok, detail = mailer.send_mail(user.email, subject, body)
    return None if ok else detail


def notify(org_id: int, user: User, template_key: str, ctx: dict,
           channels: list[str] | None = None, entity_type: str = None,
           entity_id: int = None, wa_body_override: str = None,
           wa_media_path: str = None, wa_kind: str = "alert"):
    """Send a templated notification — WhatsApp FIRST, Twilio SMS fallback (premium).

    Acceptance: WhatsApp is primary online channel, Twilio SMS is fallback if WhatsApp not available.
    """
    channels = channels or services.get_setting(org_id, "reminder_channels", ["inapp"])
    subject, body = render(template_key, ctx)
    text = wa_body_override or body

    # 1) in-app — always recorded
    db.session.add(AppNotification(org_id=org_id, user_id=user.id, channel="inapp",
                                   template_key=template_key, subject=subject, body=body,
                                   entity_type=entity_type, entity_id=entity_id, status="SENT"))

    # 2) email — only when SMTP configured and user has an email
    if "email" in channels:
        err = _send_email(user, subject, body)
        db.session.add(AppNotification(org_id=org_id, user_id=user.id, channel="email",
                                       template_key=template_key, subject=subject, body=body,
                                       entity_type=entity_type, entity_id=entity_id,
                                       status="SENT" if err is None else "FAILED", error=err))

    # 3) WhatsApp FIRST — queue for Meta Cloud API
    wa_queued = False
    if ("whatsapp" in channels or "sms" in channels) and user.phone:
        # Always try WhatsApp first
        try:
            whatsapp.queue_message(org_id, user.phone, text, kind=wa_kind,
                                   media_path=wa_media_path, entity_type=entity_type,
                                   entity_id=entity_id, to_user_id=user.id)
            wa_queued = True
        except Exception:
            wa_queued = False

    # 4) SMS fallback via Twilio — queued alongside WhatsApp, delivered if WhatsApp fails or mode disabled
    # If caller asked for whatsapp, we still queue SMS as fallback (WhatsApp-first strategy)
    if ("sms" in channels or ("whatsapp" in channels and not wa_queued)) and user.phone:
        from . import sms as sms_engine
        from . import sms_pack
        from .models import Organization
        sms_text = sms_pack.staff(template_key, dict(ctx, org_id=org_id),
                                  org=db.session.get(Organization, org_id))
        try:
            cfg = current_app.config
            if cfg.get("WHATSAPP_MODE") == "disabled" or "sms" in channels:
                sms_engine.queue_sms(org_id, user.phone, sms_text, kind=wa_kind,
                                     entity_type=entity_type, entity_id=entity_id, to_user_id=user.id)
            elif wa_queued:
                sms_engine.queue_sms(org_id, user.phone, sms_text, kind=f"{wa_kind}_fallback",
                                     entity_type=entity_type, entity_id=entity_id, to_user_id=user.id)
        except Exception:
            try:
                sms_engine.queue_sms(org_id, user.phone, sms_text, kind=wa_kind,
                                     entity_type=entity_type, entity_id=entity_id, to_user_id=user.id)
            except Exception:
                pass
    db.session.commit()


def notify_many(org_id: int, users: list[User], template_key: str, ctx: dict, **kw):
    for u in users:
        if u and u.active:
            notify(org_id, u, template_key, dict(ctx, name=u.name), **kw)


def admin_managers(org_id: int) -> list[User]:
    return db.session.query(User).filter_by(org_id=org_id, role="ADMIN_MANAGER", active=True).all()


def md_ceos(org_id: int) -> list[User]:
    """Executive escalation targets.

    Includes the Deputy MD so a breach still reaches a decision-maker when the
    MD/CEO is away — the whole point of having a deputy. Falls back to the
    MD/CEO alone if no deputy exists.
    """
    return (db.session.query(User)
            .filter(User.org_id == org_id, User.active.is_(True),
                    User.role.in_(("MD_CEO", "DMD")))
            .order_by(User.role.desc()).all())


def super_admins(org_id: int) -> list[User]:
    return db.session.query(User).filter_by(org_id=org_id, role="SUPER_ADMIN", active=True).all()


# ------------------------------------------------------------------ patient (no login) — SMS + WhatsApp
def patient_update_text(event: str, hospital: str, ref: str, extra: str = "") -> str:
    from . import sms_pack
    class _O:
        name = hospital
        code = ""
        phone = None
        id = None
    return sms_pack.complaint(_O(), event, ref, extra)


def notify_complaint_patient(org, complaint, event: str, extra: str = "") -> str:
    """Send the patient an acknowledgment / outcome — WhatsApp FIRST, Twilio SMS fallback.

    Patients have no login, so the same words are also stored on the complaint
    history and shown on the public status page (their in-app inbox).
    Returns the message text.
    """
    from . import sms_pack
    body = sms_pack.complaint(org, event, complaint.ref, extra)
    db.session.add(AppNotification(
        org_id=org.id, user_id=None, channel="inapp",
        template_key=f"patient_{event}", subject=f"Complaint {complaint.ref}",
        body=body, entity_type="complaint", entity_id=complaint.id, status="SENT"))
    phone = (complaint.phone or "").strip()
    # Anonymous and erased complaints have no reachable contact by design —
    # never attempt (or log) a delivery to a placeholder value.
    if getattr(complaint, "is_anonymous", False) or getattr(complaint, "anonymized_at", None):
        phone = ""
    if phone and phone.lower() not in ("not provided", "n/a", "-", "anonymous", "[erased]"):
        from . import sms as sms_engine
        from . import whatsapp
        # WhatsApp FIRST
        whatsapp.queue_message(org.id, phone, body, kind="alert",
                               entity_type="complaint", entity_id=complaint.id)
        # Twilio SMS fallback — queued as fallback, sent if WhatsApp fails
        sms_engine.queue_sms(org.id, phone, body, kind="alert_fallback",
                             entity_type="complaint", entity_id=complaint.id)
        from .tasks import dispatch_delivery
        dispatch_delivery()
    return body
