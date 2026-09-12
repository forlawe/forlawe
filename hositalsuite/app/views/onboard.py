"""Public walk that opens a new hospital. Phone-first. No jargon."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_user
from sqlalchemy.exc import IntegrityError

from .. import onboard as engine
from .. import services
from ..audit import audit
from ..models import Organization, db
from ..security import rate_limit, require_role

bp = Blueprint("onboard", __name__)


@bp.get("/start")
def start():
    form = {
        "name": "",
        "code": "",
        "phone": "",
        "email": "",
        "address": "",
        "admin_name": "",
        "username": "",
        "admin_phone": "",
        "brand_primary": "#0E5A8A",
        "brand_accent": "#12B5A5",
        "brand_gold": "#FFD700",
        "main_name": "Main",
        "annex_name": "",
        "install_departments": "1",
        "voice_lang": "en",
        "invite": (request.args.get("code") or "").strip(),
    }
    from .. import i18n
    return render_template(
        "onboard/wizard.html",
        form=form,
        errors=[],
        need_invite=engine.needs_invite(),
        hospital_count=engine.hospital_count(),
        langs=i18n.LANGS,
        already_admin=(current_user.is_authenticated
                       and getattr(current_user, "role", "") == "SUPER_ADMIN"),
    )


@bp.post("/start")
@rate_limit(limit=6, window=3600.0, key_extra="onboard")
def start_save():
    values, errors = engine.validate(request.form)
    if errors:
        from .. import i18n
        form = request.form.to_dict()
        form["install_departments"] = "1" if request.form.get("install_departments") else ""
        return render_template(
            "onboard/wizard.html",
            form=form,
            errors=errors,
            need_invite=engine.needs_invite(),
            hospital_count=engine.hospital_count(),
            langs=i18n.LANGS,
            already_admin=(current_user.is_authenticated
                           and getattr(current_user, "role", "") == "SUPER_ADMIN"),
        ), 422
    try:
        org, admin = engine.create_hospital(
            values,
            actor=current_user if current_user.is_authenticated else None,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("onboard.start"))
    except IntegrityError:
        db.session.rollback()
        flash("That hospital code or sign-in name was just taken. Try again.",
              "error")
        return redirect(url_for("onboard.start"))
    except Exception:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception("hospital onboarding failed")
        flash("We could not finish the setup. Please try again in a moment.",
              "error")
        return redirect(url_for("onboard.start"))

    login_user(admin, remember=False)
    flash(f"{org.name} is ready. You are signed in as {admin.username}.",
          "success")
    return redirect(url_for("onboard.done"))


@bp.get("/start/done")
def done():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    org = db.session.get(Organization, current_user.org_id)
    return render_template("onboard/done.html", org=org)


@bp.post("/start/guide-done")
def guide_done():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    services.set_setting(current_user.org_id, "onboard_guide", False)
    db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.post("/admin/onboard-invite")
@require_role("SUPER_ADMIN")
def invite():
    code = engine.mint_invite(current_user.org_id)
    audit("ONBOARD_INVITE_MINTED", "organization", current_user.org_id,
          {"hours": engine.INVITE_HOURS})
    db.session.commit()
    flash(f"Setup code for a new hospital: {code}. It works once and expires "
          f"in {engine.INVITE_HOURS} hours. Send it only to the person who "
          f"will run that hospital. They open /start and type the code.",
          "success")
    return redirect(url_for("admin.security_check"))
