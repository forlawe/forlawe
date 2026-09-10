"""Merged admin — Hospital Structure: Departments + Clinics + Rooms + Destinations + TV.

Founder said: "I don't get you — Merge Department vs Clinic admin"
This file answers it by putting everything on ONE page with tabs, but keeping
the data separate behind (Department = who you work for, Clinic = where patient
goes today). No data loss, premium++ UX, per-tenant.

Old pages still work: /admin/structure, /admin/servicepoints, /admin/tv
New merged page: /admin/hospital-structure
"""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import (
    ConsultingRoom,
    Department,
    ServiceClinic,
    ServiceDestination,
    TvScreen,
    User,
    db,
    now_naive,
)
from ..security import PHONE_RE, clean_phone, require_role
from ..servicepoints import ensure_defaults as sp_ensure, all_clinics, all_rooms, all_destinations
from .. import tv as tv_engine

bp = Blueprint("hospital_structure", __name__, url_prefix="/admin/hospital-structure")
SUPER = ("SUPER_ADMIN",)


@bp.before_request
def _seed():
    try:
        sp_ensure(current_user.org_id)
        tv_engine.ensure_default_screens(current_user.org_id)
    except Exception:
        pass


def _tab():
    t = (request.args.get("tab") or request.form.get("tab") or "departments").strip().lower()
    if t not in ("departments", "clinics", "rooms", "destinations", "tv"):
        return "departments"
    return t


def _redirect(tab: str):
    return redirect(url_for("hospital_structure.overview", tab=tab))


@bp.get("")
@require_role(*SUPER)
def overview():
    org_id = current_user.org_id
    tab = _tab()
    depts = db.session.query(Department).filter_by(org_id=org_id).order_by(Department.name).all()
    clinics = all_clinics(org_id)
    rooms = all_rooms(org_id)
    dests = all_destinations(org_id)
    screens = db.session.query(TvScreen).filter_by(org_id=org_id).order_by(TvScreen.code).all()
    hods = (
        db.session.query(User)
        .filter_by(org_id=org_id, active=True)
        .filter(User.role.in_(("HOD", "MD_CEO", "SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER")))
        .order_by(User.name)
        .all()
    )
    from ..models import ROSTER_MODE_LABELS

    return render_template(
        "admin/hospital_structure.html",
        tab=tab,
        depts=depts,
        clinics=clinics,
        rooms=rooms,
        destinations=dests,
        screens=screens,
        hods=hods,
        roster_modes=ROSTER_MODE_LABELS,
    )


# ------------------------------------------------------------------ departments (reuses logic from admincp)
@bp.post("/departments")
@require_role(*SUPER)
def department_save():
    tab = "departments"
    name = (request.form.get("name") or "").strip()
    hod_id = request.form.get("hod_user_id", type=int)
    dept_id = request.form.get("department_id", type=int)
    hod_name = (request.form.get("hod_name") or "").strip()
    hod_phone = (request.form.get("hod_phone") or "").strip().replace(" ", "").replace("-", "")
    if not name:
        flash("Department name is required.", "error")
        return _redirect(tab)
    if hod_id:
        picked = db.session.get(User, hod_id)
        if picked and picked.org_id == current_user.org_id:
            hod_name = hod_name or picked.name
            hod_phone = hod_phone or clean_phone(picked.phone or "")
    if not dept_id and (not hod_name or not hod_phone):
        flash("HOD name and phone required for new department.", "error")
        return _redirect(tab)
    if hod_phone and not PHONE_RE.match(hod_phone):
        flash("Enter valid HOD phone e.g. 08012345678", "error")
        return _redirect(tab)
    from ..models import DEPT_SHIFTS

    roster_mode = request.form.get("roster_mode") or "two_12h"
    if roster_mode not in DEPT_SHIFTS:
        roster_mode = "two_12h"
    try:
        per_shift = max(1, min(20, int(request.form.get("roster_staff_per_shift") or 1)))
    except ValueError:
        per_shift = 1

    if dept_id:
        dept = db.session.get(Department, dept_id)
        if not dept or dept.org_id != current_user.org_id:
            abort(404)
        dept.name = name
        dept.hod_user_id = hod_id or None
        dept.hod_name = hod_name or None
        dept.hod_phone = hod_phone or None
        dept.roster_mode = roster_mode
        dept.roster_staff_per_shift = per_shift
    else:
        exists = db.session.query(Department).filter_by(org_id=current_user.org_id, name=name).first()
        if exists:
            flash("Department name already exists.", "error")
            return _redirect(tab)
        dept = Department(
            org_id=current_user.org_id,
            name=name,
            hod_user_id=hod_id or None,
            hod_name=hod_name or None,
            hod_phone=hod_phone or None,
            roster_mode=roster_mode,
            roster_staff_per_shift=per_shift,
        )
        db.session.add(dept)
    db.session.commit()
    flash(f"Department {name} saved.", "success")
    return _redirect(tab)


@bp.post("/departments/<int:did>/toggle")
@require_role(*SUPER)
def department_toggle(did: int):
    d = db.session.get(Department, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    d.active = not d.active
    db.session.commit()
    flash(f"Department {d.name} {'activated' if d.active else 'suspended'}.", "success")
    return _redirect("departments")


@bp.post("/departments/<int:did>/delete")
@require_role(*SUPER)
def department_delete(did: int):
    d = db.session.get(Department, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    if d.sections:
        flash("Delete its sections first, or Suspend instead.", "error")
        return _redirect("departments")
    # block if referenced
    from ..models import Appointment, Complaint, DeptRosterEntry, Inspection, PatientFeedback, QueueTicket, Referral, RosterEntry

    checks = [
        (Inspection.department_id, "inspections"),
        (Complaint.department_id, "complaints"),
        (Appointment.department_id, "bookings"),
        (QueueTicket.department_id, "queue tickets"),
        (PatientFeedback.department_id, "feedback"),
        (DeptRosterEntry.department_id, "roster entries"),
        (RosterEntry.department_id, "roster entries"),
        (Referral.department_id, "referral links"),
    ]
    for col, label in checks:
        if db.session.query(col).filter(col == d.id).first() is not None:
            flash(f"Has {label} — cannot delete, Suspend instead.", "error")
            return _redirect("departments")
    db.session.delete(d)
    db.session.commit()
    flash(f"Department {d.name} deleted.", "success")
    return _redirect("departments")


@bp.post("/departments/install-standard")
@require_role(*SUPER)
def install_standard():
    from ..standard_departments import install as install_std

    try:
        made = install_std(current_user.org_id, only_missing=True)
        db.session.commit()
        if made["departments"]:
            flash(f"Added {made['departments']} dept, {made['sections']} sections, {made['units']} units.", "success")
        else:
            flash("Already have all standard departments.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not add: {exc}", "error")
    return _redirect("departments")


# ------------------------------------------------------------------ clinics
@bp.post("/clinics/create")
@require_role(*SUPER)
def clinic_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    desc = (request.form.get("description") or "").strip()[:300]
    if not code or not name:
        flash("Clinic code and name required.", "error")
        return _redirect("clinics")
    if db.session.query(ServiceClinic).filter_by(org_id=current_user.org_id, code=code).first():
        flash(f"Clinic {code} already exists.", "error")
        return _redirect("clinics")
    c = ServiceClinic(org_id=current_user.org_id, code=code, name=name, description=desc, active=True)
    db.session.add(c)
    db.session.commit()
    flash(f"Clinic {name} ({code}) created.", "success")
    return _redirect("clinics")


@bp.post("/clinics/<int:cid>/edit")
@require_role(*SUPER)
def clinic_edit(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    name = (request.form.get("name") or "").strip()[:120]
    code = (request.form.get("code") or "").strip().upper()[:20]
    desc = (request.form.get("description") or "").strip()[:300]
    if not name or not code:
        flash("Name and code required.", "error")
        return _redirect("clinics")
    other = (
        db.session.query(ServiceClinic)
        .filter(ServiceClinic.org_id == current_user.org_id, ServiceClinic.code == code, ServiceClinic.id != c.id)
        .first()
    )
    if other:
        flash(f"Another clinic uses code {code}.", "error")
        return _redirect("clinics")
    c.name = name
    c.code = code
    c.description = desc
    c.updated_at = now_naive()
    db.session.commit()
    flash(f"Clinic {name} updated.", "success")
    return _redirect("clinics")


@bp.post("/clinics/<int:cid>/toggle")
@require_role(*SUPER)
def clinic_toggle(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    c.active = not c.active
    c.updated_at = now_naive()
    db.session.commit()
    flash(f"Clinic {c.name} {'activated' if c.active else 'suspended'}.", "success")
    return _redirect("clinics")


@bp.post("/clinics/<int:cid>/delete")
@require_role(*SUPER)
def clinic_delete(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    from ..models import DoctorSession, PatientVisit, ClinicDestination

    if db.session.query(DoctorSession).filter_by(org_id=c.org_id, clinic=c.code).first():
        flash(f"Cannot delete {c.code} — used in sessions. Suspend instead.", "error")
        return _redirect("clinics")
    if db.session.query(PatientVisit).filter_by(org_id=c.org_id, clinic=c.code).first():
        flash(f"Cannot delete {c.code} — used in visits. Suspend instead.", "error")
        return _redirect("clinics")
    db.session.query(ClinicDestination).filter_by(clinic_id=c.id).delete()
    db.session.delete(c)
    db.session.commit()
    flash(f"Clinic {c.name} deleted.", "success")
    return _redirect("clinics")


# ------------------------------------------------------------------ rooms
@bp.post("/rooms/create")
@require_role(*SUPER)
def room_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    clinic_id = request.form.get("clinic_id", type=int)
    if not code or not name:
        flash("Room code and name required.", "error")
        return _redirect("rooms")
    if db.session.query(ConsultingRoom).filter_by(org_id=current_user.org_id, code=code).first():
        flash(f"Room {code} exists.", "error")
        return _redirect("rooms")
    if clinic_id:
        cl = db.session.get(ServiceClinic, clinic_id)
        if not cl or cl.org_id != current_user.org_id:
            clinic_id = None
    r = ConsultingRoom(org_id=current_user.org_id, code=code, name=name, clinic_id=clinic_id, active=True)
    db.session.add(r)
    db.session.commit()
    flash(f"Room {name} created.", "success")
    return _redirect("rooms")


@bp.post("/rooms/<int:rid>/edit")
@require_role(*SUPER)
def room_edit(rid: int):
    r = db.session.get(ConsultingRoom, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    clinic_id = request.form.get("clinic_id", type=int)
    if not code or not name:
        flash("Code and name required.", "error")
        return _redirect("rooms")
    other = (
        db.session.query(ConsultingRoom)
        .filter(ConsultingRoom.org_id == current_user.org_id, ConsultingRoom.code == code, ConsultingRoom.id != r.id)
        .first()
    )
    if other:
        flash(f"Another room uses code {code}.", "error")
        return _redirect("rooms")
    r.code = code
    r.name = name
    if clinic_id:
        cl = db.session.get(ServiceClinic, clinic_id)
        r.clinic_id = cl.id if cl and cl.org_id == current_user.org_id else None
    else:
        r.clinic_id = None
    r.updated_at = now_naive()
    db.session.commit()
    flash(f"Room {name} updated.", "success")
    return _redirect("rooms")


@bp.post("/rooms/<int:rid>/toggle")
@require_role(*SUPER)
def room_toggle(rid: int):
    r = db.session.get(ConsultingRoom, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    r.active = not r.active
    r.updated_at = now_naive()
    db.session.commit()
    flash(f"Room {r.name} {'activated' if r.active else 'suspended'}.", "success")
    return _redirect("rooms")


@bp.post("/rooms/<int:rid>/delete")
@require_role(*SUPER)
def room_delete(rid: int):
    r = db.session.get(ConsultingRoom, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    from ..models import DoctorSession, PatientVisit

    if db.session.query(DoctorSession).filter_by(org_id=r.org_id, consulting_room=r.code).first():
        flash(f"Cannot delete {r.code} — used in sessions. Suspend instead.", "error")
        return _redirect("rooms")
    if db.session.query(PatientVisit).filter_by(org_id=r.org_id, consulting_room=r.code).first():
        flash(f"Cannot delete {r.code} — used in visits. Suspend instead.", "error")
        return _redirect("rooms")
    db.session.delete(r)
    db.session.commit()
    flash(f"Room {r.name} deleted.", "success")
    return _redirect("rooms")


# ------------------------------------------------------------------ destinations
@bp.post("/destinations/create")
@require_role(*SUPER)
def dest_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    place = (request.form.get("place") or "").strip()[:200]
    desc = (request.form.get("description") or "").strip()[:300]
    if not code or not name:
        flash("Code and name required.", "error")
        return _redirect("destinations")
    if db.session.query(ServiceDestination).filter_by(org_id=current_user.org_id, code=code).first():
        flash(f"Destination {code} exists.", "error")
        return _redirect("destinations")
    d = ServiceDestination(
        org_id=current_user.org_id, code=code, name=name, place=place or name, description=desc, active=True
    )
    db.session.add(d)
    db.session.commit()
    flash(f"Destination {name} created.", "success")
    return _redirect("destinations")


@bp.post("/destinations/<int:did>/edit")
@require_role(*SUPER)
def dest_edit(did: int):
    d = db.session.get(ServiceDestination, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    place = (request.form.get("place") or "").strip()[:200]
    desc = (request.form.get("description") or "").strip()[:300]
    if not code or not name:
        flash("Code and name required.", "error")
        return _redirect("destinations")
    other = (
        db.session.query(ServiceDestination)
        .filter(ServiceDestination.org_id == current_user.org_id, ServiceDestination.code == code, ServiceDestination.id != d.id)
        .first()
    )
    if other:
        flash(f"Another destination uses code {code}.", "error")
        return _redirect("destinations")
    d.code = code
    d.name = name
    d.place = place or name
    d.description = desc
    d.updated_at = now_naive()
    db.session.commit()
    flash(f"Destination {name} updated.", "success")
    return _redirect("destinations")


@bp.post("/destinations/<int:did>/toggle")
@require_role(*SUPER)
def dest_toggle(did: int):
    d = db.session.get(ServiceDestination, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    d.active = not d.active
    d.updated_at = now_naive()
    db.session.commit()
    flash(f"Destination {d.name} {'activated' if d.active else 'suspended'}.", "success")
    return _redirect("destinations")


@bp.post("/destinations/<int:did>/delete")
@require_role(*SUPER)
def dest_delete(did: int):
    d = db.session.get(ServiceDestination, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    from ..models import VisitOnward, ClinicDestination

    if db.session.query(VisitOnward).filter_by(org_id=d.org_id, destination=d.code).first():
        flash(f"Cannot delete {d.code} — used in routing. Suspend instead.", "error")
        return _redirect("destinations")
    db.session.query(ClinicDestination).filter_by(destination_id=d.id).delete()
    db.session.delete(d)
    db.session.commit()
    flash(f"Destination {d.name} deleted.", "success")
    return _redirect("destinations")


# ------------------------------------------------------------------ TV screens (reuse tv logic)
@bp.post("/tv/create")
@require_role(*SUPER)
def tv_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    location = (request.form.get("location") or "").strip()[:120]
    screen_type = request.form.get("screen_type") or "WAITING_MAIN"
    clinic_code = (request.form.get("clinic_code") or "").strip().upper()[:20] or None
    dept_id = request.form.get("department_id", type=int)
    if not code or not name:
        flash("Code and name required for TV.", "error")
        return _redirect("tv")
    if db.session.query(TvScreen).filter_by(org_id=current_user.org_id, code=code).first():
        flash(f"TV {code} exists.", "error")
        return _redirect("tv")
    s = TvScreen(
        org_id=current_user.org_id,
        code=code,
        name=name,
        location=location,
        screen_type=screen_type,
        clinic_code=clinic_code,
        department_id=dept_id,
        show_full_name=True,
        show_queue_stats=True,
        voice_enabled=True,
        voice_rotate_daily=True,
        voice_languages="en,yo",
        voice_volume=100,
        active=True,
    )
    db.session.add(s)
    db.session.commit()
    flash(f"TV {name} ({code}) created.", "success")
    return _redirect("tv")


@bp.post("/tv/<int:sid>/edit")
@require_role(*SUPER)
def tv_edit(sid: int):
    s = db.session.get(TvScreen, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    s.name = (request.form.get("name") or s.name).strip()[:120]
    s.location = (request.form.get("location") or "").strip()[:120]
    s.screen_type = request.form.get("screen_type") or s.screen_type
    s.clinic_code = (request.form.get("clinic_code") or "").strip().upper()[:20] or None
    s.department_id = request.form.get("department_id", type=int)
    s.show_full_name = bool(request.form.get("show_full_name"))
    s.show_queue_stats = bool(request.form.get("show_queue_stats"))
    s.voice_enabled = bool(request.form.get("voice_enabled"))
    s.voice_rotate_daily = bool(request.form.get("voice_rotate_daily"))
    s.voice_languages = (request.form.get("voice_languages") or "en,yo").strip()[:20]
    try:
        vol = int(request.form.get("voice_volume") or s.voice_volume or 100)
        s.voice_volume = max(0, min(100, vol))
    except ValueError:
        pass
    s.active = bool(request.form.get("active"))
    db.session.commit()
    flash(f"TV {s.name} updated.", "success")
    return _redirect("tv")


@bp.post("/tv/<int:sid>/toggle")
@require_role(*SUPER)
def tv_toggle(sid: int):
    s = db.session.get(TvScreen, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    s.active = not s.active
    db.session.commit()
    flash(f"TV {s.name} {'activated' if s.active else 'suspended'}.", "success")
    return _redirect("tv")


@bp.post("/tv/<int:sid>/delete")
@require_role(*SUPER)
def tv_delete(sid: int):
    s = db.session.get(TvScreen, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    if s.code == "MAIN":
        flash("Cannot delete MAIN — suspend instead.", "error")
        return _redirect("tv")
    db.session.delete(s)
    db.session.commit()
    flash(f"TV {s.name} deleted.", "success")
    return _redirect("tv")
