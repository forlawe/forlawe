"""Authentication views."""
from __future__ import annotations

import secrets
from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .. import accounts
from ..audit import audit
from ..models import (LoginAttempt, Organization, PasswordReset, User, db,
                      now_naive)
from ..security import (client_ip, password_strength_errors, rate_limit,
                        require_login, safe_next)

bp = Blueprint("auth", __name__)

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5

# pages reachable while a password change is pending
ALLOWED_WHEN_PENDING = ("auth.change_password", "auth.change_password_post",
                        "auth.logout", "static")


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("login.html", next=request.args.get("next", ""))


def _lock_row(username: str, org_id: int | None = None) -> LoginAttempt:
    """Lockout counter scoped to (hospital, username) — F-021. With no
    hospital context the row is keyed org_id=NULL, so an attacker hammering
    the bare server cannot lock anyone's account inside a real hospital."""
    row = (db.session.query(LoginAttempt)
           .filter_by(org_id=org_id, username=username).first())
    if row is None:
        row = LoginAttempt(org_id=org_id, username=username, failures=0)
        db.session.add(row)
        db.session.flush()
    return row


def _lockout_remaining(row: LoginAttempt) -> int:
    """Minutes left on an active lockout, else 0."""
    if row.locked_until and row.locked_until > now_naive():
        return max(1, int((row.locked_until - now_naive()).total_seconds() // 60) + 1)
    return 0


def _explicit_login_org() -> Organization | None:
    """The hospital this login request EXPLICITLY belongs to (F-021).

    ?h= code, a mapped subdomain, or a genuinely single-tenant server.
    Unlike _home_org()/current_org() it never falls back to "first org":
    on a multi-hospital server an unidentified request must not be silently
    routed to hospital #1 — an ambiguous username gets guidance instead.
    """
    try:
        hint = (request.args.get("h") or "").strip()
        if hint:
            org = (db.session.query(Organization)
                   .filter(db.or_(Organization.slug == hint.lower(),
                                  Organization.code == hint.upper())).first())
            if org is not None:
                return org
        host = (request.host or "").split(":")[0].lower()
        label = host.split(".")[0] if host.count(".") >= 2 else ""
        if label and label not in ("www", "localhost", "hospital-suite"):
            org = db.session.query(Organization).filter_by(slug=label).first()
            if org is not None:
                return org
    except Exception:                                    # noqa: BLE001
        pass
    try:
        if db.session.query(Organization).count() == 1:
            return db.session.query(Organization).order_by(Organization.id).first()
    except Exception:                                    # noqa: BLE001
        pass
    return None


@bp.post("/login")
@rate_limit(limit=8, window=60.0, key_extra="login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    nxt = request.form.get("next") or ""

    max_fail = current_app.config.get("LOGIN_MAX_FAILURES", 10)
    lock_mins = current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15)

    # Account-scoped brute-force gate. The per-IP limiter cannot help when every
    # request arrives from the same proxy, so failures are also counted per user.
    home_org = _explicit_login_org()
    org_id = home_org.id if home_org else None
    lock = _lock_row(username, org_id) if username else None
    if lock is not None:
        left = _lockout_remaining(lock)
        if left:
            audit("LOGIN_LOCKED_OUT", detail={"username": username})
            db.session.commit()
            flash(f"Too many failed attempts. Try again in {left} minute(s), "
                  "or use 'Forgot password'.", "error")
            return render_template("login.html", next=nxt, username=username), 429

    user = accounts.find_login_user(username, org_id=org_id)
    if user is None and accounts.find_login_user_ambiguous(username):
        db.session.commit()
        flash("This sign-in name is used in more than one hospital on this "
              "server. Please open your own hospital's page (your hospital's "
              "link or QR poster) and sign in there.", "error")
        return render_template("login.html", next=nxt, username=username), 400
    if not user or not user.check_password(password):
        if lock is not None:
            lock.failures = (lock.failures or 0) + 1
            lock.last_failure_at = now_naive()
            lock.last_ip = client_ip()
            if lock.failures >= max_fail:
                lock.locked_until = now_naive() + timedelta(minutes=lock_mins)
                lock.failures = 0
                audit("ACCOUNT_LOCKED", "user", user.id if user else None,
                      {"username": username, "minutes": lock_mins})
        audit("LOGIN_FAILED", detail={"username": username})
        db.session.commit()
        flash("Invalid username or password.", "error")
        return render_template("login.html", next=nxt, username=username), 401
    if lock is not None:
        lock.failures = 0
        lock.locked_until = None
    ok, reason = accounts.can_enter(user)
    if not ok:
        if reason == "VERIFY":
            session["pending_verify_uid"] = user.id
            session["pending_verify_next"] = nxt
            shown = _kick_activation(user)
            audit("LOGIN_EMAIL_UNVERIFIED", "user", user.id, {"username": user.username})
            db.session.commit()
            if session.get("activation_sent"):
                flash("Enter the 6-digit code we sent to your email to activate this account.",
                      "info")
            else:
                flash("We could not send the 6-digit code. Ask the System Admin to tap "
                      "Confirm email on Users, or set up the mail van on System Health.",
                      "error")
            if shown:
                flash(f"(Test code: {shown})", "info")
            return redirect(url_for("auth.verify_email"))
        if reason == "PROFILE":
            session["pending_register_uid"] = user.id
            audit("LOGIN_PROFILE_PENDING", "user", user.id, {"username": user.username})
            db.session.commit()
            flash("Fill in your staff card so the System Admin can give you access.", "info")
            return redirect(url_for("auth.staff_card"))
        audit("LOGIN_BLOCKED", "user", user.id, {"username": user.username, "why": reason})
        db.session.commit()
        flash(reason, "error")
        return render_template("login.html", next=nxt, username=username), 403
    from .mfa import mfa_is_enforced
    if getattr(user, "mfa_enabled", False) and mfa_is_enforced():
        session["pending_mfa_uid"] = user.id
        session["pending_mfa_next"] = nxt
        session.permanent = True
        audit("LOGIN_MFA_PENDING", "user", user.id, {"username": user.username})
        db.session.commit()
        return redirect(url_for("mfa.verify"))
    login_user(user, remember=False)
    session.permanent = True
    session.pop("pending_mfa_uid", None)
    user.last_login_at = now_naive()
    db.session.commit()
    audit("LOGIN", "user", user.id, {"username": user.username}, user=user, org_id=user.org_id)
    if user.must_change_password:
        flash("This is a temporary password. Please choose your own password now.", "info")
        return redirect(url_for("auth.change_password"))
    from .mfa import user_must_setup
    if user_must_setup(user):
        flash("Your job requires a phone code. Set it up now — it takes one minute.",
              "info")
        return redirect(url_for("mfa.setup"))
    target = safe_next(nxt, "")
    if target:
        return redirect(target)
    return redirect(url_for("main.dashboard"))


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        audit("LOGOUT", "user", current_user.id, user=current_user, org_id=current_user.org_id)
    session.pop("pending_mfa_uid", None)
    session.pop("pending_mfa_next", None)
    session.pop("pending_verify_uid", None)
    session.pop("pending_register_uid", None)
    session.pop("mfa_setup_secret", None)
    logout_user()
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------ forced password change
@bp.get("/change-password")
@require_login
def change_password():
    return render_template("change_password.html")


@bp.post("/change-password")
@require_login
def change_password_post():
    current_pw = request.form.get("current_password") or ""
    new_pw = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""
    if not current_user.check_password(current_pw):
        flash("Your current password is incorrect.", "error")
        return render_template("change_password.html"), 401
    if new_pw != confirm:
        flash("The new passwords do not match.", "error")
        return render_template("change_password.html"), 422
    errs = password_strength_errors(new_pw, username=current_user.username,
                                    email=current_user.email or "")
    if errs:
        for e in errs:
            flash(e, "error")
        return render_template("change_password.html"), 422
    if new_pw == current_pw:
        flash("The new password must be different from the old one.", "error")
        return render_template("change_password.html"), 422
    current_user.set_password(new_pw)
    current_user.must_change_password = False
    audit("PASSWORD_CHANGED", "user", current_user.id, {"self": True})
    db.session.commit()
    flash("Password updated successfully.", "success")
    from .mfa import user_must_setup
    if user_must_setup(current_user):
        return redirect(url_for("mfa.setup"))
    return redirect(url_for("main.dashboard"))


def enforce_pending_password_change():
    """Before-request guard: users with a temporary password can only reach
    the change-password page and logout."""
    if not current_user.is_authenticated:
        return None
    if not current_user.must_change_password:
        return None
    if request.endpoint in ALLOWED_WHEN_PENDING:
        return None
    return redirect(url_for("auth.change_password"))


# ================================================================ request access + activate email
def _home_org() -> Organization | None:
    """Home org for public pages — tries host-based current_org first, then first org only if single-tenant.
    Multi-hospital fix: no leak of first org when multiple orgs exist and host not mapped."""
    try:
        from ..services import current_org
        org = current_org()
        if org:
            return org
    except Exception:
        pass
    try:
        # Only fallback to first org if single org — avoids cross-hospital leak
        if db.session.query(Organization).count() <= 1:
            return db.session.query(Organization).order_by(Organization.id).first()
        return None
    except Exception:
        return None


def _org_from_signup_code(code: str | None) -> Organization | None:
    raw = (code or request.args.get("h") or "").strip().upper()
    if not raw:
        return None
    return db.session.query(Organization).filter_by(code=raw).first()


def _signup_org(org_code: str | None = None) -> Organization | None:
    """Which hospital this Sign up belongs to.

    A private link /signup/GHE is the real door. If this server only has
    ONE hospital, the bare /signup still works. If there are many, a
    stranger without a link is not dropped into the first hospital.
    """
    picked = _org_from_signup_code(org_code)
    if picked:
        return picked
    try:
        n = db.session.query(Organization).count()
    except Exception:
        n = 0
    if n <= 1:
        return _home_org()
    return None


def _kick_activation(user: User) -> str | None:
    """Send a code. Returns the digits only in TESTING so tests can read them.

    Never prints the digits on a live page. Sandbox used to flash the code
    to whoever signed up — that is a hole.
    """
    otp = accounts.issue_email_code(user)
    org = db.session.get(Organization, user.org_id)
    result = accounts.send_activation(user, otp, hospital_name=(org.name if org else "the hospital"))
    session["activation_sent"] = bool(result.get("ok"))
    session["activation_via"] = result.get("via") or ""
    session["activation_error"] = (result.get("error") or "")[:200]
    from flask import current_app
    if result.get("ok"):
        current_app.logger.info("activation sent to %s via %s", user.username, result.get("via"))
    else:
        current_app.logger.warning("activation NOT sent to %s: %s",
                                   user.username, result.get("error"))
    if current_app.config.get("TESTING"):
        return otp
    return None


@bp.get("/signup/<org_code>")
@bp.get("/signup")
@bp.get("/request-access")
def request_access(org_code: str | None = None):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    org = _signup_org(org_code)
    if org is None:
        return render_template("signup_pick.html"), 404
    return render_template("request_access.html", hospital=org, org_code=org.code)


@bp.post("/signup/<org_code>")
@bp.post("/signup")
@bp.post("/request-access")
@rate_limit(limit=5, window=300.0, key_extra="request-access")
def request_access_post(org_code: str | None = None):
    org = _signup_org(org_code)
    if org is None:
        flash("Ask your hospital for their own Sign up link.", "error")
        return redirect(url_for("auth.login"))
    name = (request.form.get("name") or "").strip()
    username = (request.form.get("username") or "").strip().lower()
    email = accounts.normalize_email(request.form.get("email") or "")
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""
    errors = []
    if len(name) < 3:
        errors.append("Type your full name.")
    errors.extend(accounts.username_errors(username))
    errors.extend(accounts.email_allowed_for_hospital(email, org.email))
    if password != confirm:
        errors.append("The two passwords do not match.")
    errors.extend(password_strength_errors(password, username=username, email=email))
    if db.session.query(User).filter_by(username=username).first():
        errors.append("That username is already used. Pick another.")
    if accounts.email_taken(org.id, email):
        errors.append("That email is already on an account. Sign in, or use Forgot password.")
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("request_access.html", hospital=org, org_code=org.code,
                               name=name, username=username, email=email), 422
    u = User(org_id=org.id, username=username, name=name[:120], role="STAFF",
             email=email, approved=False, email_verified=False,
             profile_completed=False, active=True, must_change_password=False)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    shown = _kick_activation(u)
    audit("ACCESS_REQUESTED", "user", u.id, {"username": username, "email": email})
    db.session.commit()
    session["pending_verify_uid"] = u.id
    if session.get("activation_sent"):
        flash("We sent a 6-digit code. Then fill your staff card. "
              "The System Admin must tap Approve before you can sign in.", "success")
    else:
        flash("Your account is saved, but the 6-digit code could not be sent. "
              "Ask the System Admin to tap Confirm email on Users, or tap Send a new code after mail is set up.",
              "error")
    if shown:
        flash(f"(Test code: {shown})", "info")
    return redirect(url_for("auth.verify_email"))


@bp.get("/verify-email")
def verify_email():
    uid = session.get("pending_verify_uid")
    user = db.session.get(User, uid) if uid else None
    if user is None:
        flash("Start again from Sign in or Sign up.", "error")
        return redirect(url_for("auth.login"))
    return render_template(
        "verify_email.html",
        email=user.email or "",
        sent=session.get("activation_sent"),
        via=session.get("activation_via") or "",
        send_error=session.get("activation_error") or "",
    )


@bp.post("/verify-email")
@rate_limit(limit=8, window=300.0, key_extra="verify-email")
def verify_email_post():
    uid = session.get("pending_verify_uid")
    user = db.session.get(User, uid) if uid else None
    if user is None:
        flash("Start again from Sign in.", "error")
        return redirect(url_for("auth.login"))
    err = accounts.check_email_code(user, request.form.get("code") or "")
    if err:
        db.session.commit()
        flash(err, "error")
        return render_template(
            "verify_email.html",
            email=user.email or "",
            sent=session.get("activation_sent"),
            via=session.get("activation_via") or "",
            send_error=session.get("activation_error") or "",
        ), 401
    audit("EMAIL_VERIFIED", "user", user.id, {"email": user.email})
    db.session.commit()
    session.pop("pending_verify_uid", None)
    if not getattr(user, "profile_completed", True):
        session["pending_register_uid"] = user.id
        flash("Email confirmed. Now fill in your staff card.", "success")
        return redirect(url_for("auth.staff_card"))
    if not user.approved:
        flash("Email confirmed. Wait for the System Admin to give you access.", "success")
        return redirect(url_for("auth.login"))
    flash("Email confirmed. Sign in with your password.", "success")
    return redirect(url_for("auth.login"))


@bp.post("/verify-email/resend")
@rate_limit(limit=3, window=300.0, key_extra="verify-resend")
def verify_email_resend():
    uid = session.get("pending_verify_uid")
    user = db.session.get(User, uid) if uid else None
    if user is None:
        return redirect(url_for("auth.login"))
    shown = _kick_activation(user)
    db.session.commit()
    if session.get("activation_sent"):
        flash("A new code is on the way.", "info")
    else:
        flash("The new code could not be sent. Ask the System Admin to tap Confirm email.",
              "error")
    if shown:
        flash(f"(Test code: {shown})", "info")
    return redirect(url_for("auth.verify_email"))


# ================================================================ staff card (after email is proved)
def _register_user():
    uid = session.get("pending_register_uid")
    return db.session.get(User, uid) if uid else None


def _dept_tree(org_id: int) -> list[dict]:
    from ..models import Department, Section, Unit
    depts = (db.session.query(Department)
             .filter_by(org_id=org_id, active=True)
             .order_by(Department.name).all())
    tree = []
    for d in depts:
        sections = []
        for s in (db.session.query(Section)
                  .filter_by(org_id=org_id, department_id=d.id)
                  .order_by(Section.name).all()):
            units = [{"id": u.id, "name": u.name} for u in
                     (db.session.query(Unit)
                      .filter_by(org_id=org_id, section_id=s.id)
                      .order_by(Unit.name).all())]
            sections.append({"id": s.id, "name": s.name, "units": units})
        tree.append({"id": d.id, "name": d.name, "sections": sections})
    return tree


@bp.get("/staff-card")
def staff_card():
    user = _register_user()
    if user is None:
        flash("Sign in first. After your email is activated we open this page.", "error")
        return redirect(url_for("auth.login"))
    if getattr(user, "profile_completed", False):
        flash("Your staff card is already with the System Admin.", "info")
        return redirect(url_for("auth.login"))
    from ..models import role_label
    roles = [(c, role_label(c)) for c in accounts.REQUESTABLE_ROLES]
    return render_template("staff_card.html", user=user, hospital=_home_org(),
                           tree=_dept_tree(user.org_id), roles=roles,
                           name=user.name or "", cadre=user.cadre or "",
                           special=user.special_duty or "",
                           department_id=user.department_id or "",
                           section_id=user.section_id or "",
                           unit_id=user.unit_id or "",
                           requested_role=user.requested_role or "STAFF")


@bp.post("/staff-card")
@rate_limit(limit=8, window=300.0, key_extra="staff-card")
def staff_card_post():
    user = _register_user()
    if user is None:
        flash("Sign in first.", "error")
        return redirect(url_for("auth.login"))
    if getattr(user, "profile_completed", False):
        return redirect(url_for("auth.login"))
    from ..models import Department, Section, Unit, role_label
    name = (request.form.get("name") or "").strip()
    dept_id = request.form.get("department_id", type=int)
    section_id = request.form.get("section_id", type=int)
    unit_id = request.form.get("unit_id", type=int)
    cadre = (request.form.get("cadre") or "").strip()[:80]
    role = (request.form.get("requested_role") or "STAFF").strip()
    special = (request.form.get("special_duty") or "").strip()[:200]
    errors = []
    if len(name) < 3:
        errors.append("Type your full name.")
    dept = db.session.get(Department, dept_id) if dept_id else None
    if not dept or dept.org_id != user.org_id:
        errors.append("Pick your department.")
        dept = None
    sec = db.session.get(Section, section_id) if section_id else None
    if sec and (sec.org_id != user.org_id or (dept and sec.department_id != dept.id)):
        errors.append("That section does not belong to the department you picked.")
        sec = None
    unt = db.session.get(Unit, unit_id) if unit_id else None
    if unt and (unt.org_id != user.org_id or (sec and unt.section_id != sec.id)):
        errors.append("That unit does not belong to the section you picked.")
        unt = None
    if role not in accounts.REQUESTABLE_ROLES:
        errors.append("Pick a job from the list. Super Admin cannot be requested.")
        role = "STAFF"
    if errors:
        for e in errors:
            flash(e, "error")
        roles = [(c, role_label(c)) for c in accounts.REQUESTABLE_ROLES]
        return render_template("staff_card.html", user=user, hospital=_home_org(),
                               tree=_dept_tree(user.org_id), roles=roles,
                               name=name, cadre=cadre, special=special,
                               department_id=dept_id or "",
                               section_id=section_id or "",
                               unit_id=unit_id or "",
                               requested_role=role), 422
    user.name = name[:120]
    user.department_id = dept.id if dept else None
    user.section_id = sec.id if sec else None
    user.unit_id = unt.id if unt else None
    user.cadre = cadre or None
    user.requested_role = role
    user.special_duty = special or None
    user.role = "STAFF"          # they ask; Admin grants
    user.profile_completed = True
    user.profile_completed_at = now_naive()
    audit("STAFF_CARD_SUBMITTED", "user", user.id,
          {"name": name, "dept": dept.name if dept else None, "role_asked": role,
           "cadre": cadre, "special": special})
    db.session.commit()
    session.pop("pending_register_uid", None)
    flash("Staff card sent. The System Admin must tap Approve before you can sign in.",
          "success")
    return redirect(url_for("auth.staff_card_done"))


@bp.get("/staff-card/done")
def staff_card_done():
    return render_template("staff_card_done.html", hospital=_home_org())


# ================================================================ self-service password reset
def _find_active_user(identifier: str):
    ident = (identifier or "").strip()
    if not ident:
        return None
    u = accounts.find_login_user(ident)
    if u and u.active:
        return u
    digits = ident.replace(" ", "").replace("-", "").replace("+", "")
    if len(digits) >= 9:
        return db.session.query(User).filter_by(active=True).filter(
            User.phone.like(f"%{digits[-9:]}%")).first()
    return None


@bp.get("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


@bp.post("/forgot-password")
@rate_limit(limit=5, window=300.0, key_extra="forgot")
def forgot_password_post():
    identifier = request.form.get("identifier") or ""
    user = _find_active_user(identifier)
    # Same sentence whether the account exists or not.
    flash("If we can reach that account, a 6-digit code is on the way. "
          f"It expires in {OTP_TTL_MINUTES} minutes.", "info")
    if user is None:
        return redirect(url_for("auth.forgot_password"))

    otp = f"{secrets.randbelow(1000000):06d}"
    db.session.query(PasswordReset).filter_by(user_id=user.id, used_at=None).update(
        {"used_at": now_naive()})

    from .. import mailer, sms_pack
    org = db.session.get(Organization, user.org_id) if user.org_id else None
    body = sms_pack.signin_code(org, otp, OTP_TTL_MINUTES)
    channel = "none"
    # Real mail van first. Sandbox SMS is not a letter — it used to mark
    # "delivered" and never try email, so Forgot password stayed silent.
    if user.email and mailer.is_configured():
        ok, _detail = mailer.send_mail(user.email, "Your hospital sign-in code", body)
        if ok:
            channel = "email"
    sms_mode = (current_app.config.get("SMS_MODE") or "sandbox").lower()
    if channel == "none" and user.phone and sms_mode not in ("sandbox", "disabled", "off", ""):
        from .. import sms as sms_engine
        from ..tasks import dispatch_delivery
        sms_engine.queue_sms(user.org_id, user.phone, body, kind="alert",
                             entity_type="password_reset", entity_id=user.id)
        dispatch_delivery()
        channel = "sms"
    db.session.add(PasswordReset(user_id=user.id, otp_hash=generate_password_hash(otp),
                                 channel=channel if channel != "none" else "email",
                                 expires_at=now_naive() + timedelta(minutes=OTP_TTL_MINUTES)))
    if current_app.config.get("TESTING") and channel == "none":
        current_app.logger.info("password-reset code not sent (no live van)")
    audit("PASSWORD_RESET_REQUESTED", "user", user.id, {"channel": channel})
    db.session.commit()
    return redirect(url_for("auth.reset_password"))


@bp.get("/reset-password")
def reset_password():
    return render_template("reset_password.html")


@bp.post("/reset-password")
@rate_limit(limit=8, window=300.0, key_extra="reset")
def reset_password_post():
    identifier = request.form.get("identifier") or ""
    otp = (request.form.get("otp") or "").strip()
    new_pw = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    user = _find_active_user(identifier)
    row = None
    if user:
        row = (db.session.query(PasswordReset)
               .filter_by(user_id=user.id, used_at=None)
               .order_by(PasswordReset.id.desc()).first())

    def fail(msg):
        flash(msg, "error")
        return render_template("reset_password.html"), 401

    if not user or not row:
        return fail("Invalid request. Start again from 'Forgot password'.")
    if row.expires_at < now_naive():
        return fail("That code has expired. Request a new one.")
    if row.attempts >= OTP_MAX_ATTEMPTS:
        return fail("Too many attempts. Request a new code.")
    row.attempts += 1
    if not check_password_hash(row.otp_hash, otp):
        db.session.commit()
        return fail("Incorrect code. Check the 6 digits and try again.")

    if new_pw != confirm:
        db.session.commit()
        return fail("The new passwords do not match.")
    errs = password_strength_errors(new_pw, username=user.username if user else "",
                                    email=(user.email or "") if user else "")
    if errs:
        db.session.commit()
        for e in errs:
            flash(e, "error")
        return render_template("reset_password.html"), 422

    row.used_at = now_naive()
    user.set_password(new_pw)
    user.must_change_password = False
    audit("PASSWORD_RESET_COMPLETED", "user", user.id, {"self_service": True})
    db.session.commit()
    flash("Password updated. Sign in with your new password.", "success")
    return redirect(url_for("auth.login"))
