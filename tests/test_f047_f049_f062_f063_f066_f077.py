"""Guards for the Phase-2/3 security findings fixed in this rebuild batch:

  F-062  login must burn the same hashing time for unknown and known users
  F-063  LoginAttempt rows are purged when stale (never grows forever)
  F-077  USSD rate limits key to the caller/session, not the shared gateway IP
  F-049  USSD status lookup requires the caller's own phone, even for today
  F-066  booking thank-you page hides details unless this browser just booked
  F-047  approving leave refuses when the person is already rostered DUTY
"""
from datetime import timedelta

from app.models import (Appointment, Department, LeaveBalance, LeaveRequest,
                        LoginAttempt, Organization, QueueTicket, RosterEntry,
                        User, db, now_naive)
from tests.conftest import csrf, login


def _mk_user(org_id, username, role="STAFF", department_id=None):
    u = User(org_id=org_id, username=username, name=username.title(),
             role=role, department_id=department_id)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


# ================================================================ F-062 login
def test_login_for_unknown_user_still_pays_hash_cost(app, client, seeded, monkeypatch):
    """The scrypt comparison runs even when the username does not exist."""
    import app.views.auth as auth_mod
    calls = {"n": 0}

    def counting_check(hashval, pw):
        calls["n"] += 1
        from werkzeug.security import check_password_hash
        return check_password_hash(hashval, pw)

    monkeypatch.setattr(auth_mod, "check_password_hash", counting_check)
    monkeypatch.setattr(auth_mod.accounts, "find_login_user", lambda *a, **k: None)
    monkeypatch.setattr(auth_mod.accounts, "find_login_user_ambiguous",
                        lambda *a, **k: None)
    tok = csrf(client, "/login")
    r = client.post("/login", data={"_csrf": tok, "username": "no.such.user",
                                    "password": "wrong"}, follow_redirects=False)
    assert r.status_code == 401
    assert calls["n"] == 1, \
        "a non-existent username must still trigger a dummy hash comparison (F-062)"


# ================================================================ F-063 purge
def test_stale_login_attempt_rows_are_purged_but_locked_kept(app):
    from app.scheduler import job_purge_login_attempts
    with app.app_context():
        now = now_naive()
        stale = LoginAttempt(username="olduser", failures=5,
                             last_failure_at=now - timedelta(days=300))
        active = LoginAttempt(username="lockeduser", failures=0,
                              locked_until=now + timedelta(hours=1),
                              last_failure_at=now)
        fresh = LoginAttempt(username="freshuser", failures=1,
                             last_failure_at=now - timedelta(days=2))
        db.session.add_all([stale, active, fresh])
        db.session.commit()
        job_purge_login_attempts(app)
        remaining = {r.username for r in db.session.query(LoginAttempt).all()}
        assert remaining == {"lockeduser", "freshuser"}, \
            f"stale rows must be purged, locked/fresh kept: {remaining}"


# ====================================================== F-077 shared-IP USSD
def test_ussd_rate_limit_keys_to_phone_not_shared_ip(app, client, seeded):
    """50 different callers through ONE gateway IP must not block each other;
    one caller hammering still hits their OWN limit."""
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org_code = db.session.query(Organization).filter_by(id=seeded["org"]).first().code
    dept = db.session.query(Department).filter_by(id=seeded["dept"]).first()
    # 45 different phones, all from the same (test) IP -> all must succeed
    for i in range(45):
        r = client.post("/api/v1/ussd/queue", json={
            "secret": "testsecret123", "hospital_code": org_code,
            "department": dept.name, "name": f"Patient {i}",
            "phone": f"0801000{i:04d}"})
        assert r.status_code == 200, f"caller {i} blocked by shared IP: {r.status_code}"
    # the same phone hammering repeatedly must be limited (per-phone bucket
    # of 20/minute — send 25, so at least the last few must be refused)
    blocked = 0
    for i in range(25):
        r = client.post("/api/v1/ussd/queue", json={
            "secret": "testsecret123", "hospital_code": org_code,
            "department": dept.name, "name": "Hammerer",
            "phone": "08099990000"})
        if r.status_code == 429:
            blocked += 1
    assert blocked >= 1, "repeated calls from ONE phone must eventually be limited"


# ============================================== F-049 USSD status phone check
def test_ussd_status_requires_own_phone_even_for_today(app, client, seeded):
    from tests.conftest import csrf as _csrf  # noqa
    client.application.config["USSD_SHARED_SECRET"] = "testsecret123"
    org = db.session.query(Organization).filter_by(id=seeded["org"]).first()
    dept = db.session.query(Department).filter_by(id=seeded["dept"]).first()
    with app.app_context():
        owner_phone = "+2348012345678"
        ticket = QueueTicket(
            org_id=org.id, code="G-001", access_key="abc" * 8,
            department_id=dept.id, queue_date=now_naive().date(),
            patient_name="Owner", phone=owner_phone, status="WAITING", source="ussd")
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id
    # the OWNER gets the status
    r = client.post("/api/v1/ussd/callback", data={
        "sessionId": "sess-owner", "phoneNumber": owner_phone,
        "text": f"{org.code}*3*G-001"})
    body = r.get_data(as_text=True)
    assert "Ticket G-001" in body and "in line" in body, body
    # a STRANGER on a different phone must NOT resolve today's sequential code
    r2 = client.post("/api/v1/ussd/callback", data={
        "sessionId": "sess-eve", "phoneNumber": "+2348099999999",
        "text": f"{org.code}*3*G-001"})
    body2 = r2.get_data(as_text=True)
    assert "not found" in body2.lower(), body2
    assert "in line" not in body2
    # a caller with NO phone number must also be refused
    r3 = client.post("/api/v1/ussd/callback", data={
        "sessionId": "sess-nonum", "text": f"{org.code}*3*G-001"})
    body3 = r3.get_data(as_text=True)
    assert "not found" in body3.lower(), body3


# ============================================================== F-066 thanks
def test_booking_thanks_hides_details_from_strangers(app, client, seeded):
    org = db.session.query(Organization).filter_by(id=seeded["org"]).first()
    tok = csrf(client, "/book")
    day = (now_naive().date() + timedelta(days=2)).isoformat()
    r = client.post("/book/submit", data={
        "_csrf": tok, "consent": "1", "is_fast_track": "1", "fast_track_consent": "1",
        "fast_track_reason": "PREMIUM", "department_id": str(seeded["dept"]),
        "appointment_date": day, "appointment_time": "09:00",
        "patient_name": "Chinwe Obi", "phone": "08033334444",
        "idem": "f066-idem-1"}, follow_redirects=False)
    assert r.status_code == 302
    thanks_url = r.headers["Location"]
    assert "/book/thanks?ref=" in thanks_url
    # the submitting browser still sees the summary (dept name in bold)
    body_owner = client.get(thanks_url).get_data(as_text=True)
    assert "<b>Emergency</b>" in body_owner, \
        "the submitter should still see the summary"
    # a stranger with only the sequential ref sees NO personal detail
    stranger = app.test_client()
    body_stranger = stranger.get(thanks_url).get_data(as_text=True)
    assert "<b>Emergency</b>" not in body_stranger, \
        "a bare sequential ref must not reveal department/date to a stranger (F-066)"
    assert "Your visit is booked" in body_stranger


# ================================================== F-047 leave vs duty
def test_leave_approval_refuses_when_person_has_duty_in_window(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        dept = Department(org_id=org, name="Ward Leave")
        nurse = _mk_user(org, "leavenurse")
        db.session.add_all([dept, nurse])
        db.session.commit()
        start = (now_naive() + timedelta(days=5)).date()
        end = start + timedelta(days=3)
        db.session.add(RosterEntry(org_id=org, duty_date=start + timedelta(days=1),
                                   user_id=nurse.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT", department_id=dept.id,
                                   source="manual", created_by=seeded["admin"]))
        req = LeaveRequest(org_id=org, user_id=nurse.id, leave_type="ANNUAL",
                           start_date=start, end_date=end, days_requested=4,
                           reason="Family event", status="PENDING")
        db.session.add(req)
        db.session.commit()
        req_id, nurse_id, org_id = req.id, nurse.id, org
    login(client, "am1")
    page = client.get("/roster/leave")
    tok = csrf(client, "/roster/leave")
    r = client.post(f"/roster/leave/{req_id}/approve", data={"_csrf": tok},
                    follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "already rostered for duty" in body.lower(), body[-800:]
    with app.app_context():
        req = db.session.get(LeaveRequest, req_id)
        assert req.status == "PENDING", \
            "approval must be refused while a DUTY row overlaps the leave window"
        # no LEAVE roster rows were written
        assert db.session.query(RosterEntry).filter_by(
            org_id=org_id, user_id=nurse_id, kind="LEAVE").count() == 0
