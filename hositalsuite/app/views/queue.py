"""Queue management (spec §6): digital tickets, staff control, privacy-safe screens."""
from __future__ import annotations

import re
import secrets

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user

from .. import sms as sms_engine
from ..audit import audit
from ..models import Appointment, Department, QueueTicket, db, now_naive
from ..navigation import require_permission
from ..security import rate_limit, require_login, require_role

bp = Blueprint("queue", __name__)

PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _default_org():
    """Tenant for this request (see services.current_org)."""
    from ..services import current_org
    return current_org()


def _dept_letter(dept: Department) -> str:
    return re.sub(r"[^A-Z]", "", dept.name.upper())[:1] or "Q"


def next_ticket(org_id: int, dept: Department, day) -> QueueTicket:
    count = (db.session.query(QueueTicket)
             .filter_by(org_id=org_id, department_id=dept.id, queue_date=day).count())
    return count + 1


def avg_service_minutes(org_id: int, department_id: int) -> float | None:
    """Average time from joining to being served (last 15 completed tickets)."""
    done = (db.session.query(QueueTicket)
            .filter_by(org_id=org_id, department_id=department_id, status="DONE")
            .filter(QueueTicket.served_at.isnot(None))
            .order_by(QueueTicket.served_at.desc()).limit(15).all())
    spans = [(t.served_at - t.created_at).total_seconds() / 60 for t in done if t.served_at]
    if len(spans) < 3:
        return None
    return sum(spans) / len(spans)


# ================================================================ PUBLIC
def announce_queue_depth(org_id: int, dept: Department) -> None:
    """Tell the department how many patients are now waiting.

    Goes to BOTH the individual staff of that department (their own phone) and
    the shared station screen, which is what the founder asked for.
    """
    from .. import announce
    from ..models import QueueTicket as QT
    waiting = (db.session.query(QT)
               .filter(QT.org_id == org_id, QT.department_id == dept.id,
                       QT.queue_date == now_naive().date(),
                       QT.status == "WAITING").count())
    if waiting <= 0:
        return
    kind = "dispensary_waiting" if "pharm" in (dept.name or "").lower() else "queue_waiting"
    place = dept.name
    # personal devices: staff assigned to that department
    for role in ("HOD", "ADMIN_MANAGER"):
        announce.to_role(org_id, role, kind, department_id=dept.id,
                         count=waiting, place=place,
                         entity_type="department", entity_id=dept.id)
    # shared station screen for the area
    announce.to_station(org_id, kind, department_id=dept.id,
                        name=dept.name, count=waiting, place=place)


@bp.get("/queue/join")
@rate_limit(limit=30, window=60.0)
def join_page():
    org = _default_org()
    if not org:
        abort(503)
    from ..patient_places import public_departments
    # Founder: Link queue only to Reception + Fast Track, show as Patient on Queue with priority for today's date only
    is_emergency = request.args.get("emergency") == "1"
    if is_emergency:
        # Emergency goes straight to Accident & Emergency
        depts = public_departments(org.id, only_reception=False)
        # Pre-select Accident & Emergency if exists
        emergency_dept = next((d for d in depts if "emergency" in d.name.lower() or "accident" in d.name.lower()), None)
        pre = emergency_dept.id if emergency_dept else None
    else:
        depts = public_departments(org.id, only_reception=True)
        pre = request.args.get("dept", type=int)
    db.session.commit()
    loc = (request.args.get("loc") or "").strip().upper()
    return render_template("queue_join.html", org=org, depts=depts, pre=pre, loc=loc, is_emergency=is_emergency)


@bp.post("/queue/join")
@rate_limit(limit=10, window=120.0)
def join_submit():
    org = _default_org()
    if not org:
        abort(503)
    now = now_naive()
    dept = db.session.get(Department, request.form.get("department_id", type=int) or 0)
    name = (request.form.get("patient_name") or "").strip()
    phone = (request.form.get("phone") or "").strip().replace(" ", "")
    if not dept or dept.org_id != org.id or len(name) < 2:
        flash("Please choose a department and enter your name.", "error")
        return redirect(url_for("queue.join_page"))
    if phone and not PHONE_RE.match(phone):
        flash("Please enter a valid phone number or leave it empty.", "error")
        return redirect(url_for("queue.join_page"))

    from ..patient_places import is_fast_track_dept
    is_fast = bool(request.form.get("is_fast_track")) or is_fast_track_dept(dept)
    fast_reason = (request.form.get("fast_track_reason") or "").strip().upper()[:40] or None
    # MUST consent for Fast Track — premium service
    if is_fast:
        if not request.form.get("fast_track_consent"):
            flash("To join Fast Track, you must tick the box that says you understand it is a premium service and you agree to pay a little more for quick service.", "error")
            return redirect(url_for("queue.join_page"))
    n = next_ticket(org.id, dept, now.date())
    # Link to existing patient folder if phone matches — closes gap #4
    patient_id = None
    if phone:
        try:
            from ..models import Patient
            pat = db.session.query(Patient).filter_by(org_id=org.id, phone=phone).first()
            if pat:
                patient_id = pat.id
        except Exception:
            patient_id = None
    t = QueueTicket(
        org_id=org.id,
        code=f"{_dept_letter(dept)}-{n:03d}",
        access_key=secrets.token_urlsafe(12),
        department_id=dept.id,
        queue_date=now.date(),
        patient_name=name[:120],
        phone=phone or None,
        patient_id=patient_id,
        status="WAITING",
        source="qr" if request.form.get("loc") else "link",
        is_fast_track=is_fast,
        fast_track_reason=fast_reason if is_fast else None,
    )
    db.session.add(t)
    db.session.flush()
    from .. import referrals as refeng
    refeng.stamp_queue(org.id)
    audit("QUEUE_JOINED", "queue_ticket", t.id, {"code": t.code}, org_id=org.id)

    # v2: Create Personal TV session — replaces SMS for patients inside hospital (cost saver)
    # Founder rule: No SMS for patients within hospital except serious complaints/emergency
    sess = None
    try:
        from .. import personal_tv as ptv
        sess = ptv.ensure_personal_session(org.id, ticket=t)
        ptv.update_session_from_ticket(sess, t)
    except Exception:
        current_app.logger.exception("personal TV session create failed")

    # Announce to the department: staff hear how many are now waiting.
    try:
        announce_queue_depth(org.id, dept)
    except Exception:                                    # noqa: BLE001
        current_app.logger.exception("queue announcement failed")

    # v2: No SMS for patients inside hospital — use Personal TV + Push + Voice + Main TV (free)
    # Only SMS if patient outside or emergency — we don't know location yet, assume inside, so NO SMS
    # If phone provided, we still have it for emergency fallback, but not for queue_number
    # Old code that sent SMS for queue_number is removed for cost saving — founder rule

    db.session.commit()
    # Redirect to new personal TV page /t/<access_key> — premium tracker, works closed like alarm
    # Use session key if available, else ticket key (they are same now after fix)
    redirect_key = sess.access_key if sess and getattr(sess, 'access_key', None) else t.access_key
    return redirect(f"/t/{redirect_key}")


@bp.get("/queue/ticket")
@rate_limit(limit=60, window=60.0, key_extra="ticket")
def ticket_page():
    key = request.args.get("key", "")
    t = db.session.query(QueueTicket).filter_by(access_key=key).first()
    if not t:
        return render_template("error.html", code=404, message="Queue ticket not found."), 404
    waiting = (db.session.query(QueueTicket)
               .filter_by(org_id=t.org_id, department_id=t.department_id,
                          queue_date=t.queue_date, status="WAITING")
               .filter(QueueTicket.id < t.id).count()) if t.status == "WAITING" else 0
    avg = avg_service_minutes(t.org_id, t.department_id)
    est = int(waiting * avg) if (avg and t.status == "WAITING") else None
    now_serving = (db.session.query(QueueTicket)
                   .filter_by(org_id=t.org_id, department_id=t.department_id,
                              queue_date=t.queue_date, status="CALLED")
                   .order_by(QueueTicket.called_at.desc()).first())

    # --- Link to reception intake + visit journey (TV ↔ patient page) ---
    intake = None
    visit = None
    segments = []
    onward = []
    total_m = 0
    journey_total = None
    try:
        from ..models import ReceptionIntake, PatientVisit, JourneySegment, VisitOnward
        from .. import tracking as tracking_engine
        # intake linked from ticket or by phone/name today
        if getattr(t, 'intake_id', None):
            intake = db.session.get(ReceptionIntake, t.intake_id)
        if not intake and t.phone:
            # try find today's intake by phone
            from ..models import now_naive as _now
            start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
            intake = (db.session.query(ReceptionIntake)
                      .filter(ReceptionIntake.org_id == t.org_id,
                              ReceptionIntake.phone == t.phone,
                              ReceptionIntake.created_at >= start)
                      .order_by(ReceptionIntake.created_at.desc()).first())
        if intake and intake.visit_id:
            visit = db.session.get(PatientVisit, intake.visit_id)
        if intake and not visit and intake.patient_id:
            # latest visit for this patient today
            from ..models import now_naive as _now
            start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
            visit = (db.session.query(PatientVisit)
                     .filter(PatientVisit.org_id == t.org_id,
                             PatientVisit.patient_id == intake.patient_id,
                             PatientVisit.started_at >= start)
                     .order_by(PatientVisit.started_at.desc()).first())
        if visit:
            segments = (db.session.query(JourneySegment)
                        .filter(JourneySegment.visit_id == visit.id)
                        .order_by(JourneySegment.entered_at.asc()).all())
            onward = (db.session.query(VisitOnward)
                      .filter(VisitOnward.visit_id == visit.id)
                      .order_by(VisitOnward.sent_at.asc()).all())
            # door to door
            if segments:
                from datetime import datetime as _dt
                first = segments[0].entered_at
                last = segments[-1].ended_at or _dt.utcnow()
                try:
                    total_m = max(0, int((last - first).total_seconds() // 60))
                except Exception:
                    total_m = 0
            try:
                est_j = tracking_engine.estimate_remaining_journey(t.org_id, visit)
                journey_total = est_j.get('total')
            except Exception:
                journey_total = None
    except Exception:
        # never crash patient page
        intake = intake
        segments = []
        onward = []
        total_m = 0

    return render_template("queue_ticket.html", t=t, ahead=waiting, est=est,
                           now_serving=now_serving, intake=intake, visit=visit,
                           segments=segments, onward=onward, total_m=total_m,
                           journey_total=journey_total)


@bp.get("/queue/screen")
def screen():
    """Privacy-safe display: ticket numbers only — never names (§6). Multi-hospital scoped."""
    org = _default_org()
    if not org:
        abort(503)
    dept_id = request.args.get("dept", type=int)
    dept = None
    try:
        dept = db.session.get(Department, dept_id) if dept_id else None
        if dept and dept.org_id != org.id:
            dept = None
    except Exception:
        dept = None
    today = now_naive().date()
    now_serving = None
    upcoming = []
    try:
        if dept:
            now_serving = (db.session.query(QueueTicket)
                           .filter_by(org_id=org.id, department_id=dept.id, queue_date=today,
                                      status="CALLED").order_by(QueueTicket.called_at.desc()).first())
            upcoming = (db.session.query(QueueTicket)
                        .filter_by(org_id=org.id, department_id=dept.id, queue_date=today,
                                   status="WAITING").order_by(QueueTicket.id).limit(6).all())
        depts = (db.session.query(Department)
                 .filter_by(org_id=org.id, active=True).order_by(Department.name).all())
    except Exception:
        # Never crash public screen — TV must stay up
        depts = []
    try:
        resp = render_template("queue_screen.html", org=org, dept=dept, depts=depts,
                               now_serving=now_serving, upcoming=upcoming)
        return resp
    except Exception:
        # Fallback minimal response if template fails
        return f"<html><body><h1>{org.name} Queue</h1><p>Screen loading...</p></body></html>", 200


# ================================================================ STAFF — patient queue contains PII, front desk + management only
@bp.get("/queue")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD", "APEX_NURSE")
def staff_queue():
    # v1.7.18: LIMIT HOD/APEX_NURSE to own Dept/Section/Unit, System Admin upgrades, STAFF not allowed here (view only via bookings/roster)
    from ..roles import visible_department_ids
    today = now_naive().date()
    dept_id = request.args.get("dept", type=int)
    q = db.session.query(QueueTicket).filter_by(org_id=current_user.org_id, queue_date=today)
    visible = visible_department_ids(current_user)
    if visible is not None:
        q = q.filter(QueueTicket.department_id.in_(visible or [-1]))
        # Also restrict dept_id param to visible only
        if dept_id and dept_id not in visible:
            dept_id = None
    if dept_id:
        q = q.filter(QueueTicket.department_id == dept_id)
    # Priority lane first — fast-track patients seen first at every desk
    waiting = q.filter(QueueTicket.status == "WAITING").order_by(QueueTicket.is_fast_track.desc(), QueueTicket.id).all()
    called = q.filter(QueueTicket.status == "CALLED").order_by(QueueTicket.called_at.desc()).all()
    done_count = q.filter(QueueTicket.status.in_(("DONE", "NO_SHOW"))).count()
    depts_q = db.session.query(Department).filter_by(org_id=current_user.org_id, active=True)
    if visible is not None:
        depts_q = depts_q.filter(Department.id.in_(visible or [-1]))
    depts = depts_q.all()
    return render_template("queue_staff.html", waiting=waiting, called=called,
                           done_count=done_count, depts=depts, dept_id=dept_id, today=today)


@bp.post("/queue/<int:tid>/call-next")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "HOD", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR")
def call_next(tid: int):
    """Staff control: call the next waiting ticket (progression)."""
    dept_id = request.form.get("department_id", type=int)
    t = None
    if tid:
        t = db.session.get(QueueTicket, tid)
        if not t or t.org_id != current_user.org_id:
            abort(404)
        if t.status != "WAITING":
            flash("That ticket is no longer waiting.", "error")
            return redirect(url_for("queue.staff_queue", dept=dept_id))
    else:
        t = (db.session.query(QueueTicket)
             .filter_by(org_id=current_user.org_id, department_id=dept_id,
                        queue_date=now_naive().date(), status="WAITING")
             .order_by(QueueTicket.id).first())
        if not t:
            flash("No patients waiting in this queue.", "info")
            return redirect(url_for("queue.staff_queue", dept=dept_id))
    t.status = "CALLED"
    t.called_at = now_naive()
    audit("QUEUE_CALLED", "queue_ticket", t.id, {"code": t.code})

    # v2: Personal TV + Push + Voice + Main TV — NO SMS for inside patients (cost saver, founder rule)
    # Only SMS if patient outside hospital or emergency — check presence
    try:
        from .. import personal_tv as ptv
        from ..models_v2 import PersonalTvSession
        sess = db.session.query(PersonalTvSession).filter_by(org_id=t.org_id, ticket_id=t.id).first()
        if not sess:
            sess = ptv.ensure_personal_session(t.org_id, ticket=t)
        ptv.update_session_from_ticket(sess, t)

        # Notify via personal TV + push (free, works closed like alarm)
        from ..notifications_v2 import notify_patient_personal
        from .. import queue_estimator
        place = t.department.name if t.department else "OPD"
        # Smart wait already computed
        notify_patient_personal(
            t.org_id, sess.access_key, "queue_next",
            {"code": t.code, "place": place, "hospital": ""},
            title="You are next!",
            body=f"{t.patient_name or 'Patient'}, you are next. Ticket {t.code}, {place}. Please walk to the desk now.",
            is_complaint_or_emergency=False
        )

        # Voice announcement on Main TV + personal voice
        from .. import announce
        spoken = announce.speech_name(t.patient_name or "patient")
        announce.to_station(t.org_id, "consult_call_in", patient=spoken, room=place,
                            entity_type="queue_ticket", entity_id=t.id)

        # Push via push.py already queued by notify_patient_personal
    except Exception:
        current_app.logger.exception("personal TV notify failed")

    # SMS fallback ONLY if patient outside hospital or no personal TV session (feature phone provision)
    # Founder rule: No SMS inside except emergency/complaints
    # So we check is_inside_hospital flag — if False, then SMS allowed
    try:
        from ..models_v2 import PersonalTvSession
        sess = db.session.query(PersonalTvSession).filter_by(org_id=t.org_id, ticket_id=t.id).first()
        should_sms = False
        if sess and not sess.is_inside_hospital:
            should_sms = True
        elif not sess:
            # No personal TV — maybe feature phone — allow SMS as fallback for queue_next (important)
            # But still try to avoid — only if phone present and no push subscription
            from ..models_v2 import PushSubscription
            has_push = db.session.query(PushSubscription).filter_by(org_id=t.org_id, patient_access_key=t.access_key if hasattr(t, 'access_key') else None, is_active=True).first()
            if not has_push and t.phone:
                should_sms = True

        if should_sms and t.phone:
            from .. import sms_pack
            from ..models import Organization
            org = db.session.get(Organization, t.org_id)
            sms_engine.queue_sms(t.org_id, t.phone,
                                 sms_pack.queue_next(org, ticket=t.code,
                                                     dept=t.department.name if t.department else "OPD"),
                                 kind="alert",
                                 entity_type="queue_ticket", entity_id=t.id)
            from ..tasks import dispatch_delivery
            dispatch_delivery()
    except Exception:
        pass

    db.session.commit()
    flash(f"Called {t.code}. Personal TV + Voice + Push notified (no SMS inside).", "success")
    return redirect(url_for("queue.staff_queue", dept=t.department_id))


@bp.post("/queue/<int:tid>/finish")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "HOD", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR")
def finish(tid: int):
    t = db.session.get(QueueTicket, tid)
    if not t or t.org_id != current_user.org_id:
        abort(404)
    outcome = request.form.get("outcome", "done")
    if outcome == "no_show":
        t.status = "NO_SHOW"
    else:
        t.status = "DONE"
        t.served_at = now_naive()
    audit("QUEUE_FINISHED", "queue_ticket", t.id, {"code": t.code, "outcome": t.status})
    db.session.commit()
    return redirect(url_for("queue.staff_queue", dept=t.department_id))


@bp.post("/queue/<int:tid>/to-reception")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "HOD", "MD_CEO")
def to_reception(tid: int):
    """Convert a QR queue ticket into a Reception intake — unifies the two queues.

    WHY THIS EXISTS (founder question #3)
    -------------------------------------
    QueueTicket (patient self-joins via /queue/join QR) and PatientVisit
    (Reception → HIMS → Triage → Doctor → Onward) were two separate worlds.
    A patient could have a ticket AND a visit, staff had two lists, and the
    patient screen showed only half the journey.

    Best approach: keep both entry points (QR is valuable), but link them.
    When staff tap \"Send to Reception\", we create a ReceptionIntake from the
    ticket, link them, and voice-announce so Reception knows someone is coming.
    The ticket is marked DONE, the journey continues as one.
    """
    from .. import announce, reception as reception_engine
    from ..models import ReceptionIntake

    t = db.session.get(QueueTicket, tid)
    if not t or t.org_id != current_user.org_id:
        abort(404)
    if t.status != "WAITING" and t.status != "CALLED":
        flash("That ticket is no longer waiting.", "error")
        return redirect(url_for("queue.staff_queue", dept=t.department_id))

    # Split name into surname/first for intake (best effort)
    parts = (t.patient_name or "").strip().split()
    surname = parts[-1] if parts else "—"
    first = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "Patient")

    # Create intake — preserve fast-track
    intake = ReceptionIntake(
        org_id=t.org_id,
        ref=reception_engine.next_ref(t.org_id),
        surname=surname[:80],
        first_name=first[:80],
        phone=t.phone,
        stage="RECEPTION",
        created_by=current_user.id,
        is_fast_track=bool(getattr(t, "is_fast_track", False)),
        fast_track_reason=getattr(t, "fast_track_reason", None),
    )
    db.session.add(intake)
    db.session.flush()

    # Link ticket → intake → journey
    t.intake_id = intake.id
    t.status = "DONE"
    t.served_at = now_naive()

    # Tracking + voice
    try:
        from .. import tracking

        tracking.safely(tracking.enter, t.org_id, "RECEPTION", intake_id=intake.id, staff_id=current_user.id)
        spoken = announce.speech_name(t.patient_name or "patient")
        announce.to_station(t.org_id, "reception_arrival", patient=spoken, detail=f"from queue {t.code}")
    except Exception:
        pass

    audit("QUEUE_TO_RECEPTION", "queue_ticket", t.id, {"code": t.code, "intake_ref": intake.ref})
    db.session.commit()
    flash(f"{t.patient_name or 'Patient'} ({t.code}) sent to Reception as {intake.ref}.", "success")
    return redirect(url_for("queue.staff_queue", dept=t.department_id))


@bp.post("/bookings/<int:aid>/checkin-queue")
@require_login
@require_permission("bookings")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "HOD", "MD_CEO")
def booking_checkin_queue(aid: int):
    """Check a booking in and give the patient a queue ticket — gates on Fast Track payment upfront."""
    from .. import services
    apt = db.session.get(Appointment, aid)
    if not apt or apt.org_id != current_user.org_id:
        abort(404)
    if apt.status != "BOOKED":
        flash("Only a booked appointment can be checked in.", "error")
        return redirect(url_for("bookings.staff_list"))
    # Payment gate: if Fast Track booking requires payment upfront, block until PAID or WAIVED
    requires_pay = bool(services.get_setting(apt.org_id, "fast_track_booking_requires_payment"))
    if apt.is_fast_track and requires_pay:
        if apt.fast_track_payment_status not in ("PAID", "WAIVED"):
            flash(f"⭐ Payment required before check-in for {apt.patient_name} — Fast Track amount {apt.fast_track_amount or ''}. Mark as PAID first.", "error")
            return redirect(url_for("bookings.staff_list"))
    now = now_naive()
    apt.status = "ARRIVED"
    apt.arrived_at = now
    n = next_ticket(apt.org_id, apt.department, apt.appointment_date)
    # Fast Track Booking linked to Reception — preserve gold flag
    ft = bool(getattr(apt, 'is_fast_track', False))
    ft_reason = getattr(apt, 'fast_track_reason', None) or "PREMIUM"
    t = QueueTicket(org_id=apt.org_id, code=f"{_dept_letter(apt.department)}-{n:03d}",
                    access_key=secrets.token_urlsafe(12), department_id=apt.department_id,
                    queue_date=apt.appointment_date, patient_name=apt.patient_name,
                    phone=apt.phone, status="WAITING", source="booking", appointment_id=apt.id,
                    is_fast_track=ft, fast_track_reason=ft_reason if ft else None)
    db.session.add(t)
    db.session.flush()
    audit("BOOKING_ARRIVED", "appointment", apt.id, {"ref": apt.ref, "queue": t.code, "fast_track": ft, "paid": apt.fast_track_payment_status})
    db.session.commit()
    flash(f"⭐ {apt.patient_name} checked in — queue ticket {t.code} gold lane.", "success")
    return redirect(url_for("queue.staff_queue", dept=apt.department_id))
