"""ONE Roster page for the whole hospital.

Replaces the two pages that used to exist — "Duty Roster" (one Admin Manager
per day) and "Dept Roster" (a department, a shift, two staff columns). Both are
now views of the same screen at ``/roster``:

  * pick a date range (a day, 7 days, 2 weeks, 3 weeks, a month, or your own);
  * pick who owns the roster (Admin Manager, or a department / section / unit);
  * add people one at a time, or upload a file;
  * record leave in the same place, so the roster refuses to put somebody on
    duty while they are on leave.

``/dept-roster`` still answers — it redirects here, so old bookmarks, printed
notes and the phone home-screen shortcut all keep working.
"""
from __future__ import annotations

from datetime import timedelta

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from .. import rosterdata as rd
from ..audit import audit
from ..models import (DEPT_SHIFTS, LEAVE_TYPES, ROSTER_MODE_LABELS, SCOPE_LABELS,
                      Department, DutyRoster, RosterEntry, Section, Unit, User,
                      db, now_naive)
from ..security import require_role

bp = Blueprint("roster", __name__)

VIEWERS = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR",
           "ADMIN_MANAGER", "HOD", "STAFF")
# v1.7.18: HOD and APEX_NURSE can create/edit/delete/upload roster for their own dept only (via can_manage)
# STAFF is VIEW only (read-only), never editor
# ADMIN_MANAGER can edit ORG roster only when on duty TODAY (checked in can_manage)
EDITORS = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "HOD", "APEX_NURSE", "ADMIN_MANAGER")


# ------------------------------------------------------------------ helpers
def _org_admin_managers(org_id: int) -> list[User]:
    return (db.session.query(User)
            .filter(User.org_id == org_id, User.role.in_(("ADMIN_MANAGER", "SUPER_ADMIN")),
                    User.active.is_(True)).order_by(User.name).all())


def _place_from_request(form=None) -> tuple[dict, list[str]]:
    src = form if form is not None else request.args
    return rd.resolve_scope(
        current_user.org_id,
        src.get("scope") or "ORG",
        src.get("department_id", type=int),
        src.get("section_id", type=int),
        src.get("unit_id", type=int),
    )


def _mode_for(place: dict) -> str:
    # The Admin Manager roster is not a shift pattern — the hospital runs every
    # day, including weekends, and there is exactly one manager on duty.
    if place.get("scope") == "ORG" or not place.get("department_id"):
        return "org"
    dept = db.session.get(Department, place["department_id"])
    return (dept.roster_mode if dept else None) or "two_12h"


def _require_edit(place: dict):
    if not rd.can_manage(current_user, place):
        abort(403)


def _back(place: dict, **extra) -> str:
    args = {"scope": place.get("scope") or "ORG", **extra}
    for k in ("department_id", "section_id", "unit_id"):
        if place.get(k):
            args[k] = place[k]
    return url_for("roster.roster_view", **args)


# ------------------------------------------------------------------ the page
@bp.get("/roster")
@require_role(*VIEWERS)
def roster_view():
    org_id = current_user.org_id
    start, end, range_label = rd.resolve_range(
        request.args.get("range", "7"), request.args.get("from", ""),
        request.args.get("to", ""))

    place, scope_errors = _place_from_request()
    if scope_errors:                       # nothing chosen yet, or an invalid pick
        place = {"scope": "ORG", "department_id": None, "section_id": None, "unit_id": None}

    depts = rd.visible_departments(current_user)
    # An HOD has no business seeing the hospital-wide Admin Manager roster page
    # as their default; drop them straight into their own department.
    if place["scope"] == "ORG" and not current_user.is_super and depts and \
            getattr(current_user, "role", "") == "HOD":
        place = {"scope": "DEPARTMENT", "department_id": depts[0].id,
                 "section_id": None, "unit_id": None}

    sections = units = []
    if place.get("department_id"):
        sections = (db.session.query(Section)
                    .filter_by(org_id=org_id, department_id=place["department_id"])
                    .order_by(Section.name).all())
    if place.get("section_id"):
        units = (db.session.query(Unit).filter_by(org_id=org_id, section_id=place["section_id"])
                 .order_by(Unit.name).all())

    mode = _mode_for(place)
    shifts = [("ADMIN", "whole day")] if mode == "org" else rd.shifts_for(mode)
    entries = rd.load_roster(org_id, start, end, place=place)

    # group by day so the page reads like a real duty sheet
    by_day = []
    for d in rd.days_between(start, end):
        rows = [e for e in entries if e["date"] == d]
        by_day.append({
            "date": d,
            "weekend": d.weekday() in rd.WEEKEND,
            "today": d == now_naive().date(),
            "duty": [r for r in rows if r["kind"] == "DUTY"],
            "leave": [r for r in rows if r["kind"] == "LEAVE"],
        })

    staff = (db.session.query(User).filter_by(org_id=org_id, active=True)
             .order_by(User.name).all())
    # "Days with nobody on duty" only means something once the roster has been
    # started. Counting 30 empty days on a blank page is noise, and an office
    # department is SUPPOSED to be empty at the weekend.
    working = [d for d in by_day if not (mode == "office" and d["weekend"])]
    gaps = [d for d in working if not d["duty"]] if any(d["duty"] for d in by_day) else []

    return render_template(
        "roster.html",
        start=start, end=end, range_label=range_label,
        range_key=request.args.get("range", "7"),
        presets=rd.RANGE_PRESETS, by_day=by_day, entries=entries,
        place=place, place_label=_place_label(place), scope_labels=SCOPE_LABELS, depts=depts, sections=sections, units=units,
        mode=mode, mode_label=ROSTER_MODE_LABELS.get(mode, "Admin Manager, one per day"),
        shifts=shifts, all_modes=ROSTER_MODE_LABELS,
        leave_types=LEAVE_TYPES, staff=staff, admins=_org_admin_managers(org_id),
        can_edit=rd.can_manage(current_user, place),
        duty_count=len([e for e in entries if e["kind"] == "DUTY"]),
        leave_count=len([e for e in entries if e["kind"] == "LEAVE"]),
        gap_count=len(gaps), nominal_hint=rd.NOMINAL_HINT,
        dept_shifts=DEPT_SHIFTS,
    )


@bp.get("/dept-roster")
@require_role(*VIEWERS)
def dept_roster_redirect():
    """The old department roster address — kept alive so bookmarks still work."""
    dept = request.args.get("dept", type=int)
    if dept:
        return redirect(url_for("roster.roster_view", scope="DEPARTMENT", department_id=dept))
    return redirect(url_for("roster.roster_view"))


# ------------------------------------------------------------------ add one person
@bp.post("/roster/add")
@require_role(*EDITORS)
def roster_add():
    place, errors = _place_from_request(request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("roster.roster_view"))
    _require_edit(place)

    mode = _mode_for(place)
    day = rd.parse_date(request.form.get("duty_date", ""))
    end = rd.parse_date(request.form.get("end_date", "")) or day
    user_id = request.form.get("user_id", type=int)
    person = db.session.get(User, user_id) if user_id else None
    kind = "LEAVE" if (request.form.get("kind") or "DUTY").upper() == "LEAVE" else "DUTY"
    shift = (request.form.get("shift") or "").strip().upper()
    leave_type = rd.normalise_leave(request.form.get("leave_type") or "")
    note = (request.form.get("note") or "").strip()[:200]

    problems = []
    if not day:
        problems.append("Choose a valid date.")
    if not person or person.org_id != current_user.org_id or not person.active:
        problems.append("Choose a member of staff.")
    if end and day and end < day:
        problems.append("The end date cannot be before the start date.")
    if day and end and (end - day).days > 120:
        problems.append("That block is longer than 120 days — split it up.")
    if kind == "DUTY":
        if place["scope"] != "ORG" and shift not in rd.shift_codes(mode):
            problems.append(f"Choose a shift: {', '.join(rd.shift_codes(mode))}.")
    elif not leave_type:
        problems.append("Choose the type of leave.")
    if problems:
        for p in problems:
            flash(p, "error")
        return redirect(_back(place))

    added = skipped = 0
    for d in rd.days_between(day, end):
        if kind == "DUTY":
            v = rd.office_mode_violation(mode, d) if place["scope"] != "ORG" else None
            if v:
                flash(v, "error")
                return redirect(_back(place))
            clash = rd.leave_on(current_user.org_id, person.id, d)
            if clash:
                flash(f"{person.name} is on {clash.display_shift.lower()} on "
                      f"{d.strftime('%a %d %b')} — they cannot be placed on duty that day.",
                      "error")
                return redirect(_back(place))
            if place["scope"] == "ORG":
                if db.session.query(DutyRoster).filter_by(org_id=current_user.org_id,
                                                          duty_date=d).first():
                    flash(f"{d.strftime('%a %d %b')} already has an Admin Manager on duty. "
                          "Reassign or delete that entry first — duplicates are not allowed.",
                          "error")
                    return redirect(_back(place))
                db.session.add(DutyRoster(org_id=current_user.org_id, duty_date=d,
                                          user_id=person.id, source="manual", note=note or None,
                                          created_by=current_user.id))
                added += 1
                continue
            dup = (db.session.query(RosterEntry)
                   .filter_by(org_id=current_user.org_id, duty_date=d, user_id=person.id,
                              shift=shift, scope=place["scope"],
                              department_id=place.get("department_id"),
                              section_id=place.get("section_id"),
                              unit_id=place.get("unit_id")).first())
            if dup:
                skipped += 1
                continue
            db.session.add(RosterEntry(
                org_id=current_user.org_id, duty_date=d, user_id=person.id, kind="DUTY",
                shift=shift, scope=place["scope"], department_id=place.get("department_id"),
                section_id=place.get("section_id"), unit_id=place.get("unit_id"),
                note=note or None, source="manual", created_by=current_user.id))
            added += 1
        else:
            if rd.leave_on(current_user.org_id, person.id, d):
                skipped += 1
                continue
            # Roster audit: refuse to also put somebody on leave on a day they
            # are already rostered for duty — the reverse direction is refused
            # too. Say where, so the HOD can remove the duty entry explicitly.
            duty = (db.session.query(RosterEntry)
                    .filter_by(org_id=current_user.org_id, user_id=person.id,
                               duty_date=d, kind="DUTY").first())
            if duty:
                flash(f"{person.name} is already on duty ({duty.display_shift} at "
                      f"{duty.place_label}) on {d.strftime('%a %d %b')} — remove that "
                      "duty entry first if they should be on leave that day. Nothing was saved.",
                      "error")
                return redirect(_back(place))
            db.session.add(RosterEntry(
                org_id=current_user.org_id, duty_date=d, user_id=person.id, kind="LEAVE",
                shift="LEAVE", leave_type=leave_type, scope=place["scope"],
                department_id=place.get("department_id"), section_id=place.get("section_id"),
                unit_id=place.get("unit_id"), note=note or None, source="manual",
                created_by=current_user.id))
            added += 1

    audit("ROSTER_ADD", "roster", None,
          {"who": person.name, "kind": kind, "from": str(day), "to": str(end),
           "shift": shift or leave_type, "place": place})
    db.session.commit()
    if added:
        word = "leave day" if kind == "LEAVE" else "duty"
        flash(f"{added} {word}{'s' if added != 1 else ''} added for {person.name}."
              + (f" {skipped} already existed and were skipped." if skipped else ""), "success")
    else:
        flash("Nothing to add — those entries already exist.", "info")
    return redirect(_back(place))


@bp.post("/roster/entry/<int:rid>/delete")
@require_role(*EDITORS)
def roster_entry_delete(rid: int):
    r = db.session.get(RosterEntry, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    place = {"scope": r.scope, "department_id": r.department_id,
             "section_id": r.section_id, "unit_id": r.unit_id}
    _require_edit(place)
    audit("ROSTER_ENTRY_DELETED", "roster", rid,
          {"date": str(r.duty_date), "who": r.user.name if r.user else "?",
           "shift": r.shift, "kind": r.kind})
    db.session.delete(r)
    db.session.commit()
    flash("Roster entry removed.", "success")
    return redirect(_back(place))


# ------------------------------------------------------------------ Admin Manager rows
@bp.post("/roster/manual")
@require_role("SUPER_ADMIN", "HEAD_ADMIN_HR")
def roster_manual():
    """Add one Admin Manager duty day (the hospital-wide roster)."""
    d = rd.parse_date(request.form.get("date", ""))
    user = db.session.get(User, request.form.get("user_id", type=int) or 0)
    note = (request.form.get("note") or "").strip()
    if not d:
        flash("Please provide a valid duty date.", "error")
        return redirect(url_for("roster.roster_view"))
    if not user or user.org_id != current_user.org_id or \
            user.role not in ("ADMIN_MANAGER", "SUPER_ADMIN"):
        flash("Please select a valid Admin Manager.", "error")
        return redirect(url_for("roster.roster_view"))
    existing = db.session.query(DutyRoster).filter_by(org_id=current_user.org_id,
                                                      duty_date=d).first()
    if existing:
        flash(f"A roster entry already exists for {d} ({existing.user.name}). "
              "Edit or delete it first — duplicates are not allowed.", "error")
        return redirect(url_for("roster.roster_view"))
    clash = rd.leave_on(current_user.org_id, user.id, d)
    if clash:
        flash(f"{user.name} is on {clash.display_shift.lower()} on {d} — "
              "they cannot be the Admin Manager on duty that day.", "error")
        return redirect(url_for("roster.roster_view"))
    db.session.add(DutyRoster(org_id=current_user.org_id, duty_date=d, user_id=user.id,
                              source="manual", note=note, created_by=current_user.id))
    audit("ROSTER_MANUAL_ADD", "roster", None, {"date": str(d), "user": user.name})
    db.session.commit()
    flash(f"Roster entry added for {d} — {user.name}.", "success")
    return redirect(url_for("roster.roster_view"))


@bp.post("/roster/<int:rid>/delete")
@require_role("SUPER_ADMIN", "HEAD_ADMIN_HR")
def roster_delete(rid: int):
    r = db.session.get(DutyRoster, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    audit("ROSTER_DELETED", "roster", r.id, {"date": str(r.duty_date), "user": r.user.name})
    db.session.delete(r)
    db.session.commit()
    flash("Roster entry deleted.", "success")
    return redirect(url_for("roster.roster_view"))


@bp.post("/roster/<int:rid>/reassign")
@require_role("SUPER_ADMIN", "HEAD_ADMIN_HR")
def roster_reassign(rid: int):
    r = db.session.get(DutyRoster, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    user = db.session.get(User, request.form.get("user_id", type=int) or 0)
    if not user or user.org_id != current_user.org_id or \
            user.role not in ("ADMIN_MANAGER", "SUPER_ADMIN"):
        flash("Select a valid Admin Manager.", "error")
        return redirect(url_for("roster.roster_view"))
    clash = rd.leave_on(current_user.org_id, user.id, r.duty_date)
    if clash:
        flash(f"{user.name} is on {clash.display_shift.lower()} on {r.duty_date}.", "error")
        return redirect(url_for("roster.roster_view"))
    old = r.user.name
    r.user_id = user.id
    audit("ROSTER_REASSIGNED", "roster", r.id,
          {"date": str(r.duty_date), "old": old, "new": user.name})
    db.session.commit()
    flash(f"Duty on {r.duty_date} reassigned to {user.name}.", "success")
    return redirect(url_for("roster.roster_view"))


# ------------------------------------------------------------------ upload
@bp.get("/roster/template")
@require_role(*VIEWERS)
def roster_template():
    mode = request.args.get("mode", "two_12h")
    if mode not in DEPT_SHIFTS:
        mode = "two_12h"
    return Response(rd.template_csv(mode), mimetype="text/csv",
                    headers={"Content-Disposition":
                             f"attachment; filename=roster-template-{mode}.csv"})


@bp.post("/roster/upload")
@require_role(*EDITORS)
def roster_upload():
    """Parse and CHECK an uploaded roster. Writes nothing — shows a preview."""
    place, errors = _place_from_request(request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("roster.roster_view"))
    _require_edit(place)

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please choose a .csv or .xlsx file to upload.", "error")
        return redirect(_back(place))

    raw_rows, err = rd.parse_file(file)
    if err:
        flash(err, "error")
        return redirect(_back(place))
    if not raw_rows:
        flash("That file has a header row but no staff on it.", "error")
        return redirect(_back(place))

    mode = _mode_for(place)
    preview = rd.build_preview(current_user.org_id, raw_rows, place=place, mode=mode)
    meta = {"place": place, "mode": mode, "filename": file.filename}
    token = rd.save_preview(current_user.org_id, preview, meta)

    ok = [r for r in preview if r["ok"]]
    return render_template("roster_upload_preview.html", rows=preview, token=token,
                           place=place, mode=mode,
                           mode_label=ROSTER_MODE_LABELS.get(mode, mode),
                           place_label=_place_label(place), filename=file.filename,
                           valid_count=len(ok), error_count=len(preview) - len(ok),
                           day_count=sum(r["days"] for r in ok),
                           leave_count=len([r for r in ok if r["kind"] == "LEAVE"]))


@bp.post("/roster/upload/confirm")
@require_role(*EDITORS)
def roster_upload_confirm():
    token = (request.form.get("token") or "").strip()
    rows, meta = rd.load_preview(current_user.org_id, token)
    if not rows:
        flash("That preview has expired or was already used. Please upload the file again.",
              "error")
        return redirect(url_for("roster.roster_view"))
    place = (meta or {}).get("place") or {"scope": "ORG"}
    _require_edit(place)
    result = rd.commit_rows(current_user.org_id, rows, place=place,
                            created_by_id=current_user.id)
    audit("ROSTER_IMPORTED", "roster", None,
          {"added": result["added"], "skipped": result["skipped"],
           "file": (meta or {}).get("filename"), "place": place})
    db.session.commit()
    rd.discard_preview(current_user.org_id, token)
    flash(f"Roster uploaded: {result['added']} day(s) saved, "
          f"{result['skipped']} skipped.", "success")
    return redirect(_back(place))


@bp.post("/roster/upload/discard")
@require_role(*EDITORS)
def roster_upload_discard():
    token = (request.form.get("token") or "").strip()
    rd.discard_preview(current_user.org_id, token)
    flash("Upload cancelled — nothing was saved.", "info")
    return redirect(url_for("roster.roster_view"))


def _place_label(place: dict) -> str:
    if place.get("scope") == "ORG":
        return "Admin Manager (hospital-wide)"
    bits = []
    d = db.session.get(Department, place["department_id"]) if place.get("department_id") else None
    if d:
        bits.append(d.name)
    s = db.session.get(Section, place["section_id"]) if place.get("section_id") else None
    if s:
        bits.append(s.name)
    u = db.session.get(Unit, place["unit_id"]) if place.get("unit_id") else None
    if u:
        bits.append(u.name)
    return " › ".join(bits) or "—"



# ------------------------------------------------------------------ leave requests (approval workflow)
@bp.get("/roster/leave")
@require_role(*VIEWERS)
def leave_list():
    """My leave requests + pending approvals for HOD/HR."""
    from ..models import LeaveRequest, LeaveBalance, now_naive
    org_id = current_user.org_id
    # My requests — resilient if table not yet migrated (avoid 500)
    try:
        my_reqs = (db.session.query(LeaveRequest)
                   .filter_by(org_id=org_id, user_id=current_user.id)
                   .order_by(LeaveRequest.requested_at.desc()).limit(100).all())
    except Exception:
        my_reqs = []
        db.session.rollback()
    pending = []
    try:
        if current_user.role in ("HOD", "HEAD_ADMIN_HR", "SUPER_ADMIN", "ADMIN_MANAGER") or getattr(current_user, "is_super", False):
            q = db.session.query(LeaveRequest).filter_by(org_id=org_id, status="PENDING")
            pending = q.order_by(LeaveRequest.requested_at.asc()).limit(100).all()
    except Exception:
        pending = []
        db.session.rollback()
    try:
        year = now_naive().date().year
        balances = (db.session.query(LeaveBalance)
                    .filter_by(org_id=org_id, user_id=current_user.id, year=year).all())
    except Exception:
        year = now_naive().date().year
        balances = []
        db.session.rollback()
    return render_template("roster/leave.html", my_reqs=my_reqs, pending=pending,
                           balances=balances, year=year, leave_types=LEAVE_TYPES)


@bp.get("/roster/leave/request")
@require_role(*VIEWERS)
def leave_request_form():
    return render_template("roster/leave_request.html", leave_types=LEAVE_TYPES)


@bp.post("/roster/leave/request")
@require_role(*VIEWERS)
def leave_request_submit():
    from ..models import LeaveRequest, LEAVE_BALANCE_DEFAULTS
    import datetime as dt
    leave_type = rd.normalise_leave(request.form.get("leave_type") or "")
    start_raw = (request.form.get("start_date") or "").strip()
    end_raw = (request.form.get("end_date") or "").strip()
    reason = (request.form.get("reason") or "").strip()[:300]

    errors = []
    if not leave_type:
        errors.append("Choose the type of leave.")
    start = rd.parse_date(start_raw)
    end = rd.parse_date(end_raw) or start
    if not start:
        errors.append("Enter a valid start date.")
    if not end:
        errors.append("Enter a valid end date.")
    if start and end and end < start:
        errors.append("End date cannot be before start date.")
    if start and (end - start).days + 1 > 90:
        errors.append("Leave request cannot exceed 90 days at once. Split it.")
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("roster.leave_request_form"))

    days = (end - start).days + 1
    req = LeaveRequest(
        org_id=current_user.org_id,
        user_id=current_user.id,
        leave_type=leave_type,
        start_date=start,
        end_date=end,
        days_requested=days,
        reason=reason,
        status="PENDING",
    )
    db.session.add(req)
    audit("LEAVE_REQUESTED", "leave_request", None,
          {"type": leave_type, "start": str(start), "end": str(end), "days": days})
    db.session.commit()
    flash(f"Leave request sent: {days} day(s) {req.label} from {start} to {end}. Your HOD/HR will review.", "success")
    return redirect(url_for("roster.leave_list"))


@bp.post("/roster/leave/<int:rid>/approve")
@require_role("HOD", "HEAD_ADMIN_HR", "SUPER_ADMIN", "ADMIN_MANAGER")
def leave_approve(rid: int):
    from ..models import LeaveRequest, LeaveBalance, RosterEntry, now_naive
    org_id = current_user.org_id
    req = db.session.get(LeaveRequest, rid)
    if not req or req.org_id != org_id:
        abort(404)
    if req.status != "PENDING":
        flash("This request is already reviewed.", "info")
        return redirect(url_for("roster.leave_list"))
    # Check balance
    year = req.start_date.year
    bal = (db.session.query(LeaveBalance)
           .filter_by(org_id=org_id, user_id=req.user_id, year=year, leave_type=req.leave_type).first())
    if not bal:
        from ..models import LEAVE_BALANCE_DEFAULTS
        entitled = LEAVE_BALANCE_DEFAULTS.get(req.leave_type, 30)
        bal = LeaveBalance(org_id=org_id, user_id=req.user_id, year=year,
                           leave_type=req.leave_type, entitled=entitled,
                           used=0, remaining=entitled)
        db.session.add(bal)
        db.session.flush()
    if bal.remaining < req.days_requested and req.leave_type not in ("SICK", "COMPASSIONATE", "OFF"):
        flash(f"{req.user.name} has only {bal.remaining} days of {req.label} left, but requested {req.days_requested}. Approve anyway? Use note.", "warning")

    # Create roster entries for each day
    try:
        for d in rd.days_between(req.start_date, req.end_date):
            # Skip if already on leave
            if rd.leave_on(org_id, req.user_id, d):
                continue
            # Find user's department for scope
            user = db.session.get(User, req.user_id)
            dept_id = getattr(user, "department_id", None)
            db.session.add(RosterEntry(
                org_id=org_id, duty_date=d, user_id=req.user_id,
                kind="LEAVE", shift="LEAVE", leave_type=req.leave_type,
                scope="DEPARTMENT" if dept_id else "ORG",
                department_id=dept_id, note=f"Approved leave #{req.id}",
                source="leave_request", created_by=current_user.id))
        req.status = "APPROVED"
        req.reviewed_by = current_user.id
        req.reviewed_at = now_naive()
        req.roster_created = True
        bal.used += req.days_requested
        bal.remaining = max(0, bal.entitled - bal.used)
        audit("LEAVE_APPROVED", "leave_request", req.id,
              {"type": req.leave_type, "days": req.days_requested, "user": req.user.name})
        db.session.commit()
        flash(f"Approved: {req.user.name} — {req.days_requested} days {req.label}.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not approve: {exc}", "error")
    return redirect(url_for("roster.leave_list"))


@bp.post("/roster/leave/<int:rid>/reject")
@require_role("HOD", "HEAD_ADMIN_HR", "SUPER_ADMIN", "ADMIN_MANAGER")
def leave_reject(rid: int):
    from ..models import LeaveRequest, now_naive
    org_id = current_user.org_id
    req = db.session.get(LeaveRequest, rid)
    if not req or req.org_id != org_id:
        abort(404)
    if req.status != "PENDING":
        flash("Already reviewed.", "info")
        return redirect(url_for("roster.leave_list"))
    note = (request.form.get("review_note") or "").strip()[:300]
    req.status = "REJECTED"
    req.reviewed_by = current_user.id
    req.reviewed_at = now_naive()
    req.review_note = note
    audit("LEAVE_REJECTED", "leave_request", req.id, {"note": note})
    db.session.commit()
    flash(f"Rejected leave request for {req.user.name}.", "info")
    return redirect(url_for("roster.leave_list"))


@bp.post("/roster/autofill")
@require_role(*EDITORS)
def roster_autofill():
    """Auto-fill next week from previous week."""
    from datetime import timedelta
    place, errs = _place_from_request(request.form)
    if errs:
        flash("Choose where this roster belongs first.", "error")
        return redirect(url_for("roster.roster_view"))
    _require_edit(place)
    src_raw = (request.form.get("source_start") or "").strip()
    tgt_raw = (request.form.get("target_start") or "").strip()
    src = rd.parse_date(src_raw)
    tgt = rd.parse_date(tgt_raw)
    if not src or not tgt:
        flash("Pick source week start and target week start dates.", "error")
        return redirect(_back(place))
    result = rd.autofill_next_week(current_user.org_id, place,
                                   source_start=src, target_start=tgt,
                                   created_by_id=current_user.id)
    audit("ROSTER_AUTOFILL", "roster", None,
          {"source": str(src), "target": str(tgt), "added": result["added"], "place": place})
    db.session.commit()
    flash(f"Auto-filled {result['added']} duty slots from week of {src} to week of {tgt}. {result['skipped']} skipped (leave or already rostered).", "success")
    return redirect(_back(place))

# ------------------------------------------------------------------ export



# ------------------------------------------------------------------ export
@bp.get("/roster/export")
@require_role(*VIEWERS)
def roster_export():
    """Download exactly what is on screen — hospitals still print rosters."""
    import csv as _csv
    import io as _io
    start, end, _ = rd.resolve_range(request.args.get("range", "7"),
                                     request.args.get("from", ""), request.args.get("to", ""))
    place, errs = _place_from_request()
    if errs:
        place = {"scope": "ORG"}
    rows = rd.load_roster(current_user.org_id, start, end, place=place)
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["Date", "Day", "Type", "Shift / Leave", "Staff", "Where", "Note"])
    for r in rows:
        w.writerow([r["date"].isoformat(), r["date"].strftime("%A"),
                    "Leave" if r["kind"] == "LEAVE" else "Duty",
                    r["label"], r["person"], r["place"], r["note"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             f"attachment; filename=roster-{start}-to-{end}.csv"})
