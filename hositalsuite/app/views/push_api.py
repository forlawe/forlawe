"""
Web Push API — subscribe, unsubscribe, vapid public key
Works even when app closed like alarm, free, cost saver
Multi-browser: Chrome, Firefox, Edge, Samsung, Opera, Safari 16.4+ (PWA)
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user

from ..models import db, now_naive
from ..security import rate_limit, csrf_exempt
from .. import push as push_service

bp = Blueprint("push_api", __name__, url_prefix="/api/v1/push")

@bp.get("/vapid-public")
def vapid_public():
    """Public VAPID key for client subscribe — no auth needed, per-org multi-hospital.
    
    If access_key provided (personal TV), use that session's org_id for per-org VAPID.
    Else try current_user org_id or current_org().
    """
    org_id = None
    access_key = (request.args.get("access_key") or "").strip()[:24]
    if access_key:
        try:
            from ..personal_tv import get_session_by_access_key
            sess = get_session_by_access_key(access_key)
            if sess:
                org_id = sess.org_id
        except Exception:
            pass
    if not org_id and current_user and current_user.is_authenticated:
        org_id = current_user.org_id
    if not org_id:
        try:
            from ..services import current_org
            org = current_org()
            if org:
                org_id = org.id
        except Exception:
            pass

    key = push_service.get_vapid_public(org_id)
    if not key:
        # Fallback global
        key = push_service.get_vapid_public()
    if not key:
        return jsonify({"error": "push not configured", "public_key": ""}), 200
    return jsonify({"public_key": key, "org_id": org_id})

@csrf_exempt("push_api.subscribe")
@bp.post("/subscribe")
@rate_limit(limit=30, window=60.0)
def subscribe():
    """Subscribe to push — staff authenticated or patient anonymous via access_key.

    Body: {endpoint, keys:{p256dh, auth}, device_info, access_key?}
    For patient: access_key must be valid PersonalTvSession
    For staff: current_user must be authenticated
    """
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()[:500]
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()[:200]
    auth = (keys.get("auth") or "").strip()[:100]
    device_info = (data.get("device_info") or request.headers.get("User-Agent", "")[:200])
    access_key = (data.get("access_key") or "").strip()[:24]

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "missing endpoint or keys"}), 422

    # Resolve org_id
    org_id = None
    user_id = None
    patient_key = None

    # Detect browser
    ua = request.headers.get("User-Agent", "")
    browser = push_service._detect_browser(ua)

    if current_user and current_user.is_authenticated:
        org_id = current_user.org_id
        user_id = current_user.id
    elif access_key:
        # Anonymous patient via personal TV session
        from ..personal_tv import get_session_by_access_key
        session = get_session_by_access_key(access_key)
        if not session:
            return jsonify({"error": "invalid access_key"}), 404
        org_id = session.org_id
        patient_key = access_key
    else:
        # Try to resolve org from default
        try:
            from ..services import current_org
            org = current_org()
            if org:
                org_id = org.id
        except Exception:
            pass
        if not org_id:
            return jsonify({"error": "unauthenticated and no access_key"}), 401

    # Check existing by endpoint
    from ..models_v2 import PushSubscription, PersonalTvSession
    existing = db.session.query(PushSubscription).filter_by(endpoint=endpoint).first()
    if existing:
        existing.is_active = True
        existing.p256dh = p256dh
        existing.auth = auth
        existing.device_info = device_info[:200]
        existing.browser = browser
        existing.last_used_at = now_naive()
        if user_id:
            existing.user_id = user_id
        if patient_key:
            existing.patient_access_key = patient_key
        db.session.commit()
        # Link to personal TV session if patient
        if patient_key:
            try:
                sess = db.session.query(PersonalTvSession).filter_by(access_key=patient_key).first()
                if sess:
                    sess.push_sub_id = existing.id
                    db.session.commit()
            except Exception:
                db.session.rollback()
        return jsonify({"ok": True, "subscription_id": existing.id, "existing": True})

    sub = PushSubscription(
        org_id=org_id,
        user_id=user_id,
        patient_access_key=patient_key,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        device_info=device_info[:200],
        browser=browser,
        is_active=True
    )
    db.session.add(sub)
    db.session.flush()

    # Link to personal TV session if patient
    if patient_key:
        try:
            sess = db.session.query(PersonalTvSession).filter_by(access_key=patient_key).first()
            if sess:
                sess.push_sub_id = sub.id
        except Exception:
            pass

    db.session.commit()
    return jsonify({"ok": True, "subscription_id": sub.id, "existing": False})

@csrf_exempt("push_api.unsubscribe")
@bp.post("/unsubscribe")
@rate_limit(limit=30, window=60.0)
def unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()[:500]
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 422
    from ..models_v2 import PushSubscription
    sub = db.session.query(PushSubscription).filter_by(endpoint=endpoint).first()
    if sub:
        sub.is_active = False
        db.session.commit()
    return jsonify({"ok": True})

@bp.post("/test")
@rate_limit(limit=10, window=60.0)
def test_push():
    """Test push to current user — proves alarm works when closed."""
    if not current_user or not current_user.is_authenticated:
        return jsonify({"error": "unauthenticated"}), 401
    from ..models_v2 import PushSubscription
    subs = db.session.query(PushSubscription).filter_by(org_id=current_user.org_id, user_id=current_user.id, is_active=True).all()
    if not subs:
        return jsonify({"error": "no subscription — enable push first"}), 404

    from ..push import queue_push
    for sub in subs:
        queue_push(
            org_id=current_user.org_id,
            subscription_id=sub.id,
            title=f"{current_user.name.split()[0]}, test alarm",
            body="This is a test — if you see this when app closed, alarm works like real alarm!",
            url="/notifications",
            category="test",
            priority="HIGH",
            require_interaction=True
        )
    db.session.commit()
    # Process immediately
    try:
        from ..push import process_push_queue
        process_push_queue(limit=10)
    except Exception:
        pass
    return jsonify({"ok": True, "queued": len(subs)})
