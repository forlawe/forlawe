"""Reception desk — the front door of the patient flow.

The receptionist takes the details ONCE, finds out what help the person needs,
records their insurance, then walks them: Billing -> Paying Point -> HIMS ->
Triage. Every hand-off is announced out loud by the browser, free of charge.
"""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import hims, reception, tracking
from ..audit import audit
from ..models import (ASSISTANCE_NEEDS, INTAKE_STAGES, MARITAL_STATUSES,
                      NIGERIAN_STATES, PATIENT_LANGS, PAYER_LABELS,
                      PAYER_TYPES, Patient, ReceptionIntake, RELIGIONS,
                      SEXES, db, now_naive)
from ..navigation import require_permission
from ..security import require_role

bp = Blueprint("reception", __name__, url_prefix="/reception")

# Who works the front of house. Billing and the paying point are staffed by the
# same front-desk roles in this hospital, so they share the screen and each
# action is audit-logged with the name of whoever pressed it.
DESK = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
VIEWERS = DESK + ("MD_CEO", "DMD", "DCST", "APEX_NURSE")

NOK_RELATIONSHIPS = ("Husband", "Wife", "Father", "Mother", "Son", "Daughter",
                     "Brother", "Sister", "Uncle", "Aunt", "Cousin", "Friend",
                     "Neighbour", "Guardian", "Employer", "Other")


def _form_context(**extra):
    ctx = dict(sexes=SEXES, payers=PAYER_TYPES, langs=PATIENT_LANGS,
               assistance_needs=ASSISTANCE_NEEDS, relationships=NOK_RELATIONSHIPS,
               marital_statuses=MARITAL_STATUSES, religions=RELIGIONS,
               states=NIGERIAN_STATES)
    ctx.update(extra)
    return ctx


# ================================================================ the desk
@bp.get("/")
@require_role(*VIEWERS)
@require_permission("reception")
def desk():
    """Who is waiting, and where they are in the walk.

    OVERHAUL 2026-08-21: Reception now shows ONLY RECEPTION stage as primary
    actionable queue. Previously it showed all stages (RECEPTION,BILLING,PAYMENT,PAID)
    in one long list, which hid the fact that Billing/Paypoint/HIMS are separate
    desks with their own screens. Staff sent to billing and then thought patient
    vanished because they looked at Reception only. Now:

    * Reception desk: only RECEPTION stage (new arrivals) — clear ownership
    * Billing desk: BILLING stage
    * Paypoint: PAYMENT stage
    * HIMS desk: PAID stage (most appropriate to open folder)

    Counts still shown for awareness, with links to each desk.
    """
    org_id = current_user.org_id
    # Primary queue: only at Reception
    at_reception = reception.waiting(org_id, stages=("RECEPTION",))
    # For counts and awareness, get all
    all_waiting = reception.waiting(org_id)
    counts = reception.counts_by_stage(org_id)
    # Also fetch queues for other desks for inline summary (optional)
    billing_q = [i for i in all_waiting if i.stage == "BILLING"]
    payment_q = [i for i in all_waiting if i.stage == "PAYMENT"]
    paid_q = [i for i in all_waiting if i.stage == "PAID"]

    return render_template(
        "reception/desk.html",
        waiting=at_reception,
        all_waiting=all_waiting,
        billing_q=billing_q,
        payment_q=payment_q,
        paid_q=paid_q,
        counts=counts,
        registered_today=reception.today_registered(org_id),
        stages=INTAKE_STAGES,
        payer_labels=PAYER_LABELS,
    )


# ================================================================ new patient
@bp.get("/new")
@require_role(*DESK)
@require_permission("reception")
def new_form():
    return render_template("reception/new.html", form={}, errors=[],
                           **_form_context())


@bp.post("/new")
@require_role(*DESK)
@require_permission("reception")
def new_save():
    values, errors = reception.clean_form(request.form)
    if errors:
        return render_template("reception/new.html", form=request.form,
                               errors=errors, **_form_context()), 400

    intake = reception.create_intake(current_user.org_id, values, current_user.id)
    tracking.safely(tracking.enter, current_user.org_id, "RECEPTION", intake_id=intake.id,
                   staff_id=current_user.id)
    reception.announce_arrival(intake)
    # v2: personal TV session for this intake — premium tracker like Domino's
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(current_user.org_id, intake=intake)
        personal_tv.update_session_from_intake(sess)
    except Exception:
        pass
    audit("RECEPTION_INTAKE_CREATED", "reception_intake", intake.id,
          {"ref": intake.ref, "name": intake.full_name})
    db.session.commit()
    flash(f"{intake.full_name} taken in ({intake.ref}). "
          f"Now send them to Billing. Personal TV: /t/{sess.access_key if 'sess' in locals() and sess else intake.ref}", "success")
    return redirect(url_for("reception.desk"))


# ================================================================ the walk
def _get(intake_id: int) -> ReceptionIntake:
    row = db.session.get(ReceptionIntake, intake_id)
    if row is None or row.org_id != current_user.org_id:
        from flask import abort
        abort(404)
    return row


@bp.post("/<int:intake_id>/to-billing")
@require_role(*DESK)
@require_permission("reception")
def to_billing(intake_id: int):
    intake = _get(intake_id)
    reception.advance(intake, "BILLING", ref=(request.form.get("bill_ref") or ""))
    tracking.safely(tracking.enter, intake.org_id, "BILLING", intake_id=intake.id,
                   staff_id=current_user.id)
    reception.announce_stage(intake)
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(intake.org_id, intake=intake)
        personal_tv.update_session_from_intake(sess)
        personal_tv.notify_patient_personal(sess, title="Moved to Billing", body=f"{intake.full_name} — now at Billing Unit")
    except Exception:
        pass
    audit("RECEPTION_SENT_TO_BILLING", "reception_intake", intake.id,
          {"ref": intake.ref})
    db.session.commit()
    flash(f"{intake.full_name} sent to the Billing Unit.", "success")
    return redirect(url_for("reception.desk"))


@bp.post("/<int:intake_id>/to-payment")
@require_role(*DESK)
@require_permission("reception")
def to_payment(intake_id: int):
    intake = _get(intake_id)
    reception.advance(intake, "PAYMENT", ref=(request.form.get("bill_ref") or ""))
    tracking.safely(tracking.enter, intake.org_id, "PAYMENT", intake_id=intake.id,
                   staff_id=current_user.id)
    reception.announce_stage(intake)
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(intake.org_id, intake=intake)
        personal_tv.update_session_from_intake(sess)
        personal_tv.notify_patient_personal(sess, title="Moved to Pay Point", body=f"{intake.full_name} — now at Megalex Pay Point")
    except Exception:
        pass
    audit("RECEPTION_SENT_TO_PAYMENT", "reception_intake", intake.id,
          {"ref": intake.ref})
    db.session.commit()
    flash(f"{intake.full_name} sent to the Megalex Paying Point.", "success")
    return redirect(url_for("reception.desk"))


@bp.post("/<int:intake_id>/paid")
@require_role(*DESK)
@require_permission("reception")
def mark_paid(intake_id: int):
    intake = _get(intake_id)
    reception.advance(intake, "PAID", ref=(request.form.get("payment_ref") or ""))
    tracking.safely(tracking.enter, intake.org_id, "HIMS", intake_id=intake.id,
                   staff_id=current_user.id)
    reception.announce_stage(intake)
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(intake.org_id, intake=intake)
        personal_tv.update_session_from_intake(sess)
        personal_tv.notify_patient_personal(sess, title="Payment Done", body=f"{intake.full_name} — payment recorded, going to HIMS")
    except Exception:
        pass
    audit("RECEPTION_PAYMENT_RECORDED", "reception_intake", intake.id,
          {"ref": intake.ref, "receipt": intake.payment_ref})
    db.session.commit()
    flash(f"Payment recorded for {intake.full_name}. HIMS can now open the folder.",
          "success")
    return redirect(url_for("reception.desk"))


@bp.post("/<int:intake_id>/cancel")
@require_role(*DESK)
@require_permission("reception")
def cancel(intake_id: int):
    intake = _get(intake_id)
    intake.stage = "CANCELLED"
    tracking.safely(tracking.close_journey, intake.org_id, intake_id=intake.id)
    audit("RECEPTION_INTAKE_CANCELLED", "reception_intake", intake.id,
          {"ref": intake.ref})
    db.session.commit()
    flash(f"{intake.full_name} marked as left without completing.", "success")
    return redirect(url_for("reception.desk"))


# ================================================================ hand to HIMS
@bp.post("/<int:intake_id>/open-folder")
@require_role(*DESK)
@require_permission("reception")
def open_folder(intake_id: int):
    """HIMS turns a PAID intake into a real patient folder.

    The details were captured at Reception, so nothing is re-typed and the
    patient is not asked the same questions twice. Folder creation itself is
    delegated to `hims` so there is exactly one definition of a valid folder.
    """
    intake = _get(intake_id)
    if intake.stage != "PAID":
        flash("That patient has not paid yet. Payment is recorded before the "
              "folder is opened.", "error")
        return redirect(url_for("reception.desk"))
    if intake.patient_id:
        flash("A folder has already been opened for that patient.", "error")
        return redirect(url_for("hims.folder", pid=intake.patient_id))

    from ..services import current_org
    org = current_org()
    if org is None:
        from flask import abort
        abort(503)

    # Run the Reception details through HIMS's own validator, so a folder made
    # this way is held to exactly the same standard as one typed at the HIMS
    # desk. If Reception ever collects something HIMS rejects, we say so
    # plainly instead of writing a half-valid folder.
    values, errors = hims.validate(reception.folder_values(intake),
                                   org_id=current_user.org_id)
    if errors:
        flash("The folder could not be opened: " + " ".join(errors), "error")
        return redirect(url_for("reception.desk"))

    # RETURNING PATIENT? REUSE THE FOLDER, NEVER OPEN A SECOND ONE.
    #
    # A folder is opened ONCE and found again on every later visit — that is
    # the whole point of a hospital number. Reception used to create a new
    # Patient every time, so a returning patient got a second folder, and the
    # visit then collided with the one already open against their real folder
    # ("already has an open visit today"). The patient was left stranded at
    # Reception and never reached Triage. Reported from the live site.
    existing = hims.possible_duplicates(
        current_user.org_id, values["surname"], values["first_name"],
        values.get("phone"))
    patient = existing[0] if existing else None

    if patient is not None:
        # Keep the folder; refresh only what Reception legitimately re-asks.
        for field in ("phone", "address", "occupation", "payer_type",
                      "payer_number", "payer_name", "preferred_lang",
                      "assistance", "care_note", "nok_name", "nok_phone",
                      "nok_relationship"):
            new_value = values.get(field)
            if new_value:
                setattr(patient, field, new_value)
        db.session.flush()
    else:
        # v2 fix: values contains consent_at from hims.validate, so don't duplicate
        clean_vals = dict(values)
        clean_vals.pop("consent_at", None)
        clean_vals.pop("created_by", None)
        clean_vals.pop("branch_id", None)
        patient = Patient(org_id=current_user.org_id,
                          hospital_number=hims.next_hospital_number(org),
                          created_by=current_user.id, consent_at=now_naive(),
                          branch_id=getattr(current_user, "branch_id", None)
                          or getattr(intake, "branch_id", None),
                          **clean_vals)
        db.session.add(patient)
        try:
            db.session.flush()
        except Exception:                                          # noqa: BLE001
            # Two clerks opening a folder in the same instant: next number.
            db.session.rollback()
            patient = Patient(org_id=current_user.org_id,
                              hospital_number=hims.next_hospital_number(org),
                              created_by=current_user.id,
                              consent_at=now_naive(),
                              branch_id=getattr(current_user, "branch_id", None)
                              or getattr(intake, "branch_id", None),
                              **clean_vals)
            db.session.add(patient)
            db.session.flush()

    # If this patient already has an attendance open today (started at the HIMS
    # desk, or a half-finished Reception walk), REUSE it. Opening a second one
    # is what stranded the patient: the visit collided and Triage never saw
    # them. One person in the building = one open visit.
    visit = next((v for v in patient.visits
                  if v.status not in ("CLOSED", "CANCELLED")
                  and v.started_at
                  and v.started_at.date() == now_naive().date()), None)
    reused = visit is not None
    if visit is None:
        visit = hims.open_visit(
            patient, user_id=current_user.id,
            visit_type="NEW" if not patient.last_visit_at else "FOLLOW_UP",
            is_fast_track=bool(intake.is_fast_track),
            fast_track_reason=intake.fast_track_reason)
    else:
        # If intake is fast-track but existing visit wasn't, upgrade it
        if intake.is_fast_track and not visit.is_fast_track:
            visit.is_fast_track = True
            visit.fast_track_reason = intake.fast_track_reason
    # Flush so the visit HAS an id. Without this, tracking linked the Reception
    # half of the journey to visit_id=None, the HIMS segment was never closed,
    # and the patient showed as waiting at HIMS forever on the live board.
    db.session.flush()
    intake.patient_id = patient.id
    intake.visit_id = visit.id
    # Reception's segments predate the folder — join them to the visit so the
    # whole journey can be measured door to door, not just the back half.
    tracking.safely(tracking.attach_visit, current_user.org_id, intake.id, visit.id, patient.id)
    tracking.safely(tracking.enter, current_user.org_id, "TRIAGE", intake_id=intake.id,
                   visit_id=visit.id, patient_id=patient.id,
                   staff_id=current_user.id)
    reception.advance(intake, "REGISTERED")
    reception.announce_stage(intake)
    # v2 personal TV — now linked to visit
    try:
        from .. import personal_tv
        sess = personal_tv.ensure_personal_session(current_user.org_id, intake=intake, visit=visit)
        personal_tv.update_session_from_intake(sess)
        personal_tv.update_session_from_visit(sess)
        personal_tv.notify_patient_personal(sess, title="Folder Opened", body=f"{patient.full_name} — folder {patient.hospital_number}, going to Triage")
    except Exception:
        pass
    audit("PATIENT_FOLDER_OPENED", "patient", patient.id,
          {"intake": intake.ref, "number": patient.hospital_number,
           "name": patient.full_name, "via": "reception"})
    db.session.commit()
    if reused:
        flash(f"{patient.full_name} already had a visit open today "
              f"({visit.visit_no}) — reusing it. Folder "
              f"{patient.hospital_number}. Sent to Triage.", "success")
    elif existing:
        flash(f"Existing folder {patient.hospital_number} found for "
              f"{patient.full_name} — no second folder created. "
              f"Sent to Triage.", "success")
    else:
        flash(f"Folder {patient.hospital_number} opened for "
              f"{patient.full_name}. Sent to Triage.", "success")
    return redirect(url_for("hims.folder", pid=patient.id))
