"""TV display - multiple TVs, waiting area shows more, Nigeria voices, EN+YO, full name + stats."""

def test_tv_main_page_loads(client, seeded):
    from tests.conftest import login
    login(client, "admin")
    # Ensure defaults
    from app.tv import ensure_default_screens
    from app.models import Organization, db
    org_id = seeded["org"]
    ensure_default_screens(org_id)
    db.session.commit()

    resp = client.get("/tv")
    assert resp.status_code == 200
    assert b"Waiting Area" in resp.data or b"TV" in resp.data
    # Should contain voice rotation info
    assert b"Nigeria" in resp.data or b"Voice" in resp.data


def test_tv_clinic_page_loads(client, seeded):
    from tests.conftest import login
    login(client, "admin")
    from app.tv import ensure_default_screens
    from app.models import db
    org_id = seeded["org"]
    ensure_default_screens(org_id)
    db.session.commit()

    resp = client.get("/tv/DENTAL")
    assert resp.status_code == 200
    assert b"Dental" in resp.data


def test_tv_api_feed(client, seeded):
    from app.tv import ensure_default_screens
    from app.models import db
    org_id = seeded["org"]
    ensure_default_screens(org_id)
    db.session.commit()

    resp = client.get("/api/tv/feed?code=MAIN")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "now_serving" in data
    assert "next_up" in data
    assert "stats" in data
    assert "rotation" in data
    # Rotation should have 2M2F
    assert data["rotation"]["slot"] in (0,1,2,3)
    assert len(data["rotation"]["all_slots"]) == 4
    # Languages include en and yo
    assert "en-NG" in data["rotation"]["languages"]


def test_tv_admin_crud(client, seeded):
    from tests.conftest import login
    login(client, "admin")
    from app.tv import ensure_default_screens
    from app.models import db
    org_id = seeded["org"]
    ensure_default_screens(org_id)
    db.session.commit()

    resp = client.get("/admin/tv")
    assert resp.status_code == 200
    assert b"TV Display" in resp.data or b"TV Screens" in resp.data

    # Create new TV
    resp = client.post("/admin/tv/create", data={
        "_csrf": client.get("/admin/tv").data.decode().split('name="_csrf" value="')[1].split('"')[0],
        "code": "ANC",
        "name": "ANC Clinic TV",
        "location": "ANC Hall",
        "screen_type": "CLINIC",
        "clinic_code": "ANC",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"ANC" in resp.data

    # Open it
    resp = client.get("/tv/ANC")
    assert resp.status_code == 200
    assert b"ANC" in resp.data


def test_tv_shows_full_name_and_stats(client, seeded):
    from app.tv import ensure_default_screens, tv_feed
    from app.models import db, Patient, PatientVisit, QueueTicket, Department
    org_id = seeded["org"]
    ensure_default_screens(org_id)

    # Create a patient visit to appear on TV
    dept = db.session.query(Department).filter_by(org_id=org_id).first()
    p = Patient(org_id=org_id, hospital_number="IJD/2026/00099", surname="ABATAN", first_name="Folake", sex="F", payer_type="SELF", category="GENERAL")
    db.session.add(p)
    db.session.flush()
    from app.models import now_naive
    v = PatientVisit(org_id=org_id, patient_id=p.id, visit_no="V-099", status="TRIAGED", clinic="DENTAL", consulting_room="Room 3", started_at=now_naive(), triaged_at=now_naive())
    db.session.add(v)
    db.session.commit()

    feed = tv_feed(org_id, None)
    # Should have stats
    assert "stats" in feed
    assert feed["stats"]["triaged"] >= 1
    # Next up should contain full name
    assert any("ABATAN" in item["name"] or "Folake" in item["name"] for item in feed["next_up"])


def test_voice_rotation_daily(client, seeded):
    from app.tv import voice_rotation_for_today
    org_id = seeded["org"]
    rot = voice_rotation_for_today(org_id)
    assert rot["slot"] in (0,1,2,3)
    # 2 male 2 female
    assert "Female" in rot["all_slots"][0]
    assert "Male" in rot["all_slots"][1]
    assert "Female" in rot["all_slots"][2]
    assert "Male" in rot["all_slots"][3]
    # Languages EN + YO
    assert "en-NG" in rot["languages"]
    assert "yo-NG" in rot["languages"] or "yo" in str(rot["languages"]).lower()
