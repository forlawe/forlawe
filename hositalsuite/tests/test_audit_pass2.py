"""Audit pass 2: tests for flows that previously had no coverage —
forced password change, controlled amendments, SLA extension audit, roster ops."""
from datetime import timedelta

from app.models import (AuditLog, Complaint, DutyRoster, Inspection, User, db,
                        now_naive)

from conftest import csrf, login


# ------------------------------------------------------------------ password policy
def test_temporary_password_blocks_app_until_changed(app, client, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(username="hod1").first()
        u.must_change_password = True
        db.session.commit()

    login(client, "hod1")
    # forced to change-password screen; normal pages redirect there
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/change-password" in r.headers["Location"]
    r = client.get("/complaints", follow_redirects=False)
    assert "/change-password" in r.headers["Location"]

    # wrong current password rejected
    tok = csrf(client, "/change-password")
    r = client.post("/change-password", data={"_csrf": tok, "current_password": "WRONG",
                                              "new_password": "NewPassw0rd!x",
                                              "confirm_password": "NewPassw0rd!x"})
    assert r.status_code == 401

    # weak password rejected
    r = client.post("/change-password", data={"_csrf": csrf(client, "/change-password"),
                                              "current_password": "Passw0rd!x",
                                              "new_password": "short",
                                              "confirm_password": "short"})
    assert r.status_code == 422

    # same as old rejected
    r = client.post("/change-password", data={"_csrf": csrf(client, "/change-password"),
                                              "current_password": "Passw0rd!x",
                                              "new_password": "Passw0rd!x",
                                              "confirm_password": "Passw0rd!x"})
    assert r.status_code == 422

    # valid change unlocks the app
    r = client.post("/change-password", data={"_csrf": csrf(client, "/change-password"),
                                              "current_password": "Passw0rd!x",
                                              "new_password": "BrandNew#9x",
                                              "confirm_password": "BrandNew#9x"},
                    follow_redirects=False)
    # staff land on their dashboard ("/" is now the patient hub)
    assert r.status_code == 302 and r.headers["Location"].endswith("/dashboard")
    assert client.get("/complaints").status_code == 200
    with app.app_context():
        u = db.session.query(User).filter_by(username="hod1").first()
        assert u.must_change_password is False
        log = db.session.query(AuditLog).filter_by(action="PASSWORD_CHANGED").first()
        assert log is not None


# ------------------------------------------------------------------ amendment process
def test_inspection_amendment_preserves_original(client, seeded):
    login(client, "am1")
    tok = csrf(client, "/inspections/new")
    client.post("/inspections/submit", data={
        "_csrf": tok, "department_id": seeded["dept"],
        "score_1": "4", "score_2": "4", "score_3": "4", "score_4": "4", "score_5": "4"},
        follow_redirects=True)
    insp = db.session.query(Inspection).first()
    assert insp.total_score == 20

    # amendment without reason is rejected
    r = client.post(f"/inspections/{insp.id}/amend",
                    data={"_csrf": csrf(client, f"/inspections/{insp.id}"),
                          **{f"score_{n}": "5" for n in range(1, 6)}},
                    follow_redirects=True)
    assert b"reason is required" in r.data

    # amendment requires explanations for new low scores
    r = client.post(f"/inspections/{insp.id}/amend",
                    data={"_csrf": csrf(client, f"/inspections/{insp.id}"), "reason": "typo",
                          "score_1": "1", **{f"score_{n}": "5" for n in range(2, 6)}},
                    follow_redirects=True)
    assert b"Explanation required" in r.data

    # valid amendment: original preserved as SUPERSEDED copy
    r = client.post(f"/inspections/{insp.id}/amend",
                    data={"_csrf": csrf(client, f"/inspections/{insp.id}"),
                          "reason": "Wrong department selected initially",
                          **{f"score_{n}": "5" for n in range(1, 6)}},
                    follow_redirects=True)
    assert r.status_code == 200
    live = db.session.get(Inspection, insp.id)
    assert live.total_score == 25 and live.rating == "EXCELLENT"
    superseded = db.session.query(Inspection).filter_by(status="SUPERSEDED").first()
    assert superseded is not None and superseded.total_score == 20
    log = db.session.query(AuditLog).filter_by(action="INSPECTION_AMENDED").first()
    assert log is not None and "Wrong department" in log.detail


def test_hod_cannot_amend_inspection(client, seeded):
    login(client, "am1")
    tok = csrf(client, "/inspections/new")
    client.post("/inspections/submit", data={
        "_csrf": tok, "department_id": seeded["dept"],
        **{f"score_{n}": "4" for n in range(1, 6)}}, follow_redirects=True)
    insp = db.session.query(Inspection).first()
    login(client, "hod1")
    assert client.post(f"/inspections/{insp.id}/amend",
                       data={"_csrf": csrf(client, f"/inspections/{insp.id}")}).status_code == 403


# ------------------------------------------------------------------ SLA extension
def test_sla_extension_is_audit_logged_and_hod_cannot_extend(client, seeded):
    tok = csrf(client, "/complaint")
    client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": tok, "department_id": seeded["dept"], "category": "Billing / charges",
        "description": "Double charged for a laboratory test yesterday.",
        "phone": "08066667777", "idem": "sla-ext-1"}, follow_redirects=True)
    c = db.session.query(Complaint).first()
    old_deadline = c.sla_deadline_at

    # HOD cannot extend SLA
    login(client, "hod1")
    r = client.post(f"/complaints/{c.id}/extend-sla",
                    data={"_csrf": csrf(client, f"/complaints/{c.id}"), "hours": "12",
                          "reason": "need more time"})
    assert r.status_code == 403

    # MD can, with audit trail
    login(client, "md")
    r = client.post(f"/complaints/{c.id}/extend-sla",
                    data={"_csrf": csrf(client, f"/complaints/{c.id}"), "hours": "12",
                          "reason": "Investigation requires lab records"},
                    follow_redirects=True)
    assert b"extension has been recorded" in r.data
    c2 = db.session.get(Complaint, c.id)
    assert c2.sla_deadline_at > old_deadline and c2.sla_extended_at is not None
    log = db.session.query(AuditLog).filter_by(action="COMPLAINT_SLA_EXTENDED").first()
    assert log is not None and "Investigation requires lab records" in log.detail

    # invalid extension rejected
    r = client.post(f"/complaints/{c.id}/extend-sla",
                    data={"_csrf": csrf(client, f"/complaints/{c.id}"), "hours": "500",
                          "reason": "x"}, follow_redirects=True)
    assert b"valid extension" in r.data


# ------------------------------------------------------------------ roster management
def test_roster_reassign_and_delete_are_audited(client, seeded):
    login(client, "admin")
    today = now_naive().date()
    entry = db.session.query(DutyRoster).filter_by(duty_date=today + timedelta(days=1)).first()
    assert entry.user_id == seeded["am2"]

    tok = csrf(client, "/roster")
    client.post(f"/roster/{entry.id}/reassign", data={"_csrf": tok, "user_id": seeded["am"]},
                follow_redirects=True)
    assert db.session.get(DutyRoster, entry.id).user_id == seeded["am"]
    log = db.session.query(AuditLog).filter_by(action="ROSTER_REASSIGNED").first()
    assert log is not None

    client.post(f"/roster/{entry.id}/delete", data={"_csrf": csrf(client, "/roster")},
                follow_redirects=True)
    assert db.session.get(DutyRoster, entry.id) is None
    assert db.session.query(AuditLog).filter_by(action="ROSTER_DELETED").first() is not None

    # non-super-admin cannot manage roster entries
    login(client, "am1")
    assert client.post(f"/roster/{seeded['am']}/delete",
                       data={"_csrf": csrf(client, "/roster")}).status_code == 403


# ------------------------------------------------------------------ concurrency hardening
def test_sqlite_wal_enabled(app):
    """SQLite must run in WAL mode. PRAGMA is meaningless on PostgreSQL, so on a
    real PostgreSQL run this asserts the connection works instead of blowing up
    with `syntax error at or near "PRAGMA"`."""
    with app.app_context():
        if not str(db.engine.url).startswith("sqlite"):
            assert db.session.execute(db.text("SELECT 1")).scalar() == 1
            return
        mode = db.session.execute(db.text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() in ("wal", "memory"), mode
