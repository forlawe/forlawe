"""Patient complaint portal (public, no login) + staff complaint management."""
from __future__ import annotations

import re

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user

from .. import notifications, qrgen, services
from ..audit import audit
from ..config import Config
from ..models import (Complaint, ComplaintCategory, ComplaintStatusHistory,
                      Department, Organization, QrLocation, db, now_naive)
from ..navigation import require_permission
from ..security import rate_limit, require_login, require_role, resolve_upload_path, save_upload
from .. import scoring

bp = Blueprint("complaints", __name__)

PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _default_org() -> Organization | None:
    """Tenant for this request (see services.current_org)."""
    from ..services import current_org
    return current_org()


# ================================================================ PUBLIC PORTAL
# The SHORT path is canonical (it is what posters, QR cards and word of mouth
# use), so it must be the endpoint's primary rule — url_for() builds the
# LAST-registered rule for an endpoint, and /complaint/portal used to win,
# changing the public URL patients see (F-024 follow-up). The long path stays
# as an alias through a tiny forwarding endpoint.
@bp.get("/complaint")
@rate_limit(limit=20, window=60.0)
def portal():
    org = _default_org()
    if not org:
        return render_template("error.html", code=503, message="System not configured yet."), 503
    loc_code = (request.args.get("loc") or "").strip().upper()
    qr_loc = db.session.query(QrLocation).filter_by(code=loc_code).first() if loc_code else None
    from ..patient_places import public_departments
    depts = public_departments(org.id)
    db.session.commit()
    categories = (db.session.query(ComplaintCategory)
                  .filter_by(org_id=org.id, active=True).order_by(ComplaintCategory.name).all())
    return render_template("complaint_portal.html", org=org, depts=depts, categories=categories,
                           qr_loc=qr_loc)


@bp.get("/complaint/portal")
@rate_limit(limit=20, window=60.0)
def portal_alias():
    """Long-hand alias for /complaint — same page, kept for old printed QR."""
    return portal()


@bp.post("/complaint/submit")
@rate_limit(limit=6, window=120.0)
def portal_submit():
    org = _default_org()
    if not org:
        abort(503)
    now = now_naive()

    # ------- idempotency: re-submitted form returns the original ticket (§41)
    idem = (request.form.get("idem") or "").strip()[:40]
    if idem:
        dup = db.session.query(Complaint).filter_by(org_id=org.id, idempotency_key=idem).first()
        if dup:
            return redirect(url_for("complaints.portal_thanks", ref=dup.ref))

    # ------- exactly five fields
    dept_id = request.form.get("department_id", type=int)
    category = (request.form.get("category") or "").strip()
    description = (request.form.get("description") or "").strip()
    phone = (request.form.get("phone") or "").strip().replace(" ", "").replace("-", "")
    contact_method = request.form.get("contact_method", "phone")
    if contact_method not in ("phone", "whatsapp", "either"):
        contact_method = "phone"
    # Anonymous complaints (staff-conduct issues are the highest-value signal and
    # go unreported when the patient must identify themselves).
    is_anonymous = request.form.get("anonymous") in ("1", "on", "true", "yes")
    consented = request.form.get("consent") in ("1", "on", "true", "yes")

    dept = db.session.get(Department, dept_id) if dept_id else None
    errors = []
    if not dept or dept.org_id != org.id:
        errors.append("Please select the department concerned.")
    if not category:
        errors.append("Please select a complaint category.")
    if len(description) < 10:
        errors.append("Please describe the complaint (at least 10 characters).")
    if len(description) > 4000:
        errors.append("Description is too long (maximum 4000 characters).")
    if is_anonymous:
        phone = ""                      # never store a number on an anonymous report
    elif not PHONE_RE.match(phone):
        errors.append("Please enter a valid phone number (digits only, e.g. 08012345678), "
                      "or tick 'Submit anonymously'.")
    if not is_anonymous and not consented:
        errors.append("Please tick the box to allow the hospital to use your contact "
                      "details to follow up on this complaint.")
    if errors:
        depts = db.session.query(Department).filter_by(org_id=org.id, active=True).all()
        categories = db.session.query(ComplaintCategory).filter_by(org_id=org.id, active=True).all()
        # preserve the QR location tag on re-render
        loc_code_err = (request.form.get("loc") or "").strip().upper()
        qr_loc_err = db.session.query(QrLocation).filter_by(code=loc_code_err).first() if loc_code_err else None
        for e in errors:
            flash(e, "error")
        return render_template("complaint_portal.html", org=org, depts=depts,
                               categories=categories, qr_loc=qr_loc_err,
                               form=request.form), 422

    # ------- optional evidence (field 5b) — validated upload
    attachment_path = None
    file = request.files.get("attachment")
    if file and file.filename:
        path, err = save_upload(file, "complaints", org_id=org.id)
        if not err:
            attachment_path = path

    # ------- QR location context
    loc_code = (request.form.get("loc") or "").strip().upper()
    qr_loc = db.session.query(QrLocation).filter_by(code=loc_code).first() if loc_code else None

    sla_hours = int(services.get_setting(org.id, "sla_hours") or 24)

    def _build():
        return Complaint(
            org_id=org.id,
            ref=services.next_complaint_ref(org, now),
            idempotency_key=idem or None,
            department_id=dept.id,
            category=category,
            description=description,
            phone=phone or "anonymous",
            contact_method=contact_method,
            is_anonymous=is_anonymous,
            consent_at=None if is_anonymous else now,
            attachment_path=attachment_path,
            source="qr" if qr_loc else "link",
            qr_location_id=qr_loc.id if qr_loc else None,
            status="NEW",
            sla_hours=sla_hours,
            sla_deadline_at=scoring.sla_deadline(now, sla_hours),
        )

    try:
        c, c_created = services.insert_with_unique_ref(
            _build,
            idem_lookup=(lambda: db.session.query(Complaint)
                         .filter_by(org_id=org.id, idempotency_key=idem).first()) if idem else None)
    except Exception:
        db.session.rollback()
        flash("The system is very busy right now. Your complaint was NOT lost — please press submit again.",
              "error")
        return redirect(url_for("complaints.portal"))
    if not c_created:
        return redirect(url_for("complaints.portal_thanks", ref=c.ref))
    ack = notifications.patient_update_text("received", org.name, c.ref)
    db.session.add(ComplaintStatusHistory(complaint_id=c.id, from_status=None, to_status="NEW",
                                          note="Submitted via public portal",
                                          patient_message=ack))
    audit("COMPLAINT_SUBMITTED", "complaint", c.id,
          {"ref": c.ref, "dept": dept.name, "category": category, "source": c.source}, org_id=org.id)

    # ------- automatic routing: Admin Manager on duty + affected HOD
    duty = services.on_duty(org.id, now.date())
    hod = services.route_hod(dept)
    ctx = {"ref": c.ref, "dept": dept.name, "category": category, "sla": sla_hours,
           "hospital": org.name}
    if duty:
        notifications.notify(org.id, duty, "complaint_new_admin", ctx, channels=["inapp", "whatsapp"],
                             entity_type="complaint", entity_id=c.id)
    else:
        for am in notifications.admin_managers(org.id):
            notifications.notify(org.id, am, "complaint_new_admin", ctx, channels=["inapp"],
                                 entity_type="complaint", entity_id=c.id)
    if hod:
        notifications.notify(org.id, hod, "complaint_new_hod", ctx, channels=["inapp", "whatsapp", "email"],
                             entity_type="complaint", entity_id=c.id)
    db.session.commit()
    notifications.notify_complaint_patient(org, c, "received")
    return redirect(url_for("complaints.portal_thanks", ref=c.ref))


@bp.get("/complaint/thanks")
def portal_thanks():
    ref = request.args.get("ref", "")
    org = _default_org()
    complaint = db.session.query(Complaint).filter_by(ref=ref).first() if ref else None
    ack = None
    if complaint:
        for h in reversed(list(complaint.history or [])):
            if h.patient_message:
                ack = h.patient_message
                break
        if not ack:
            ack = notifications.patient_update_text("received", org.name if org else "The hospital", ref)
    return render_template("complaint_thanks.html", ref=ref, org=org, complaint=complaint, ack=ack)


@bp.get("/complaint/status")
def portal_status():
    """Anonymous status check with reference number + phone (no account needed) — phone required."""
    ref = (request.args.get("ref") or "").strip()
    phone = (request.args.get("phone") or "").strip().replace(" ", "")
    complaint = None
    error = None
    if ref:
        # SECURITY: ref is sequential (ORG-CMP-YYYY-000001) — must require phone to prevent
        # enumeration of complaints (patient linkage). Anonymous complaints use phone="anonymous"
        # and cannot be checked via this portal (by design).
        if not phone or len(phone) < 7:
            error = "Please enter both reference number and phone number to verify."
        else:
            q = db.session.query(Complaint).filter(Complaint.ref.ilike(ref))
            q = q.filter(Complaint.phone == phone)
            complaint = q.first()
            if not complaint:
                error = "No complaint found for that reference and phone number."
    return render_template("complaint_status.html", complaint=complaint, error=error,
                           ref=ref, phone=phone)


# ================================================================ QR CODES
@bp.get("/lang/<code>")
def set_lang(code: str):
    """Public language switch (session cookie), then return to the page you came from."""
    from flask import session as flask_session
    if code in ("en", "yo", "ha", "ig"):
        flask_session["lang"] = code
    from ..security import safe_next
    back = safe_next(request.args.get("next") or request.referrer, "/complaint")
    return redirect(back)


@bp.get("/complaint/qr/<code>.png")
def qr_png(code: str):
    loc = db.session.query(QrLocation).filter_by(code=code.upper()).first()
    if not loc:
        abort(404)
    url = f"{Config.PUBLIC_BASE_URL}/complaint?loc={loc.code}"
    png = qrgen.make_qr_png(url)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


# ================================================================ STAFF MANAGEMENT
def _staff_only():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))
    return None


@bp.get("/complaints")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
def staff_queue():
    from .. import roles as R
    q = db.session.query(Complaint).filter(Complaint.org_id == current_user.org_id)

    # SCOPE. "HOD and Staff should see only action and happening relating to
    # their department/unit/Station only." Applied HERE, in the query, not in
    # the template — a filter applied only on the page still ships every other
    # department's complaints down the wire to the phone.
    visible = R.visible_department_ids(current_user)
    if visible is not None:
        # A person with no department gets an empty list rather than
        # everything. Failing OPEN here would have quietly undone the whole
        # feature the first time somebody's record was incomplete.
        q = q.filter(Complaint.department_id.in_(visible or [-1]))
    status = request.args.get("status")
    if status in ("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "ESCALATED"):
        q = q.filter(Complaint.status == status)
    elif status == "OPEN":
        q = q.filter(Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED")))
    dept = request.args.get("dept", type=int)
    if dept:
        q = q.filter(Complaint.department_id == dept)
    escalated = request.args.get("escalated")
    if escalated == "1":
        q = q.filter(Complaint.escalated.is_(True))
    sla = request.args.get("sla")
    now = now_naive()
    if sla == "breached":
        q = q.filter(Complaint.status.notin_(("RESOLVED", "CLOSED")), Complaint.sla_deadline_at < now)
    qstr = request.args.get("q", "").strip()
    if qstr:
        like = f"%{qstr}%"
        q = q.filter(db.or_(Complaint.ref.ilike(like), Complaint.description.ilike(like),
                              Complaint.phone.ilike(like)))
    items = q.order_by(Complaint.submitted_at.desc()).limit(200).all()
    dq = db.session.query(Department).filter_by(org_id=current_user.org_id, active=True)
    if visible is not None:
        dq = dq.filter(Department.id.in_(visible or [-1]))
    depts = dq.all()
    return render_template("complaint_queue.html", items=items, depts=depts, args=request.args,
                           now=now, scope_note=R.scope_note(current_user))


@bp.get("/complaints/<int:cid>")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
def staff_detail(cid: int):
    from .. import escalation
    from .. import roles as R
    c = db.session.get(Complaint, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    # Typing the id of another department's complaint must not work either.
    # Hiding it from the list is presentation; THIS is the security + audit.
    if not R.can_see_department_audit(current_user, c.department_id, action=f"VIEW_COMPLAINT_{cid}"):
        abort(403)
    hod = services.route_hod(c.department)
    may_escalate = escalation.may_escalate(current_user, c)
    return render_template("complaint_detail.html", c=c, hod=hod, now=now_naive(),
                           can_act=current_user.role in ("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER")
                           or (hod and hod.id == current_user.id),
                           may_escalate=may_escalate,
                           authorities=escalation.authorities(c.org_id) if may_escalate else [],
                           hours_left=escalation.hours_left(c))


@bp.post("/complaints/<int:cid>/escalate")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER", "HOD")
def staff_escalate(cid: int):
    """An HOD raises it to higher authority BEFORE the clock runs out.

    Deliberate escalation is a decision, not a failure. The audit trail records
    it as a separate action from an automatic timeout so an HOD who spots a
    problem early is never scored as one who let it lapse — otherwise every HOD
    quickly learns to sit on problems until the deadline.
    """
    from .. import escalation
    c = db.session.get(Complaint, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    if not escalation.may_escalate(current_user, c):
        abort(403)

    to_id = request.form.get("to_user_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    from ..models import User as _User
    target = db.session.get(_User, to_id) if to_id else None
    if target is None or target.org_id != c.org_id or target.role not in escalation.AUTHORITY_LADDER:
        flash("Choose who you are escalating this to.", "error")
        return redirect(url_for("complaints.staff_detail", cid=cid))
    if len(reason) < 10:
        flash("Say in one or two lines why this needs a higher authority. "
              "The person receiving it needs to know what to do.", "error")
        return redirect(url_for("complaints.staff_detail", cid=cid))

    result = escalation.escalate(c, by_user=current_user, to_user=target, reason=reason)
    db.session.commit()
    if result["in_time"]:
        flash(f"Escalated to {result['to']} with {result['hours_left']} hours still "
              f"on the clock. They have been notified and will hear it announced.",
              "success")
    else:
        flash(f"Escalated to {result['to']}. Note that this complaint was already "
              f"past its deadline — the record shows that honestly.", "success")
    return redirect(url_for("complaints.staff_detail", cid=cid))


@bp.post("/complaints/<int:cid>/update")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER", "HOD")
def staff_update(cid: int):
    from .. import roles as R
    c = db.session.get(Complaint, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    if not R.can_see_department_audit(current_user, c.department_id, action=f"UPDATE_COMPLAINT_{cid}"):
        abort(403)
    action = request.form.get("action_type")
    old_status = c.status

    extra = ""
    event = None
    if action == "acknowledge":
        if c.status != "NEW":
            flash("Only NEW complaints can be acknowledged.", "error")
            return redirect(url_for("complaints.staff_detail", cid=cid))
        c.status = "ACKNOWLEDGED"
        c.acknowledged_at = now_naive()
        note = "Acknowledged"
        event = "acknowledged"
    elif action == "progress":
        action_taken = (request.form.get("action_taken") or "").strip()
        if not action_taken:
            flash("Please describe the action taken.", "error")
            return redirect(url_for("complaints.staff_detail", cid=cid))
        c.status = "IN_PROGRESS"
        c.action_taken = (c.action_taken + "\n" if c.action_taken else "") + \
            f"[{now_naive():%d %b %H:%M}] {action_taken}"
        note = "Action recorded"
        extra = action_taken[:200]
        event = "progress"
    elif action == "resolve":
        notes = (request.form.get("resolution_notes") or "").strip()
        if not notes:
            flash("Resolution notes are required.", "error")
            return redirect(url_for("complaints.staff_detail", cid=cid))
        c.status = "RESOLVED"
        c.resolution_notes = notes
        c.resolved_at = now_naive()
        note = "Resolved"
        extra = notes[:200]
        event = "resolved"
    elif action == "close":
        if c.status != "RESOLVED":
            flash("Only RESOLVED complaints can be closed.", "error")
            return redirect(url_for("complaints.staff_detail", cid=cid))
        c.status = "CLOSED"
        note = "Closed"
        event = "closed"
    else:
        flash("Unknown action.", "error")
        return redirect(url_for("complaints.staff_detail", cid=cid))

    org = db.session.get(Organization, c.org_id)
    pmsg = notifications.patient_update_text(event, org.name, c.ref, extra) if event else None
    db.session.add(ComplaintStatusHistory(complaint_id=c.id, from_status=old_status,
                                          to_status=c.status, note=note, user_id=current_user.id,
                                          patient_message=pmsg))
    audit("COMPLAINT_UPDATED", "complaint", c.id,
          {"old_status": old_status, "new_status": c.status, "note": note})
    db.session.commit()
    if event:
        notifications.notify_complaint_patient(org, c, event, extra)
    flash(f"Complaint updated to {c.status}. The patient has been notified.", "success")
    return redirect(url_for("complaints.staff_detail", cid=cid))


@bp.post("/complaints/<int:cid>/extend-sla")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO")
def staff_extend_sla(cid: int):
    """SLA extension is allowed but ALWAYS recorded as an audit event (never silently reset)."""
    if current_user.role not in ("SUPER_ADMIN", "MD_CEO"):
        abort(403)
    c = db.session.get(Complaint, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    hours = request.form.get("hours", type=int) or 0
    reason = (request.form.get("reason") or "").strip()
    if hours <= 0 or hours > 168 or not reason:
        flash("Provide a valid extension (1–168 hours) and a reason.", "error")
        return redirect(url_for("complaints.staff_detail", cid=cid))
    from datetime import timedelta
    old_deadline = c.sla_deadline_at
    # an extension may only ever ADD time — never shorten the deadline
    candidate = old_deadline + timedelta(hours=hours)
    c.sla_deadline_at = max(candidate, now_naive() + timedelta(hours=hours))
    c.sla_extended_at = now_naive()
    audit("COMPLAINT_SLA_EXTENDED", "complaint", c.id,
          {"old_deadline": str(old_deadline), "new_deadline": str(c.sla_deadline_at),
           "hours": hours, "reason": reason})
    db.session.commit()
    flash("SLA extended. The extension has been recorded in the audit trail.", "success")
    return redirect(url_for("complaints.staff_detail", cid=cid))


@bp.get("/complaints/<int:cid>/attachment")
@require_login
@require_permission("complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
def staff_attachment(cid: int):
    c = db.session.get(Complaint, cid)
    if not c or c.org_id != current_user.org_id or not c.attachment_path:
        abort(404)
    from .. import storage
    try:
        return storage.send(c.attachment_path)
    except FileNotFoundError:
        abort(404)
