"""Administrator Control Center — hospital setup, users, structure, settings, logs."""
from __future__ import annotations

import os
import shutil

from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user

from .. import services, whatsapp
from ..audit import audit, verify_chain
from ..config import Config
from ..models import (AppNotification, AuditLog, Branch, Complaint, ComplaintCategory,
                      Department, DutyRoster, Organization, QrLocation, ReportFile,
                      ROLES, Section, Unit, User, WhatsAppMessage, db, new_code,
                      now_naive, role_label)
from ..security import (PHONE_RE, clean_phone, password_strength_errors,
                        require_role, save_upload)

bp = Blueprint("admin", __name__, url_prefix="/admin")

SUPER = ("SUPER_ADMIN",)
# Executive view: audit log, data requests, KB approval.
SUPER_MD = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")


# ------------------------------------------------------------------ overview
@bp.get("")
@require_role(*SUPER)
def overview():
    org = db.session.get(Organization, current_user.org_id)
    counts = {
        "users": db.session.query(User).filter_by(org_id=org.id).count(),
        "departments": db.session.query(Department).filter_by(org_id=org.id).count(),
        "roster": db.session.query(DutyRoster).filter_by(org_id=org.id).count(),
        "reports": db.session.query(ReportFile).filter_by(org_id=org.id).count(),
        "wa_failed": db.session.query(WhatsAppMessage).filter_by(org_id=org.id, status="FAILED").count(),
        "wa_queue": db.session.query(WhatsAppMessage).filter_by(org_id=org.id, status="QUEUED").count(),
    }
    from ..backup import list_backups
    backups = [{"name": b.key.split("/")[-1],
                "size_kb": (b.size or 0) // 1024,
                "at": b.created_at} for b in list_backups(limit=10)]
    ok, n = verify_chain(org.id)
    return render_template("admin/overview.html", org=org, counts=counts, backups=backups,
                           chain_ok=ok, chain_rows=n)


# ------------------------------------------------------------------ hospital setup
@bp.get("/hospital")
@require_role(*SUPER)
def hospital():
    org = db.session.get(Organization, current_user.org_id)
    brand = {
        "brand_primary": services.get_setting(org.id, "brand_primary") or "#0E5A8A",
        "brand_accent": services.get_setting(org.id, "brand_accent") or "#12B5A5",
        "brand_gold": services.get_setting(org.id, "brand_gold") or "#FFD700",
        "sms_sender_tag": services.get_setting(org.id, "sms_sender_tag") or "",
    }
    return render_template("admin/hospital.html", org=org, brand=brand)


@bp.post("/hospital")
@require_role(*SUPER)
def hospital_save():
    org = db.session.get(Organization, current_user.org_id)
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    if name:
        org.name = name
    if code and len(code) <= 12 and code.isalnum():
        org.code = code
    org.email = (request.form.get("email") or "").strip() or None
    org.phone = (request.form.get("phone") or "").strip() or None
    org.phone_alt = (request.form.get("phone_alt") or "").strip() or None
    org.address = (request.form.get("address") or "").strip() or None
    file = request.files.get("logo")
    if file and file.filename:
        # Premium loading time: compress logo to max 512x512, <100KB, for fast home screen icon
        # Multi-hospital: per-org logo stored as logos/org_<id>.png, used in manifest for PWA home screen
        try:
            from PIL import Image
            import io as _io
            file.seek(0)
            raw = file.read()
            img = Image.open(_io.BytesIO(raw))
            # Convert to RGBA if needed, keep transparency
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            # Resize to max 512x512 preserving aspect, for PWA icons 192/512/maskable
            w, h = img.size
            max_size = 512
            if max(w, h) > max_size:
                ratio = max_size / max(w, h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            # Compress: save as PNG optimized, <100KB
            out_buf = _io.BytesIO()
            img.save(out_buf, format="PNG", optimize=True, compress_level=9)
            compressed = out_buf.getvalue()
            # If still >100KB, try JPEG with white bg
            if len(compressed) > 100*1024 and img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                out_buf = _io.BytesIO()
                bg.save(out_buf, format="JPEG", quality=85, optimize=True)
                compressed = out_buf.getvalue()
            # Use compressed data for upload
            file.seek(0)
            # Create a file-like object with compressed data
            class _CompressedFile:
                def __init__(self, data, filename):
                    self._data = data
                    self.filename = filename
                    self._pos = 0
                def read(self, size=-1):
                    if size == -1:
                        d = self._data[self._pos:]
                        self._pos = len(self._data)
                        return d
                    d = self._data[self._pos:self._pos+size]
                    self._pos += len(d)
                    return d
                def seek(self, pos, whence=0):
                    if whence == 0:
                        self._pos = pos
                    elif whence == 1:
                        self._pos += pos
                    elif whence == 2:
                        self._pos = len(self._data) + pos
                def tell(self):
                    return self._pos
            compressed_file = _CompressedFile(compressed, file.filename)
            path, err = save_upload(compressed_file, "logos", org_id=org.id)
        except Exception:
            # Fallback to original if compression fails
            file.seek(0)
            path, err = save_upload(file, "logos", org_id=org.id)

        if err:
            flash(err, "error")
        else:
            org.logo_path = path
            try:
                from .. import storage
                from PIL import Image
                import io as _io
                data = storage.get(path)
                if data:
                    w, h = Image.open(_io.BytesIO(data)).size
                    size_kb = len(data)//1024
                    if min(w, h) < 200:
                        flash(f"Logo uploaded ({w}x{h}, {size_kb}KB), but small — may look blurry on phone home screen. Upload 400x400 PNG for sharp PWA icon.", "info")
                    else:
                        flash(f"Logo uploaded ({w}x{h}, {size_kb}KB) — will show on phone home screen when PWA installed. Optimized for fast loading.", "success")
            except Exception:
                current_app.logger.exception("logo dimension check failed")
    # Colours — per hospital, never per-deploy. Only accept #RRGGBB.
    import re as _re
    for key in ("brand_primary", "brand_accent", "brand_gold"):
        raw = (request.form.get(key) or "").strip()
        if _re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
            services.set_setting(org.id, key, raw.upper())
    from .. import sms_pack
    tag = sms_pack.parse_tag(request.form.get("sms_sender_tag") or "")
    if tag:
        services.set_setting(org.id, "sms_sender_tag", tag)
    elif (request.form.get("sms_sender_tag") or "").strip():
        flash("SMS name must be 3–11 letters or numbers (no spaces). Left unchanged.", "error")
    audit("HOSPITAL_UPDATED", "organization", org.id, {"name": org.name, "code": org.code})
    db.session.commit()
    flash("Hospital profile updated.", "success")
    return redirect(url_for("admin.hospital"))


# ------------------------------------------------------------------ users & roles
@bp.get("/users")
@require_role(*SUPER)
def users():
    items = (db.session.query(User).filter_by(org_id=current_user.org_id)
             .order_by(User.role, User.name).all())
    depts = (db.session.query(Department)
             .filter_by(org_id=current_user.org_id, active=True)
             .order_by(Department.name).all())
    pending = [u for u in items if (not u.approved)
               or (not getattr(u, "email_verified", True))
               or (not getattr(u, "profile_completed", True))]
    from .. import branches as br
    br.ensure_main_branch(current_user.org_id)
    sites = br.list_active(current_user.org_id)
    return render_template("admin/users.html", items=items, depts=depts, pending=pending,
                           branches=sites,
                           role_choices=[(r, role_label(r)) for r in ROLES])


@bp.post("/users/create")
@require_role(*SUPER)
def user_create():
    username = (request.form.get("username") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    role = request.form.get("role")
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    password = request.form.get("password") or ""
    dept_id = request.form.get("department_id", type=int)
    branch_id = request.form.get("branch_id", type=int)
    phone = clean_phone(phone)
    if phone and not PHONE_RE.match(phone):
        flash("Enter a valid phone number (digits only, e.g. 08012345678).", "error")
        return redirect(url_for("admin.users"))
    if dept_id:
        d = db.session.get(Department, dept_id)
        if not d or d.org_id != current_user.org_id:
            flash("We couldn't find that department — it may have been removed or belongs to another hospital. Please choose from the list.", "error")
            return redirect(url_for("admin.users"))
    if branch_id:
        from .. import branches as br
        if not br.get_in_org(branch_id, current_user.org_id):
            flash("We couldn't find that site — it may have been removed. Please choose from the list.", "error")
            return redirect(url_for("admin.users"))
    if not username or not name or role not in ROLES:
        flash("Username, full name and a valid role are required.", "error")
        return redirect(url_for("admin.users"))
    from ..accounts import username_available
    if not username_available(current_user.org_id, username):
        flash("That username is already used in this hospital.", "error")
        return redirect(url_for("admin.users"))
    from .. import accounts
    org = db.session.get(Organization, current_user.org_id)
    mail_errs = accounts.email_allowed_for_hospital(email, org.email if org else None)
    if mail_errs:
        for e in mail_errs:
            flash(e, "error")
        return redirect(url_for("admin.users"))
    if accounts.email_taken(current_user.org_id, email):
        flash("That email is already on another account.", "error")
        return redirect(url_for("admin.users"))
    errs = password_strength_errors(password, username=username, email=email)
    if errs:
        for e in errs:
            flash(e, "error")
        return redirect(url_for("admin.users"))
    u = User(org_id=current_user.org_id, username=username, name=name, role=role,
             email=accounts.normalize_email(email), phone=phone or None,
             department_id=dept_id or None, branch_id=branch_id or None,
             approved=False, email_verified=False, profile_completed=False,
             must_change_password=True)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    try:
        otp = accounts.issue_email_code(u)
        accounts.send_activation(u, otp, hospital_name=(org.name if org else "the hospital"))
        if current_app.config.get("TESTING"):
            current_app.logger.info("activation code for %s: %s", u.username, otp)
    except Exception:
        current_app.logger.exception("activation send failed")
    audit("USER_CREATED", "user", u.id, {"username": username, "role": role})
    db.session.commit()
    flash(f"{name} saved. They activate their email, fill their staff card, "
          f"then you tap Approve. If the mail never arrives, tap Mark email seen.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/edit")
@require_role(*SUPER)
def user_edit(uid: int):
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    name = (request.form.get("name") or "").strip()
    role = request.form.get("role")
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    if not name:
        flash("Full name is required.", "error")
        return redirect(url_for("admin.users"))
    if role not in ROLES:
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))
    phone = clean_phone(phone)
    if phone and not PHONE_RE.match(phone):
        flash("Enter a valid phone number (digits only, e.g. 08012345678).", "error")
        return redirect(url_for("admin.users"))
    dept_id = request.form.get("department_id", type=int)
    branch_id = request.form.get("branch_id", type=int)
    if dept_id:
        d = db.session.get(Department, dept_id)
        if not d or d.org_id != current_user.org_id:
            flash("We couldn't find that department — it may have been removed or belongs to another hospital. Please choose from the list.", "error")
            return redirect(url_for("admin.users"))
    if branch_id:
        from .. import branches as br
        if not br.get_in_org(branch_id, current_user.org_id):
            flash("We couldn't find that site — it may have been removed. Please choose from the list.", "error")
            return redirect(url_for("admin.users"))
    # Never let an admin strip the last SUPER_ADMIN of its role — that would
    # lock every administrator out of the system with no way back in.
    if u.role == "SUPER_ADMIN" and role != "SUPER_ADMIN":
        remaining = (db.session.query(User)
                     .filter(User.org_id == current_user.org_id,
                             User.role == "SUPER_ADMIN", User.active.is_(True),
                             User.id != u.id).count())
        if remaining == 0:
            flash("This is the last Super Admin — change someone else to Super Admin first.",
                  "error")
            return redirect(url_for("admin.users"))
    from .. import accounts
    org = db.session.get(Organization, current_user.org_id)
    new_email = accounts.normalize_email(email)
    if new_email:
        mail_errs = accounts.email_allowed_for_hospital(new_email, org.email if org else None)
        if mail_errs:
            for e in mail_errs:
                flash(e, "error")
            return redirect(url_for("admin.users"))
        if accounts.email_taken(current_user.org_id, new_email, ignore_user_id=u.id):
            flash("That email is already on another account.", "error")
            return redirect(url_for("admin.users"))
    old = {"name": u.name, "role": u.role, "email": u.email, "phone": u.phone,
           "department_id": u.department_id, "branch_id": u.branch_id}
    u.name = name
    u.role = role
    if new_email and new_email != accounts.normalize_email(u.email or ""):
        u.email = new_email
        u.email_verified = False
        u.email_verified_at = None
    elif new_email:
        u.email = new_email
    # Blank email on an old account is left as-is so existing staff stay editable.
    u.phone = phone or None
    u.department_id = dept_id or None
    u.branch_id = branch_id or None
    audit("USER_EDITED", "user", u.id, {"old": old, "new": {"name": name, "role": role,
                                        "email": email, "phone": phone,
                                        "department_id": dept_id,
                                        "branch_id": branch_id}})
    db.session.commit()
    flash(f"User {name} updated.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/toggle")
@require_role(*SUPER)
def user_toggle(uid: int):
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    if u.id == current_user.id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.users"))
    u.active = not u.active
    audit("USER_TOGGLED", "user", u.id, {"active": u.active})
    db.session.commit()
    flash(f"User {'activated' if u.active else 'deactivated'}.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/approve")
@require_role(*SUPER)
def user_approve(uid: int):
    """Approve a pending account so its owner can sign in."""
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    from .. import accounts
    asked = (request.form.get("role") or u.requested_role or u.role or "STAFF").strip()
    if asked == "SUPER_ADMIN":
        remaining = (db.session.query(User)
                     .filter(User.org_id == current_user.org_id,
                             User.role == "SUPER_ADMIN", User.active.is_(True)).count())
        # Allow granting Super Admin only if one already exists (you).
        if remaining == 0:
            asked = "STAFF"
    elif asked not in accounts.REQUESTABLE_ROLES and asked != "SUPER_ADMIN":
        asked = "STAFF"
    u.role = asked
    u.approved = True
    audit("USER_APPROVED", "user", u.id, {"username": u.username, "role": asked,
                                          "asked": u.requested_role})
    db.session.commit()
    extra = ""
    if not getattr(u, "email_verified", True):
        extra = " They still need to activate their email."
    elif not getattr(u, "profile_completed", True):
        extra = " They still need to send their staff card."
    flash(f"{u.name} approved as {asked.replace('_', ' ')}.{extra}", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/confirm-email")
@require_role(*SUPER)
def user_confirm_email(uid: int):
    """Mark the mailbox as seen — for when the activation mail never arrived."""
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    u.email_verified = True
    u.email_verified_at = now_naive()
    audit("EMAIL_CONFIRMED_BY_ADMIN", "user", u.id, {"email": u.email, "by": current_user.username})
    db.session.commit()
    flash(f"{u.name}'s email is marked as activated.", "success")
    return redirect(url_for("admin.users"))


# Every column in the database that points at a user, with a plain-English
# name for it. Ordered so the most meaningful reason is reported first.
#
# WHY THE FULL LIST MATTERS
# ------------------------
# This guard used to check FIVE tables. There are THIRTY-TWO columns pointing
# at user.id. Anything else the person had ever touched — a single alert in
# their inbox is enough — made PostgreSQL refuse the delete, and the founder
# got a bare "500 Something went wrong on our side".
#
# SQLite does not enforce foreign keys by default, so this could never be
# reproduced locally: on a developer machine the delete quietly "worked".
_USER_REFERENCES = [
    # --- clinical and operational history: the audit trail depends on these
    ("Inspection", "inspector_id", "inspections they signed"),
    ("CorrectiveAction", "owner_id", "corrective actions assigned to them"),
    ("CorrectiveAction", "verified_by_id", "corrective actions they verified"),
    ("Department", "hod_user_id", "departments where they are the HOD"),
    ("Section", "hod_user_id", "sections where they are the head"),
    ("Unit", "hod_user_id", "units where they are the head"),
    # --- rosters
    ("DutyRoster", "user_id", "duty roster entries"),
    ("DutyRoster", "created_by", "duty rosters they created"),
    ("RosterEntry", "user_id", "roster entries"),
    ("RosterEntry", "created_by", "roster entries they created"),
    ("DeptRosterEntry", "staff1_user_id", "department roster entries"),
    ("DeptRosterEntry", "staff2_user_id", "department roster entries"),
    ("DeptRosterEntry", "created_by", "department rosters they created"),
    # --- the patient journey
    ("PatientVisit", "doctor_id", "patient visits as the doctor"),
    ("PatientVisit", "registered_by", "patients they registered"),
    ("DoctorSession", "doctor_id", "consulting room sessions"),
    ("VisitOnward", "sent_by", "patients they sent on to another desk"),
    ("VisitOnward", "completed_by", "onward steps they completed"),
    ("JourneySegment", "staff_id", "recorded patient journey steps"),
    ("ReceptionIntake", "created_by", "patients they took in at Reception"),
    ("Patient", "created_by", "patient folders they opened"),
    # --- everything else that names them
    ("ComplaintStatusHistory", "user_id", "complaint updates they made"),
    ("DataRequest", "handled_by_id", "data requests they handled"),
    ("KnowledgeArticle", "submitted_by", "assistant answers they wrote"),
    ("KnowledgeArticle", "approved_by", "assistant answers they approved"),
    ("Referral", "created_by_id", "referral links they created"),
    ("ReportFile", "created_by_id", "reports they generated"),
    ("AppNotification", "user_id", "alerts in their inbox"),
    ("WhatsAppMessage", "to_user_id", "WhatsApp messages sent to them"),
    ("AuditLog", "user_id", "entries in the audit trail"),
    ("StaffAttendance", "user_id", "clock-in records"),
    ("StaffAttendance", "override_by_id", "clock-ins they accepted"),
    # NOTE: UserPref and PasswordReset are deliberately NOT here. They belong
    # to the account itself, not to the hospital's records, so they should go
    # WITH the account rather than prevent it being removed.
]


def _user_has_history(u) -> str | None:
    """Reason this user cannot be hard-deleted (their records must keep an author).

    Returns a plain-English reason, or None when the account is genuinely
    unused and safe to remove.
    """
    from .. import models as M
    for model_name, column, label in _USER_REFERENCES:
        model = getattr(M, model_name, None)
        if model is None:
            continue                       # model not in this build; skip
        col = getattr(model, column, None)
        if col is None:
            continue                       # column renamed; skip rather than crash
        try:
            # Query the COLUMN, never model.id: UserPref has a composite
            # primary key and no `id` attribute, which made this blow up and
            # block the deletion of EVERY user, including brand-new ones.
            if db.session.query(col).filter(col == u.id).first() is not None:
                return label
        except Exception:                                    # noqa: BLE001
            # A query we cannot run is not proof the user is clean. Refuse the
            # delete rather than risk a 500 or an orphaned record.
            db.session.rollback()
            return "records we could not fully check"
    return None


@bp.post("/users/<int:uid>/delete")
@require_role(*SUPER)
def user_delete(uid: int):
    """Permanently delete a user — only when they have no history.

    Staff who have signed inspections or held duty CANNOT be deleted: their
    records must keep a real author for the audit trail to mean anything.
    Deactivate those accounts instead (the button says so).
    """
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    if u.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))
    if u.role == "SUPER_ADMIN":
        remaining = (db.session.query(User)
                     .filter(User.org_id == current_user.org_id, User.role == "SUPER_ADMIN",
                             User.id != u.id).count())
        if remaining == 0:
            flash("You cannot delete the last Super Admin.", "error")
            return redirect(url_for("admin.users"))
    blocked = _user_has_history(u)
    if blocked:
        flash(f"{u.name} cannot be deleted because they have {blocked}. "
              "Deactivate the account instead — this keeps the records honest.", "error")
        return redirect(url_for("admin.users"))
    label = f"{u.name} ({u.username})"
    audit("USER_DELETED", "user", u.id, {"username": u.username, "role": u.role})
    db.session.delete(u)
    # BELT AND BRACES. The list above should catch everything, but a future
    # table could add another link to user.id and nobody would remember to
    # update it. If the database refuses the delete, the administrator must
    # get a sentence they can act on — never a bare "500 Something went wrong".
    try:
        db.session.commit()
    except Exception:                                        # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("user delete refused by the database")
        flash(f"{u.name} cannot be deleted because their name is still "
              f"attached to records elsewhere in the system. Use "
              f"\u201cSuspend\u201d instead — the account stops working "
              f"immediately and the records keep an honest author.", "error")
        return redirect(url_for("admin.users"))
    flash(f"User {label} permanently deleted.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/reset-password")
@require_role(*SUPER)
def user_reset_password(uid: int):
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    pw = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""
    errs = password_strength_errors(pw, username=u.username, email=u.email or "")
    if confirm and pw != confirm:
        errs = ["The two passwords do not match."] + list(errs)
    if errs:
        for e in errs:
            flash(e, "error")
        # Back to the page they were on, with the rules still in front of
        # them — not to a list where the error scrolls away unseen.
        return redirect(url_for("admin.user_password", uid=u.id))
    u.set_password(pw)
    u.must_change_password = True
    audit("PASSWORD_RESET", "user", u.id, {"target": u.username})
    db.session.commit()
    flash(f"Password reset for {u.username}. They must change it at next login.", "success")
    return redirect(url_for("admin.users"))


@bp.get("/users/<int:uid>/password")
@require_role(*SUPER)
def user_password(uid: int):
    """A real page for resetting one person's password.

    This used to be a <details> popover inside a horizontally scrolling table.
    On a phone the panel was clipped by the table, so tapping "Reset password"
    appeared to do nothing at all. A page has room for the rules, a
    confirmation box, and an error the administrator can actually read.
    """
    u = db.session.get(User, uid)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    return render_template("admin/user_password.html", u=u)


# ------------------------------------------------------------------ departments
@bp.get("/structure")
@require_role(*SUPER)
def structure():
    depts = (db.session.query(Department).filter_by(org_id=current_user.org_id)
             .order_by(Department.name).all())
    hods = db.session.query(User).filter_by(org_id=current_user.org_id, active=True)\
        .filter(User.role.in_(("HOD", "MD_CEO", "SUPER_ADMIN"))).order_by(User.name).all()
    from ..models import ROSTER_MODE_LABELS
    return render_template("admin/structure.html", depts=depts, hods=hods,
                           roster_modes=ROSTER_MODE_LABELS)


@bp.post("/structure/department")
@require_role(*SUPER)
def department_save():
    name = (request.form.get("name") or "").strip()
    hod_id = request.form.get("hod_user_id", type=int)
    dept_id = request.form.get("department_id", type=int)
    hod_name = (request.form.get("hod_name") or "").strip()
    hod_phone = (request.form.get("hod_phone") or "").strip().replace(" ", "").replace("-", "")
    if not name:
        flash("Department name is required.", "error")
        return redirect(url_for("admin.structure"))
    # A new department must name a head and give a reachable number: complaint
    # routing and SLA escalation depend on being able to contact the HOD.
    # If an HOD staff account was picked, fall back to that account's details.
    if hod_id:
        picked = db.session.get(User, hod_id)
        if picked and picked.org_id == current_user.org_id:
            hod_name = hod_name or picked.name
            hod_phone = hod_phone or clean_phone(picked.phone or "")
    # A new department must name a head and give a reachable number: complaint
    # routing and SLA escalation depend on being able to contact the HOD.
    if not dept_id and (not hod_name or not hod_phone):
        flash("HOD name and HOD phone number are required for a new department.", "error")
        return redirect(url_for("admin.structure"))
    if hod_phone and not PHONE_RE.match(hod_phone):
        flash("Enter a valid HOD phone number (digits only, e.g. 08012345678).", "error")
        return redirect(url_for("admin.structure"))
    from ..models import DEPT_SHIFTS
    roster_mode = request.form.get("roster_mode")
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
        audit("DEPARTMENT_UPDATED", "department", dept.id,
              {"name": name, "roster_mode": roster_mode, "staff_per_shift": per_shift})
    else:
        exists = db.session.query(Department).filter_by(org_id=current_user.org_id, name=name).first()
        if exists:
            flash("A department with that name already exists.", "error")
            return redirect(url_for("admin.structure"))
        dept = Department(org_id=current_user.org_id, name=name, hod_user_id=hod_id or None,
                          hod_name=hod_name or None, hod_phone=hod_phone or None,
                          roster_mode=roster_mode, roster_staff_per_shift=per_shift)
        db.session.add(dept)
        db.session.flush()
        audit("DEPARTMENT_CREATED", "department", dept.id,
              {"name": name, "roster_mode": roster_mode, "staff_per_shift": per_shift})
    db.session.commit()
    flash("Department saved.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/install-standard")
@require_role(*SUPER)
def install_standard_departments():
    """Add any missing standard general-hospital departments.

    Existing departments are never touched, so a hospital that has already
    customised its structure can safely top up what it is missing.
    """
    from ..standard_departments import install as install_standard
    try:
        made = install_standard(current_user.org_id, only_missing=True)
        audit("STANDARD_DEPARTMENTS_INSTALLED", "organization", current_user.org_id, made)
        db.session.commit()
    except Exception as exc:                          # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("standard department install failed")
        flash(f"Could not add the standard departments: {exc}", "error")
        return redirect(url_for("admin.structure"))
    if made["departments"]:
        flash(f"Added {made['departments']} department(s), {made['sections']} section(s) "
              f"and {made['units']} unit(s). Existing ones were left unchanged.", "success")
    else:
        flash("You already have all the standard departments — nothing to add.", "info")
    return redirect(url_for("admin.structure"))


def _dept_referenced(d) -> str | None:
    """Return a reason if the department has live data (block hard delete)."""
    from ..models import (Appointment, Complaint, DeptRosterEntry, Inspection,
                          PatientFeedback, QueueTicket, Referral, RosterEntry)
    checks = [
        (Inspection.department_id, "inspections"), (Complaint.department_id, "complaints"),
        (Appointment.department_id, "bookings"), (QueueTicket.department_id, "queue tickets"),
        (PatientFeedback.department_id, "feedback"), (DeptRosterEntry.department_id, "roster entries"),
        (RosterEntry.department_id, "roster entries"),
        (Referral.department_id, "referral links"),
    ]
    for col, label in checks:
        if db.session.query(col).filter(col == d.id).first() is not None:
            return label
    return None


@bp.post("/structure/department/<int:did>/delete")
@require_role(*SUPER)
def department_delete(did: int):
    d = db.session.get(Department, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    if d.sections:
        flash("Delete its sections/units first, or use Suspend (deactivate) instead.", "error")
        return redirect(url_for("admin.structure"))
    why = _dept_referenced(d)
    if why:
        flash(f"This department has {why} attached — it cannot be deleted. Use Suspend instead.", "error")
        return redirect(url_for("admin.structure"))
    audit("DEPARTMENT_DELETED", "department", d.id, {"name": d.name})
    db.session.delete(d)
    db.session.commit()
    flash(f"Department {d.name} deleted.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/section/<int:sid>/edit")
@require_role(*SUPER)
def section_edit(sid: int):
    s = db.session.get(Section, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Section name required.", "error")
        return redirect(url_for("admin.structure"))
    old = s.name
    s.name = name
    s.hod_user_id = request.form.get("hod_user_id", type=int) or None
    audit("SECTION_EDITED", "section", sid, {"old": old, "new": name})
    db.session.commit()
    flash("Section updated.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/section/<int:sid>/delete")
@require_role(*SUPER)
def section_delete(sid: int):
    s = db.session.get(Section, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    if s.units:
        flash("Delete its units first.", "error")
        return redirect(url_for("admin.structure"))
    from ..models import Inspection
    if db.session.query(Inspection).filter_by(section_id=s.id).first():
        flash("Inspections reference this section — it cannot be deleted.", "error")
        return redirect(url_for("admin.structure"))
    audit("SECTION_DELETED", "section", sid, {"name": s.name})
    db.session.delete(s)
    db.session.commit()
    flash("Section deleted.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/unit/<int:uid_>/edit")
@require_role(*SUPER)
def unit_edit(uid_: int):
    u = db.session.get(Unit, uid_)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Unit name required.", "error")
        return redirect(url_for("admin.structure"))
    old = u.name
    u.name = name
    u.hod_user_id = request.form.get("hod_user_id", type=int) or None
    audit("UNIT_EDITED", "unit", u.id, {"old": old, "new": name})
    db.session.commit()
    flash("Unit updated.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/unit/<int:uid_>/delete")
@require_role(*SUPER)
def unit_delete(uid_: int):
    u = db.session.get(Unit, uid_)
    if not u or u.org_id != current_user.org_id:
        abort(404)
    from ..models import Inspection
    if db.session.query(Inspection).filter_by(unit_id=u.id).first():
        flash("Inspections reference this unit — it cannot be deleted.", "error")
        return redirect(url_for("admin.structure"))
    audit("UNIT_DELETED", "unit", u.id, {"name": u.name})
    db.session.delete(u)
    db.session.commit()
    flash("Unit deleted.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/settings/categories/<int:cid>/toggle")
@require_role(*SUPER)
def category_toggle(cid: int):
    c = db.session.get(ComplaintCategory, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    c.active = not c.active
    audit("CATEGORY_TOGGLED", "category", cid, {"name": c.name, "active": c.active})
    db.session.commit()
    return redirect(url_for("admin.settings"))


@bp.post("/settings/categories/<int:cid>/delete")
@require_role(*SUPER)
def category_delete(cid: int):
    c = db.session.get(ComplaintCategory, cid)
    if not c or c.org_id != current_user.org_id:
        abort(404)
    from ..models import Complaint
    if db.session.query(Complaint).filter_by(category=c.name).first():
        flash("Complaints use this category — suspend it instead of deleting.", "error")
        return redirect(url_for("admin.settings"))
    audit("CATEGORY_DELETED", "category", cid, {"name": c.name})
    db.session.delete(c)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin.settings"))


@bp.post("/settings/locations/<int:lid>/edit")
@require_role(*SUPER)
def location_edit(lid: int):
    l = db.session.get(QrLocation, lid)
    if not l or l.org_id != current_user.org_id:
        abort(404)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Location name required.", "error")
        return redirect(url_for("admin.settings"))
    old = l.name
    l.name = name
    audit("QR_LOCATION_EDITED", "qr_location", lid, {"old": old, "new": name})
    db.session.commit()
    flash("Location renamed.", "success")
    return redirect(url_for("admin.settings"))


@bp.post("/settings/locations/<int:lid>/delete")
@require_role(*SUPER)
def location_delete(lid: int):
    l = db.session.get(QrLocation, lid)
    if not l or l.org_id != current_user.org_id:
        abort(404)
    from ..models import Appointment, Complaint
    if db.session.query(Complaint).filter_by(qr_location_id=l.id).first() or \
       db.session.query(Appointment).filter_by(qr_location_id=l.id).first():
        flash("Records reference this location — it cannot be deleted.", "error")
        return redirect(url_for("admin.settings"))
    audit("QR_LOCATION_DELETED", "qr_location", lid, {"name": l.name})
    db.session.delete(l)
    db.session.commit()
    flash("Location deleted.", "success")
    return redirect(url_for("admin.settings"))


@bp.post("/structure/section")
@require_role(*SUPER)
def section_save():
    dept = db.session.get(Department, request.form.get("department_id", type=int) or 0)
    name = (request.form.get("name") or "").strip()
    if not dept or dept.org_id != current_user.org_id or not name:
        flash("Select a department and provide a section name.", "error")
        return redirect(url_for("admin.structure"))
    db.session.add(Section(org_id=current_user.org_id, department_id=dept.id, name=name,
                           hod_user_id=request.form.get("hod_user_id", type=int) or None))
    audit("SECTION_CREATED", "section", None, {"name": name, "dept": dept.name})
    db.session.commit()
    flash("Section added.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/unit")
@require_role(*SUPER)
def unit_save():
    section = db.session.get(Section, request.form.get("section_id", type=int) or 0)
    name = (request.form.get("name") or "").strip()
    if not section or section.org_id != current_user.org_id or not name:
        flash("Select a section and provide a unit name.", "error")
        return redirect(url_for("admin.structure"))
    db.session.add(Unit(org_id=current_user.org_id, department_id=section.department_id,
                        section_id=section.id, name=name,
                        hod_user_id=request.form.get("hod_user_id", type=int) or None))
    audit("UNIT_CREATED", "unit", None, {"name": name})
    db.session.commit()
    flash("Unit added.", "success")
    return redirect(url_for("admin.structure"))


@bp.post("/structure/department/<int:did>/toggle")
@require_role(*SUPER)
def department_toggle(did: int):
    d = db.session.get(Department, did)
    if not d or d.org_id != current_user.org_id:
        abort(404)
    d.active = not d.active
    audit("DEPARTMENT_TOGGLED", "department", d.id, {"active": d.active})
    db.session.commit()
    return redirect(url_for("admin.structure"))


# ------------------------------------------------------------------ settings
@bp.get("/settings")
@require_role(*SUPER)
def settings():
    org_id = current_user.org_id
    cats = db.session.query(ComplaintCategory).filter_by(org_id=org_id).order_by(ComplaintCategory.name).all()
    locs = db.session.query(QrLocation).filter_by(org_id=org_id).order_by(QrLocation.name).all()
    return render_template("admin/settings.html", s=services.org_settings_bundle(org_id),
                           categories=cats, locations=locs, settings_mode=whatsapp.mode())


@bp.post("/settings")
@require_role(*SUPER)
def settings_save():
    org_id = current_user.org_id
    f = request.form
    try:
        sla = max(1, min(336, int(f.get("sla_hours") or 24)))
    except ValueError:
        sla = 24
    services.set_setting(org_id, "sla_hours", sla)
    services.set_setting(org_id, "reminder_day_before_time", f.get("reminder_day_before_time") or "18:00")
    services.set_setting(org_id, "reminder_duty_day_time", f.get("reminder_duty_day_time") or "07:00")
    services.set_setting(org_id, "inspection_deadline_time", f.get("inspection_deadline_time") or "18:00")
    services.set_setting(org_id, "overdue_notify_time", f.get("overdue_notify_time") or "19:00")
    gps = f.get("gps_mode")
    services.set_setting(org_id, "gps_mode", gps if gps in ("mandatory", "optional", "disabled") else "optional")
    services.set_setting(org_id, "whatsapp_md_number", (f.get("whatsapp_md_number") or "").strip())
    try:
        services.set_setting(org_id, "multiple_two_threshold", max(1, int(f.get("multiple_two_threshold") or 2)))
        services.set_setting(org_id, "recurring_window", max(3, int(f.get("recurring_window") or 10)))
        services.set_setting(org_id, "recurring_threshold", max(2, int(f.get("recurring_threshold") or 3)))
        services.set_setting(org_id, "retention_days", max(30, int(f.get("retention_days") or 2190)))
    except ValueError:
        pass
    channels = f.getlist("reminder_channels")
    services.set_setting(org_id, "reminder_channels",
                         [c for c in channels if c in ("inapp", "email", "whatsapp", "sms")] or ["inapp"])
    # booking settings
    try:
        services.set_setting(org_id, "booking_window_days", max(1, int(f.get("booking_window_days") or 30)))
        services.set_setting(org_id, "booking_capacity_per_slot", max(1, int(f.get("booking_capacity_per_slot") or 20)))
    except ValueError:
        pass
    raw_slots = [x.strip() for x in (f.get("booking_slots") or "").split(",") if x.strip()]
    import re as _re
    valid_slots = [x for x in raw_slots if _re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", x)]
    if valid_slots:
        services.set_setting(org_id, "booking_slots", valid_slots)
    services.set_setting(org_id, "booking_confirmation_sms", bool(f.get("booking_confirmation_sms")))
    # ---- Fast Track executive premium (per-tenant pricing) ----
    try:
        ft_price_raw = (f.get("fast_track_price") or "15000").replace(",", "").strip()
        ft_price = int(ft_price_raw or 15000)
        services.set_setting(org_id, "fast_track_price", max(0, min(1000000, ft_price)))
    except ValueError:
        pass
    services.set_setting(org_id, "fast_track_currency", (f.get("fast_track_currency") or "NGN").strip().upper()[:6] or "NGN")
    services.set_setting(org_id, "fast_track_building_name", (f.get("fast_track_building_name") or "Executive Premium Building").strip()[:120] or "Executive Premium Building")
    services.set_setting(org_id, "fast_track_description", (f.get("fast_track_description") or "").strip()[:500])
    services.set_setting(org_id, "fast_track_payment_instructions", (f.get("fast_track_payment_instructions") or "").strip()[:500])
    services.set_setting(org_id, "fast_track_price_note", (f.get("fast_track_price_note") or "").strip()[:300])
    services.set_setting(org_id, "fast_track_enabled", bool(f.get("fast_track_enabled")))
    services.set_setting(org_id, "fast_track_booking_requires_payment", bool(f.get("fast_track_booking_requires_payment")))
    # ---- Per-org VAPID for push — multi-hospital, shows hospital name/logo on phone home screen
    # If set per org, overrides global env VAPID_PUBLIC_KEY/PRIVATE/SUBJECT
    # Founder rule: Main App Logo upload shown on phone home screen + push works closed like alarm
    vapid_pub = (f.get("vapid_public_key") or "").strip()
    vapid_priv = (f.get("vapid_private_key") or "").strip()
    vapid_subj = (f.get("vapid_subject") or "").strip()
    # Only save if provided, allow clearing by empty? Save if length >10 to avoid accidental clear
    if vapid_pub and len(vapid_pub) > 20:
        services.set_setting(org_id, "vapid_public_key", vapid_pub)
    elif f.get("vapid_public_key") == "":
        # Explicit clear
        services.set_setting(org_id, "vapid_public_key", "")
    if vapid_priv and len(vapid_priv) > 20:
        services.set_setting(org_id, "vapid_private_key", vapid_priv)
    elif f.get("vapid_private_key") == "":
        services.set_setting(org_id, "vapid_private_key", "")
    if vapid_subj:
        services.set_setting(org_id, "vapid_subject", vapid_subj)
    elif f.get("vapid_subject") == "":
        services.set_setting(org_id, "vapid_subject", "")
    # ---- Staff clock-in fence (per hospital)
    from .. import attendance as att
    mode = (f.get("attendance_mode") or "off").strip()
    if mode not in att.MODES:
        mode = "off"
    services.set_setting(org_id, "attendance_mode", mode)
    services.set_setting(org_id, "attendance_radius_m",
                         att.parse_radius(f.get("attendance_radius_m")))
    services.set_setting(org_id, "attendance_lat",
                         att.parse_coord(f.get("attendance_lat"), kind="lat"))
    services.set_setting(org_id, "attendance_lng",
                         att.parse_coord(f.get("attendance_lng"), kind="lng"))
    services.set_setting(org_id, "attendance_grace_minutes",
                         att.parse_grace(f.get("attendance_grace_minutes")))
    audit("SETTINGS_UPDATED", "settings", org_id,
          {"sla_hours": sla, "gps_mode": services.get_setting(org_id, "gps_mode"),
           "fast_track_price": services.get_setting(org_id, "fast_track_price")})
    db.session.commit()
    flash("Settings saved.", "success")
    return redirect(url_for("admin.settings"))


@bp.post("/settings/categories")
@require_role(*SUPER)
def category_add():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Category name required.", "error")
        return redirect(url_for("admin.settings"))
    exists = db.session.query(ComplaintCategory).filter_by(org_id=current_user.org_id, name=name).first()
    if exists:
        exists.active = True
    else:
        db.session.add(ComplaintCategory(org_id=current_user.org_id, name=name))
    audit("CATEGORY_ADDED", "category", None, {"name": name})
    db.session.commit()
    flash("Complaint category added.", "success")
    return redirect(url_for("admin.settings"))


@bp.post("/settings/locations")
@require_role(*SUPER)
def location_add():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Location name required.", "error")
        return redirect(url_for("admin.settings"))
    exists = db.session.query(QrLocation).filter_by(org_id=current_user.org_id, name=name).first()
    if not exists:
        db.session.add(QrLocation(org_id=current_user.org_id, name=name, code=new_code(6)))
        audit("QR_LOCATION_ADDED", "qr_location", None, {"name": name})
    db.session.commit()
    flash("QR location added.", "success")
    return redirect(url_for("admin.settings"))


# ------------------------------------------------------------------ WhatsApp / notifications
@bp.get("/notifications")
@require_role(*SUPER_MD)
def notification_logs():
    wa = (db.session.query(WhatsAppMessage).filter_by(org_id=current_user.org_id)
          .order_by(WhatsAppMessage.created_at.desc()).limit(100).all())
    app = (db.session.query(AppNotification).filter_by(org_id=current_user.org_id)
           .order_by(AppNotification.created_at.desc()).limit(200).all())
    from ..models import SmsMessage
    sms_rows = (db.session.query(SmsMessage).filter_by(org_id=current_user.org_id)
                .order_by(SmsMessage.created_at.desc()).limit(100).all())
    from flask import current_app as _ca
    return render_template("admin/notifications.html", wa=wa, app=app, sms=sms_rows,
                           mode=whatsapp.mode(), sms_mode=_ca.config.get("SMS_MODE", "sandbox"),
                           md_number=services.get_setting(current_user.org_id, "whatsapp_md_number"))


@bp.post("/notifications/whatsapp/<int:mid>/retry")
@require_role(*SUPER_MD)
def whatsapp_retry(mid: int):
    m = db.session.get(WhatsAppMessage, mid)
    if not m or m.org_id != current_user.org_id:
        abort(404)
    m.status = "QUEUED"
    m.attempts = 0
    db.session.commit()
    whatsapp.send_message(m)
    audit("WHATSAPP_RETRY", "whatsapp", m.id, {"status": m.status})
    db.session.commit()
    flash(f"WhatsApp message retried — status: {m.status}" +
          (f" ({m.last_error})" if m.last_error else ""), "success" if m.status in ("SENT", "DELIVERED") else "error")
    return redirect(url_for("admin.notification_logs"))


@bp.post("/notifications/whatsapp/test")
@require_role(*SUPER)
def whatsapp_test():
    number = (request.form.get("number") or "").strip()
    if not number:
        flash("Enter a destination number (E.164, e.g. 2348012345678).", "error")
        return redirect(url_for("admin.notification_logs"))
    m = whatsapp.queue_message(current_user.org_id, number,
                               "Test message from Hospital Admin Manager Suite.", kind="alert")
    whatsapp.send_message(m)
    audit("WHATSAPP_TEST", "whatsapp", m.id, {"to": number, "status": m.status})
    db.session.commit()
    flash(f"Test message {m.status.lower()}." + (f" Error: {m.last_error}" if m.last_error else ""),
          "success" if m.status in ("SENT", "DELIVERED") else "error")
    return redirect(url_for("admin.notification_logs"))


# ------------------------------------------------------------------ QR poster pack (§43A)
POSTER_SERVICES = {
    "complaint": {
        "title": "Make a Complaint",
        "subtitle": "Your voice matters — we listen and act",
        "steps": ["Point your phone camera at the QR code",
                  "Choose the department and describe the problem (typing or speaking)",
                  "Get your reference number instantly — management is notified immediately"],
        "path": "/complaint",
    },
    "booking": {
        "title": "Book a Hospital Visit",
        "subtitle": "Skip the uncertainty — reserve your slot in 1 minute",
        "steps": ["Scan the QR code with your phone camera",
                  "Pick the service, date and time that suits you",
                  "Save your booking reference — see it at reception on arrival"],
        "path": "/book",
    },
    "queue": {
        "title": "Join the Queue",
        "subtitle": "Get your number and track your position",
        "steps": ["Scan the QR code with your phone camera",
                  "Enter your name to receive a queue number",
                  "Watch your position live — you'll get an SMS when it's your turn"],
        "path": "/queue/join",
    },
    "feedback": {
        "title": "Rate Your Experience",
        "subtitle": "1 minute of feedback makes care better for everyone",
        "steps": ["Scan the QR code after your visit",
                  "Tap a star rating — add a comment by typing or speaking",
                  "Low ratings reach management immediately; high ratings help us improve"],
        "path": "/feedback",
    },
    "referral": {
        "title": "Recommend Us to Family",
        "subtitle": "Share good care — no account, no pressure, no prizes",
        "steps": ["Scan the QR code with your phone camera",
                  "Share the page with a friend or family member who needs care",
                  "They can book a visit in one minute — the hospital will know you sent them"],
        "path": "/r/",
    },
}


@bp.get("/posters")
@require_role(*SUPER)
def posters():
    locs = db.session.query(QrLocation).filter_by(org_id=current_user.org_id).order_by(QrLocation.name).all()
    return render_template("admin/posters.html", locs=locs, services=POSTER_SERVICES,
                           base=Config.PUBLIC_BASE_URL)


@bp.get("/posters/download")
@require_role(*SUPER)
def posters_download():
    org = db.session.get(Organization, current_user.org_id)
    from ..config import Config as _Cfg
    wanted = [s for s in (request.args.get("services") or "").split(",") if s in POSTER_SERVICES] \
        or list(POSTER_SERVICES.keys())
    locs = db.session.query(QrLocation).filter_by(org_id=org.id).order_by(QrLocation.name).all()
    posters = []
    base = _Cfg.PUBLIC_BASE_URL.rstrip("/")
    hospital_code = None
    if "referral" in wanted:
        from .. import referrals as refeng
        hospital_code = refeng.ensure_hospital_referral(org).code
        db.session.commit()
    for svc_key in wanted:
        svc = POSTER_SERVICES[svc_key]
        if svc_key in ("complaint", "booking") and locs:
            for loc in locs:
                posters.append({
                    "title": svc["title"],
                    "subtitle": f"{svc['subtitle']}  ·  📍 {loc.name}",
                    "url": f"{base}{svc['path']}?loc={loc.code}",
                    "steps": svc["steps"],
                })
        elif svc_key == "referral":
            posters.append({"title": svc["title"], "subtitle": svc["subtitle"],
                            "url": f"{base}/r/{hospital_code}", "steps": svc["steps"]})
        else:
            posters.append({"title": svc["title"], "subtitle": svc["subtitle"],
                            "url": f"{base}{svc['path']}", "steps": svc["steps"]})
    from .. import pdfgen, storage
    path = f"reports/qr-posters-{new_code(4)}.pdf"
    storage.build_pdf(pdfgen.build_poster_pdf, path, org, posters, org_id=org.id)
    rf = ReportFile(org_id=org.id, kind="posters", title=f"QR Poster Pack ({len(posters)} posters)",
                    path=path, verify_code=new_code(10), created_by_id=current_user.id)
    db.session.add(rf)
    audit("POSTERS_GENERATED", "report", None, {"count": len(posters), "services": wanted})
    db.session.commit()
    return storage.send(path, as_attachment=True, download_name="QR-Poster-Pack.pdf",
                        mimetype="application/pdf")


# ------------------------------------------------------------------ audit log
@bp.get("/audit")
@require_role(*SUPER_MD)
def audit_log():
    q = db.session.query(AuditLog).filter_by(org_id=current_user.org_id)
    action = request.args.get("action")
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    items = q.order_by(AuditLog.id.desc()).limit(300).all()
    ok, n = verify_chain(current_user.org_id)
    return render_template("admin/audit.html", items=items, chain_ok=ok, chain_rows=n,
                           action=action or "")


# ------------------------------------------------------------------ backups
@bp.post("/backup")
@require_role(*SUPER)
def backup_now():
    """Create a real backup on ANY engine (SQLite or PostgreSQL)."""
    from flask import current_app
    from ..backup import create_backup, prune_backups
    try:
        key, size = create_backup(current_app, kind="manual")
        prune_backups(keep=Config.BACKUP_KEEP)
        audit("BACKUP_MANUAL", "system", None, {"key": key, "bytes": size})
        db.session.commit()
        flash(f"Backup created ({size // 1024} KB). Download it below and keep a "
              "copy somewhere outside this server.", "success")
    except Exception as exc:                      # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("manual backup failed")
        flash(f"Backup failed: {exc}", "error")
    return redirect(url_for("admin.overview"))


@bp.get("/backup/download/<name>")
@require_role(*SUPER)
def backup_download(name: str):
    """Download a backup archive from durable storage."""
    from .. import storage
    safe = os.path.basename(name)
    if not (safe.endswith(".zip") or safe.endswith(".db")):
        abort(404)
    try:
        resp = storage.send(f"backups/{safe}", as_attachment=True, download_name=safe)
    except FileNotFoundError:
        abort(404)
    audit("BACKUP_DOWNLOADED", "system", None, {"file": safe})
    db.session.commit()
    return resp


# ------------------------------------------------------------------ system health
@bp.get("/health")
@require_role(*SUPER)
def health():
    from ..chatbot import ai
    ai_status = ai.status(current_user.org_id)
    from .. import mailer
    mail = mailer.status()
    info = {
        "database": "connected" if db.session.execute(db.text("SELECT 1")).scalar() == 1 else "error",
        "whatsapp_mode": whatsapp.mode(),
        "backup_dir": Config.BACKUP_DIR,
        "disk": None,
        "mail": mail,
    }
    try:
        usage = shutil.disk_usage(os.path.dirname(Config.BACKUP_DIR))
        info["disk"] = f"{usage.free / 1e9:.1f} GB free of {usage.total / 1e9:.1f} GB"
    except OSError:
        pass
    return render_template("admin/health.html", info=info, ai=ai_status)


@bp.post("/health/test-mail")
@require_role(*SUPER)
def health_test_mail():
    """Send one letter to the signed-in admin so they can see if mail works."""
    from .. import mailer
    dest = (current_user.email or "").strip()
    if not dest:
        flash("Your own account has no email. Add one on Users first.", "error")
        return redirect(url_for("admin.health"))
    ok, detail = mailer.send_mail(
        dest,
        "Hospital Suite test letter",
        "This is a test. If you can read this, the 6-digit codes can leave the hospital.",
    )
    audit("MAIL_TEST", "system", None, {"ok": ok, "detail": detail, "to": dest})
    db.session.commit()
    if ok:
        flash(f"Test letter sent to {dest} via {detail}. Check the inbox (and Spam).", "success")
    else:
        flash(f"Test letter did not leave: {detail}", "error")
    return redirect(url_for("admin.health"))


# ================================================================ KB / chatbot admin (§SaaS)
@bp.post("/kb/sync")
@require_role(*SUPER)
def kb_sync():
    """Ship newly-added global dialogues to this deployment (no edits lost)."""
    from ..chatbot.seed_kb import seed_global_kb
    added = seed_global_kb(current_app)
    audit("KB_GLOBAL_SYNC", "kb", None, {"added": added})
    db.session.commit()
    flash(f"Global library updated — {added} new dialogue(s) added." if added
          else "Global library is already up to date.", "success")
    return redirect(url_for("admin.kb_list", scope="global"))


@bp.get("/kb")
@require_role(*SUPER_MD)
def kb_list():
    from ..models import KnowledgeArticle
    q = db.session.query(KnowledgeArticle)
    scope = request.args.get("scope")
    if scope == "global":
        q = q.filter(KnowledgeArticle.org_id.is_(None))
    elif scope == "tenant":
        q = q.filter(KnowledgeArticle.org_id == current_user.org_id)
    elif scope == "pending":
        q = q.filter(KnowledgeArticle.status == "pending")
    else:
        q = q.filter(db.or_(KnowledgeArticle.org_id.is_(None),
                            KnowledgeArticle.org_id == current_user.org_id))
    items = q.order_by(KnowledgeArticle.category, KnowledgeArticle.intent).limit(400).all()
    return render_template("admin/kb.html", items=items, scope=scope or "all")


# ------------------------------------------------------------------ quick edit
@bp.get("/kb/code")
@require_role("SUPER_ADMIN")
def kb_code():
    """Set the word that lets the Super Admin correct answers from the chat."""
    from ..chatbot import quickedit
    return render_template("admin/kb_code.html",
                           has_code=quickedit.has_code(current_user.org_id),
                           suggestion=quickedit.suggest_code())


@bp.post("/kb/code")
@require_role("SUPER_ADMIN")
def kb_code_save():
    from ..chatbot import quickedit
    ok, message = quickedit.set_code(current_user.org_id,
                                     request.form.get("code", ""))
    if ok:
        # The code itself is NEVER written to the audit log.
        audit("KB_QUICK_EDIT_CODE_SET", "organization", current_user.org_id, {})
        db.session.commit()
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.kb_code"))


# ------------------------------------------------------------------ learning
@bp.get("/kb/learning")
@require_role(*SUPER_MD)
def kb_learning():
    """What the assistant has learned from real conversations, awaiting a tap.

    The assistant NEVER changes what it tells patients on its own. It watches,
    it proposes, a human approves. An answer nobody approved is an answer
    nobody is accountable for — and this app talks to sick people.
    """
    from ..chatbot import learning
    days = max(1, min(request.args.get("days", type=int) or 30, 180))
    org_id = current_user.org_id
    # Worked out once and shared: a word already proposed as a missing TRIGGER
    # must not also be listed as a missing ANSWER.
    _words = learning.missing_words(org_id, days)
    return render_template(
        "admin/kb_learning.html", days=days,
        accuracy=learning.accuracy(org_id, days),
        missing_words=_words,
        missing_answers=learning.missing_answers(
            org_id, days, exclude_words={w["word"] for w in _words}),
        failing=learning.failing_answers(org_id),
        coin_flips=learning.coin_flip_matches(org_id, days),
        corrections=learning.corrections(org_id))


@bp.post("/kb/learn-word")
@require_role(*SUPER_MD)
def kb_learn_word():
    """Approve ONE new trigger word for an answer that already exists.

    The safest kind of learning there is: the words a patient reads do not
    change at all, an approved answer simply becomes findable.
    """
    from ..chatbot import learning
    ok, message = learning.add_keyword(
        current_user.org_id,
        request.form.get("article_id", type=int) or 0,
        request.form.get("word", ""),
        user_id=current_user.id)
    if ok:
        audit("KB_LEARNED_KEYWORD", "knowledge_article",
              request.form.get("article_id", type=int),
              {"word": request.form.get("word", "")})
        db.session.commit()
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.kb_learning"))


@bp.post("/kb/dismiss-note/<int:mid>")
@require_role(*SUPER_MD)
def kb_dismiss_note(mid: int):
    """Mark a correction as dealt with, so the list stays honest."""
    from ..models import ChatMessage
    m = db.session.get(ChatMessage, mid)
    if m is not None:
        m.unanswered = False
        audit("KB_NOTE_ACTIONED", "chat_message", mid, {})
        db.session.commit()
    flash("Marked as dealt with.", "success")
    return redirect(url_for("admin.kb_learning"))


@bp.post("/kb/add")
@require_role(*SUPER_MD)
def kb_add():
    from ..models import KnowledgeArticle
    f = request.form
    intent = (f.get("intent") or "").strip()
    en = (f.get("en") or "").strip()
    if not intent or not en:
        flash("Intent and English response are required.", "error")
        return redirect(url_for("admin.kb_list"))
    is_super = current_user.is_super
    db.session.add(KnowledgeArticle(
        org_id=None if (is_super and f.get("scope") == "global") else current_user.org_id,
        scope="global" if (is_super and f.get("scope") == "global") else "tenant",
        status="approved" if is_super else "pending",
        category=(f.get("category") or "general").strip(),
        intent=intent,
        keywords=(f.get("keywords") or "").replace(",", "\n"),
        en=en, pidgin=f.get("pidgin") or None, yo=f.get("yo") or None,
        ha=f.get("ha") or None, ig=f.get("ig") or None, cta=f.get("cta") or None,
        submitted_by=current_user.id,
        approved_by=current_user.id if is_super else None))
    audit("KB_ADDED", "kb", None, {"intent": intent, "scope": f.get("scope")})
    db.session.commit()
    flash("Dialogue added." if is_super else
          "Dialogue submitted — pending approval before it goes live.", "success")
    return redirect(url_for("admin.kb_list"))


@bp.post("/kb/<int:kid>/edit")
@require_role(*SUPER_MD)
def kb_edit(kid: int):
    from ..models import KnowledgeArticle
    a = db.session.get(KnowledgeArticle, kid)
    if not a or (a.org_id and a.org_id != current_user.org_id and not current_user.is_super):
        abort(404)
    # The shared global library is every hospital's assistant — only a Super
    # Administrator may rewrite or remove it. A tenant's head office edits
    # their own hospital's voice, never the shared one (the same invariant
    # the keyword-learning path already enforces).
    if a.org_id is None and not current_user.is_super:
        abort(404)
    f = request.form
    a.intent = (f.get("intent") or a.intent).strip()
    a.category = (f.get("category") or a.category).strip()
    a.keywords = (f.get("keywords") or a.keywords).replace(",", "\n")
    a.en = (f.get("en") or a.en).strip()
    a.pidgin = f.get("pidgin") or None
    a.yo = f.get("yo") or None
    a.ha = f.get("ha") or None
    a.ig = f.get("ig") or None
    a.cta = f.get("cta") or None
    audit("KB_EDITED", "kb", kid, {"intent": a.intent})
    db.session.commit()
    flash("Dialogue updated.", "success")
    return redirect(url_for("admin.kb_list", scope=request.args.get("scope") or "all"))


@bp.post("/kb/<int:kid>/approve")
@require_role(*SUPER)
def kb_approve(kid: int):
    from ..models import KnowledgeArticle
    a = db.session.get(KnowledgeArticle, kid)
    if not a:
        abort(404)
    a.status = "approved"
    a.approved_by = current_user.id
    audit("KB_APPROVED", "kb", kid, {"intent": a.intent})
    db.session.commit()
    flash("Dialogue approved and live.", "success")
    return redirect(url_for("admin.kb_list", scope="pending"))


@bp.post("/kb/<int:kid>/promote")
@require_role(*SUPER)
def kb_promote(kid: int):
    """Learning loop: promote a good tenant answer into the global master library."""
    from ..models import KnowledgeArticle
    a = db.session.get(KnowledgeArticle, kid)
    if not a:
        abort(404)
    a.org_id = None
    a.scope = "global"
    a.status = "approved"
    a.approved_by = current_user.id
    audit("KB_PROMOTED_TO_GLOBAL", "kb", kid, {"intent": a.intent})
    db.session.commit()
    flash("Promoted to the global master library.", "success")
    return redirect(url_for("admin.kb_list"))


@bp.post("/kb/<int:kid>/delete")
@require_role(*SUPER_MD)
def kb_delete(kid: int):
    from ..models import KnowledgeArticle
    a = db.session.get(KnowledgeArticle, kid)
    if not a or (a.org_id and a.org_id != current_user.org_id and not current_user.is_super):
        abort(404)
    # The shared global library is every hospital's assistant — only a Super
    # Administrator may rewrite or remove it. A tenant's head office edits
    # their own hospital's voice, never the shared one (the same invariant
    # the keyword-learning path already enforces).
    if a.org_id is None and not current_user.is_super:
        abort(404)
    audit("KB_DELETED", "kb", kid, {"intent": a.intent})
    db.session.delete(a)
    db.session.commit()
    flash("Dialogue deleted.", "success")
    return redirect(url_for("admin.kb_list"))


# ================================================================ NDPA data-subject requests
@bp.get("/data-requests")
@require_role(*SUPER_MD)
def data_requests():
    from ..models import DataRequest
    items = (db.session.query(DataRequest)
             .filter_by(org_id=current_user.org_id)
             .order_by(DataRequest.status.desc(), DataRequest.created_at.desc())
             .limit(200).all())
    return render_template("admin/data_requests.html", items=items, now=now_naive())


def _records_for_phone(org_id: int, phone: str) -> dict:
    """Every record tied to a phone number, across all patient-facing tables."""
    from ..models import Appointment, PatientFeedback, QueueTicket
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    tail = digits[-9:] if len(digits) >= 9 else digits
    like = f"%{tail}%"
    return {
        "complaints": db.session.query(Complaint).filter(
            Complaint.org_id == org_id, Complaint.phone.like(like)).all(),
        "appointments": db.session.query(Appointment).filter(
            Appointment.org_id == org_id, Appointment.phone.like(like)).all(),
        "feedback": db.session.query(PatientFeedback).filter(
            PatientFeedback.org_id == org_id, PatientFeedback.phone.like(like)).all(),
        "queue": db.session.query(QueueTicket).filter(
            QueueTicket.org_id == org_id, QueueTicket.phone.like(like)).all(),
    }


@bp.get("/data-requests/<int:rid>")
@require_role(*SUPER_MD)
def data_request_detail(rid: int):
    from ..models import DataRequest
    req = db.session.get(DataRequest, rid)
    if not req or req.org_id != current_user.org_id:
        abort(404)
    found = _records_for_phone(req.org_id, req.phone)
    return render_template("admin/data_request_detail.html", req=req, found=found)


@bp.post("/data-requests/<int:rid>/fulfil")
@require_role(*SUPER_MD)
def data_request_fulfil(rid: int):
    """Action an access or erasure request and record exactly what was done."""
    from ..models import DataRequest
    req = db.session.get(DataRequest, rid)
    if not req or req.org_id != current_user.org_id:
        abort(404)
    if req.status != "NEW":
        flash("That request has already been handled.", "info")
        return redirect(url_for("admin.data_requests"))

    action = request.form.get("action")
    found = _records_for_phone(req.org_id, req.phone)
    counts = {k: len(v) for k, v in found.items()}

    if action == "erase":
        now = now_naive()
        for c in found["complaints"]:
            c.phone = "[erased]"
            c.description = "[erased at the patient's request]"
            c.attachment_path = None
            c.anonymized_at = now
        for a in found["appointments"]:
            a.patient_name, a.phone, a.anonymized_at = "[erased]", "[erased]", now
        for f in found["feedback"]:
            f.phone = None
            if f.comment:
                f.comment = "[erased at the patient's request]"
            f.anonymized_at = now
        for t in found["queue"]:
            t.patient_name, t.phone, t.anonymized_at = "[erased]", None, now
        req.outcome = f"Erased personal identifiers from {sum(counts.values())} record(s): {counts}"
    elif action == "access":
        req.outcome = (f"Copy of {sum(counts.values())} record(s) provided to the patient: "
                       f"{counts}")
    elif action == "reject":
        req.status = "REJECTED"
        req.outcome = (request.form.get("reason") or "Rejected — identity could not be verified.")[:1000]
    else:
        flash("We couldn't understand that action — it may be outdated. Please try again or ask for help.", "error")
        return redirect(url_for("admin.data_request_detail", rid=rid))

    if req.status != "REJECTED":
        req.status = "DONE"
    req.handled_at = now_naive()
    req.handled_by_id = current_user.id
    audit("DATA_REQUEST_HANDLED", "data_request", req.id,
          {"ref": req.ref, "action": action, "counts": counts})
    db.session.commit()
    flash(f"Request {req.ref} marked {req.status.lower()}.", "success")
    return redirect(url_for("admin.data_requests"))


# ================================================================ bulk staff upload
@bp.get("/users/import")
@require_role(*SUPER)
def users_import_form():
    depts = (db.session.query(Department)
             .filter_by(org_id=current_user.org_id, active=True)
             .order_by(Department.name).all())
    return render_template("admin/users_import.html", depts=depts,
                           role_choices=[(r, role_label(r)) for r in ROLES])


@bp.get("/users/import/template")
@require_role(*SUPER)
def users_import_template():
    """Download a starter spreadsheet matching the hospital's own paperwork."""
    from .. import bulkusers
    kind = request.args.get("kind", "nominal")
    csv_text = bulkusers.template_csv(kind)
    return Response(csv_text, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=staff-upload-{kind}.csv"})


@bp.post("/users/import")
@require_role(*SUPER)
def users_import_preview():
    from .. import bulkusers
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please choose a CSV or Excel (.xlsx) file.", "error")
        return redirect(url_for("admin.users_import_form"))

    raw, err = bulkusers.parse_file(file)
    if err:
        flash(err, "error")
        return redirect(url_for("admin.users_import_form"))
    if not raw:
        flash("No staff rows were found in that file.", "error")
        return redirect(url_for("admin.users_import_form"))

    default_dept = request.form.get("default_department_id", type=int)
    rows = bulkusers.build_preview(current_user.org_id, raw,
                                   default_department_id=default_dept)
    token = bulkusers.save_preview(current_user.org_id, rows)
    valid = sum(1 for r in rows if r["ok"])
    return render_template("admin/users_import_preview.html", rows=rows, token=token,
                           valid_count=valid, error_count=len(rows) - valid)


@bp.post("/users/import/confirm")
@require_role(*SUPER)
def users_import_confirm():
    from .. import bulkusers
    token = (request.form.get("token") or "").strip()
    rows = bulkusers.load_preview(current_user.org_id, token)
    if rows is None:
        flash("That import preview has expired. Please upload the file again.", "error")
        return redirect(url_for("admin.users_import_form"))
    try:
        result = bulkusers.commit_preview(current_user.org_id, rows,
                                          created_by_id=current_user.id)
        audit("USERS_BULK_IMPORTED", "user", None,
              {"created": result["created_count"], "skipped": result["skipped"]})
        db.session.commit()
    except Exception as exc:                             # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("bulk user import failed")
        flash(f"The import could not be completed: {exc}", "error")
        return redirect(url_for("admin.users_import_form"))

    bulkusers.discard_preview(current_user.org_id, token)
    flash(f"{result['created_count']} staff account(s) created. "
          f"{result['skipped']} row(s) skipped. Each account is awaiting your approval.",
          "success")
    return render_template("admin/users_import_done.html", result=result)


# ================================================================ security (Build 6)
@bp.get("/security")
@require_role(*SUPER)
def security_check():
    from .. import pentest
    sample = {}
    # Run the header checks against a real response from this app.
    try:
        with current_app.test_request_context("/login"):
            pass
        probe = current_app.test_client().get("/login")
        sample = dict(probe.headers)
    except Exception:                                         # noqa: BLE001
        current_app.logger.exception("security header probe failed")
    checks = pentest.run(current_app, current_user.org_id, sample_headers=sample)
    tally = pentest.summary(checks)
    required = services.get_setting(current_user.org_id, "mfa_required_roles") or []
    staff = (db.session.query(User)
             .filter_by(org_id=current_user.org_id, active=True)
             .order_by(User.role, User.name).all())
    return render_template("admin/security.html", checks=checks, tally=tally,
                           required=set(required), roles=ROLES,
                           role_choices=[(r, role_label(r)) for r in ROLES],
                           staff=staff)


@bp.post("/security/policy")
@require_role(*SUPER)
def security_policy():
    picked = [r for r in request.form.getlist("mfa_required_roles") if r in ROLES]
    services.set_setting(current_user.org_id, "mfa_required_roles", picked)
    audit("MFA_POLICY_UPDATED", "settings", current_user.org_id, {"roles": picked})
    db.session.commit()
    flash("Phone-code rule saved. People in those jobs must set it up at next sign-in.",
          "success")
    return redirect(url_for("admin.security_check"))


# ================================================================ branches (Build 6)
@bp.get("/branches")
@require_role(*SUPER)
def branches():
    from .. import branches as br
    br.ensure_main_branch(current_user.org_id)
    db.session.commit()
    items = (db.session.query(Branch)
             .filter_by(org_id=current_user.org_id)
             .order_by(Branch.is_main.desc(), Branch.name).all())
    counts = {}
    for b in items:
        counts[b.id] = db.session.query(User).filter_by(org_id=current_user.org_id,
                                                        branch_id=b.id).count()
    return render_template("admin/branches.html", items=items, counts=counts)


@bp.post("/branches")
@require_role(*SUPER)
def branch_save():
    from .. import branches as br
    bid = request.form.get("branch_id", type=int)
    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    if not name:
        flash("Give the site a name people will recognise (e.g. Main, Annex).", "error")
        return redirect(url_for("admin.branches"))
    if not code or not code.replace("-", "").isalnum() or len(code) > 16:
        flash("Site code must be short letters or numbers (e.g. MAIN, ANNEX).", "error")
        return redirect(url_for("admin.branches"))
    if bid:
        b = br.get_in_org(bid, current_user.org_id)
        if not b:
            abort(404)
        clash = (db.session.query(Branch)
                 .filter(Branch.org_id == current_user.org_id,
                         Branch.code == code, Branch.id != b.id).first())
        if clash:
            flash("Another site already uses that code.", "error")
            return redirect(url_for("admin.branches"))
        b.name = name
        b.code = code
        b.address = (request.form.get("address") or "").strip() or None
        b.phone = (request.form.get("phone") or "").strip() or None
        b.email = (request.form.get("email") or "").strip() or None
        from .. import attendance as att
        b.lat = att.parse_coord(request.form.get("lat"), kind="lat")
        b.lng = att.parse_coord(request.form.get("lng"), kind="lng")
        raw_r = (request.form.get("fence_meters") or "").strip()
        b.fence_meters = att.parse_radius(raw_r) if raw_r else None
        audit("BRANCH_UPDATED", "branch", b.id, {"name": name, "code": code,
                                                "lat": b.lat, "lng": b.lng})
    else:
        clash = (db.session.query(Branch)
                 .filter_by(org_id=current_user.org_id, code=code).first())
        if clash:
            flash("Another site already uses that code.", "error")
            return redirect(url_for("admin.branches"))
        from .. import attendance as att
        b = Branch(org_id=current_user.org_id, code=code, name=name,
                   address=(request.form.get("address") or "").strip() or None,
                   phone=(request.form.get("phone") or "").strip() or None,
                   email=(request.form.get("email") or "").strip() or None,
                   lat=att.parse_coord(request.form.get("lat"), kind="lat"),
                   lng=att.parse_coord(request.form.get("lng"), kind="lng"),
                   fence_meters=(att.parse_radius(request.form.get("fence_meters"))
                                 if (request.form.get("fence_meters") or "").strip() else None),
                   is_main=False, active=True)
        db.session.add(b)
        db.session.flush()
        audit("BRANCH_CREATED", "branch", b.id, {"name": name, "code": code})
    db.session.commit()
    flash("Site saved.", "success")
    return redirect(url_for("admin.branches"))


@bp.post("/branches/<int:bid>/main")
@require_role(*SUPER)
def branch_make_main(bid: int):
    from .. import branches as br
    b = br.get_in_org(bid, current_user.org_id)
    if not b:
        abort(404)
    for other in db.session.query(Branch).filter_by(org_id=current_user.org_id).all():
        other.is_main = (other.id == b.id)
    audit("BRANCH_SET_MAIN", "branch", b.id, {"name": b.name})
    db.session.commit()
    flash(f"{b.name} is now the main site.", "success")
    return redirect(url_for("admin.branches"))


@bp.post("/branches/<int:bid>/toggle")
@require_role(*SUPER)
def branch_toggle(bid: int):
    from .. import branches as br
    b = br.get_in_org(bid, current_user.org_id)
    if not b:
        abort(404)
    if b.is_main and b.active:
        flash("The main site cannot be switched off. Make another site main first.",
              "error")
        return redirect(url_for("admin.branches"))
    b.active = not b.active
    audit("BRANCH_TOGGLED", "branch", b.id, {"active": b.active, "name": b.name})
    db.session.commit()
    flash(f"{b.name} {'is open again' if b.active else 'is hidden from new work'}.",
          "success")
    return redirect(url_for("admin.branches"))

