"""
Personal Patient TV — /t/<access_key> — premium tracker, no login, cost saver
-------------------------------------------------------------------------
No SMS for patients inside hospital except serious complaints/emergency.
So personal TV replaces SMS.

Multi-hospital: per org_id via session.org_id
Slow internet: server-rendered first paint, then JS poll every 10s, payload <1KB
Loading time: minimal CSS/JS, inline critical, lazy rest
Browser: Chrome, Firefox, Safari, Edge, Samsung, UC, Opera + feature phone fallback
Feature phone: if no JS, meta refresh every 30s, no push, uses TV + voice
"""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request
from ..models import db, now_naive
from .. import personal_tv as ptv_engine
from ..security import rate_limit

bp = Blueprint("personal_tv", __name__)

def _resolve_org_from_session(session):
    return session.org_id if session else None

@bp.get("/t/<access_key>")
@rate_limit(limit=120, window=60.0)
def personal_tv_page(access_key: str):
    """Public personal TV page — no login, secret access_key, premium UX."""
    access_key = (access_key or "").strip()[:24]
    session = ptv_engine.get_session_by_access_key(access_key)
    if not session:
        abort(404)

    # Update last seen for presence detection — smart routing knows user online
    try:
        session.last_seen_at = now_naive()
        # Also update UserPresence for smart SMS routing
        from ..models_v2 import UserPresence
        presence = db.session.query(UserPresence).filter_by(org_id=session.org_id, patient_access_key=access_key).first()
        if not presence:
            presence = UserPresence(org_id=session.org_id, patient_access_key=access_key, last_seen_at=now_naive(), is_inside_hospital=True)
            db.session.add(presence)
        else:
            presence.last_seen_at = now_naive()
        db.session.commit()
    except Exception:
        db.session.rollback()

    feed = ptv_engine.build_personal_feed(session.org_id, session)

    # QR data URI for keeping page — no install needed, works on any browser, premium
    # Multi-browser: Chrome, Firefox, Safari, Edge, Samsung, UC, Opera
    qr_data_uri = ""
    try:
        from ..qrgen import make_qr_data_uri
        # Build full URL for this personal TV page
        base = request.url_root.rstrip("/")
        personal_url = f"{base}/t/{access_key}"
        qr_data_uri = make_qr_data_uri(personal_url)
    except Exception:
        try:
            # Fallback to tv.py helper
            from .tv import _qr_data_uri
            base = request.url_root.rstrip("/")
            personal_url = f"{base}/t/{access_key}"
            qr_data_uri = _qr_data_uri(personal_url, box_size=6)
        except Exception:
            qr_data_uri = ""

    return render_template("personal_tv.html", feed=feed, session=session, access_key=access_key, qr_data_uri=qr_data_uri)

@bp.get("/my-visit/<access_key>")
@rate_limit(limit=120, window=60.0)
def my_visit_api(access_key: str):
    """JSON feed for personal TV live poll — <1KB, fast on slow internet."""
    access_key = (access_key or "").strip()[:24]
    session = ptv_engine.get_session_by_access_key(access_key)
    if not session:
        return jsonify({"error": "not found"}), 404

    # Update presence
    try:
        from ..models_v2 import UserPresence
        presence = db.session.query(UserPresence).filter_by(org_id=session.org_id, patient_access_key=access_key).first()
        if presence:
            presence.last_seen_at = now_naive()
        else:
            presence = UserPresence(org_id=session.org_id, patient_access_key=access_key, last_seen_at=now_naive(), is_inside_hospital=True)
            db.session.add(presence)
        # Also update session last_seen
        session.last_seen_at = now_naive()
        db.session.commit()
    except Exception:
        db.session.rollback()

    feed = ptv_engine.build_personal_feed(session.org_id, session)
    return jsonify(feed)

@bp.post("/api/v1/my-visit/<access_key>/seen")
@rate_limit(limit=120, window=60.0)
def my_visit_seen(access_key: str):
    """Update last_seen_at — called by JS every 30s for presence detection."""
    access_key = (access_key or "").strip()[:24]
    session = ptv_engine.get_session_by_access_key(access_key)
    if not session:
        return jsonify({"error": "not found"}), 404
    try:
        from ..models_v2 import UserPresence
        session.last_seen_at = now_naive()
        presence = db.session.query(UserPresence).filter_by(org_id=session.org_id, patient_access_key=access_key).first()
        if presence:
            presence.last_seen_at = now_naive()
        else:
            presence = UserPresence(org_id=session.org_id, patient_access_key=access_key, last_seen_at=now_naive(), is_inside_hospital=True)
            db.session.add(presence)
        db.session.commit()
        return jsonify({"ok": True, "last_seen": session.last_seen_at.isoformat()})
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False}), 500

@bp.get("/my-visit/offline")
def offline_shell():
    """Offline shell for personal TV — cached by SW, shows last known."""
    return render_template("personal_tv_offline.html")
