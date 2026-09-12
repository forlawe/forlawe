"""Triage desk — Stage B. Place patients into a clinic and a doctor's room."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import tracking, triage
from ..audit import audit
from ..models import (CATEGORY_LABELS, CLINIC_LABELS, CLINICS,
                      CONSULTING_ROOMS, DoctorSession, Patient, PatientVisit,
                      User, db, now_naive)
from ..servicepoints import (
    active_clinics as _sp_active_clinics,
    active_rooms as _sp_active_rooms,
    ensure_defaults as _sp_ensure,
)


def _clinics_for_template(org_id: int):
    """DB clinics if seeded, else fallback to hard-coded tuple. Returns list of (code,label)."""
    try:
        _sp_ensure(org_id)
        clinics = _sp_active_clinics(org_id)
        if clinics:
            return [(c.code, c.name) for c in clinics], {c.code: c.name for c in clinics}
    except Exception:
        pass
    return list(CLINICS), dict(CLINIC_LABELS)


def _rooms_for_template(org_id: int):
    try:
        rooms = _sp_active_rooms(org_id)
        if rooms:
            return [r.name for r in rooms], [r.code for r in rooms]
    except Exception:
        pass
    return list(CONSULTING_ROOMS), list(CONSULTING_ROOMS)
from ..security import require_role

bp = Blueprint("triage", __name__, url_prefix="/triage")

# The triage bench is nurse-run; management can see it.
DESK = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "APEX_NURSE", "HOD")
VIEWERS = DESK + ("MD_CEO", "DMD", "DCST")


def _visit(vid: int) -> PatientVisit:
    v = db.session.get(PatientVisit, vid)
    if v is None or v.org_id != current_user.org_id:
        from flask import abort
        abort(404)
    return v


# ================================================================ the bench
@bp.get("/")
@require_role(*VIEWERS)
def bench():
    org_id = current_user.org_id
    clinics_tuple, clinic_labels = _clinics_for_template(org_id)
    queue = triage.waiting(org_id)
    patients = {p.id: p for p in db.session.query(Patient)
                .filter(Patient.id.in_([v.patient_id for v in queue] or [0])).all()}
    sessions = triage.ready_doctors(org_id)
    load = triage.doctor_load(org_id)
    rows = []
    for v in queue:
        p = patients.get(v.patient_id)
        clinic = triage.suggest_clinic_with_cover(org_id, p) if p else "OPD"
        # PRE-SELECT the free doctor with the shortest queue.
        suggested = triage.suggest_doctor(org_id, clinic)
        try:
            journey_est = tracking.estimate_remaining_journey(org_id, v)
        except Exception:
            journey_est = {"total": 0, "stages": [], "fast_track": bool(v.is_fast_track)}
        rows.append({
            "visit": v,
            "patient": p,
            "waited": triage.wait_minutes(v),
            "suggest_clinic": clinic,
            "suggest_session_id": suggested.id if suggested else None,
            "journey_estimate": journey_est,
        })
    return render_template(
        "triage/bench.html", rows=rows, sessions=sessions, load=load,
        clinics=clinics_tuple, clinic_labels=clinic_labels,
        category_labels=CATEGORY_LABELS, stats=triage.stats(org_id),
        placed=triage.placed_today(org_id), long_wait=triage.LONG_WAIT_MINUTES)


@bp.post("/<int:vid>/place")
@require_role(*DESK)
def place(vid: int):
    visit = _visit(vid)
    patient = db.session.get(Patient, visit.patient_id)
    clinic = (request.form.get("clinic") or "").strip().upper()

    session = None
    sid = request.form.get("session_id", type=int)
    if sid:
        session = db.session.get(DoctorSession, sid)
        if session is None or session.org_id != current_user.org_id:
            flash("That consulting room is no longer available.", "error")
            return redirect(url_for("triage.bench"))

    err = triage.place(visit, clinic=clinic, session=session,
                       blood_sugar_done=bool(request.form.get("blood_sugar_done")),
                       user_id=current_user.id)
    if err:
        flash(err, "error")
        return redirect(url_for("triage.bench"))

    tracking.safely(tracking.enter, visit.org_id, "WAIT_DOCTOR", visit_id=visit.id,
                   patient_id=visit.patient_id,
                   department_id=visit.department_id,
                   staff_id=session.doctor_id if session else None)
    triage.announce_placement(visit, patient, session)
    if clinic == "EMERGENCY":
        triage.announce_emergency(visit, patient)
    # v2 personal TV + queue estimator update
    try:
        from .. import personal_tv
        pt_sess = personal_tv.ensure_personal_session(visit.org_id, visit=visit)
        personal_tv.update_session_from_visit(pt_sess)
        doctor_name = session.doctor.name if session and session.doctor else (visit.consulting_room or "Doctor")
        personal_tv.notify_patient_personal(pt_sess, title="Placed for Doctor", body=f"{patient.full_name} — now waiting for {doctor_name}", data={"stage": "WAIT_DOCTOR"})
    except Exception:
        pass
    audit("PATIENT_TRIAGED", "patient_visit", visit.id,
          {"clinic": clinic, "room": visit.consulting_room,
           "doctor": session.doctor.name if session and session.doctor else None})
    db.session.commit()

    where = visit.consulting_room or CLINIC_LABELS.get(clinic, clinic)
    flash(f"{patient.full_name} placed in {where}.", "success")
    return redirect(url_for("triage.bench"))


@bp.post("/call-long-waiters")
@require_role(*DESK)
def call_long_waiters():
    """Nobody should be forgotten on a bench."""
    n = triage.announce_long_waits(current_user.org_id)
    db.session.commit()
    flash(f"Called {n} patient(s) who have been waiting a long time."
          if n else "Nobody has been waiting too long. Well done.", "success")
    return redirect(url_for("triage.bench"))


# ================================================================ doctors
@bp.get("/consulting-room")
@require_role(*VIEWERS)
def consulting_room():
    """Superseded by the full Stage C room, which can also call patients in
    and route them onward. Kept so older links and bookmarks still work."""
    from flask import redirect as _redirect, url_for as _url_for
    return _redirect(_url_for("consulting.room"))


@bp.get("/consulting-room/legacy")
@require_role(*VIEWERS)
def consulting_room_legacy():
    org_id = current_user.org_id
    clinics_tuple, clinic_labels = _clinics_for_template(org_id)
    rooms_list, _ = _rooms_for_template(org_id)
    mine = (db.session.query(DoctorSession)
            .filter_by(org_id=org_id, doctor_id=current_user.id,
                       duty_date=now_naive().date(), ended_at=None).first())
    start = now_naive().replace(hour=0, minute=0, second=0, microsecond=0)
    queue = (db.session.query(PatientVisit)
             .filter(PatientVisit.org_id == org_id,
                     PatientVisit.doctor_id == current_user.id,
                     PatientVisit.started_at >= start,
                     PatientVisit.status.in_(("TRIAGED", "IN_CONSULTATION")))
             .order_by(PatientVisit.triaged_at.asc()).all())
    patients = {p.id: p for p in db.session.query(Patient)
                .filter(Patient.id.in_([v.patient_id for v in queue] or [0])).all()}
    return render_template("triage/consulting_room.html", session=mine,
                           clinics=clinics_tuple, rooms=rooms_list,
                           queue=queue, patients=patients,
                           clinic_labels=clinic_labels,
                           available=triage.is_available(org_id, current_user.id))


@bp.post("/ready")
@require_role(*VIEWERS)
def ready():
    session, err = triage.open_session(
        current_user.org_id, current_user,
        (request.form.get("clinic") or "").strip().upper(),
        (request.form.get("consulting_room") or "").strip())
    if err:
        flash(err, "error")
        return redirect(url_for("triage.consulting_room"))
    audit("DOCTOR_READY_TO_CONSULT", "doctor_session", session.id,
          {"clinic": session.clinic, "room": session.consulting_room})
    db.session.commit()
    flash(f"You are ready to consult in {session.consulting_room}. "
          f"Triage can now send you patients.", "success")
    return redirect(url_for("triage.consulting_room"))


@bp.post("/not-ready")
@require_role(*VIEWERS)
def not_ready():
    closed = triage.close_session(current_user.org_id, current_user.id)
    if closed:
        audit("DOCTOR_STOPPED_CONSULTING", "user", current_user.id, {})
        db.session.commit()
        flash("You are no longer taking new patients. Triage has been told.",
              "success")
    return redirect(url_for("triage.consulting_room"))
