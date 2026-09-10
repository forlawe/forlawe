"""End-to-end tests of the full business workflow (spec section 40 & 46)."""
import io
import os
from datetime import timedelta

from app import scoring, services, whatsapp
from app.models import (AppNotification, Complaint, DutyRoster, Inspection,
                        Setting, User, WhatsAppMessage, db, now_naive)
from app.audit import verify_chain

from conftest import csrf, login


# ================================================================ INSPECTION E2E
def test_full_inspection_flow_low_score_requires_explanation_pdf_whatsapp(client, seeded, app):
    login(client, "am1")

    # 1) score of 2 WITHOUT explanation must be rejected
    token = csrf(client, "/inspections/new")
    data = {"_csrf": token, "department_id": seeded["dept"],
            "score_1": "5", "score_2": "5", "score_3": "2", "score_4": "5", "score_5": "5"}
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    assert b"explanation is REQUIRED" in r.data
    assert db.session.query(Inspection).count() == 0

    # 2) every criterion must be scored
    data2 = dict(data, explanation_3="Equipment broken")
    del data2["score_4"]
    r = client.post("/inspections/submit", data=data2, follow_redirects=True)
    assert b"Criterion 4 is missing" in r.data

    # 3) valid submission with explanation
    data = {"_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
            "score_1": "5", "score_2": "4", "score_3": "2",
            "explanation_3": "Two suction machines not working in triage.",
            "score_4": "4", "score_5": "5"}
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    assert r.status_code == 200

    insp = db.session.query(Inspection).first()
    assert insp is not None
    assert insp.status == "SUBMITTED"
    assert insp.total_score == 20
    assert insp.percent == 80.0
    assert insp.rating == "GOOD"
    assert insp.ref.startswith("TEST-INS-")

    # 4) PDF generated and archived in DURABLE storage (survives restarts)
    from app import storage
    assert insp.pdf_path and storage.exists(insp.pdf_path)
    assert len(storage.get(insp.pdf_path)) > 1500

    # 5) WhatsApp report queued to MD/CEO and delivered (sandbox) — normalized to +234
    wa = db.session.query(WhatsAppMessage).filter_by(kind="report").first()
    assert wa is not None
    assert "8000000001" in wa.to_number
    assert wa.status == "DELIVERED"
    assert wa.media_path == insp.pdf_path

    # 6) MD received in-app notification; audit trail recorded & chain intact
    n = db.session.query(AppNotification).filter_by(template_key="inspection_submitted").first()
    assert n is not None and n.user_id == seeded["md"]
    ok, rows = verify_chain(seeded["org"])
    assert ok and rows > 0

    # 7) duplicate submission blocked
    r = client.post("/inspections/submit", data=dict(data, _csrf=csrf(client, "/inspections/new")),
                    follow_redirects=True)
    assert b"already submitted" in r.data
    assert db.session.query(Inspection).count() == 1

    # 8) verification page
    r = client.get(f"/verify/{insp.verify_code}")
    assert r.status_code == 200 and b"verified" in r.data
    r = client.get("/verify/WRONGCODE1")
    assert r.status_code == 404


def test_score_1_also_requires_explanation(client, seeded):
    login(client, "am1")
    data = {"_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
            "score_1": "1", "score_2": "5", "score_3": "5", "score_4": "5", "score_5": "5"}
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    assert b"explanation is REQUIRED" in r.data


def test_scores_3_to_5_need_no_explanation(client, seeded):
    login(client, "am1")
    data = {"_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
            "score_1": "3", "score_2": "3", "score_3": "3", "score_4": "3", "score_5": "3"}
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    assert r.status_code == 200
    insp = db.session.query(Inspection).first()
    assert insp.total_score == 15 and insp.rating == "FAIR / NEEDS IMPROVEMENT"


def test_only_duty_admin_manager_submits(client, seeded):
    login(client, "am2")  # am1 is on duty today
    data = {"_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
            **{f"score_{n}": "4" for n in range(1, 6)}}
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    # v1.7.18: off-duty AM gets 403 or message about assigned to on-duty AM
    assert r.status_code in (403, 200)
    if r.status_code == 200:
        assert b"Alice Manager" in r.data  # told who is responsible
    assert db.session.query(Inspection).count() == 0


def test_offline_json_sync_submission(client, seeded):
    login(client, "am1")
    token = csrf(client, "/inspections/new")
    payload = {"department_id": seeded["dept"],
               **{f"score_{n}": 4 for n in range(1, 6)},
               "lat": 6.5244, "lng": 3.3792}
    r = client.post("/inspections/submit", json=payload, headers={"X-CSRF-Token": token})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    insp = db.session.query(Inspection).first()
    assert insp.gps_captured is True

    # missing explanation via JSON -> 422 JSON error
    payload2 = dict(payload, score_1=2)
    r = client.post("/inspections/submit", json=payload2, headers={"X-CSRF-Token": csrf(client, "/")})
    assert r.status_code in (409, 422)  # duplicate first (already submitted today)


# ================================================================ COMPLAINT E2E
def test_complaint_flow_routing_and_escalation(client, seeded, app):
    # 1) public portal opens WITHOUT login
    r = client.get("/complaint")
    assert r.status_code == 200 and b"Visitor Portal" in r.data

    # 2) validation errors
    r = client.post("/complaint/submit", data={"consent": "1", "_csrf": csrf(client, "/complaint"),
                                               "department_id": "", "category": "",
                                               "description": "short", "phone": "abc"},
                    follow_redirects=True)
    assert b"select the department" in r.data

    # 3) valid submission — no account needed
    token = csrf(client, "/complaint")
    r = client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": token, "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "We have been waiting for over four hours at triage without any update.",
        "phone": "08012345678", "contact_method": "whatsapp"}, follow_redirects=True)
    assert b"has been received" in r.data
    c = db.session.query(Complaint).first()
    assert c.ref.startswith("TEST-CMP-")
    assert c.status == "NEW"
    delta = c.sla_deadline_at - c.submitted_at
    assert timedelta(hours=23, minutes=59) <= delta <= timedelta(hours=24, minutes=1)

    # 4) routed to Admin Manager on duty AND the department HOD
    notes = db.session.query(AppNotification).filter(
        AppNotification.template_key.in_(("complaint_new_admin", "complaint_new_hod"))).all()
    recipients = {n.user_id for n in notes}
    assert seeded["am"] in recipients      # AM on duty
    assert seeded["hod"] in recipients     # HOD of Emergency
    wa = db.session.query(WhatsAppMessage).all()
    assert any("8000000003" in m.to_number for m in wa)  # HOD WhatsApp normalized

    # 5) status check with reference + phone
    r = client.get(f"/complaint/status?ref={c.ref}&phone=08012345678")
    assert c.ref.encode() in r.data

    # 6) HOD acknowledges within SLA
    login(client, "hod1")
    r = client.post(f"/complaints/{c.id}/update",
                    data={"_csrf": csrf(client, f"/complaints/{c.id}"), "action_type": "acknowledge"},
                    follow_redirects=True)
    assert db.session.get(Complaint, c.id).status == "ACKNOWLEDGED"

    # 7) simulate SLA expiry -> scheduler escalates to MD/CEO
    with app.app_context():
        c2 = db.session.get(Complaint, c.id)
        c2.sla_deadline_at = now_naive() - timedelta(hours=1)
        db.session.commit()
    from app.scheduler import tick
    tick(app)
    with app.app_context():
        c3 = db.session.get(Complaint, c.id)
        assert c3.escalated is True
        assert c3.status == "ESCALATED"
        esc_note = db.session.query(AppNotification).filter_by(template_key="complaint_escalated").all()
        assert any(n.user_id == seeded["md"] for n in esc_note)
        # escalation recorded in audit
        from app.models import AuditLog
        log = db.session.query(AuditLog).filter_by(action="COMPLAINT_ESCALATED").first()
        assert log is not None

    # 8) escalation is idempotent (second tick does not re-escalate)
    before = db.session.query(AppNotification).filter_by(template_key="complaint_escalated").count()
    tick(app)
    after = db.session.query(AppNotification).filter_by(template_key="complaint_escalated").count()
    assert before == after


def test_resolved_complaint_never_escalated(client, seeded, app):
    token = csrf(client, "/complaint")
    client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": token, "department_id": seeded["dept"], "category": "Billing / charges",
        "description": "I was charged twice for the same laboratory test yesterday.",
        "phone": "08098765432"}, follow_redirects=True)
    c = db.session.query(Complaint).first()
    login(client, "hod1")
    tok = csrf(client, f"/complaints/{c.id}")
    client.post(f"/complaints/{c.id}/update",
                data={"_csrf": tok, "action_type": "resolve",
                      "resolution_notes": "Refund processed and confirmed with patient."})
    with app.app_context():
        c2 = db.session.get(Complaint, c.id)
        c2.sla_deadline_at = now_naive() - timedelta(hours=5)
        db.session.commit()
    from app.scheduler import tick
    tick(app)
    c3 = db.session.get(Complaint, c.id)
    assert c3.escalated is False and c3.status == "RESOLVED"


# ================================================================ ROSTER & REMINDERS
def test_roster_upload_validation_preview_and_confirm(client, seeded):
    """Upload to the hospital-wide Admin Manager roster: preview, then commit."""
    login(client, "admin")
    today = now_naive().date()
    csv_content = (
        "Name,Date\n"
        f"Alice Manager,{today + timedelta(days=5)}\n"      # valid
        f"Nobody Here,{today + timedelta(days=6)}\n"        # unknown user
        f"Alice Manager,{today}\n"                          # already rostered
        f"Bob Manager,not-a-date\n"                          # invalid date
        f",{today + timedelta(days=7)}\n"                   # missing name
    )
    r = client.post("/roster/upload",
                    data={"_csrf": csrf(client, "/roster"), "scope": "ORG",
                          "file": (io.BytesIO(csv_content.encode()), "roster.csv")},
                    content_type="multipart/form-data", follow_redirects=True)
    body = r.data.decode()
    assert "No active staff account matches" in body
    assert "already has an Admin Manager on duty" in body
    assert "Cannot read the date" in body
    assert "No staff name on this line" in body
    token = body.split('name="token" value="')[1].split('"')[0]

    before = db.session.query(DutyRoster).count()
    client.post("/roster/upload/confirm",
                data={"_csrf": csrf(client, "/roster"), "token": token},
                follow_redirects=True)
    assert db.session.query(DutyRoster).count() == before + 1  # only the valid row


def test_roster_duplicate_date_blocked(client, seeded):
    login(client, "admin")
    today = now_naive().date()
    r = client.post("/roster/manual", data={"_csrf": csrf(client, "/roster"),
                                            "date": today.isoformat(),
                                            "user_id": seeded["am2"]},
                    follow_redirects=True)
    assert b"already exists" in r.data
    assert db.session.query(DutyRoster).filter_by(duty_date=today).count() == 1


def test_reminders_generated_once_at_configured_times(app, seeded):
    with app.app_context():
        services.set_setting(seeded["org"], "reminder_day_before_time", "00:00")
        services.set_setting(seeded["org"], "reminder_duty_day_time", "00:00")
        db.session.commit()
    from app.scheduler import tick
    tick(app)
    with app.app_context():
        before = db.session.query(AppNotification).filter(
            AppNotification.template_key.in_(("duty_reminder_day_before", "duty_reminder_day_of"))).count()
        assert before >= 2  # day-of for am1, day-before for am2
        # idempotent: no duplicates on the next pass
    tick(app)
    with app.app_context():
        after = db.session.query(AppNotification).filter(
            AppNotification.template_key.in_(("duty_reminder_day_before", "duty_reminder_day_of"))).count()
        assert after == before


def test_overdue_inspection_flags_management(app, seeded):
    with app.app_context():
        services.set_setting(seeded["org"], "inspection_deadline_time", "00:00")
        services.set_setting(seeded["org"], "overdue_notify_time", "00:00")
        db.session.commit()
    from app.scheduler import tick
    tick(app)
    with app.app_context():
        n = db.session.query(AppNotification).filter_by(template_key="inspection_overdue").all()
        assert n  # AM nudged + management informed


# ================================================================ WHATSAPP
def test_whatsapp_retry_after_failure(app, seeded):
    app.config["WHATSAPP_SIMULATE_FAILURE"] = True
    with app.app_context():
        m = whatsapp.queue_message(seeded["org"], "2348000000099", "hello", kind="alert")
        whatsapp.send_message(m)
        assert m.status in ("QUEUED", "FAILED") and m.attempts == 1
        m2 = db.session.get(WhatsAppMessage, m.id)
        whatsapp.send_message(m2)
        assert m2.status == "DELIVERED"
        assert m2.attempts == 2
    app.config["WHATSAPP_SIMULATE_FAILURE"] = False


# ================================================================ RBAC / SECURITY
def test_rbac_hod_cannot_access_admin_or_inspection(client, seeded):
    login(client, "hod1")
    assert client.get("/admin").status_code == 403
    assert client.get("/admin/settings").status_code == 403
    assert client.get("/inspections/new").status_code == 403
    assert client.get("/complaints").status_code == 200  # HOD can manage complaints


def test_anonymous_access(client, seeded):
    assert client.get("/complaint").status_code == 200          # public portal open
    r = client.get("/inspections")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.get("/admin").status_code == 302


def test_bad_login_rate_limited_or_rejected(client, seeded):
    for _ in range(3):
        r = client.post("/login", data={"_csrf": csrf(client, "/login"),
                                        "username": "am1", "password": "wrong"})
        assert r.status_code in (401, 429)
    assert db.session.query(User).filter_by(username="am1").first().last_login_at is None


def test_csrf_required(client, seeded):
    login(client, "am1")
    r = client.post("/inspections/submit", data={"department_id": seeded["dept"]})
    assert r.status_code == 403


def test_audit_chain_tamper_evidence(app, seeded):
    with app.app_context():
        from app.audit import audit
        audit("TEST_ACTION", "test", 1, {"x": 1}, org_id=seeded["org"])
        db.session.commit()
        ok, rows = verify_chain(seeded["org"])
        assert ok and rows >= 1
        from app.models import AuditLog
        row = db.session.query(AuditLog).first()
        row.detail = '{"tampered": true}'
        db.session.commit()
        ok2, _ = verify_chain(seeded["org"])
        assert ok2 is False


# ================================================================ USSD API
def test_ussd_intake_requires_secret_and_creates_complaint(client, seeded):
    r = client.post("/api/v1/ussd/complaint", json={
        "secret": "wrong", "hospital_code": "TEST", "department": "Emergency",
        "category": "Other", "description": "USSD complaint text", "phone": "08011112222"})
    assert r.status_code == 401
    r = client.post("/api/v1/ussd/complaint", json={
        "secret": "ussd-test-secret", "hospital_code": "TEST", "department": "Emergency",
        "category": "Other", "description": "USSD complaint text from phone",
        "phone": "08011112222"})
    assert r.status_code == 200
    assert r.get_json()["ref"].startswith("TEST-CMP-")
    assert db.session.query(Complaint).first().source == "ussd"
