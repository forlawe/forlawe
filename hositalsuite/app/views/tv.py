"""TV display — public monitors showing live queue + doctor calls with Nigerian voices."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user

from ..models import TvScreen, db
from .. import tv as tv_engine
from ..security import csrf_exempt, rate_limit, require_role

bp = Blueprint("tv", __name__)

SUPER = ("SUPER_ADMIN",)


def _resolve_org():
    """Org for public TV: from screen code or from logged-in user or host mapping.
    
    Multi-hospital fix: NO fallback to first org (security loophole closed).
    Returns None if org cannot be resolved — caller must 503, not leak other hospital data.
    Feature phone / USSD / voice provision: TV is per-org, never cross-org.
    """
    from ..services import current_org
    from flask_login import current_user

    # If logged in, use user's org — admin viewing TV config
    try:
        if current_user and current_user.is_authenticated:
            return current_user.org_id
    except Exception:
        pass
    # Public portal: resolve via host/domain mapping (multi-tenant)
    try:
        org = current_org()
        if org:
            return org.id
    except Exception:
        pass
    # No fallback to first org — security loophole closed for multi-hospital isolation
    # Caller should 503 if no org resolved, not show first org's data
    return None


@bp.get("/tv")
def main_tv():
    """Waiting Area Main TV — shows MORE (founder req). Public, no login, per-tenant via org."""
    org_id = _resolve_org()
    if not org_id:
        abort(503)
    tv_engine.ensure_default_screens(org_id)
    screen = db.session.query(TvScreen).filter_by(org_id=org_id, code="MAIN", active=True).first()
    if not screen:
        screen = db.session.query(TvScreen).filter_by(org_id=org_id, active=True).first()
    feed = tv_engine.tv_feed(org_id, screen)
    rotation = tv_engine.voice_rotation_for_today(org_id, screen.id if screen else None)
    # Friendly attractive design: we pass everything
    return render_template("tv/main.html", feed=feed, screen=screen, rotation=rotation, is_main=True)


@bp.get("/tv/<code>")
def screen_by_code(code: str):
    """Any TV by code: /tv/DENTAL, /tv/OPD, /tv/PHARMACY — public, per-tenant."""
    code = (code or "").strip().upper()[:20]
    org_id = _resolve_org()
    if not org_id:
        abort(503)
    tv_engine.ensure_default_screens(org_id)
    screen = db.session.query(TvScreen).filter_by(org_id=org_id, code=code, active=True).first()
    if not screen:
        abort(404)
    feed = tv_engine.tv_feed(org_id, screen)
    rotation = tv_engine.voice_rotation_for_today(org_id, screen.id)
    # Main waiting area shows more, clinic TV shows filtered
    is_main = screen.screen_type == "WAITING_MAIN"
    template = "tv/main.html" if is_main else "tv/clinic.html"
    return render_template(template, feed=feed, screen=screen, rotation=rotation, is_main=is_main)


@csrf_exempt("tv.api_volume")
@bp.post("/api/tv/volume")
@rate_limit(limit=60, window=60.0)
def api_volume():
    """Save volume per TV — public, per-tenant, best effort. No auth needed for TV remote, but scoped to org. Hardened."""
    org_id = _resolve_org()
    if not org_id:
        return jsonify({"error": "no org"}), 503
    try:
        code = (request.args.get("code") or request.form.get("code") or "").strip().upper()[:20]
        vol = request.args.get("volume", type=int)
        if vol is None:
            vol = request.form.get("volume", type=int)
        bright = request.args.get("brightness", type=int)
        if bright is None:
            bright = request.form.get("brightness", type=int)
        if not code:
            return jsonify({"ok": False, "error": "code required"}), 400
        screen = db.session.query(TvScreen).filter_by(org_id=org_id, code=code).first()
        if not screen:
            return jsonify({"ok": False, "error": "not found"}), 404
        if vol is not None:
            try:
                vol = max(0, min(100, int(vol)))
                screen.voice_volume = vol
            except Exception:
                pass
        if bright is not None:
            try:
                bright = max(10, min(100, int(bright)))
                screen.brightness = bright
            except Exception:
                pass
        db.session.commit()
        return jsonify({"ok": True, "code": code, "volume": getattr(screen, 'voice_volume', 100), "brightness": getattr(screen, 'brightness', 100)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "server error"}), 500


@csrf_exempt("tv.api_brightness")
@bp.post("/api/tv/brightness")
@rate_limit(limit=60, window=60.0)
def api_brightness():
    """Save brightness + night mode per TV — public, per-tenant. Hardened."""
    org_id = _resolve_org()
    if not org_id:
        return jsonify({"error": "no org"}), 503
    try:
        code = (request.args.get("code") or request.form.get("code") or "").strip().upper()[:20]
        bright = request.args.get("brightness", type=int)
        if bright is None:
            bright = request.form.get("brightness", type=int)
        night = request.args.get("night_mode")
        if night is None:
            night = request.form.get("night_mode")
        if not code:
            return jsonify({"ok": False, "error": "code required"}), 400
        screen = db.session.query(TvScreen).filter_by(org_id=org_id, code=code).first()
        if not screen:
            return jsonify({"ok": False, "error": "not found"}), 404
        if bright is not None:
            try:
                screen.brightness = max(10, min(100, int(bright)))
            except Exception:
                pass
        if night is not None:
            try:
                if isinstance(night, str):
                    night = night.lower() in ("1", "true", "on", "yes")
                screen.night_mode = bool(night)
            except Exception:
                pass
        db.session.commit()
        return jsonify({"ok": True, "code": code, "brightness": getattr(screen, 'brightness', 100), "night_mode": bool(getattr(screen, 'night_mode', False))})
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "server error"}), 500


@csrf_exempt("tv.api_feed")
@bp.get("/api/tv/feed")
@rate_limit(limit=60, window=60.0)   # F-028: screens poll every 5-30s; this only throttles scrapers
def api_feed():
    """JSON feed for TV auto-refresh — public, per-tenant. Hardened, never crashes TV."""
    org_id = _resolve_org()
    if not org_id:
        return jsonify({"error": "no org"}), 503
    try:
        code = (request.args.get("code") or "MAIN").strip().upper()[:20]
        screen = db.session.query(TvScreen).filter_by(org_id=org_id, code=code, active=True).first()
        if not screen:
            screen = db.session.query(TvScreen).filter_by(org_id=org_id, code="MAIN", active=True).first()
        try:
            feed = tv_engine.tv_feed(org_id, screen)
        except Exception:
            # Never crash TV feed — return minimal safe payload
            feed = {"now_serving": [], "next_up": [], "stats": {}, "clinic_counts": {}, "now": __import__("datetime").datetime.utcnow()}
        try:
            rotation = tv_engine.voice_rotation_for_today(org_id, screen.id if screen else None)
        except Exception:
            rotation = {"slot": 0, "slot_name": "Female Voice 1", "languages": ["en-NG", "en"]}

        return jsonify(
            {
                "screen": {
                    "code": getattr(screen, 'code', 'MAIN') if screen else 'MAIN',
                    "name": getattr(screen, 'name', 'Main TV') if screen else 'Main TV',
                    "type": getattr(screen, 'screen_type', 'WAITING_MAIN') if screen else 'WAITING_MAIN',
                    "clinic": getattr(screen, 'clinic_code', None) if screen else None,
                    "voice_languages": getattr(screen, 'voice_languages', 'en,yo,ha,ig') if screen else 'en,yo,ha,ig',
                    "brightness": getattr(screen, 'brightness', 100) if screen else 100,
                    "night_mode": bool(getattr(screen, 'night_mode', False)) if screen else False,
                } if screen else None,
                "now_serving": feed.get("now_serving", []) if isinstance(feed, dict) else [],
                "next_up": feed.get("next_up", []) if isinstance(feed, dict) else [],
                "stats": feed.get("stats", {}) if isinstance(feed, dict) else {},
                "clinic_counts": feed.get("clinic_counts", {}) if isinstance(feed, dict) else {},
                "rotation": rotation,
                "timestamp": feed.get("now").isoformat() if isinstance(feed, dict) and hasattr(feed.get("now"), 'isoformat') else __import__("datetime").datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        # Absolute fallback — TV must never show 500
        return jsonify({"error": "feed error", "now_serving": [], "next_up": [], "stats": {}, "clinic_counts": {}, "screen": None}), 200


# ------------------------------------------------------------------ admin CRUD for TV screens
@bp.get("/admin/tv")
@require_role(*SUPER)
def admin_list():
    org_id = current_user.org_id
    tv_engine.ensure_default_screens(org_id)
    screens = db.session.query(TvScreen).filter_by(org_id=org_id).order_by(TvScreen.code).all()
    from ..models import Department, ServiceClinic

    depts = db.session.query(Department).filter_by(org_id=org_id, active=True).order_by(Department.name).all()
    clinics = db.session.query(ServiceClinic).filter_by(org_id=org_id, active=True).order_by(ServiceClinic.name).all()
    return render_template("admin/tv.html", screens=screens, depts=depts, clinics=clinics)


@bp.post("/admin/tv/create")
@require_role(*SUPER)
def admin_create():
    from flask import flash, redirect, url_for

    code = (request.form.get("code") or "").strip().upper()[:20]
    name = (request.form.get("name") or "").strip()[:120]
    location = (request.form.get("location") or "").strip()[:120]
    screen_type = request.form.get("screen_type") or "WAITING_MAIN"
    clinic_code = (request.form.get("clinic_code") or "").strip().upper()[:20] or None
    dept_id = request.form.get("department_id", type=int)

    if not code or not name:
        flash("Code and name required for TV screen.", "error")
        return redirect(url_for("tv.admin_list"))

    existing = db.session.query(TvScreen).filter_by(org_id=current_user.org_id, code=code).first()
    if existing:
        flash(f"TV code {code} already exists.", "error")
        return redirect(url_for("tv.admin_list"))

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
        voice_languages="en,yo,ha,ig",
        voice_volume=100,
        brightness=100,
        night_mode=False,
        show_fast_track_only=bool(request.form.get("show_fast_track_only") or request.form.get("is_executive")),
        is_executive=bool(request.form.get("is_executive")),
        active=True,
    )
    db.session.add(s)
    db.session.commit()
    flash(f"TV screen {name} ({code}) created. Open /tv/{code} on the TV.", "success")
    return redirect(url_for("tv.admin_list"))


@bp.post("/admin/tv/<int:sid>/edit")
@require_role(*SUPER)
def admin_edit(sid: int):
    from flask import flash, redirect, url_for

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
    s.voice_languages = (request.form.get("voice_languages") or "en,yo,ha,ig").strip()[:30]
    s.show_fast_track_only = bool(request.form.get("show_fast_track_only"))
    s.is_executive = bool(request.form.get("is_executive"))
    if s.is_executive and not s.show_fast_track_only:
        # Executive TV usually wants gold only, but allow admin to override — if executive checked, suggest fast only
        pass
    try:
        vol = int(request.form.get("voice_volume") or s.voice_volume or 100)
        s.voice_volume = max(0, min(100, vol))
    except ValueError:
        pass
    try:
        bright = int(request.form.get("brightness") or getattr(s, 'brightness', 100) or 100)
        s.brightness = max(10, min(100, bright))
    except ValueError:
        pass
    s.night_mode = bool(request.form.get("night_mode"))
    s.active = bool(request.form.get("active"))
    db.session.commit()
    flash(f"TV {s.name} updated.", "success")
    return redirect(url_for("tv.admin_list"))


@bp.post("/admin/tv/<int:sid>/toggle")
@require_role(*SUPER)
def admin_toggle(sid: int):
    from flask import flash, redirect, url_for

    s = db.session.get(TvScreen, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    s.active = not s.active
    db.session.commit()
    flash(f"TV {s.name} {'activated' if s.active else 'suspended'}.", "success")
    return redirect(url_for("tv.admin_list"))


@bp.post("/admin/tv/<int:sid>/delete")
@require_role(*SUPER)
def admin_delete(sid: int):
    from flask import flash, redirect, url_for

    s = db.session.get(TvScreen, sid)
    if not s or s.org_id != current_user.org_id:
        abort(404)
    if s.code == "MAIN":
        flash("Cannot delete MAIN waiting area TV — suspend instead.", "error")
        return redirect(url_for("tv.admin_list"))
    db.session.delete(s)
    db.session.commit()
    flash(f"TV {s.name} deleted.", "success")
    return redirect(url_for("tv.admin_list"))


# ------------------------------------------------------------------ QR poster
def _tv_base_url() -> str:
    # Prefer configured public base URL (Render, custom domain) — avoids Host
    # header spoofing and gives correct QR when behind proxy.
    try:
        from flask import current_app

        base = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if base:
            return base
    except Exception:
        pass
    try:
        return request.url_root.rstrip("/")
    except Exception:
        return ""


def _qr_data_uri(text: str, box_size: int = 10) -> str:
    try:
        import base64
        import io
        import qrcode
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


@bp.get("/admin/tv/posters")
@require_role(*SUPER)
def admin_posters():
    org_id = current_user.org_id
    tv_engine.ensure_default_screens(org_id)
    screens = db.session.query(TvScreen).filter_by(org_id=org_id).order_by(TvScreen.code).all()
    base = _tv_base_url()
    items = []
    for s in screens:
        url = f"{base}/tv/{s.code}" if base else f"/tv/{s.code}"
        items.append({"screen": s, "url": url, "qr": _qr_data_uri(url, box_size=8)})
    return render_template("admin/tv_posters.html", items=items, base_url=base)


@bp.get("/admin/tv/<code>/poster")
@require_role(*SUPER)
def admin_poster_one(code: str):
    code = (code or "").strip().upper()[:20]
    org_id = current_user.org_id
    s = db.session.query(TvScreen).filter_by(org_id=org_id, code=code).first()
    if not s:
        abort(404)
    base = _tv_base_url()
    url = f"{base}/tv/{s.code}" if base else f"/tv/{s.code}"
    qr = _qr_data_uri(url, box_size=12)
    rotation = tv_engine.voice_rotation_for_today(org_id, s.id)
    return render_template("admin/tv_poster_single.html", screen=s, url=url, qr=qr, rotation=rotation, base_url=base)


@csrf_exempt("tv.api_qr_url")
@bp.get("/api/tv/qr-url")
def api_qr_url():
    """Public QR for TV ↔ patient page linking — returns data URI, no auth, per-tenant safe. Hardened."""
    code = (request.args.get("code") or "MAIN").strip().upper()[:20]
    text = (request.args.get("text") or "").strip()[:500]
    if not text:
        base = _tv_base_url()
        if code and code.startswith("Q-"):
            # ticket code — keep base /welcome if no explicit text
            text = f"{base}/welcome" if base else "/welcome"
        else:
            # TV screen QR → patient portal
            text = f"{base}/welcome" if base else "/welcome"
            if base and code:
                # For TV itself, QR should point to /welcome (patient tracking entry)
                # not to TV screen (TV already shows itself). Patient page link.
                text = f"{base}/welcome"
    qr = _qr_data_uri(text, box_size=6)
    return jsonify({"ok": True, "qr": qr, "text": text, "code": code})


@bp.get("/admin/tv/qr/<code>.png")
@require_role(*SUPER)
def admin_qr_png(code: str):
    code = (code or "").strip().upper()[:20]
    org_id = current_user.org_id
    s = db.session.query(TvScreen).filter_by(org_id=org_id, code=code).first()
    if not s:
        abort(404)
    base = _tv_base_url()
    url = f"{base}/tv/{s.code}" if base else f"/tv/{s.code}"
    try:
        import io
        import qrcode
        from flask import send_file
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png", as_attachment=False, download_name=f"TV-{s.code}-QR.png")
    except Exception:
        abort(500)
