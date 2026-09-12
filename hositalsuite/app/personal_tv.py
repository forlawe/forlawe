"""
Personal Patient TV Engine — Individual tracker like Domino's, no login, cost saver
---------------------------------------------------------------------------------
Founder rule: No SMS for patients within hospital except serious complaints/emergency.
So we need personal TV to replace SMS.

What it does:
- For each QueueTicket / ReceptionIntake / PatientVisit, create PersonalTvSession with access_key secret
- That access_key is like boarding pass — patient scans QR at Main TV or ticket print
- Page /t/<access_key> shows live position, estimated wait, journey timeline, voice, push
- Works on any browser (Chrome, Firefox, Safari, Edge, Samsung, UC, Opera) + feature phone fallback
- Multi-hospital: per org_id
- Slow internet: payload <1KB, offline shell cached, low-data mode
- Loading time: minimal JS, server-rendered first paint, then live poll every 10s

Feature phone provision:
- If browser no JS or feature phone (KaiOS, etc): server-rendered page with meta refresh every 30s
- If no push support: use TV + voice announcement + USSD *xxx# to check status
- If truly future phone with no browser: Main TV + voice call-out + staff assistance
- Note provision in docs.

Premium UI: gold theme for fast track, timeline with checkmarks, big buttons, voice, vibrate.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .models import (
    QueueTicket,
    ReceptionIntake,
    PatientVisit,
    Patient,
    JourneySegment,
    db,
    now_naive,
)

def generate_access_key() -> str:
    """24-char secret, like boarding pass, not guessable."""
    return secrets.token_urlsafe(18)[:24]

def ensure_personal_session(org_id: int, ticket: QueueTicket | None = None,
                            intake: ReceptionIntake | None = None,
                            visit: PatientVisit | None = None,
                            patient: Patient | None = None,
                            appointment: Any = None) -> Any:
    """Ensure PersonalTvSession exists for this patient journey — idempotent."""
    from .models_v2 import PersonalTvSession

    # Find existing
    existing = None
    if ticket:
        try:
            existing = db.session.query(PersonalTvSession).filter_by(org_id=org_id, ticket_id=ticket.id).first()
        except Exception:
            existing = None
    if not existing and intake:
        try:
            existing = db.session.query(PersonalTvSession).filter_by(org_id=org_id, intake_id=intake.id).first()
        except Exception:
            existing = None
    if not existing and visit:
        try:
            existing = db.session.query(PersonalTvSession).filter_by(org_id=org_id, visit_id=visit.id).first()
        except Exception:
            existing = None
    # Appointment has no FK in PersonalTvSession, so we check by patient phone or create new
    if existing:
        return existing

    # Create new — reuse ticket/intake access_key if available so /t/<ticket_key> works
    access_key = None
    if ticket and getattr(ticket, 'access_key', None):
        access_key = ticket.access_key
        # Ensure not already used by another session
        if db.session.query(PersonalTvSession).filter_by(access_key=access_key).first():
            access_key = None
    if not access_key:
        access_key = generate_access_key()
        while db.session.query(PersonalTvSession).filter_by(access_key=access_key).first():
            access_key = generate_access_key()

    is_fast = False
    fast_reason = None
    pref_lang = "en"
    if ticket:
        is_fast = bool(getattr(ticket, 'is_fast_track', False))
        fast_reason = getattr(ticket, 'fast_track_reason', None)
    if intake:
        is_fast = is_fast or bool(getattr(intake, 'is_fast_track', False))
        fast_reason = fast_reason or getattr(intake, 'fast_track_reason', None)
        pref_lang = getattr(intake, 'preferred_lang', 'en') or 'en'
    if patient:
        pref_lang = getattr(patient, 'preferred_lang', 'en') or pref_lang
    if visit:
        is_fast = is_fast or bool(getattr(visit, 'is_fast_track', False))
        fast_reason = fast_reason or getattr(visit, 'fast_track_reason', None)
    if appointment:
        is_fast = is_fast or bool(getattr(appointment, 'is_fast_track', False))
        fast_reason = fast_reason or getattr(appointment, 'fast_track_reason', None)

    session = PersonalTvSession(
        org_id=org_id,
        access_key=access_key,
        ticket_id=ticket.id if ticket else None,
        intake_id=intake.id if intake else None,
        visit_id=visit.id if visit else None,
        patient_id=patient.id if patient else (ticket.patient_id if ticket and ticket.patient_id else None),
        current_stage="RECEPTION",
        position=0,
        estimated_wait=0,
        is_fast_track=is_fast,
        fast_track_reason=fast_reason,
        preferred_lang=pref_lang,
        is_inside_hospital=True,
        last_seen_at=now_naive()
    )
    db.session.add(session)
    db.session.flush()
    return session

def get_session_by_access_key(access_key: str) -> Optional[Any]:
    from .models_v2 import PersonalTvSession
    return db.session.query(PersonalTvSession).filter_by(access_key=access_key).first()

def update_session_from_ticket(session, ticket: QueueTicket):
    """Update position and stage from ticket status — hardened for None created_at."""
    from . import queue_estimator
    org_id = session.org_id
    today = now_naive().date()

    # Count waiting before this ticket — defensive for None created_at
    if ticket.status == "WAITING":
        try:
            if getattr(ticket, 'created_at', None):
                waiting = db.session.query(QueueTicket).filter(
                    QueueTicket.org_id == org_id,
                    QueueTicket.queue_date == today,
                    QueueTicket.status == "WAITING",
                    QueueTicket.created_at < ticket.created_at,
                    QueueTicket.department_id == ticket.department_id
                ).count()
            else:
                waiting = 0
        except Exception:
            waiting = 0
        session.position = waiting + 1
        session.current_stage = "RECEPTION" if not getattr(ticket, 'patient_id', None) else "TRIAGE"
        try:
            session.estimated_wait = queue_estimator.estimate_wait_minutes(org_id, "RECEPTION", position=waiting, is_fast_track=getattr(session, 'is_fast_track', False))
        except Exception:
            session.estimated_wait = 5
    elif ticket.status == "CALLED":
        session.position = 0
        session.current_stage = "CALLED"
        session.estimated_wait = 0
    elif ticket.status == "DONE":
        session.current_stage = "DONE"
        session.estimated_wait = 0
    try:
        session.updated_at = now_naive()
    except Exception:
        pass

def update_session_from_appointment(session, appointment: Any):
    """Update personal TV session from Appointment (USSD booking) — feature phone provision."""
    from . import queue_estimator
    org_id = session.org_id
    try:
        session.current_stage = "BOOKED"
        session.position = 0
        # Estimate wait based on appointment date — if today, use reception estimate, else 0
        today = now_naive().date()
        apt_date = getattr(appointment, 'appointment_date', None)
        if apt_date == today:
            session.estimated_wait = queue_estimator.estimate_wait_minutes(org_id, "RECEPTION", position=0, is_fast_track=getattr(session, 'is_fast_track', False))
        else:
            session.estimated_wait = 0
        session.updated_at = now_naive()
    except Exception:
        session.estimated_wait = 0
        try:
            session.updated_at = now_naive()
        except Exception:
            pass

def update_session_from_intake(session, intake: ReceptionIntake):
    from . import queue_estimator
    org_id = session.org_id
    stage = getattr(intake, 'stage', 'RECEPTION')
    session.current_stage = stage
    # Position based on intake queue — defensive for None created_at
    if stage == "RECEPTION":
        try:
            today_start = datetime.combine(now_naive().date(), datetime.min.time())
            if getattr(intake, 'created_at', None):
                waiting = db.session.query(ReceptionIntake).filter(
                    ReceptionIntake.org_id == org_id,
                    ReceptionIntake.stage == "RECEPTION",
                    ReceptionIntake.created_at < intake.created_at,
                    ReceptionIntake.created_at >= today_start
                ).count()
            else:
                waiting = 0
            session.position = waiting + 1
            session.estimated_wait = queue_estimator.estimate_wait_minutes(org_id, "RECEPTION", position=waiting, is_fast_track=getattr(session, 'is_fast_track', False))
        except Exception:
            session.position = 0
            session.estimated_wait = 5
    else:
        session.position = 0
        try:
            est = queue_estimator.estimate_intake_journey(org_id, intake)
            session.estimated_wait = est["total"]
        except Exception:
            session.estimated_wait = 5
    try:
        session.updated_at = now_naive()
    except Exception:
        pass

def update_session_from_visit(session, visit: PatientVisit):
    from . import queue_estimator
    org_id = session.org_id
    status = getattr(visit, 'status', 'REGISTERED')
    stage_map = {
        "REGISTERED": "HIMS",
        "TRIAGED": "WAIT_DOCTOR",
        "IN_CONSULTATION": "CONSULTATION",
        "ONWARD": "ONWARD",
        "CLOSED": "DONE",
        "CANCELLED": "CANCELLED"
    }
    session.current_stage = stage_map.get(status, "TRIAGE")

    if status == "TRIAGED":
        try:
            today_start = datetime.combine(now_naive().date(), datetime.min.time())
            if getattr(visit, 'started_at', None):
                waiting = db.session.query(PatientVisit).filter(
                    PatientVisit.org_id == org_id,
                    PatientVisit.status == "TRIAGED",
                    PatientVisit.started_at < visit.started_at,
                    PatientVisit.started_at >= today_start
                ).count()
            else:
                waiting = 0
            session.position = waiting + 1
            session.estimated_wait = queue_estimator.estimate_wait_minutes(org_id, "WAIT_DOCTOR", position=waiting, is_fast_track=getattr(session, 'is_fast_track', False))
        except Exception:
            session.position = 0
            session.estimated_wait = 10
    elif status == "ONWARD":
        try:
            est = queue_estimator.estimate_remaining_journey(org_id, visit)
            session.estimated_wait = est["total"]
        except Exception:
            session.estimated_wait = 15
        session.position = 0
    else:
        session.position = 0
        session.estimated_wait = 0
    try:
        session.updated_at = now_naive()
    except Exception:
        pass

def build_personal_feed(org_id: int, session) -> Dict[str, Any]:
    """Build JSON feed for personal TV — <1KB, fast on slow internet, multi-browser."""
    from . import queue_estimator
    from .models import Organization

    org = db.session.get(Organization, org_id)
    now = now_naive()

    # Get related entities
    ticket = db.session.get(QueueTicket, session.ticket_id) if session.ticket_id else None
    intake = db.session.get(ReceptionIntake, session.intake_id) if session.intake_id else None
    visit = db.session.get(PatientVisit, session.visit_id) if session.visit_id else None
    patient = db.session.get(Patient, session.patient_id) if session.patient_id else None

    # Journey timeline — premium UX like Domino's
    timeline = []
    stages_order = ["RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "LABORATORY", "PHARMACY", "DONE"]
    # Determine which stages done based on journey segments
    done_stages = set()
    current_stage = session.current_stage
    try:
        # Get journey segments for this patient
        segs = db.session.query(JourneySegment).filter(
            JourneySegment.org_id == org_id,
            (JourneySegment.patient_id == session.patient_id) | (JourneySegment.intake_id == session.intake_id) | (JourneySegment.visit_id == session.visit_id)
        ).order_by(JourneySegment.entered_at.asc()).all()
        for seg in segs:
            if seg.ended_at:
                done_stages.add(seg.stage)
    except Exception:
        pass

    # Build timeline with status
    for st in stages_order:
        if st == "DONE" and current_stage == "DONE":
            status = "done"
        elif st in done_stages:
            status = "done"
        elif st == current_stage or (current_stage == "CALLED" and st == "WAIT_DOCTOR"):
            status = "current"
        elif stages_order.index(st) < stages_order.index(current_stage) if current_stage in stages_order else False:
            status = "done"
        else:
            status = "upcoming"

        # Estimate for upcoming
        est = 0
        if status == "upcoming":
            est = queue_estimator.get_historical_avg(org_id, st, now) // 60

        timeline.append({
            "stage": st,
            "label": st.replace("_", " ").title(),
            "status": status,
            "estimated": est,
            "is_current": status == "current"
        })

    # Position text — premium
    pos_text = ""
    if session.position == 0:
        if current_stage == "CALLED":
            pos_text = "You are next — please go now!"
        elif current_stage == "DONE":
            pos_text = "You are done — safe journey!"
        else:
            pos_text = "You are being attended to"
    elif session.position == 1:
        pos_text = "You are next in line"
    else:
        pos_text = f"You are {session.position}th in line"

    # Estimated wait text
    wait_text = ""
    if session.estimated_wait == 0:
        if current_stage == "CALLED":
            wait_text = "Go now"
        elif current_stage == "DONE":
            wait_text = "Done"
        else:
            wait_text = "Soon"
    elif session.estimated_wait == 1:
        wait_text = "1 minute"
    else:
        wait_text = f"{session.estimated_wait} minutes"

    # Patient name — privacy: first name only on personal TV (full name is private)
    patient_name = ""
    if patient:
        patient_name = patient.first_name or ""
    elif ticket and ticket.patient_name:
        patient_name = ticket.patient_name.split()[0] if ticket.patient_name else ""
    elif intake:
        patient_name = intake.first_name or ""

    # Live counts — defensive, Africa slow internet <1KB
    live_counts = {}
    if current_stage not in ("DONE", "CANCELLED"):
        try:
            live_counts = queue_estimator.get_live_counts(org_id)
        except Exception:
            live_counts = {}

    return {
        "org": {"name": org.name if org else "Hospital", "code": org.code if org else "HOSP"},
        "access_key": session.access_key,
        "ticket": {"code": getattr(ticket, 'code', '') if ticket else "", "status": getattr(ticket, 'status', '') if ticket else ""} if ticket else None,
        "intake": {"ref": getattr(intake, 'ref', '') if intake else "", "stage": getattr(intake, 'stage', '') if intake else ""} if intake else None,
        "visit": {"visit_no": getattr(visit, 'visit_no', '') if visit else "", "status": getattr(visit, 'status', '') if visit else "", "clinic": getattr(visit, 'clinic', '') if visit else "", "room": getattr(visit, 'consulting_room', '') if visit else ""} if visit else None,
        "patient_name": patient_name,
        "current_stage": current_stage,
        "position": getattr(session, 'position', 0) or 0,
        "position_text": pos_text,
        "estimated_wait": getattr(session, 'estimated_wait', 0) or 0,
        "wait_text": wait_text,
        "is_fast_track": getattr(session, 'is_fast_track', False),
        "fast_track_reason": getattr(session, 'fast_track_reason', None),
        "preferred_lang": getattr(session, 'preferred_lang', 'en') or 'en',
        "timeline": timeline,
        "last_updated": now.isoformat(),
        "is_inside_hospital": getattr(session, 'is_inside_hospital', True),
        "personal_tv_url": f"/t/{session.access_key}",
        "live_counts": live_counts
    }
