"""Dashboards, notification inbox, corrective actions, management attention."""
from __future__ import annotations

from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from .. import scoring, services
from ..audit import audit
from ..models import (AppNotification, Complaint, CorrectiveAction, DataRequest,
                      Department, DutyRoster, Inspection, db, new_code, now_naive)
from ..navigation import require_permission
from ..security import rate_limit, require_login, require_role, save_upload

bp = Blueprint("main", __name__)


def _kpi(org_id: int, viewer=None) -> dict:
    """v1.7.18: scoped KPI — HOD/APEX_NURSE/STAFF see only own Department/Section/Unit, System Admin upgrades.

    - SUPER_ADMIN, HEAD_ADMIN_HR, MD_CEO, DMD, DCST, ADMIN_MANAGER on-duty: whole hospital
    - HOD, APEX_NURSE: only own dept(s) via visible_department_ids
    - STAFF: only own dept
    """
    now = now_naive()
    today = now.date()
    st = services.inspection_state(org_id, today, now=now)

    # Determine visible departments for this viewer
    visible_ids = None
    is_limited = False
    if viewer is not None:
        try:
            from ..roles import visible_department_ids
            visible_ids = visible_department_ids(viewer)
            if visible_ids is not None:
                is_limited = True
        except Exception:
            visible_ids = None

    # Base query for inspections
    insp_q = db.session.query(Inspection).filter_by(org_id=org_id, status="SUBMITTED")
    if is_limited and visible_ids is not None:
        insp_q = insp_q.filter(Inspection.department_id.in_(visible_ids or [-1]))
    insp_all = insp_q.all()
    total_inspections = len(insp_all)
    avg_score = round(sum(i.total_score or 0 for i in insp_all) / total_inspections, 1) if total_inspections else 0

    # department averages (last 30 days) — scoped
    since = today - timedelta(days=30)
    dept_query = db.session.query(Department).filter_by(org_id=org_id, active=True)
    if is_limited and visible_ids is not None:
        dept_query = dept_query.filter(Department.id.in_(visible_ids or [-1]))
    dept_rows = []
    for d in dept_query.order_by(Department.name).all():
        recent = [i.total_score for i in insp_all if i.department_id == d.id and i.duty_date >= since]
        if recent:
            dept_rows.append({"dept": d, "avg": round(sum(recent) / len(recent), 1), "n": len(recent)})
    dept_rows.sort(key=lambda r: r["avg"])

    critical_findings = sum(i.critical_count or 0 for i in insp_all if i.duty_date >= since)

    # Complaints — for limited roles, only complaints related to their dept? Complaints are hospital-wide but filter if possible
    complaints_q = db.session.query(Complaint).filter_by(org_id=org_id)
    # Complaints don't have department_id directly, so for HOD/STAFF we show only 0 or limited? Keep 0 for STAFF, own dept complaints for HOD if we can match via department name? For now, hide for STAFF, show for HOD/APEX limited view = 0 unless they are management
    if is_limited:
        role = getattr(viewer, "role", "") if viewer else ""
        if role == "STAFF":
            complaints = []  # STAFF does not see complaints at all
        else:
            # HOD/APEX_NURSE: if complaint has department link? For now show all but filtered to their dept if possible via inspection dept? To be safe, show 0 for non-management to avoid leaking hospital-wide complaint counts
            # Actually HOD should see complaints for own dept — but Complaint model has no department_id, so we show empty to avoid leaking
            # System Admin can upgrade via Role Management if needed
            complaints = [] if is_limited and role in ("HOD", "APEX_NURSE") else complaints_q.all()
            if not is_limited:
                complaints = complaints_q.all()
            else:
                # For HOD/APEX limited, try to get complaints if they have department_id attr, else empty
                try:
                    complaints = complaints_q.all() if getattr(viewer, "is_super", False) else []
                except Exception:
                    complaints = []
        # Re-evaluate if complaints not yet set
        if 'complaints' not in locals() or complaints is None:
            complaints = []
    else:
        complaints = complaints_q.all()

    # For non-limited (management), complaints as before
    if not is_limited:
        complaints = db.session.query(Complaint).filter_by(org_id=org_id).all()

    open_complaints = [c for c in complaints if c.status in ("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED")]
    escalated = [c for c in complaints if c.escalated]
    resolved = [c for c in complaints if c.status in ("RESOLVED", "CLOSED")]
    sla_breaches = len([c for c in complaints if c.escalated])

    # inspection compliance (last 30 days): roster days with a submitted inspection — whole hospital only for management, 0 for limited
    if is_limited:
        compliance = 0
        roster_days = []
    else:
        roster_days = db.session.query(DutyRoster).filter(
            DutyRoster.org_id == org_id, DutyRoster.duty_date >= since, DutyRoster.duty_date <= today).all()
        inspected_dates = {i.duty_date for i in insp_all if i.duty_date >= since}
        compliance = round(100 * len([r for r in roster_days if r.duty_date in inspected_dates]) / len(roster_days)) if roster_days else 0

    cas_open_q = db.session.query(CorrectiveAction).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.status.in_(("OPEN", "IN_PROGRESS", "OVERDUE")))
    if is_limited and visible_ids is not None:
        # Corrective actions may have department link via source? Filter if possible, else empty for STAFF
        role = getattr(viewer, "role", "") if viewer else ""
        if role == "STAFF":
            cas_open = []
        else:
            # For HOD/APEX, show only CAs they own
            cas_open = cas_open_q.filter(CorrectiveAction.owner_id == viewer.id).all() if viewer else []
    else:
        cas_open = cas_open_q.all()

    from ..models import Appointment, PatientFeedback, QueueTicket, ReferralEvent
    bookings_q = db.session.query(Appointment).filter_by(org_id=org_id, appointment_date=today, status="BOOKED")
    queue_q = db.session.query(QueueTicket).filter_by(org_id=org_id, queue_date=today, status="WAITING")
    if is_limited and visible_ids is not None:
        bookings_q = bookings_q.filter(Appointment.department_id.in_(visible_ids or [-1]))
        queue_q = queue_q.filter(QueueTicket.department_id.in_(visible_ids or [-1]))
    bookings_today = bookings_q.count()
    queue_waiting = queue_q.count()

    fb_all = []
    satisfaction_avg = None
    if not is_limited:
        fb_all = db.session.query(PatientFeedback).filter_by(org_id=org_id).all()
        satisfaction_avg = round(sum(f.rating for f in fb_all) / len(fb_all), 1) if fb_all else None

    since30 = now - timedelta(days=30)
    referral_books_30d = 0
    repeat_visits_30d = 0
    if not is_limited:
        referral_books_30d = (db.session.query(ReferralEvent)
                              .filter(ReferralEvent.org_id == org_id,
                                      ReferralEvent.kind == "book",
                                      ReferralEvent.created_at >= since30).count())
        repeat_visits_30d = (db.session.query(Appointment)
                             .filter(Appointment.org_id == org_id,
                                     Appointment.is_repeat.is_(True),
                                     Appointment.created_at >= since30).count())

    heatmap = services.heatmap_data(org_id, days=14)
    if is_limited and visible_ids is not None:
        # Filter heatmap to visible departments only
        try:
            heatmap = {k: v for k, v in heatmap.items() if any(dept_id in (visible_ids or []) for dept_id in [getattr(v, 'department_id', None)] )} if isinstance(heatmap, dict) else []
            # If heatmap is list of dicts, filter
            if isinstance(heatmap, list):
                heatmap = [h for h in heatmap if h.get('department_id') in (visible_ids or [])]
        except Exception:
            # If filtering fails, hide heatmap for limited roles
            heatmap = []

    return {
        "bookings_today": bookings_today,
        "queue_waiting": queue_waiting,
        "satisfaction_avg": satisfaction_avg,
        "feedback_count": len(fb_all),
        "referral_books_30d": referral_books_30d,
        "repeat_visits_30d": repeat_visits_30d,
        "today": st,
        "total_inspections": total_inspections,
        "avg_score": avg_score,
        "lowest_depts": dept_rows[:5],
        "critical_findings_30d": critical_findings,
        "complaints_total": len(complaints),
        "complaints_new": len([c for c in complaints if c.status == "NEW"]),
        "complaints_open": len(open_complaints),
        "complaints_escalated": len(escalated),
        "sla_breaches": sla_breaches,
        "resolution_rate": round(100 * len(resolved) / len(complaints)) if complaints else 0,
        "compliance_rate": compliance,
        "cas_open": cas_open,
        "heatmap": heatmap,
        "is_limited": is_limited,
        "visible_ids": visible_ids,
    }


@bp.get("/branding/logo")
@bp.get("/branding/logo/<int:size>")
@bp.get("/branding/logo/<string:variant>")
def branding_logo(size=None, variant=None):
    """Public hospital logo — per-org, multi-hospital, compressed, shows on phone home screen.
    Hardened: never 500, handles None org, corrupted image, missing file, PIL errors.

    - /branding/logo → original optimized logo (max 512)
    - /branding/logo/192 → 192x192 for PWA manifest <30KB
    - /branding/logo/512 → 512x512 <80KB
    - /branding/logo/maskable → 512 with padding for maskable purpose (20% safe zone white)
    - /branding/logo/apple → 180x180 apple-touch-icon

    Loading time premium: resized on fly, cached, <30KB for 192, <80KB for 512
    Slow internet: small sizes for fast load, Cache-Control 86400
    Security: no org leak, per-tenant via current_org(), 404 if no logo
    """
    from .. import storage
    from flask import Response
    import io

    try:
        from ..services import current_org
        org = current_org()
    except Exception:
        org = None

    if not org or not getattr(org, 'logo_path', None):
        abort(404)

    # Determine target size — defensive
    target = 512
    is_maskable = False
    try:
        if variant == "maskable":
            target = 512
            is_maskable = True
        elif variant == "apple":
            target = 180
        elif isinstance(size, int) and size in (192, 512, 180, 256, 384):
            target = size
        elif isinstance(size, int):
            target = min(512, max(48, size))
        # variant could be numeric string like "192"
        if variant and isinstance(variant, str) and variant.isdigit():
            try:
                target = min(512, max(48, int(variant)))
            except Exception:
                pass
    except Exception:
        target = 512
        is_maskable = False

    # Try to get raw bytes — defensive
    raw = None
    try:
        raw = storage.get(org.logo_path)
    except FileNotFoundError:
        abort(404)
    except Exception:
        current_app.logger.exception("logo storage.get failed")
        abort(404)

    if not raw:
        abort(404)

    # If requesting original and size is None, serve directly via storage.send (handles caching)
    if size is None and variant is None:
        try:
            return storage.send(org.logo_path, max_age=3600)
        except FileNotFoundError:
            abort(404)
        except Exception:
            current_app.logger.exception("logo send failed")
            abort(404)

    # Resize with PIL — premium, keeps transparency for maskable, hardened for corrupted image
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        # PIL not installed — fallback to original
        try:
            return storage.send(org.logo_path, max_age=3600)
        except Exception:
            abort(404)

    try:
        # Open image — may raise UnidentifiedImageError if corrupted
        img = Image.open(io.BytesIO(raw))
        # Verify image is not truncated / corrupted
        try:
            img.load()
        except Exception:
            # Corrupted — fallback to original or 404
            raise UnidentifiedImageError("corrupted image")

        if is_maskable:
            # Maskable needs 20% padding safe zone — Android adaptive icons
            # Spec: logo centered 80% with white background, 20% safe zone padding
            # Premium: white opaque background for maskable, not transparent, so icon visible on any wallpaper
            try:
                canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
                logo_size = int(512 * 0.8)
                img_copy = img.copy()
                if img_copy.mode != "RGBA":
                    img_copy = img_copy.convert("RGBA")
                img_copy.thumbnail((logo_size, logo_size), Image.LANCZOS)
                x = (512 - img_copy.width)//2
                y = (512 - img_copy.height)//2
                canvas.paste(img_copy, (x, y), img_copy)
                img = canvas
            except Exception:
                # If maskable fails, fallback to regular thumbnail
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                img.thumbnail((512, 512), Image.LANCZOS)
        else:
            # Regular resize preserving aspect, max target
            try:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                img.thumbnail((target, target), Image.LANCZOS)
            except Exception:
                # If thumbnail fails, try to serve original
                raise

        out = io.BytesIO()
        try:
            img.save(out, format="PNG", optimize=True, compress_level=9)
        except Exception:
            # If PNG save fails (e.g., too large), try JPEG fallback or original
            try:
                # Convert to RGB for JPEG if has alpha
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=85, optimize=True)
            except Exception:
                # Final fallback to original
                try:
                    return storage.send(org.logo_path, max_age=3600)
                except Exception:
                    abort(404)
        out.seek(0)
        data = out.getvalue()
        # Enforce size limits for premium loading time — 192 <30KB, 512 <80KB
        # If larger, we still serve but log warning (not crash)
        try:
            if target == 192 and len(data) > 35*1024:
                current_app.logger.warning(f"logo 192 larger than expected: {len(data)} bytes")
            if target == 512 and len(data) > 90*1024:
                current_app.logger.warning(f"logo 512 larger than expected: {len(data)} bytes")
        except Exception:
            pass
        resp = Response(data, mimetype="image/png" if target != 0 else "image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        resp.headers["Content-Length"] = str(len(data))
        return resp

    except FileNotFoundError:
        abort(404)
    except Exception as e:
        # Catch all — including UnidentifiedImageError, OSError for corrupted image
        try:
            current_app.logger.exception("logo resize failed, fallback to original")
        except Exception:
            pass
        # Fallback to original via storage.send, not crash
        try:
            return storage.send(org.logo_path, max_age=3600)
        except FileNotFoundError:
            abort(404)
        except Exception:
            abort(404)


@bp.get("/")
def home():
    """Front door.

    Patients (not signed in) get the service hub. Staff go to their dashboard.
    Previously "/" simply demanded a login, so a patient scanning a QR code
    landed on a staff login screen — the wrong first impression entirely.
    """
    if current_user.is_authenticated:
        return dashboard()
    return patient_hub()


@bp.get("/welcome")
def patient_hub():
    """Patient & visitor service hub — the six things a patient can do.

    Always reachable at /welcome, even for signed-in staff who want to preview
    what patients see (or scan their own QR posters).
    """
    from .. import referrals as refeng
    from ..models import QrLocation
    from ..services import current_org

    org = current_org()
    if not org:
        # Empty database: send the founder to the setup walk, not a dead page.
        return redirect(url_for("onboard.start"))

    # Keep the QR-location tag (?loc=) and referral code (?ref=) across the hub
    # so posters keep attributing correctly when the patient picks a service.
    keep = {}
    loc_code = (request.args.get("loc") or "").strip().upper()
    qr_loc = None
    if loc_code:
        qr_loc = db.session.query(QrLocation).filter_by(code=loc_code).first()
        if qr_loc:
            keep["loc"] = qr_loc.code
    ref_code = (request.args.get("ref") or "").strip()
    if ref_code:
        keep["ref"] = ref_code
    q = ("?" + "&".join(f"{k}={v}" for k, v in keep.items())) if keep else ""

    # Hospital-wide share link for the "tell a friend" tile.
    share_url = wa_url = None
    try:
        row = refeng.ensure_hospital_referral(org)
        db.session.commit()
        share_url = refeng.share_url(row)
        wa_url = refeng.whatsapp_share_url(org.name, share_url)
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("hub: could not build the share link")

    share_text = (f"I recommend {org.name}. You can book an appointment or join the "
                  f"queue from your phone here:")
    return render_template("patient_hub.html", org=org, qr_loc=qr_loc, q=q,
                           share_url=share_url, wa_url=wa_url, share_text=share_text)


@bp.get("/dashboard")
@require_login
def dashboard():
    from flask import current_app
    try:
        org_id = current_user.org_id
        role = getattr(current_user, "role", "") or ""
        if role == "STAFF":
            # F-007: the deptdesk blueprint's entry endpoint is `desk`
            # (@bp.get("")). This used to point at a nonexistent
            # `deptdesk.my_department`, which raised BuildError — a 500 on
            # login for every ordinary staff member. Guarded by a regression
            # test that logs in EVERY role and asserts no crash.
            return redirect(url_for("deptdesk.desk"))

        try:
            kpi = _kpi(org_id, viewer=current_user)
        except Exception:
            current_app.logger.exception("kpi failed")
            kpi = {"bookings_today": 0, "queue_waiting": 0, "today": {}, "total_inspections": 0, "avg_score": 0, "lowest_depts": [], "critical_findings_30d": 0, "complaints_total": 0, "complaints_new": 0, "complaints_open": 0, "complaints_escalated": 0, "sla_breaches": 0, "resolution_rate": 0, "compliance_rate": 0, "cas_open": [], "heatmap": [], "is_limited": False, "visible_ids": None}

        attention = []
        try:
            if getattr(current_user, "is_management", False) and role not in ("HOD", "APEX_NURSE"):
                attention = services.management_attention(org_id)
        except Exception:
            current_app.logger.exception("management_attention failed")
            attention = []

        my_cas = None
        try:
            if getattr(current_user, "is_am", False) or getattr(current_user, "is_hod", False) or role == "APEX_NURSE":
                q = (db.session.query(CorrectiveAction)
                     .filter(CorrectiveAction.org_id == org_id, CorrectiveAction.owner_id == current_user.id,
                             CorrectiveAction.status.in_(("OPEN", "IN_PROGRESS", "OVERDUE"))))
                my_cas = q.order_by(CorrectiveAction.deadline).all()
        except Exception:
            my_cas = []

        recent_complaints = None
        try:
            if role in ("MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "SUPER_ADMIN") or getattr(current_user, "is_super", False):
                recent_complaints = (db.session.query(Complaint)
                                     .filter(Complaint.org_id == org_id,
                                             Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED")))
                                     .order_by(Complaint.submitted_at.desc()).limit(8).all())
        except Exception:
            recent_complaints = []

        flow = None
        try:
            from .. import tracking as _tracking
            if role not in ("STAFF",):
                try:
                    flow = {"head": _tracking.headline(org_id, 7), "advice": _tracking.suggest_allocation(org_id)[:2]}
                except Exception:
                    flow = {"head": {"median_journey": None, "average_journey": None, "longest_journey": None,
                                     "patients_completed": 0, "in_hospital_now": 0, "stuck_now": 0,
                                     "reliable": False, "days": 7}, "advice": []}
        except Exception:
            current_app.logger.exception("patient-flow summary unavailable")
            flow = None

        return render_template("dashboard.html", kpi=kpi, attention=attention, my_cas=my_cas,
                               recent_complaints=recent_complaints, scoring=scoring,
                               flow=flow, is_limited=kpi.get("is_limited", False))
    except Exception:
        current_app.logger.exception("dashboard outer failed")
        try:
            return render_template("dashboard.html",
                                   kpi={"bookings_today": 0, "queue_waiting": 0, "today": {}, "total_inspections": 0, "avg_score": 0, "lowest_depts": [], "critical_findings_30d": 0, "complaints_total": 0, "complaints_new": 0, "complaints_open": 0, "complaints_escalated": 0, "sla_breaches": 0, "resolution_rate": 0, "compliance_rate": 0, "cas_open": [], "heatmap": [], "is_limited": False},
                                   attention=[], my_cas=[], recent_complaints=[], scoring=scoring, flow=None, is_limited=False)
        except Exception:
            return render_template("error.html", code=500, message="Dashboard loading — please refresh."), 500



# ------------------------------------------------------------------ notifications inbox
@bp.get("/notifications")
@require_login
def notifications_inbox():
    items = (db.session.query(AppNotification)
             .filter_by(org_id=current_user.org_id, user_id=current_user.id, channel="inapp")
             .order_by(AppNotification.created_at.desc()).limit(100).all())
    return render_template("notifications.html", items=items)


# ------------------------------------------------------------------ alert preferences (§19)
@bp.get("/alert-settings")
@require_login
def alert_settings():
    from ..models import UserPref
    return render_template("alert_settings.html", prefs=UserPref.bundle(current_user.id))


@bp.post("/alert-settings")
@require_login
def alert_settings_save():
    from ..models import UserPref
    f = request.form
    UserPref.set(current_user.id, "voice_enabled", bool(f.get("voice_enabled")))
    lvl = f.get("voice_min_level")
    UserPref.set(current_user.id, "voice_min_level",
                 lvl if lvl in ("standard", "urgent", "emergency") else "standard")
    qs, qe = f.get("quiet_start") or "22:00", f.get("quiet_end") or "07:00"
    UserPref.set(current_user.id, "quiet_start", qs)
    UserPref.set(current_user.id, "quiet_end", qe)
    UserPref.set(current_user.id, "push_enabled", bool(f.get("push_enabled")))
    audit("ALERT_PREFS_UPDATED", "user", current_user.id,
          {"voice": bool(f.get("voice_enabled")), "level": UserPref.get(current_user.id, "voice_min_level")})
    db.session.commit()
    flash("Alert preferences saved.", "success")
    return redirect(url_for("main.alert_settings"))


@bp.post("/notifications/read")
@require_login
def notifications_read():
    (db.session.query(AppNotification)
     .filter_by(org_id=current_user.org_id, user_id=current_user.id, channel="inapp", status="SENT")
     .update({"status": "READ"}))
    db.session.commit()
    return redirect(url_for("main.notifications_inbox"))


# ------------------------------------------------------------------ corrective actions — management + HOD only, not all staff
@bp.get("/corrective-actions")
@require_login
@require_permission("corrective")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
def corrective_actions():
    q = db.session.query(CorrectiveAction).filter(CorrectiveAction.org_id == current_user.org_id)
    status = request.args.get("status")
    if status in ("OPEN", "IN_PROGRESS", "COMPLETED", "OVERDUE", "VERIFIED"):
        q = q.filter(CorrectiveAction.status == status)
    mine = request.args.get("mine")
    if mine == "1":
        q = q.filter(CorrectiveAction.owner_id == current_user.id)
    items = q.order_by(CorrectiveAction.deadline).all()
    from ..models import User
    users = db.session.query(User).filter_by(org_id=current_user.org_id, active=True).order_by(User.name).all()
    return render_template("corrective_actions.html", items=items, users=users,
                           highlight=request.args.get("highlight"),
                           can_create=current_user.role in ("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER"))


@bp.post("/corrective-actions")
@require_login
@require_permission("corrective")
@require_role("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER")
def corrective_action_create():
    if current_user.role not in ("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER"):
        return redirect(url_for("main.corrective_actions"))
    finding = (request.form.get("finding") or "").strip()
    action_required = (request.form.get("action_required") or "").strip()
    owner_id = request.form.get("owner_id", type=int)
    deadline = request.form.get("deadline")
    source_type = request.form.get("source_type", "inspection")
    source_id = request.form.get("source_id", type=int) or 0
    if not finding or not action_required or not owner_id or not deadline:
        flash("All corrective-action fields are required.", "error")
        return redirect(url_for("main.corrective_actions"))
    from datetime import date as _date
    try:
        dl = _date.fromisoformat(deadline)
    except ValueError:
        flash("Invalid deadline date.", "error")
        return redirect(url_for("main.corrective_actions"))
    ca = CorrectiveAction(org_id=current_user.org_id, source_type=source_type, source_id=source_id,
                          finding=finding, action_required=action_required, owner_id=owner_id,
                          deadline=dl, status="OPEN")
    db.session.add(ca)
    db.session.flush()
    audit("CA_CREATED", "ca", ca.id, {"finding": finding[:120], "deadline": deadline})
    from .. import notifications
    notifications.notify(current_user.org_id, ca.owner, "ca_assigned",
                         {"details": finding[:100], "date": dl.strftime("%d %b %Y")},
                         channels=["inapp"], entity_type="ca", entity_id=ca.id)
    db.session.commit()
    flash("Corrective action created and owner notified.", "success")
    return redirect(url_for("main.corrective_actions"))


@bp.post("/corrective-actions/<int:ca_id>/update")
@require_login
@require_permission("corrective")
def corrective_action_update(ca_id: int):
    ca = db.session.get(CorrectiveAction, ca_id)
    if not ca or ca.org_id != current_user.org_id:
        flash("Corrective action not found.", "error")
        return redirect(url_for("main.corrective_actions"))
    new_status = request.form.get("status")
    if new_status not in ("OPEN", "IN_PROGRESS", "COMPLETED", "VERIFIED"):
        flash("Invalid status.", "error")
        return redirect(url_for("main.corrective_actions"))
    # verification is management-only
    if new_status == "VERIFIED" and current_user.role not in ("SUPER_ADMIN", "MD_CEO"):
        flash("Only management can verify a corrective action.", "error")
        return redirect(url_for("main.corrective_actions"))
    old = ca.status
    ca.status = new_status
    if new_status == "COMPLETED":
        ca.completed_at = now_naive()
        file = request.files.get("evidence")
        if file and file.filename:
            path, err = save_upload(file, "ca", org_id=ca.org_id)
            if not err:
                ca.evidence_path = path
    if new_status == "VERIFIED":
        ca.verified_by_id = current_user.id
        ca.verified_at = now_naive()
    audit("CA_UPDATED", "ca", ca.id, {"old_status": old, "new_status": new_status})
    db.session.commit()
    flash(f"Corrective action updated to {new_status}.", "success")
    return redirect(url_for("main.corrective_actions"))


# ================================================================ NDPA: privacy & data rights
@bp.get("/privacy")
def privacy():
    """Public privacy notice. Required before a hospital's legal officer will sign."""
    return render_template("privacy.html", today=now_naive())


@bp.get("/sales")
def sales_landing():
    """World-class premium sales landing page — Adobe/Figma/Apple/Canva inspired."""
    return render_template("landing_sales.html")

@bp.get("/privacy/request")
def privacy_request():
    return render_template("privacy_request.html")


@bp.post("/privacy/request")
@rate_limit(limit=5, window=600.0, key_extra="dsr")
def privacy_request_post():
    """Log a data-subject access/erasure request for staff to action."""
    from ..services import current_org
    org = current_org()
    if not org:
        abort(503)
    kind = request.form.get("kind")
    phone = (request.form.get("phone") or "").strip().replace(" ", "").replace("-", "")
    note = (request.form.get("note") or "").strip()[:1000]
    if kind not in ("access", "erase") or len(phone) < 7:
        flash("Please choose what you need and enter the phone number you used.", "error")
        return render_template("privacy_request.html"), 422

    req = DataRequest(org_id=org.id, ref=f"DSR-{now_naive():%Y}-{new_code(6)}",
                      kind=kind, phone=phone, note=note or None)
    db.session.add(req)
    audit("DATA_REQUEST_SUBMITTED", "data_request", None,
          {"kind": kind, "ref": req.ref}, org_id=org.id)
    db.session.commit()
    flash(f"Request received. Your reference is {req.ref}. "
          "We will respond within 30 days.", "success")
    return redirect(url_for("main.privacy"))


# ================================================================ install-on-phone (PWA)
@bp.get("/manifest.webmanifest")
def web_manifest():
    from .. import pwa
    from ..services import current_org, org_settings_bundle
    org = current_org()
    bundle = org_settings_bundle(org.id) if org else {}
    return pwa.manifest_response(org, bundle)


@bp.get("/sw.js")
def service_worker():
    from .. import pwa
    return pwa.service_worker_response()


@bp.get("/offline")
def offline_page():
    return render_template("offline.html")
