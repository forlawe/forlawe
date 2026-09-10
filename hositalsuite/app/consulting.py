"""Stages C and D — the consulting room, and where the patient goes next.

STAGE C — THE CALL ROOM QUEUE
    "The doctors on duty and also ready to work by clicking to consult would
     see patients assigned to them from TRIAGE (the Call Room Queue)"

The doctor sees their own queue, calls the next patient in (which announces
them by name), and marks the consultation finished.

STAGE D — ONWARD ROUTING
    "The Doctor after attending to the patient would now push the patient to
     one, two or three out of the following
     (LAHSMA/Billing/Megalek/Laboratory/Pharmacy/Emergency)"

One, two or three — so destinations are rows, not a single column. Each is
completed independently by the desk that receives the patient, and the visit
closes only when every destination is done.

STILL NOT AN EMR
----------------
This module records WHERE a patient was sent and WHETHER they arrived. It never
records what a test was for, what was prescribed, or any clinical reason.
"Send to Pharmacy" is a direction to a desk, not a prescription. A guard test
fails the build if a clinical column ever appears.
"""
from __future__ import annotations

from datetime import datetime

from . import announce
from .clinical_tier import clinical_order, emergency_tier_expr
from .models import (ONWARD_CODES, ONWARD_LABELS, Patient, PatientVisit,
                     VisitOnward, db, now_naive)
from .servicepoints import active_destinations, destinations_for_clinic, ensure_defaults as sp_ensure


def _valid_dest_codes(org_id: int) -> set[str]:
    """Destination codes from DB if present, else fallback to constants."""
    try:
        dests = active_destinations(org_id)
        if dests:
            return {d.code.upper() for d in dests}
    except Exception:
        pass
    return set(ONWARD_CODES)


# ------------------------------------------------------------------ the queue
def doctor_queue(org_id: int, doctor_id: int) -> list[PatientVisit]:
    """This doctor's call room queue today — longest waiting first.

    TWO KINDS OF PATIENT APPEAR HERE, AND MISSING THE SECOND WAS A REAL BUG
    ----------------------------------------------------------------------
      1. Patients Triage assigned to this doctor BY NAME.
      2. Patients Triage placed into this doctor's CLINIC without naming a
         doctor — "— waiting for a doctor —".

    Triage is allowed to place a patient into a clinic with nobody named (that
    is deliberate: it beats leaving them stuck in the reception backlog). But
    the queue originally matched only `doctor_id == me`, so those patients
    appeared on the Triage board as TRIAGED and then showed up in NOBODY's
    room. The founder hit this immediately on the live site: three patients
    placed, and an empty call room queue.

    A doctor who is ready in Accident & Emergency must see the people waiting
    in Accident & Emergency. Anything else strands them.
    """
    from sqlalchemy import and_, func, or_

    session = _open_session_for(org_id, doctor_id)
    conditions = [PatientVisit.doctor_id == doctor_id]
    if session is not None:
        # Unassigned patients waiting in the clinic THIS doctor has open.
        # Compared case-insensitively and ignoring stray spaces: a clinic saved
        # as "Emergency" or " EMERGENCY " must still match, because a patient
        # is not going to be seen by a string comparison.
        conditions.append(and_(
            PatientVisit.doctor_id.is_(None),
            func.upper(func.trim(PatientVisit.clinic)) ==
            (session.clinic or "").strip().upper()))

    # NO DATE WINDOW.
    #
    # This used to be limited to visits started today. It looked sensible and
    # it was wrong twice over: a patient placed at 23:50 vanished from the
    # doctor's room at midnight while still sitting in the waiting area, and
    # any clock or timezone difference between the app and the database could
    # hide today's patients entirely. An OPEN visit is open until somebody
    # closes it, whatever the calendar says. Stale rows are handled properly by
    # the tracking cleanup job, not by hiding real patients from a doctor.
    # F-012 clinical tier rule: EMERGENCY clinic first, then Fast Track
    # WITHIN the tier, then longest wait. Fast Track can never jump an
    # emergency patient — see app/clinical_tier.py.
    return (db.session.query(PatientVisit)
            .filter(PatientVisit.org_id == org_id,
                    PatientVisit.status.in_(("TRIAGED", "IN_CONSULTATION")),
                    or_(*conditions))
            .order_by(*clinical_order(
                emergency_tier_expr(PatientVisit.clinic),
                PatientVisit.is_fast_track,
                PatientVisit.triaged_at.asc().nullsfirst()))
            .all())


def _open_session_for(org_id: int, doctor_id: int):
    """The room this doctor currently has open, if any."""
    from .models import DoctorSession
    return (db.session.query(DoctorSession)
            .filter_by(org_id=org_id, doctor_id=doctor_id,
                       duty_date=now_naive().date(), ended_at=None)
            .first())


def in_consultation(org_id: int, doctor_id: int) -> PatientVisit | None:
    """The patient currently in the room with this doctor, if any."""
    # Same rule as doctor_queue: no date window. A consultation that began
    # before midnight is still happening at 00:05.
    return (db.session.query(PatientVisit)
            .filter(PatientVisit.org_id == org_id,
                    PatientVisit.doctor_id == doctor_id,
                    PatientVisit.status == "IN_CONSULTATION")
            .first())


def wait_minutes(visit: PatientVisit, now: datetime | None = None) -> int:
    """How long since Triage placed them — the wait that matters to a doctor."""
    now = now or now_naive()
    since = visit.triaged_at or visit.started_at or now
    return max(0, int((now - since).total_seconds() // 60))


# ------------------------------------------------------------------ Stage C
def call_in(visit: PatientVisit, doctor_id: int) -> str:
    """Doctor calls the next patient into the room. Returns "" or an error.

    Only ONE patient may be in the room at a time. If the doctor forgot to
    finish the last one, say so plainly rather than quietly having two people
    'in consultation' with the same doctor.
    """
    # A patient may be unassigned ("— waiting for a doctor —") and simply
    # waiting in this doctor's clinic. Calling them in CLAIMS them, which is
    # exactly how a real clinic works: whoever is free takes the next patient.
    session = _open_session_for(visit.org_id, doctor_id)
    claimable = (visit.doctor_id is None and session is not None
                 and (visit.clinic or "").strip().upper()
                 == (session.clinic or "").strip().upper())
    if visit.doctor_id != doctor_id and not claimable:
        return "That patient is not on your call room queue."
    if visit.status == "IN_CONSULTATION":
        return "That patient is already in your room."
    if visit.status != "TRIAGED":
        return "That patient is not waiting to be seen."

    busy = in_consultation(visit.org_id, doctor_id)
    if busy is not None and busy.id != visit.id:
        return ("You already have a patient in your room. Finish that "
                "consultation first.")

    if claimable:
        # Two doctors in the same clinic could tap the same patient at the same
        # moment. Claim only if still free; otherwise say so plainly rather
        # than quietly stealing a colleague's patient.
        rows = (db.session.query(PatientVisit)
                .filter(PatientVisit.id == visit.id,
                        PatientVisit.doctor_id.is_(None))
                .update({"doctor_id": doctor_id,
                         "consulting_room": session.consulting_room},
                        synchronize_session=False))
        if not rows:
            db.session.refresh(visit)
            return ("Another doctor has just taken that patient. "
                    "Please call the next one.")
        db.session.refresh(visit)

    visit.status = "IN_CONSULTATION"
    visit.seen_at = now_naive()
    return ""


def finish(visit: PatientVisit, doctor_id: int, destinations: list[str],
           note: str = "") -> tuple[str, list[VisitOnward]]:
    """Doctor finishes and pushes the patient onward. Returns (error, steps).

    With no destinations the visit is simply CLOSED — plenty of patients are
    seen and sent home, and forcing a destination would make the doctor invent
    one. With destinations the visit goes ONWARD and stays open until each is
    completed.
    """
    if visit.doctor_id != doctor_id:
        return "That patient is not on your call room queue.", []
    if visit.status not in ("IN_CONSULTATION", "TRIAGED"):
        return "That consultation has already been finished.", []

    valid_codes = _valid_dest_codes(visit.org_id)
    raw = [str(d).strip().upper() for d in (destinations or []) if str(d).strip()]
    # dedupe preserve order, keep only valid codes
    picked = []
    seen = set()
    for code in raw:
        if code not in seen and code in valid_codes:
            seen.add(code)
            picked.append(code)
    now = now_naive()
    steps: list[VisitOnward] = []
    for dest in picked:
        step = VisitOnward(org_id=visit.org_id, visit_id=visit.id,
                           destination=dest, status="PENDING",
                           note=(note or "").strip()[:200] or None,
                           sent_at=now, sent_by=doctor_id)
        db.session.add(step)
        steps.append(step)

    if picked:
        visit.status = "ONWARD"
    else:
        visit.status = "CLOSED"
        visit.closed_at = now
    if visit.seen_at is None:
        visit.seen_at = now
    db.session.flush()
    return "", steps


# ------------------------------------------------------------------ Stage D
def pending_for(org_id: int, destination: str) -> list[VisitOnward]:
    """Everyone the doctors have sent to one desk.

    F-012 clinical tier rule: an EMERGENCY routing outranks Fast Track; Fast
    Track outranks time within the same tier. See app/clinical_tier.py."""
    return (db.session.query(VisitOnward)
            .join(PatientVisit, VisitOnward.visit_id == PatientVisit.id)
            .filter(VisitOnward.org_id == org_id,
                    VisitOnward.destination == destination,
                    VisitOnward.status == "PENDING")
            .order_by(*clinical_order(
                emergency_tier_expr(VisitOnward.destination),
                PatientVisit.is_fast_track,
                VisitOnward.sent_at.asc()))
            .limit(200).all())


def pending_counts(org_id: int) -> dict[str, int]:
    rows = (db.session.query(VisitOnward.destination,
                             db.func.count(VisitOnward.id))
            .filter(VisitOnward.org_id == org_id,
                    VisitOnward.status == "PENDING")
            .group_by(VisitOnward.destination).all())
    return {dest: n for dest, n in rows}


def complete_step(step: VisitOnward, user_id: int | None = None) -> bool:
    """A desk finishes with the patient. Closes the visit if it was the last.

    Returns True when this completion closed the whole visit.
    """
    if step.status == "DONE":
        return False
    step.status = "DONE"
    step.completed_at = now_naive()
    step.completed_by = user_id

    visit = db.session.get(PatientVisit, step.visit_id)
    if visit is None:
        return False
    outstanding = [s for s in visit.onward_steps if s.status != "DONE"]
    if not outstanding and visit.status == "ONWARD":
        visit.status = "CLOSED"
        visit.closed_at = now_naive()
        return True
    return False


def outstanding_for_visit(visit: PatientVisit) -> list[VisitOnward]:
    return [s for s in visit.onward_steps if s.status != "DONE"]


# ------------------------------------------------------------------ voice
def announce_called_in(visit: PatientVisit, patient: Patient) -> None:
    """Call the patient into the room, by name. This is the moment they wait for."""
    announce.to_station(
        visit.org_id, "consult_call_in",
        patient=announce.speech_name(patient.spoken_name),
        room=visit.consulting_room or "the consulting room")


def announce_onward(visit: PatientVisit, patient: Patient,
                    steps: list[VisitOnward]) -> None:
    """Tell the patient where to go next, and tell each desk to expect them."""
    spoken = announce.speech_name(patient.spoken_name)
    if not steps:
        announce.to_station(visit.org_id, "visit_complete", patient=spoken)
        return

    # One sentence to the patient naming every place, so they hear it once and
    # in order rather than as three separate announcements they must piece
    # together while walking away from the door.
    places = [s.place for s in steps]
    if len(places) == 1:
        where = places[0]
    elif len(places) == 2:
        where = f"{places[0]}, then {places[1]}"
    else:
        where = ", then ".join(places)
    announce.to_station(visit.org_id, "go_onward", patient=spoken, place=where)

    for step in steps:
        if step.destination == "EMERGENCY":
            announce.to_station(visit.org_id, "emergency_arrival",
                                place="Accident and Emergency",
                                detail=f"{spoken} is being sent from the "
                                       f"consulting room now.")
        else:
            announce.to_station(visit.org_id, "desk_expecting",
                                patient=spoken, place=step.place)


def announce_desk_backlog(org_id: int, destination: str) -> None:
    """Tell a desk out loud when patients are stacking up waiting for it."""
    n = len(pending_for(org_id, destination))
    if n >= 3:
        announce.to_station(
            org_id, "queue_waiting", count=n,
            place=ONWARD_LABELS.get(destination, destination).split(" — ")[0])
