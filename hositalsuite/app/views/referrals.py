"""Public referral landing + staff referral analytics (spec §14)."""
from __future__ import annotations

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from .. import qrgen, referrals as engine
from ..audit import audit
from ..models import Department, Organization, Referral, db
from ..navigation import require_permission
from ..security import rate_limit, require_login, require_role

bp = Blueprint("referrals", __name__)


def _default_org() -> Organization | None:
    """Tenant for this request (see services.current_org)."""
    from ..services import current_org
    return current_org()


# ================================================================ PUBLIC
@bp.get("/r/<code>")
@rate_limit(limit=40, window=60.0)
def landing(code: str):
    org = _default_org()
    if not org:
        abort(503)
    row = engine.find_any(org.id, code)
    if not row:
        return render_template("error.html", code=404,
                               message="This referral link is not valid."), 404
    if not row.active:
        return render_template("error.html", code=404,
                               message="This referral link is no longer active."), 404
    engine.record_click_once(row)
    db.session.commit()
    return render_template("referral_landing.html", org=org, referral=row,
                           share_url=engine.share_url(row))


@bp.get("/r/<code>.png")
@rate_limit(limit=40, window=60.0)
def qr_png(code: str):
    org = _default_org()
    if not org:
        abort(503)
    row = engine.find_any(org.id, code)
    if not row:
        abort(404)
    png = qrgen.make_qr_png(engine.share_url(row))
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


# ================================================================ STAFF — referral analytics contain patient flow, not PII but staff-only
@bp.get("/referrals")
@require_login
@require_permission("referrals")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER")
def staff_list():
    org = db.session.get(Organization, current_user.org_id)
    hospital = engine.ensure_hospital_referral(org)
    db.session.commit()
    days = request.args.get("days", type=int) or 30
    days = max(7, min(365, days))
    stats = engine.analytics(org.id, days=days)
    depts = (db.session.query(Department)
             .filter_by(org_id=org.id, active=True).order_by(Department.name).all())
    return render_template(
        "referrals_staff.html",
        org=org,
        hospital=hospital,
        share_url=engine.share_url(hospital),
        wa=engine.whatsapp_share_url(org.name, engine.share_url(hospital)),
        stats=stats,
        depts=depts,
        can_manage=current_user.role in ("SUPER_ADMIN", "MD_CEO"),
    )


@bp.post("/referrals/create")
@require_role("SUPER_ADMIN", "MD_CEO")
def staff_create():
    org = db.session.get(Organization, current_user.org_id)
    note = (request.form.get("note") or "").strip()
    if len(note) < 2:
        flash("Please give this link a short name (e.g. Ward A poster).", "error")
        return redirect(url_for("referrals.staff_list"))
    dept_id = request.form.get("department_id", type=int)
    dept = db.session.get(Department, dept_id) if dept_id else None
    if dept and dept.org_id != org.id:
        dept = None
    engine.issue_staff_referral(org, note=note,
                                department_id=dept.id if dept else None,
                                created_by_id=current_user.id)
    db.session.commit()
    flash("New share-link created. Print the QR or copy the link.", "success")
    return redirect(url_for("referrals.staff_list"))


@bp.post("/referrals/<int:rid>/toggle")
@require_role("SUPER_ADMIN", "MD_CEO")
def staff_toggle(rid: int):
    row = db.session.get(Referral, rid)
    if not row or row.org_id != current_user.org_id:
        abort(404)
    row.active = not row.active
    audit("REFERRAL_TOGGLED", "referral", row.id,
          {"code": row.code, "active": row.active})
    db.session.commit()
    flash(f"Link {row.code} is now {'active' if row.active else 'turned off'}.", "success")
    return redirect(url_for("referrals.staff_list"))
