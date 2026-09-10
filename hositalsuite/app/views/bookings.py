"""Patient booking (public, no account) + staff booking management — spec §5."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import notifications, referrals as refeng, services, sms as sms_engine
from ..audit import audit
from ..models import (Appointment, Department, Organization, QrLocation, db,
                      now_naive)
from ..navigation import require_permission
from ..security import rate_limit, require_login, require_role

bp = Blueprint("bookings", __name__)

PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _default_org() -> Organization | None:
    """Tenant for this request (see services.current_org)."""
    from ..services import current_org
    return current_org()


# ================================================================ PUBLIC
@bp.get("/book")
@rate_limit(limit=30, window=60.0)
def portal():
    org = _default_org()
    if not org:
        return render_template("error.html", code=503, message="System not configured yet."), 503
    loc_code = (request.args.get("loc") or "").strip().upper()
    qr_loc = db.session.query(QrLocation).filter_by(code=loc_code).first() if loc_code else None
    ref_code = refeng.code_from_request()
    if ref_code and refeng.find_active(org.id, ref_code):
        refeng.remember(ref_code)
    else:
        ref_code = ""
    from ..patient_places import public_departments
    depts = public_departments(org.id)
    db.session.commit()
    today = now_naive().date()
    window = int(services.get_setting(org.id, "booking_window_days") or 30)
    s = services.org_settings_bundle(org.id)
    return render_template("booking_portal.html", org=org, depts=depts, qr_loc=qr_loc,
                           ref_code=ref_code, s=s,
                           min_date=today.isoformat(),
                           max_date=(today + timedelta(days=window)).isoformat(),
                           slots=services.get_setting(org.id, "booking_slots") or [],
                           idem=_new_idem())


def _new_idem() -> str:
    import secrets
    return secrets.token_urlsafe(16)


@bp.post("/book/submit")
@rate_limit(limit=10, window=120.0)
def portal_submit():
    org = _default_org()
    if not org:
        abort(503)
    now = now_naive()

    idem = (request.form.get("idem") or "").strip()[:40]
    # idempotency: a re-submitted form (double-tap / retry) returns the original booking
    if idem:
        dup = db.session.query(Appointment).filter_by(org_id=org.id, idempotency_key=idem).first()
        if dup:
            return redirect(url_for("bookings.portal_thanks", ref=dup.ref))

    dept_id = request.form.get("department_id", type=int)
    raw_date = (request.form.get("appointment_date") or "").strip()
    slot = (request.form.get("appointment_time") or "").strip()
    name = (request.form.get("patient_name") or "").strip()
    phone = (request.form.get("phone") or "").strip().replace(" ", "").replace("-", "")

    dept = db.session.get(Department, dept_id) if dept_id else None
    errors = []
    day = None
    if not dept or dept.org_id != org.id:
        errors.append("Please select a service/department.")
    try:
        day = date.fromisoformat(raw_date)
    except ValueError:
        day = None
        errors.append("Please choose a valid date.")
    if day:
        window = int(services.get_setting(org.id, "booking_window_days") or 30)
        if day < now.date():
            errors.append("The date cannot be in the past.")
        elif day > now.date() + timedelta(days=window):
            errors.append(f"Bookings are open up to {window} days ahead.")
    slots = services.get_setting(org.id, "booking_slots") or []
    if slot not in slots:
        errors.append("Please choose one of the available time slots.")
    elif day == now.date() and datetime.strptime(slot, "%H:%M").time() <= now.time():
        errors.append("That time slot has already passed today — please pick a later slot.")
    if len(name) < 2:
        errors.append("Please enter the patient's full name.")
    if not PHONE_RE.match(phone):
        errors.append("Please enter a valid phone number (e.g. 08012345678).")
    if request.form.get("consent") not in ("1", "on", "true", "yes"):
        errors.append("Please tick the box to allow the hospital to store your "
                      "details for this appointment.")
    # MUST consent for Fast Track premium service
    is_ft_check = (request.form.get("is_fast_track") or "").strip() in ("1","on","true","yes") or True
    if is_ft_check and request.form.get("fast_track_consent") not in ("1","on","true","yes"):
        errors.append("To use Fast Track, you must agree that it is a premium service and you will pay a little more for quick, private care.")
    if day and dept and slot in slots and services.slot_is_full(org.id, dept.id, day, slot):
        errors.append("That time slot is full — please choose another time.")

    if errors:
        from ..patient_places import public_departments
        depts = public_departments(org.id)
        for e in errors:
            flash(e, "error")
        # preserve the QR location tag on re-render
        loc_code_err = (request.form.get("loc") or "").strip().upper()
        qr_loc_err = db.session.query(QrLocation).filter_by(code=loc_code_err).first() if loc_code_err else None
        s_err = services.org_settings_bundle(org.id)
        return render_template("booking_portal.html", org=org, depts=depts, qr_loc=qr_loc_err,
                               ref_code=(request.form.get("r") or ""), s=s_err,
                               min_date=now.date().isoformat(),
                               max_date=(now.date() + timedelta(days=int(
                                   services.get_setting(org.id, "booking_window_days") or 30))).isoformat(),
                               slots=services.get_setting(org.id, "booking_slots") or [],
                               idem=_new_idem(), form=request.form), 422

    loc_code = (request.form.get("loc") or "").strip().upper()
    qr_loc = db.session.query(QrLocation).filter_by(code=loc_code).first() if loc_code else None

    from ..patient_places import is_fast_track_dept
    # Fast Track — Booking is now Fast Track premium linked to Reception
    is_ft = ((request.form.get("is_fast_track") or "").strip() in ("1","on","true","yes")
             or is_fast_track_dept(dept) or True)
    ft_reason = (request.form.get("fast_track_reason") or "PREMIUM").strip().upper()[:40] or "PREMIUM"
    ft_price = int(services.get_setting(org.id, "fast_track_price") or 15000)
    ft_requires_pay = bool(services.get_setting(org.id, "fast_track_booking_requires_payment"))
    # Payment status: if requires payment, start PENDING, else not needed
    pay_status = "PENDING" if (is_ft and ft_requires_pay) else ("WAIVED" if is_ft else "PENDING")

    def _build_apt():
        # Link to existing patient folder if phone matches — closes gap #4
        patient_id = None
        try:
            from ..models import Patient
            pat = db.session.query(Patient).filter_by(org_id=org.id, phone=phone).first()
            if not pat:
                # try normalized phone without spaces
                clean = phone.replace(" ", "").replace("-", "")
                pat = db.session.query(Patient).filter_by(org_id=org.id, phone=clean).first()
            if pat:
                patient_id = pat.id
        except Exception:
            patient_id = None
        return Appointment(
            org_id=org.id,
            ref=services.next_appointment_ref(org, now),
            idempotency_key=idem or None,
            department_id=dept.id,
            appointment_date=day,
            appointment_time=slot,
            patient_name=name[:120],
            phone=phone,
            patient_id=patient_id,
            consent_at=now,
            status="BOOKED",
            source="qr" if qr_loc else "link",
            qr_location_id=qr_loc.id if qr_loc else None,
            is_fast_track=is_ft,
            fast_track_reason=ft_reason,
            fast_track_amount=ft_price if is_ft else None,
            fast_track_payment_status=pay_status,
            fast_track_paid=False,
        )

    try:
        apt, apt_created = services.insert_with_unique_ref(
            _build_apt,
            idem_lookup=(lambda: db.session.query(Appointment)
                         .filter_by(org_id=org.id, idempotency_key=idem).first()) if idem else None)
    except Exception:
        db.session.rollback()
        flash("The system is very busy right now. Please try booking again.", "error")
        return redirect(url_for("bookings.portal"))
    if not apt_created:
        return redirect(url_for("bookings.portal_thanks", ref=apt.ref))
    refeng.stamp_booking(org.id, apt, code=request.form.get("r"))
    audit("BOOKING_CREATED", "appointment", apt.id,
          {"ref": apt.ref, "dept": dept.name, "date": str(day), "slot": slot,
           "repeat": bool(apt.is_repeat), "referral_id": apt.referral_id}, org_id=org.id)

    # confirmation — one SMS (160). WhatsApp may carry the same short line.
    from .. import sms_pack
    confirm_body = sms_pack.visit_booked(
        org, day=day, time=slot, dept=dept.name, ref=apt.ref, fast_track=bool(is_ft))
    if services.get_setting(org.id, "booking_confirmation_sms", True):
        try:
            from .. import whatsapp as wa_engine
            wa_engine.queue_message(org.id, phone, confirm_body, kind="confirmation",
                                    entity_type="appointment", entity_id=apt.id)
        except Exception:
            pass
        sms_engine.queue_sms(org.id, phone, confirm_body, kind="confirmation",
                             entity_type="appointment", entity_id=apt.id)
        from ..tasks import dispatch_delivery
        dispatch_delivery()   # §39 — async delivery, WhatsApp first then SMS

    # inform the Admin Manager on duty (in-app)
    duty = services.on_duty(org.id, now.date())
    if duty:
        notifications.notify(org.id, duty, "booking_new",
                             {"ref": apt.ref, "dept": dept.name, "hospital": org.name},
                             channels=["inapp"], entity_type="appointment", entity_id=apt.id)
    db.session.commit()
    return redirect(url_for("bookings.portal_thanks", ref=apt.ref))


@bp.get("/book/thanks")
def portal_thanks():
    ref = request.args.get("ref", "")
    apt = db.session.query(Appointment).filter_by(ref=ref).first()
    s = services.org_settings_bundle(apt.org_id) if apt else {}
    return render_template("booking_thanks.html", apt=apt, ref=ref, s=s)


@bp.get("/book/status")
def portal_status():
    ref = (request.args.get("ref") or "").strip()
    phone = (request.args.get("phone") or "").strip()
    apt, error = None, None
    if ref:
        # SECURITY: ref is sequential (ORG-APT-YYYY-000001) — must require phone verification
        # to prevent enumeration of patient bookings (PII: name, phone, dept, date)
        if not phone or len(phone) < 7:
            error = "Please enter both reference number and phone number to verify your booking."
        else:
            q = db.session.query(Appointment).filter(Appointment.ref.ilike(ref))
            q = q.filter(Appointment.phone == phone.replace(" ", ""))
            apt = q.first()
            if not apt:
                error = "No booking found for that reference and phone number. Check both."
    return render_template("booking_status.html", apt=apt, error=error, ref=ref, phone=phone)


@bp.post("/book/cancel")
@rate_limit(limit=6, window=60.0)
def portal_cancel():
    ref = (request.form.get("ref") or "").strip()
    phone = (request.form.get("phone") or "").strip().replace(" ", "")
    apt = db.session.query(Appointment).filter_by(ref=ref, phone=phone).first()
    if not apt:
        flash("Booking not found — check the reference and phone number.", "error")
        return redirect(url_for("bookings.portal_status", ref=ref, phone=phone))
    if apt.status != "BOOKED":
        flash("Only upcoming bookings can be cancelled.", "error")
        return redirect(url_for("bookings.portal_status", ref=ref, phone=phone))
    apt.status = "CANCELLED"
    apt.cancelled_at = now_naive()
    audit("BOOKING_CANCELLED", "appointment", apt.id, {"ref": apt.ref}, org_id=apt.org_id)
    try:
        from .. import sms_pack
        from ..models import Organization
        org = db.session.get(Organization, apt.org_id)
        body = sms_pack.visit_cancelled(org, day=apt.appointment_date,
                                        time=apt.appointment_time, ref=apt.ref)
        sms_engine.queue_sms(apt.org_id, phone, body, kind="alert",
                             entity_type="appointment", entity_id=apt.id)
        from ..tasks import dispatch_delivery
        dispatch_delivery()
    except Exception:
        pass
    db.session.commit()
    flash("Your booking has been cancelled.", "success")
    return redirect(url_for("bookings.portal_status", ref=ref, phone=phone))


# ================================================================ STAFF — strictly front desk + management only
# Patient bookings contain PII (name, phone, dept, date). Must not be visible to
# unauthorized staff (e.g. HOD of Theatre). Enforced by bookings permission + role.
@bp.get("/bookings")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD", "APEX_NURSE")
def staff_list():
    # v1.7.18: LIMIT to own Department/Section/Unit for HOD/APEX_NURSE/STAFF, System Admin upgrades
    from ..roles import visible_department_ids
    q = db.session.query(Appointment).filter(Appointment.org_id == current_user.org_id)
    visible = visible_department_ids(current_user)
    if visible is not None:
        q = q.filter(Appointment.department_id.in_(visible or [-1]))
    day = request.args.get("date")
    status = request.args.get("status")
    if day:
        try:
            q = q.filter(Appointment.appointment_date == date.fromisoformat(day))
        except ValueError:
            pass
    else:
        q = q.filter(Appointment.appointment_date >= now_naive().date())
    if status in ("BOOKED", "ARRIVED", "CANCELLED", "NO_SHOW"):
        q = q.filter(Appointment.status == status)
    items = q.order_by(Appointment.is_fast_track.desc(), Appointment.appointment_date, Appointment.appointment_time).limit(300).all()
    return render_template("bookings_staff.html", items=items, args=request.args,
                           today=now_naive().date())


@bp.post("/bookings/<int:aid>/mark-paid-fasttrack")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "HOD", "MD_CEO")
def mark_paid_fasttrack(aid: int):
    """Mark Fast Track booking as paid upfront — premium."""
    apt = db.session.get(Appointment, aid)
    if not apt or apt.org_id != current_user.org_id:
        abort(404)
    if not apt.is_fast_track:
        flash("Only Fast Track bookings have premium payment.", "error")
        return redirect(url_for("bookings.staff_list"))
    ref = (request.form.get("payment_ref") or "").strip()[:80] or f"FT-PAY-{apt.ref}"
    apt.fast_track_paid = True
    apt.fast_track_payment_status = "PAID"
    apt.fast_track_payment_ref = ref
    apt.fast_track_paid_at = now_naive()
    audit("FASTTRACK_BOOKING_PAID", "appointment", apt.id,
          {"ref": apt.ref, "payment_ref": ref, "amount": apt.fast_track_amount}, org_id=apt.org_id)
    if apt.phone:
        try:
            from .. import sms_pack, sms as sms_engine
            from ..models import Organization
            from ..tasks import dispatch_delivery
            org = db.session.get(Organization, apt.org_id)
            body = sms_pack.fasttrack_paid(org, day=apt.appointment_date,
                                           time=apt.appointment_time, ref=apt.ref)
            sms_engine.queue_sms(apt.org_id, apt.phone, body, kind="confirmation",
                                 entity_type="appointment", entity_id=apt.id)
            dispatch_delivery()
        except Exception:
            pass
    db.session.commit()
    flash(f"⭐ {apt.patient_name} Fast Track marked PAID — {ref} — gold lane ready.", "success")
    return redirect(url_for("bookings.staff_list"))


# Note: appointment check-in is handled by /bookings/<id>/checkin-queue
# (see app/views/queue.py) which also issues the patient's queue ticket.
