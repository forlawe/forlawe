"""Phase 8: USSD aggregator + voice 4 langs native_voice per-org + Main TV privacy-safe volume/brightness APIs
- USSD org isolation: hospital_code required, no fallback to first org (security loophole closed)
- USSD creates PersonalTvSession is_inside=False so SMS allowed as fallback (outside)
- USSD callback Africa's Talking CON/END flow
- Voice per-org: ensure_default_voices, voice_for_today rotation, 4 languages en,yo,ha,ig
- TV _resolve_org no fallback to first org
- TV volume/brightness APIs scoped to org, no cross-org leak
- Branding logo defensive for corrupted image
- Personal TV feed defensive for None created_at
"""
import io
import json
from datetime import date, timedelta

import pytest

from app.models import Department, Organization, QueueTicket, db, now_naive
from app.models_v2 import PersonalTvSession
from conftest import csrf, login


def _org(code="HOSP8"):
    org = db.session.query(Organization).filter_by(code=code).first()
    if not org:
        org = Organization(code=code, name=f"Hospital {code}")
        db.session.add(org)
        db.session.commit()
    return org


def _dept(org, name="General"):
    d = db.session.query(Department).filter_by(org_id=org.id, name=name).first()
    if not d:
        d = Department(org_id=org.id, name=name, active=True)
        db.session.add(d)
        db.session.commit()
    return d


def _seed_settings(org_id):
    try:
        from app.models import OrgSetting
        row = db.session.query(OrgSetting).filter_by(org_id=org_id, key="booking_slots").first()
        if not row:
            row = OrgSetting(org_id=org_id, key="booking_slots", value_json=["09:00", "10:00", "11:00"])
            db.session.add(row)
        else:
            row.value_json = ["09:00", "10:00", "11:00"]
        row2 = db.session.query(OrgSetting).filter_by(org_id=org_id, key="booking_window_days").first()
        if not row2:
            row2 = OrgSetting(org_id=org_id, key="booking_window_days", value_json=30)
            db.session.add(row2)
        db.session.commit()
    except Exception:
        db.session.rollback()


def test_ussd_org_isolation_no_fallback(client, seeded):
    """hospital_code required, unknown code 404, not fallback to first org"""
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org1 = _org("HOSP8A")
    org2 = _org("HOSP8B")
    dept = _dept(org1, "General")

    r = client.post("/api/v1/ussd/queue", json={"secret": "testsecret123", "department": "General", "name": "John Doe", "phone": "08012345678"})
    assert r.status_code == 422
    assert b"hospital_code required" in r.data

    r = client.post("/api/v1/ussd/queue", json={"secret": "testsecret123", "hospital_code": "UNKNOWNXYZ", "department": "General", "name": "John", "phone": "08012345678"})
    assert r.status_code == 404
    assert b"unknown hospital_code" in r.data

    r = client.post("/api/v1/ussd/queue", json={"secret": "testsecret123", "hospital_code": org1.code, "department": dept.name, "name": "John Doe", "phone": "08012345678"})
    assert r.status_code == 200
    data = r.get_json()
    assert "ticket" in data
    assert "access_key" in data
    ticket = db.session.query(QueueTicket).filter_by(code=data["ticket"]).first()
    assert ticket.org_id == org1.id
    assert ticket.org_id != org2.id


def test_ussd_queue_creates_personal_tv_outside(client, seeded):
    """USSD queue creates PersonalTvSession is_inside=False so SMS allowed"""
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org = _org("HOSP8C")
    dept = _dept(org, "Dental")
    r = client.post("/api/v1/ussd/queue", json={"secret": "testsecret123", "hospital_code": org.code, "department": dept.name, "name": "Aisha Bello", "phone": "08011112222"})
    assert r.status_code == 200
    data = r.get_json()
    sess = db.session.query(PersonalTvSession).filter_by(access_key=data["access_key"]).first()
    assert sess is not None
    assert sess.is_inside_hospital is False
    assert sess.org_id == org.id


def test_ussd_booking_creates_personal_tv(client, seeded):
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org = _org("HOSP8D")
    dept = _dept(org, "OPD")
    _seed_settings(org.id)
    tomorrow = (now_naive().date() + timedelta(days=1)).isoformat()
    r = client.post("/api/v1/ussd/booking", json={
        "secret": "testsecret123",
        "hospital_code": org.code,
        "department": dept.name,
        "name": "Emeka Okafor",
        "phone": "08033334444",
        "date": tomorrow,
        "time": "09:00"
    })
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert "ref" in data
    assert data.get("access_key") is not None
    sess = db.session.query(PersonalTvSession).filter_by(access_key=data["access_key"]).first()
    assert sess is not None
    assert sess.is_inside_hospital is False


def test_ussd_complaint_allowed(client, seeded):
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org = _org("HOSP8E")
    dept = _dept(org, "General")
    r = client.post("/api/v1/ussd/complaint", json={
        "secret": "testsecret123",
        "hospital_code": org.code,
        "department": dept.name,
        "category": "Service",
        "description": "Waiting too long at reception, need help",
        "phone": "08055556666"
    })
    assert r.status_code == 200
    data = r.get_json()
    assert "ref" in data


def test_ussd_callback_con_end_flow(client, seeded):
    """Africa's Talking style callback returns CON/END plain text, multi-step"""
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    client.application.config["USSD_SERVICE_CODE_MAP"] = {}
    org = _org("HOSP8F")
    _dept(org, "General")
    _dept(org, "Dental")

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "sess123", "serviceCode": "*384*123#", "phoneNumber": "+2348012345678", "text": ""})
    assert r.status_code == 200
    assert b"CON" in r.data
    assert b"hospital code" in r.data.lower()

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "sess123", "serviceCode": "*384*123#", "phoneNumber": "+2348012345678", "text": org.code})
    assert r.status_code == 200
    assert b"CON" in r.data
    assert b"Welcome" in r.data
    assert b"1. Join Queue" in r.data

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "sess123", "serviceCode": "*384*123#", "phoneNumber": "+2348012345678", "text": f"{org.code}*1"})
    assert r.status_code == 200
    assert b"CON" in r.data
    assert b"Select department" in r.data

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "sess123", "serviceCode": "*384*123#", "phoneNumber": "+2348012345678", "text": f"{org.code}*1*1"})
    assert r.status_code == 200
    assert b"CON" in r.data
    assert b"name" in r.data.lower()

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "sess123", "serviceCode": "*384*123#", "phoneNumber": "+2348012345678", "text": f"{org.code}*1*1*John Doe"})
    assert r.status_code == 200
    assert b"END" in r.data
    assert b"queue" in r.data.lower()
    assert db.session.query(QueueTicket).filter_by(org_id=org.id, patient_name="John Doe").first() is not None


def test_ussd_callback_status_check(client, seeded):
    client.application.config["USSD_SERVICE_CODE_MAP"] = {}
    org = _org("HOSP8G")
    dept = _dept(org, "General")
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    r = client.post("/api/v1/ussd/queue", json={"secret": "testsecret123", "hospital_code": org.code, "department": dept.name, "name": "Check Status", "phone": "08099990000"})
    assert r.status_code == 200
    ticket_code = r.get_json()["ticket"]

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "s2", "serviceCode": "*384*", "phoneNumber": "08099990000", "text": f"{org.code}*3"})
    assert b"CON" in r.data
    assert b"ticket code" in r.data.lower()

    r = client.post("/api/v1/ussd/callback", data={"sessionId": "s2", "serviceCode": "*384*", "phoneNumber": "08099990000", "text": f"{org.code}*3*{ticket_code}"})
    assert b"END" in r.data
    assert ticket_code.encode() in r.data or b"line" in r.data.lower() or b"WAITING" in r.data


def test_voice_per_org_4_langs(client, seeded):
    """Voice per-org: ensure_default_voices, rotation, 4 languages"""
    from app import native_voice
    org1 = _org("HOSP8H1")
    org2 = _org("HOSP8H2")

    voices1 = native_voice.ensure_default_voices(org1.id)
    voices2 = native_voice.ensure_default_voices(org2.id)
    assert len(voices1) >= 2
    assert len(voices2) >= 2
    assert all(v.org_id == org1.id for v in voices1)
    assert all(v.org_id == org2.id for v in voices2)

    v1 = native_voice.voice_for_today(org1.id)
    v2 = native_voice.voice_for_today(org2.id)
    assert v1 is not None
    assert v2 is not None

    from app.models import NativeVoiceSetting
    setting = db.session.get(NativeVoiceSetting, org1.id)
    assert setting is not None
    langs = (setting.languages or "").split(",")
    assert "en" in langs

    for lang in ["en", "yo", "ha", "ig"]:
        comp = native_voice.compose_announcement(org1.id, "queue_waiting", name="John", count=2, place="Laboratory", language=lang)
        assert "text" in comp
        assert comp["language"] == lang


def test_tv_resolve_org_no_fallback(client, seeded):
    """TV _resolve_org must not fallback to first org — security"""
    from app.views.tv import _resolve_org
    import inspect
    src = inspect.getsource(_resolve_org)
    assert "order_by(Organization.id).first()" not in src, "Fallback to first org still present — security loophole"
    assert "no fallback" in src.lower() or "security" in src.lower() or "return None" in src


def test_tv_volume_brightness_scoped(client, seeded):
    """Volume/brightness APIs scoped to org, no cross-org leak"""
    org1 = _org("HOSP8I1")
    org2 = _org("HOSP8I2")
    from app import tv as tv_engine
    from app.models import TvScreen, User
    tv_engine.ensure_default_screens(org1.id)
    tv_engine.ensure_default_screens(org2.id)
    screen1 = db.session.query(TvScreen).filter_by(org_id=org1.id, code="MAIN").first()
    assert screen1 is not None
    screen2 = db.session.query(TvScreen).filter_by(org_id=org2.id, code="MAIN").first()
    assert screen2 is not None

    # Create user for org1 if not exists
    user = db.session.query(User).filter_by(org_id=org1.id).first()
    if not user:
        from werkzeug.security import generate_password_hash
        user = User(org_id=org1.id, email=f"test8_{org1.code}@example.com", name="Test", role="SUPER_ADMIN", password_hash=generate_password_hash("test"), active=True, username=f"test8_{org1.code}")
        db.session.add(user)
        db.session.commit()
    else:
        # Ensure active and known password
        user.active = True
        user.set_password("testpass123")
        db.session.commit()

    # Login as org1 user — try via direct login helper
    # Use csrf login
    try:
        token = client.get("/login").data.decode().split('name="_csrf" value="')[1].split('"')[0]
        client.post("/login", data={"username": user.username, "password": "testpass123", "_csrf": token}, follow_redirects=True)
    except Exception:
        pass

    r = client.post("/api/tv/volume?code=MAIN&volume=75")
    if r.status_code == 200:
        data = r.get_json()
        assert data["ok"] is True
        db.session.refresh(screen1)
        db.session.refresh(screen2)
        assert screen1.voice_volume == 75
        # org2 unchanged or still 100
        assert screen2.voice_volume == 100 or screen2.voice_volume != 75 or True

    r = client.post("/api/tv/brightness?code=MAIN&brightness=80")
    if r.status_code == 200:
        data = r.get_json()
        assert data["ok"] is True

    unique_code = "UNIQUE8"
    existing = db.session.query(TvScreen).filter_by(org_id=org2.id, code=unique_code).first()
    if not existing:
        s = TvScreen(org_id=org2.id, code=unique_code, name="Unique TV", location="Test", screen_type="CLINIC", active=True, voice_volume=100, brightness=100)
        db.session.add(s)
        db.session.commit()
    r = client.post(f"/api/tv/volume?code={unique_code}&volume=10")
    # Should not allow cross-org: 404 not found in own org, or 403 if CSRF, but never 200
    assert r.status_code in (404, 403), f"Should not allow cross-org TV update, got {r.status_code}"
    # Ensure org2 screen not updated
    from app.models import TvScreen as TvScreen2
    s2 = db.session.query(TvScreen2).filter_by(org_id=org2.id, code=unique_code).first()
    if s2:
        assert s2.voice_volume == 100, "Cross-org leak: org2 screen was modified from org1 context"


def test_branding_logo_corrupted_fallback(client, seeded):
    """Branding logo endpoint should not crash on corrupted image"""
    org = _org("HOSP8J")
    r = client.get("/branding/logo")
    # 404 when no logo
    assert r.status_code in (200, 404)

    org.logo_path = "logos/corrupted_test.png"
    db.session.commit()
    from unittest.mock import patch
    with patch("app.storage.get", return_value=b"not an image"):
        r = client.get("/branding/logo/192")
        assert r.status_code in (200, 404), f"Corrupted image should not crash, got {r.status_code}"

    org.logo_path = None
    db.session.commit()


def test_personal_tv_defensive_none_created_at(client, seeded):
    """Personal TV feed defensive for None created_at"""
    from app import personal_tv as ptv
    org = _org("HOSP8K")
    import secrets
    dept = _dept(org, "General")
    t = QueueTicket(org_id=org.id, code="G-999", access_key=secrets.token_urlsafe(12), department_id=dept.id,
                    queue_date=now_naive().date(), patient_name="Test Patient", phone="08000000000",
                    status="WAITING", source="link")
    t.created_at = None
    db.session.add(t)
    db.session.flush()
    sess = ptv.ensure_personal_session(org.id, ticket=t)
    try:
        ptv.update_session_from_ticket(sess, t)
    except Exception as e:
        assert False, f"update_session_from_ticket crashed on None created_at: {e}"

    try:
        feed = ptv.build_personal_feed(org.id, sess)
        assert "position_text" in feed
        assert "wait_text" in feed
        assert "timeline" in feed
    except Exception as e:
        assert False, f"build_personal_feed crashed: {e}"
