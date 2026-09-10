"""Fast Track Desk — quick, calm, private premium service.

Fast Track is our premium service. Patients who choose it are seen quickly
in a quiet, comfortable lounge. No long queue. For anyone who values time
and comfort and is happy to pay a little more.

Their registration appears at Reception and Fast Track Desk right away,
marked gold so staff see them first.

This desk handles the full Fast Track journey:
- Reception → Billing → Pay → Registration → Nurse → Doctor → Lab / Pharmacy / Billing / LAHSMA / Emergency
- All Fast Track patients appear here and at Reception, marked gold
- We show estimated time left and speak their name in 4 languages

NOT an EMR — only names, codes, places, counts, payer info.
Per-tenant, SUPER_ADMIN + ADMIN_MANAGER + HOD can work it.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user

from .. import reception as reception_engine, tracking as tracking_engine, hims as hims_engine
from ..models import (
    Patient,
    PatientVisit,
    ReceptionIntake,
    QueueTicket,
    VisitOnward,
    db,
    now_naive,
)
from ..security import require_role
from ..audit import audit

bp = Blueprint("fasttrack", __name__)

DESK = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
VIEWERS = DESK + ("MD_CEO", "DMD", "DCST", "APEX_NURSE")

# Fast Track reasons — simple, human, premium
FAST_TRACK_REASONS = [
    ("PREMIUM", "Premium — Quick service, comfortable lounge"),
    ("BUSINESS", "Busy — I have little time today"),
    ("ELDERLY", "Elderly — Please help me be seen quickly"),
    ("PREGNANT", "Pregnant — Need quick attention"),
    ("CHILD", "Child — Small child needs fast care"),
    ("ASSISTANCE", "Need help — Wheelchair or mobility support"),
    ("FAMILY", "Family — Want to stay together and be seen fast"),
    ("VIP", "VIP — Private and fast service"),
]

FAST_TRACK_LABELS = dict(FAST_TRACK_REASONS)

# Keep old reasons for backward compatibility with existing data
LEGACY_REASONS = {
    "ELDERLY": "Elderly 60+",
    "PREGNANT": "Pregnant / Antenatal",
    "CHILD": "Child under 5",
    "WHEELCHAIR": "Wheelchair / Mobility",
}
ALL_LABELS = {**FAST_TRACK_LABELS, **LEGACY_REASONS}


def _fast_intakes(org_id: int):
    """All fast-track intakes mid-walk — priority gold."""
    return (
        db.session.query(ReceptionIntake)
        .filter(
            ReceptionIntake.org_id == org_id,
            ReceptionIntake.is_fast_track.is_(True),
            ReceptionIntake.stage.in_(("RECEPTION", "BILLING", "PAYMENT", "PAID", "REGISTERED")),
        )
        .order_by(ReceptionIntake.created_at.asc())
        .limit(200)
        .all()
    )


def _fast_visits(org_id: int):
    """All fast-track visits today that are not closed."""
    start = datetime.combine(now_naive().date(), datetime.min.time())
    return (
        db.session.query(PatientVisit)
        .filter(
            PatientVisit.org_id == org_id,
            PatientVisit.is_fast_track.is_(True),
            PatientVisit.started_at >= start,
            PatientVisit.status.notin_(("CLOSED", "CANCELLED")),
        )
        .order_by(PatientVisit.started_at.asc())
        .limit(200)
        .all()
    )


def _fast_tickets(org_id: int):
    """Fast-track queue tickets today."""
    return (
        db.session.query(QueueTicket)
        .filter(
            QueueTicket.org_id == org_id,
            QueueTicket.is_fast_track.is_(True),
            QueueTicket.queue_date == now_naive().date(),
            QueueTicket.status.in_(("WAITING", "CALLED")),
        )
        .order_by(QueueTicket.created_at.asc())
        .limit(100)
        .all()
    )


def _fast_onward(org_id: int):
    """Fast-track onward pending across all desks."""
    return (
        db.session.query(VisitOnward)
        .join(PatientVisit, VisitOnward.visit_id == PatientVisit.id)
        .filter(
            VisitOnward.org_id == org_id,
            VisitOnward.status == "PENDING",
            PatientVisit.is_fast_track.is_(True),
        )
        .order_by(VisitOnward.sent_at.asc())
        .limit(200)
        .all()
    )


@bp.get("/fasttrack")
@require_role(*VIEWERS)
def desk():
    org_id = current_user.org_id
    from .. import services as svc
    s = svc.org_settings_bundle(org_id)
    intakes = _fast_intakes(org_id)
    visits = _fast_visits(org_id)
    tickets = _fast_tickets(org_id)
    onward = _fast_onward(org_id)

    # Enrich visits with patient + journey + waited
    patient_ids = {v.patient_id for v in visits}
    patients = {p.id: p for p in db.session.query(Patient).filter(Patient.id.in_(patient_ids or [0])).all()}

    visit_rows = []
    for v in visits:
        p = patients.get(v.patient_id)
        waited = max(0, int((now_naive() - (v.triaged_at or v.started_at)).total_seconds() // 60))
        try:
            journey = tracking_engine.estimate_remaining_journey(org_id, v)
        except Exception:
            journey = {"total": 0, "stages": [], "fast_track": True}
        visit_rows.append(
            {
                "visit": v,
                "patient": p,
                "waited": waited,
                "journey": journey,
                "label": ALL_LABELS.get(v.fast_track_reason, v.fast_track_reason or "Premium"),
            }
        )

    # Enrich intakes with journey
    intake_rows = []
    for r in intakes:
        waited = max(0, int((now_naive() - r.created_at).total_seconds() // 60))
        try:
            journey = tracking_engine.estimate_intake_journey(org_id, r)
        except Exception:
            journey = {"total": 0, "stages": [], "fast_track": True}
        intake_rows.append(
            {
                "intake": r,
                "waited": waited,
                "journey": journey,
                "label": ALL_LABELS.get(r.fast_track_reason, r.fast_track_reason or "Premium"),
            }
        )

    # Enrich onward
    visit_map = {v.id: v for v in visits}
    # Need all visits for onward, not just today's fast visits (onward may have older)
    all_visit_ids = {s.visit_id for s in onward}
    all_visits = {v.id: v for v in db.session.query(PatientVisit).filter(PatientVisit.id.in_(all_visit_ids or [0])).all()}
    all_patient_ids = {v.patient_id for v in all_visits.values()}
    all_patients = {p.id: p for p in db.session.query(Patient).filter(Patient.id.in_(all_patient_ids or [0])).all()}

    onward_rows = []
    for s in onward:
        v = all_visits.get(s.visit_id)
        p = all_patients.get(v.patient_id) if v else None
        waited = max(0, int((now_naive() - s.sent_at).total_seconds() // 60))
        onward_rows.append(
            {
                "step": s,
                "visit": v,
                "patient": p,
                "waited": waited,
                "label": ALL_LABELS.get(getattr(v, 'fast_track_reason', None), getattr(v, 'fast_track_reason', '') if v else "Premium"),
            }
        )

    stats = {
        "intakes": len(intakes),
        "visits": len(visits),
        "tickets": len(tickets),
        "onward": len(onward),
        "total": len(intakes) + len(visits) + len(tickets),
    }

    return render_template(
        "fasttrack/desk.html",
        intake_rows=intake_rows,
        visit_rows=visit_rows,
        tickets=tickets,
        onward_rows=onward_rows,
        stats=stats,
        reasons=FAST_TRACK_REASONS,
        all_labels=ALL_LABELS,
        s=s,
    )


# --- Actions: same as reception but scoped to fast-track desk, audit under fast-track desk name ---

def _get_intake(iid: int) -> ReceptionIntake:
    row = db.session.get(ReceptionIntake, iid)
    if not row or row.org_id != current_user.org_id:
        abort(404)
    if not row.is_fast_track:
        flash("That patient is not Fast Track — use Reception desk.", "error")
        abort(400)
    return row


@bp.post("/fasttrack/<int:iid>/to-billing")
@require_role(*DESK)
def to_billing(iid: int):
    intake = _get_intake(iid)
    reception_engine.advance(intake, "BILLING", ref=(request.form.get("bill_ref") or ""))
    tracking_engine.safely(tracking_engine.enter, intake.org_id, "BILLING", intake_id=intake.id, staff_id=current_user.id)
    reception_engine.announce_stage(intake)
    audit("FASTTRACK_SENT_TO_BILLING", "reception_intake", intake.id, {"ref": intake.ref, "fast_track": True})
    db.session.commit()
    flash(f"⭐ {intake.full_name} (Fast Track) sent to Billing — gold lane.", "success")
    return redirect(url_for("fasttrack.desk"))


@bp.post("/fasttrack/<int:iid>/to-payment")
@require_role(*DESK)
def to_payment(iid: int):
    intake = _get_intake(iid)
    reception_engine.advance(intake, "PAYMENT", ref=(request.form.get("bill_ref") or ""))
    tracking_engine.safely(tracking_engine.enter, intake.org_id, "PAYMENT", intake_id=intake.id, staff_id=current_user.id)
    reception_engine.announce_stage(intake)
    audit("FASTTRACK_SENT_TO_PAYMENT", "reception_intake", intake.id, {"ref": intake.ref, "fast_track": True})
    db.session.commit()
    flash(f"⭐ {intake.full_name} (Fast Track) sent to Pay Point — executive fast.", "success")
    return redirect(url_for("fasttrack.desk"))


@bp.post("/fasttrack/<int:iid>/paid")
@require_role(*DESK)
def mark_paid(iid: int):
    intake = _get_intake(iid)
    reception_engine.advance(intake, "PAID", ref=(request.form.get("payment_ref") or ""))
    tracking_engine.safely(tracking_engine.enter, intake.org_id, "HIMS", intake_id=intake.id, staff_id=current_user.id)
    reception_engine.announce_stage(intake)
    audit("FASTTRACK_PAYMENT_RECORDED", "reception_intake", intake.id, {"ref": intake.ref, "receipt": intake.payment_ref, "fast_track": True})
    db.session.commit()
    flash(f"Payment recorded for ⭐ {intake.full_name} (Fast Track). HIMS can open folder in executive building.", "success")
    return redirect(url_for("fasttrack.desk"))


@bp.post("/fasttrack/<int:iid>/open-folder")
@require_role(*DESK)
def open_folder(iid: int):
    """Fast Track desk opens folder directly — premium, no waiting."""
    from .. import hims as hims_engine
    from ..services import current_org

    intake = _get_intake(iid)
    if intake.stage != "PAID":
        flash("Payment must be recorded before folder is opened.", "error")
        return redirect(url_for("fasttrack.desk"))
    if intake.patient_id:
        flash("Folder already opened.", "error")
        return redirect(url_for("fasttrack.desk"))

    org = current_org()
    if not org:
        abort(503)

    values, errors = hims_engine.validate(reception_engine.folder_values(intake), org_id=current_user.org_id)
    if errors:
        flash("Folder could not be opened: " + " ".join(errors), "error")
        return redirect(url_for("fasttrack.desk"))

    existing = hims_engine.possible_duplicates(current_user.org_id, values["surname"], values["first_name"], values.get("phone"))
    patient = existing[0] if existing else None

    if patient:
        for field in ("phone", "address", "occupation", "payer_type", "payer_number", "payer_name", "preferred_lang", "assistance", "care_note", "nok_name", "nok_phone", "nok_relationship"):
            nv = values.get(field)
            if nv:
                setattr(patient, field, nv)
        db.session.flush()
    else:
        patient = Patient(org_id=current_user.org_id, hospital_number=hims_engine.next_hospital_number(org), created_by=current_user.id, consent_at=now_naive(), **values)
        db.session.add(patient)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
            patient = Patient(org_id=current_user.org_id, hospital_number=hims_engine.next_hospital_number(org), created_by=current_user.id, consent_at=now_naive(), **values)
            db.session.add(patient)
            db.session.flush()

    visit = hims_engine.open_visit(patient, user_id=current_user.id, visit_type="NEW", is_fast_track=True, fast_track_reason=intake.fast_track_reason)
    db.session.flush()
    intake.patient_id = patient.id
    intake.visit_id = visit.id
    tracking_engine.safely(tracking_engine.attach_visit, current_user.org_id, intake.id, visit.id, patient.id)
    tracking_engine.safely(tracking_engine.enter, current_user.org_id, "TRIAGE", intake_id=intake.id, visit_id=visit.id, patient_id=patient.id, staff_id=current_user.id)
    reception_engine.advance(intake, "REGISTERED")
    reception_engine.announce_stage(intake)
    audit("FASTTRACK_FOLDER_OPENED", "patient", patient.id, {"intake": intake.ref, "number": patient.hospital_number, "fast_track": True})
    db.session.commit()
    flash(f"⭐ Fast Track folder {patient.hospital_number} opened for {patient.full_name} — sent to Triage executive lane.", "success")
    return redirect(url_for("fasttrack.desk"))


@bp.post("/fasttrack/ticket/<int:tid>/to-reception")
@require_role(*DESK)
def ticket_to_reception(tid: int):
    """Convert fast-track queue ticket to reception intake — appears at Reception + Fast Track Desk immediately with gold colour."""
    from .. import announce
    from ..models import ReceptionIntake, QueueTicket

    t = db.session.get(QueueTicket, tid)
    if not t or t.org_id != current_user.org_id:
        abort(404)
    if not t.is_fast_track:
        flash("That ticket is not Fast Track.", "error")
        return redirect(url_for("fasttrack.desk"))
    if t.status not in ("WAITING", "CALLED"):
        flash("Ticket no longer waiting.", "error")
        return redirect(url_for("fasttrack.desk"))

    parts = (t.patient_name or "").strip().split()
    surname = parts[-1] if parts else "—"
    first = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "Patient")

    intake = ReceptionIntake(
        org_id=t.org_id,
        ref=reception_engine.next_ref(t.org_id),
        surname=surname[:80],
        first_name=first[:80],
        phone=t.phone,
        stage="RECEPTION",
        created_by=current_user.id,
        is_fast_track=True,
        fast_track_reason=t.fast_track_reason or "PREMIUM",
    )
    db.session.add(intake)
    db.session.flush()
    t.intake_id = intake.id
    t.status = "DONE"
    t.served_at = now_naive()
    try:
        tracking_engine.safely(tracking_engine.enter, t.org_id, "RECEPTION", intake_id=intake.id, staff_id=current_user.id)
        spoken = announce.speech_name(t.patient_name or "patient")
        announce.to_station(t.org_id, "reception_arrival", patient=spoken, detail=f"Fast Track {t.code} — executive")
    except Exception:
        pass
    audit("FASTTRACK_QUEUE_TO_RECEPTION", "queue_ticket", t.id, {"code": t.code, "intake_ref": intake.ref, "fast_track": True})
    db.session.commit()
    flash(f"⭐ {t.patient_name} ({t.code}) Fast Track sent to Reception as {intake.ref} — gold lane, seen immediately.", "success")
    return redirect(url_for("fasttrack.desk"))
