"""TV display engine — live feed for monitors in waiting areas.

WHAT IT DOES
------------
Multiple TVs, but waiting area main TV shows MORE (founder req):
- Queue tickets (code + full name + stats)
- Reception / Billing / PayPoint
- HIMS registered
- Triage waiting + placed
- Doctor call-ins (NOW SERVING)
- Onward desks (Lab, Pharmacy, Wards, etc.)
- LAHSMA clearance

Each TV is a row in tv_screen, per-tenant, admin editable.
Clinic TV filters to its clinic, Department TV to its department,
Main TV shows everything.

NIGERIA NATIVE VOICES - 2 male 2 female recycled daily
-------------------------------------------------------
Browser Speech API voices differ per device. We pick 4 best Nigerian-friendly
voices available:
- Prefer en-NG, yo, ig, ha, then en-GB, en-US
- Try to detect gender from voice name (contains female/male, or known lists)
- Recycle daily: day_of_year % 4 picks which voice speaks today
  Mon = Female1, Tue = Male1, Wed = Female2, Thu = Male2, then repeat
- If no Nigerian voice found, use best English and still rotate

Bilingual: English + Yoruba (founder req). We announce in both:
EN: "Folake Abatan, please go to Room 3, Dental Clinic"
YO: "Folake Abatan, ẹ jọwọ lọ sí Room 3, Dental Clinic"
We use i18n for Yoruba translations of fixed phrases, name stays same.

NO EMR - only names, codes, places, counts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .clinical_tier import clinical_order, emergency_tier_expr
from .models import (
    ConsultingRoom,
    DoctorSession,
    JourneySegment,
    Patient,
    PatientVisit,
    QueueTicket,
    ReceptionIntake,
    ServiceClinic,
    ServiceDestination,
    TvScreen,
    VisitOnward,
    db,
    now_naive,
)
from . import tracking as tracking_engine


# ------------------------------------------------------------------ helpers
def ensure_default_screens(org_id: int) -> list[TvScreen]:
    """Seed default TVs if none exist. Idempotent."""
    existing = db.session.query(TvScreen).filter_by(org_id=org_id).all()
    if existing:
        return existing
    defaults = [
        TvScreen(
            org_id=org_id,
            code="MAIN",
            name="Waiting Area Main TV",
            location="General Waiting Hall",
            screen_type="WAITING_MAIN",
            show_full_name=True,
            show_queue_stats=True,
            show_reception=True,
            show_triage=True,
            show_consulting=True,
            show_onward=True,
            voice_enabled=True,
            voice_rotate_daily=True,
            voice_languages="en,yo,ha,ig",
            voice_volume=100,
            brightness=100,
            night_mode=False,
            active=True,
        ),
        TvScreen(
            org_id=org_id,
            code="DENTAL",
            name="Dental Clinic TV",
            location="Dental Waiting Area",
            screen_type="CLINIC",
            clinic_code="DENTAL",
            show_full_name=True,
            show_queue_stats=True,
            voice_enabled=True,
            voice_rotate_daily=True,
            voice_languages="en,yo,ha,ig",
            voice_volume=90,
            brightness=100,
            night_mode=False,
            active=True,
        ),
        TvScreen(
            org_id=org_id,
            code="OPD",
            name="OPD TV",
            location="OPD Waiting Area",
            screen_type="CLINIC",
            clinic_code="OPD",
            show_full_name=True,
            show_queue_stats=True,
            voice_enabled=True,
            voice_rotate_daily=True,
            voice_languages="en,yo,ha,ig",
            voice_volume=90,
            brightness=100,
            night_mode=False,
            active=True,
        ),
        TvScreen(
            org_id=org_id,
            code="PHARMACY",
            name="Pharmacy TV",
            location="Pharmacy Waiting Area",
            screen_type="DEPARTMENT",
            show_full_name=True,
            show_queue_stats=False,
            voice_enabled=True,
            voice_rotate_daily=True,
            voice_languages="en,yo,ha,ig",
            voice_volume=80,
            brightness=100,
            night_mode=False,
            active=True,
        ),
        TvScreen(
            org_id=org_id,
            code="FASTTRACK",
            name="⭐ Fast Track Executive TV",
            location="Executive Premium Building — Fast Track Lounge",
            screen_type="EXECUTIVE",
            show_full_name=True,
            show_queue_stats=True,
            show_reception=True,
            show_triage=True,
            show_consulting=True,
            show_onward=True,
            show_fast_track_only=True,
            is_executive=True,
            voice_enabled=True,
            voice_rotate_daily=True,
            voice_languages="en,yo,ha,ig",
            voice_volume=100,
            brightness=100,
            night_mode=False,
            active=True,
        ),
    ]
    for s in defaults:
        db.session.add(s)
    db.session.commit()
    return defaults


def _today_start() -> datetime:
    return datetime.combine(now_naive().date(), datetime.min.time())


def _tv_public_code(patient, ticket_code: str | None) -> str:
    """Identifier a PUBLIC screen may show for a patient (F-028).

    The queue ticket code (e.g. "E-014") is the identifier patients actually
    hold, so it is safe and preferred. Without one we mask the hospital
    number to its last 3 characters — enough for a patient to recognise
    their own call, useless to a stranger harvesting full numbers.
    """
    if ticket_code:
        return ticket_code
    hn = (getattr(patient, "hospital_number", "") or "").replace(" ", "")
    return f"••{hn[-3:]}" if hn else "—"


def _first_name_only(full: str | None) -> str:
    """Public displays announce first names only (NDPA — see tv_feed)."""
    return (full or "").strip().split()[0] if (full or "").strip() else "Patient"


# ------------------------------------------------------------------ feed
def tv_feed(org_id: int, screen: TvScreen | None = None) -> dict[str, Any]:
    """Build live data for a TV screen. Returns dict for JSON + template."""
    start = _today_start()
    now = now_naive()

    # Determine filters
    clinic_filter = (screen.clinic_code or "").strip().upper() if screen else None
    dept_filter = screen.department_id if screen and screen.department_id else None
    fast_only = bool(getattr(screen, 'show_fast_track_only', False)) if screen else False
    is_executive = bool(getattr(screen, 'is_executive', False)) if screen else False
    # Executive TV automatically implies fast-track gold theme, but filter is explicit

    # --- Queue tickets today
    q_q = db.session.query(QueueTicket).filter(
        QueueTicket.org_id == org_id, QueueTicket.queue_date == now.date()
    )
    if dept_filter:
        q_q = q_q.filter(QueueTicket.department_id == dept_filter)
    if fast_only:
        q_q = q_q.filter(QueueTicket.is_fast_track.is_(True))
    queue_all = q_q.order_by(QueueTicket.created_at.desc()).limit(100).all()
    queue_waiting = [t for t in queue_all if t.status == "WAITING"]
    queue_called = [t for t in queue_all if t.status == "CALLED"]
    queue_done = [t for t in queue_all if t.status == "DONE"]

    # --- Reception intakes waiting
    r_q = db.session.query(ReceptionIntake).filter(
        ReceptionIntake.org_id == org_id, ReceptionIntake.created_at >= start
    )
    if fast_only:
        r_q = r_q.filter(ReceptionIntake.is_fast_track.is_(True))
    reception_rows = r_q.filter(ReceptionIntake.stage.in_(("RECEPTION", "BILLING", "PAYMENT", "PAID"))).order_by(
        ReceptionIntake.created_at.asc()
    ).limit(50).all()

    # --- Patient visits today
    v_q = db.session.query(PatientVisit).filter(
        PatientVisit.org_id == org_id, PatientVisit.started_at >= start
    )
    if clinic_filter:
        v_q = v_q.filter(db.func.upper(db.func.trim(PatientVisit.clinic)) == clinic_filter)
    if fast_only:
        v_q = v_q.filter(PatientVisit.is_fast_track.is_(True))
    visits = v_q.order_by(PatientVisit.started_at.desc()).limit(100).all()
    visits_by_id = {v.id: v for v in visits}
    patient_ids = {v.patient_id for v in visits}
    patients = {p.id: p for p in db.session.query(Patient).filter(Patient.id.in_(patient_ids or [0])).all()}

    triaged = [v for v in visits if v.status == "TRIAGED"]
    in_consult = [v for v in visits if v.status == "IN_CONSULTATION"]
    onward = [v for v in visits if v.status == "ONWARD"]

    # --- Doctor sessions open today
    sessions = (
        db.session.query(DoctorSession)
        .filter(
            DoctorSession.org_id == org_id,
            DoctorSession.duty_date == now.date(),
            DoctorSession.ended_at.is_(None),
            DoctorSession.ready.is_(True),
        )
        .all()
    )
    if clinic_filter:
        sessions = [s for s in sessions if (s.clinic or "").strip().upper() == clinic_filter]

    # --- Onward steps pending — only today's visits, fast-track first, deduped
    # Previously queried ALL pending across all time, so abandoned rows from days ago
    # showed as 5249m ago and made TV look broken. Now filter to today's visits.
    o_q = db.session.query(VisitOnward).join(PatientVisit, VisitOnward.visit_id == PatientVisit.id).filter(
        VisitOnward.org_id == org_id, VisitOnward.status == "PENDING",
        PatientVisit.started_at >= start,
    )
    if fast_only:
        o_q = o_q.filter(PatientVisit.is_fast_track.is_(True))
        # F-012: the TV board displays the same clinical order staff act on —
    # EMERGENCY routing first, then Fast Track, then time (app/clinical_tier.py).
    pending_onward_raw = o_q.order_by(*clinical_order(
        emergency_tier_expr(VisitOnward.destination),
        PatientVisit.is_fast_track,
        VisitOnward.sent_at.asc())).limit(100).all()
    # Deduplicate by (visit_id, destination) — unique constraint should prevent dupes,
    # but guard against race / old data
    seen_onward = set()
    pending_onward = []
    for step in pending_onward_raw:
        key = (step.visit_id, step.destination)
        if key in seen_onward:
            continue
        seen_onward.add(key)
        pending_onward.append(step)
    # Filter onward by clinic if screen is clinic-specific
    if clinic_filter:
        pending_onward = [
            step for step in pending_onward if visits_by_id.get(step.visit_id) and (visits_by_id[step.visit_id].clinic or "").upper() == clinic_filter
        ]

    # Enrich onward with visit + patient — privacy: first name only
    onward_enriched = []
    for step in pending_onward[:20]:
        visit = visits_by_id.get(step.visit_id)
        patient = patients.get(visit.patient_id) if visit else None
        waited = max(0, int((now - step.sent_at).total_seconds() // 60))
        display_name = "Patient"
        if patient:
            display_name = _first_name_only(getattr(patient, 'spoken_name', None) or patient.full_name)  # F-028: spoken_name is calling order; full_name is SURNAME-first
        onward_enriched.append({
            "step": step,
            "visit": visit,
            "patient": patient,
            "display_name": display_name,
            "waited": waited,
            "is_fast_track": bool(visit.is_fast_track) if visit else False,
            "fast_track_reason": getattr(visit, 'fast_track_reason', None) if visit else None,
        })

    # --- Journey segments open (where patient is now)
    open_segments = (
        db.session.query(JourneySegment)
        .filter(JourneySegment.org_id == org_id, JourneySegment.ended_at.is_(None))
        .order_by(JourneySegment.entered_at.desc())
        .limit(100)
        .all()
    )

    # --- Build NOW SERVING: patients IN_CONSULTATION + recently CALLED queue + recently triaged placed
    # Privacy: public TV shows first name only + ticket code, NOT full name + hospital number (NDPA)
    # F-028: the JSON feed honours the same rule the screen follows — no full
    # names, no full hospital numbers on the public wire. Voice announces the
    # first-name display field (the TV page reads item.name, never a private key).
    ticket_code_by_patient = {t.patient_id: t.code for t in queue_all if t.patient_id}
    now_serving = []
    # 1. Patients currently in consultation (most important)
    for v in sorted(in_consult, key=lambda x: x.seen_at or x.triaged_at or x.started_at, reverse=True)[:3]:
        p = patients.get(v.patient_id)
        if not p:
            continue
        try:
            journey_est = tracking_engine.estimate_remaining_journey(org_id, v)
        except Exception:
            journey_est = {"total": 0, "stages": [], "fast_track": bool(v.is_fast_track)}
        # Privacy: use spoken_name (title + first name) for display, code is ticket or masked hospital number
        display_name = _first_name_only(getattr(p, 'spoken_name', None) or p.full_name)  # F-028: spoken_name is calling order; full_name is SURNAME-first
        now_serving.append(
            {
                "type": "consultation",
                "code": _tv_public_code(p, ticket_code_by_patient.get(p.id)),
                "name": display_name,  # first name only for privacy
                "spoken": display_name,  # F-028: first name only (spoken_name carries the surname)
                "clinic": v.clinic,
                "room": v.consulting_room,
                "doctor": v.doctor.name if v.doctor else "",
                "since": v.seen_at or v.triaged_at,
                "waited": max(0, int((now - (v.seen_at or v.triaged_at or v.started_at)).total_seconds() // 60)),
                "is_fast_track": bool(v.is_fast_track),
                "fast_track_reason": v.fast_track_reason,
                "journey_estimate": journey_est,
                "preferred_lang": getattr(p, 'preferred_lang', 'en') or 'en',
            }
        )
    # 2. Recently called queue tickets
    for t in sorted(queue_called, key=lambda x: x.called_at or x.created_at, reverse=True)[:2]:
        now_serving.append(
            {
                "type": "queue_called",
                "code": t.code,
                "name": _first_name_only(t.patient_name),  # F-028: first name only on the wire
                "spoken": _first_name_only(t.patient_name),
                "clinic": t.department.name if t.department else "",
                "room": t.department.name if t.department else "",
                "doctor": "",
                "since": t.called_at,
                "waited": 0,
                "is_fast_track": bool(getattr(t, "is_fast_track", False)),
                "fast_track_reason": getattr(t, "fast_track_reason", None),
            }
        )

    # --- NEXT: triaged waiting + queue waiting (fast-track first, then oldest) — premium patient care
    next_up = []
    # Triaged: fast-track first — privacy: first name only
    sorted_triaged = sorted(triaged, key=lambda x: (not bool(x.is_fast_track), x.triaged_at or x.started_at))
    for idx, v in enumerate(sorted_triaged[:5]):
        p = patients.get(v.patient_id)
        if not p:
            continue
        try:
            journey_est = tracking_engine.estimate_remaining_journey(org_id, v)
            wait_est = tracking_engine.estimate_wait_minutes(org_id, stage="WAIT_DOCTOR", position=idx, is_fast_track=bool(v.is_fast_track))
        except Exception:
            journey_est = {"total": 0, "stages": [], "fast_track": bool(v.is_fast_track)}
            wait_est = 0
        display_name = _first_name_only(getattr(p, 'spoken_name', None) or p.full_name)  # F-028: spoken_name is calling order; full_name is SURNAME-first
        next_up.append(
            {
                "type": "triaged",
                "code": _tv_public_code(p, ticket_code_by_patient.get(p.id)),
                "name": display_name,
                "spoken": display_name,  # F-028: first name only (spoken_name carries the surname)
                "clinic": v.clinic,
                "room": v.consulting_room or v.clinic,
                "doctor": v.doctor.name if v.doctor else "",
                "is_fast_track": bool(v.is_fast_track),
                "fast_track_reason": v.fast_track_reason,
                "position": idx + 1,
                "estimated_wait": wait_est,
                "journey_estimate": journey_est,
                "preferred_lang": getattr(p, 'preferred_lang', 'en') or 'en',
            }
        )
    # Queue waiting: fast-track first
    sorted_q_wait = sorted(queue_waiting, key=lambda x: (not bool(getattr(x, "is_fast_track", False)), x.created_at))
    for idx, t in enumerate(sorted_q_wait[:5]):
        if len(next_up) >= 8:
            break
        try:
            wait_est = tracking_engine.estimate_wait_minutes(org_id, stage="RECEPTION", position=idx, is_fast_track=bool(getattr(t, "is_fast_track", False)))
        except Exception:
            wait_est = 0
        next_up.append(
            {
                "type": "queue_waiting",
                "code": t.code,
                "name": _first_name_only(t.patient_name),  # F-028: first name only on the wire
                "spoken": _first_name_only(t.patient_name),
                "clinic": t.department.name if t.department else "",
                "room": "",
                "doctor": "",
                "is_fast_track": bool(getattr(t, "is_fast_track", False)),
                "fast_track_reason": getattr(t, "fast_track_reason", None),
                "position": idx + 1,
                "estimated_wait": wait_est,
            }
        )

    # --- Reception rows with fast-track + journey estimate — privacy: first name only
    reception_enriched = []
    for idx, r in enumerate(reception_rows):
        try:
            journey_est = tracking_engine.estimate_intake_journey(org_id, r)
            wait_est = tracking_engine.estimate_wait_minutes(org_id, stage="RECEPTION", position=idx, is_fast_track=bool(r.is_fast_track))
        except Exception:
            journey_est = {"total": 0, "stages": [], "fast_track": bool(r.is_fast_track)}
            wait_est = 0
        # Privacy: show first name only, not full name
        first = (r.full_name.split()[0] if getattr(r, 'full_name', None) else "Patient")
        reception_enriched.append(
            {
                "row": r,
                "display_name": first,
                "is_fast_track": bool(r.is_fast_track),
                "fast_track_reason": r.fast_track_reason,
                "position": idx + 1,
                "estimated_wait": wait_est,
                "journey_estimate": journey_est,
            }
        )

    # --- Stats for waiting area main TV (include fast-track counts)
    fast_track_waiting = len([v for v in visits if v.is_fast_track and v.status in ("REGISTERED", "TRIAGED")]) + len([r for r in reception_rows if r.is_fast_track])
    stats = {
        "queue_waiting": len(queue_waiting),
        "queue_called": len(queue_called),
        "queue_done": len(queue_done),
        "reception_waiting": len(reception_rows),
        "triaged": len(triaged),
        "in_consultation": len(in_consult),
        "onward_pending": len(pending_onward),
        "doctors_ready": len(sessions),
        "total_today": len(visits) + len(queue_all),
        "fast_track_waiting": fast_track_waiting,
    }

    # --- Per clinic breakdown for main TV
    clinic_counts = {}
    for v in visits:
        key = (v.clinic or "UNKNOWN").upper()
        clinic_counts[key] = clinic_counts.get(key, 0) + 1

    return {
        "screen": screen,
        "now": now,
        "now_serving": now_serving,
        "next_up": next_up,
        "queue_waiting": queue_waiting,
        "queue_called": queue_called,
        "reception": reception_rows,
        "reception_enriched": reception_enriched,
        "triaged": triaged,
        "in_consultation": in_consult,
        "onward_pending": pending_onward,
        "onward_enriched": onward_enriched,
        "visits_by_id": visits_by_id,
        "sessions": sessions,
        "stats": stats,
        "clinic_counts": clinic_counts,
        "patients": patients,
    }


# ------------------------------------------------------------------ voice rotation
def voice_rotation_for_today(org_id: int, screen_id: int | None = None) -> dict:
    """Pick 2 male 2 female Nigerian voices recycled daily, 4 languages.

    Returns dict with day_index, voice_slot, and description.
    Actual voice selection happens in browser (getVoices), but we tell browser
    which slot to use today so all TVs in same hospital speak same voice that day.
    Now includes Hausa + Igbo (en,yo,ha,ig) — founder wanted Nigeria native voices,
    premium++ speaks patient's preferred language + all 4 for inclusivity.
    """
    day_of_year = now_naive().timetuple().tm_yday
    # 4 slots: 0=Female1,1=Male1,2=Female2,3=Male2
    slot = day_of_year % 4
    slot_names = ["Female Voice 1 - Ada (Nigerian)", "Male Voice 1 - Emeka (Nigerian)", "Female Voice 2 - Folake (Nigerian)", "Male Voice 2 - Chinedu (Nigerian)"]
    # Language codes for browser Speech API — includes Hausa + Igbo
    # Not all devices have ha-NG/ig-NG voices installed, but we request them;
    # browser falls back to en-NG with Nigerian accent, still premium.
    return {
        "day_of_year": day_of_year,
        "slot": slot,
        "slot_name": slot_names[slot],
        "all_slots": slot_names,
        "languages": ["en-NG", "yo-NG", "ha-NG", "ig-NG", "en"],
        "language_labels": {
            "en": "English",
            "yo": "Yorùbá",
            "ha": "Hausa",
            "ig": "Igbo",
        },
    }
