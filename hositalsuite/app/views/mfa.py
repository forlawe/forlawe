"""Two-step sign-in: phone code after the password."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_user, logout_user

from .. import mfa as engine
from .. import services
from ..audit import audit
from ..models import User, db, now_naive
from ..security import rate_limit, require_login, safe_next

bp = Blueprint("mfa", __name__)

SETUP_ALLOWED = ("mfa.setup", "mfa.setup_post", "mfa.backup_once",
                 "auth.logout", "static")
VERIFY_ALLOWED = ("mfa.verify", "mfa.verify_post", "auth.logout",
                  "auth.login", "auth.login_post", "static")


def _required_roles(org_id: int) -> list:
    raw = services.get_setting(org_id, "mfa_required_roles") or []
    if isinstance(raw, str):
        return [r.strip() for r in raw.split(",") if r.strip()]
    return list(raw)


def mfa_is_enforced() -> bool:
    """Phone-code lock. Off until the hospital is ready to use it.

    The founder was trapped on the setup screen and could not reach the
    hospital. Keep the feature, but do not block sign-in unless MFA_ENFORCED=1.
    """
    import os
    return os.environ.get("MFA_ENFORCED", "0") == "1"


def user_must_setup(user) -> bool:
    if not mfa_is_enforced():
        return False
    if not user or getattr(user, "mfa_enabled", False):
        return False
    return engine.role_must_use_mfa(user.role, _required_roles(user.org_id))


def enforce_mfa():
    """Before-request: pending verify (not yet signed in) or forced setup."""
    if not mfa_is_enforced():
        session.pop("pending_mfa_uid", None)
        session.pop("mfa_force_setup", None)
        return None
    pending = session.get("pending_mfa_uid")
    if pending and not current_user.is_authenticated:
        if request.endpoint in VERIFY_ALLOWED:
            return None
        return redirect(url_for("mfa.verify"))

    if not current_user.is_authenticated:
        return None
    if current_user.must_change_password:
        return None
    if user_must_setup(current_user) or session.get("mfa_force_setup"):
        if request.endpoint in SETUP_ALLOWED:
            return None
        return redirect(url_for("mfa.setup"))
    return None


def _finish_login(user, nxt: str = ""):
    login_user(user, remember=False)
    session.permanent = True
    session.pop("pending_mfa_uid", None)
    session.pop("pending_mfa_next", None)
    user.last_login_at = now_naive()
    db.session.commit()
    audit("LOGIN", "user", user.id, {"username": user.username, "mfa": True},
          user=user, org_id=user.org_id)
    if user.must_change_password:
        flash("This is a temporary password. Please choose your own password now.",
              "info")
        return redirect(url_for("auth.change_password"))
    if user_must_setup(user):
        flash("Your job requires a phone code. Set it up now — it takes one minute.",
              "info")
        return redirect(url_for("mfa.setup"))
    target = safe_next(nxt, "")
    if target:
        return redirect(target)
    return redirect(url_for("main.dashboard"))


@bp.get("/mfa/verify")
def verify():
    uid = session.get("pending_mfa_uid")
    if not uid:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, uid)
    if not user or not user.mfa_enabled:
        session.pop("pending_mfa_uid", None)
        return redirect(url_for("auth.login"))
    return render_template("mfa_verify.html", name=user.name.split()[0])


@bp.post("/mfa/verify")
@rate_limit(limit=8, window=60.0, key_extra="mfa")
def verify_post():
    uid = session.get("pending_mfa_uid")
    if not uid:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, uid)
    if not user or not user.mfa_enabled:
        session.pop("pending_mfa_uid", None)
        return redirect(url_for("auth.login"))
    code = (request.form.get("code") or "").strip()
    nxt = session.get("pending_mfa_next") or ""
    if engine.verify_totp(user.mfa_secret or "", code):
        return _finish_login(user, nxt)
    ok, remaining = engine.consume_backup_code(user.mfa_backup, code)
    if ok:
        user.mfa_backup = remaining
        left = 0
        try:
            import json
            left = len(json.loads(remaining or "[]"))
        except Exception:
            pass
        audit("MFA_BACKUP_USED", "user", user.id, {"left": left},
              user=user, org_id=user.org_id)
        db.session.commit()
        flash(f"Signed in with a backup code. {left} spare code(s) left. "
              "Make new ones after you sign in if this was your last.", "info")
        return _finish_login(user, nxt)
    audit("MFA_FAILED", "user", user.id, {"username": user.username})
    db.session.commit()
    flash("That code is not right. Try the 6 digits on your phone, or a spare code.",
          "error")
    return render_template("mfa_verify.html", name=user.name.split()[0]), 401


@bp.get("/mfa/setup")
@require_login
def setup():
    secret = session.get("mfa_setup_secret")
    if not secret:
        secret = engine.new_secret()
        session["mfa_setup_secret"] = secret
    uri = engine.otpauth_uri(secret, current_user.username)
    qr = engine.qr_data_uri(uri)
    forced = user_must_setup(current_user)
    return render_template("mfa_setup.html", qr=qr, secret=secret, uri=uri,
                           forced=forced, enabled=bool(current_user.mfa_enabled))


@bp.post("/mfa/setup")
@require_login
@rate_limit(limit=8, window=60.0, key_extra="mfa-setup")
def setup_post():
    secret = session.get("mfa_setup_secret") or ""
    code = (request.form.get("code") or "").strip()
    if not secret or not engine.verify_totp(secret, code):
        flash("The 6-digit code did not match. Open the app and try the newest number.",
              "error")
        return redirect(url_for("mfa.setup"))
    codes = engine.new_backup_codes()
    current_user.mfa_secret = secret
    current_user.mfa_enabled = True
    current_user.mfa_backup = engine.hash_backup_codes(codes)
    current_user.mfa_confirmed_at = now_naive()
    session.pop("mfa_setup_secret", None)
    session.pop("mfa_force_setup", None)
    audit("MFA_ENABLED", "user", current_user.id, {"username": current_user.username})
    db.session.commit()
    session["mfa_backup_once"] = codes
    flash("Phone code is on. Save the spare codes on the next screen — we will "
          "not show them again.", "success")
    return redirect(url_for("mfa.backup_once"))


@bp.get("/mfa/backup-codes")
@require_login
def backup_once():
    codes = session.pop("mfa_backup_once", None)
    if not codes:
        flash("Spare codes are only shown once, just after you turn the phone "
              "code on. Turn it off and on again to make a new set.", "info")
        return redirect(url_for("mfa.setup"))
    return render_template("mfa_backup.html", codes=codes)


@bp.post("/mfa/disable")
@require_login
def disable():
    pw = request.form.get("password") or ""
    code = (request.form.get("code") or "").strip()
    if not current_user.check_password(pw):
        flash("Your password is not right.", "error")
        return redirect(url_for("mfa.setup"))
    if current_user.mfa_enabled and not engine.verify_totp(current_user.mfa_secret or "", code):
        ok, remaining = engine.consume_backup_code(current_user.mfa_backup, code)
        if not ok:
            flash("Enter the 6-digit phone code (or a spare code) to turn this off.",
                  "error")
            return redirect(url_for("mfa.setup"))
        current_user.mfa_backup = remaining
    if user_must_setup(current_user):
        flash("Your job requires a phone code. You cannot turn it off.", "error")
        return redirect(url_for("mfa.setup"))
    current_user.mfa_secret = None
    current_user.mfa_enabled = False
    current_user.mfa_backup = None
    current_user.mfa_confirmed_at = None
    audit("MFA_DISABLED", "user", current_user.id, {"username": current_user.username})
    db.session.commit()
    flash("Phone code turned off. You will sign in with only your password.", "success")
    return redirect(url_for("mfa.setup"))
