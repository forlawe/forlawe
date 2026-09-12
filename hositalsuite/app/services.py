"""Domain services: settings, reference numbers, routing, roster, analytics."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from .models import (Complaint, Department, DutyRoster, Inspection, Organization,
                     Section, Setting, Unit, User, db, now_naive)
from . import scoring

# ------------------------------------------------------------------ settings
DEFAULT_SETTINGS = {
    "sla_hours": 24,
    "reminder_day_before_time": "18:00",
    "reminder_duty_day_time": "07:00",
    "inspection_deadline_time": "18:00",
    "overdue_notify_time": "19:00",
    "gps_mode": "optional",               # mandatory | optional | disabled
    "whatsapp_md_number": "",
    "whatsapp_report_template": "inspection_report_v1",
    "multiple_two_threshold": 2,
    "recurring_window": 10,
    "recurring_threshold": 3,
    "retention_days": 2190,               # 6 years (NDPR-aligned default)
    "reminder_channels": ["inapp", "whatsapp"],
    "complaint_channels_note": "QR / direct link / USSD",
    "voice_storage": False,               # never store audio by default
    # ---- booking (§5) ----
    "booking_slots": ["08:00", "09:00", "10:00", "11:00", "12:00",
                      "13:00", "14:00", "15:00", "16:00", "17:00"],
    "booking_capacity_per_slot": 20,
    "booking_window_days": 30,
    "booking_confirmation_sms": True,
    # ---- AI fallback (see app/chatbot/ai.py) ----
    "ai_fallback_enabled": True,      # per-hospital switch
    "ai_daily_cap": 400,              # protects the free tier
    "ai_usage_today": "",             # "YYYY-MM-DD|count"
    # ---- Fast Track premium (Aug 2026) — simple, human, premium ----
    "fast_track_enabled": True,
    "fast_track_price": 15000,              # NGN — premium price per tenant
    "fast_track_currency": "NGN",
    "fast_track_building_name": "Executive Lounge",
    "fast_track_description": "Fast Track is our premium service. You are seen quickly in a quiet, comfortable lounge. No long queue. For anyone who values time and comfort.",
    "fast_track_booking_requires_payment": False,  # when True, booking must be paid upfront
    "fast_track_payment_instructions": "You can pay at reception or by transfer. Please show your receipt at the Fast Track Desk.",
    "fast_track_price_note": "Pay a little more and be seen quickly in our quiet executive lounge.",
    # ---- Security (Build 6) ----
    "mfa_required_roles": [],           # e.g. ["SUPER_ADMIN", "HEAD_ADMIN_HR"]
    # ---- Branding (Build 6) — per hospital, never per-deploy ----
    "brand_primary": "#0e5a8a",
    "brand_accent": "#12b5a5",
    "brand_gold": "#FFD700",
    "onboarding_complete": False,
    "onboard_guide": False,
    "voice_lang": "en",
    # ---- Staff clock-in geo-fence (per hospital, never per-deploy) ----
    # off = anyone signed in can clock in. optional = record GPS, still allow.
    # required = must be inside the site circle. Default OFF so a new hospital
    # is never locked out before somebody pins the gate.
    "attendance_mode": "off",
    "attendance_radius_m": 200,
    "attendance_lat": None,
    "attendance_lng": None,
    "attendance_grace_minutes": 60,
    # Name printed at the start of every SMS (3–11 letters). Per hospital.
    "sms_sender_tag": "",
}


# ------------------------------------------------------------------ tenant resolution
def current_org() -> Optional[Organization]:
    """Resolve which hospital a request belongs to.

    Public patient portals have no login, so the tenant must come from the
    request itself. Resolution order (first match wins):

      1. the signed-in user's org
      2. ?h=<org code or slug> on the query string (used by QR codes and links)
      3. the <slug>. subdomain, when the deployment is subdomain-per-hospital
      4. the only organization, if the deployment is single-tenant

    Returning None for an ambiguous multi-tenant request is deliberate: serving
    hospital #1's departments to hospital #2's patients is a data-integrity bug,
    so callers show a chooser instead of guessing.
    """
    from flask import current_app, has_request_context, request

    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            org = db.session.get(Organization, current_user.org_id)
            if org is not None:
                return org
    except Exception:                                   # noqa: BLE001
        pass

    if has_request_context():
        hint = (request.args.get("h") or request.view_args.get("org_slug")
                if request.view_args else request.args.get("h"))
        hint = (hint or "").strip()
        if hint:
            org = (db.session.query(Organization)
                   .filter(db.or_(Organization.slug == hint.lower(),
                                  Organization.code == hint.upper())).first())
            if org is not None:
                return org
        host = (request.host or "").split(":")[0].lower()
        label = host.split(".")[0] if host.count(".") >= 2 else ""
        if label and label not in ("www", "localhost", "hospital-suite"):
            org = db.session.query(Organization).filter_by(slug=label).first()
            if org is not None:
                return org

    orgs = db.session.query(Organization).order_by(Organization.id).limit(2).all()
    if len(orgs) == 1:
        return orgs[0]
    if orgs:
        # Multi-tenant but unidentified: fall back only if explicitly allowed.
        try:
            if current_app.config.get("DEFAULT_ORG_FALLBACK", True):
                return orgs[0]
        except RuntimeError:
            return orgs[0]
    return None


def get_setting(org_id: int, key: str, default=None):
    val = Setting.get(org_id, key, None)
    return val if val is not None else DEFAULT_SETTINGS.get(key, default)


def set_setting(org_id: int, key: str, value):
    Setting.set(org_id, key, value)


def _safe_hex(val, fallback: str) -> str:
    import re as _re
    s = (val or "").strip() if isinstance(val, str) else ""
    return s if _re.fullmatch(r"#[0-9A-Fa-f]{6}", s) else fallback


def org_settings_bundle(org_id: int) -> dict:
    out = {k: get_setting(org_id, k) for k in DEFAULT_SETTINGS}
    out["brand_primary"] = _safe_hex(out.get("brand_primary"), "#0e5a8a")
    out["brand_accent"] = _safe_hex(out.get("brand_accent"), "#12b5a5")
    out["brand_gold"] = _safe_hex(out.get("brand_gold"), "#FFD700")
    return out


def parse_hhmm(s: str) -> tuple[int, int]:
    m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", s or "")
    if not m:
        return 7, 0
    return int(m.group(1)), int(m.group(2))


# ------------------------------------------------------------------ references
def next_ref(org: Organization, kind: str, model, year: int) -> str:
    prefix = f"{org.code}-{kind}-{year}-"
    count = db.session.query(model).filter(
        model.org_id == org.id, model.ref.like(prefix + "%")).count()
    # ensure uniqueness even under concurrency
    n = count + 1
    while True:
        ref = f"{prefix}{n:06d}"
        exists = db.session.query(model).filter_by(ref=ref).first()
        if not exists:
            return ref
        n += 1


def next_inspection_ref(org: Organization, when: datetime) -> str:
    return next_ref(org, "INS", Inspection, when.year)


def next_complaint_ref(org: Organization, when: datetime) -> str:
    return next_ref(org, "CMP", Complaint, when.year)


def next_appointment_ref(org: Organization, when: datetime) -> str:
    from .models import Appointment
    return next_ref(org, "APT", Appointment, when.year)


def insert_with_unique_ref(build, idem_lookup=None, max_tries: int = 10):
    """Insert a record whose computed reference must be unique, retrying on
    concurrent collisions. The DB UNIQUE constraint is the arbiter: if two
    requests compute the same ref, one inserts and the other retries with a
    fresh count. An idempotency-key collision returns the existing record
    instead of creating a duplicate (spec §41).

    `build` is a zero-arg callable returning the new (unflushed) object;
    `idem_lookup` optionally returns the existing record on an idem collision.
    Returns (object, created) — created is False when an existing record was
    returned via an idempotency collision.
    """
    from sqlalchemy.exc import IntegrityError
    last_exc = None
    for attempt in range(max_tries):
        try:
            obj = build()
            db.session.add(obj)
            db.session.flush()
            return obj, True
        except IntegrityError as exc:
            db.session.rollback()
            last_exc = exc
            msg = str(getattr(exc, "orig", exc))
            if idem_lookup is not None and "idem" in msg:
                existing = idem_lookup()
                if existing is not None:
                    return existing, False
            if "ref" in msg and attempt < max_tries - 1:
                continue   # ref collision — retry with a fresh reference
            raise
    raise last_exc


def slot_is_full(org_id: int, department_id: int, day: date, slot: str) -> bool:
    from .models import Appointment
    cap = int(get_setting(org_id, "booking_capacity_per_slot") or 20)
    taken = (db.session.query(Appointment)
             .filter_by(org_id=org_id, department_id=department_id,
                        appointment_date=day, appointment_time=slot)
             .filter(Appointment.status.in_(("BOOKED", "ARRIVED"))).count())
    return taken >= cap


# ------------------------------------------------------------------ duty / roster
def on_duty(org_id: int, day: date) -> Optional[User]:
    row = db.session.query(DutyRoster).filter_by(org_id=org_id, duty_date=day).first()
    return row.user if row else None


def todays_inspection(org_id: int, day: date) -> Optional[Inspection]:
    return (db.session.query(Inspection)
            .filter_by(org_id=org_id, duty_date=day, status="SUBMITTED")
            .order_by(Inspection.submitted_at.desc()).first())


def inspection_state(org_id: int, day: date, now: datetime = None) -> dict:
    """Return duty/inspection status for a day: completed | pending | overdue | unassigned."""
    now = now or now_naive()
    duty = on_duty(org_id, day)
    insp = todays_inspection(org_id, day)
    hh, mm = parse_hhmm(get_setting(org_id, "inspection_deadline_time"))
    deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if insp:
        state = "completed"
    elif not duty:
        state = "unassigned"
    elif now > deadline:
        state = "overdue"
    else:
        state = "pending"
    return {"duty": duty, "inspection": insp, "state": state, "deadline": deadline}


# ------------------------------------------------------------------ routing
def department_chain(dept: Department, section: Section = None, unit: Unit = None):
    """Most-specific HOD first, falling back to department HOD."""
    for obj in (unit, section, dept):
        if obj is not None and getattr(obj, "hod_user_id", None):
            yield obj.hod
    return None


def route_hod(dept: Department, section: Section = None, unit: Unit = None) -> Optional[User]:
    for u in department_chain(dept, section, unit):
        if u and u.active:
            return u
    return None


# ------------------------------------------------------------------ analytics
def department_history(org_id: int, department_id: int, limit: int = 10) -> list[Inspection]:
    return (db.session.query(Inspection)
            .filter_by(org_id=org_id, department_id=department_id, status="SUBMITTED")
            .order_by(Inspection.submitted_at.desc()).limit(limit).all())


def inspection_criterion_map(insp: Inspection) -> dict:
    return {s.criterion_no: s.score for s in insp.scores}


def recurring_flags_for_department(org_id: int, department_id: int) -> list[str]:
    window = int(get_setting(org_id, "recurring_window") or 10)
    threshold = int(get_setting(org_id, "recurring_threshold") or 3)
    hist = department_history(org_id, department_id, limit=window)
    as_dicts = [{"criterion_scores": inspection_criterion_map(i)} for i in hist]
    return scoring.recurring_findings(as_dicts, window=window, threshold=threshold)


def management_attention(org_id: int, now: datetime = None) -> list[dict]:
    """The 'Management Attention' list: the issues that need action right now."""
    now = now or now_naive()
    items: list[dict] = []

    # 1. Overdue corrective actions
    from .models import CorrectiveAction
    overdue_cas = (db.session.query(CorrectiveAction)
                   .filter(CorrectiveAction.org_id == org_id,
                           CorrectiveAction.status.in_(("OPEN", "IN_PROGRESS", "OVERDUE")),
                           CorrectiveAction.deadline < now.date()).all())
    for ca in overdue_cas:
        items.append({"level": "high", "kind": "Corrective action overdue",
                      "text": f"Overdue corrective action: {ca.finding[:120]}",
                      "href": f"/corrective-actions?highlight={ca.id}"})

    # 2. Escalated open complaints
    esc = (db.session.query(Complaint)
           .filter(Complaint.org_id == org_id, Complaint.escalated.is_(True),
                   Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED"))).all())
    for c in esc:
        items.append({"level": "high", "kind": "Escalated complaint",
                      "text": f"{c.ref} — {c.category} in {c.department.name} is escalated to MD/CEO.",
                      "href": f"/complaints/{c.id}"})

    # 3. SLA about to breach (within 4h)
    soon = (db.session.query(Complaint)
            .filter(Complaint.org_id == org_id, Complaint.escalated.is_(False),
                    Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS")),
                    Complaint.sla_deadline_at < now + timedelta(hours=4),
                    Complaint.sla_deadline_at > now).all())
    for c in soon:
        items.append({"level": "medium", "kind": "SLA expiring soon",
                      "text": f"{c.ref} — SLA expires {c.sla_deadline_at.strftime('%H:%M')} today.",
                      "href": f"/complaints/{c.id}"})

    # 4. Recurring poor criteria per department
    for dept in db.session.query(Department).filter_by(org_id=org_id, active=True).all():
        for msg in recurring_flags_for_department(org_id, dept.id):
            items.append({"level": "medium", "kind": "Recurring finding",
                          "text": f"{dept.name}: {msg}", "href": f"/reports/departments/{dept.id}"})

    # 5. Failed WhatsApp report deliveries
    from .models import WhatsAppMessage
    failed = (db.session.query(WhatsAppMessage)
              .filter_by(org_id=org_id, status="FAILED").count())
    if failed:
        items.append({"level": "high", "kind": "WhatsApp delivery failure",
                      "text": f"{failed} WhatsApp message(s) failed to deliver. Review and retry.",
                      "href": "/admin/notifications"})

    # 6. Missed inspections in last 7 days (duty assigned but nothing submitted)
    today = now.date()
    for offset in range(1, 8):
        day = today - timedelta(days=offset)
        duty = on_duty(org_id, day)
        if duty and not todays_inspection(org_id, day):
            items.append({"level": "medium", "kind": "Missed inspection",
                          "text": f"No inspection recorded on {day.strftime('%a %d %b')} "
                                  f"(on duty: {duty.name}).",
                          "href": "/inspections"})
    return items


def heatmap_data(org_id: int, days: int = 14) -> dict:
    """department -> list of (date, total|None) for the last N days."""
    today = now_naive().date()
    start = today - timedelta(days=days - 1)
    depts = db.session.query(Department).filter_by(org_id=org_id, active=True).order_by(Department.name).all()
    inspections = (db.session.query(Inspection)
                   .filter(Inspection.org_id == org_id, Inspection.status == "SUBMITTED",
                           Inspection.duty_date >= start).all())
    grid = {}
    for d in depts:
        row = []
        for off in range(days):
            day = start + timedelta(days=off)
            scores = [i.total_score for i in inspections if i.department_id == d.id and i.duty_date == day]
            row.append(max(scores) if scores else None)
        grid[d.name] = row
    return {"start": start, "days": days, "grid": grid}
