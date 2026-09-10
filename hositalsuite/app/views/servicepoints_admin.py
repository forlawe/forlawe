"""Admin CRUD for clinics, consulting rooms, and onward destinations.

All per-tenant (org_id), suspendable, editable. No hard deletes when in use —
suspend instead. Founder wanted Dental, ANC, O&G, Eye etc, plus 25+ destinations
and 8 rooms, all admin editable.

Voice: every action that changes where patients go announces via app.js speak()
on the admin page? Actually voice reminder at every handoff is for patient
stations; admin page gets plain flash messages.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import ConsultingRoom, ServiceClinic, ServiceDestination, db, now_naive
from ..security import require_role
from ..servicepoints import (
    DEFAULT_CLINICS,
    DEFAULT_DESTINATIONS,
    DEFAULT_ROOMS,
    ensure_defaults,
    all_clinics,
    all_destinations,
    all_rooms,
)

bp = Blueprint("servicepoints_admin", __name__, url_prefix="/admin/servicepoints")
SUPER = ("SUPER_ADMIN",)


@bp.before_request
def _seed():
    try:
        ensure_defaults(current_user.org_id)
    except Exception:
        pass


# ------------------------------------------------------------------ overview
@bp.get("")
@require_role(*SUPER)
def overview():
    org_id = current_user.org_id
    clinics = all_clinics(org_id)
    rooms = all_rooms(org_id)
    dests = all_destinations(org_id)
    return render_template(
        "admin/servicepoints.html",
        clinics=clinics,
        rooms=rooms,
        destinations=dests,
        default_clinics=DEFAULT_CLINICS,
        default_rooms=DEFAULT_ROOMS,
        default_destinations=DEFAULT_DESTINATIONS,
    )


# ------------------------------------------------------------------ clinics
@bp.post("/clinics/create")
@require_role(*SUPER)
def clinic_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    desc = (request.form.get("description") or "").strip()[:300]
    if not code or not name:
        flash("Clinic code and name are required.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    existing = db.session.query(ServiceClinic).filter_by(org_id=current_user.org_id, code=code).first()
    if existing:
        flash(f"Clinic code {code} already exists — edit it instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    c = ServiceClinic(org_id=current_user.org_id, code=code, name=name, description=desc, active=True)
    db.session.add(c)
    db.session.commit()
    flash(f"Clinic {name} ({code}) created.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#clinics")


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
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    # Check code clash
    other = (
        db.session.query(ServiceClinic)
        .filter(ServiceClinic.org_id == current_user.org_id, ServiceClinic.code == code, ServiceClinic.id != c.id)
        .first()
    )
    if other:
        flash(f"Another clinic already uses code {code}.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    c.name = name
    c.code = code
    c.description = desc
    c.updated_at = now_naive()
    db.session.commit()
    flash(f"Clinic {name} updated.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#clinics")


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
    return redirect(url_for("servicepoints_admin.overview") + "#clinics")


@bp.post("/clinics/<int:cid>/delete")
@require_role(*SUPER)
def clinic_delete(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    # Block if used
    from ..models import DoctorSession, PatientVisit

    if db.session.query(DoctorSession).filter_by(org_id=c.org_id, clinic=c.code).first():
        flash(f"Cannot delete {c.code} — used in doctor sessions. Suspend instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    if db.session.query(PatientVisit).filter_by(org_id=c.org_id, clinic=c.code).first():
        flash(f"Cannot delete {c.code} — used in patient visits. Suspend instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#clinics")
    # Delete shortlist links first
    from ..models import ClinicDestination

    db.session.query(ClinicDestination).filter_by(clinic_id=c.id).delete()
    db.session.delete(c)
    db.session.commit()
    flash(f"Clinic {c.name} deleted.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#clinics")


# ------------------------------------------------------------------ rooms
@bp.post("/rooms/create")
@require_role(*SUPER)
def room_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    clinic_id = request.form.get("clinic_id", type=int)
    if not code or not name:
        flash("Room code and name required.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
    existing = db.session.query(ConsultingRoom).filter_by(org_id=current_user.org_id, code=code).first()
    if existing:
        flash(f"Room code {code} already exists.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
    if clinic_id:
        cl = db.session.get(ServiceClinic, clinic_id)
        if not cl or cl.org_id != current_user.org_id:
            clinic_id = None
    r = ConsultingRoom(
        org_id=current_user.org_id, code=code, name=name, clinic_id=clinic_id, active=True
    )
    db.session.add(r)
    db.session.commit()
    flash(f"Room {name} ({code}) created.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#rooms")


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
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
    other = (
        db.session.query(ConsultingRoom)
        .filter(ConsultingRoom.org_id == current_user.org_id, ConsultingRoom.code == code, ConsultingRoom.id != r.id)
        .first()
    )
    if other:
        flash(f"Another room already uses code {code}.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
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
    return redirect(url_for("servicepoints_admin.overview") + "#rooms")


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
    return redirect(url_for("servicepoints_admin.overview") + "#rooms")


@bp.post("/rooms/<int:rid>/delete")
@require_role(*SUPER)
def room_delete(rid: int):
    r = db.session.get(ConsultingRoom, rid)
    if not r or r.org_id != current_user.org_id:
        abort(404)
    from ..models import DoctorSession, PatientVisit

    if db.session.query(DoctorSession).filter_by(org_id=r.org_id, consulting_room=r.code).first():
        flash(f"Cannot delete {r.code} — used in sessions. Suspend instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
    if db.session.query(PatientVisit).filter_by(org_id=r.org_id, consulting_room=r.code).first():
        flash(f"Cannot delete {r.code} — used in visits. Suspend instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#rooms")
    db.session.delete(r)
    db.session.commit()
    flash(f"Room {r.name} deleted.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#rooms")


# ------------------------------------------------------------------ destinations
@bp.post("/destinations/create")
@require_role(*SUPER)
def dest_create():
    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    place = (request.form.get("place") or "").strip()[:200]
    desc = (request.form.get("description") or "").strip()[:300]
    if not code or not name:
        flash("Destination code and name required.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#destinations")
    existing = db.session.query(ServiceDestination).filter_by(org_id=current_user.org_id, code=code).first()
    if existing:
        flash(f"Destination code {code} already exists.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#destinations")
    d = ServiceDestination(
        org_id=current_user.org_id, code=code, name=name, place=place or name, description=desc, active=True
    )
    db.session.add(d)
    db.session.commit()
    flash(f"Destination {name} ({code}) created.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#destinations")


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
        return redirect(url_for("servicepoints_admin.overview") + "#destinations")
    other = (
        db.session.query(ServiceDestination)
        .filter(ServiceDestination.org_id == current_user.org_id, ServiceDestination.code == code, ServiceDestination.id != d.id)
        .first()
    )
    if other:
        flash(f"Another destination already uses code {code}.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#destinations")
    d.code = code
    d.name = name
    d.place = place or name
    d.description = desc
    d.updated_at = now_naive()
    db.session.commit()
    flash(f"Destination {name} updated.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#destinations")


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
    return redirect(url_for("servicepoints_admin.overview") + "#destinations")


@bp.post("/destinations/<int:did>/delete")
@require_role(*SUPER)
def dest_delete(did: int):
    d = db.session.get(ServiceDestination, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    from ..models import VisitOnward

    if db.session.query(VisitOnward).filter_by(org_id=d.org_id, destination=d.code).first():
        flash(f"Cannot delete {d.code} — used in patient routing. Suspend instead.", "error")
        return redirect(url_for("servicepoints_admin.overview") + "#destinations")
    # Remove shortlist links
    from ..models import ClinicDestination

    db.session.query(ClinicDestination).filter_by(destination_id=d.id).delete()
    db.session.delete(d)
    db.session.commit()
    flash(f"Destination {d.name} deleted.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#destinations")


# ------------------------------------------------------------------ clinic shortlists
@bp.get("/clinics/<int:cid>/shortlist")
@require_role(*SUPER)
def clinic_shortlist(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    dests = all_destinations(current_user.org_id)
    from ..models import ClinicDestination

    linked = {link.destination_id for link in db.session.query(ClinicDestination).filter_by(clinic_id=c.id).all()}
    return render_template("admin/clinic_shortlist.html", clinic=c, destinations=dests, linked=linked)


@bp.post("/clinics/<int:cid>/shortlist")
@require_role(*SUPER)
def clinic_shortlist_save(cid: int):
    c = db.session.get(ServiceClinic, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    dest_ids = request.form.getlist("destination_ids", type=int)
    from ..models import ClinicDestination, ServiceDestination

    # Delete existing
    db.session.query(ClinicDestination).filter_by(clinic_id=c.id).delete()
    for did in dest_ids:
        d = db.session.get(ServiceDestination, did)
        if d and d.org_id == current_user.org_id:
            db.session.add(ClinicDestination(org_id=current_user.org_id, clinic_id=c.id, destination_id=d.id))
    db.session.commit()
    if not dest_ids:
        flash(f"{c.name} shortlist cleared — doctors will now see ALL active destinations.", "success")
    else:
        flash(f"{c.name} shortlist updated — {len(dest_ids)} destinations.", "success")
    return redirect(url_for("servicepoints_admin.overview") + "#clinics")
