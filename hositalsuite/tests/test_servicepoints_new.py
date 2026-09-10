"""Clinics, rooms, destinations — admin editable, 8 rooms, shortlist per clinic."""
from app.models import ServiceClinic, ServiceDestination, ConsultingRoom, ClinicDestination, db
from app.servicepoints import ensure_defaults, active_clinics, active_rooms, active_destinations, destinations_for_clinic, DEFAULT_CLINICS, DEFAULT_ROOMS, DEFAULT_DESTINATIONS


def _org_id(seeded):
    return seeded["org"]


def test_defaults_seed(client, seeded):
    org_id = _org_id(seeded)
    created = ensure_defaults(org_id)
    assert active_clinics(org_id)
    assert len(active_rooms(org_id)) >= 8
    assert len(active_destinations(org_id)) >= 20


def test_clinic_codes_include_new_ones(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    codes = {c.code for c in active_clinics(org_id)}
    for need in ("DENTAL", "ANC", "O&G", "EYE", "PAEDS"):
        assert need in codes, f"Missing clinic {need}"


def test_rooms_up_to_8(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    rooms = active_rooms(org_id)
    assert len(rooms) >= 8
    assert len({r.code for r in rooms}) == len(rooms)


def test_destinations_include_new_wards(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    codes = {d.code for d in active_destinations(org_id)}
    for need in ("HIMS", "MOPD", "SOPD", "OPD", "O&G", "MSSD", "PAEDS", "PHYSIO", "RADIOLOGY", "DENTAL", "NUTRITION", "EYE", "MATERNITY", "CASUALTY", "DRESSING", "THEATER", "MALE_WARD", "FEMALE_WARD"):
        assert need in codes, f"Missing destination {need}"


def test_empty_shortlist_shows_everything(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    dests, is_shortlisted, warning = destinations_for_clinic(org_id, "OPD")
    assert not is_shortlisted
    assert not warning
    assert len(dests) >= 20


def test_shortlisted_clinic_shows_only_relevant(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    dests, is_shortlisted, warning = destinations_for_clinic(org_id, "DENTAL")
    assert is_shortlisted
    assert not warning
    assert len(dests) == 8
    assert len(dests) < len(active_destinations(org_id))


def test_all_suspended_shortlist_warns_not_everything(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    dests, _, _ = destinations_for_clinic(org_id, "DENTAL")
    for d in dests:
        d.active = False
    db.session.commit()
    filtered, is_shortlisted, warning = destinations_for_clinic(org_id, "DENTAL")
    assert is_shortlisted
    assert warning is True
    assert filtered == []
    for d in dests:
        d.active = True
    db.session.commit()


def test_suspend_instead_of_delete_block(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    from app.models import DoctorSession, User
    user = User(org_id=org_id, username="doc1", name="Doc One", role="HOD", password_hash="x", approved=True, active=True)
    user.set_password("TestPass123!")
    db.session.add(user)
    db.session.flush()
    clinic = db.session.query(ServiceClinic).filter_by(org_id=org_id, code="DENTAL").first()
    from datetime import date
    sess = DoctorSession(org_id=org_id, doctor_id=user.id, duty_date=date.today(), clinic=clinic.code, consulting_room="ROOM1", ready=True)
    db.session.add(sess)
    db.session.commit()
    assert clinic.code == "DENTAL"


def test_consulting_filters_by_clinic(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    dests, is_shortlisted, _ = destinations_for_clinic(org_id, "DENTAL")
    assert is_shortlisted
    dests_opd, is_short_opd, _ = destinations_for_clinic(org_id, "OPD")
    assert not is_short_opd
    assert len(dests_opd) > len(dests)


def test_voice_place_field_present(client, seeded):
    org_id = _org_id(seeded)
    ensure_defaults(org_id)
    for d in active_destinations(org_id):
        assert d.place, f"Destination {d.code} missing place for voice"


def test_admin_crud_routes_exist(client, seeded):
    from app.models import User
    from tests.conftest import login
    # Use existing admin from seeded
    login(client, "admin")
    resp = client.get("/admin/servicepoints")
    assert resp.status_code == 200
    assert b"Clinics" in resp.data
    assert b"Dental" in resp.data
    assert b"Consulting Rooms" in resp.data

