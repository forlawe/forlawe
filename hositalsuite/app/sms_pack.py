"""One-SMS pack: every live text stays under 160 GSM-7 characters.

WHY
---
A long booking text is billed as two (or more) SMS, can be blocked on
Termii's generic/promo route, and looks like spam. Termii DND and
Twilio transactional both want one short fact: who, when, what to do,
hospital phone. No diagnosis. No naira sign. No emoji.

Per-hospital name-on-text is a setting (`sms_sender_tag`), never a
deploy-wide constant.
"""
from __future__ import annotations

import re
from datetime import date, datetime

SMS_MAX = 160

# GSM-7 basic + a few extension-safe ASCII stand-ins. Anything else
# silently becomes a space so the phone never flips to 70-char unicode.
_GSM_OK = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)


def gsm_clean(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = (raw.replace("—", "-").replace("–", "-").replace("−", "-")
              .replace("‘", "'").replace("’", "'")
              .replace("“", '"').replace("”", '"')
              .replace("₦", "NGN ").replace("⭐", "")
              .replace("\u00a0", " "))
    out = []
    for ch in raw:
        if ch in _GSM_OK:
            out.append(ch)
        elif ch == "\t":
            out.append(" ")
        # drop emoji / accents that would split the SMS
    cleaned = re.sub(r" {2,}", " ", "".join(out)).strip()
    return cleaned


def one_sms(text: str, limit: int = SMS_MAX) -> str:
    """Hard cap. Prefer a full stop cut; otherwise slice."""
    cleaned = gsm_clean(text)
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    # don't leave a dangling word if we can stop at punctuation
    for mark in (". ", "! ", "? ", "; "):
        i = cut.rfind(mark)
        if i >= 80:
            return cut[: i + 1].strip()
    return cut.rstrip()


def sender_tag(org=None, org_id: int | None = None) -> str:
    """3–11 letters/numbers shown at the start of every SMS."""
    tag = ""
    try:
        from . import services
        oid = org_id or (getattr(org, "id", None) if org is not None else None)
        if oid:
            tag = (services.get_setting(oid, "sms_sender_tag") or "") or ""
    except Exception:
        tag = ""
    tag = re.sub(r"[^A-Za-z0-9]", "", str(tag))[:11].upper()
    if len(tag) >= 3:
        return tag
    code = re.sub(r"[^A-Za-z0-9]", "", getattr(org, "code", "") or "")[:11].upper()
    if len(code) >= 3:
        return code
    name = re.sub(r"[^A-Za-z0-9]", "", getattr(org, "name", "") or "")[:11].upper()
    if len(name) >= 3:
        return name
    return "HOSPITAL"


def desk_phone(org=None) -> str:
    raw = (getattr(org, "phone", None) or "").strip()
    digits = re.sub(r"[^\d+]", "", raw)
    return digits[:15]


def _org(org=None, org_id: int | None = None):
    if org is not None:
        return org
    if not org_id:
        return None
    try:
        from .models import Organization, db
        return db.session.get(Organization, org_id)
    except Exception:
        return None


def _date(day) -> str:
    if isinstance(day, datetime):
        day = day.date()
    if isinstance(day, date):
        return day.strftime("%a %d %b")
    return str(day or "")[:11]


def _time(slot) -> str:
    return str(slot or "")[:5]


def _dept(name) -> str:
    return gsm_clean(str(name or "OPD"))[:18]


def _ref(ref) -> str:
    return gsm_clean(str(ref or ""))[:22]


def _clip_phone_tail(body: str, phone: str) -> str:
    """Keep Call {phone} if it still fits."""
    phone = desk_phone(type("O", (), {"phone": phone})()) if not isinstance(phone, str) else re.sub(r"[^\d+]", "", phone)[:15]
    if not phone:
        return one_sms(body)
    tail = f" Call {phone}"
    if len(gsm_clean(body) + tail) <= SMS_MAX:
        return one_sms(body + tail)
    return one_sms(body)


# ------------------------------------------------------------------ patient lines
def visit_booked(org, *, day, time, dept, ref, fast_track: bool = False) -> str:
    org = _org(org)
    tag = sender_tag(org)
    phone = desk_phone(org)
    if fast_track:
        body = (f"{tag}: Fast Track booked {_date(day)} {_time(time)}. "
                f"Ref {_ref(ref)}. Pay at Reception gold lane.")
    else:
        body = (f"{tag}: Visit booked {_date(day)} at {_time(time)}, {_dept(dept)}. "
                f"Ref {_ref(ref)}. Come 15 min early.")
    return _clip_phone_tail(body, phone)


def visit_cancelled(org, *, day, time, ref) -> str:
    org = _org(org)
    tag = sender_tag(org)
    body = (f"{tag}: Your visit Ref {_ref(ref)} on {_date(day)} at {_time(time)} "
            f"is cancelled. Book again or call")
    # _clip_phone_tail adds Call already — rewrite
    phone = desk_phone(org)
    if phone:
        return one_sms(f"{tag}: Your visit Ref {_ref(ref)} on {_date(day)} at "
                       f"{_time(time)} is cancelled. Book again or call {phone}")
    return one_sms(body)


def queue_next(org, *, ticket, dept) -> str:
    org = _org(org)
    tag = sender_tag(org)
    return one_sms(f"{tag}: You are next. Ticket {_ref(ticket)}, {_dept(dept)}. "
                   f"Please walk to the desk now.")


def fasttrack_paid(org, *, day, time, ref) -> str:
    org = _org(org)
    tag = sender_tag(org)
    return one_sms(f"{tag}: Fast Track PAID. Ref {_ref(ref)}. "
                   f"Go to Reception gold lane on {_date(day)} at {_time(time)}.")


def queue_number(org, *, ticket, dept) -> str:
    org = _org(org)
    tag = sender_tag(org)
    return one_sms(f"{tag}: Your number is {_ref(ticket)} at {_dept(dept)}. "
                   f"Keep this SMS. We will text you when it is your turn.")


def complaint(org, event: str, ref: str, extra: str = "") -> str:
    org = _org(org)
    tag = sender_tag(org)
    phone = desk_phone(org)
    ref = _ref(ref)
    extra = gsm_clean(extra)[:40]
    if event == "received":
        body = f"{tag} received your complaint. Ref {ref}. We are looking into it. Keep this number."
    elif event == "acknowledged":
        body = f"{tag}: We have seen your complaint {ref}. Our team is working on it. Thank you."
    elif event == "resolved":
        body = f"{tag}: Your complaint {ref} has been resolved. Thank you."
    elif event == "closed":
        body = f"{tag}: Your complaint {ref} is now closed. Thank you for telling us."
    elif event == "escalated":
        body = f"{tag}: Your complaint {ref} has gone to hospital management for urgent attention."
    else:
        extra_bit = f" {extra}" if extra else ""
        body = f"{tag}: An update on your complaint {ref}.{extra_bit}"
    return _clip_phone_tail(body, phone) if event in ("received", "resolved", "closed") else one_sms(body)


def thank_you(org, feedback_url: str = "/feedback") -> str:
    org = _org(org)
    tag = sender_tag(org)
    url = gsm_clean(feedback_url).replace("https://", "").replace("http://", "")[:48]
    return one_sms(f"{tag}: Thank you for coming today. Please rate us: {url}")


def signin_code(org, otp: str, minutes: int = 10) -> str:
    org = _org(org)
    tag = sender_tag(org)
    code = re.sub(r"\D", "", str(otp))[:8]
    return one_sms(f"{tag}: Your sign-in code is {code}. It dies in {int(minutes)} minutes. "
                   f"If you did not ask, ignore this.")


# ------------------------------------------------------------------ staff lines (when SMS is on)
def staff(template_key: str, ctx: dict, org=None) -> str:
    org = _org(org, ctx.get("org_id"))
    tag = sender_tag(org)
    ref = _ref(ctx.get("ref"))
    dept = _dept(ctx.get("dept"))
    day = _date(ctx.get("date"))
    name = gsm_clean(str(ctx.get("name") or ""))[:20]
    hours = str(ctx.get("hours") or ctx.get("sla") or "")[:3]
    if template_key == "duty_reminder_day_before":
        return one_sms(f"{tag}: You are on duty TOMORROW {day}. Please prepare the daily walk-round.")
    if template_key == "duty_reminder_day_of":
        return one_sms(f"{tag}: You are on duty TODAY {day}. Please finish today's walk-round.")
    if template_key == "inspection_overdue":
        return one_sms(f"{tag}: Today's walk-round is late. Duty officer: {name or 'unassigned'}. Please complete it now.")
    if template_key == "complaint_new_hod":
        return one_sms(f"{tag}: New patient report {ref}, {dept}. Reply within {hours or '24'} hrs. Open Complaints.")
    if template_key == "complaint_new_admin":
        return one_sms(f"{tag}: New patient report {ref}, {dept}. See Complaints on your phone.")
    if template_key == "complaint_escalated":
        return one_sms(f"{tag}: Report {ref} ({dept}) missed its time and is now with you. Open Complaints.")
    if template_key == "complaint_sla_warning":
        return one_sms(f"{tag}: Report {ref} must be closed in {hours or '4'} hrs or it goes to the MD. Open Complaints now.")
    if template_key == "ca_assigned":
        return one_sms(f"{tag}: A fix is assigned to you. Deadline {day}. Open Corrective Actions on your phone.")
    if template_key == "ca_overdue":
        return one_sms(f"{tag}: A fix is overdue (deadline {day}). Open Corrective Actions now.")
    if template_key == "critical_score":
        return one_sms(f"{tag} ALERT: Walk-round {ref} at {dept} has a critical finding. Act now.")
    if template_key == "booking_new":
        return one_sms(f"{tag}: New visit booked. Ref {ref}, {dept}. See Bookings.")
    if template_key == "inspection_submitted":
        return one_sms(f"{tag}: Walk-round {ref} for {dept} submitted. See Reports.")
    # last resort: clip whatever they passed
    return one_sms(f"{tag}: {gsm_clean(str(ctx.get('details') or template_key))}")


def parse_tag(raw: str) -> str | None:
    """Validate a hospital's chosen SMS name. None if not usable."""
    tag = re.sub(r"[^A-Za-z0-9]", "", raw or "")[:11].upper()
    return tag if len(tag) >= 3 else None


def samples(tag: str = "GHIJEDE", phone: str = "08031234567") -> list[tuple[str, str]]:
    """Fixed samples for Termii / tests. Each must be <= 160."""
    class _O:
        code = tag
        name = tag
        phone = None
        id = None

    o = _O()
    o.phone = phone
    day = date(2026, 8, 24)
    return [
        ("visit_booked", visit_booked(o, day=day, time="09:00", dept="OPD", ref="BK24082401")),
        ("fasttrack_booked", visit_booked(o, day=day, time="09:00", dept="OPD", ref="FT24082401", fast_track=True)),
        ("fasttrack_paid", fasttrack_paid(o, day=day, time="09:00", ref="FT24082401")),
        ("visit_cancelled", visit_cancelled(o, day=day, time="09:00", ref="BK24082401")),
        ("queue_next", queue_next(o, ticket="E-014", dept="OPD")),
        ("queue_number", queue_number(o, ticket="E-014", dept="OPD")),
        ("report_received", complaint(o, "received", "CP24082401")),
        ("report_seen", complaint(o, "acknowledged", "CP24082401")),
        ("report_done", complaint(o, "resolved", "CP24082401")),
        ("report_urgent", complaint(o, "escalated", "CP24082401")),
        ("thank_you", thank_you(o, "hospital-suite.onrender.com/feedback")),
        ("signin_code", signin_code(o, "847291", 10)),
        ("duty_tomorrow", staff("duty_reminder_day_before", {"date": day}, o)),
    ]
