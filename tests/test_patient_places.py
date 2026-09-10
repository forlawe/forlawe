"""Patients must not be asked to pick Laundry or Internal Audit."""
from app.models import Department, db
from app.patient_places import is_patient_place, public_departments
from tests.conftest import csrf


def test_back_office_is_not_a_patient_place():
    assert is_patient_place("Laundry") is False
    assert is_patient_place("Internal Audit") is False
    assert is_patient_place("Store Unit") is False
    assert is_patient_place("Finance & Accounts") is False
    assert is_patient_place("ICT") is False


def test_clinical_and_fast_track_are_patient_places():
    assert is_patient_place("Fast Track") is True
    assert is_patient_place("Emergency") is True
    assert is_patient_place("Pharmacy") is True
    assert is_patient_place("Accident & Emergency") is True


def test_queue_join_hides_laundry_and_shows_fast_track(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        db.session.add(Department(org_id=org_id, name="Laundry", active=True))
        db.session.add(Department(org_id=org_id, name="Internal Audit", active=True))
        db.session.commit()

    body = client.get("/queue/join").get_data(as_text=True)
    assert "Fast Track" in body
    assert "Laundry" not in body
    assert "Internal Audit" not in body
    assert "Emergency" in body


def test_public_list_puts_fast_track_first(app, seeded):
    with app.app_context():
        names = [d.name for d in public_departments(seeded["org"])]
        assert names[0] == "Fast Track"
        assert "Emergency" in names


def test_picking_fast_track_joins_the_gold_lane(app, client, seeded):
    with app.app_context():
        ft = public_departments(seeded["org"])[0]
        db.session.commit()
        ft_id = ft.id
    token = csrf(client, "/queue/join")
    r = client.post("/queue/join", data={
        "_csrf": token,
        "department_id": ft_id,
        "patient_name": "Aisha Bello",
        "is_fast_track": "1",
        "fast_track_consent": "1",
        "fast_track_reason": "PREMIUM",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Fast Track" in r.data
