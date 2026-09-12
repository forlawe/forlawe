"""Triage — Stage B. Placement, not clinical assessment.

Closes the dead end left by Reception: patients were told "go to Triage" and
there was nowhere for them to go.
"""
from datetime import date, timedelta

from app import triage
from app.models import (DoctorSession, Patient, PatientVisit, RosterEntry,
                        User, db, now_naive)
from tests.conftest import csrf, login


# ------------------------------------------------------------------ helpers
_seq = [0]


def _patient(org_id, surname="Abatan", first="Folake", category="GENERAL", **kw):
    # Unique folder number per patient: the real column is unique per org, and
    # a truncated surname collides ("Queue1"/"Queue2" both -> QUE).
    _seq[0] += 1
    p = Patient(org_id=org_id, hospital_number=f"IJE/2026/{_seq[0]:05d}",
                surname=surname, first_name=first, sex="F", category=category, **kw)
    db.session.add(p)
    db.session.flush()
    return p


def _visit(org_id, patient, minutes_ago=0):
    v = PatientVisit(org_id=org_id, patient_id=patient.id,
                     visit_no=f"V-{patient.id}-{minutes_ago}", visit_type="NEW",
                     status="REGISTERED",
                     started_at=now_naive() - timedelta(minutes=minutes_ago))
    db.session.add(v)
    db.session.flush()
    return v


def _doctor(org_id, username="doc1", name="Dr Ade Ogun", rostered=True):
    u = User(org_id=org_id, username=username, name=name, role="HOD")
    u.set_password("Passw0rd!x")
    db.session.add(u)
    db.session.flush()
    if rostered:
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=u.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT"))
        db.session.flush()
    return u


# ------------------------------------------------------------------ the rule
def test_a_doctor_must_be_BOTH_rostered_and_ready(app, seeded):
    """The founder's rule. Either one alone must not make them available."""
    with app.app_context():
        org_id = seeded["org"]

        # rostered but has NOT clicked ready
        rostered_only = _doctor(org_id, "doc_r", "Dr Rostered", rostered=True)
        db.session.commit()
        assert not triage.is_available(org_id, rostered_only.id), \
            "a doctor who never clicked ready was offered to Triage"

        # clicked ready but NOT on the roster
        not_rostered = _doctor(org_id, "doc_n", "Dr Notrostered", rostered=False)
        db.session.commit()
        session, err = triage.open_session(org_id, not_rostered, "OPD", "Room 2")
        assert session is None and "not on the roster" in err

        # both -> available
        session, err = triage.open_session(org_id, rostered_only, "OPD", "Room 1")
        db.session.commit()
        assert err == "" and session is not None
        assert triage.is_available(org_id, rostered_only.id)


def test_a_doctor_who_stops_is_removed_immediately(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "OPD", "Room 1")
        db.session.commit()
        assert triage.is_available(org_id, doc.id)

        triage.close_session(org_id, doc.id)
        db.session.commit()
        assert not triage.is_available(org_id, doc.id), \
            "Triage would still send patients to an empty room"


def test_two_doctors_cannot_hold_the_same_room(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        a = _doctor(org_id, "doc_a", "Dr A")
        b = _doctor(org_id, "doc_b", "Dr B")
        db.session.commit()
        triage.open_session(org_id, a, "OPD", "Room 1")
        db.session.commit()
        session, err = triage.open_session(org_id, b, "OPD", "Room 1")
        assert session is None and "already in use" in err


# ------------------------------------------------------------------ placement
def test_placement_uses_category_not_symptoms(app, seeded):
    """Triage places by CATEGORY. It must never reason about illness."""
    with app.app_context():
        org_id = seeded["org"]
        child = _patient(org_id, "Bello", "Tunde", category="CHILD")
        elderly = _patient(org_id, "Sanni", "Musa", category="ELDERLY")
        db.session.commit()
        assert triage.suggest_clinic(child) == "OPD"
        assert triage.suggest_clinic(elderly) == "MOPD"


def test_placing_a_patient_moves_them_out_of_the_queue(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        doc = _doctor(org_id)
        db.session.commit()
        session, _ = triage.open_session(org_id, doc, "OPD", "Room 1")
        db.session.commit()

        assert len(triage.waiting(org_id)) == 1
        err = triage.place(v, clinic="OPD", session=session)
        db.session.commit()
        assert err == ""
        assert v.status == "TRIAGED"
        assert v.clinic == "OPD"
        assert v.consulting_room == "Room 1"
        assert v.doctor_id == doc.id
        assert v.triaged_at is not None
        assert len(triage.waiting(org_id)) == 0


def test_a_patient_can_be_placed_in_a_clinic_with_no_doctor_yet(app, seeded):
    """Honest: 'waiting in MOPD' beats leaving them stuck in the backlog."""
    with app.app_context():
        org_id = seeded["org"]
        v = _visit(org_id, _patient(org_id))
        db.session.commit()
        assert triage.place(v, clinic="MOPD", session=None) == ""
        assert v.status == "TRIAGED" and v.doctor_id is None


def test_the_same_patient_cannot_be_placed_twice(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        v = _visit(org_id, _patient(org_id))
        db.session.commit()
        assert triage.place(v, clinic="OPD", session=None) == ""
        err = triage.place(v, clinic="SOPD", session=None)
        assert "already been placed" in err


def test_a_doctor_who_went_home_cannot_be_assigned(app, seeded):
    """The room emptied between the page loading and the nurse pressing place."""
    with app.app_context():
        org_id = seeded["org"]
        v = _visit(org_id, _patient(org_id))
        doc = _doctor(org_id)
        db.session.commit()
        session, _ = triage.open_session(org_id, doc, "OPD", "Room 1")
        db.session.commit()
        triage.close_session(org_id, doc.id)
        db.session.commit()

        err = triage.place(v, clinic="OPD", session=session)
        assert "no longer ready" in err


def test_work_is_shared_fairly_between_free_doctors(app, seeded):
    """Suggest the shortest queue, not simply the first doctor in the list."""
    with app.app_context():
        org_id = seeded["org"]
        busy = _doctor(org_id, "doc_busy", "Dr Busy")
        free = _doctor(org_id, "doc_free", "Dr Free")
        db.session.commit()
        s_busy, _ = triage.open_session(org_id, busy, "OPD", "Room 1")
        s_free, _ = triage.open_session(org_id, free, "OPD", "Room 2")
        db.session.commit()

        for i in range(3):
            v = _visit(org_id, _patient(org_id, f"Load{i}", "X"))
            triage.place(v, clinic="OPD", session=s_busy)
        db.session.commit()

        assert triage.suggest_doctor(org_id, "OPD").doctor_id == free.id


# ------------------------------------------------------------------ waiting
def test_nobody_is_forgotten_on_the_bench(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        _visit(org_id, _patient(org_id, "Longwait", "Ade"), minutes_ago=45)
        _visit(org_id, _patient(org_id, "Justcame", "Bola"), minutes_ago=2)
        db.session.commit()

        assert len(triage.long_waiters(org_id)) == 1
        called = triage.announce_long_waits(org_id)
        db.session.commit()
        assert called == 1
        said = " ".join(r.body for r in db.session.query(AppNotification).all()).lower()
        assert "45 minutes" in said


def test_the_desk_is_told_out_loud_when_the_queue_builds_up(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        for i in range(4):
            _visit(org_id, _patient(org_id, f"Queue{i}", "X"))
        db.session.commit()
        triage.announce_backlog(org_id)
        db.session.commit()
        rows = db.session.query(AppNotification).filter_by(
            template_key="triage_backlog").all()
        assert rows and "4 patients" in rows[0].body


def test_placement_calls_the_patient_and_tells_the_doctor(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        doc = _doctor(org_id)
        db.session.commit()
        session, _ = triage.open_session(org_id, doc, "OPD", "Room 3")
        db.session.commit()
        triage.place(v, clinic="OPD", session=session)
        triage.announce_placement(v, p, session)
        db.session.commit()

        rows = db.session.query(AppNotification).all()
        kinds = {r.template_key for r in rows}
        assert "queue_assigned" in kinds, "the patient was never called"
        assert "consult_ready" in kinds, "the doctor was never told"
        to_doctor = [r for r in rows if r.template_key == "consult_ready"]
        assert to_doctor[0].user_id == doc.id
        assert "room 3" in to_doctor[0].body.lower()


# ------------------------------------------------------------------ NOT an EMR
def test_triage_records_that_the_blood_sugar_test_happened_never_a_reading(app, seeded):
    """'Blood sugar test' is a step and a billing line, NOT a result."""
    with app.app_context():
        org_id = seeded["org"]
        v = _visit(org_id, _patient(org_id))
        db.session.commit()
        triage.place(v, clinic="OPD", session=None, blood_sugar_done=True)
        db.session.commit()
        assert "Blood sugar test done" in (v.reason or "")
        # nothing numeric may be stored anywhere on the visit
        assert not any(ch.isdigit() for ch in (v.reason or "").replace("Blood sugar test done", ""))


def test_the_doctor_session_holds_no_medical_record(app, seeded):
    banned = {"diagnosis", "symptoms", "temperature", "blood_pressure", "bp",
              "pulse", "weight", "glucose", "blood_sugar_value", "reading",
              "prescription", "medication", "test_result", "notes_clinical"}
    columns = {c.name for c in DoctorSession.__table__.columns}
    leaked = banned & columns
    assert not leaked, f"EMR field(s) appeared on the doctor session: {leaked}"


# ------------------------------------------------------------------ routes
def _login_desk(client, app, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"],
                                             role="ADMIN_MANAGER").first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


def test_every_triage_route_answers_without_a_server_error(app, client, seeded):
    """Drives the real pages — catches view bugs the engine tests cannot see."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        _visit(org_id, p)
        db.session.commit()

    _login_desk(client, app, seeded)
    assert client.get("/triage/").status_code == 200
    # /triage/consulting-room is superseded by the full Stage C room and now
    # redirects there — old bookmarks must still land somewhere useful.
    assert client.get("/triage/consulting-room").status_code == 302
    assert client.get("/triage/consulting-room",
                      follow_redirects=True).status_code == 200

    with app.app_context():
        vid = db.session.query(PatientVisit).one().id

    r = client.post(f"/triage/{vid}/place",
                    data={"_csrf": csrf(client, "/triage/"), "clinic": "OPD"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "placed in" in r.get_data(as_text=True).lower()

    with app.app_context():
        assert db.session.get(PatientVisit, vid).status == "TRIAGED"


def test_a_doctor_can_declare_ready_and_see_their_own_queue(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = db.session.query(User).filter_by(org_id=org_id, role="HOD").first()
        doc.must_change_password = False
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=doc.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT"))
        db.session.commit()
        username = doc.username

    login(client, username)
    r = client.post("/triage/ready",
                    data={"_csrf": csrf(client, "/consulting-room"),
                          "clinic": "OPD", "consulting_room": "Room 1"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "ready to consult" in r.get_data(as_text=True).lower()

    r = client.post("/triage/not-ready",
                    data={"_csrf": csrf(client, "/consulting-room")},
                    follow_redirects=True)
    assert "no longer taking new patients" in r.get_data(as_text=True).lower()


# ------------------------------------------------------------------ F-006
def test_emergency_alert_failures_are_logged_not_swallowed(app, seeded, monkeypatch, caplog):
    """F-006: a failed emergency alert used to vanish into `except: pass`.

    The alert IS the safety action here — a silent failure means the team was
    never alarmed. Every channel failure must now log a loud, greppable ERROR
    while triage itself still does not crash.
    """
    import logging

    from app import triage

    with app.app_context():
        visit = type("V", (), {"org_id": 1})()
        patient = type("P", (), {"spoken_name": "Test Patient"})()

        def boom_station(*a, **kw):
            raise RuntimeError("voice backend down")

        calls = {"roles": []}

        def boom_role(org_id, role, *a, **kw):
            calls["roles"].append(role)
            raise RuntimeError("announce backend down")

        monkeypatch.setattr(triage.announce, "to_station", boom_station)
        monkeypatch.setattr(triage.announce, "to_role", boom_role)

        with caplog.at_level(logging.ERROR):
            # must not raise, even though EVERY channel fails
            triage.announce_emergency(visit, patient)

        joined = " ".join(rec.getMessage() for rec in caplog.records)
        assert "EMERGENCY ALERT FAILURE" in joined
        assert "station broadcast" in joined
        # every role was attempted and every failure was logged
        assert len(calls["roles"]) == 13
        assert "role alert DOCTOR" in joined
        assert "role alert TRIAGE_NURSE" in joined
