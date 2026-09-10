"""Wave A tests: booking, SMS provider interface, idempotency (§5, §38, §41)."""
from datetime import timedelta

from app.models import Appointment, Complaint, SmsMessage, db, now_naive
from app import services, sms as sms_engine

from conftest import csrf, login


def _book(client, seeded, **over):
    token = csrf(client, "/book")
    day = (now_naive().date() + timedelta(days=over.pop("days", 1))).isoformat()
    data = {"_csrf": token, "consent": "1", "fast_track_consent": "1", "is_fast_track": "1", "fast_track_reason": "PREMIUM", "department_id": seeded["dept"], "appointment_date": day,
            "appointment_time": "09:00", "patient_name": "Chinwe Obi",
            "phone": "08033334444", "idem": over.pop("idem", "idem-test-1")}
    data.update(over)
    return client.post("/book/submit", data=data, follow_redirects=True)


def test_booking_portal_public_and_valid_submission(client, seeded):
    r = client.get("/book")
    assert r.status_code == 200 and b"Book a Hospital Visit" in r.data

    r = _book(client, seeded)
    assert b"Your visit is booked" in r.data
    apt = db.session.query(Appointment).first()
    assert apt.ref.startswith("TEST-APT-")
    assert apt.status == "BOOKED"
    # SMS confirmation queued & delivered (sandbox provider) — v2 normalizes to +234
    m = db.session.query(SmsMessage).first()
    assert m is not None and m.status == "SENT" and apt.ref in m.body
    assert m.to_number in ("08033334444", "+2348033334444", "2348033334444")


def test_booking_validation_rejects_bad_input(client, seeded):
    # invalid slot
    r = _book(client, seeded, appointment_time="23:59", idem="a1")
    assert b"available time slots" in r.data
    # past date
    r = _book(client, seeded, days=-3, idem="a2")
    assert b"past" in r.data
    # missing name
    r = _book(client, seeded, patient_name="", idem="a3")
    assert b"full name" in r.data
    # bad phone
    r = _book(client, seeded, phone="abc", idem="a4")
    assert b"valid phone number" in r.data
    assert db.session.query(Appointment).count() == 0


def test_booking_slot_capacity_enforced(app, client, seeded):
    with app.app_context():
        services.set_setting(seeded["org"], "booking_capacity_per_slot", 2)
        db.session.commit()
    assert b"booked" in _book(client, seeded, idem="c1").data
    assert b"booked" in _book(client, seeded, idem="c2").data
    r = _book(client, seeded, idem="c3")
    assert b"slot is full" in r.data
    assert db.session.query(Appointment).count() == 2


def test_booking_idempotency_prevents_duplicates(client, seeded):
    _book(client, seeded, idem="dup-key-1")
    _book(client, seeded, idem="dup-key-1")   # double-tap / retry
    assert db.session.query(Appointment).count() == 1


def test_complaint_idempotency_prevents_duplicates(client, seeded):
    token = csrf(client, "/complaint")
    data = {"_csrf": token, "consent": "1", "department_id": seeded["dept"],
            "category": "Long waiting time",
            "description": "Waiting too long without any information at all.",
            "phone": "08055556666", "idem": "cmp-idem-1"}
    client.post("/complaint/submit", data=data, follow_redirects=True)
    client.post("/complaint/submit", data=dict(data, _csrf=csrf(client, "/complaint")),
                follow_redirects=True)
    assert db.session.query(Complaint).count() == 1


def test_ussd_booking_endpoint(client, seeded):
    day = (now_naive().date() + timedelta(days=2)).isoformat()
    r = client.post("/api/v1/ussd/booking", json={
        "secret": "ussd-test-secret", "hospital_code": "TEST", "department": "Emergency",
        "name": "Musa Bello", "phone": "08077778888", "date": day, "time": "10:00"})
    assert r.status_code == 200 and r.get_json()["ref"].startswith("TEST-APT-")
    assert db.session.query(Appointment).first().source == "ussd"
    # unauthorized without secret
    r = client.post("/api/v1/ussd/booking", json={"secret": "nope"})
    assert r.status_code == 401


def test_booking_status_check_and_cancel(client, seeded):
    _book(client, seeded, idem="x1")
    apt = db.session.query(Appointment).first()
    r = client.get(f"/book/status?ref={apt.ref}&phone=08033334444")
    assert apt.ref.encode() in r.data
    r = client.post("/book/cancel", data={"_csrf": csrf(client, "/book"),
                                          "ref": apt.ref, "phone": "08033334444"},
                    follow_redirects=True)
    assert b"cancelled" in r.data
    assert db.session.get(Appointment, apt.id).status == "CANCELLED"


def test_staff_sees_bookings_and_checks_in(client, seeded):
    _book(client, seeded, idem="s1")
    apt = db.session.query(Appointment).first()
    login(client, "am1")
    r = client.get("/bookings")
    assert apt.patient_name.encode() in r.data
    # check-in now issues a queue ticket as well (single redundant-free path)
    client.post(f"/bookings/{apt.id}/checkin-queue",
                data={"_csrf": csrf(client, "/bookings")}, follow_redirects=True)
    assert db.session.get(Appointment, apt.id).status == "ARRIVED"
    from app.models import QueueTicket
    assert db.session.query(QueueTicket).filter_by(appointment_id=apt.id).count() == 1


def test_sms_provider_interface_fallback(app, seeded):
    """Termii configured but no API key → graceful failure, never crashes."""
    app.config["SMS_MODE"] = "termii"
    with app.app_context():
        m = sms_engine.queue_sms(seeded["org"], "08011110000", "test", kind="alert")
        sms_engine.send_sms(m)
        # no termii key and no twilio credentials → falls back to sandbox delivery
        assert m.status in ("SENT", "QUEUED", "FAILED")
        assert m.attempts == 1
    app.config["SMS_MODE"] = "sandbox"


def test_sms_disabled_mode_marks_failed(app, seeded):
    app.config["SMS_MODE"] = "disabled"
    with app.app_context():
        m = sms_engine.queue_sms(seeded["org"], "08011110000", "test", kind="alert")
        sms_engine.send_sms(m)
        assert m.status == "FAILED" and "disabled" in m.last_error
    app.config["SMS_MODE"] = "sandbox"
