"""LAHSMA desk — simple clearance, just flow tracking.

Founder: \"limited to seeing patient together with policy numbers and attend to
them with basic minimum by issuing clearance. just like billing issues Bill\"

This is NOT a claims engine. LAHSMA has their own web app for policy management.
This desk just tracks that the patient was sent here and clearance was issued.
"""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user

from .. import lahsma, tracking
from ..audit import audit
from ..models import VisitOnward, db
from ..navigation import require_permission
from ..security import require_role

bp = Blueprint("lahsma", __name__)

DESK = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
VIEWERS = DESK + ("MD_CEO", "DMD", "DCST", "APEX_NURSE")


@bp.get("/lahsma")
@require_role(*VIEWERS)
@require_permission("lahsma")
def desk():
    org_id = current_user.org_id
    rows = lahsma.pending(org_id)
    return render_template(
        "lahsma/desk.html",
        rows=rows,
        count=len(rows),
    )


@bp.post("/lahsma/<int:step_id>/clear")
@require_role(*DESK)
@require_permission("lahsma")
def clear(step_id: int):
    step = db.session.get(VisitOnward, step_id)
    if step is None or step.org_id != current_user.org_id:
        from flask import abort

        abort(404)
    if step.destination != "LAHSMA":
        flash("That patient is not waiting at LAHSMA.", "error")
        return redirect(url_for("lahsma.desk"))
    if step.status == "DONE":
        flash("Clearance already issued for that patient.", "error")
        return redirect(url_for("lahsma.desk"))

    tracking.safely(tracking.leave, step.org_id, visit_id=step.visit_id, stage="LAHSMA")
    closed = lahsma.issue_clearance(step, current_user.id)
    if closed:
        tracking.safely(tracking.close_journey, step.org_id, visit_id=step.visit_id)
        try:
            from .. import aftercare
            from ..models import Patient, PatientVisit
            v = db.session.get(PatientVisit, step.visit_id)
            if v:
                pt = db.session.get(Patient, v.patient_id)
                if pt:
                    aftercare.thank_you_sms(step.org_id, v, pt)
        except Exception:
            pass

    audit(
        "LAHSMA_CLEARANCE_ISSUED",
        "visit_onward",
        step.id,
        {"destination": "LAHSMA", "closed_visit": closed},
    )
    db.session.commit()

    # Announce
    try:
        from .. import announce

        if step.visit_id:
            from ..models import Patient, PatientVisit

            visit = db.session.get(PatientVisit, step.visit_id)
            if visit:
                patient = db.session.get(Patient, visit.patient_id)
                if patient:
                    announce.to_station(
                        current_user.org_id,
                        "visit_complete" if closed else "desk_expecting",
                        patient=announce.speech_name(patient.spoken_name),
                        place="LAHSMA desk" if not closed else None,
                    )
    except Exception:
        pass

    flash(
        f"Clearance issued for {step.visit_id}. "
        + ("Visit closed — patient finished for today." if closed else "Sent onward if needed."),
        "success",
    )
    return redirect(url_for("lahsma.desk"))
