"""JSON APIs: WhatsApp webhook, USSD complaint intake, health, offline sync."""
from __future__ import annotations

import hashlib
import hmac
import time

from flask import Blueprint, current_app, jsonify, request

from .. import services, whatsapp
from ..audit import audit
from ..models import Complaint, ComplaintStatusHistory, Department, Organization, db, now_naive
from ..security import csrf_exempt, rate_limit
from .. import scoring

bp = Blueprint("api", __name__, url_prefix="/api/v1")

# ---------------------------------------------------------------------------
# Probe result caches. /health and /ready are pinged by Render, UptimeRobot
# and the founder's dashboards every few seconds, around the clock. The
# schema-drift check in /ready is a FULL introspection of 100+ tables — small
# per call, but 24/7 polling on a metered-egress database (Supabase counts
# every byte shipped, and this org once shipped 424 GB in a month) makes
# per-ping introspection pure waste: schema drift does not appear and vanish
# between two pings 60 seconds apart. Both caches are per-process and expire
# quickly; a drift incident is therefore visible within a minute.
_READY_CACHE_TTL = 60.0
_ready_cache = {"at": 0.0, "payload": None, "status": 200}
_backup_cache = {"at": 0.0, "value": None}
_HEALTH_CACHE_TTL = 30.0
_health_extra = {"at": 0.0, "last_backup": None}


@bp.get("/health")
def health():
    """Liveness + readiness. Used by Render's health check and by the founder.

    Reports the things that actually break in production: the database, whether
    the background scheduler is still alive (it runs reminders, SLA escalation
    and backups — silent death means missed escalations), and when the last
    backup ran.
    """
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception:                                 # noqa: BLE001
        db.session.rollback()
        db_ok = False

    scheduler_ok = None
    try:
        from ..scheduler import ensure_running, is_alive
        scheduler_ok = is_alive()
        if scheduler_ok is False:
            # Self-heal: a dead scheduler means SLA escalations and duty
            # reminders have silently stopped. Restart it on the spot.
            ensure_running(current_app._get_current_object())
            scheduler_ok = is_alive()
    except Exception:                                 # noqa: BLE001
        scheduler_ok = None

    last_backup = _health_extra["last_backup"]
    now = time.monotonic()
    if (current_app.config.get("TESTING")
            or now - _health_extra["at"] > _HEALTH_CACHE_TTL):
        try:
            from ..backup import list_backups
            rows = list_backups(limit=1)
            last_backup = rows[0].created_at.isoformat() if rows else None
            _health_extra.update(at=now, last_backup=last_backup)
        except Exception:                             # noqa: BLE001
            # never cache a failed lookup — the next ping retries at once
            db.session.rollback()
            _health_extra.update(at=0.0, last_backup=None)
            last_backup = None

    healthy = db_ok and (scheduler_ok is not False)
    # v2 push + queue estimator + personal TV
    push_ok = False
    try:
        from .. import push as push_engine
        push_ok = push_engine.is_configured()
    except Exception:
        push_ok = False

    payload = {
        "status": "ok" if healthy else "degraded",
        "database": db_ok,
        "scheduler": scheduler_ok,
        "last_backup": last_backup,
        "storage": current_app.config.get("STORAGE_BACKEND", "db"),
        "whatsapp_mode": whatsapp.mode(),
        "sms_mode": current_app.config.get("SMS_MODE", "sandbox"),
        "twilio_sid_set": bool(current_app.config.get("TWILIO_ACCOUNT_SID")),
        "twilio_from_set": bool(current_app.config.get("TWILIO_FROM")),
        "twilio_wa_from_set": bool(current_app.config.get("TWILIO_WHATSAPP_FROM") or current_app.config.get("TWILIO_FROM")),
        "push_configured": push_ok,
        "push_mode": "vapid" if push_ok else "off",
        "queue_estimator": current_app.config.get("QUEUE_ESTIMATOR_ENABLED", True),
        "patient_sms_inside": current_app.config.get("PATIENT_SMS_INSIDE_HOSPITAL", False),
        "version": current_app.config.get("APP_VERSION", "1.8.0"),
        "mail": None,
    }
    try:
        from .. import mailer
        payload["mail"] = mailer.status()["provider"] if mailer.is_configured() else "off"
    except Exception:  # noqa: BLE001
        payload["mail"] = "off"
    # ALWAYS HTTP 200 — this is a LIVENESS probe, and it is the URL the host
    # uses to decide whether a deploy succeeded. Returning 503 while the
    # database is down makes the platform kill a perfectly good container,
    # turning a recoverable database wobble into a total site outage (exactly
    # what happened on 2026-08-15). Read the "status" field to see health;
    # use /api/v1/ready when you specifically need a readiness check.
    return jsonify(payload), 200


@bp.get("/ready")
def ready():
    """Strict readiness probe: 503 unless the database is actually usable.

    Deliberately NOT the platform health check — use this for monitoring
    dashboards and alerting, where you want to be paged for a degraded state.
    """
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:                                 # noqa: BLE001
        db.session.rollback()
        return jsonify(ready=False, reason="database unreachable"), 503

    # SCHEMA DRIFT CHECK.
    # A reachable database is not the same as a USABLE one. /hims/ once
    # returned 500 for every visitor because a migration had been edited after
    # it was applied, so the live table was missing a column the app read.
    # Connectivity looked perfect throughout. This compares what the app
    # expects against what the database actually has, so the next drift is
    # visible from outside instead of being discovered by a patient.
    #
    # CACHED for _READY_CACHE_TTL — but ONLY the healthy answer. Success is
    # the steady state that monitors hammer every few seconds; failure is
    # rare and must always be evaluated fresh so recovery is instant.
    # Under TESTING the cache is bypassed entirely: the test suite recreates
    # the database between tests, so a cached answer would lie.
    now = time.monotonic()
    if (not current_app.config.get("TESTING")
            and _ready_cache["status"] == 200
            and now - _ready_cache["at"] <= _READY_CACHE_TTL
            and _ready_cache["payload"] is not None):
        return _ready_cache["payload"], 200
    try:
        from sqlalchemy import inspect as _inspect
        insp = _inspect(db.engine)
        present = set(insp.get_table_names())
        missing = []
        for tname, table in db.metadata.tables.items():
            if tname not in present:
                missing.append(tname)
                continue
            cols = {c["name"] for c in insp.get_columns(tname)}
            missing.extend(f"{tname}.{c.name}" for c in table.columns
                           if c.name not in cols)
        if missing:
            _ready_cache.update(at=0.0, payload=None, status=503)
            return jsonify(ready=False, reason="schema drift",
                           missing=sorted(missing)[:20]), 503
        _ready_cache.update(at=now, payload=jsonify(ready=True), status=200)
        return _ready_cache["payload"], 200
    except Exception as exc:                          # noqa: BLE001
        db.session.rollback()
        _ready_cache.update(at=0.0, payload=None, status=503)
        return jsonify(ready=False, reason=f"schema check failed: {exc}"[:200]), 503


# ================================================================ live alerts (§19/§37)
# Admin/quality alerts.
ALERT_TEMPLATES = {
    "complaint_escalated": "emergency",
    "critical_score": "emergency",
    "inspection_overdue": "urgent",
    "ca_overdue": "urgent",
    "complaint_sla_warning": "standard",
}


def _speakable() -> dict:
    """Admin alerts PLUS patient-flow announcements.

    Previously only the five admin events above could ever be spoken, so a
    nurse waiting on patient announcements heard nothing at all — the engine
    worked, but nothing was ever routed into it.
    """
    from ..announce import PATIENT_ALERTS
    out = dict(ALERT_TEMPLATES)
    for key, (urgency, _subject) in PATIENT_ALERTS.items():
        out[key] = urgency
    return out


@bp.get("/alerts/prefs")
def alerts_prefs():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify(error="unauthenticated"), 401
    from ..models import UserPref
    return jsonify(UserPref.bundle(current_user.id))


@bp.get("/alerts/poll")
def alerts_poll():
    """New alert-level notifications since ?after=<id> — drives toasts, browser
    notifications and voice announcements (polling fallback per §22/§40).
    v2: also updates presence for smart SMS routing (no SMS if online) + returns personal TV url + priority."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify(error="unauthenticated"), 401
    after = request.args.get("after", type=int) or 0
    from ..models import AppNotification, UserPref
    speakable = _speakable()
    rows = (db.session.query(AppNotification)
            .filter(AppNotification.user_id == current_user.id,
                    AppNotification.channel.in_(("inapp","personal_tv","push")),
                    AppNotification.id > after,
                    AppNotification.template_key.in_(tuple(speakable)))
            .order_by(AppNotification.id).limit(10).all())
    prefs = UserPref.bundle(current_user.id)

    # v2: Update presence — smart routing knows user online, no SMS needed (cost saver)
    try:
        from ..models_v2 import UserPresence
        org_id = current_user.org_id
        presence = db.session.query(UserPresence).filter_by(org_id=org_id, user_id=current_user.id).first()
        if presence:
            presence.last_seen_at = now_naive()
            presence.device_info = request.headers.get("User-Agent", "")[:200]
        else:
            presence = UserPresence(org_id=org_id, user_id=current_user.id, last_seen_at=now_naive(),
                                    device_info=request.headers.get("User-Agent", "")[:200], is_inside_hospital=True)
            db.session.add(presence)
        db.session.commit()
    except Exception:
        db.session.rollback()

    # v2: Live counts for smart queue estimator — <1KB, fast on slow internet
    live_counts = {}
    try:
        from .. import queue_estimator
        live_counts = queue_estimator.get_live_counts(current_user.org_id)
    except Exception:
        pass

    return jsonify({
        "prefs": prefs,
        "alerts": [{"id": r.id, "subject": r.subject, "body": r.body,
                    "speech": r.body,
                    "urgency": speakable.get(r.template_key, "standard"),
                    "priority": getattr(r, 'priority', 'NORMAL'),
                    "category": getattr(r, 'category', 'general'),
                    "personal_tv_url": getattr(r, 'personal_tv_url', None),
                    "require_interaction": getattr(r, 'require_interaction', False),
                    "vibrate": getattr(r, 'vibrate', None),
                    "at": r.created_at.strftime("%H:%M")} for r in rows],
        "last_id": rows[-1].id if rows else after,
        "live_counts": live_counts,
        "push_configured": bool(current_app.config.get("VAPID_PUBLIC_KEY")),
    })


@bp.get("/alerts/station")
@rate_limit(limit=120, window=60.0)
def alerts_station():
    """Shared station screen feed (dispensary tablet, nurses' desk).

    No login: a ward tablet is not signed in as any individual. It is scoped to
    one department and only ever returns announcements — never patient names
    from other areas, never clinical detail.
    """
    from ..announce import PATIENT_ALERTS
    from ..models import AppNotification
    from ..services import current_org
    org = current_org()
    if not org:
        return jsonify(alerts=[], last_id=0)
    after = request.args.get("after", type=int) or 0
    dept_id = request.args.get("dept", type=int)
    q = (db.session.query(AppNotification)
         .filter(AppNotification.org_id == org.id,
                 AppNotification.channel == "station",
                 AppNotification.id > after,
                 AppNotification.template_key.in_(tuple(PATIENT_ALERTS))))
    if dept_id:
        q = q.filter(AppNotification.entity_id == dept_id)
    rows = q.order_by(AppNotification.id).limit(10).all()
    return jsonify({
        "alerts": [{"id": r.id, "subject": r.subject, "body": r.body,
                    "speech": r.body,
                    "urgency": PATIENT_ALERTS.get(r.template_key, ("standard",))[0],
                    "at": r.created_at.strftime("%H:%M")} for r in rows],
        "last_id": rows[-1].id if rows else after,
    })


# ================================================================ WhatsApp webhook
@csrf_exempt("api.whatsapp_webhook")
@bp.get("/whatsapp/webhook")
def whatsapp_verify():
    """Meta subscription verification handshake."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and token == current_app.config.get("WHATSAPP_VERIFY_TOKEN", "") \
            and current_app.config.get("WHATSAPP_VERIFY_TOKEN"):
        return challenge, 200
    return "forbidden", 403


@csrf_exempt("api.whatsapp_webhook_post")
@bp.post("/whatsapp/webhook")
def whatsapp_webhook():
    """Receive delivery statuses + inbound messages from the Cloud API.

    F-005: this used to SKIP signature verification when WHATSAPP_APP_SECRET
    was unset — anyone on the internet could POST fake inbound messages or
    delivery statuses. It now fails CLOSED: no secret configured means the
    webhook is not deployed, and requests are refused with 503 until an
    operator sets the secret. With the secret set, the Meta signature is
    mandatory (constant-time compare) and mismatched signatures get 403.
    """
    secret = (current_app.config.get("WHATSAPP_APP_SECRET") or "").strip()
    if not secret:
        current_app.logger.error(
            "WhatsApp webhook POST received while WHATSAPP_APP_SECRET is not "
            "configured — REJECTING (fail-closed). Set the secret in the "
            "Meta app dashboard and the environment before enabling.")
        return "webhook not configured", 503
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return "invalid signature", 403
    data = request.get_json(silent=True) or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for status in value.get("statuses", []):
                whatsapp.apply_webhook_status(status.get("id", ""), status.get("status", ""))
            for message in value.get("messages", []):
                if (message.get("type") or "") != "text":
                    continue
                body = ((message.get("text") or {}).get("body") or "").strip()
                frm = (message.get("from") or "").strip()
                if not body or not frm:
                    continue
                try:
                    from ..chatbot.serve import handle_whatsapp
                    from ..services import current_org
                    # F-019: route by the business number that received the
                    # message — each hospital records its own Meta number
                    # identity (whatsapp_phone_number_id / _display_number
                    # settings). Only a genuinely single-hospital deployment
                    # may fall back to "the" org; on a multi-hospital server
                    # an unmapped number is logged and ignored, never guessed.
                    meta = value.get("metadata") or {}
                    org = whatsapp.org_for_number(meta.get("phone_number_id"),
                                                  meta.get("display_phone_number"))
                    if org is None:
                        fallback = current_org()
                        multi = db.session.query(Organization).count() > 1
                        if multi:
                            current_app.logger.error(
                                "Inbound WhatsApp for number id=%s display=%s matches "
                                "no hospital's number mapping — NOT routing (multi-tenant). "
                                "Set the hospital's whatsapp_phone_number_id setting.",
                                meta.get("phone_number_id"), meta.get("display_phone_number"))
                            continue
                        org = fallback
                    handle_whatsapp(org.id, frm, body)
                except Exception:                        # noqa: BLE001
                    current_app.logger.exception("whatsapp inbound chat failed")
                    db.session.rollback()
    return "ok", 200


# ================================================================ USSD / gateway intake
@csrf_exempt("api.ussd_queue")
@bp.post("/ussd/queue")
@rate_limit(limit=30, window=60.0)
def ussd_queue():
    """USSD intake: join the queue (spec §6 USSD/SMS fallback).
    Multi-hospital: hospital_code required, no fallback to first org (security fix).
    Feature phone provision: USSD works without smartphone.
    Cost saver: PersonalTvSession is_inside=False so SMS allowed as fallback (outside hospital).
    """
    import secrets as _secrets
    from ..sms import normalize_ng_number
    cfg_secret = current_app.config.get("USSD_SHARED_SECRET", "")
    data = request.get_json(silent=True) or {}
    if not cfg_secret or data.get("secret") != cfg_secret:
        return jsonify(error="unauthorized"), 401
    hcode = (data.get("hospital_code") or "").strip().upper()
    if not hcode:
        return jsonify(error="hospital_code required"), 422
    org = db.session.query(Organization).filter_by(code=hcode).first()
    if not org:
        return jsonify(error="unknown hospital_code"), 404
    dept_q = (data.get("department") or "").strip()
    if not dept_q:
        return jsonify(error="department required"), 422
    dept = (db.session.query(Department)
            .filter_by(org_id=org.id, active=True)
            .filter(Department.name.ilike(f"%{dept_q}%")).first())
    name = (data.get("name") or "").strip()
    if not dept or len(name) < 2:
        return jsonify(error="missing department or name"), 422
    from ..models import QueueTicket
    from .queue import next_ticket, _dept_letter
    now = now_naive()
    phone_raw = (data.get("phone") or "").strip()
    try:
        phone_norm = normalize_ng_number(phone_raw) if phone_raw else None
    except Exception:
        phone_norm = None
    n = next_ticket(org.id, dept, now.date())
    t = QueueTicket(org_id=org.id, code=f"{_dept_letter(dept)}-{n:03d}",
                    access_key=_secrets.token_urlsafe(12), department_id=dept.id,
                    queue_date=now.date(), patient_name=name[:120],
                    phone=phone_norm or phone_raw or None,
                    status="WAITING", source="ussd")
    db.session.add(t)
    db.session.flush()
    try:
        from .. import personal_tv as ptv
        sess = ptv.ensure_personal_session(org.id, ticket=t)
        sess.is_inside_hospital = False
        ptv.update_session_from_ticket(sess, t)
    except Exception:
        current_app.logger.exception("personal TV session create failed for USSD queue")
    audit("QUEUE_JOINED", "queue_ticket", t.id, {"code": t.code, "source": "ussd"}, org_id=org.id)
    db.session.commit()
    return jsonify(ticket=t.code, access_key=t.access_key,
                   personal_tv_url=f"/t/{t.access_key}",
                   message=f"You are in the {dept.name} queue. Your number is {t.code}. Track at /t/{t.access_key}")


@csrf_exempt("api.ussd_booking")
@bp.post("/ussd/booking")
@rate_limit(limit=30, window=60.0)
def ussd_booking():
    """USSD aggregator intake for bookings (spec §5 USSD-ready).
    Multi-hospital: hospital_code required, no fallback (security fix).
    Feature phone provision: USSD booking without smartphone.
    """
    from datetime import date as _date, timedelta
    from ..sms import normalize_ng_number
    cfg_secret = current_app.config.get("USSD_SHARED_SECRET", "")
    data = request.get_json(silent=True) or {}
    if not cfg_secret or data.get("secret") != cfg_secret:
        return jsonify(error="unauthorized"), 401
    hcode = (data.get("hospital_code") or "").strip().upper()
    if not hcode:
        return jsonify(error="hospital_code required"), 422
    org = db.session.query(Organization).filter_by(code=hcode).first()
    if not org:
        return jsonify(error="unknown hospital_code"), 404
    dept_q = (data.get("department") or "").strip()
    if not dept_q:
        return jsonify(error="department required"), 422
    dept = (db.session.query(Department)
            .filter_by(org_id=org.id, active=True)
            .filter(Department.name.ilike(f"%{dept_q}%")).first())
    phone_raw = (data.get("phone") or "").strip()
    try:
        phone_norm = normalize_ng_number(phone_raw) if phone_raw else phone_raw
    except Exception:
        phone_norm = phone_raw
    name = (data.get("name") or "").strip()
    raw_date = (data.get("date") or "").strip()
    slot = (data.get("time") or "").strip()
    if not dept or not name or len(phone_norm or "") < 7:
        return jsonify(error="missing department, name or phone"), 422
    try:
        day = _date.fromisoformat(raw_date)
    except ValueError:
        return jsonify(error="invalid date"), 422
    now = now_naive()
    window = int(services.get_setting(org.id, "booking_window_days") or 30)
    slots = services.get_setting(org.id, "booking_slots") or []
    if day < now.date() or day > now.date() + timedelta(days=window) or slot not in slots:
        return jsonify(error="date/time not available"), 422
    if services.slot_is_full(org.id, dept.id, day, slot):
        return jsonify(error="slot full"), 422
    from ..models import Appointment
    apt = Appointment(org_id=org.id, ref=services.next_appointment_ref(org, now),
                      department_id=dept.id, appointment_date=day, appointment_time=slot,
                      patient_name=name[:120], phone=phone_norm, status="BOOKED", source="ussd")
    db.session.add(apt)
    db.session.flush()
    from .. import referrals as refeng
    refeng.stamp_booking(org.id, apt, code=data.get("referral_code") or "")
    # Personal TV session for booking — outside hospital, SMS allowed as fallback
    try:
        from .. import personal_tv as ptv
        sess = ptv.ensure_personal_session(org.id, appointment=apt)
        sess.is_inside_hospital = False
        ptv.update_session_from_appointment(sess, apt)
    except Exception:
        current_app.logger.exception("personal TV session create failed for USSD booking")
    # Capture personal TV access key for response — feature phone provision
    ptv_key = None
    try:
        ptv_key = sess.access_key if 'sess' in locals() and sess else None
    except Exception:
        ptv_key = None
    audit("BOOKING_CREATED", "appointment", apt.id, {"ref": apt.ref, "source": "ussd"}, org_id=org.id)
    db.session.commit()
    return jsonify(ref=apt.ref, status="BOOKED",
                   access_key=ptv_key,
                   personal_tv_url=f"/t/{ptv_key}" if ptv_key else None,
                   message=f"Booking confirmed: {day} at {slot}. Reference: {apt.ref}")


@csrf_exempt("api.ussd_complaint")
@bp.post("/ussd/complaint")
@rate_limit(limit=30, window=60.0)
def ussd_complaint():
    """Intake for a Nigerian USSD aggregator.

    Expected JSON: {secret, hospital_code, department, category, description, phone}
    The aggregator collects the fields over USSD sessions and POSTs here.
    Multi-hospital: hospital_code required, no fallback (security fix).
    Cost saver: complaints are serious — SMS allowed even inside per founder rule.
    """
    cfg_secret = current_app.config.get("USSD_SHARED_SECRET", "")
    data = request.get_json(silent=True) or {}
    if not cfg_secret or data.get("secret") != cfg_secret:
        return jsonify(error="unauthorized"), 401
    hcode = (data.get("hospital_code") or "").strip().upper()
    if not hcode:
        return jsonify(error="hospital_code required"), 422
    org = db.session.query(Organization).filter_by(code=hcode).first()
    if not org:
        return jsonify(error="unknown hospital_code"), 404
    dept_q = (data.get("department") or "").strip()
    if not dept_q:
        return jsonify(error="department required"), 422
    dept = (db.session.query(Department)
            .filter_by(org_id=org.id, active=True)
            .filter(Department.name.ilike(f"%{dept_q}%")).first())
    phone_raw = (data.get("phone") or "").strip()
    description = (data.get("description") or "").strip()
    if not dept or len(description) < 5 or len(phone_raw) < 7:
        return jsonify(error="missing department, description or phone"), 422

    from .complaints import PHONE_RE
    from ..sms import normalize_ng_number
    try:
        phone_norm = normalize_ng_number(phone_raw)
    except Exception:
        phone_norm = phone_raw
    if not PHONE_RE.match((phone_norm or phone_raw).replace(" ", "")):
        return jsonify(error="invalid phone"), 422

    now = now_naive()
    sla_hours = int(services.get_setting(org.id, "sla_hours") or 24)
    c = Complaint(org_id=org.id, ref=services.next_complaint_ref(org, now),
                  department_id=dept.id, category=(data.get("category") or "General").strip(),
                  description=description, phone=phone_norm or phone_raw, source="ussd", status="NEW",
                  sla_hours=sla_hours, sla_deadline_at=scoring.sla_deadline(now, sla_hours))
    db.session.add(c)
    db.session.flush()
    from .. import notifications as _notes
    ack = _notes.patient_update_text("received", org.name, c.ref)
    db.session.add(ComplaintStatusHistory(complaint_id=c.id, from_status=None, to_status="NEW",
                                          note="Submitted via USSD", patient_message=ack))
    audit("COMPLAINT_SUBMITTED", "complaint", c.id, {"ref": c.ref, "source": "ussd"}, org_id=org.id)

    from .. import notifications
    ctx = {"ref": c.ref, "dept": dept.name, "category": c.category, "sla": sla_hours,
           "hospital": org.name}
    duty = services.on_duty(org.id, now.date())
    if duty:
        notifications.notify(org.id, duty, "complaint_new_admin", ctx, channels=["inapp"],
                             entity_type="complaint", entity_id=c.id)
    hod = services.route_hod(dept)
    if hod:
        notifications.notify(org.id, hod, "complaint_new_hod", ctx, channels=["inapp"],
                             entity_type="complaint", entity_id=c.id)
    db.session.commit()
    # Complaints are serious — SMS allowed even inside per founder rule (PATIENT_SMS_INSIDE check bypassed for complaints)
    notifications.notify_complaint_patient(org, c, "received")
    return jsonify(ref=c.ref, status="NEW",
                   message=f"Your complaint has been received. Reference: {c.ref}")

# ================================================================ USSD callback for Africa's Talking / generic aggregator
# Feature phone / future phone / non-Android/iOS provision — USSD works without smartphone
# Multi-hospital: hospital_code required or serviceCode mapping
# Slow internet: CON/END plain text <160 chars, no JSON, works on 2G
# Premium: personal TV session created, is_inside=False so SMS allowed as fallback (outside)
@csrf_exempt("api.ussd_callback")
@bp.post("/ussd/callback")
@rate_limit(limit=60, window=60.0)
def ussd_callback():
    """Africa's Talking USSD callback — CON/END plain text.

    Accepts both form-encoded (AT) and JSON.
    AT sends: sessionId, serviceCode, phoneNumber, text
    Generic aggregator may send: hospital_code, phone, text, session_id

    Flow is stateless via text split by * — Africa optimized for slow 2G.

    Returns text/plain with CON or END — must be exactly that format.
    """
    from flask import Response
    from ..sms import normalize_ng_number
    import secrets as _secrets

    # Parse input — support both form and JSON
    data_form = request.form.to_dict() if request.form else {}
    data_json = request.get_json(silent=True) or {}
    data = {**data_json, **data_form}  # form overrides json if both

    session_id = (data.get("sessionId") or data.get("session_id") or "").strip()
    service_code = (data.get("serviceCode") or data.get("service_code") or "").strip()
    phone_raw = (data.get("phoneNumber") or data.get("phone") or data.get("msisdn") or "").strip()
    text = (data.get("text") or "").strip()

    try:
        phone_norm = normalize_ng_number(phone_raw) if phone_raw else phone_raw
    except Exception:
        phone_norm = phone_raw

    parts = text.split("*") if text else []

    # Resolve org — via serviceCode mapping or first token as hospital_code
    org = None
    org_code = None
    offset = 0  # how many tokens consumed for org identification

    # Check serviceCode mapping from config: USSD_SERVICE_CODE_MAP like {"*384*123#": "HOSP"}
    try:
        mapping = current_app.config.get("USSD_SERVICE_CODE_MAP") or {}
        if isinstance(mapping, str):
            import json as _json
            mapping = _json.loads(mapping) if mapping else {}
        if service_code and service_code in mapping:
            org_code = str(mapping[service_code]).strip().upper()
            org = db.session.query(Organization).filter_by(code=org_code).first()
            offset = 0
    except Exception:
        pass

    # If not via mapping, first token is hospital_code if text non-empty
    if not org:
        if parts and parts[0]:
            # Try first part as org code — must be 2-10 alphanumeric
            candidate = parts[0].strip().upper()
            if 2 <= len(candidate) <= 12 and candidate.isalnum():
                # Check if org exists
                cand_org = db.session.query(Organization).filter_by(code=candidate).first()
                if cand_org:
                    org = cand_org
                    org_code = candidate
                    offset = 1
                else:
                    # If we have no mapping and first token not a valid org, but text is like "1" (menu choice)
                    # then we need org — but we don't know it yet, so ask for it
                    # Only treat as org code if it looks like code and we are at first level
                    # If parts length ==1 and it is numeric menu, then org missing
                    if candidate.isdigit():
                        # Menu choice but org not resolved — need org code
                        pass
                    else:
                        # Invalid hospital code
                        resp_text = f"END Invalid hospital code {candidate}. Please check and dial again."
                        return Response(resp_text, mimetype="text/plain")

    # If org still not resolved and text empty — ask for hospital code
    if not org and not text:
        resp_text = "CON Welcome to Hospital Suite\nEnter hospital code:"
        return Response(resp_text, mimetype="text/plain")

    # If org still not resolved and text non-empty but first token was not org — ask for org
    if not org:
        # Could be that user entered menu choice without org — we need to ask org first
        # If text is numeric (menu), we need org
        resp_text = "CON Enter hospital code:"
        # If text has content that is not org, we treat it as org attempt and failed
        if parts and parts[0] and not parts[0].strip().upper().isdigit():
            resp_text = f"END Invalid hospital code {parts[0]}. Dial again."
        return Response(resp_text, mimetype="text/plain")

    # Now org resolved — remaining parts after offset
    remaining = parts[offset:] if len(parts) > offset else []
    # Filter empty trailing?
    # remaining may have [""] if text ends with * — handle

    # Helper to get department list string for USSD (numbered)
    def dept_list_con():
        depts = db.session.query(Department).filter_by(org_id=org.id, active=True).order_by(Department.name).limit(8).all()
        if not depts:
            return "END No departments available. Try later."
        lines = [f"{i+1}. {d.name[:20]}" for i, d in enumerate(depts)]
        return "CON Select department:\n" + "\n".join(lines)

    def resolve_dept(input_str):
        input_str = (input_str or "").strip()
        if not input_str:
            return None
        # If numeric, map to department by index
        if input_str.isdigit():
            try:
                idx = int(input_str) - 1
                depts = db.session.query(Department).filter_by(org_id=org.id, active=True).order_by(Department.name).limit(8).all()
                if 0 <= idx < len(depts):
                    return depts[idx]
            except Exception:
                pass
        # Else try ilike
        return db.session.query(Department).filter_by(org_id=org.id, active=True).filter(Department.name.ilike(f"%{input_str}%")).first()

    # If no remaining — show main menu
    if not remaining or (len(remaining) == 1 and remaining[0] == ""):
        resp_text = f"CON Welcome to {org.name}\n1. Join Queue\n2. Book Appointment\n3. Check Status\n4. Complaint\n5. Help"
        return Response(resp_text, mimetype="text/plain")

    choice = (remaining[0] or "").strip()

    # Choice 1: Join Queue
    if choice == "1":
        if len(remaining) == 1:
            return Response(dept_list_con(), mimetype="text/plain")
        if len(remaining) == 2:
            return Response("CON Enter your full name:", mimetype="text/plain")
        if len(remaining) >= 3:
            dept_input = remaining[1]
            name_input = remaining[2]
            dept = resolve_dept(dept_input)
            if not dept:
                return Response("END Invalid department. Dial again.", mimetype="text/plain")
            if len(name_input.strip()) < 2:
                return Response("END Name too short. Dial again.", mimetype="text/plain")
            # Create ticket
            try:
                from ..models import QueueTicket
                from .queue import next_ticket, _dept_letter
                now = now_naive()
                n = next_ticket(org.id, dept, now.date())
                t = QueueTicket(org_id=org.id, code=f"{_dept_letter(dept)}-{n:03d}",
                                access_key=_secrets.token_urlsafe(12), department_id=dept.id,
                                queue_date=now.date(), patient_name=name_input.strip()[:120],
                                phone=phone_norm or phone_raw or None,
                                status="WAITING", source="ussd")
                db.session.add(t)
                db.session.flush()
                try:
                    from .. import personal_tv as ptv
                    sess = ptv.ensure_personal_session(org.id, ticket=t)
                    sess.is_inside_hospital = False
                    ptv.update_session_from_ticket(sess, t)
                except Exception:
                    current_app.logger.exception("USSD callback personal TV failed")
                audit("QUEUE_JOINED", "queue_ticket", t.id, {"code": t.code, "source": "ussd_callback", "session": session_id}, org_id=org.id)
                db.session.commit()
                return Response(f"END You are in {dept.name} queue. Your number is {t.code}. Track: /t/{t.access_key} SMS will update you.", mimetype="text/plain")
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception("USSD queue callback failed")
                return Response("END Sorry, could not join queue. Try again later.", mimetype="text/plain")

    # Choice 2: Book Appointment — simplified for USSD: dept, date YYYY-MM-DD, time, name
    elif choice == "2":
        if len(remaining) == 1:
            return Response(dept_list_con(), mimetype="text/plain")
        if len(remaining) == 2:
            return Response("CON Enter date YYYY-MM-DD:", mimetype="text/plain")
        if len(remaining) == 3:
            # Validate date then ask time
            try:
                from datetime import date as _date
                _date.fromisoformat(remaining[2].strip())
            except Exception:
                return Response("END Invalid date format. Use YYYY-MM-DD.", mimetype="text/plain")
            # Show available slots for that date
            try:
                slots = services.get_setting(org.id, "booking_slots") or ["09:00", "10:00", "11:00"]
                slot_lines = [f"{i+1}. {s}" for i, s in enumerate(slots[:6])]
                return Response("CON Select time:\n" + "\n".join(slot_lines), mimetype="text/plain")
            except Exception:
                return Response("CON Enter time HH:MM:", mimetype="text/plain")
        if len(remaining) == 4:
            return Response("CON Enter your full name:", mimetype="text/plain")
        if len(remaining) >= 5:
            dept_input = remaining[1]
            date_input = remaining[2]
            time_input = remaining[3]
            name_input = remaining[4]
            dept = resolve_dept(dept_input)
            if not dept:
                return Response("END Invalid department.", mimetype="text/plain")
            # Resolve time if numeric
            if time_input.isdigit():
                try:
                    slots = services.get_setting(org.id, "booking_slots") or []
                    idx = int(time_input)-1
                    if 0 <= idx < len(slots):
                        time_input = slots[idx]
                except Exception:
                    pass
            # Create booking
            try:
                from datetime import date as _date, timedelta
                day = _date.fromisoformat(date_input.strip())
                now = now_naive()
                window = int(services.get_setting(org.id, "booking_window_days") or 30)
                slots = services.get_setting(org.id, "booking_slots") or []
                if day < now.date() or day > now.date() + timedelta(days=window) or (slots and time_input not in slots):
                    return Response("END Date/time not available.", mimetype="text/plain")
                if services.slot_is_full(org.id, dept.id, day, time_input):
                    return Response("END Slot full. Try another time.", mimetype="text/plain")
                from ..models import Appointment
                apt = Appointment(org_id=org.id, ref=services.next_appointment_ref(org, now),
                                  department_id=dept.id, appointment_date=day, appointment_time=time_input,
                                  patient_name=name_input.strip()[:120], phone=phone_norm or phone_raw or None,
                                  status="BOOKED", source="ussd")
                db.session.add(apt)
                db.session.flush()
                try:
                    from .. import personal_tv as ptv
                    sess = ptv.ensure_personal_session(org.id, appointment=apt)
                    sess.is_inside_hospital = False
                    ptv.update_session_from_appointment(sess, apt)
                    ptv_key = sess.access_key
                except Exception:
                    ptv_key = None
                audit("BOOKING_CREATED", "appointment", apt.id, {"ref": apt.ref, "source": "ussd_callback"}, org_id=org.id)
                db.session.commit()
                extra = f" Track /t/{ptv_key}" if ptv_key else ""
                return Response(f"END Booking confirmed {day} at {time_input}. Ref: {apt.ref}.{extra}", mimetype="text/plain")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("USSD booking callback failed")
                return Response("END Booking failed. Try later.", mimetype="text/plain")

    # Choice 3: Check Status
    elif choice == "3":
        if len(remaining) == 1:
            return Response("CON Enter ticket code (e.g. G-001):", mimetype="text/plain")
        if len(remaining) >= 2:
            code_input = remaining[1].strip().upper()
            try:
                from ..models import QueueTicket
                # USSD audit: ticket codes recycle EVERY day (G-001 is today's
                # first ticket and last month's). Match today's ticket first;
                # for an older code, only the caller's own number may resolve
                # it — a bare sequential code must not reveal a stranger's
                # queue status.
                t = (db.session.query(QueueTicket)
                     .filter_by(org_id=org.id, code=code_input,
                                queue_date=now_naive().date()).first())
                if t is None and (phone_norm or phone_raw):
                    t = (db.session.query(QueueTicket)
                         .filter(QueueTicket.org_id == org.id,
                                 QueueTicket.code == code_input,
                                 QueueTicket.phone.in_(
                                     [p for p in (phone_norm, phone_raw) if p]))
                         .order_by(QueueTicket.id.desc()).first())
                if not t:
                    return Response("END Ticket not found. Check code.", mimetype="text/plain")
                # Estimate position
                try:
                    from .. import queue_estimator
                    waiting = db.session.query(QueueTicket).filter(
                        QueueTicket.org_id == org.id,
                        QueueTicket.queue_date == t.queue_date,
                        QueueTicket.status == "WAITING",
                        QueueTicket.created_at < t.created_at,
                        QueueTicket.department_id == t.department_id
                    ).count() if t.created_at else 0
                    pos = waiting + 1 if t.status == "WAITING" else 0
                    wait = queue_estimator.estimate_wait_minutes(org.id, "RECEPTION", position=waiting, is_fast_track=bool(getattr(t, 'is_fast_track', False))) if t.status == "WAITING" else 0
                    if t.status == "WAITING":
                        return Response(f"END Ticket {t.code}: {pos} in line, ~{wait} min wait. Dept {t.department.name if t.department else ''}.", mimetype="text/plain")
                    else:
                        return Response(f"END Ticket {t.code}: {t.status}.", mimetype="text/plain")
                except Exception:
                    return Response(f"END Ticket {t.code}: {t.status}.", mimetype="text/plain")
            except Exception:
                return Response("END Error checking status.", mimetype="text/plain")

    # Choice 4: Complaint
    elif choice == "4":
        if len(remaining) == 1:
            return Response(dept_list_con(), mimetype="text/plain")
        if len(remaining) == 2:
            return Response("CON Enter complaint category (e.g. Service, Cleanliness):", mimetype="text/plain")
        if len(remaining) == 3:
            return Response("CON Enter description (short):", mimetype="text/plain")
        if len(remaining) >= 4:
            dept_input = remaining[1]
            cat_input = remaining[2]
            desc_input = remaining[3]
            dept = resolve_dept(dept_input)
            if not dept:
                return Response("END Invalid department.", mimetype="text/plain")
            if len(desc_input.strip()) < 5:
                return Response("END Description too short.", mimetype="text/plain")
            try:
                sla_hours = int(services.get_setting(org.id, "sla_hours") or 24)
                c = Complaint(org_id=org.id, ref=services.next_complaint_ref(org, now_naive()),
                              department_id=dept.id, category=cat_input.strip()[:50] or "General",
                              description=desc_input.strip()[:500], phone=phone_norm or phone_raw or None,
                              source="ussd", status="NEW", sla_hours=sla_hours,
                              sla_deadline_at=scoring.sla_deadline(now_naive(), sla_hours))
                db.session.add(c)
                db.session.flush()
                from .. import notifications as _notes
                ack = _notes.patient_update_text("received", org.name, c.ref)
                db.session.add(ComplaintStatusHistory(complaint_id=c.id, from_status=None, to_status="NEW",
                                                      note="Submitted via USSD callback", patient_message=ack))
                audit("COMPLAINT_SUBMITTED", "complaint", c.id, {"ref": c.ref, "source": "ussd_callback"}, org_id=org.id)
                ctx = {"ref": c.ref, "dept": dept.name, "category": c.category, "sla": sla_hours, "hospital": org.name}
                duty = services.on_duty(org.id, now_naive().date())
                if duty:
                    from .. import notifications
                    notifications.notify(org.id, duty, "complaint_new_admin", ctx, channels=["inapp"], entity_type="complaint", entity_id=c.id)
                hod = services.route_hod(dept)
                if hod:
                    from .. import notifications
                    notifications.notify(org.id, hod, "complaint_new_hod", ctx, channels=["inapp"], entity_type="complaint", entity_id=c.id)
                db.session.commit()
                from .. import notifications
                notifications.notify_complaint_patient(org, c, "received")
                return Response(f"END Complaint received. Ref: {c.ref}. We will respond.", mimetype="text/plain")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("USSD complaint callback failed")
                return Response("END Complaint failed. Try later.", mimetype="text/plain")

    # Choice 5: Help
    elif choice == "5":
        return Response(f"END {org.name} Help: Dial *xxx# then hospital code {org.code}. For assistance visit reception or call. TV screens show live queue.", mimetype="text/plain")

    # Unknown choice
    return Response("END Invalid choice. Dial again and select 1-5.", mimetype="text/plain")

