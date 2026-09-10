"""Stage C — the consulting room. Stage D — the onward desks."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import consulting, tracking, triage
from ..audit import audit
from ..models import (CLINIC_LABELS, CLINICS, CONSULTING_ROOMS,
                      ONWARD_DESTINATIONS, ONWARD_LABELS, DoctorSession,
                      Patient, PatientVisit, VisitOnward, db, now_naive)
from ..security import require_role
from ..servicepoints import (
    active_clinics as _sp_active_clinics,
    active_rooms as _sp_active_rooms,
    active_destinations as _sp_active_dests,
    destinations_for_clinic as _sp_dests_for_clinic,
    ensure_defaults as _sp_ensure,
)


def _clinics_for_template(org_id: int):
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
            return [r.name for r in rooms]
    except Exception:
        pass
    return list(CONSULTING_ROOMS)


def _destinations_for_template(org_id: int, clinic_code: str | None = None):
    """Clinic determines what will load — founder requirement."""
    try:
        if clinic_code:
            dests, is_shortlisted, all_suspended = _sp_dests_for_clinic(org_id, clinic_code)
            if all_suspended:
                return [], True, True
            if dests:
                return [(d.code, d.name) for d in dests], is_shortlisted, False
        all_d = _sp_active_dests(org_id)
        if all_d:
            return [(d.code, d.name) for d in all_d], False, False
    except Exception:
        pass
    return list(ONWARD_DESTINATIONS), False, False

bp = Blueprint("consulting", __name__)

# An onward destination and a journey stage are deliberately different things:
# BILLING at the front door is not the same measurement as BILLING after the
# consultation, and a manager needs to tell them apart.
_ONWARD_STAGE = {
    "LABORATORY": "LABORATORY", "PHARMACY": "PHARMACY",
    "BILLING": "BILLING_OUT", "MEGALEX": "MEGALEX",
    "LAHSMA": "LAHSMA", "EMERGENCY": "EMERGENCY",
}

CLINICAL = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "APEX_NURSE",
            "HOD", "MD_CEO", "DMD", "DCST")
# The onward desks (lab, pharmacy, billing, pay point) are staffed by the same
# front-of-house roles as Reception in this hospital.
DESKS = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "APEX_NURSE", "HOD")


def _visit(vid: int) -> PatientVisit:
    v = db.session.get(PatientVisit, vid)
    if v is None or v.org_id != current_user.org_id:
        from flask import abort
        abort(404)
    return v


# ================================================================ Stage C
@bp.get("/consulting-room")
@require_role(*CLINICAL)
def room():
    """The doctor's own call room queue: call in, then finish and route on."""
    org_id = current_user.org_id
    day = now_naive().date()
    session = (db.session.query(DoctorSession)
               .filter_by(org_id=org_id, doctor_id=current_user.id,
                          duty_date=day, ended_at=None).first())
    clinics_tuple, clinic_labels = _clinics_for_template(org_id)
    rooms_list = _rooms_for_template(org_id)

    # Clinic where doctor is consulting determines what destinations load
    clinic_code = session.clinic if session else None
    destinations, is_shortlisted, all_suspended = _destinations_for_template(org_id, clinic_code)

    queue = consulting.doctor_queue(org_id, current_user.id)
    patients = {p.id: p for p in db.session.query(Patient)
                .filter(Patient.id.in_([v.patient_id for v in queue] or [0])).all()}
    rows = []
    for v in queue:
        try:
            journey_est = tracking.estimate_remaining_journey(org_id, v)
        except Exception:
            journey_est = {"total": 0, "stages": [], "fast_track": bool(v.is_fast_track)}
        rows.append({
            "visit": v, "patient": patients.get(v.patient_id),
            "waited": consulting.wait_minutes(v),
            "unclaimed": v.doctor_id is None,
            "journey_estimate": journey_est,
        })
    return render_template(
        "consulting/room.html", session=session, rows=rows,
        current=consulting.in_consultation(org_id, current_user.id),
        patients=patients, clinics=clinics_tuple, rooms=rooms_list,
        clinic_labels=clinic_labels, destinations=destinations,
        is_shortlisted=is_shortlisted, all_suspended=all_suspended,
        doctor_clinic=clinic_code,
        available=triage.is_available(org_id, current_user.id))


@bp.post("/consulting-room/<int:vid>/call-in")
@require_role(*CLINICAL)
def call_in(vid: int):
    visit = _visit(vid)
    err = consulting.call_in(visit, current_user.id)
    if err:
        flash(err, "error")
        return redirect(url_for("consulting.room"))
    patient = db.session.get(Patient, visit.patient_id)
    tracking.safely(tracking.enter, visit.org_id, "CONSULTATION", visit_id=visit.id,
                   patient_id=visit.patient_id,
                   department_id=visit.department_id,
                   staff_id=current_user.id)
    consulting.announce_called_in(visit, patient)
    # v2 personal TV — patient called in, alarm-like
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(visit.org_id, visit=visit)
        personal_tv.update_session_from_visit(sess)
        personal_tv.notify_patient_personal(sess, title="You are next! Doctor calling", body=f"{patient.full_name} — please go to {visit.consulting_room or 'consulting room'} NOW", data={"stage":"CONSULTATION"})
    except Exception:
        pass
    audit("PATIENT_CALLED_IN", "patient_visit", visit.id,
          {"room": visit.consulting_room})
    db.session.commit()
    flash(f"{patient.full_name} has been called in to "
          f"{visit.consulting_room or 'your room'}.", "success")
    return redirect(url_for("consulting.room"))


@bp.post("/consulting-room/<int:vid>/finish")
@require_role(*CLINICAL)
def finish(vid: int):
    visit = _visit(vid)
    patient = db.session.get(Patient, visit.patient_id)
    destinations = request.form.getlist("destination")
    err, steps = consulting.finish(visit, current_user.id, destinations,
                                   note=request.form.get("note", ""))
    if err:
        flash(err, "error")
        return redirect(url_for("consulting.room"))

    if steps:
        tracking.safely(tracking.leave, visit.org_id, visit_id=visit.id)
        for step in steps:
            tracking.safely(tracking.enter, visit.org_id, _ONWARD_STAGE.get(step.destination, "PHARMACY"),
                           visit_id=visit.id, patient_id=visit.patient_id,
                           staff_id=current_user.id, close_previous=False)
    else:
        tracking.safely(tracking.close_journey, visit.org_id, visit_id=visit.id)
        # Thank-you — now via personal TV + push, not SMS (cost saver) unless outside
        try:
            from .. import personal_tv
            sess = personal_tv.ensure_personal_session(visit.org_id, visit=visit)
            personal_tv.update_session_from_visit(sess)
            personal_tv.notify_patient_personal(sess, title="Visit Finished ✅", body=f"Thank you {patient.full_name} — your visit is complete. Get well soon!", data={"stage":"DONE"})
        except Exception:
            pass
        try:
            from .. import aftercare
            aftercare.thank_you_sms(visit.org_id, visit, patient)
        except Exception:
            pass

    consulting.announce_onward(visit, patient, steps)
    # v2 onward notify personal TV
    try:
        from .. import personal_tv
        if steps:
            sess = personal_tv.ensure_personal_session(visit.org_id, visit=visit)
            personal_tv.update_session_from_visit(sess)
            where = ", ".join(ONWARD_LABELS.get(s.destination, s.destination).split(" — ")[0] for s in steps)
            personal_tv.notify_patient_personal(sess, title=f"Sent to {where}", body=f"{patient.full_name} — please go to {where}")
    except Exception:
        pass
    audit("CONSULTATION_FINISHED", "patient_visit", visit.id,
          {"sent_to": [s.destination for s in steps] or ["home"]})
    db.session.commit()

    if steps:
        where = ", ".join(ONWARD_LABELS.get(s.destination, s.destination).split(" — ")[0]
                          for s in steps)
        flash(f"{patient.full_name} sent to {where}.", "success")
    else:
        flash(f"{patient.full_name} is finished for today. Visit closed.", "success")
    return redirect(url_for("consulting.room"))


# ================================================================ Stage D
@bp.get("/onward")
@require_role(*DESKS)
def onward_board():
    """Every desk in one board: who has been sent to you, and how long ago."""
    org_id = current_user.org_id
    counts = consulting.pending_counts(org_id)
    # Use DB destinations if present
    try:
        _sp_ensure(org_id)
        db_dests = _sp_active_dests(org_id)
        if db_dests:
            dest_list = [(d.code, d.name) for d in db_dests]
        else:
            dest_list = list(ONWARD_DESTINATIONS)
    except Exception:
        dest_list = list(ONWARD_DESTINATIONS)

    boards = []
    for code, label in dest_list:
        steps = consulting.pending_for(org_id, code)
        visits = {v.id: v for v in db.session.query(PatientVisit)
                  .filter(PatientVisit.id.in_([s.visit_id for s in steps] or [0])).all()}
        patients = {p.id: p for p in db.session.query(Patient)
                    .filter(Patient.id.in_([v.patient_id for v in visits.values()] or [0])).all()}
        boards.append({
            "code": code, "label": label, "count": counts.get(code, 0),
            "rows": [{"step": s, "visit": visits.get(s.visit_id),
                      "patient": patients.get(visits[s.visit_id].patient_id)
                      if s.visit_id in visits else None,
                      "waited": max(0, int((now_naive() - s.sent_at).total_seconds() // 60))}
                     for s in steps],
        })
    return render_template("consulting/onward.html", boards=boards,
                           total=sum(counts.values()))


@bp.post("/onward/<int:step_id>/done")
@require_role(*DESKS)
def onward_done(step_id: int):
    step = db.session.get(VisitOnward, step_id)
    if step is None or step.org_id != current_user.org_id:
        from flask import abort
        abort(404)
    visit = db.session.get(PatientVisit, step.visit_id)
    patient = db.session.get(Patient, visit.patient_id) if visit else None

    tracking.safely(tracking.leave, step.org_id, visit_id=step.visit_id,
                   stage=_ONWARD_STAGE.get(step.destination))
    closed = consulting.complete_step(step, current_user.id)
    if closed:
        tracking.safely(tracking.close_journey, step.org_id, visit_id=step.visit_id)
        try:
            from .. import aftercare
            if patient is not None and visit is not None:
                aftercare.thank_you_sms(step.org_id, visit, patient)
        except Exception:
            pass
    if closed and patient is not None:
        consulting.announce_onward(visit, patient, [])
    audit("ONWARD_STEP_COMPLETED", "visit_onward", step.id,
          {"destination": step.destination, "closed_visit": closed})
    db.session.commit()

    name = patient.full_name if patient else "Patient"
    flash(f"{name} done at {step.label.split(' — ')[0]}."
          + (" Visit closed — they are finished for today." if closed else ""),
          "success")
    return redirect(url_for("consulting.onward_board"))
