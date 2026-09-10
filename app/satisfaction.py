"""How patients rated their visit — per hospital, never per-deploy.

WHY THIS FILE EXISTS
--------------------
The public page already collects 1–5 stars. This file turns those stars into
one honest picture a matron can read on a cheap phone: how we are doing,
which department is slipping, and which low scores still need a human.

Not a medical record. Stars and comments only. Never a diagnosis.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .models import Department, PatientFeedback, db, now_naive
from .roles import scope_note, visible_department_ids


PERIODS = (7, 30, 90)
DEFAULT_DAYS = 30

WORDS = (
    (4.5, "Excellent"),
    (4.0, "Good"),
    (3.0, "Fair"),
    (2.0, "Poor"),
    (0.0, "Critical"),
)


def word_for(avg) -> str:
    if avg is None:
        return "No ratings yet"
    for floor, label in WORDS:
        if avg >= floor:
            return label
    return "Critical"


def parse_days(raw) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return n if n in PERIODS else DEFAULT_DAYS


def _visible(user):
    q = db.session.query(PatientFeedback).filter_by(org_id=user.org_id)
    ids = visible_department_ids(user)
    if ids is not None:
        q = q.filter(PatientFeedback.department_id.in_(ids or [-1]))
    return q


def _avg(rows) -> float | None:
    if not rows:
        return None
    return round(sum(r.rating for r in rows) / len(rows), 1)


def _counts(rows) -> dict[int, int]:
    out = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in rows:
        if r.rating in out:
            out[r.rating] += 1
    return out


def dashboard(user, *, days: int = DEFAULT_DAYS, now: datetime | None = None) -> dict:
    """One picture of how patients rated this hospital (or this department)."""
    now = now or now_naive()
    days = days if days in PERIODS else DEFAULT_DAYS
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    q = _visible(user)
    current = q.filter(PatientFeedback.created_at >= start).all()
    previous = q.filter(PatientFeedback.created_at >= prev_start,
                        PatientFeedback.created_at < start).all()
    recent = (q.order_by(PatientFeedback.created_at.desc()).limit(40).all())

    avg = _avg(current)
    prev_avg = _avg(previous)
    trend = None
    if avg is not None and prev_avg is not None:
        trend = round(avg - prev_avg, 1)
    stars = _counts(current)
    total = len(current)
    happy = stars[4] + stars[5]
    low = stars[1] + stars[2]
    routed = sum(1 for r in current if r.status == "ROUTED")
    open_low = [r for r in current if r.rating <= 2 and r.status != "ROUTED"]

    by_dept: dict[int | None, list] = defaultdict(list)
    for r in current:
        by_dept[r.department_id].append(r)
    dept_rows = []
    for did, rows in by_dept.items():
        dept = rows[0].department if rows and rows[0].department else None
        a = _avg(rows)
        dept_rows.append({
            "id": did,
            "name": dept.name if dept else "No department picked",
            "n": len(rows),
            "avg": a,
            "word": word_for(a),
            "low": sum(1 for x in rows if x.rating <= 2),
            "happy": sum(1 for x in rows if x.rating >= 4),
        })
    dept_rows.sort(key=lambda r: ((r["avg"] if r["avg"] is not None else 99), r["name"]))

    day_bars = []
    for i in range(13, -1, -1):
        day = (now.date() - timedelta(days=i))
        day_rows = [r for r in current if r.created_at.date() == day]
        day_bars.append({
            "day": day,
            "n": len(day_rows),
            "avg": _avg(day_rows),
        })

    spoken = (
        f"Average satisfaction is {avg} out of 5 from {total} ratings."
        if avg is not None else
        "No patient ratings in this period yet."
    )
    if trend is not None and trend != 0:
        spoken += (" Up " if trend > 0 else " Down ") + f"{abs(trend)} from the period before."

    return {
        "days": days,
        "start": start.date(),
        "end": now.date(),
        "avg": avg,
        "word": word_for(avg),
        "prev_avg": prev_avg,
        "trend": trend,
        "total": total,
        "stars": stars,
        "happy": happy,
        "happy_pct": round(100 * happy / total) if total else 0,
        "low": low,
        "low_pct": round(100 * low / total) if total else 0,
        "routed": routed,
        "open_low": open_low,
        "departments": dept_rows,
        "recent": recent,
        "day_bars": day_bars,
        "scope": scope_note(user),
        "spoken": spoken,
    }


def csv_rows(user, *, days: int = DEFAULT_DAYS) -> tuple[list[str], list[list]]:
    now = now_naive()
    days = days if days in PERIODS else DEFAULT_DAYS
    start = now - timedelta(days=days)
    items = (_visible(user)
             .filter(PatientFeedback.created_at >= start)
             .order_by(PatientFeedback.created_at.desc())
             .limit(2000).all())
    header = ["When", "Stars", "Department", "Comment", "Sent to recovery", "Ticket"]
    rows = []
    for r in items:
        rows.append([
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            r.rating,
            r.department.name if r.department else "",
            (r.comment or "").replace("\n", " ")[:400],
            "yes" if r.status == "ROUTED" else "no",
            r.complaint.ref if r.complaint else "",
        ])
    return header, rows
