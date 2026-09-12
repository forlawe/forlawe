"""Wave B tests: referral engine + repeat-visit detection (spec §14)."""
from datetime import timedelta

from app.models import (Appointment, PatientFeedback, Referral, ReferralEvent,
                        db, now_naive)

from conftest import csrf, login


def _rate(client, rating, **over):
    data = {"_csrf": csrf(client, "/feedback"), "rating": str(rating), "consent": "1"}
    data.update({k: str(v) for k, v in over.items()})
    return client.post("/feedback/submit", data=data, follow_redirects=True)


def _book(client, seeded, **over):
    token = csrf(client, "/book")
    day = (now_naive().date() + timedelta(days=over.pop("days", 2))).isoformat()
    data = {"_csrf": token, "consent": "1", "fast_track_consent": "1",
            "is_fast_track": "1", "fast_track_reason": "PREMIUM",
            "department_id": seeded["dept"], "appointment_date": day,
            "appointment_time": "09:00", "patient_name": over.pop("name", "Chinwe Obi"),
            "phone": over.pop("phone", "08033334444"),
            "idem": over.pop("idem", "ref-idem-1")}
    data.update(over)
    return client.post("/book/submit", data=data, follow_redirects=True)


def test_high_rating_issues_trackable_referral(client, seeded):
    r = _rate(client, 5, comment="The nurses were wonderful and very quick.",
              department_id=seeded["dept"], phone="08030001111")
    assert b"glad you had a good experience" in r.data
    assert b"BOOK ANOTHER VISIT" in r.data and b"REFER A FRIEND" in r.data
    ref = db.session.query(Referral).filter_by(kind="patient").first()
    assert ref is not None and ref.active
    assert ref.referrer_phone == "08030001111"
    assert ref.code.encode() in r.data
    assert b"/r/" in r.data
    # QR is rendered for the patient to show a friend
    assert f"/r/{ref.code}.png".encode() in r.data


def test_rating_four_also_issues_link(client, seeded):
    _rate(client, 4, department_id=seeded["dept"])
    assert db.session.query(Referral).count() == 1


def test_low_and_neutral_do_not_issue_referral(client, seeded):
    _rate(client, 1, comment="Nobody attended to my mother for hours.",
          department_id=seeded["dept"], phone="08044445555")
    _rate(client, 3, department_id=seeded["dept"])
    assert db.session.query(Referral).count() == 0
    assert db.session.query(PatientFeedback).count() == 2


def test_same_feedback_does_not_duplicate_code(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    fb = db.session.query(PatientFeedback).first()
    from app.models import Organization
    from app import referrals as engine
    org = db.session.get(Organization, seeded["org"])
    again = engine.issue_patient_referral(org, fb, referrer_phone="08030001111")
    assert db.session.query(Referral).count() == 1
    assert again.id == db.session.query(Referral).first().id


def test_landing_records_one_click_per_session(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    r = client.get(f"/r/{code}")
    assert r.status_code == 200
    assert b"A friend recommended this hospital" in r.data
    assert b"BOOK A VISIT" in r.data
    assert db.session.query(ReferralEvent).filter_by(kind="click").count() == 1
    # refresh must not inflate the count
    client.get(f"/r/{code}")
    client.get(f"/r/{code}")
    assert db.session.query(ReferralEvent).filter_by(kind="click").count() == 1


def test_unknown_and_inactive_codes(client, seeded):
    assert client.get("/r/NOPECODE").status_code == 404
    _rate(client, 5, department_id=seeded["dept"])
    row = db.session.query(Referral).first()
    row.active = False
    db.session.commit()
    assert client.get(f"/r/{row.code}").status_code == 404
    # QR of a known (even inactive) code still renders — staff may print then retire
    assert client.get(f"/r/{row.code}.png").status_code == 200
    assert client.get("/r/NOPECODE.png").status_code == 404


def test_booking_via_referral_is_conversion(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    client.get(f"/r/{code}")   # friend opens the link
    r = _book(client, seeded, phone="08099990000", name="Musa Bello",
              r=code, idem="conv-1")
    assert b"Your visit is booked" in r.data
    apt = db.session.query(Appointment).first()
    assert apt.referral_id == db.session.query(Referral).first().id
    assert apt.source == "referral"
    assert apt.is_repeat is False
    assert db.session.query(ReferralEvent).filter_by(kind="book").count() == 1


def test_session_sticky_referral_without_hidden_field(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    client.get(f"/r/{code}")
    # /book should carry the code from the session
    page = client.get("/book")
    assert code.encode() in page.data
    _book(client, seeded, phone="08088887777", name="Ada Guest", idem="sticky-1")
    apt = db.session.query(Appointment).first()
    assert apt.referral_id is not None


def test_own_link_is_repeat_not_conversion(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    _book(client, seeded, phone="08030001111", name="Original Patient",
          r=code, idem="self-1")
    apt = db.session.query(Appointment).first()
    assert apt.is_repeat is True
    assert apt.referral_id is None
    assert db.session.query(ReferralEvent).filter_by(kind="book").count() == 0


def test_second_booking_same_phone_is_repeat(client, seeded):
    _book(client, seeded, phone="08011112222", name="First Visit", idem="rep-1", days=2)
    _book(client, seeded, phone="08011112222", name="Second Visit", idem="rep-2", days=5)
    apts = db.session.query(Appointment).order_by(Appointment.id).all()
    assert apts[0].is_repeat is False
    assert apts[1].is_repeat is True


def test_same_phone_not_double_converted(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    _book(client, seeded, phone="08077776666", name="Friend One", r=code, idem="d1", days=2)
    _book(client, seeded, phone="08077776666", name="Friend One again", r=code, idem="d2", days=6)
    assert db.session.query(ReferralEvent).filter_by(kind="book").count() == 1
    second = db.session.query(Appointment).order_by(Appointment.id.desc()).first()
    assert second.is_repeat is True


def test_staff_analytics_and_hospital_code(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    client.get(f"/r/{code}")
    _book(client, seeded, phone="08055556666", name="Referred", r=code, idem="st-1")
    login(client, "md")
    r = client.get("/referrals")
    assert r.status_code == 200
    assert b"Referrals" in r.data
    assert b"Share-links issued" in r.data
    assert code.encode() in r.data
    # hospital-wide code is created on first staff visit
    assert db.session.query(Referral).filter_by(kind="hospital").count() == 1
    assert b"Hospital-wide QR" in r.data


def test_staff_can_create_and_deactivate(client, seeded):
    login(client, "admin")
    tok = csrf(client, "/referrals")
    r = client.post("/referrals/create",
                    data={"_csrf": tok, "note": "Ward A poster",
                          "department_id": seeded["dept"]},
                    follow_redirects=True)
    assert r.status_code == 200
    row = db.session.query(Referral).filter_by(kind="staff").first()
    assert row is not None and row.note == "Ward A poster" and row.active
    tok = csrf(client, "/referrals")
    client.post(f"/referrals/{row.id}/toggle", data={"_csrf": tok}, follow_redirects=True)
    assert db.session.get(Referral, row.id).active is False
    # HOD cannot create
    login(client, "hod1")
    tok = csrf(client, "/referrals")
    r = client.post("/referrals/create",
                    data={"_csrf": tok, "note": "Should fail"}, follow_redirects=False)
    assert r.status_code == 403


def test_referral_report_csv_and_pdf(client, seeded):
    _rate(client, 5, department_id=seeded["dept"])
    login(client, "admin")
    csv_r = client.get("/reports/referrals?format=csv")
    assert csv_r.status_code == 200 and b"Code" in csv_r.data
    pdf_r = client.get("/reports/referrals?format=pdf")
    assert pdf_r.status_code == 200 and pdf_r.data[:4] == b"%PDF"


def test_poster_pack_includes_referral(client, seeded):
    login(client, "admin")
    r = client.get("/admin/posters/download?services=referral")
    assert r.status_code == 200 and r.data[:4] == b"%PDF"
    assert db.session.query(Referral).filter_by(kind="hospital").count() == 1


def test_qr_png_is_image(client, seeded):
    _rate(client, 5, department_id=seeded["dept"])
    code = db.session.query(Referral).first().code
    r = client.get(f"/r/{code}.png")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("image/png")
    assert r.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_dashboard_shows_referral_kpis(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], phone="08030001111")
    code = db.session.query(Referral).first().code
    _book(client, seeded, phone="08012121212", name="KPI Guest", r=code, idem="kpi-1")
    login(client, "md")
    r = client.get("/")
    assert r.status_code == 200
    assert b"Referred bookings" in r.data
    assert b"Repeat visits" in r.data
