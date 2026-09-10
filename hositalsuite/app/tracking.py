"""Monitoring & Tracking Engine — how long everything actually takes.

WHAT THIS IS FOR
----------------
Every stage of the journey already stamps a time. Nobody was reading them. This
engine turns those stamps into the answers a hospital manager cannot get today:

  * How long does one patient take, front door to home?
  * How long do they stand at each desk?
  * Which department is quick, and which one holds everybody up?
  * Which doctor's room is overloaded right now, and who is free?
  * Is the hospital getting better week on week, or worse?

THE ONE RULE THAT MATTERS MOST
------------------------------
**Monitoring must NEVER break patient care.**

If this engine has a bug, a patient must still be able to walk from Reception
to the Pharmacy. So every function that WRITES is wrapped: it logs the fault
and returns quietly instead of raising. A crashed measurement is an annoyance;
a crashed reception desk is a queue of angry people and a hospital that stops
trusting the software. `track()` is the guard that enforces this, and there is
a test that deliberately breaks the engine and proves Reception still works.

HONEST NUMBERS
--------------
  * Averages come from CLOSED segments only. A patient still standing in the
    pharmacy has no duration yet, and guessing one would flatter the figures.
  * The median is reported next to the mean, because one forgotten patient at
    four hours drags a mean to nonsense while the median stays truthful.
  * A stage with fewer than MIN_SAMPLE finished patients is marked "not enough
    data" rather than shown as a confident number. Three patients is an
    anecdote, not a measurement.

NOT AN EMR
----------
Where a patient was and for how long. Never why they were there, never what
was found. A guard test fails the build if a clinical column ever appears.
"""
from __future__ import annotations

import functools
import logging
from datetime import date, datetime, timedelta

from . import announce
from .models import (JOURNEY_STAGE_CODES, JOURNEY_STAGE_LABELS, JourneySegment,
                     db, now_naive)
from .timefmt import say_hm

log = logging.getLogger(__name__)

# Below this many finished patients we say "not enough data yet" instead of
# printing a number somebody might act on.
MIN_SAMPLE = 5

# A patient cannot really be standing at one desk for eight hours — the desk
# forgot to tick them off, or the app was closed. Segments longer than this are
# excluded from averages so one forgotten row cannot poison a department's
# figures. They still show on the live board, flagged, because a real person
# may genuinely have been abandoned and somebody should go and look.
SANITY_CAP_HOURS = 8
SANITY_CAP_SECONDS = SANITY_CAP_HOURS * 3600


# ------------------------------------------------------------------ the guard
def _safe(default=None):
    """Decorator: this function may NEVER raise into patient care.

    Measurement is secondary to care. A receptionist must be able to take a
    patient in even if the statistics engine is completely broken, so every
    public write is wrapped at its OWN boundary.

    Applying the guard as a decorator (rather than an inner helper) is
    deliberate and was found the hard way: a guard placed INSIDE the function
    only protects the code it wraps, so a fault in the function's own
    signature, defaults or argument handling still escaped and took the
    reception desk down with it. Guarding at the boundary means nothing in
    here can reach the caller.
    """
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:                             # noqa: BLE001
                log.exception("tracking failed in %s (patient care continues)",
                              getattr(fn, "__name__", "?"))
                # DO NOT roll back. The caller is mid-transaction with real
                # patient work in this same session — an un-committed intake, a
                # folder, a visit. Rolling back here to tidy up OUR failed
                # measurement would silently discard THEIR patient, and the
                # page would still return 200 so nobody would notice. That is
                # far worse than a missing statistic. We drop the tracking row
                # instead: SQLAlchemy will simply not flush a row we abandoned,
                # and any partial write is harmless because every duration is
                # recomputed from timestamps, never accumulated.
                return default() if callable(default) else default
        return inner
    return wrap


def safely(fn, *args, **kwargs):
    """Call a tracking function from a VIEW without any risk to the request.

    The functions below already guard themselves. This is the second layer, for
    the case the guards themselves are wrong: views call
    `tracking.safely(tracking.enter, ...)` so that even a completely broken
    tracking module cannot stop a patient being seen.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:                                     # noqa: BLE001
        log.exception("tracking call failed (patient care continues)")
        # Deliberately no rollback — see the note in _safe(). The caller's
        # patient work is in this same session and must survive our failure.
        return None


def track(fn, *args, **kwargs):
    """Run any callable without letting it break the caller. Kept for callers
    that want to guard a one-off block rather than a whole function."""
    try:
        return fn(*args, **kwargs)
    except Exception:                                     # noqa: BLE001
        log.exception("tracking failed (patient care continues)")
        return None


# ------------------------------------------------------------------ writing
def _open_segment(org_id, stage, *, intake_id=None, visit_id=None,
                  patient_id=None, department_id=None, staff_id=None):
    """Write one tracking row inside a SAVEPOINT.

    WHY A SAVEPOINT (learned on real PostgreSQL, not SQLite)
    --------------------------------------------------------
    PostgreSQL aborts the ENTIRE transaction when any statement fails, and then
    refuses every later statement until it is rolled back. SQLite does not, so
    this never showed locally.

    That matters here because a tracking row can legitimately fail — a bad
    foreign key, a race, a schema drift. Catching the error was not enough: the
    caller's transaction was already poisoned, so the patient work that came
    AFTER our failure would die too, and the desk would break for a reason
    nobody could see.

    A savepoint contains the damage. If our row fails we roll back only to the
    savepoint; the caller's un-committed patient work is untouched and the
    transaction stays usable. This is the difference between "we lost a
    statistic" and "we lost the patient".
    """
    if stage not in JOURNEY_STAGE_CODES:
        return None
    row = JourneySegment(org_id=org_id, stage=stage, intake_id=intake_id,
                         visit_id=visit_id, patient_id=patient_id,
                         department_id=department_id, staff_id=staff_id,
                         entered_at=now_naive())
    nested = db.session.begin_nested()
    try:
        db.session.add(row)
        db.session.flush()
        nested.commit()
    except Exception:                                     # noqa: BLE001
        nested.rollback()                                 # only OUR row is undone
        raise
    return row


@_safe(default=list)
def open_segments(org_id, *, intake_id=None, visit_id=None, patient_id=None):
    """Every stretch this patient is currently standing in."""
    # Match on ANY identifier supplied, not just the first one set. A journey
    # begins before the folder exists, so its early rows carry only an intake
    # id; once the folder is opened the later rows carry a visit id. Matching
    # only the visit id left those early rows open forever and the patient
    # appeared to be standing at HIMS all day. Belt and braces on top of the
    # caller flushing first.
    from sqlalchemy import or_
    conditions = []
    if visit_id is not None:
        conditions.append(JourneySegment.visit_id == visit_id)
    if intake_id is not None:
        conditions.append(JourneySegment.intake_id == intake_id)
    if patient_id is not None:
        conditions.append(JourneySegment.patient_id == patient_id)
    if not conditions:
        return []
    return (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.ended_at.is_(None),
                    or_(*conditions))
            .all())


def _close(row, when=None):
    when = when or now_naive()
    row.ended_at = when
    delta = (when - row.entered_at).total_seconds()
    row.seconds = max(0, int(delta))        # clocks can drift; never negative
    return row


@_safe()
def enter(org_id, stage, *, intake_id=None, visit_id=None, patient_id=None,
          department_id=None, staff_id=None, close_previous=True):
    """The patient has arrived somewhere. Closes where they were before.

    Returns the new segment, or None if tracking is unavailable — callers must
    treat None as "no measurement", never as an error worth showing a patient.
    """
    if close_previous:
        for prev in open_segments(org_id, intake_id=intake_id,
                                  visit_id=visit_id, patient_id=patient_id):
            _close(prev)
    return _open_segment(org_id, stage, intake_id=intake_id,
                         visit_id=visit_id, patient_id=patient_id,
                         department_id=department_id, staff_id=staff_id)


@_safe(default=list)
def leave(org_id, *, intake_id=None, visit_id=None, patient_id=None, stage=None):
    """Close whatever the patient is standing in, without opening anything new."""
    closed = []
    for row in open_segments(org_id, intake_id=intake_id, visit_id=visit_id,
                             patient_id=patient_id):
        if stage is None or row.stage == stage:
            closed.append(_close(row))
    return closed


@_safe(default=list)
def attach_visit(org_id, intake_id, visit_id, patient_id):
    """Reception segments predate the folder — join them to the visit.

    Without this the front half of the journey (Reception, Billing, Paying
    Point) would be orphaned from the back half, and "how long did the whole
    visit take?" could never be answered.
    """
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.intake_id == intake_id).all())
    for row in rows:
        row.visit_id = visit_id
        row.patient_id = patient_id
    return rows


@_safe(default=list)
def close_journey(org_id, *, visit_id=None, intake_id=None):
    """The patient has gone home. Nothing may be left open."""
    return leave(org_id, visit_id=visit_id, intake_id=intake_id)


# ------------------------------------------------------------------ one patient
def journey_for(org_id, visit_id) -> list[JourneySegment]:
    return (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.visit_id == visit_id)
            .order_by(JourneySegment.entered_at.asc()).all())


def total_minutes(segments) -> int:
    """Door to door: first arrival to last departure, not the sum of parts.

    Summing the parts would double-count anything that overlapped and would
    silently drop the gaps between desks — the walking, the queueing that
    nobody logged. Wall-clock is the number the patient actually experienced.
    """
    rows = [s for s in segments if s.entered_at]
    if not rows:
        return 0
    start = min(s.entered_at for s in rows)
    ends = [s.ended_at for s in rows if s.ended_at]
    end = max(ends) if len(ends) == len(rows) else now_naive()
    return max(0, int((end - start).total_seconds() // 60))


# ------------------------------------------------------------------ maths
def _median(values):
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _summarise(seconds_list) -> dict:
    """Mean AND median, plus an honest 'is this enough data?' flag."""
    clean = [s for s in seconds_list if s is not None and 0 <= s <= SANITY_CAP_SECONDS]
    n = len(clean)
    if n == 0:
        return {"count": 0, "average": 0, "median": 0, "longest": 0,
                "reliable": False}
    return {
        "count": n,
        "average": int(sum(clean) / n // 60),
        "median": int(_median(clean) // 60),
        "longest": int(max(clean) // 60),
        "reliable": n >= MIN_SAMPLE,
    }


def _range(days: int):
    end = now_naive()
    start = datetime.combine((end - timedelta(days=days - 1)).date(),
                             datetime.min.time())
    return start, end


# ------------------------------------------------------------------ by stage
def stage_performance(org_id, days: int = 7) -> list[dict]:
    """How long each stage takes. The heart of the whole engine."""
    start, end = _range(days)
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.entered_at >= start,
                    JourneySegment.ended_at.isnot(None))
            .all())
    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r.stage, []).append(r.seconds)

    out = []
    for code, label in [(c, JOURNEY_STAGE_LABELS[c]) for c in JOURNEY_STAGE_CODES]:
        stats = _summarise(buckets.get(code, []))
        stats.update({"stage": code, "label": label,
                      "rating": rate_stage(stats)})
        out.append(stats)
    out.sort(key=lambda s: (-s["count"], s["label"]))
    return out


# How long each stage SHOULD take, in minutes. These are starting points a
# hospital can argue with — the point is to have a line, not to be perfect.
STAGE_TARGET_MINUTES = {
    "RECEPTION": 10, "BILLING": 10, "PAYMENT": 10, "HIMS": 10,
    "TRIAGE": 15, "WAIT_DOCTOR": 30, "CONSULTATION": 20,
    "LABORATORY": 30, "PHARMACY": 20, "BILLING_OUT": 10,
    "MEGALEX": 10, "LAHSMA": 15, "EMERGENCY": 5,
}


def rate_stage(stats: dict, stage: str | None = None) -> str:
    """Plain-English verdict, never a bare number."""
    if not stats.get("count"):
        return "NO DATA"
    if not stats.get("reliable"):
        return "TOO FEW"
    target = STAGE_TARGET_MINUTES.get(stage or stats.get("stage", ""), 20)
    median = stats.get("median", 0)
    if median <= target * 0.6:
        return "EXCELLENT"
    if median <= target:
        return "GOOD"
    if median <= target * 1.5:
        return "SLOW"
    return "HOLDING EVERYONE UP"


RATING_COLOURS = {
    "EXCELLENT": "#1a7f37", "GOOD": "#4d9e3f", "SLOW": "#b58900",
    "HOLDING EVERYONE UP": "#c0262c", "TOO FEW": "#6b7280", "NO DATA": "#9ca3af",
}


# ------------------------------------------------------------------ by department
def department_performance(org_id, days: int = 7, only_departments=None) -> list[dict]:
    """Per-department figures. `only_departments` narrows it to what the
    viewer is allowed to see — an HOD gets their own department, not a
    league table of colleagues they cannot manage.
    """
    from .models import Department
    start, _ = _range(days)
    q = (db.session.query(JourneySegment)
         .filter(JourneySegment.org_id == org_id,
                 JourneySegment.entered_at >= start,
                 JourneySegment.ended_at.isnot(None),
                 JourneySegment.department_id.isnot(None)))
    if only_departments is not None:
        q = q.filter(JourneySegment.department_id.in_(only_departments or [-1]))
    rows = q.all()
    buckets: dict[int, list] = {}
    for r in rows:
        buckets.setdefault(r.department_id, []).append(r.seconds)
    if not buckets:
        return []
    names = {d.id: d.name for d in db.session.query(Department)
             .filter(Department.id.in_(list(buckets))).all()}
    out = []
    for dept_id, seconds in buckets.items():
        stats = _summarise(seconds)
        stats.update({"department_id": dept_id,
                      "label": names.get(dept_id, "—"),
                      "rating": rate_stage(stats)})
        out.append(stats)
    out.sort(key=lambda s: -s["median"])
    return out


# ------------------------------------------------------------------ by staff
def staff_workload(org_id, days: int = 7, only_departments=None) -> list[dict]:
    """How many patients each person handled, and how long they took.

    DELIBERATELY NOT A LEAGUE TABLE. A doctor who sees the hardest patients
    will look "slow", and ranking people on that would be unfair and would
    push staff to rush. It is labelled as workload, for spotting who is
    drowning and who has room — which is what fair allocation needs.
    """
    from .models import User
    start, _ = _range(days)
    q = (db.session.query(JourneySegment)
         .filter(JourneySegment.org_id == org_id,
                 JourneySegment.entered_at >= start,
                 JourneySegment.ended_at.isnot(None),
                 JourneySegment.staff_id.isnot(None)))
    if only_departments is not None:
        q = q.filter(JourneySegment.department_id.in_(only_departments or [-1]))
    rows = q.all()
    buckets: dict[int, list] = {}
    for r in rows:
        buckets.setdefault(r.staff_id, []).append(r.seconds)
    if not buckets:
        return []
    names = {u.id: u.name for u in db.session.query(User)
             .filter(User.id.in_(list(buckets))).all()}
    out = []
    for staff_id, seconds in buckets.items():
        stats = _summarise(seconds)
        stats.update({"staff_id": staff_id, "label": names.get(staff_id, "—")})
        out.append(stats)
    out.sort(key=lambda s: -s["count"])
    return out


# ------------------------------------------------------------------ live board
def live_board(org_id) -> list[dict]:
    """Who is standing where, right now, and for how long."""
    from .models import Patient, ReceptionIntake
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.ended_at.is_(None))
            .order_by(JourneySegment.entered_at.asc()).limit(300).all())
    now = now_naive()
    patients = {p.id: p for p in db.session.query(Patient)
                .filter(Patient.id.in_([r.patient_id for r in rows if r.patient_id] or [0])).all()}
    intakes = {i.id: i for i in db.session.query(ReceptionIntake)
               .filter(ReceptionIntake.id.in_([r.intake_id for r in rows if r.intake_id] or [0])).all()}
    out = []
    for r in rows:
        who = patients.get(r.patient_id) or intakes.get(r.intake_id)
        waited = max(0, int((now - r.entered_at).total_seconds() // 60))
        target = STAGE_TARGET_MINUTES.get(r.stage, 20)
        out.append({
            "segment": r,
            "name": who.full_name if who else "—",
            # Screens show register order (SURNAME First); the voice must use
            # the name a person is actually called, or the same patient gets
            # announced two different ways during one visit.
            "spoken": (getattr(who, "spoken_name", None) or
                       (who.full_name if who else "A patient")),
            "stage": r.stage,
            "label": r.label,
            "waited": waited,
            # Flagged, not hidden: a genuinely abandoned patient must be seen.
            "stuck": waited > target * 2,
            "abandoned": waited > SANITY_CAP_HOURS * 60,
        })
    out.sort(key=lambda x: -x["waited"])
    return out


# ------------------------------------------------------------------ headline
def headline(org_id, days: int = 7) -> dict:
    """The numbers the founder can put in front of a judge or a commissioner."""
    start, _ = _range(days)
    finished = (db.session.query(JourneySegment)
                .filter(JourneySegment.org_id == org_id,
                        JourneySegment.entered_at >= start,
                        JourneySegment.visit_id.isnot(None))
                .all())
    by_visit: dict[int, list] = {}
    for r in finished:
        by_visit.setdefault(r.visit_id, []).append(r)

    completed = []
    for segments in by_visit.values():
        if segments and all(s.ended_at for s in segments):
            completed.append(total_minutes(segments) * 60)

    stats = _summarise(completed)
    live = live_board(org_id)
    return {
        "days": days,
        "patients_completed": stats["count"],
        "average_journey": stats["average"],
        "median_journey": stats["median"],
        "longest_journey": stats["longest"],
        "reliable": stats["reliable"],
        "in_hospital_now": len(live),
        "stuck_now": len([x for x in live if x["stuck"]]),
    }


def trend(org_id, weeks: int = 4) -> list[dict]:
    """Week on week: is the hospital actually getting better?"""
    out = []
    today = now_naive().date()
    for w in range(weeks - 1, -1, -1):
        end = today - timedelta(days=7 * w)
        start = end - timedelta(days=6)
        rows = (db.session.query(JourneySegment)
                .filter(JourneySegment.org_id == org_id,
                        JourneySegment.entered_at >= datetime.combine(start, datetime.min.time()),
                        JourneySegment.entered_at <= datetime.combine(end, datetime.max.time()),
                        JourneySegment.visit_id.isnot(None)).all())
        by_visit: dict[int, list] = {}
        for r in rows:
            by_visit.setdefault(r.visit_id, []).append(r)
        completed = [total_minutes(v) * 60 for v in by_visit.values()
                     if v and all(s.ended_at for s in v)]
        stats = _summarise(completed)
        out.append({"week_ending": end, "patients": stats["count"],
                    "median": stats["median"], "average": stats["average"],
                    "reliable": stats["reliable"]})
    return out


# ------------------------------------------------------------------ prediction
def busiest_hours(org_id, days: int = 28) -> list[dict]:
    """When patients actually arrive — so staff can be rostered to match."""
    start, _ = _range(days)
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.stage == "RECEPTION",
                    JourneySegment.entered_at >= start).all())
    counts: dict[int, int] = {}
    for r in rows:
        counts[r.entered_at.hour] = counts.get(r.entered_at.hour, 0) + 1
    if not counts:
        return []
    busiest = max(counts.values())
    return [{"hour": h, "count": counts.get(h, 0),
             "share": round(counts.get(h, 0) / busiest * 100)}
            for h in range(7, 19)]


def suggest_allocation(org_id) -> list[str]:
    """Plain-English advice from the numbers. Advisory, never automatic.

    The founder asked the system to "learn to predict patient allocation to
    hospital personnel". This is that, deliberately kept as SUGGESTIONS a human
    reads and acts on — an app that silently moves patients between doctors
    would be trusted once and never again.
    """
    tips: list[str] = []
    live = live_board(org_id)

    stuck = [x for x in live if x["stuck"] and not x["abandoned"]]
    if stuck:
        worst = stuck[0]
        tips.append(
            f"{worst['name']} has been waiting {say_hm(worst['waited'])} at "
            f"{worst['label']}. Somebody should go and see why.")

    abandoned = [x for x in live if x["abandoned"]]
    if abandoned:
        tips.append(
            f"{len(abandoned)} patient(s) have been showing as waiting for over "
            f"{SANITY_CAP_HOURS} hours. They have probably gone home and the "
            f"desk forgot to tick them off — please close them.")

    # Where the crowd is right now
    by_stage: dict[str, int] = {}
    for x in live:
        by_stage[x["label"]] = by_stage.get(x["label"], 0) + 1
    for label, n in sorted(by_stage.items(), key=lambda kv: -kv[1])[:1]:
        if n >= 5:
            tips.append(f"{n} patients are queued at {label} right now — "
                        f"it is the tightest point in the hospital this minute.")

    # The slowest reliable stage over the week
    slow = [s for s in stage_performance(org_id, 7)
            if s["reliable"] and s["rating"] in ("SLOW", "HOLDING EVERYONE UP")]
    if slow:
        slow.sort(key=lambda s: -s["median"])
        worst = slow[0]
        tips.append(
            f"{worst['label']} takes {say_hm(worst['median'])} for a typical "
            f"patient this week — the slowest step in the journey. Adding one "
            f"person there would shorten every patient's visit.")

    # Fair doctor allocation, right now
    try:
        from . import triage
        sessions = triage.ready_doctors(org_id)
        load = triage.doctor_load(org_id)
        if len(sessions) >= 2:
            ranked = sorted(sessions, key=lambda s: load.get(s.doctor_id, 0))
            free, busy = ranked[0], ranked[-1]
            if load.get(busy.doctor_id, 0) - load.get(free.doctor_id, 0) >= 3:
                tips.append(
                    f"{busy.doctor.name} has {load.get(busy.doctor_id, 0)} waiting "
                    f"while {free.doctor.name} has {load.get(free.doctor_id, 0)}. "
                    f"Send the next patients to {free.doctor.name}.")
    except Exception:                                     # noqa: BLE001
        log.exception("allocation advice unavailable")

    if not tips:
        tips.append("Nothing needs your attention right now. The hospital is "
                    "flowing well.")
    return tips


# ------------------------------------------------------------------ journey time estimation (Feature #2)
# Premium++: tell a patient how long their whole visit will take.
# Uses real averages when available, otherwise targets.
# Fast-track patients get half the estimate (priority lane).
# Per-tenant, no EMR, safe fallback.

# Average minutes per destination for onward journey
ONWARD_TARGET_MINUTES = {
    "LABORATORY": 30, "PHARMACY": 20, "BILLING": 10, "MEGALEX": 10,
    "LAHSMA": 15, "EMERGENCY": 5,
}


def _avg_for_stage(org_id, stage_code: str, days: int = 14) -> int:
    """Real average for this stage if reliable, else target — delegates to smart estimator v2."""
    try:
        from . import queue_estimator as qe
        return qe.get_historical_avg(org_id, stage_code)
    except Exception:
        pass
    try:
        perf = stage_performance(org_id, days)
        for s in perf:
            if s["stage"] == stage_code and s.get("reliable") and s.get("median"):
                return int(s["median"])
    except Exception:
        pass
    return STAGE_TARGET_MINUTES.get(stage_code, 15)


def estimate_wait_minutes(org_id, *, stage: str, position: int = 0, is_fast_track: bool = False) -> int:
    """Smart adaptive wait — Little's Law + EMA + load factor + staff availability.

    Uses queue_estimator v2 if available — free AI-like logic, considers reception,
    billing, megalex, lahsma, hims, triage, doctor availability, onward.
    Falls back to simple calc for backward compat.
    """
    try:
        from . import queue_estimator as qe
        return qe.estimate_wait_minutes(org_id, stage, position=position, is_fast_track=is_fast_track)
    except Exception:
        pass
    base = _avg_for_stage(org_id, stage)
    per_patient = max(5, int(base * 0.7))
    estimated = position * per_patient + int(base * 0.3)
    if is_fast_track:
        estimated = max(1, estimated // 2)
    return estimated


def estimate_remaining_journey(org_id, visit) -> dict:
    """Smart remaining journey — uses queue_estimator v2 adaptive logic."""
    try:
        from . import queue_estimator as qe
        return qe.estimate_remaining_journey(org_id, visit)
    except Exception:
        pass
    # Fallback old logic
    stages = []
    total = 0
    status = getattr(visit, "status", "") or ""
    is_fast = bool(getattr(visit, "is_fast_track", False))
    if status in ("REGISTERED",):
        seq = ["TRIAGE", "WAIT_DOCTOR", "CONSULTATION"]
    elif status in ("TRIAGED",):
        seq = ["WAIT_DOCTOR", "CONSULTATION"]
    elif status in ("IN_CONSULTATION",):
        seq = ["CONSULTATION"]
    elif status in ("ONWARD",):
        try:
            pending = [s.destination for s in getattr(visit, "onward_steps", []) if getattr(s, "status", "") != "DONE"]
            for dest in pending:
                stage_map = {"LABORATORY": "LABORATORY", "PHARMACY": "PHARMACY",
                             "BILLING": "BILLING_OUT", "MEGALEX": "MEGALEX",
                             "LAHSMA": "LAHSMA", "EMERGENCY": "EMERGENCY"}
                sc = stage_map.get(dest, "PHARMACY")
                mins = ONWARD_TARGET_MINUTES.get(dest, 15)
                if is_fast:
                    mins = max(1, mins // 2)
                stages.append({"stage": sc, "label": JOURNEY_STAGE_LABELS.get(sc, dest), "minutes": mins})
                total += mins
            return {"total": total, "stages": stages, "fast_track": is_fast, "reason": getattr(visit, "fast_track_reason", None)}
        except Exception:
            seq = ["PHARMACY"]
    else:
        seq = []
    for sc in seq:
        mins = _avg_for_stage(org_id, sc)
        if sc == "WAIT_DOCTOR":
            try:
                from .triage import waiting as triage_waiting
                q = triage_waiting(org_id)
                pos = next((i for i, v in enumerate(q) if v.id == visit.id), 0)
                mins = estimate_wait_minutes(org_id, stage=sc, position=pos, is_fast_track=is_fast)
            except Exception:
                pass
        if is_fast:
            mins = max(1, mins // 2)
        stages.append({"stage": sc, "label": JOURNEY_STAGE_LABELS.get(sc, sc), "minutes": mins})
        total += mins
    if status in ("REGISTERED", "TRIAGED"):
        for extra in ["LABORATORY", "PHARMACY"]:
            mins = _avg_for_stage(org_id, extra)
            if is_fast:
                mins = max(1, mins // 2)
            stages.append({"stage": extra, "label": JOURNEY_STAGE_LABELS.get(extra, extra), "minutes": mins, "typical": True})
            total += mins
    return {"total": total, "stages": stages, "fast_track": is_fast, "reason": getattr(visit, "fast_track_reason", None)}


def estimate_intake_journey(org_id, intake) -> dict:
    """Smart intake journey — uses queue_estimator v2."""
    try:
        from . import queue_estimator as qe
        return qe.estimate_intake_journey(org_id, intake)
    except Exception:
        pass
    is_fast = bool(getattr(intake, "is_fast_track", False))
    reason = getattr(intake, "fast_track_reason", None)
    stage = getattr(intake, "stage", "RECEPTION")
    seq_map = {
        "RECEPTION": ["RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "LABORATORY", "PHARMACY"],
        "BILLING": ["BILLING", "PAYMENT", "HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "LABORATORY", "PHARMACY"],
        "PAYMENT": ["PAYMENT", "HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "LABORATORY", "PHARMACY"],
        "PAID": ["HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "LABORATORY", "PHARMACY"],
    }
    seq = seq_map.get(stage, ["RECEPTION", "BILLING", "PAYMENT", "HIMS", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION"])
    stages = []
    total = 0
    for sc in seq:
        mins = _avg_for_stage(org_id, sc)
        if is_fast:
            mins = max(1, mins // 2)
        stages.append({"stage": sc, "label": JOURNEY_STAGE_LABELS.get(sc, sc), "minutes": mins})
        total += mins
    return {"total": total, "stages": stages, "fast_track": is_fast, "reason": reason}


# ------------------------------------------------------------------ voice
# Voice is a standing requirement of every feature, and a dashboard nobody
# opens is a dashboard nobody acts on. But an alert that fires constantly gets
# ignored within a week, so this speaks about exactly two things: a patient who
# looks forgotten, and a department that is holding the whole hospital up.
def announce_forgotten(org_id) -> int:
    """Say out loud that somebody has been left waiting far too long."""
    said = 0
    for row in live_board(org_id):
        if not row["stuck"] or row["abandoned"]:
            continue                       # abandoned ones are a cleanup job
        announce.to_station(org_id, "patient_forgotten",
                            patient=announce.speech_name(row["spoken"]),
                            place=row["label"],
                            detail=say_hm(row["waited"]))
        said += 1
    return said


def announce_bottleneck(org_id, days: int = 1) -> int:
    """Say out loud which department is holding everyone up today."""
    slow = [s for s in stage_performance(org_id, days)
            if s["reliable"] and s["rating"] == "HOLDING EVERYONE UP"]
    if not slow:
        return 0
    slow.sort(key=lambda s: -s["median"])
    worst = slow[0]
    announce.to_station(
        org_id, "flow_bottleneck", place=worst["label"],
        detail=f"A typical patient waits {say_hm(worst['median'])} there, "
               f"against a target of "
               f"{say_hm(STAGE_TARGET_MINUTES.get(worst['stage'], 20))}.")
    return 1


# ------------------------------------------------------------------ cleanup
def close_abandoned(org_id, hours: int = SANITY_CAP_HOURS) -> int:
    """Close stretches nobody ever ticked off.

    WHY THIS IS NEEDED
    ------------------
    A desk gets busy and forgets to press "done". Without this, that patient
    stays on the live board forever, tomorrow's board fills with yesterday's
    ghosts, and the manager stops trusting the screen entirely — which is worse
    than having no screen at all.

    The row is CLOSED but its duration is left as None, so it is visibly
    "unknown" rather than a made-up number. Guessing a duration here would
    quietly corrupt every average in the system.
    """
    cutoff = now_naive() - timedelta(hours=hours)
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.ended_at.is_(None),
                    JourneySegment.entered_at < cutoff)
            .all())
    for row in rows:
        row.ended_at = now_naive()
        row.seconds = None                 # honestly unknown, never invented
    return len(rows)
