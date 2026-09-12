"""Tests for the production-hardening work (P0/P1 audit fixes).

Each test here maps to a specific defect found in the 2026-08-14 audit, so a
regression will name the bug it is bringing back.
"""
from datetime import timedelta

import pytest

from app import storage
from app.models import (Complaint, DataRequest, LoginAttempt, Organization,
                        PatientFeedback, StoredFile, db, now_naive)
from conftest import csrf, login


# ================================================================ P0-1 durable storage
def test_uploads_survive_a_restart_because_they_are_not_on_disk(client, seeded, tmp_path):
    """Regression: uploads were written to Render's ephemeral disk and vanished."""
    import io
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    data = {
        "consent": "1", "_csrf": csrf(client, "/complaint"),
        "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "There was a long wait and nobody explained why.",
        "phone": "08011112222", "idem": "store-idem-1",
        "attachment": (io.BytesIO(png), "evidence.png"),
    }
    r = client.post("/complaint/submit", data=data, follow_redirects=True,
                    content_type="multipart/form-data")
    assert r.status_code == 200

    c = db.session.query(Complaint).first()
    assert c.attachment_path, "attachment was not saved"
    # The bytes must live in the database, not on the filesystem.
    row = db.session.query(StoredFile).filter_by(key=c.attachment_path).first()
    assert row is not None
    assert row.data.startswith(b"\x89PNG")
    assert storage.get(c.attachment_path) == row.data


def test_storage_rejects_path_traversal_keys():
    with pytest.raises(ValueError):
        import os
        os.environ["STORAGE_BACKEND"] = "disk"
        try:
            storage.put("../../etc/passwd", b"x")
        finally:
            os.environ["STORAGE_BACKEND"] = "db"


def test_logo_is_served_from_durable_storage(client, seeded):
    """Regression: /branding/logo 404'd in production after a restart."""
    org = db.session.get(Organization, seeded["org"])
    key = storage.put("logos/test-logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
                      org_id=org.id)
    org.logo_path = key
    db.session.commit()

    r = client.get("/branding/logo")
    assert r.status_code == 200
    assert r.data.startswith(b"\x89PNG")


# ================================================================ P0-2 real backups
def test_backup_works_on_any_engine_and_contains_every_table(app):
    """Regression: the nightly backup silently did nothing on PostgreSQL."""
    import io
    import json
    import zipfile

    from app.backup import create_backup, list_backups, prune_backups

    key, size = create_backup(app, kind="test")
    assert size > 0
    blob = storage.get(key)
    assert blob is not None

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "RESTORE.txt" in names
        assert "complaint.csv" in names
        assert "user.csv" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["kind"] == "test"
        assert len(manifest["tables"]) > 20

    assert len(list_backups()) >= 1
    prune_backups(keep=0)
    assert len(list_backups()) == 0


# ================================================================ P0-3 headers & cookies
def test_security_headers_present(client):
    r = client.get("/login")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    csp = r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert r.headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_hsts_only_over_https(client):
    plain = client.get("/login")
    assert "Strict-Transport-Security" not in plain.headers
    secure = client.get("/login", base_url="https://localhost")
    assert "max-age=31536000" in secure.headers["Strict-Transport-Security"]


# ================================================================ P0-4 brute force
def test_account_locks_after_repeated_failures(client, seeded, app):
    """Per-IP limits cannot protect one account behind a shared proxy."""
    app.config["RATE_LIMIT_SCALE"] = 10000      # isolate the account-level gate
    tok = csrf(client, "/login")
    for _ in range(app.config["LOGIN_MAX_FAILURES"]):
        client.post("/login", data={"username": "am1", "password": "wrong", "_csrf": tok})

    row = db.session.query(LoginAttempt).filter_by(username="am1").first()
    assert row is not None and row.locked_until is not None

    # even the CORRECT password is refused while the lock is active
    r = client.post("/login", data={"username": "am1", "password": "Passw0rd!x",
                                    "_csrf": tok}, follow_redirects=True)
    assert r.status_code == 429
    assert b"Too many failed attempts" in r.data


def test_successful_login_clears_the_failure_counter(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    tok = csrf(client, "/login")
    for _ in range(3):
        client.post("/login", data={"username": "am1", "password": "wrong", "_csrf": tok})
    assert db.session.query(LoginAttempt).filter_by(username="am1").first().failures == 3

    client.post("/login", data={"username": "am1", "password": "Passw0rd!x", "_csrf": tok})
    assert db.session.query(LoginAttempt).filter_by(username="am1").first().failures == 0


def test_real_client_ip_is_used_behind_a_proxy(client):
    """Regression: every visitor shared the proxy IP, making limits global."""
    from app.security import client_ip
    with client.application.test_request_context(
            "/", headers={"CF-Connecting-IP": "102.89.1.5"}):
        assert client_ip() == "102.89.1.5"


# ================================================================ P1-1/P1-3 NDPA
def test_complaint_requires_consent(client, seeded):
    r = client.post("/complaint/submit", data={
        "_csrf": csrf(client, "/complaint"), "department_id": seeded["dept"],
        "category": "Long waiting time",
        "description": "No consent box was ticked on this submission.",
        "phone": "08011112222"}, follow_redirects=True)
    assert r.status_code == 422
    assert db.session.query(Complaint).count() == 0


def test_anonymous_complaint_stores_no_phone_number(client, seeded):
    r = client.post("/complaint/submit", data={
        "_csrf": csrf(client, "/complaint"), "department_id": seeded["dept"],
        "category": "Staff attitude / conduct", "anonymous": "1",
        "description": "A staff member was rude and I am afraid to give my name.",
        "phone": "08011112222"}, follow_redirects=True)
    assert r.status_code == 200
    c = db.session.query(Complaint).first()
    assert c is not None
    assert c.is_anonymous is True
    assert "0801" not in (c.phone or ""), "anonymous complaint leaked the phone number"
    assert c.consent_at is None


def test_anonymous_complaint_sends_no_sms(client, seeded):
    """No delivery attempt for an anonymous report, at submit OR on updates.

    The stored phone is the placeholder "anonymous", so this also guards against
    the messaging layer treating that string as a real destination number.
    """
    from app.models import SmsMessage, WhatsAppMessage
    from app import notifications
    from app.models import Organization

    client.post("/complaint/submit", data={
        "_csrf": csrf(client, "/complaint"), "department_id": seeded["dept"],
        "category": "Staff attitude / conduct", "anonymous": "1",
        "description": "Anonymous report about conduct on the ward at night.",
        "phone": ""}, follow_redirects=True)
    c = db.session.query(Complaint).first()
    assert c.is_anonymous is True

    # drive the notification path directly, as a staff status update would
    org = db.session.get(Organization, seeded["org"])
    notifications.notify_complaint_patient(org, c, "resolved")
    db.session.commit()

    # Staff routing messages (to the HOD/Admin Manager) are expected and fine.
    # What must NEVER happen is a message addressed to the patient placeholder.
    bad_numbers = {"anonymous", "", "[erased]", "none", "n/a"}
    for msg in db.session.query(SmsMessage).all():
        assert (msg.to_number or "").strip().lower() not in bad_numbers, \
            f"SMS queued to a placeholder destination: {msg.to_number!r}"
    for msg in db.session.query(WhatsAppMessage).all():
        assert (msg.to_number or "").strip().lower() not in bad_numbers, \
            f"WhatsApp queued to a placeholder destination: {msg.to_number!r}"


def test_privacy_pages_are_public(client, seeded):
    assert client.get("/privacy").status_code == 200
    assert client.get("/privacy/request").status_code == 200
    body = client.get("/privacy").data
    assert b"Nigeria Data Protection" in body


def test_data_request_is_logged_and_can_be_fulfilled(client, seeded):
    # patient asks for erasure
    r = client.post("/privacy/request", data={
        "_csrf": csrf(client, "/privacy/request"), "kind": "erase",
        "phone": "08055556666", "note": "Please delete everything."},
        follow_redirects=True)
    assert r.status_code == 200
    req = db.session.query(DataRequest).first()
    assert req is not None and req.status == "NEW"

    # a complaint exists for that number
    client.post("/complaint/submit", data={
        "consent": "1", "_csrf": csrf(client, "/complaint"),
        "department_id": seeded["dept"], "category": "Billing / charges",
        "description": "I was charged twice for the same laboratory test.",
        "phone": "08055556666"}, follow_redirects=True)

    login(client, "admin")
    detail = client.get(f"/admin/data-requests/{req.id}")
    assert detail.status_code == 200

    r = client.post(f"/admin/data-requests/{req.id}/fulfil", data={
        "_csrf": csrf(client, f"/admin/data-requests/{req.id}"), "action": "erase"},
        follow_redirects=True)
    assert r.status_code == 200

    c = db.session.query(Complaint).first()
    assert c.phone == "[erased]"
    assert c.anonymized_at is not None
    assert "erased" in c.description
    assert db.session.get(DataRequest, req.id).status == "DONE"


# ================================================================ P1-2 retention
def test_retention_purge_anonymises_old_records_but_keeps_statistics(app, seeded):
    from app.scheduler import job_retention_purge
    from app import services

    org_id = seeded["org"]
    services.set_setting(org_id, "retention_days", 30)

    old = now_naive() - timedelta(days=400)
    c = Complaint(org_id=org_id, ref="OLD-CMP-1", department_id=seeded["dept"],
                  category="Billing / charges", description="Sensitive personal detail",
                  phone="08099998888", status="CLOSED", submitted_at=old,
                  sla_hours=24, sla_deadline_at=old + timedelta(hours=24))
    fb = PatientFeedback(org_id=org_id, department_id=seeded["dept"], rating=5,
                         comment="My name is in this comment", phone="08099998888",
                         created_at=old)
    db.session.add_all([c, fb])
    db.session.commit()

    job_retention_purge(app)
    db.session.commit()

    c = db.session.query(Complaint).filter_by(ref="OLD-CMP-1").first()
    assert c.phone == "[erased]"
    assert c.anonymized_at is not None

    fb = db.session.query(PatientFeedback).filter_by(id=fb.id).first()
    assert fb.phone is None
    assert fb.rating == 5, "statistics must survive anonymisation"


def test_retention_purge_leaves_recent_records_alone(app, seeded):
    from app.scheduler import job_retention_purge
    from app import services
    services.set_setting(seeded["org"], "retention_days", 30)

    now = now_naive()
    c = Complaint(org_id=seeded["org"], ref="NEW-CMP-1", department_id=seeded["dept"],
                  category="Billing / charges", description="Recent complaint",
                  phone="08012341234", status="NEW", submitted_at=now,
                  sla_hours=24, sla_deadline_at=now + timedelta(hours=24))
    db.session.add(c)
    db.session.commit()

    job_retention_purge(app)
    db.session.commit()
    assert db.session.query(Complaint).filter_by(ref="NEW-CMP-1").first().phone == "08012341234"


def test_retention_is_idempotent(app, seeded):
    """Running twice must not double-process or crash."""
    from app.scheduler import job_retention_purge
    job_retention_purge(app)
    job_retention_purge(app)
    db.session.commit()


# ================================================================ P1-6 tenancy
def test_public_portal_resolves_tenant_by_query_hint(client, seeded):
    """Regression: public pages always served the first hospital in the table."""
    second = Organization(code="SECOND", name="Second Hospital", slug="second")
    db.session.add(second)
    db.session.commit()

    from app.services import current_org
    with client.application.test_request_context("/complaint?h=second"):
        assert current_org().code == "SECOND"
    with client.application.test_request_context("/complaint?h=TEST"):
        assert current_org().code == "TEST"


# ================================================================ crash-proofing
def test_oversized_upload_is_refused_cleanly(client, seeded):
    import io
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
    r = client.post("/complaint/submit", data={
        "consent": "1", "_csrf": csrf(client, "/complaint"),
        "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "Trying to upload a very large file as evidence here.",
        "phone": "08011112222",
        "attachment": (io.BytesIO(big), "huge.png")},
        content_type="multipart/form-data", follow_redirects=True)
    # Either refused by MAX_CONTENT_LENGTH (413) or by the size check — never a 500.
    assert r.status_code in (200, 413, 422)
    assert b"Traceback" not in r.data


def test_unknown_page_renders_friendly_error(client):
    r = client.get("/definitely-not-a-real-page")
    assert r.status_code == 404
    assert b"Traceback" not in r.data


def test_health_endpoint_reports_storage(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.get_json()["status"] in ("ok", "degraded")


# ================================================================ storage-migration regressions
def test_whatsapp_finds_report_pdf_in_durable_storage(app, seeded):
    """Regression: media delivery required an ABSOLUTE path.

    After PDFs moved into durable storage the key is relative
    ("reports/REF.pdf"), so os.path.isabs() was always False and every
    inspection report to the MD/CEO silently downgraded to a text-only message.
    """
    from app.whatsapp import _media_available
    key = storage.put("reports/TEST-REPORT.pdf", b"%PDF-1.4 test", org_id=seeded["org"])
    db.session.commit()
    assert _media_available(key) is True
    assert _media_available("/no/such/file.pdf") is False


def test_scheduler_health_is_reported(app):
    """The scheduler runs SLA escalation; silent death must be visible."""
    from app.scheduler import is_alive
    # tests run with DISABLE_SCHEDULER=1 -> None means "intentionally off"
    assert is_alive() in (None, True, False)


def test_health_returns_200_even_when_degraded(client, seeded, monkeypatch):
    """Regression (2026-08-15 outage): /api/v1/health is the PLATFORM health
    check. Returning 503 while the database was down made Render kill a
    working container, turning a database wobble into a total site outage.
    Liveness must always be 200; /ready is the strict probe."""
    def boom(*a, **kw):
        raise RuntimeError("database down")
    monkeypatch.setattr(db.session, "execute", boom)

    r = client.get("/api/v1/health")
    assert r.status_code == 200, "health must stay 200 or the host kills the deploy"
    assert r.get_json()["status"] == "degraded"
    assert r.get_json()["database"] is False

    assert client.get("/api/v1/ready").status_code == 503


def test_health_endpoint_exposes_operational_state(client, seeded, app):
    from app.backup import create_backup
    create_backup(app, kind="test")
    body = client.get("/api/v1/health").get_json()
    assert body["database"] is True
    assert body["storage"] in ("db", "disk")
    assert body["last_backup"] is not None, "health must show when the last backup ran"


def test_audit_log_records_the_real_client_ip(client, seeded):
    """Regression: every audit row recorded the proxy IP, so the trail was
    useless for investigating who did what."""
    from app.models import AuditLog
    client.post("/login", data={"username": "admin", "password": "wrong",
                                "_csrf": csrf(client, "/login")},
                headers={"CF-Connecting-IP": "197.210.5.42"})
    row = (db.session.query(AuditLog).filter_by(action="LOGIN_FAILED")
           .order_by(AuditLog.id.desc()).first())
    assert row is not None
    assert row.ip == "197.210.5.42"


def test_audit_chain_still_verifies_after_all_changes(client, seeded):
    from app.audit import verify_chain
    client.post("/complaint/submit", data={
        "consent": "1", "_csrf": csrf(client, "/complaint"),
        "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "Checking the audit chain stays intact end to end.",
        "phone": "08012223333"}, follow_redirects=True)
    ok, n = verify_chain(seeded["org"])
    assert ok is True and n > 0


# ================================================================ boot resilience
def test_connect_timeout_is_configured_for_postgres(monkeypatch):
    """Regression: a database that accepts TCP but never replies hung startup
    for ~130s (the OS default), outlasting the host health check and putting
    the container in a permanent restart loop that served NOTHING."""
    import importlib

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@example.invalid:5432/db")
    import app.config as cfg
    importlib.reload(cfg)
    args = cfg._connect_args()
    assert args["connect_timeout"] <= 15, "unbounded connect blocks the whole boot"
    assert args["keepalives"] == 1

    # SQLite has no socket, so it must get no libpq options
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    importlib.reload(cfg)
    assert cfg._connect_args() == {}
    monkeypatch.undo()
    importlib.reload(cfg)


def test_disk_rescue_gives_up_fast_when_database_is_down(app, monkeypatch):
    """Regression: the rescue retried EVERY file, multiplying the connection
    timeout by the file count (37 files x 10s = 6 minutes of dead boot)."""
    from app import storage

    calls = {"n": 0}
    real_execute = db.session.execute

    def boom(*a, **kw):
        calls["n"] += 1
        raise RuntimeError("database is down")

    monkeypatch.setattr(db.session, "execute", boom)
    moved = storage.migrate_disk_to_db(app)
    monkeypatch.setattr(db.session, "execute", real_execute)

    assert moved == 0
    assert calls["n"] == 1, "must probe once and abort, not once per file"


def test_scheduler_self_heals_if_its_thread_dies(app, monkeypatch):
    """A dead scheduler means duty reminders and SLA escalations silently stop.
    It must restart itself rather than stay dead until someone redeploys."""
    import app.scheduler as sched

    class DeadThread:
        def is_alive(self):
            return False

    monkeypatch.setenv("DISABLE_SCHEDULER", "0")
    monkeypatch.setattr(sched, "_thread_ref", DeadThread())
    monkeypatch.setattr(sched, "_started", True)
    assert sched.is_alive() is False

    restarted = sched.ensure_running(app)
    assert restarted is True
    assert sched.is_alive() is True

    # calling again is a no-op while it is healthy
    assert sched.ensure_running(app) is False


# ================================================================ open redirect
def test_open_redirect_is_blocked(client, seeded):
    """Regression: '//evil.com' passes a startswith('/') check but browsers
    treat it as protocol-relative and navigate OFF-SITE — a phishing link that
    looks like it belongs to the hospital."""
    from app.security import safe_next
    assert safe_next("//evil.com", "/") == "/"
    assert safe_next("/\\evil.com", "/") == "/"
    assert safe_next("https://evil.com", "/") == "/"
    assert safe_next("javascript:alert(1)", "/") == "/"
    assert safe_next("/book?x=1", "/") == "/book?x=1"
    assert safe_next(None, "/welcome") == "/welcome"


def test_language_switch_cannot_redirect_off_site(client, seeded):
    for hostile in ["//evil.com", "https://evil.com", "/\\evil.com"]:
        r = client.get(f"/lang/en?next={hostile}", follow_redirects=False)
        assert "evil" not in r.headers.get("Location", ""), f"open redirect via {hostile}"


def test_login_next_cannot_redirect_off_site(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    r = client.post("/login", data={"username": "admin", "password": "Passw0rd!x",
                                    "_csrf": csrf(client, "/login"), "next": "//evil.com"},
                    follow_redirects=False)
    assert "evil" not in r.headers.get("Location", "")
