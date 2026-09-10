"""Staff clock-in geo-fence — per hospital, per site.

WHY THIS EXISTS
---------------
The roster says who is *supposed* to be on duty. This file answers a
different question: is this person actually standing at the hospital?

RULES
-----
* Settings are per tenant (and the pin is per site). Never an env var.
* Default mode is OFF. Turning it on is a human decision on Admin → Sites.
* If the fence is ON but the site has no pin, we never refuse the clock-in.
  A missing pin is our fault, not the nurse's.
* Distance is a straight-line (haversine) in metres.
* A phone can lie about its place. We mark cheats; we do not pretend the
  browser is a locked gate. A fake-place punch is refused when the fence
  is Required.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import services
from .models import (Branch, Department, RosterEntry, StaffAttendance, User,
                     db, now_naive)


EARTH_M = 6_371_000
DEFAULT_RADIUS = 200
MIN_RADIUS = 50
MAX_RADIUS = 2000
MODES = ("off", "optional", "required")
DEFAULT_GRACE = 60
HELP_REASONS = (
    ("LOST_PHONE", "Lost phone"),
    ("SPOILT_PHONE", "Spoilt / broken phone"),
    ("NO_NETWORK", "No internet on the phone"),
    ("ERRAND", "Official errand"),
    ("NO_GPS", "Phone has no place (GPS)"),
)
HELP_LABELS = dict(HELP_REASONS)
HELP_CODES = tuple(c for c, _ in HELP_REASONS)

# When each shift is supposed to start. Used for the one-hour grace.
SHIFT_START = {
    "DAY": (7, 0),
    "NIGHT": (19, 0),
    "24H": (7, 0),
    "OFFICE": (8, 0),
    "MORNING": (7, 0),
    "AFTERNOON": (14, 0),
}

# A person cannot jump more than this many metres in 10 minutes.
JUMP_LIMIT_M = 15_000


def metres_between(lat1, lng1, lat2, lng2) -> int:
    """Straight-line metres between two WGS84 points."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlmb = math.radians(float(lng2) - float(lng1))
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return int(round(2 * EARTH_M * math.asin(min(1.0, math.sqrt(a)))))


def parse_coord(raw, *, kind: str) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if kind == "lat" and -90 <= v <= 90:
        return v
    if kind == "lng" and -180 <= v <= 180:
        return v
    return None


def parse_radius(raw, default: int = DEFAULT_RADIUS) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(MIN_RADIUS, min(MAX_RADIUS, n))


def parse_grace(raw, default: int = DEFAULT_GRACE) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(0, min(240, n))


def parse_when(raw) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None)
    text = str(raw).strip().replace("Z", "")
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text[:26])
    except ValueError:
        return None


def as_bool(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Fence:
    lat: float | None
    lng: float | None
    radius_m: int
    mode: str
    place: str

    @property
    def pinned(self) -> bool:
        return self.lat is not None and self.lng is not None


def fence_for(org_id: int, branch: Branch | None) -> Fence:
    mode = services.get_setting(org_id, "attendance_mode") or "off"
    if mode not in MODES:
        mode = "off"
    default_r = parse_radius(services.get_setting(org_id, "attendance_radius_m"),
                             DEFAULT_RADIUS)
    lat = lng = None
    radius = default_r
    place = "the hospital"
    if branch is not None:
        place = branch.name
        if branch.lat is not None and branch.lng is not None:
            lat, lng = float(branch.lat), float(branch.lng)
        if branch.fence_meters:
            radius = parse_radius(branch.fence_meters, default_r)
    if lat is None:
        lat = parse_coord(services.get_setting(org_id, "attendance_lat"), kind="lat")
        lng = parse_coord(services.get_setting(org_id, "attendance_lng"), kind="lng")
        if lat is not None:
            place = "the hospital"
    return Fence(lat=lat, lng=lng, radius_m=radius, mode=mode, place=place)


def site_for(user: User) -> Branch | None:
    if getattr(user, "branch_id", None):
        b = db.session.get(Branch, user.branch_id)
        if b and b.org_id == user.org_id and b.active:
            return b
    return (db.session.query(Branch)
            .filter_by(org_id=user.org_id, is_main=True, active=True)
            .first())


def judge(fence: Fence, lat, lng, accuracy_m=None) -> dict:
    """Decide whether this phone is inside the circle.

    Returns a dict the views can show in plain English. Never raises.
    """
    out = {
        "ok": True,
        "inside": None,
        "distance_m": None,
        "reason": "",
        "lat": lat,
        "lng": lng,
        "accuracy_m": accuracy_m,
    }
    if fence.mode == "off":
        out["reason"] = "The gate check is switched off at this hospital."
        return out
    if lat is None or lng is None:
        if fence.mode == "required":
            out["ok"] = False
            out["reason"] = ("This hospital needs your phone's place to sign in. "
                             "Allow location, stand in the open, and try again.")
        else:
            out["reason"] = "No phone place was sent. Signed in without a pin."
        return out
    if not fence.pinned:
        out["reason"] = (f"No gate pin is set for {fence.place} yet, so anybody "
                         "who is signed in can clock in. Ask Admin to pin the gate.")
        return out
    dist = metres_between(lat, lng, fence.lat, fence.lng)
    out["distance_m"] = dist
    # A very fuzzy GPS reading is not proof of being outside.
    acc = int(accuracy_m) if isinstance(accuracy_m, (int, float)) and accuracy_m else 0
    if acc > fence.radius_m * 2 and fence.mode == "required":
        out["ok"] = False
        out["reason"] = ("Your phone is not sure where you are. Step outside, "
                         "wait a few seconds, and try again.")
        return out
    inside = dist <= fence.radius_m
    out["inside"] = inside
    if inside:
        out["reason"] = f"You are at {fence.place} ({dist} m from the gate)."
        return out
    out["reason"] = (f"You are about {dist} m from {fence.place}. "
                     f"The allowed circle is {fence.radius_m} m.")
    if fence.mode == "required":
        out["ok"] = False
    return out


def inspect_tamper(user: User, *, lat, lng, accuracy_m, mocked: bool,
                   client_at: datetime | None, now: datetime) -> tuple[list[str], str | None]:
    """Return (plain-English flags, hard-refuse reason or None)."""
    flags: list[str] = []
    refuse = None
    if mocked:
        flags.append("Phone reported a fake place.")
        refuse = ("Your phone is using a fake place. Stand at the gate with a "
                  "real phone, or ask your HOD to sign you in with a photo.")
    if accuracy_m is not None:
        try:
            acc = float(accuracy_m)
        except (TypeError, ValueError):
            acc = None
        if acc is not None and 0 < acc <= 1 and lat is not None:
            flags.append("Place is unnaturally exact.")
    if client_at is not None:
        drift = (now - client_at).total_seconds()
        if drift < -300:
            flags.append("Phone clock is ahead of the hospital clock.")
            refuse = refuse or ("Your phone clock is ahead. Set the time to "
                                "automatic and try again.")
        elif drift > 18 * 3600:
            flags.append("This tap sat on the phone more than 18 hours.")
            refuse = refuse or ("This tap is too old to trust. Sign in again now.")
        elif drift > 300:
            flags.append("Signed in after the phone was offline.")
    if lat is not None and lng is not None:
        last = (db.session.query(StaffAttendance)
                .filter(StaffAttendance.org_id == user.org_id,
                        StaffAttendance.user_id == user.id,
                        StaffAttendance.in_lat.isnot(None))
                .order_by(StaffAttendance.clock_in_at.desc())
                .first())
        if last is not None and last.in_lat is not None and last.in_lng is not None:
            minutes = (now - last.clock_in_at).total_seconds() / 60.0
            if 0 < minutes < 10:
                dist = metres_between(lat, lng, last.in_lat, last.in_lng)
                if dist > JUMP_LIMIT_M:
                    flags.append("Jumped too far too fast.")
                    refuse = ("This place cannot be reached that quickly. "
                              "Stand at the real gate, or ask your HOD with a photo.")
    return flags, refuse


def roster_start_at(user: User, day, now: datetime) -> datetime | None:
    """When this person's DUTY shift starts today. None if they are not rostered."""
    rows = (db.session.query(RosterEntry)
            .filter_by(org_id=user.org_id, user_id=user.id, duty_date=day, kind="DUTY")
            .all())
    if not rows:
        return None
    best = None
    for row in rows:
        hh, mm = SHIFT_START.get((row.shift or "DAY").upper(), (7, 0))
        start = datetime(day.year, day.month, day.day, hh, mm)
        if best is None or start < best:
            best = start
    return best


def grace_for(user: User, now: datetime | None = None) -> dict:
    now = now or now_naive()
    minutes = parse_grace(services.get_setting(user.org_id, "attendance_grace_minutes"),
                          DEFAULT_GRACE)
    start = roster_start_at(user, now.date(), now)
    if start is None:
        return {"late_minutes": None, "in_grace": False, "rostered": False,
                "grace_minutes": minutes}
    late = int((now - start).total_seconds() // 60)
    if late < 0:
        late = 0
    return {"late_minutes": late, "in_grace": late <= minutes, "rostered": True,
            "grace_minutes": minutes}


def supervise_dept_ids(helper: User) -> set[int] | None:
    """Departments this person may sign for. None = the whole hospital.

    v1.7.18 STRICT:
    - SUPER_ADMIN, HEAD_ADMIN_HR, MD_CEO, DMD, DCST: whole hospital (None)
    - HOD, APEX_NURSE: ONLY own Department/Section/Unit (ids = own + headed + extra grants)
    - ADMIN_MANAGER: ONLY when on duty TODAY (roster & day-on-duty) → whole hospital when on duty, else own dept only
    - STAFF: empty set (cannot sign co-staff) — view only roster, no attendance sign-in
    """
    if helper is None:
        return set()
    from .navigation import permissions_for
    from .roles import sees_whole_hospital, visible_department_ids

    role = getattr(helper, "role", "") or ""

    # SUPER_ADMIN always whole hospital
    if getattr(helper, "is_super", False):
        return None

    # ADMIN_MANAGER: only on-duty today gets whole hospital attendance_admin
    if role == "ADMIN_MANAGER":
        try:
            from .services import on_duty
            from .models import now_naive
            today = now_naive().date()
            duty = on_duty(helper.org_id, today)
            if duty and duty.id == helper.id:
                return None  # on duty → whole hospital
            # Not on duty → only own department (if any) for viewing, but not supervise others
            # Actually per rule, off-duty Admin Manager should NOT have attendance_admin
            # So return own dept only if they have it, but can_supervise will be limited
            # For safety, return empty set if not on duty (cannot sign others)
            # But allow them to see own dept board? We'll return own dept if exists
            if helper.department_id:
                return {helper.department_id}
            return set()
        except Exception:
            return set()

    can = permissions_for(helper)

    # HEAD_ADMIN_HR, MD_CEO, DMD, DCST have attendance_admin and whole hospital
    if role in ("HEAD_ADMIN_HR", "MD_CEO", "DMD", "DCST"):
        if can.get("attendance_admin") or sees_whole_hospital(helper):
            return None

    # SUPER_ADMIN already handled, but also check sees_whole_hospital for other management
    # For MD_CEO etc, we already returned None above, but keep for safety
    if sees_whole_hospital(helper) and role in ("MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR"):
        return None

    # HOD and APEX_NURSE: only own Dept/Section/Unit
    if role in ("HOD", "APEX_NURSE"):
        ids = set()
        if helper.department_id:
            ids.add(helper.department_id)
        for d in (db.session.query(Department)
                  .filter_by(org_id=helper.org_id, hod_user_id=helper.id).all()):
            ids.add(d.id)
        extra = visible_department_ids(helper)
        if extra:
            ids.update(extra)
        # Must have dept_manage or be HOD/APEX_NURSE to supervise own dept
        if can.get("dept_manage") or role in ("HOD", "APEX_NURSE"):
            return ids
        return set()

    # STAFF: never supervise (view/read only roster, no sign-in co-staff)
    if role == "STAFF":
        return set()

    # Others: if they have attendance_admin via custom role, allow whole hospital, else own dept
    if can.get("attendance_admin"):
        return None

    # Fallback: own department only if they have dept_manage, else nothing
    if can.get("dept_manage") and helper.department_id:
        return {helper.department_id}
    return set()


def can_supervise(helper: User) -> bool:
    """HOD, named head, department manager, or hospital admin."""
    ids = supervise_dept_ids(helper)
    return ids is None or bool(ids)


def can_help(helper: User, target: User) -> bool:
    """May this person sign a colleague in? Admin yes; HOD only own department.

    v1.7.18: STAFF cannot sign-in co-staff (view/read only roster). Only HOD/APEX_NURSE (own dept), HEAD_ADMIN_HR, ADMIN_MANAGER on duty, SUPER_ADMIN can.
    """
    if helper is None or target is None:
        return False
    if helper.org_id != target.org_id:
        return False
    if helper.id == target.id:
        return False
    # v1.7.18 explicit: STAFF never helps
    if getattr(helper, "role", "") == "STAFF":
        return False
    ids = supervise_dept_ids(helper)
    if ids is None:
        return True
    return bool(target.department_id and target.department_id in ids)


def helpable_staff(helper: User) -> list[User]:
    q = (db.session.query(User)
         .filter_by(org_id=helper.org_id, active=True, approved=True)
         .order_by(User.name))
    ids = supervise_dept_ids(helper)
    if ids is None:
        return [u for u in q.all() if u.id != helper.id]
    if not ids:
        return []
    return [u for u in q.filter(User.department_id.in_(ids)).all()
            if u.id != helper.id]


def save_gate(org_id: int, *, mode: str, lat, lng, radius_m, grace_minutes=None,
              branch: Branch | None = None) -> Fence:
    """Pin the circle. Per hospital (and the site you are standing at)."""
    mode = mode if mode in MODES else "off"
    radius = parse_radius(radius_m)
    pin_lat = parse_coord(lat, kind="lat")
    pin_lng = parse_coord(lng, kind="lng")
    services.set_setting(org_id, "attendance_mode", mode)
    services.set_setting(org_id, "attendance_radius_m", radius)
    services.set_setting(org_id, "attendance_lat", pin_lat)
    services.set_setting(org_id, "attendance_lng", pin_lng)
    if grace_minutes is not None:
        services.set_setting(org_id, "attendance_grace_minutes",
                             parse_grace(grace_minutes))
    if branch is None:
        from .branches import ensure_main_branch
        branch = ensure_main_branch(org_id)
    if branch is not None and branch.org_id == org_id:
        branch.lat = pin_lat
        branch.lng = pin_lng
        branch.fence_meters = radius
    return fence_for(org_id, branch)


def pending_reviews(viewer: User, day=None) -> list[StaffAttendance]:
    """Flagged punches this HOD / admin has not yet signed."""
    day = day or now_naive().date()
    q = (db.session.query(StaffAttendance)
         .filter_by(org_id=viewer.org_id, duty_date=day, flagged=True)
         .filter(StaffAttendance.reviewed_at.is_(None))
         .order_by(StaffAttendance.clock_in_at.asc()))
    rows = q.all()
    ids = supervise_dept_ids(viewer)
    if ids is None:
        return rows
    out = []
    for r in rows:
        person = r.user if getattr(r, "user", None) else db.session.get(User, r.user_id)
        if person and (person.department_id in ids or person.id == viewer.id):
            out.append(r)
    return out


def accept_review(viewer: User, row: StaffAttendance, note: str = "") -> bool:
    if row is None or row.org_id != viewer.org_id:
        return False
    if not can_supervise(viewer):
        return False
    person = row.user if getattr(row, "user", None) else db.session.get(User, row.user_id)
    ids = supervise_dept_ids(viewer)
    if ids is not None:
        if person is None:
            return False
        if person.department_id not in ids and person.id != viewer.id:
            return False
    row.reviewed_at = now_naive()
    row.reviewed_by_id = viewer.id
    row.review_note = (note or "Accepted by supervisor.")[:200]
    return True


def open_row(org_id: int, user_id: int) -> StaffAttendance | None:
    return (db.session.query(StaffAttendance)
            .filter_by(org_id=org_id, user_id=user_id, clock_out_at=None)
            .order_by(StaffAttendance.clock_in_at.desc())
            .first())


def clock_in(user: User, *, lat=None, lng=None, accuracy_m=None,
             device_info: str = "", override_reason: str = "",
             override_by: User | None = None,
             mocked: bool = False, client_at=None,
             help_reason: str | None = None,
             evidence_path: str | None = None,
             now: datetime | None = None) -> tuple[StaffAttendance | None, dict]:
    """Start today's attendance. Refuses a second open row for the same person."""
    existing = open_row(user.org_id, user.id)
    if existing is not None:
        return existing, {"ok": False, "already": True,
                          "reason": "You are already signed in. Sign out first if you are leaving."}
    now = now or now_naive()
    site = site_for(user)
    fence = fence_for(user.org_id, site)
    verdict = judge(fence, lat, lng, accuracy_m)
    helped = bool(override_reason and override_by is not None)
    if helped:
        verdict = {**verdict, "ok": True,
                   "reason": f"Accepted by {override_by.name}: {override_reason}"}
    flags, refuse = inspect_tamper(
        user, lat=lat, lng=lng, accuracy_m=accuracy_m,
        mocked=mocked, client_at=parse_when(client_at), now=now)
    # A helped punch is the honest way around a broken or fake phone.
    if refuse and not helped:
        if mocked and fence.mode == "required":
            return None, {"ok": False, "reason": refuse, "flags": flags}
        if "too old" in (refuse or "") or "ahead" in (refuse or "") or "quickly" in (refuse or ""):
            return None, {"ok": False, "reason": refuse, "flags": flags}
        if mocked:
            flags = flags or ["Phone reported a fake place."]
    if not helped and not verdict["ok"]:
        return None, {**verdict, "flags": flags}
    grace = grace_for(user, now)
    late = grace["late_minutes"]
    in_grace = bool(grace["in_grace"])
    if grace["rostered"] and late and late > grace["grace_minutes"]:
        flags.append(f"Late by {late} minutes (grace is {grace['grace_minutes']}).")
    note = "; ".join(flags)[:240] if flags else None
    row = StaffAttendance(
        org_id=user.org_id, branch_id=site.id if site else None, user_id=user.id,
        duty_date=now.date(), clock_in_at=now,
        in_lat=lat, in_lng=lng,
        in_accuracy_m=int(accuracy_m) if accuracy_m is not None else None,
        in_distance_m=verdict.get("distance_m"),
        in_inside=verdict.get("inside"),
        mode=fence.mode,
        override_reason=(override_reason or None),
        override_by_id=override_by.id if override_by else None,
        device_info=(device_info or "")[:200] or None,
        flagged=bool(flags),
        flag_note=note,
        mocked=bool(mocked),
        client_punched_at=parse_when(client_at),
        late_minutes=late,
        in_grace=in_grace,
        help_reason=(help_reason if help_reason in HELP_CODES else None),
        evidence_path=evidence_path,
    )
    db.session.add(row)
    db.session.flush()
    verdict["row_id"] = row.id
    verdict["already"] = False
    verdict["flags"] = flags
    verdict["late_minutes"] = late
    verdict["in_grace"] = in_grace
    if flags and verdict.get("ok"):
        verdict["reason"] = (verdict.get("reason") or "Signed in.") + " Marked for review."
    return row, verdict


def clock_out(user: User, *, lat=None, lng=None, accuracy_m=None,
              mocked: bool = False, client_at=None,
              now: datetime | None = None) -> tuple[StaffAttendance | None, dict]:
    row = open_row(user.org_id, user.id)
    if row is None:
        return None, {"ok": False, "reason": "You are not signed in."}
    site = db.session.get(Branch, row.branch_id) if row.branch_id else site_for(user)
    fence = fence_for(user.org_id, site)
    verdict = judge(fence, lat, lng, accuracy_m)
    # Leaving is always allowed — we record whether they were still inside.
    now = now or now_naive()
    row.clock_out_at = now
    row.out_lat = lat
    row.out_lng = lng
    row.out_accuracy_m = int(accuracy_m) if accuracy_m is not None else None
    row.out_distance_m = verdict.get("distance_m")
    row.out_inside = verdict.get("inside")
    if mocked and not row.mocked:
        row.mocked = True
        row.flagged = True
        extra = "Phone reported a fake place at sign-out."
        row.flag_note = ((row.flag_note + "; ") if row.flag_note else "") + extra
        row.flag_note = row.flag_note[:240]
    db.session.flush()
    verdict["ok"] = True
    verdict["reason"] = "You are signed out. Thank you."
    return row, verdict


def today_board(org_id: int, day=None, branch_id=None) -> list[StaffAttendance]:
    day = day or now_naive().date()
    q = (db.session.query(StaffAttendance)
         .filter_by(org_id=org_id, duty_date=day))
    if branch_id:
        q = q.filter_by(branch_id=branch_id)
    return q.order_by(StaffAttendance.clock_in_at.asc()).all()


def letter_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    if score >= 50:
        return "E"
    return "F"


def week_bounds(day=None):
    day = day or now_naive().date()
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    return start, end


def weekly_report(org_id: int, start=None, end=None) -> dict:
    """A–F ratings for one hospital week. Per person, then rolled up."""
    if start is None or end is None:
        start, end = week_bounds()
    people = (db.session.query(User)
              .filter_by(org_id=org_id, active=True, approved=True)
              .order_by(User.name).all())
    punches = (db.session.query(StaffAttendance)
               .filter(StaffAttendance.org_id == org_id,
                       StaffAttendance.duty_date >= start,
                       StaffAttendance.duty_date <= end).all())
    by_user: dict[int, list] = {}
    for p in punches:
        by_user.setdefault(p.user_id, []).append(p)
    roster = (db.session.query(RosterEntry)
              .filter(RosterEntry.org_id == org_id,
                      RosterEntry.duty_date >= start,
                      RosterEntry.duty_date <= end,
                      RosterEntry.kind == "DUTY").all())
    rostered: dict[int, set] = {}
    for r in roster:
        rostered.setdefault(r.user_id, set()).add(r.duty_date)

    staff_rows = []
    for u in people:
        days_on = rostered.get(u.id, set())
        rows = by_user.get(u.id, [])
        present_days = {p.duty_date for p in rows}
        expected = len(days_on) or max(1, len(present_days))
        present = len(present_days) if days_on else len(present_days)
        if days_on:
            present = len(days_on & present_days)
            absent = len(days_on - present_days)
        else:
            absent = 0
        late = sum(1 for p in rows if (p.late_minutes or 0) > 0 and not p.in_grace)
        flagged = sum(1 for p in rows if p.flagged or p.mocked)
        helped = sum(1 for p in rows if p.override_by_id)
        # Score: start 100. −15 absent day, −8 late, −12 flagged, −6 helped.
        score = 100.0
        score -= 15 * absent
        score -= 8 * late
        score -= 12 * flagged
        score -= 6 * helped
        if expected and present == 0 and days_on:
            score = min(score, 40)
        score = max(0.0, min(100.0, score))
        if not days_on and not rows:
            continue
        staff_rows.append({
            "user": u,
            "department": u.department.name if u.department else "—",
            "department_id": u.department_id,
            "expected": expected if days_on else present,
            "present": present if days_on else len(present_days),
            "absent": absent,
            "late": late,
            "flagged": flagged,
            "helped": helped,
            "score": round(score, 1),
            "grade": letter_grade(score),
        })

    def _roll(items, key_fn, name_fn):
        groups: dict = {}
        for row in items:
            k = key_fn(row)
            groups.setdefault(k, []).append(row)
        out = []
        for k, rows in groups.items():
            if not rows:
                continue
            avg = sum(r["score"] for r in rows) / len(rows)
            out.append({
                "name": name_fn(rows[0], k),
                "people": len(rows),
                "score": round(avg, 1),
                "grade": letter_grade(avg),
                "absent": sum(r["absent"] for r in rows),
                "late": sum(r["late"] for r in rows),
                "flagged": sum(r["flagged"] for r in rows),
            })
        out.sort(key=lambda r: (-r["score"], r["name"]))
        return out

    depts = _roll(staff_rows,
                  lambda r: r["department_id"] or 0,
                  lambda r, k: r["department"])
    hospital_avg = (sum(r["score"] for r in staff_rows) / len(staff_rows)
                    if staff_rows else 0.0)
    staff_rows.sort(key=lambda r: (-r["score"], r["user"].name))
    return {
        "start": start,
        "end": end,
        "staff": staff_rows,
        "departments": depts,
        "hospital": {
            "name": "Whole hospital",
            "people": len(staff_rows),
            "score": round(hospital_avg, 1),
            "grade": letter_grade(hospital_avg) if staff_rows else "—",
        },
    }
