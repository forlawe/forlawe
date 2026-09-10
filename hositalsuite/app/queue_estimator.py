"""
Smart Real-Time Queue Time Estimator — Free AI-like Logic, No External API
--------------------------------------------------------------------------

Founder requirement: adjust queueing time based on available patients at:
- Reception, Billing, MEGALEX/PayPoint, LAHSMA, HIMS, Triage,
- patients waiting to see each doctor, and other Onward locations (Lab, Pharmacy, etc)

Design for Africa: slow internet, low battery, works offline with cached averages.

How it works (Little's Law + Exponential Moving Average):
- Each stage has historical avg_seconds per hour_of_day + day_of_week (EMA alpha 0.3)
- Wait ≈ (patients ahead of YOU) ÷ (staff ÷ seconds_per_patient) — staff enters
  the math exactly ONCE, as throughput (F-014 fix; the old dual load/staff
  factor double-penalized low staffing and went deaf above ~4 staff)
- Real position via position_in_stage() — no more "everyone sees the same wait"
  (F-013 fix; the old code hardcoded position=0 for every journey estimate)
- Fast Track shortens the wait WITHIN a triage tier only (effective position
  halved); it can never express cross-tier priority (F-012, enforced in the
  queue ordering and pinned by tests)
- Free: no ML API, just math that runs in ~5ms on a cheap phone

Multi-hospital: per org_id, per stage, per hour, per day.

Premium UX: shows "12 min" not "720 seconds", updates live every 30s.

Considerations:
- App loading time: estimator is lazy, only computed when needed, cached 60s
- Slow internet: payload is tiny JSON {position, wait, stage}, <1KB
- Feature phones: if no JS, fallback to server-rendered wait time in template
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any

from .models import (
    JourneySegment,
    QueueTicket,
    ReceptionIntake,
    PatientVisit,
    DoctorSession,
    WorkClaim,
    VisitOnward,
    db,
    now_naive,
)

# Stages we track — matches JOURNEY_STAGES + reception sub-stages
STAGES = [
    "RECEPTION",
    "BILLING",
    "PAYMENT",
    "HIMS",
    "TRIAGE",
    "WAIT_DOCTOR",
    "CONSULTATION",
    "LABORATORY",
    "PHARMACY",
    "BILLING_OUT",
    "MEGALEX",
    "LAHSMA",
    "EMERGENCY",
]

# Default averages if no history — in seconds, conservative for Nigeria
DEFAULT_AVG = {
    "RECEPTION": 300,      # 5 min
    "BILLING": 180,        # 3 min
    "PAYMENT": 240,        # 4 min
    "HIMS": 180,           # 3 min
    "TRIAGE": 300,         # 5 min
    "WAIT_DOCTOR": 900,    # 15 min — biggest
    "CONSULTATION": 600,   # 10 min
    "LABORATORY": 1200,    # 20 min
    "PHARMACY": 600,       # 10 min
    "BILLING_OUT": 180,
    "MEGALEX": 240,
    "LAHSMA": 300,
    "EMERGENCY": 120,      # 2 min — urgent
}

_cache: Dict[str, Any] = {}
_cache_at: Dict[str, datetime] = {}  # per-org timestamp to avoid cross-org stale + race

def _get_estimate_row(org_id: int, stage: str, hour: int, dow: int):
    """Get historical average for this org/stage/hour/dow, or None."""
    try:
        from .models_v2 import QueueEstimate
        row = db.session.query(QueueEstimate).filter_by(
            org_id=org_id, stage=stage, hour_of_day=hour, day_of_week=dow
        ).first()
        return row
    except Exception:
        return None

def get_historical_avg(org_id: int, stage: str, now: datetime | None = None) -> int:
    """Get avg seconds for stage at this hour/dow, with fallback to DEFAULT_AVG."""
    now = now or now_naive()
    hour = now.hour
    dow = now.weekday()
    row = _get_estimate_row(org_id, stage, hour, dow)
    if row and row.avg_seconds:
        return int(row.avg_seconds)
    # Try any hour same stage
    try:
        from .models_v2 import QueueEstimate
        any_row = db.session.query(QueueEstimate).filter_by(org_id=org_id, stage=stage).order_by(QueueEstimate.sample_count.desc()).first()
        if any_row and any_row.avg_seconds:
            return int(any_row.avg_seconds)
    except Exception:
        pass
    return DEFAULT_AVG.get(stage, 300)

def update_estimate_from_segment(segment: JourneySegment):
    """Called when a JourneySegment closes — updates moving average.

    Free AI-like: Exponential Moving Average (EMA) — alpha 0.3
    So recent data matters more, but old data not forgotten.
    """
    if not segment.seconds or segment.seconds <= 0:
        return
    if segment.seconds > 7200:  # >2h is abandoned, ignore
        return
    try:
        from .models_v2 import QueueEstimate
        org_id = segment.org_id
        stage = segment.stage
        entered = segment.entered_at or now_naive()
        hour = entered.hour
        dow = entered.weekday()
        row = db.session.query(QueueEstimate).filter_by(
            org_id=org_id, stage=stage, hour_of_day=hour, day_of_week=dow
        ).first()
        if not row:
            row = QueueEstimate(
                org_id=org_id, stage=stage, hour_of_day=hour, day_of_week=dow,
                avg_seconds=segment.seconds, min_seconds=segment.seconds,
                max_seconds=segment.seconds, sample_count=1
            )
            db.session.add(row)
        else:
            # EMA: new_avg = alpha * new + (1-alpha) * old
            alpha = 0.3
            old = row.avg_seconds or DEFAULT_AVG.get(stage, 300)
            row.avg_seconds = int(alpha * segment.seconds + (1 - alpha) * old)
            row.min_seconds = min(row.min_seconds or segment.seconds, segment.seconds)
            row.max_seconds = max(row.max_seconds or segment.seconds, segment.seconds)
            row.sample_count = (row.sample_count or 0) + 1
            row.last_updated = now_naive()
        # Don't commit here — caller commits
    except Exception:
        pass

def count_open_segments(org_id: int, stage: str) -> int:
    """How many patients are currently in this stage (open segments).
    
    Founder: adjust based on available patients at reception, billing, MEGALEX, LASHMA, HIMS, Triage, per-doctor, onward.
    So we count both JourneySegment open + ReceptionIntake in that stage today + VisitOnward pending for onward.
    """
    total = 0
    try:
        total += db.session.query(JourneySegment).filter_by(
            org_id=org_id, stage=stage, ended_at=None
        ).count()
    except Exception:
        pass

    # Reception-related stages also have ReceptionIntake rows today
    if stage in ("RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE"):
        try:
            today = now_naive().date()
            today_start = datetime.combine(today, datetime.min.time())
            total += db.session.query(ReceptionIntake).filter(
                ReceptionIntake.org_id == org_id,
                ReceptionIntake.stage == stage,
                ReceptionIntake.created_at >= today_start
            ).count()
        except Exception:
            pass

    # Onward destinations also have VisitOnward pending
    if stage in ("LABORATORY", "PHARMACY", "BILLING_OUT", "MEGALEX", "LAHSMA", "EMERGENCY"):
        try:
            today = now_naive().date()
            today_start = datetime.combine(today, datetime.min.time())
            total += db.session.query(VisitOnward).filter(
                VisitOnward.org_id == org_id,
                VisitOnward.destination == stage,
                VisitOnward.status == "PENDING",
                VisitOnward.sent_at >= today_start
            ).count()
        except Exception:
            pass

    return total

def count_staff_available(org_id: int, stage: str) -> int:
    """How many staff are available for this stage — free logic.

    For WAIT_DOCTOR: count open DoctorSessions
    For others: count open WorkClaims for that kind
    Fallback 1 if unknown (avoid div by zero)
    """
    try:
        if stage in ("WAIT_DOCTOR", "CONSULTATION"):
            today = now_naive().date()
            return db.session.query(DoctorSession).filter(
                DoctorSession.org_id == org_id,
                DoctorSession.duty_date == today,
                DoctorSession.ended_at.is_(None),
                DoctorSession.ready.is_(True)
            ).count() or 1
        # Map stage to WorkClaim kind
        kind_map = {
            "RECEPTION": "RECEPTION",
            "BILLING": "BILLING",
            "PAYMENT": "PAYMENT",
            "HIMS": "HIMS",
            "TRIAGE": "TRIAGE",
            "LABORATORY": "LABORATORY",
            "PHARMACY": "PHARMACY",
        }
        kind = kind_map.get(stage)
        if kind:
            return db.session.query(WorkClaim).filter(
                WorkClaim.org_id == org_id,
                WorkClaim.kind == kind,
                WorkClaim.ended_at.is_(None)
            ).count() or 1
    except Exception:
        pass
    return 1

def estimate_wait_minutes(org_id: int, stage: str, position: int = 0, is_fast_track: bool = False, now: datetime | None = None) -> int:
    """Wait estimate for ONE patient, from their REAL place in line.

    F-014 fix (2026-09-04 audit): the old formula multiplied the base wait by
    BOTH a load factor containing staff AND a separate staff factor, so low
    staffing was punished twice; the staff factor floored at 0.5, which made
    everything stop responding above ~4 staff. It now applies staff EXACTLY
    once, via throughput (Little's Law):

        wait ≈ (patients ahead of you) ÷ (staff_count ÷ avg_seconds_per_patient)

    `position` = number of patients AHEAD of you in this stage (0 = you are
    next). All production callers already pass exactly that (queue index or
    same-stage count created before you).

    F-013: journey estimators below now derive this from live data instead of
    hardcoding 0 — see position_in_stage().

    is_fast_track: priority WITHIN the same triage tier — modelled as being
    seen ahead of roughly half of the same-tier queue (effective position
    halved, floored at 0). It NEVER lets the estimate cross a clinical
    priority tier; see F-012 test in tests/test_queue_estimator.py.
    """
    now = now or now_naive()
    avg_sec = max(30, get_historical_avg(org_id, stage, now))
    staff_count = max(1, count_staff_available(org_id, stage))

    # Little's Law, applied ONCE: patients served per second by this stage.
    throughput_per_sec = staff_count / float(avg_sec)

    ahead = max(0, int(position or 0))
    if is_fast_track:
        # Priority within the tier: pulled ahead of about half the queue.
        ahead = ahead // 2

    wait_min = (ahead / throughput_per_sec) / 60.0

    # Time of day friction: lunch 13-14 slower, late afternoon slower.
    hour = now.hour
    time_factor = 1.2 if 13 <= hour <= 14 else (1.3 if hour >= 16 else 1.0)
    wait_min *= time_factor

    # Clamp: at least 1 min (you still wait to be called), at most 3 hours.
    return max(1, min(180, int(wait_min)))


def position_in_stage(org_id: int, stage: str, *, intake=None, visit=None) -> int:
    """How many patients are AHEAD of this one in this stage, right now.

    F-013 fix: the personal ETA used to hardcode position=0, so every patient
    in a stage saw the same wait. This counts the real competition in the
    same sources count_open_segments() uses, strictly before this patient:

      * JourneySegment rows in the stage, entered before mine
      * ReceptionIntake rows in the stage, created today before mine
      * VisitOnward rows pending for the destination, sent before mine

    Falls back to the stage's full open count when the patient's own row
    cannot be located (e.g. estimating a stage they have not entered yet —
    they would join behind everyone there).
    """
    today_start = datetime.combine(now_naive().date(), datetime.min.time())

    try:
        # --- my own marker in this stage
        mine = None
        q = db.session.query(JourneySegment).filter(
            JourneySegment.org_id == org_id,
            JourneySegment.stage == stage,
            JourneySegment.ended_at.is_(None))
        if visit is not None and getattr(visit, "id", None):
            mine = q.filter(JourneySegment.visit_id == visit.id).first()
        if mine is None and intake is not None and getattr(intake, "id", None):
            mine = q.filter(JourneySegment.intake_id == intake.id).first()

        ahead = 0
        # `placed` = we located this patient in this stage, so a position of 0
        # is a REAL answer ("you are next"), not a failure to find them.
        placed = mine is not None
        if mine is not None and getattr(mine, "entered_at", None):
            ahead += db.session.query(JourneySegment).filter(
                JourneySegment.org_id == org_id,
                JourneySegment.stage == stage,
                JourneySegment.ended_at.is_(None),
                db.or_(
                    JourneySegment.entered_at < mine.entered_at,
                    db.and_(JourneySegment.entered_at == mine.entered_at,
                            JourneySegment.id < mine.id),
                )).count()

        # --- reception desk stages: the intake queue
        if stage in ("RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE"):
            if intake is not None and getattr(intake, "stage", None) == stage \
                    and getattr(intake, "created_at", None):
                placed = True
                ahead += db.session.query(ReceptionIntake).filter(
                    ReceptionIntake.org_id == org_id,
                    ReceptionIntake.stage == stage,
                    ReceptionIntake.created_at >= today_start,
                    ReceptionIntake.created_at < intake.created_at).count()

        # --- onward destinations: pending referrals sent before mine
        if stage in ("LABORATORY", "PHARMACY", "BILLING_OUT", "MEGALEX",
                     "LAHSMA", "EMERGENCY") and visit is not None:
            my_onward = (db.session.query(VisitOnward)
                         .filter(VisitOnward.org_id == org_id,
                                 VisitOnward.visit_id == visit.id,
                                 VisitOnward.destination == stage,
                                 VisitOnward.status == "PENDING")
                         .order_by(VisitOnward.sent_at.asc()).first())
            placed = True
            if my_onward is not None and getattr(my_onward, "sent_at", None):
                ahead += db.session.query(VisitOnward).filter(
                    VisitOnward.org_id == org_id,
                    VisitOnward.destination == stage,
                    VisitOnward.status == "PENDING",
                    VisitOnward.sent_at >= today_start,
                    VisitOnward.sent_at < my_onward.sent_at).count()
            else:
                # referred here but no row yet — join behind everyone pending
                ahead += db.session.query(VisitOnward).filter(
                    VisitOnward.org_id == org_id,
                    VisitOnward.destination == stage,
                    VisitOnward.status == "PENDING",
                    VisitOnward.sent_at >= today_start).count()

        if placed:
            return ahead
    except Exception:                                    # noqa: BLE001 — an estimate must never crash a page
        db.session.rollback()

    # Fallback: we could not place this patient — they join behind everyone
    # currently open in the stage.
    return count_open_segments(org_id, stage)

def estimate_remaining_journey(org_id: int, visit, now: datetime | None = None) -> Dict[str, Any]:
    """Estimate remaining journey for a visit — from current stage to end.

    F-013: the CURRENT stage uses the patient's real position
    (position_in_stage); later stages assume they join behind everyone
    already open in that stage. Never position=0 for everybody.
    """
    now = now or now_naive()
    remaining_stages = []
    total_min = 0

    # Determine current stage from visit.status
    status_to_stage = {
        "REGISTERED": "TRIAGE",
        "TRIAGED": "WAIT_DOCTOR",
        "IN_CONSULTATION": "CONSULTATION",
        "ONWARD": "ONWARD",  # will expand to actual onward destinations
    }
    current = status_to_stage.get(getattr(visit, 'status', ''), "TRIAGE")

    def _wait(stage: str, *, current_stage: bool) -> int:
        if current_stage:
            pos = position_in_stage(org_id, stage, visit=visit)
        else:
            pos = count_open_segments(org_id, stage)   # join behind the queue
        return estimate_wait_minutes(org_id, stage, position=pos,
                                     is_fast_track=getattr(visit, 'is_fast_track', False),
                                     now=now)

    # Stages to estimate
    if current in ("TRIAGE", "REGISTERED"):
        # Triage + wait doctor + consultation
        for st in ["TRIAGE", "WAIT_DOCTOR", "CONSULTATION"]:
            wait = _wait(st, current_stage=(st == "TRIAGE"))
            remaining_stages.append({"stage": st, "minutes": wait})
            total_min += wait
    elif current == "WAIT_DOCTOR":
        for st in ["WAIT_DOCTOR", "CONSULTATION"]:
            wait = _wait(st, current_stage=(st == "WAIT_DOCTOR"))
            remaining_stages.append({"stage": st, "minutes": wait})
            total_min += wait
    elif current == "CONSULTATION":
        wait = _wait("CONSULTATION", current_stage=True)
        remaining_stages.append({"stage": "CONSULTATION", "minutes": wait})
        total_min += wait

    # Onward steps
    try:
        pending = [s for s in getattr(visit, 'onward_steps', []) if s.status == "PENDING"]
        for step in pending:
            dest = step.destination  # LABORATORY, PHARMACY, etc
            wait = _wait(dest, current_stage=True)
            remaining_stages.append({"stage": dest, "minutes": wait})
            total_min += wait
    except Exception:
        pass

    return {"total": total_min, "stages": remaining_stages, "fast_track": bool(getattr(visit, 'is_fast_track', False))}

def estimate_intake_journey(org_id: int, intake, now: datetime | None = None) -> Dict[str, Any]:
    """Estimate for ReceptionIntake — from current stage to Triage.

    F-013: current stage uses the patient's real position in that desk queue.
    """
    now = now or now_naive()
    stage_order = ["RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE"]
    try:
        idx = stage_order.index(getattr(intake, 'stage', 'RECEPTION'))
    except ValueError:
        idx = 0
    remaining = stage_order[idx:]
    total = 0
    stages = []
    for st in remaining:
        if st == getattr(intake, 'stage', None):
            pos = position_in_stage(org_id, st, intake=intake)
        else:
            pos = count_open_segments(org_id, st)      # join behind the queue
        wait = estimate_wait_minutes(org_id, st, position=pos,
                                     is_fast_track=getattr(intake, 'is_fast_track', False),
                                     now=now)
        stages.append({"stage": st, "minutes": wait})
        total += wait
    return {"total": total, "stages": stages, "fast_track": bool(getattr(intake, 'is_fast_track', False))}

def get_live_counts(org_id: int) -> Dict[str, int]:
    """Live counts for all stages — for dashboard and personal TV, <1KB JSON.
    
    Founder requirement: adjust queueing time based on available patients at:
    - Reception, Billing, MEGALEX/PayPoint, LAHSMA, HIMS, Triage,
    - patients waiting to see each doctor, and other Onward locations (Lab, Pharmacy, etc)
    
    Africa optimized: cached 60s per-org to avoid DB hammer on slow internet, low battery.
    FIX 2026-09-04: egress guard — was 30s cache, each call did 20+ COUNT(*)
    queries. With personal TV polling every 10s and TV dashboards polling,
    100 concurrent patients => 2000+ COUNTs/min => 424 GB Supabase egress.
    60s cache cuts egress ~50% and is still real-time enough; counts are
    estimates, not seconds.
    Multi-hospital: per org_id, per-org timestamp (fixed cross-org stale bug).
    """
    global _cache, _cache_at
    cache_key = f"live_counts_{org_id}"
    now = now_naive()
    # Check cache 60s per-org — fixed bug where global _cache_at caused cross-org stale
    try:
        last_at = _cache_at.get(cache_key)
        if last_at and (now - last_at).total_seconds() < 60:
            if cache_key in _cache:
                return _cache[cache_key]
    except Exception:
        pass

    counts = {}
    for stage in STAGES:
        counts[stage] = count_open_segments(org_id, stage)

    try:
        today = now_naive().date()
        today_start = datetime.combine(today, datetime.min.time())

        # Queue tickets waiting today — per-department but total
        counts["QUEUE_WAITING"] = db.session.query(QueueTicket).filter(
            QueueTicket.org_id == org_id,
            QueueTicket.queue_date == today,
            QueueTicket.status == "WAITING"
        ).count()

        # Reception stages — from ReceptionIntake (founder: available patients at reception, billing, HIMS, Triage)
        # Each ReceptionIntake stage represents patients at that desk
        for rec_stage in ["RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE"]:
            try:
                c = db.session.query(ReceptionIntake).filter(
                    ReceptionIntake.org_id == org_id,
                    ReceptionIntake.stage == rec_stage,
                    ReceptionIntake.created_at >= today_start
                ).count()
                # Merge with JourneySegment count for same stage (max of both to show real load)
                counts[rec_stage] = max(counts.get(rec_stage, 0), c)
                counts[f"INTAKE_{rec_stage}"] = c
            except Exception:
                pass

        # Per-doctor waiting — founder: patients waiting to see each doctors
        try:
            counts["DOCTORS_READY"] = db.session.query(DoctorSession).filter(
                DoctorSession.org_id == org_id,
                DoctorSession.duty_date == today,
                DoctorSession.ended_at.is_(None),
                DoctorSession.ready.is_(True)
            ).count()
            counts["TRIAGE_OPEN"] = db.session.query(WorkClaim).filter(
                WorkClaim.org_id == org_id,
                WorkClaim.kind == "TRIAGE",
                WorkClaim.ended_at.is_(None)
            ).count()
            # Per-doctor queue: PatientVisit TRIAGED waiting
            counts["WAIT_DOCTOR_VISITS"] = db.session.query(PatientVisit).filter(
                PatientVisit.org_id == org_id,
                PatientVisit.status == "TRIAGED",
                PatientVisit.started_at >= today_start
            ).count()
        except Exception:
            pass

        # Onward locations — LAB, PHARMACY, BILLING_OUT, MEGALEX, LAHSMA, EMERGENCY
        # Founder: other Onward locations
        try:
            for onward_dest in ["LABORATORY", "PHARMACY", "BILLING_OUT", "MEGALEX", "LAHSMA", "EMERGENCY"]:
                c = db.session.query(VisitOnward).filter(
                    VisitOnward.org_id == org_id,
                    VisitOnward.destination == onward_dest,
                    VisitOnward.status == "PENDING",
                    VisitOnward.sent_at >= today_start
                ).count()
                counts[f"ONWARD_{onward_dest}"] = c
                # Merge into main stage count
                if onward_dest in counts:
                    counts[onward_dest] = counts[onward_dest] + c
                else:
                    counts[onward_dest] = c
        except Exception:
            pass

        # Billing counts — from JourneySegment BILLING + VisitOnward BILLING_OUT
        # Already counted via STAGES loop

    except Exception:
        pass

    # Cache 30s per-org
    try:
        _cache[cache_key] = counts
        _cache_at[cache_key] = now
    except Exception:
        pass
    return counts
