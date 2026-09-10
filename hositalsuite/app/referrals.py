"""Referral engine (spec §14).

Happy patients get a personal share-link + QR. The hospital can see how many
people opened it and how many then booked. No prizes, no coupons, no pressure.

Also detects returning patients (same phone booked before).
"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Optional
from urllib.parse import quote

from flask import has_request_context, request, session

from .audit import audit
from .models import (Appointment, Organization, Referral, ReferralEvent,
                     db, new_code, now_naive)

HIGH_RATING = 4          # 4★ and 5★ unlock a personal share-link
CODE_LEN = 8


def public_base() -> str:
    """Prefer the URL the visitor is actually on (works in Arena + Render)."""
    try:
        if has_request_context() and request.host:
            return request.host_url.rstrip("/")
    except Exception:
        pass
    from .config import Config
    return (Config.PUBLIC_BASE_URL or "http://localhost:8077").rstrip("/")


def share_url(referral: Referral) -> str:
    return f"{public_base()}/r/{referral.code}"


def whatsapp_share_url(org_name: str, url: str) -> str:
    text = (f"I had a good experience at {org_name}. "
            f"You can book a visit here (no account needed): {url}")
    return "https://wa.me/?text=" + quote(text)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("234") and len(digits) >= 13:
        digits = "0" + digits[3:]
    return digits


def same_phone(a: str, b: str) -> bool:
    na, nb = normalize_phone(a), normalize_phone(b)
    return bool(na and nb and na == nb)


def _unique_code() -> str:
    for _ in range(12):
        code = new_code(CODE_LEN)
        if db.session.query(Referral).filter_by(code=code).first() is None:
            return code
    return new_code(CODE_LEN + 2)


def find_active(org_id: int, code: str) -> Optional[Referral]:
    code = (code or "").strip().upper()
    if not code:
        return None
    return (db.session.query(Referral)
            .filter_by(org_id=org_id, code=code, active=True).first())


def find_any(org_id: int, code: str) -> Optional[Referral]:
    code = (code or "").strip().upper()
    if not code:
        return None
    return db.session.query(Referral).filter_by(org_id=org_id, code=code).first()


def remember(code: str) -> None:
    """Stick the code to this browser session so /book picks it up."""
    if not code:
        return
    session["referral_code"] = code.strip().upper()


def code_from_request() -> str:
    raw = (request.form.get("r") or request.args.get("r")
           or session.get("referral_code") or "")
    return str(raw).strip().upper()


def from_request(org_id: int) -> Optional[Referral]:
    return find_active(org_id, code_from_request())


def issue_patient_referral(org: Organization, feedback, *,
                           department_id: int | None = None,
                           referrer_phone: str | None = None,
                           referrer_name: str | None = None) -> Referral:
    """One personal code per happy-feedback row (idempotent)."""
    existing = (db.session.query(Referral)
                .filter_by(org_id=org.id, feedback_id=feedback.id).first())
    if existing:
        return existing
    r = Referral(
        org_id=org.id,
        code=_unique_code(),
        kind="patient",
        source="feedback",
        feedback_id=feedback.id,
        department_id=department_id,
        referrer_phone=(referrer_phone or None),
        referrer_name=(referrer_name or None),
        note="Issued after a high satisfaction rating",
        active=True,
    )
    db.session.add(r)
    db.session.flush()
    audit("REFERRAL_ISSUED", "referral", r.id,
          {"code": r.code, "source": "feedback", "rating": getattr(feedback, "rating", None)},
          org_id=org.id)
    return r


def ensure_hospital_referral(org: Organization) -> Referral:
    """The single hospital-wide poster / 'share us' code. Created once, reused."""
    existing = (db.session.query(Referral)
                .filter_by(org_id=org.id, kind="hospital", active=True)
                .order_by(Referral.id).first())
    if existing:
        return existing
    r = Referral(
        org_id=org.id,
        code=_unique_code(),
        kind="hospital",
        source="poster",
        note="Hospital-wide share link (posters & reception)",
        active=True,
    )
    db.session.add(r)
    db.session.flush()
    audit("REFERRAL_ISSUED", "referral", r.id,
          {"code": r.code, "source": "poster", "kind": "hospital"}, org_id=org.id)
    return r


def issue_staff_referral(org: Organization, *, note: str,
                         department_id: int | None = None,
                         created_by_id: int | None = None) -> Referral:
    r = Referral(
        org_id=org.id,
        code=_unique_code(),
        kind="staff",
        source="staff",
        note=(note or "Staff link")[:200],
        department_id=department_id,
        created_by_id=created_by_id,
        active=True,
    )
    db.session.add(r)
    db.session.flush()
    audit("REFERRAL_STAFF_CREATED", "referral", r.id,
          {"code": r.code, "note": r.note}, org_id=org.id)
    return r


def record_event(referral: Referral, kind: str, *,
                 appointment_id: int | None = None,
                 feedback_id: int | None = None) -> ReferralEvent:
    ev = ReferralEvent(
        org_id=referral.org_id,
        referral_id=referral.id,
        kind=kind,
        appointment_id=appointment_id,
        feedback_id=feedback_id,
    )
    db.session.add(ev)
    if kind == "click":
        referral.last_clicked_at = now_naive()
    return ev


def record_click_once(referral: Referral) -> bool:
    """Count a click at most once per browser session (refresh ≠ new visitor)."""
    seen = session.get("ref_clicks") or []
    if referral.code in seen:
        return False
    record_event(referral, "click")
    seen = list(seen) + [referral.code]
    session["ref_clicks"] = seen
    remember(referral.code)
    return True


def is_returning_patient(org_id: int, phone: str, exclude_id: int | None = None) -> bool:
    if not phone:
        return False
    q = (db.session.query(Appointment)
         .filter_by(org_id=org_id, phone=phone)
         .filter(Appointment.status.in_(("BOOKED", "ARRIVED", "NO_SHOW"))))
    if exclude_id:
        q = q.filter(Appointment.id != exclude_id)
    if q.count():
        return True
    # fallback: compare normalised digits (080… vs 234…)
    rows = (db.session.query(Appointment.id, Appointment.phone)
            .filter_by(org_id=org_id)
            .filter(Appointment.status.in_(("BOOKED", "ARRIVED", "NO_SHOW"))))
    if exclude_id:
        rows = rows.filter(Appointment.id != exclude_id)
    return any(same_phone(row[1], phone) for row in rows.all())


def already_converted(referral: Referral, phone: str) -> bool:
    if not phone:
        return False
    return (db.session.query(Appointment)
            .filter_by(referral_id=referral.id, phone=phone)
            .first()) is not None


def resolve_for_booking(org_id: int, code: str, phone: str) -> tuple[Optional[Referral], bool]:
    """Return (referral, is_conversion).

    A conversion is a *new* patient (or a friend) booking through someone else's
    link. The original patient booking again through their own link is a
    repeat visit, not a referral conversion. No incentives to game.
    """
    r = find_active(org_id, code)
    if not r:
        return None, False
    if r.referrer_phone and phone and same_phone(r.referrer_phone, phone):
        return r, False
    if already_converted(r, phone):
        return r, False
    return r, True


def stamp_booking(org_id: int, apt, code: str | None = None) -> Optional[Referral]:
    """Attach inbound referral + repeat flag to a freshly built appointment."""
    code = (code or code_from_request() or "").strip().upper()
    apt.is_repeat = bool(apt.is_repeat) or is_returning_patient(
        org_id, apt.phone, exclude_id=getattr(apt, "id", None))
    referral, is_conversion = resolve_for_booking(org_id, code, apt.phone)
    if referral is None:
        return None
    if is_conversion:
        apt.referral_id = referral.id
        if apt.source in (None, "link"):
            apt.source = "referral"
        record_event(referral, "book", appointment_id=apt.id)
        audit("REFERRAL_CONVERSION", "referral", referral.id,
              {"code": referral.code, "apt": apt.ref}, org_id=org_id)
        return referral
    # own-link / already converted: still a returning patient
    if referral.referrer_phone and same_phone(referral.referrer_phone, apt.phone):
        apt.is_repeat = True
    return referral


def stamp_feedback(org_id: int, fb) -> Optional[Referral]:
    r = from_request(org_id)
    if not r:
        return None
    fb.referral_id = r.id
    record_event(r, "feedback", feedback_id=fb.id)
    return r


def stamp_queue(org_id: int) -> Optional[Referral]:
    r = from_request(org_id)
    if not r:
        return None
    record_event(r, "queue")
    return r


def event_counts(referral_id: int) -> dict[str, int]:
    rows = (db.session.query(ReferralEvent.kind, db.func.count(ReferralEvent.id))
            .filter_by(referral_id=referral_id)
            .group_by(ReferralEvent.kind).all())
    out = {"click": 0, "book": 0, "feedback": 0, "queue": 0}
    for kind, n in rows:
        out[kind] = int(n)
    return out


def analytics(org_id: int, days: int = 30) -> dict:
    since = now_naive() - timedelta(days=days)
    codes = (db.session.query(Referral)
             .filter_by(org_id=org_id)
             .order_by(Referral.created_at.desc()).all())
    events = (db.session.query(ReferralEvent)
              .filter(ReferralEvent.org_id == org_id,
                      ReferralEvent.created_at >= since).all())
    clicks = sum(1 for e in events if e.kind == "click")
    books = sum(1 for e in events if e.kind == "book")
    issued = sum(1 for r in codes if r.created_at and r.created_at >= since)
    repeats = (db.session.query(Appointment)
               .filter(Appointment.org_id == org_id,
                       Appointment.is_repeat.is_(True),
                       Appointment.created_at >= since)
               .count())
    conversion = round(100.0 * books / clicks, 1) if clicks else 0.0

    counts_by_id: dict[int, dict[str, int]] = {}
    all_events = (db.session.query(ReferralEvent)
                  .filter_by(org_id=org_id).all())
    for e in all_events:
        bucket = counts_by_id.setdefault(e.referral_id, {"click": 0, "book": 0,
                                                         "feedback": 0, "queue": 0})
        bucket[e.kind] = bucket.get(e.kind, 0) + 1

    rows = []
    for r in codes:
        c = counts_by_id.get(r.id, {"click": 0, "book": 0, "feedback": 0, "queue": 0})
        rows.append({"referral": r, "clicks": c["click"], "books": c["book"],
                     "feedback": c["feedback"], "queue": c["queue"]})

    top = sorted(rows, key=lambda x: (x["books"], x["clicks"]), reverse=True)[:8]
    recent_books = (db.session.query(Appointment)
                    .filter(Appointment.org_id == org_id,
                            Appointment.referral_id.isnot(None))
                    .order_by(Appointment.created_at.desc()).limit(20).all())
    return {
        "days": days,
        "codes": len(codes),
        "issued": issued,
        "clicks": clicks,
        "books": books,
        "repeats": repeats,
        "conversion": conversion,
        "rows": rows,
        "top": top,
        "recent_books": recent_books,
        "active": sum(1 for r in codes if r.active),
    }
