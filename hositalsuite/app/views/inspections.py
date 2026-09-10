"""Inspection views: daily inspection wizard, list/detail, amendments, verification."""
from __future__ import annotations

import os

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user

from .. import (notifications, pdfgen, rosterdata, scoring, services,
                whatsapp)
from ..audit import audit
from ..config import Config
from ..inspection_areas import INSPECTION_AREAS, match_department
from ..models import (CorrectiveAction, Department, Inspection,
                      InspectionScore, Organization, ReportFile,
                      User, db, new_code, now_naive)
from ..navigation import require_permission
from ..security import require_login, require_role, save_upload

bp = Blueprint("inspections", __name__)


def _my_org():
    return db.session.get(Organization, current_user.org_id)


def _admin_manager_page():
    """One Admin Manager screen: today's inspection + history. No sub-menus."""
    now = now_naive()
    today = now.date()
    duty = services.on_duty(current_user.org_id, today)
    is_on_duty = duty is not None and duty.id == current_user.id
    existing = (db.session.query(Inspection)
                .filter_by(org_id=current_user.org_id, duty_date=today,
                           inspector_id=current_user.id, status="SUBMITTED").first())
    depts = (db.session.query(Department)
             .filter_by(org_id=current_user.org_id, active=True).order_by(Department.name).all())
    gps_mode = services.get_setting(current_user.org_id, "gps_mode")
    q = (db.session.query(Inspection)
         .filter_by(org_id=current_user.org_id, status="SUBMITTED"))
    dept = request.args.get("dept", type=int)
    inspector = request.args.get("inspector", type=int)
    rating = request.args.get("rating")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if dept:
        q = q.filter(Inspection.department_id == dept)
    if inspector:
        q = q.filter(Inspection.inspector_id == inspector)
    if rating:
        q = q.filter(Inspection.rating == rating)
    if date_from:
        from datetime import date as _d
        try:
            q = q.filter(Inspection.duty_date >= _d.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        from datetime import date as _d
        try:
            q = q.filter(Inspection.duty_date <= _d.fromisoformat(date_to))
        except ValueError:
            pass
    items = q.order_by(Inspection.duty_date.desc(), Inspection.submitted_at.desc()).limit(300).all()
    inspectors = db.session.query(User).filter_by(org_id=current_user.org_id, role="ADMIN_MANAGER").all()
    show_form = current_user.role in ("ADMIN_MANAGER", "SUPER_ADMIN")
    return render_template(
        "admin_manager.html", duty=duty, is_on_duty=is_on_duty, existing=existing,
        depts=depts, gps_mode=gps_mode, criteria=scoring.CRITERIA, today=today,
        items=items, inspectors=inspectors, args=request.args, show_form=show_form,
        ratings=["EXCELLENT", "GOOD", "FAIR / NEEDS IMPROVEMENT", "POOR", "CRITICAL"],
        device=request.headers.get("User-Agent", "")[:280])


# ------------------------------------------------------------------ Admin Manager (single page)
@bp.get("/admin-manager")
@bp.get("/inspections/new")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def inspection_new():
    return _admin_manager_page()


@bp.post("/inspections/departments/<int:dept_id>/children")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def department_children(dept_id: int):
    # v1.7.18: ADMIN_MANAGER day-on-duty
    if getattr(current_user, "role", "") == "ADMIN_MANAGER":
        from ..security import is_admin_manager_on_duty
        if not is_admin_manager_on_duty(current_user):
            abort(403, description="Only on-duty Admin Manager can access.")
    dept = db.session.get(Department, dept_id)
    if not dept or dept.org_id != current_user.org_id:
        abort(404)
    out = {"sections": []}
    for s in dept.sections:
        out["sections"].append({
            "id": s.id, "name": s.name,
            "units": [{"id": u.id, "name": u.name} for u in s.units],
        })
    return jsonify(out)


@bp.post("/inspections/submit")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def inspection_submit():
    now = now_naive()
    today = now.date()
    org = _my_org()
    api_mode = request.is_json

    def fail(msg: str):
        if api_mode:
            return jsonify(ok=False, error=msg), 422
        flash(msg, "error")
        return redirect(url_for("inspections.inspection_new"))

    # --- duty guard: the rostered Admin Manager is the primary responsible person
    duty = services.on_duty(current_user.org_id, today)
    if duty and duty.id != current_user.id and not current_user.is_super:
        return fail(f"Today's inspection is assigned to {duty.name}. "
                    "Only the Admin Manager on duty submits today's inspection.")

    # --- duplicate guard: one submitted inspection per inspector per day
    dup = (db.session.query(Inspection)
           .filter_by(org_id=current_user.org_id, duty_date=today,
                      inspector_id=current_user.id, status="SUBMITTED").first())
    if dup:
        if api_mode:
            return jsonify(ok=False, error="duplicate", ref=dup.ref), 409
        flash(f"You already submitted today's inspection ({dup.ref}). "
              "Use the amendment process if a correction is needed.", "error")
        return redirect(url_for("inspections.inspection_detail", insp_id=dup.id))

    # --- parse payload (supports both form POST and JSON offline-sync)
    payload = request.get_json(silent=True) if request.is_json else None
    form = payload if payload else request.form

    dept_id = int(form.get("department_id") or 0)
    section_id = int(form.get("section_id") or 0) or None
    unit_id = int(form.get("unit_id") or 0) or None
    dept = db.session.get(Department, dept_id)
    if not dept or dept.org_id != current_user.org_id:
        return fail("Please select a valid department.")

    scores: dict[int, int] = {}
    for no in range(1, 6):
        raw = form.get(f"score_{no}")
        try:
            scores[no] = int(raw)
        except (TypeError, ValueError):
            return fail(f"Please score every criterion (1–5). Criterion {no} is missing.")

    errors = scoring.validate_scores(scores)
    if errors:
        return fail(" ".join(errors))

    # --- mandatory explanations for scores 1 or 2
    explanations: dict[int, str] = {}
    for no in range(1, 6):
        expl = (form.get(f"explanation_{no}") or "").strip()
        if scoring.explanation_required(scores[no]) and not expl:
            return fail(f"An explanation is REQUIRED for criterion {no} "
                        f"({scoring.CRITERIA[no]['title']}) because the score is {scores[no]}.")
        explanations[no] = expl

    # --- Admin Manager's overall closing comment (optional, voice-to-text capable)
    final_comment = (form.get("final_comment") or "").strip()[:4000]

    # --- started time: recorded when the inspector opened the form (client-sent,
    # clamped server-side to today and never in the future)
    started_at = now
    try:
        raw_ts = form.get("started_ts")
        if raw_ts not in (None, ""):
            from datetime import datetime as _dt
            candidate = _dt.fromtimestamp(float(raw_ts) / 1000.0)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if day_start <= candidate <= now:
                started_at = candidate
    except (TypeError, ValueError, OSError):
        pass

    gps_mode = services.get_setting(current_user.org_id, "gps_mode")
    lat = form.get("lat", type=float) if hasattr(form, "get") and not isinstance(form, dict) else None
    lng = form.get("lng", type=float) if hasattr(form, "get") and not isinstance(form, dict) else None
    if isinstance(form, dict):
        lat = form.get("lat")
        lng = form.get("lng")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            lat = lng = None
    if gps_mode == "mandatory" and (lat is None or lng is None):
        return fail("GPS location is mandatory for inspections at this hospital. "
                    "Please enable location and try again.")

    evald = scoring.evaluate(scores)

    # upload evidence first (file side-effects must not repeat on ref-collision retry)
    evidence_paths = {}
    for no in range(1, 6):
        evidence_paths[no] = None
        if not api_mode:
            ev = request.files.get(f"evidence_{no}")
            if ev and ev.filename:
                path, err = save_upload(ev, "inspections")
                if not err:
                    evidence_paths[no] = path

    def _build_insp():
        obj = Inspection(
            org_id=current_user.org_id,
            ref=services.next_inspection_ref(org, now),
            verify_code=new_code(10),
            inspector_id=current_user.id,
            duty_date=today,
            department_id=dept_id,
            section_id=section_id,
            unit_id=unit_id,
            status="SUBMITTED",
            started_at=started_at,
            submitted_at=now,
            total_score=evald["total"],
            percent=evald["percent"],
            rating=evald["rating"],
            critical_count=evald["critical_count"],
            poor_count=evald["poor_count"],
            gps_mode=gps_mode,
            lat=lat,
            lng=lng,
            gps_captured=(lat is not None and lng is not None),
            device_info=request.headers.get("User-Agent", "")[:280],
            final_comment=final_comment or None,
        )
        db.session.add(obj)
        db.session.flush()
        for no in range(1, 6):
            db.session.add(InspectionScore(inspection_id=obj.id, criterion_no=no,
                                           score=scores[no], explanation=explanations[no] or None,
                                           evidence_path=evidence_paths[no]))
        return obj

    try:
        insp, _created = services.insert_with_unique_ref(_build_insp)
    except Exception:
        db.session.rollback()
        return fail("The system is very busy right now. Your inspection was NOT saved — please submit again.")
    db.session.flush()

    audit("INSPECTION_SUBMITTED", "inspection", insp.id,
          {"ref": insp.ref, "total": evald["total"], "rating": evald["rating"],
           "scores": scores}, org_id=org.id)
    db.session.commit()

    # --- PDF generation (failure must not break submission)
    try:
        from .. import storage
        scores_by_no = {s.criterion_no: s for s in insp.scores}
        pdf_path = f"reports/{insp.ref}.pdf"
        verify_url = f"{Config.PUBLIC_BASE_URL}/verify/{insp.verify_code}"
        storage.build_pdf(pdfgen.build_inspection_pdf, pdf_path,
                          org, insp, scores_by_no, verify_url,
                          dest_pos=3, org_id=org.id)
        insp.pdf_path = pdf_path
        db.session.add(ReportFile(org_id=org.id, kind="inspection",
                                  title=f"Inspection {insp.ref} — {dept.name}",
                                  entity_type="inspection", entity_id=insp.id,
                                  path=pdf_path, verify_code=insp.verify_code,
                                  created_by_id=current_user.id))
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        audit("PDF_GENERATION_FAILED", "inspection", insp.id, {"error": str(exc)[:200]}, org_id=org.id)
        db.session.commit()
        if not api_mode:
            flash("Inspection saved, but PDF generation failed. Administrators have been notified.", "error")

    # --- WhatsApp delivery to MD/CEO (official Business API; sandbox locally)
    md_number = services.get_setting(org.id, "whatsapp_md_number") or ""
    summary = (f"Daily Inspection Report\n"
               f"{org.name}\n"
               f"Ref: {insp.ref}\n"
               f"Dept: {dept.name}\n"
               f"Date: {today.strftime('%d %b %Y')}\n"
               f"By: {current_user.name}\n"
               f"Total: {evald['total']}/25 ({evald['percent']}%)\n"
               f"Rating: {evald['rating']}")
    targets = [md for md in notifications.md_ceos(org.id)]
    for md in targets:
        number = md.phone or md_number
        if number:
            whatsapp.queue_message(org.id, number, summary, kind="report",
                                   media_path=insp.pdf_path, entity_type="inspection",
                                   entity_id=insp.id, to_user_id=md.id)
    if not targets and md_number:
        whatsapp.queue_message(org.id, md_number, summary, kind="report",
                               media_path=insp.pdf_path, entity_type="inspection", entity_id=insp.id)
    from ..tasks import dispatch_delivery
    dispatch_delivery()   # §39 — never block the submission on third-party APIs

    # --- management notifications + executive alerts
    ctx = {"ref": insp.ref, "dept": dept.name, "name": current_user.name,
           "rating": evald["rating"], "total": f"{evald['total']}", "hospital": org.name}
    for md in targets:
        notifications.notify(org.id, md, "inspection_submitted", ctx, channels=["inapp"],
                             entity_type="inspection", entity_id=insp.id)
    threshold = int(services.get_setting(org.id, "multiple_two_threshold") or 2)
    alerts = scoring.alert_conditions(scores, multiple_two_threshold=threshold)
    if alerts:
        for md in targets + notifications.super_admins(org.id):
            notifications.notify(org.id, md, "critical_score", ctx, channels=["inapp"],
                                 entity_type="inspection", entity_id=insp.id)
        audit("EXECUTIVE_ALERT", "inspection", insp.id, {"alerts": alerts}, org_id=org.id)

    if api_mode:
        return jsonify(ok=True, ref=insp.ref, rating=evald["rating"], total=evald["total"],
                       percent=evald["percent"], id=insp.id,
                       detail_url=url_for("inspections.inspection_detail", insp_id=insp.id))
    flash(f"Inspection {insp.ref} submitted. Overall rating: {evald['rating']} "
          f"({evald['total']}/25).", "success")
    return redirect(url_for("inspections.inspection_detail", insp_id=insp.id))


# ------------------------------------------------------------------ list / detail — Admin Manager only, patient-adjacent data
@bp.get("/inspections")
@require_login
@require_permission("inspections")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "MD_CEO")
def inspection_list():
    return _admin_manager_page()


@bp.get("/inspections/<int:insp_id>")
@require_login
@require_permission("inspections")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR")
def inspection_detail(insp_id: int):
    insp = db.session.get(Inspection, insp_id)
    if not insp or insp.org_id != current_user.org_id:
        abort(404)
    scores_by_no = {s.criterion_no: s for s in insp.scores}
    cas = (db.session.query(CorrectiveAction)
           .filter_by(org_id=current_user.org_id, source_type="inspection", source_id=insp.id).all())
    trend_prev = (db.session.query(Inspection)
                  .filter_by(org_id=current_user.org_id, department_id=insp.department_id,
                             status="SUBMITTED")
                  .filter(Inspection.id != insp.id, Inspection.submitted_at < (insp.submitted_at or now_naive()))
                  .order_by(Inspection.submitted_at.desc()).first())
    trend = scoring.trend(insp.total_score, trend_prev.total_score if trend_prev else None)
    can_amend = current_user.is_super or (
        insp.status == "SUBMITTED" and current_user.is_am and insp.inspector_id == current_user.id)
    users = (db.session.query(User).filter_by(org_id=current_user.org_id, active=True)
             .order_by(User.name).all())
    return render_template("inspection_detail.html", insp=insp, scores=scores_by_no,
                           cas=cas, trend=trend, criteria=scoring.CRITERIA, can_amend=bool(can_amend),
                           users=users)


@bp.get("/inspections/<int:insp_id>/pdf")
@require_login
@require_permission("inspections")
@require_role("SUPER_ADMIN", "ADMIN_MANAGER", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR")
def inspection_pdf(insp_id: int):
    insp = db.session.get(Inspection, insp_id)
    if not insp or insp.org_id != current_user.org_id:
        abort(404)
    from .. import storage
    if not insp.pdf_path or not storage.exists(insp.pdf_path):
        flash("The PDF for this inspection is not available yet.", "error")
        return redirect(url_for("inspections.inspection_detail", insp_id=insp_id))
    audit("PDF_DOWNLOADED", "inspection", insp.id, {"ref": insp.ref})
    db.session.commit()
    return storage.send(insp.pdf_path, as_attachment=True,
                        download_name=f"{insp.ref}.pdf", mimetype="application/pdf")


# ------------------------------------------------------------------ amendment
@bp.post("/inspections/<int:insp_id>/amend")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def inspection_amend(insp_id: int):
    # v1.7.18: ADMIN_MANAGER only on duty
    if getattr(current_user, "role", "") == "ADMIN_MANAGER":
        from ..security import is_admin_manager_on_duty
        if not is_admin_manager_on_duty(current_user):
            abort(403, description="Only on-duty Admin Manager can amend.")
    """Controlled amendment: the original is locked & superseded, a new record is created."""
    insp = db.session.get(Inspection, insp_id)
    if not insp or insp.org_id != current_user.org_id:
        abort(404)
    if insp.status != "SUBMITTED":
        flash("Only a submitted inspection can be amended.", "error")
        return redirect(url_for("inspections.inspection_detail", insp_id=insp_id))
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("A reason is required to amend an inspection.", "error")
        return redirect(url_for("inspections.inspection_detail", insp_id=insp_id))

    now = now_naive()
    new_scores = {}
    for no in range(1, 6):
        raw = request.form.get(f"score_{no}")
        try:
            new_scores[no] = int(raw)
        except (TypeError, ValueError):
            flash(f"All five criteria must be re-scored. Criterion {no} missing.", "error")
            return redirect(url_for("inspections.inspection_detail", insp_id=insp_id))
    for no in range(1, 6):
        if scoring.explanation_required(new_scores[no]) and not (request.form.get(f"explanation_{no}") or "").strip():
            flash(f"Explanation required for criterion {no} (score {new_scores[no]}).", "error")
            return redirect(url_for("inspections.inspection_detail", insp_id=insp_id))

    evald = scoring.evaluate(new_scores)
    old = Inspection(
        org_id=insp.org_id, ref=insp.ref + "-SUP", verify_code=new_code(10),
        inspector_id=insp.inspector_id, duty_date=insp.duty_date,
        department_id=insp.department_id, section_id=insp.section_id, unit_id=insp.unit_id,
        status="SUPERSEDED", started_at=insp.started_at, submitted_at=insp.submitted_at,
        total_score=insp.total_score, percent=insp.percent, rating=insp.rating,
        critical_count=insp.critical_count, poor_count=insp.poor_count,
        gps_mode=insp.gps_mode, lat=insp.lat, lng=insp.lng, gps_captured=insp.gps_captured,
        device_info=insp.device_info)
    db.session.add(old)
    insp.status = "AMENDED"
    insp.amendment_of_id = old.id
    # apply new scores to the live record
    for s in insp.scores:
        s.score = new_scores[s.criterion_no]
        s.explanation = (request.form.get(f"explanation_{s.criterion_no}") or "").strip() or None
    insp.total_score, insp.percent, insp.rating = evald["total"], evald["percent"], evald["rating"]
    insp.critical_count, insp.poor_count = evald["critical_count"], evald["poor_count"]
    insp.submitted_at = now
    insp.status = "SUBMITTED"
    audit("INSPECTION_AMENDED", "inspection", insp.id,
          {"reason": reason, "old_total": old.total_score, "new_total": evald["total"]})
    db.session.commit()
    flash("Amendment recorded. The original record is preserved in the audit trail.", "success")
    return redirect(url_for("inspections.inspection_detail", insp_id=insp.id))


# ------------------------------------------------------------------ public verification
@bp.get("/verify/<code>")
def verify(code: str):
    insp = db.session.query(Inspection).filter_by(verify_code=code).first()
    if insp:
        org = db.session.get(Organization, insp.org_id)
        return render_template("verify.html", ok=True, kind="Inspection Report",
                               ref=insp.ref, org=org, date=insp.duty_date,
                               rating=insp.rating, total=insp.total_score,
                               submitted=insp.submitted_at)
    rf = db.session.query(ReportFile).filter_by(verify_code=code).first()
    if rf:
        org = db.session.get(Organization, rf.org_id)
        return render_template("verify.html", ok=True, kind=rf.kind.title() + " Report",
                               ref=rf.title, org=org, date=rf.created_at.date(),
                               rating=None, total=None, submitted=rf.created_at)
    return render_template("verify.html", ok=False), 404


# ================================================================ WALK-ROUND
# The Admin Manager does not inspect one department a day — he walks the whole
# hospital and scores every area he passes. This is that page: 24 self-contained
# collapsible cards, each with its own five scores, its own staff-on-duty list
# from the roster, and its own justification box that appears the moment a low
# score is given.
def _walk_areas(org_id: int, day):
    """Build the card list: area -> matched department -> who is on duty."""
    depts = (db.session.query(Department)
             .filter_by(org_id=org_id, active=True).order_by(Department.name).all())
    duty_map = rosterdata.on_duty_map(org_id, day)
    done = {r.department_id for r in db.session.query(Inspection)
            .filter_by(org_id=org_id, duty_date=day, status="SUBMITTED").all()
            if r.department_id}
    cards = []
    for key, label, _aliases in INSPECTION_AREAS:
        dept = match_department(key, depts)
        cards.append({
            "key": key,
            "label": label,
            "dept": dept,
            "dept_id": dept.id if dept else None,
            "on_duty": duty_map.get(dept.id, []) if dept else [],
            "done": bool(dept and dept.id in done),
        })
    return cards


@bp.get("/admin-manager/walk")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def walk_round():
    today = now_naive().date()
    duty = services.on_duty(current_user.org_id, today)
    return render_template(
        "admin_manager_walk.html",
        cards=_walk_areas(current_user.org_id, today),
        criteria=scoring.CRITERIA, today=today, duty=duty,
        gps_mode=services.get_setting(current_user.org_id, "gps_mode"))


@bp.post("/admin-manager/walk")
@require_role("ADMIN_MANAGER", "SUPER_ADMIN")
def walk_round_submit():
    """Save every area the manager actually scored. Blank cards are skipped.

    A walk-round is not all-or-nothing: if he inspected nine areas before being
    called away, those nine must save. Refusing the lot because the other
    fifteen are blank would lose real work and teach him not to trust the page.
    """
    now = now_naive()
    today = now.date()
    org = _my_org()

    duty = services.on_duty(current_user.org_id, today)
    if duty and duty.id != current_user.id and not current_user.is_super:
        flash(f"Today's inspection is assigned to {duty.name}.", "error")
        return redirect(url_for("inspections.walk_round"))

    depts = (db.session.query(Department)
             .filter_by(org_id=current_user.org_id, active=True).all())
    already = {r.department_id for r in db.session.query(Inspection)
               .filter_by(org_id=current_user.org_id, duty_date=today,
                          status="SUBMITTED").all() if r.department_id}

    saved, skipped, problems = [], [], []
    for key, label, _aliases in INSPECTION_AREAS:
        raw = [request.form.get(f"{key}_score_{n}") for n in range(1, 6)]
        if not any(v for v in raw):
            continue                                    # not inspected today
        if not all(v for v in raw):
            problems.append(f"{label}: please score all five criteria, or none.")
            continue

        dept = match_department(key, depts)
        if dept is None:
            problems.append(
                f"{label}: there is no matching department yet. Add it in "
                f"Admin → Structure, then score it.")
            continue
        if dept.id in already:
            skipped.append(label)
            continue

        try:
            scores = {n: int(raw[n - 1]) for n in range(1, 6)}
        except (TypeError, ValueError):
            problems.append(f"{label}: scores must be numbers from 1 to 5.")
            continue
        errs = scoring.validate_scores(scores)
        if errs:
            problems.append(f"{label}: " + " ".join(errs))
            continue

        explanations = {}
        missing = []
        for n in range(1, 6):
            expl = (request.form.get(f"{key}_explanation_{n}") or "").strip()
            if scoring.explanation_required(scores[n]) and not expl:
                missing.append(str(n))
            explanations[n] = expl
        if missing:
            problems.append(
                f"{label}: a reason is required for the low score on "
                f"criterion {', '.join(missing)}.")
            continue

        evald = scoring.evaluate(scores)
        insp = Inspection(
            org_id=current_user.org_id,
            ref=services.next_inspection_ref(org, now),
            verify_code=new_code(10),
            inspector_id=current_user.id,
            duty_date=today,
            department_id=dept.id,
            status="SUBMITTED",
            started_at=now,
            submitted_at=now,
            total_score=evald["total"],
            percent=evald["percent"],
            rating=evald["rating"],
            critical_count=evald["critical_count"],
            poor_count=evald["poor_count"],
            gps_mode=services.get_setting(current_user.org_id, "gps_mode"),
            device_info=request.headers.get("User-Agent", "")[:280],
            final_comment=(request.form.get("overall_report") or "").strip()[:4000] or None,
        )
        db.session.add(insp)
        db.session.flush()
        for n in range(1, 6):
            db.session.add(InspectionScore(
                inspection_id=insp.id, criterion_no=n, score=scores[n],
                explanation=explanations[n] or None))
        already.add(dept.id)
        saved.append(f"{label} ({evald['total']}/25)")
        audit("INSPECTION_SUBMITTED", "inspection", insp.id,
              {"ref": insp.ref, "area": label, "total": evald["total"]})

    if saved:
        db.session.commit()
    else:
        db.session.rollback()

    if saved:
        flash(f"Saved {len(saved)} area(s): " + ", ".join(saved), "success")
    if skipped:
        flash("Already inspected today, left unchanged: " + ", ".join(skipped), "success")
    for p in problems:
        flash(p, "error")
    if not saved and not problems:
        flash("Nothing was scored yet. Open an area and give it five scores.", "error")
    return redirect(url_for("inspections.walk_round"))
