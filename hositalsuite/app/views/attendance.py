"""Staff clock-in / clock-out. Phone first, plain English."""
from __future__ import annotations

from datetime import datetime

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from .. import attendance as engine
from ..audit import audit
from ..models import Branch, StaffAttendance, User, db, now_naive
from ..navigation import permissions_for
from ..security import save_upload

bp = Blueprint("attendance", __name__)


def _coords(src=None):
    src = src if src is not None else request.form
    lat = engine.parse_coord(src.get("lat"), kind="lat")
    lng = engine.parse_coord(src.get("lng"), kind="lng")
    try:
        acc = int(float(src.get("accuracy") or 0)) or None
    except (TypeError, ValueError):
        acc = None
    return lat, lng, acc


def _mocked(src=None) -> bool:
    src = src if src is not None else request.form
    return engine.as_bool(src.get("mocked"))


def _client_at(src=None):
    src = src if src is not None else request.form
    return engine.parse_when(src.get("client_at") or src.get("punched_at"))


def _may_see_board(user) -> bool:
    if permissions_for(user).get("attendance_admin"):
        return True
    return engine.can_supervise(user)


def _scoped_rows(viewer, day, branch_id=None):
    rows = engine.today_board(viewer.org_id, day=day, branch_id=branch_id)
    ids = engine.supervise_dept_ids(viewer)
    if ids is None:
        return rows
    out = []
    for r in rows:
        person = r.user if getattr(r, "user", None) else db.session.get(User, r.user_id)
        if person and (person.department_id in ids or person.id == viewer.id):
            out.append(r)
    return out


@bp.get("/attendance")
@login_required
def desk():
    site = engine.site_for(current_user)
    fence = engine.fence_for(current_user.org_id, site)
    open_row = engine.open_row(current_user.org_id, current_user.id)
    can = permissions_for(current_user)
    can_admin = bool(can.get("attendance_admin") or can.get("admin"))
    can_board = _may_see_board(current_user)
    helpers = engine.helpable_staff(current_user)
    open_ids = {r.user_id for r in engine.today_board(current_user.org_id)
                if r.is_open}
    reviews = engine.pending_reviews(current_user) if can_board else []
    return render_template(
        "attendance.html",
        fence=fence, site=site, open_row=open_row,
        can_admin=can_admin,
        can_board=can_board,
        can_help=engine.can_supervise(current_user),
        help_staff=helpers,
        open_ids=open_ids,
        help_reasons=engine.HELP_REASONS,
        reviews=reviews,
    )


@bp.post("/attendance/in")
@login_required
def punch_in():
    lat, lng, acc = _coords()
    device = (request.headers.get("User-Agent") or "")[:200]
    row, verdict = engine.clock_in(
        current_user, lat=lat, lng=lng, accuracy_m=acc, device_info=device,
        mocked=_mocked(), client_at=_client_at())
    if not verdict.get("ok"):
        flash(verdict["reason"], "error")
        return redirect(url_for("attendance.desk"))
    audit("ATTENDANCE_IN", "staff_attendance", row.id if row else None,
          {"inside": verdict.get("inside"), "distance_m": verdict.get("distance_m"),
           "mode": (row.mode if row else None),
           "flagged": bool(row.flagged) if row else False})
    db.session.commit()
    flash(verdict["reason"] if verdict.get("already") else "You are signed in. Welcome.",
          "info" if verdict.get("already") else "success")
    return redirect(url_for("attendance.desk"))


@bp.post("/attendance/out")
@login_required
def punch_out():
    lat, lng, acc = _coords()
    row, verdict = engine.clock_out(
        current_user, lat=lat, lng=lng, accuracy_m=acc,
        mocked=_mocked(), client_at=_client_at())
    if not verdict.get("ok") or row is None:
        flash(verdict.get("reason") or "You are not signed in.", "error")
        return redirect(url_for("attendance.desk"))
    audit("ATTENDANCE_OUT", "staff_attendance", row.id, {})
    db.session.commit()
    flash("You are signed out. Thank you.", "success")
    return redirect(url_for("attendance.desk"))


@bp.post("/attendance/gate")
@login_required
def save_gate():
    """System Admin pins the circle on a map — from I am here, not a hidden page.

    v1.7.18: ADMIN_MANAGER only on duty TODAY can pin gate.
    """
    can = permissions_for(current_user)
    # v1.7.18: only SUPER_ADMIN / system admin may pin gate; ADMIN_MANAGER on duty may; HOD may NOT
    # attendance_admin allows viewing board & signing flagged, but NOT pinning gate
    if not can.get("admin"):
        # Allow ADMIN_MANAGER on duty even without admin (has attendance_admin)
        if getattr(current_user, "role", "") == "ADMIN_MANAGER":
            from ..security import is_admin_manager_on_duty
            if not is_admin_manager_on_duty(current_user):
                abort(403, description="Only on-duty Admin Manager can pin gate.")
        else:
            abort(403)
    else:
        # Even admin role ADMIN_MANAGER must be on duty for gate
        if getattr(current_user, "role", "") == "ADMIN_MANAGER":
            from ..security import is_admin_manager_on_duty
            if not is_admin_manager_on_duty(current_user):
                abort(403, description="Only on-duty Admin Manager can pin gate.")
    site = engine.site_for(current_user)
    fence = engine.save_gate(
        current_user.org_id,
        mode=(request.form.get("attendance_mode") or "off").strip(),
        lat=request.form.get("attendance_lat") or request.form.get("lat"),
        lng=request.form.get("attendance_lng") or request.form.get("lng"),
        radius_m=request.form.get("attendance_radius_m"),
        grace_minutes=request.form.get("attendance_grace_minutes"),
        branch=site,
    )
    audit("ATTENDANCE_GATE", "organization", current_user.org_id,
          {"mode": fence.mode, "radius_m": fence.radius_m,
           "pinned": fence.pinned, "place": fence.place})
    db.session.commit()
    if fence.mode == "off":
        flash("Gate check is off. Staff can still sign in.", "success")
    elif fence.pinned:
        flash(f"Gate pin saved for {fence.place}. Circle is {fence.radius_m} metres.",
              "success")
    else:
        flash("Strictness saved. Drop the pin on the map and save again.", "info")
    return redirect(url_for("attendance.desk"))


@bp.post("/attendance/sync")
@login_required
def sync():
    """Replay punches that sat on the phone while there was no internet."""
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    results = []
    for item in items[:20]:
        kind = (item.get("kind") or "").lower()
        body = item.get("payload") or item
        lat = engine.parse_coord(body.get("lat"), kind="lat")
        lng = engine.parse_coord(body.get("lng"), kind="lng")
        try:
            acc = int(float(body.get("accuracy") or 0)) or None
        except (TypeError, ValueError):
            acc = None
        mocked = engine.as_bool(body.get("mocked"))
        client_at = engine.parse_when(body.get("client_at") or item.get("at"))
        device = (request.headers.get("User-Agent") or "")[:200]
        if kind == "out":
            row, verdict = engine.clock_out(
                current_user, lat=lat, lng=lng, accuracy_m=acc,
                mocked=mocked, client_at=client_at)
        else:
            row, verdict = engine.clock_in(
                current_user, lat=lat, lng=lng, accuracy_m=acc,
                device_info=device, mocked=mocked, client_at=client_at)
        results.append({"ok": bool(verdict.get("ok")),
                        "reason": verdict.get("reason"),
                        "already": verdict.get("already")})
        if verdict.get("ok") and row is not None:
            audit("ATTENDANCE_SYNC", "staff_attendance", row.id,
                  {"kind": kind or "in", "offline": True})
    db.session.commit()
    return jsonify({"ok": True, "results": results})


@bp.get("/attendance/today")
@login_required
def today():
    if not _may_see_board(current_user):
        abort(403)
    day = now_naive().date()
    raw = (request.args.get("date") or "").strip()
    if raw:
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            day = now_naive().date()
    branch_id = request.args.get("branch_id", type=int)
    if branch_id:
        b = db.session.get(Branch, branch_id)
        if not b or b.org_id != current_user.org_id:
            abort(404)
    rows = _scoped_rows(current_user, day, branch_id)
    sites = (db.session.query(Branch)
             .filter_by(org_id=current_user.org_id, active=True)
             .order_by(Branch.is_main.desc(), Branch.name).all())
    open_ids = {r.user_id for r in rows if r.is_open}
    staff = engine.helpable_staff(current_user)
    in_now = sum(1 for r in rows if r.is_open)
    reviews = engine.pending_reviews(current_user, day)
    return render_template(
        "attendance_today.html", rows=rows, day=day, sites=sites,
        branch_id=branch_id, in_now=in_now, total=len(rows),
        staff=staff, open_ids=open_ids,
        help_reasons=engine.HELP_REASONS,
        help_labels=engine.HELP_LABELS,
        reviews=reviews,
        scope_note=("Whole hospital" if engine.supervise_dept_ids(current_user) is None
                    else "Your department only"),
    )


@bp.post("/attendance/override")
@login_required
def override():
    """HOD / supervisor / admin signs someone in. Photo + fixed reason required.

    v1.7.18: STAFF cannot sign-in co-staff. ADMIN_MANAGER only on duty TODAY.
    """
    uid = request.form.get("user_id", type=int)
    code = (request.form.get("help_reason") or "").strip()
    extra = (request.form.get("reason") or "").strip()[:120]
    target = db.session.get(User, uid) if uid else None
    next_url = request.form.get("next") or url_for("attendance.desk")
    dest = (url_for("attendance.today")
            if str(next_url).startswith("/attendance/today")
            else url_for("attendance.desk"))
    if not target or target.org_id != current_user.org_id or not target.active:
        flash("Pick a member of staff.", "error")
        return redirect(dest)
    # v1.7.18: STAFF explicit block
    if getattr(current_user, "role", "") == "STAFF":
        flash("Staff cannot sign-in co-staff. Only HOD, Apex Nurse (own dept), Admin Manager on duty, or System Admin.", "error")
        return redirect(dest)
    # v1.7.18: ADMIN_MANAGER on-duty check
    if getattr(current_user, "role", "") == "ADMIN_MANAGER":
        from ..security import is_admin_manager_on_duty
        if not is_admin_manager_on_duty(current_user):
            flash("Only the Admin Manager on duty TODAY can sign-in co-staff.", "error")
            return redirect(dest)
    if not engine.can_help(current_user, target):
        flash("You may only help staff in your own department.", "error")
        return redirect(dest)
    if code not in engine.HELP_CODES:
        flash("Pick a reason from the list. Free text alone is not enough.", "error")
        return redirect(dest)
    photo = request.files.get("evidence")
    if not photo or not photo.filename:
        flash("Take a photo of the person at the gate. No photo, no help.", "error")
        return redirect(dest)
    path, err = save_upload(photo, "attendance", org_id=current_user.org_id)
    if err:
        flash(err, "error")
        return redirect(dest)
    label = engine.HELP_LABELS[code]
    reason = f"{label}" + (f" — {extra}" if extra else "")
    row, verdict = engine.clock_in(
        target, override_reason=reason, override_by=current_user,
        help_reason=code, evidence_path=path)
    if not verdict.get("ok"):
        flash(verdict["reason"], "error")
        return redirect(dest)
    audit("ATTENDANCE_OVERRIDE", "staff_attendance", row.id if row else None,
          {"for": target.username, "reason": reason, "help_reason": code,
           "by": current_user.username})
    db.session.commit()
    flash(f"{target.name} is signed in. Photo and reason kept on the record.", "success")
    return redirect(dest)


@bp.post("/attendance/review")
@login_required
def review():
    """HOD / supervisor signs a flagged punch so it is no longer hanging."""
    if not _may_see_board(current_user):
        abort(403)
    rid = request.form.get("row_id", type=int)
    note = (request.form.get("note") or "").strip()[:200]
    row = db.session.get(StaffAttendance, rid or 0)
    if not engine.accept_review(current_user, row, note):
        flash("You cannot sign this record.", "error")
        return redirect(request.form.get("next") or url_for("attendance.desk"))
    audit("ATTENDANCE_REVIEW", "staff_attendance", row.id,
          {"by": current_user.username, "note": note})
    db.session.commit()
    who = row.user.name if row.user else "Staff"
    flash(f"Signed. {who}'s clock-in is accepted.", "success")
    dest = request.form.get("next") or url_for("attendance.desk")
    return redirect(dest if dest.startswith("/attendance") else url_for("attendance.desk"))


@bp.get("/attendance/week")
@login_required
def week():
    if not _may_see_board(current_user):
        abort(403)
    raw = (request.args.get("date") or "").strip()
    day = now_naive().date()
    if raw:
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            day = now_naive().date()
    start, end = engine.week_bounds(day)
    report = engine.weekly_report(current_user.org_id, start, end)
    ids = engine.supervise_dept_ids(current_user)
    if ids is not None:
        report["staff"] = [r for r in report["staff"]
                           if r["department_id"] in ids or r["user"].id == current_user.id]
        report["departments"] = [d for d in report["departments"]
                                 if d["name"] in {r["department"] for r in report["staff"]}]
    return render_template("attendance_week.html", report=report, day=day)
