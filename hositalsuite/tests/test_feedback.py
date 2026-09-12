"""Wave A tests: patient feedback + service-recovery routing (§7, §8)."""
from app.models import AppNotification, Complaint, PatientFeedback, db

from conftest import csrf, login


def _rate(client, rating, **over):
    data = {"_csrf": csrf(client, "/feedback"), "rating": str(rating), "consent": "1"}
    data.update({k: str(v) for k, v in over.items()})
    return client.post("/feedback/submit", data=data, follow_redirects=True)


def test_feedback_portal_public(client, seeded):
    r = client.get("/feedback")
    assert r.status_code == 200 and b"How was your experience" in r.data


def test_positive_feedback_thanks_and_refer_prompts(client, seeded):
    r = _rate(client, 5, comment="The nurses were wonderful and very quick.",
              department_id=seeded["dept"])
    assert b"glad you had a good experience" in r.data
    assert b"BOOK ANOTHER VISIT" in r.data and b"REFER A FRIEND" in r.data
    fb = db.session.query(PatientFeedback).first()
    assert fb.rating == 5 and fb.status == "NEW"
    # positive feedback must NOT create a complaint
    assert db.session.query(Complaint).count() == 0


def test_low_feedback_routes_instantly_to_service_recovery(client, seeded):
    r = _rate(client, 1, comment="Nobody attended to my mother for hours.",
              department_id=seeded["dept"], phone="08044445555")
    assert b"sent" in r.data and b"immediately" in r.data
    fb = db.session.query(PatientFeedback).first()
    c = db.session.query(Complaint).first()
    assert fb.status == "ROUTED" and fb.complaint_id == c.id
    assert "rated their experience 1/5" in c.description
    assert c.status == "NEW"
    # routed to HOD + AM on duty like a complaint
    notes = db.session.query(AppNotification).filter(
        AppNotification.template_key.in_(("complaint_new_admin", "complaint_new_hod"))).all()
    recipients = {n.user_id for n in notes}
    assert seeded["am"] in recipients and seeded["hod"] in recipients
    # reference shown to the patient for tracking
    assert c.ref.encode() in r.data


def test_neutral_feedback_not_routed(client, seeded):
    _rate(client, 3, department_id=seeded["dept"])
    fb = db.session.query(PatientFeedback).first()
    assert fb.status == "NEW"
    assert db.session.query(Complaint).count() == 0


def test_invalid_rating_rejected(client, seeded):
    r = _rate(client, 9)
    assert db.session.query(PatientFeedback).count() == 0


def test_staff_see_feedback_and_satisfaction(client, seeded):
    _rate(client, 5, department_id=seeded["dept"])
    _rate(client, 2, department_id=seeded["dept"])
    login(client, "md")
    r = client.get("/feedbacks")
    assert r.status_code == 200
    assert b"Average satisfaction" in r.data
    assert b"Recovery ticket" in r.data  # low rating shows its linked ticket
    assert b"How patients rated" in r.data
    assert b"3.5" in r.data or b"3.5" in r.data  # (5+2)/2
    assert b"Stars given" in r.data
    assert b"Each department" in r.data


def test_satisfaction_csv_has_no_phone_and_no_clinical_words(client, seeded):
    _rate(client, 5, department_id=seeded["dept"], comment="Kind nurses")
    login(client, "admin")
    r = client.get("/feedbacks.csv?days=30")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "Stars" in body
    assert "Kind nurses" in body
    assert "080" not in body
    for banned in ("diagnosis", "prescription", "blood_group", "genotype"):
        assert banned not in body.lower()


def test_hod_does_not_see_another_department_rating(client, seeded):
    from app.models import Department, User
    other = Department(org_id=seeded["org"], name="Pharmacy Store")
    db.session.add(other)
    db.session.flush()
    _rate(client, 1, department_id=other.id, comment="Pharmacy was rude")
    _rate(client, 5, department_id=seeded["dept"], comment="Emergency was kind")
    login(client, "hod1")
    page = client.get("/feedbacks")
    assert page.status_code == 200
    assert b"Emergency was kind" in page.data
    assert b"Pharmacy was rude" not in page.data


def test_two_hospitals_cannot_see_each_others_ratings(app, seeded):
    from app.models import Organization, User
    from app import satisfaction as sat
    other = Organization(code="OTH2", name="Other Clinic")
    db.session.add(other)
    db.session.flush()
    _ = PatientFeedback(org_id=other.id, rating=1, comment="secret other hospital")
    db.session.add(_)
    db.session.commit()
    md = db.session.get(User, seeded["md"])
    board = sat.dashboard(md, days=30)
    texts = " ".join((r.comment or "") for r in board["recent"])
    assert "secret other hospital" not in texts


def test_word_for_stars():
    from app import satisfaction as sat
    assert sat.word_for(4.8) == "Excellent"
    assert sat.word_for(4.0) == "Good"
    assert sat.word_for(3.2) == "Fair"
    assert sat.word_for(2.1) == "Poor"
    assert sat.word_for(1.0) == "Critical"
    assert sat.word_for(None) == "No ratings yet"
