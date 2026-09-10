"""Triage — Stage B of the patient flow.

WHAT TRIAGE DOES HERE (and what it must never do)
-------------------------------------------------
The founder's words:

    "Triage — Place patient to the OPD/SOPD/MOPD/EMERGENCY according to
     available doctors, patients needs, Patients Categories, Day of the week,
     Clinics of the day etc"
    "The TRIAGE Assign Patients on the QUEUE to doctors in the consulting
     room 1, 2, 3, 4, or Emergency"

So Triage is a PLACEMENT desk, not a clinical assessment. It decides WHERE a
patient goes and WHO sees them. It does not decide what is wrong with them.

    ✅ category, day of the week, clinic of the day, which doctors are free
    ❌ no symptom scoring, no vital signs, no temperature, no blood pressure,
       no diagnosis, no clinical notes

"Blood sugar test" is a STEP the patient is sent for and a billing line. This
module records only that it was done — never a reading. A test guards that.

DOCTOR AVAILABILITY
-------------------
A doctor is offered by Triage only when BOTH are true:
  * they are on the roster for today, and
  * they have clicked "I am ready to consult" and opened a session.
The roster says who should be in the building. The session says who is
actually sitting in a room. Sending a patient to an empty room because the
roster said so is exactly the failure this prevents.
"""
from __future__ import annotations

from datetime import date, datetime

from . import announce, rosterdata
from .clinical_tier import clinical_order, emergency_tier_expr
from .models import (
    CLINIC_CODES,
    CLINIC_LABELS,
    CONSULTING_ROOMS,
    DoctorSession,
    Patient,
    PatientVisit,
    User,
    db,
    now_naive,
)
from .servicepoints import ensure_defaults as sp_ensure, active_clinics, active_rooms


def _valid_clinic_codes(org_id: int) -> set[str]:
    """Clinic codes from DB if present, else fallback to hard-coded constants."""
    try:
        clinics = active_clinics(org_id)
        if clinics:
            return {c.code.upper() for c in clinics}
    except Exception:
        pass
    return set(CLINIC_CODES)


def _valid_room_names(org_id: int) -> set[str]:
    try:
        rooms = active_rooms(org_id)
        if rooms:
            # Allow both code and name to match, case-insensitive
            s = set()
            for r in rooms:
                s.add(r.code.upper())
                s.add(r.name.upper())
                s.add(r.name.strip().upper())
            return s
    except Exception:
        pass
    return {r.upper() for r in CONSULTING_ROOMS}

# How long a patient may sit unplaced before the desk is told out loud.
LONG_WAIT_MINUTES = 30

# Which clinic a patient category is normally placed in. Triage can always
# override — this is a sensible default, not a rule that argues with the nurse.
CATEGORY_CLINIC = {
    "CHILD":     "OPD",
    "ANTENATAL": "OPD",
    "ELDERLY":   "MOPD",
    "CHRONIC":   "MOPD",
    "GENERAL":   "OPD",
}


# ------------------------------------------------------------------ the queue
def waiting(org_id: int) -> list[PatientVisit]:
    """Patients registered today and not yet placed — triage bench order.

    F-012 clinical tier rule: an EMERGENCY-clinic walk-in is triaged before
    any Fast Track patient, however gold their badge; Fast Track then ranks
    within the tier, then longest wait. See app/clinical_tier.py."""
    start = datetime.combine(now_naive().date(), datetime.min.time())
    return (db.session.query(PatientVisit)
            .filter(PatientVisit.org_id == org_id,
                    PatientVisit.status == "REGISTERED",
                    PatientVisit.started_at >= start)
            .order_by(*clinical_order(
                emergency_tier_expr(PatientVisit.clinic),
                PatientVisit.is_fast_track,
                PatientVisit.started_at.asc()))
            .limit(200).all())


def placed_today(org_id: int) -> list[PatientVisit]:
    start = datetime.combine(now_naive().date(), datetime.min.time())
    return (db.session.query(PatientVisit)
            .filter(PatientVisit.org_id == org_id,
                    PatientVisit.status.in_(("TRIAGED", "IN_CONSULTATION")),
                    PatientVisit.started_at >= start)
            .order_by(PatientVisit.triaged_at.desc().nullslast())
            .limit(200).all())


def wait_minutes(visit: PatientVisit, now: datetime | None = None) -> int:
    """How long this patient has been waiting, in whole minutes."""
    now = now or now_naive()
    started = visit.started_at or now
    return max(0, int((now - started).total_seconds() // 60))


def long_waiters(org_id: int, threshold: int = LONG_WAIT_MINUTES) -> list[PatientVisit]:
    return [v for v in waiting(org_id) if wait_minutes(v) >= threshold]


def stats(org_id: int) -> dict:
    q = waiting(org_id)
    waits = [wait_minutes(v) for v in q]
    return {
        "waiting": len(q),
        "placed": len(placed_today(org_id)),
        "longest_wait": max(waits) if waits else 0,
        "average_wait": int(sum(waits) / len(waits)) if waits else 0,
    }


# ------------------------------------------------------------------ doctors
def ready_doctors(org_id: int, day: date | None = None) -> list[DoctorSession]:
    """Doctors who are rostered AND have said they are ready, right now."""
    day = day or now_naive().date()
    sessions = (db.session.query(DoctorSession)
                .filter(DoctorSession.org_id == org_id,
                        DoctorSession.duty_date == day,
                        DoctorSession.ready.is_(True),
                        DoctorSession.ended_at.is_(None))
                .all())
    rostered = _rostered_user_ids(org_id, day)
    out = [s for s in sessions if s.doctor_id in rostered]
    out.sort(key=lambda s: (s.clinic, s.consulting_room))
    return out


def _rostered_user_ids(org_id: int, day: date) -> set[int]:
    """Everyone on the roster to WORK today (leave rows excluded)."""
    from .models import RosterEntry
    rows = (db.session.query(RosterEntry.user_id)
            .filter(RosterEntry.org_id == org_id,
                    RosterEntry.duty_date == day,
                    RosterEntry.kind == "DUTY")
            .all())
    return {r[0] for r in rows}


def is_available(org_id: int, doctor_id: int, day: date | None = None) -> bool:
    """BOTH rostered AND ready. Either one alone is not enough."""
    day = day or now_naive().date()
    return any(s.doctor_id == doctor_id for s in ready_doctors(org_id, day))


def open_session(org_id: int, doctor: User, clinic: str, room: str,
                 day: date | None = None) -> tuple[DoctorSession | None, str]:
    """A doctor clicks 'ready to consult'. Returns (session, error message)."""
    day = day or now_naive().date()
    # Ensure defaults seeded so new clinics/rooms exist
    try:
        sp_ensure(org_id)
    except Exception:
        pass

    clinic_upper = (clinic or "").strip().upper()
    room_upper = (room or "").strip().upper()

    valid_clinics = _valid_clinic_codes(org_id)
    if clinic_upper not in valid_clinics:
        return None, "Please choose a valid clinic."

    valid_rooms = _valid_room_names(org_id)
    if room_upper not in valid_rooms and room_upper not in {r.upper() for r in CONSULTING_ROOMS}:
        # Allow any room code that exists in DB, or fallback to old list
        # If not in either, still check if room name matches DB case-insensitively
        # To be safe, allow any non-empty room if DB has no rooms (first boot)
        if valid_rooms and room_upper not in valid_rooms:
            return None, "Please choose a valid consulting room."

    if doctor.id not in _rostered_user_ids(org_id, day):
        return None, (f"{doctor.name} is not on the roster for today, so Triage "
                      f"cannot send patients to them. Add them to today's roster first.")

    taken = [s for s in ready_doctors(org_id, day)
             if s.consulting_room == room and s.doctor_id != doctor.id]
    if taken:
        return None, (f"{room} is already in use by {taken[0].doctor.name}. "
                      f"Please choose another room.")

    existing = (db.session.query(DoctorSession)
                .filter_by(org_id=org_id, doctor_id=doctor.id, duty_date=day,
                           ended_at=None).first())
    if existing:
        existing.clinic = clinic
        existing.consulting_room = room
        existing.ready = True
        return existing, ""

    row = DoctorSession(org_id=org_id, doctor_id=doctor.id, duty_date=day,
                        clinic=clinic, consulting_room=room, ready=True)
    db.session.add(row)
    db.session.flush()
    return row, ""


def close_session(org_id: int, doctor_id: int, day: date | None = None) -> bool:
    """Doctor steps away. Triage stops offering the room immediately."""
    day = day or now_naive().date()
    row = (db.session.query(DoctorSession)
           .filter_by(org_id=org_id, doctor_id=doctor_id, duty_date=day,
                      ended_at=None).first())
    if row is None:
        return False
    row.ready = False
    row.ended_at = now_naive()
    return True


def doctor_load(org_id: int) -> dict[int, int]:
    """How many patients are already queued for each doctor today."""
    start = datetime.combine(now_naive().date(), datetime.min.time())
    rows = (db.session.query(PatientVisit.doctor_id,
                             db.func.count(PatientVisit.id))
            .filter(PatientVisit.org_id == org_id,
                    PatientVisit.started_at >= start,
                    PatientVisit.status.in_(("TRIAGED", "IN_CONSULTATION")),
                    PatientVisit.doctor_id.isnot(None))
            .group_by(PatientVisit.doctor_id).all())
    return {doc_id: n for doc_id, n in rows}


# ------------------------------------------------------------------ placement
def suggest_clinic(patient: Patient) -> str:
    """A sensible default clinic from the patient's category. Never a diagnosis."""
    return CATEGORY_CLINIC.get(patient.category or "GENERAL", "OPD")


def suggest_doctor(org_id: int, clinic: str) -> DoctorSession | None:
    """The free doctor in that clinic with the shortest queue — fair, not first.

    Compared case-insensitively and ignoring stray spaces, for the same reason
    the consulting room does: a patient must not be left unassigned because two
    strings differed by a space.
    """
    want = (clinic or "").strip().upper()
    candidates = [s for s in ready_doctors(org_id)
                  if (s.clinic or "").strip().upper() == want]
    if not candidates:
        return None
    load = doctor_load(org_id)
    candidates.sort(key=lambda s: (load.get(s.doctor_id, 0), s.consulting_room))
    return candidates[0]


def suggest_clinic_with_cover(org_id: int, patient) -> str:
    """The clinic to offer Triage: the right one, unless nobody is there.

    WHY THIS EXISTS
    ---------------
    suggest_clinic() answers "where does this KIND of patient normally go?" —
    a general adult goes to OPD. But if the only doctor on duty is sitting in
    Accident & Emergency, offering OPD means the page pre-selects a clinic with
    nobody in it, the patient is placed with no doctor, and they wait for a
    room that will not open today.

    So: keep the clinically sensible default WHEN somebody is covering it, and
    otherwise offer the clinic that actually has a free doctor. Triage can
    always override — this only changes what the box says before anyone types.
    """
    preferred = suggest_clinic(patient)
    if suggest_doctor(org_id, preferred) is not None:
        return preferred
    open_clinics = [s.clinic for s in ready_doctors(org_id)]
    return open_clinics[0] if open_clinics else preferred


def place(visit: PatientVisit, *, clinic: str, session: DoctorSession | None,
          blood_sugar_done: bool = False, user_id: int | None = None) -> str:
    """Place a patient into a clinic and (usually) with a named doctor.

    Returns an error message, or "" on success. A patient may be placed into a
    clinic with no doctor yet — that is honest ("waiting for a doctor in MOPD")
    and better than refusing to move them out of the reception backlog.
    """
    clinic_upper = (clinic or "").strip().upper()
    valid_clinics = _valid_clinic_codes(visit.org_id)
    if clinic_upper not in valid_clinics:
        return "Please choose a valid clinic."
    if visit.status != "REGISTERED":
        return "That patient has already been placed."

    visit.clinic = clinic
    visit.status = "TRIAGED"
    visit.triaged_at = now_naive()
    if session is not None:
        if not is_available(visit.org_id, session.doctor_id):
            return ("That doctor is no longer ready to consult. "
                    "Please choose another.")
        visit.doctor_id = session.doctor_id
        visit.consulting_room = session.consulting_room
    if blood_sugar_done:
        # ONLY that it happened. Never a reading — this is not a medical record.
        note = "Blood sugar test done"
        visit.reason = (f"{visit.reason} · {note}" if visit.reason else note)[:300]
    return ""


# ------------------------------------------------------------------ voice
def announce_placement(visit: PatientVisit, patient: Patient,
                       session: DoctorSession | None) -> None:
    """Call the patient by name, and tell the doctor someone is coming."""
    spoken = announce.speech_name(patient.spoken_name)
    room = visit.consulting_room or CLINIC_LABELS.get(visit.clinic, visit.clinic)

    # To the waiting area: the patient hears where to go.
    announce.to_station(visit.org_id, "queue_assigned", patient=spoken, room=room)

    # To the doctor personally: someone is on their way to your room.
    if session is not None and session.doctor is not None:
        announce.to_user(visit.org_id, session.doctor, "consult_ready",
                         patient=spoken, room=room)


def announce_backlog(org_id: int) -> None:
    """Tell Triage out loud when the queue is building up."""
    n = len(waiting(org_id))
    if n >= 3:
        announce.to_station(org_id, "triage_backlog", count=n)


def announce_long_waits(org_id: int) -> int:
    """Nobody should be forgotten on a bench. Returns how many were called."""
    called = 0
    for visit in long_waiters(org_id):
        patient = db.session.get(Patient, visit.patient_id)
        if patient is None:
            continue
        announce.to_station(
            org_id, "patient_waiting_long",
            patient=announce.speech_name(patient.spoken_name),
            place="the triage bench",
            detail=f"{wait_minutes(visit)} minutes")
        called += 1
    return called


def announce_emergency(visit: PatientVisit, patient: Patient) -> None:
    """Emergency arrival: alarm everywhere, and LOG every failure.

    F-006: the per-role alert loop and the personal-TV push were wrapped in
    silent `except: pass`. Everywhere else in the codebase swallowing a
    secondary effect is deliberate resilience; HERE the swallowed effect IS
    the safety-critical action — a silent failure means the emergency team
    was never alarmed and nobody would ever know. Every failure is now
    logged at ERROR with the role/station it failed for; triage flow itself
    still never crashes (the alerts stay best-effort).
    """
    # Voice alarm to ALL — founder: emergency must alarm everywhere
    spoken = announce.speech_name(patient.spoken_name) if patient else "Emergency patient"
    detail = f"{spoken} needs immediate attention in Accident and Emergency."
    try:
        announce.to_station(visit.org_id, "emergency_arrival",
                            place="Accident and Emergency",
                            detail=detail)
    except Exception:                                    # noqa: BLE001
        _log_emergency_failure("station broadcast (ALL stations)", visit.org_id)

    # Alarm every management + clinical role
    for role in ("SUPER_ADMIN","MD_CEO","DMD","DCST","HEAD_ADMIN_HR","ADMIN_MANAGER","HOD","APEX_NURSE","DOCTOR","NURSE","RECEPTIONIST","TRIAGE_NURSE","HIMS_CLERK"):
        try:
            announce.to_role(visit.org_id, role, "emergency_arrival",
                             place="Accident and Emergency",
                             detail=detail, count=1, patient=spoken)
        except Exception:                                # noqa: BLE001
            _log_emergency_failure(f"role alert {role}", visit.org_id)
    try:
        from . import personal_tv
        sess = personal_tv.ensure_personal_session(visit.org_id, visit=visit)
        personal_tv.update_session_from_visit(sess)
        personal_tv.notify_patient_personal(sess, title="Emergency - A&E", body=f"{spoken} - go to Accident and Emergency now, you will be seen immediately", data={"priority": "EMERGENCY", "stage": "EMERGENCY"})
    except Exception:                                    # noqa: BLE001
        _log_emergency_failure("patient personal-TV emergency push", visit.org_id)


def _log_emergency_failure(what: str, org_id) -> None:
    """One loud, greppable line per failed emergency-alert channel."""
    from flask import current_app
    try:
        current_app.logger.error(
            "EMERGENCY ALERT FAILURE: could not %s for org %s — the "
            "emergency team may not have been alarmed. Check the announce/"
            "notification backends NOW.", what, org_id)
        current_app.logger.exception("emergency alert channel failure detail")
    except Exception:                                    # noqa: BLE001 — logging must never be the thing that crashes triage
        pass
