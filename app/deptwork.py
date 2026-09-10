"""The department's own desk — today's work, who is on it, and how we did.

WHAT THE FOUNDER ASKED FOR, IN HIS WORDS
----------------------------------------
  ii. "HOD and Staff should see only action and happening relating to their
       department/unit/Station only."
  ii. "Staff efficiency should be measure in relationship to patient flow to
       the department on daily bases."
  iii. "There should be provision for multiple staff to work simultaneously and
        also working on the same task or another task within the
        department/unit/Station."

Three things, one screen. A member of staff opens it and sees ONLY their own
department: the patients who came through today, who is on duty and what each
of them is currently doing, and an honest line about how the department is
handling the flow.

WHY EFFICIENCY IS MEASURED AGAINST FLOW, NOT AGAINST PEOPLE
-----------------------------------------------------------
The obvious thing to build is a league table: rank the staff by patients per
hour, put it on the wall. It is also the fastest way to ruin a hospital. The
person who takes the frightened elderly patient looks "slow"; the person who
rushes looks "efficient"; and within a month everybody has learned to rush.

So the measure here is always a RATIO of what arrived to what was handled:

    handled ÷ arrived, and how long the department held each patient

That answers the real question — "is this department keeping up with what is
walking through its door today?" — without ever implying that a slow morning
is one person's fault. Where an individual figure IS shown, it is labelled as
workload (how much they carried), never as a score.

FOUR HONESTY RULES
------------------
1. Fewer than MIN_SAMPLE patients is reported as "too early to say", never as
   a confident percentage. Three patients is an anecdote.
2. Open stretches are excluded from time averages. A patient still standing at
   the desk has no duration yet, and guessing one would flatter the figures.
3. A department that handled nobody is shown as "nothing came here today", not
   as 0%.
4. The median sits next to the average, because one forgotten patient at four
   hours drags an average to nonsense while the median stays truthful.

NOT AN EMR. Who was where, for how long, and who was on it. Never why.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from . import announce
from .models import (JourneySegment, User, WORK_KIND_LABELS, WorkClaim, db,
                     now_naive)

log = logging.getLogger(__name__)

# Below this many patients we say "too early to say" instead of a number
# somebody might act on.
MIN_SAMPLE = 5

# A claim left open this long was forgotten, not worked. Same reasoning as the
# tracking engine's sanity cap.
CLAIM_SANITY_HOURS = 12


def _today_bounds():
    today = now_naive().date()
    return (datetime.combine(today, datetime.min.time()),
            datetime.combine(today, datetime.max.time()))


# ================================================================ FLOW TO A DEPARTMENT
def flow_today(org_id: int, department_id: int) -> dict:
    """What arrived at this department today, and what it did with it."""
    start, end = _today_bounds()
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.department_id == department_id,
                    JourneySegment.entered_at >= start,
                    JourneySegment.entered_at <= end)
            .all())

    arrived = len(rows)
    handled = [r for r in rows if r.ended_at is not None and r.seconds is not None]
    still_here = [r for r in rows if r.ended_at is None]

    durations = sorted(r.seconds for r in handled)
    if durations:
        avg = round(sum(durations) / len(durations) / 60)
        mid = len(durations) // 2
        median = round((durations[mid] if len(durations) % 2
                        else (durations[mid - 1] + durations[mid]) / 2) / 60)
        longest = round(durations[-1] / 60)
    else:
        avg = median = longest = 0

    # The ratio that actually answers "are we keeping up?".
    completion = round(len(handled) / arrived * 100) if arrived else 0
    reliable = arrived >= MIN_SAMPLE

    return {
        "department_id": department_id,
        "arrived": arrived,
        "handled": len(handled),
        "still_here": len(still_here),
        "completion": completion,
        "average_minutes": avg,
        "median_minutes": median,
        "longest_minutes": longest,
        "reliable": reliable,
        "verdict": _verdict(arrived, len(handled), median, reliable),
    }


def _verdict(arrived: int, handled: int, median: int, reliable: bool) -> str:
    """A sentence, not a score. Written to be read by a worried human."""
    if arrived == 0:
        return "Nothing has come to this department today yet."
    if not reliable:
        return (f"Only {arrived} patient(s) so far today — too early to say "
                f"how the department is doing.")
    waiting = arrived - handled
    if waiting == 0:
        return (f"Everybody who came here today has been dealt with. "
                f"A typical patient took {median} minutes.")
    if waiting >= handled and waiting >= 5:
        return (f"{waiting} of {arrived} patients are still waiting here. "
                f"This department is falling behind the flow coming in.")
    if waiting >= 3:
        return (f"{handled} of {arrived} handled, {waiting} still waiting. "
                f"Keeping up, but only just.")
    return (f"{handled} of {arrived} handled — the department is keeping up. "
            f"A typical patient took {median} minutes.")


def staff_effort_today(org_id: int, department_id: int) -> list[dict]:
    """How much each person carried today. WORKLOAD, never a league table.

    Deliberately sorted by name, not by output. Sorting by output turns a list
    into a ranking whether you label it one or not, and the person at the
    bottom is usually the one who took the hardest cases.
    """
    start, end = _today_bounds()
    rows = (db.session.query(JourneySegment)
            .filter(JourneySegment.org_id == org_id,
                    JourneySegment.department_id == department_id,
                    JourneySegment.entered_at >= start,
                    JourneySegment.entered_at <= end,
                    JourneySegment.staff_id.isnot(None))
            .all())
    claims = (db.session.query(WorkClaim)
              .filter(WorkClaim.org_id == org_id,
                      WorkClaim.department_id == department_id,
                      WorkClaim.started_at >= start,
                      WorkClaim.started_at <= end)
              .all())

    buckets: dict[int, dict] = {}
    for r in rows:
        b = buckets.setdefault(r.staff_id, {"patients": 0, "seconds": [], "tasks": 0})
        b["patients"] += 1
        if r.seconds is not None:
            b["seconds"].append(r.seconds)
    for c in claims:
        b = buckets.setdefault(c.user_id, {"patients": 0, "seconds": [], "tasks": 0})
        b["tasks"] += 1

    if not buckets:
        return []
    names = {u.id: u.name for u in db.session.query(User)
             .filter(User.id.in_(list(buckets))).all()}
    out = []
    for uid, b in buckets.items():
        secs = b["seconds"]
        out.append({
            "staff_id": uid,
            "name": names.get(uid, "—"),
            "patients": b["patients"],
            "tasks": b["tasks"],
            "average_minutes": round(sum(secs) / len(secs) / 60) if secs else 0,
            # Honest about what we cannot say from three data points.
            "reliable": len(secs) >= MIN_SAMPLE,
        })
    out.sort(key=lambda s: s["name"])
    return out


# ================================================================ TEAMWORK
def open_claims(org_id: int, department_id: int | None = None) -> list[WorkClaim]:
    """Everything being worked on right now, in this department."""
    q = (db.session.query(WorkClaim)
         .filter(WorkClaim.org_id == org_id, WorkClaim.ended_at.is_(None)))
    if department_id is not None:
        q = q.filter(WorkClaim.department_id == department_id)
    return q.order_by(WorkClaim.started_at.asc()).limit(200).all()


def who_else_is_on(org_id: int, kind: str, entity_type=None, entity_id=None,
                   exclude_user_id=None) -> list[WorkClaim]:
    """Who ELSE is already on this exact task. The anti-duplication signal."""
    q = (db.session.query(WorkClaim)
         .filter(WorkClaim.org_id == org_id, WorkClaim.kind == kind,
                 WorkClaim.ended_at.is_(None)))
    if entity_type is not None:
        q = q.filter(WorkClaim.entity_type == entity_type,
                     WorkClaim.entity_id == entity_id)
    else:
        q = q.filter(WorkClaim.entity_type.is_(None))
    if exclude_user_id is not None:
        q = q.filter(WorkClaim.user_id != exclude_user_id)
    return q.order_by(WorkClaim.started_at.asc()).all()


def claim(org_id: int, user, kind: str, *, department_id=None, unit_id=None,
          entity_type=None, entity_id=None, note=None) -> tuple[WorkClaim, list]:
    """Put your name on a piece of work. Returns (your claim, who else is on it).

    NEVER AN EXCLUSIVE LOCK. Anybody may join anything, because in a real
    hospital two porters do move one trolley and three nurses do clear one
    queue together. Refusing the second person would be software telling a
    ward how to nurse.

    The one thing refused is the SAME person claiming the SAME task twice —
    that is a double-tap on a phone, not a second worker, and letting it
    through would double-count their effort in every figure on the screen.
    """
    if kind not in WORK_KIND_LABELS:
        kind = "OTHER"
    if department_id is None:
        department_id = getattr(user, "department_id", None)

    mine = (db.session.query(WorkClaim)
            .filter(WorkClaim.org_id == org_id, WorkClaim.user_id == user.id,
                    WorkClaim.kind == kind, WorkClaim.entity_type == entity_type,
                    WorkClaim.entity_id == entity_id,
                    WorkClaim.ended_at.is_(None)).first())
    if mine is not None:
        return mine, who_else_is_on(org_id, kind, entity_type, entity_id, user.id)

    row = WorkClaim(org_id=org_id, department_id=department_id, unit_id=unit_id,
                    user_id=user.id, kind=kind, entity_type=entity_type,
                    entity_id=entity_id, note=(note or "")[:200] or None)
    db.session.add(row)
    db.session.flush()
    others = who_else_is_on(org_id, kind, entity_type, entity_id, user.id)

    # Tell the people already on it that somebody has joined — voice is a
    # standing requirement, and silent help is help nobody knows they have.
    for other in others:
        try:
            # to_user() supplies `name` itself (the person being spoken TO),
            # so passing it here is a TypeError that silently swallows every
            # announcement. Caught the first time this was exercised.
            announce.to_user(org_id, other.user, "colleague_joined",
                             patient=announce.speech_name(user.name),
                             place=WORK_KIND_LABELS.get(kind, "this task"))
        except Exception:                                  # noqa: BLE001
            log.exception("could not announce a colleague joining")
    return row, others


def release(claim_row: WorkClaim) -> WorkClaim:
    """Step off a task. Records how long you were on it."""
    if claim_row.ended_at is None:
        claim_row.ended_at = now_naive()
        claim_row.seconds = max(
            0, int((claim_row.ended_at - claim_row.started_at).total_seconds()))
    return claim_row


def my_open_claims(org_id: int, user_id: int) -> list[WorkClaim]:
    return (db.session.query(WorkClaim)
            .filter(WorkClaim.org_id == org_id, WorkClaim.user_id == user_id,
                    WorkClaim.ended_at.is_(None))
            .order_by(WorkClaim.started_at.asc()).all())


def close_forgotten_claims(org_id: int, hours: int = CLAIM_SANITY_HOURS) -> int:
    """Close claims nobody ever stepped off.

    Somebody goes home without pressing "done" and the board shows them still
    working at 3am. Left alone, tomorrow's board fills with yesterday's ghosts
    and staff stop trusting the screen — which is worse than having no screen.

    The row is closed but its duration is left as None: honestly unknown,
    never invented. Guessing would quietly corrupt every average here.
    """
    cutoff = now_naive() - timedelta(hours=hours)
    rows = (db.session.query(WorkClaim)
            .filter(WorkClaim.org_id == org_id, WorkClaim.ended_at.is_(None),
                    WorkClaim.started_at < cutoff).all())
    for r in rows:
        r.ended_at = now_naive()
        r.seconds = None
    return len(rows)
