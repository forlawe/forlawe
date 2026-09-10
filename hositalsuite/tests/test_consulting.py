"""Stage C (consulting room) and Stage D (onward routing).

Closes the last two gaps in the patient journey: the doctor could see a queue
but not call anybody in or finish with them, and there was nowhere to send a
patient afterwards.
"""
from datetime import date, timedelta

from app import consulting, triage
from app.models import (Patient, PatientVisit, RosterEntry, User, VisitOnward,
                        db, now_naive)
from tests.conftest import csrf, login

_seq = [0]


def _patient(org_id, surname="Abatan", first="Folake", **kw):
    _seq[0] += 1
    p = Patient(org_id=org_id, hospital_number=f"IJE/2026/{_seq[0]:05d}",
                surname=surname, first_name=first, sex="F", **kw)
    db.session.add(p)
    db.session.flush()
    return p


def _doctor(org_id, username="doc1", name="Dr Ade Ogun"):
    u = User(org_id=org_id, username=username, name=name, role="HOD")
    u.set_password("Passw0rd!x")
    db.session.add(u)
    db.session.flush()
    db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                               user_id=u.id, kind="DUTY", shift="DAY",
                               scope="DEPARTMENT"))
    db.session.flush()
    return u


def _registered(org_id, patient):
    """A visit waiting for Triage — no clinic, no doctor yet."""
    v = PatientVisit(org_id=org_id, patient_id=patient.id,
                     visit_no=f"V-REG-{patient.id}", visit_type="NEW",
                     status="REGISTERED")
    db.session.add(v)
    db.session.flush()
    return v


def _triaged(org_id, patient, doctor, room="Room 1", minutes_ago=10):
    v = PatientVisit(org_id=org_id, patient_id=patient.id,
                     visit_no=f"V-{patient.id}", visit_type="NEW",
                     status="TRIAGED", clinic="OPD", consulting_room=room,
                     doctor_id=doctor.id,
                     started_at=now_naive() - timedelta(minutes=minutes_ago + 5),
                     triaged_at=now_naive() - timedelta(minutes=minutes_ago))
    db.session.add(v)
    db.session.flush()
    return v


# ------------------------------------------------------------------ Stage C
def test_the_doctor_sees_only_their_own_queue(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        mine = _doctor(org_id, "doc_a", "Dr A")
        theirs = _doctor(org_id, "doc_b", "Dr B")
        _triaged(org_id, _patient(org_id, "Mine", "P"), mine)
        _triaged(org_id, _patient(org_id, "Theirs", "P"), theirs)
        db.session.commit()

        q = consulting.doctor_queue(org_id, mine.id)
        assert len(q) == 1
        assert db.session.get(Patient, q[0].patient_id).surname == "Mine"


def test_calling_a_patient_in_puts_them_in_the_room(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()

        assert consulting.call_in(v, doc.id) == ""
        db.session.commit()
        assert v.status == "IN_CONSULTATION"
        assert v.seen_at is not None
        assert consulting.in_consultation(org_id, doc.id).id == v.id


def test_only_one_patient_at_a_time_in_a_room(app, seeded):
    """Two people 'in consultation' with one doctor is a lie about reality."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        first = _triaged(org_id, _patient(org_id, "First", "P"), doc)
        second = _triaged(org_id, _patient(org_id, "Second", "P"), doc)
        db.session.commit()

        assert consulting.call_in(first, doc.id) == ""
        db.session.commit()
        err = consulting.call_in(second, doc.id)
        assert "already have a patient" in err
        assert second.status == "TRIAGED"


def test_a_doctor_cannot_call_in_another_doctors_patient(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        mine = _doctor(org_id, "doc_a", "Dr A")
        theirs = _doctor(org_id, "doc_b", "Dr B")
        v = _triaged(org_id, _patient(org_id), theirs)
        db.session.commit()
        assert "not on your call room queue" in consulting.call_in(v, mine.id)


def test_finishing_with_no_destination_closes_the_visit(app, seeded):
    """Plenty of patients are seen and simply go home."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        err, steps = consulting.finish(v, doc.id, [])
        db.session.commit()
        assert err == "" and steps == []
        assert v.status == "CLOSED" and v.closed_at is not None


def test_a_consultation_cannot_be_finished_twice(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        consulting.finish(v, doc.id, ["PHARMACY"])
        db.session.commit()
        err, _ = consulting.finish(v, doc.id, ["LABORATORY"])
        assert "already been finished" in err


# ------------------------------------------------------------------ Stage D
def test_a_patient_can_be_sent_to_one_two_or_three_places(app, seeded):
    """The founder's exact words: 'one, two or three out of the following'."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        err, steps = consulting.finish(
            v, doc.id, ["LABORATORY", "PHARMACY", "BILLING"])
        db.session.commit()

        assert err == ""
        assert len(steps) == 3
        assert v.status == "ONWARD"
        assert {s.destination for s in v.onward_steps} == {
            "LABORATORY", "PHARMACY", "BILLING"}
        assert all(s.status == "PENDING" for s in v.onward_steps)


def test_rubbish_destinations_are_ignored_not_saved(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id,
                                     ["PHARMACY", "'; DROP TABLE--", "NOWHERE"])
        db.session.commit()
        assert [s.destination for s in steps] == ["PHARMACY"]


def test_the_same_desk_is_never_added_twice(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id, ["PHARMACY", "PHARMACY"])
        db.session.commit()
        assert len(steps) == 1


def test_the_visit_closes_only_when_every_desk_is_done(app, seeded):
    """The lab finishing must not send a patient home who still owes pharmacy."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id, ["LABORATORY", "PHARMACY"])
        db.session.commit()

        closed = consulting.complete_step(steps[0])
        db.session.commit()
        assert closed is False, "the visit closed while pharmacy was still waiting"
        assert v.status == "ONWARD"

        closed = consulting.complete_step(steps[1])
        db.session.commit()
        assert closed is True
        assert v.status == "CLOSED" and v.closed_at is not None


def test_each_desk_sees_only_its_own_patients(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v1 = _triaged(org_id, _patient(org_id, "Labonly", "P"), doc)
        v2 = _triaged(org_id, _patient(org_id, "Pharmonly", "P"), doc, room="Room 2")
        db.session.commit()
        consulting.call_in(v1, doc.id)
        consulting.finish(v1, doc.id, ["LABORATORY"])
        db.session.commit()
        consulting.call_in(v2, doc.id)
        consulting.finish(v2, doc.id, ["PHARMACY"])
        db.session.commit()

        assert len(consulting.pending_for(org_id, "LABORATORY")) == 1
        assert len(consulting.pending_for(org_id, "PHARMACY")) == 1
        assert len(consulting.pending_for(org_id, "BILLING")) == 0
        assert consulting.pending_counts(org_id)["LABORATORY"] == 1


def test_completing_a_step_twice_does_not_double_close(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        v = _triaged(org_id, _patient(org_id), doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id, ["PHARMACY"])
        db.session.commit()
        assert consulting.complete_step(steps[0]) is True
        db.session.commit()
        assert consulting.complete_step(steps[0]) is False


# ------------------------------------------------------------------ voice
def test_calling_a_patient_in_says_their_name_and_the_room(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        p = _patient(org_id)
        v = _triaged(org_id, p, doc, room="Room 3")
        db.session.commit()
        consulting.call_in(v, doc.id)
        consulting.announce_called_in(v, p)
        db.session.commit()

        rows = db.session.query(AppNotification).filter_by(
            template_key="consult_call_in").all()
        assert rows, "the patient was never called in"
        assert "folake" in rows[0].body.lower(), (
            "the patient was called by a different name than Reception used")
        assert "room 3" in rows[0].body.lower()


def test_onward_tells_the_patient_every_place_in_one_sentence(app, seeded):
    """Three separate announcements while walking away is impossible to follow."""
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        p = _patient(org_id)
        v = _triaged(org_id, p, doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id, ["LABORATORY", "PHARMACY"])
        consulting.announce_onward(v, p, steps)
        db.session.commit()

        rows = db.session.query(AppNotification).filter_by(
            template_key="go_onward").all()
        assert len(rows) == 1, "the patient should hear ONE clear instruction"
        said = rows[0].body.lower()
        assert "laboratory" in said and "pharmacy" in said
        assert "then" in said, "the order was not made clear"

        # and each desk is told to expect them
        desks = db.session.query(AppNotification).filter_by(
            template_key="desk_expecting").all()
        assert len(desks) == 2


def test_a_patient_sent_to_emergency_raises_an_emergency_call(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        p = _patient(org_id)
        v = _triaged(org_id, p, doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        _, steps = consulting.finish(v, doc.id, ["EMERGENCY"])
        consulting.announce_onward(v, p, steps)
        db.session.commit()
        assert db.session.query(AppNotification).filter_by(
            template_key="emergency_arrival").count() == 1


def test_a_finished_patient_is_told_they_can_go_home(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        p = _patient(org_id)
        v = _triaged(org_id, p, doc)
        db.session.commit()
        consulting.call_in(v, doc.id)
        consulting.finish(v, doc.id, [])
        consulting.announce_onward(v, p, [])
        db.session.commit()
        rows = db.session.query(AppNotification).filter_by(
            template_key="visit_complete").all()
        assert rows and "done for today" in rows[0].body.lower()


# ------------------------------------------------------------------ NOT an EMR
def test_onward_routing_holds_no_medical_record(app, seeded):
    """'Send to Pharmacy' is a direction to a desk, NOT a prescription."""
    banned = {"prescription", "medication", "drug", "dose", "dosage",
              "diagnosis", "symptoms", "test_type", "test_result", "result",
              "temperature", "blood_pressure", "clinical_note", "findings"}
    columns = {c.name for c in VisitOnward.__table__.columns}
    leaked = banned & columns
    assert not leaked, f"EMR field(s) appeared on onward routing: {leaked}"


# ------------------------------------------------------------------ routes
def _login_as(client, app, seeded, role="ADMIN_MANAGER"):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"], role=role).first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


def test_every_consulting_and_onward_route_answers(app, client, seeded):
    """Drives the real pages — catches view bugs the engine tests cannot see."""
    with app.app_context():
        org_id = seeded["org"]
        am = db.session.query(User).filter_by(org_id=org_id,
                                              role="ADMIN_MANAGER").first()
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=am.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT"))
        p = _patient(org_id)
        v = PatientVisit(org_id=org_id, patient_id=p.id, visit_no="V-R1",
                         visit_type="NEW", status="TRIAGED", clinic="OPD",
                         consulting_room="Room 1", doctor_id=am.id,
                         triaged_at=now_naive())
        db.session.add(v)
        db.session.commit()
        vid = v.id

    _login_as(client, app, seeded)
    assert client.get("/consulting-room").status_code == 200
    assert client.get("/onward").status_code == 200

    r = client.post(f"/consulting-room/{vid}/call-in",
                    data={"_csrf": csrf(client, "/consulting-room")},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "called in" in r.get_data(as_text=True).lower()

    r = client.post(f"/consulting-room/{vid}/finish",
                    data={"_csrf": csrf(client, "/consulting-room"),
                          "destination": ["LABORATORY", "PHARMACY"],
                          "note": "bring the card back"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "sent to" in r.get_data(as_text=True).lower()

    with app.app_context():
        steps = db.session.query(VisitOnward).all()
        assert len(steps) == 2
        first_id = steps[0].id

    board = client.get("/onward").get_data(as_text=True)
    assert "ABATAN" in board.upper()   # written register order on screen
    assert "bring the card back" in board

    r = client.post(f"/onward/{first_id}/done",
                    data={"_csrf": csrf(client, "/onward")},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "done at" in r.get_data(as_text=True).lower()

    with app.app_context():
        # one desk done, one still pending -> visit must stay open
        assert db.session.get(PatientVisit, vid).status == "ONWARD"


def test_the_old_triage_room_link_still_works(app, client, seeded):
    """Old bookmarks must not 404 after the page was superseded."""
    _login_as(client, app, seeded)
    r = client.get("/triage/consulting-room", follow_redirects=True)
    assert r.status_code == 200
    assert "call room queue" in r.get_data(as_text=True).lower()


def test_a_patient_is_called_the_SAME_name_at_every_step(app, seeded):
    """Reception says "Folake". Triage and the doctor must not say "Abatan".

    The folder is written SURNAME-first because that is how a register reads,
    but a person is CALLED by their first name. Announcing two different names
    for one patient across one visit is exactly the confusion this app exists
    to remove.
    """
    from app.models import AppNotification
    from app import reception
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        p = _patient(org_id, surname="Abatan", first="Folake")
        v = _triaged(org_id, p, doc)
        db.session.commit()

        triage.announce_placement(v, p, None)
        consulting.call_in(v, doc.id)
        consulting.announce_called_in(v, p)
        _, steps = consulting.finish(v, doc.id, ["PHARMACY"])
        consulting.announce_onward(v, p, steps)
        db.session.commit()

        spoken_to_patient = [
            r.body.lower() for r in db.session.query(AppNotification).all()
            if r.template_key in ("consult_call_in", "go_onward", "queue_assigned")
        ]
        assert spoken_to_patient, "nothing was said to the patient"
        for said in spoken_to_patient:
            assert "folake" in said, f"patient called by the wrong name: {said!r}"


# ================================================================ the live bug
# THE FOUNDER HIT THIS ON THE LIVE SITE, MINUTES AFTER DEPLOY.
#
# Triage placed three patients into clinics without naming a doctor — which is
# allowed and deliberate. The Triage board showed them as TRIAGED. But the
# doctor's call room queue matched only `doctor_id == me`, so those patients
# appeared in NOBODY's room. Three real people were stranded in the system.
#
# A doctor who is ready in Accident & Emergency must see the people waiting in
# Accident & Emergency.

def test_a_doctor_sees_unassigned_patients_waiting_in_their_clinic(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        session, err = triage.open_session(org_id, doc, "EMERGENCY",
                                           "Emergency Room")
        assert err == ""
        db.session.commit()

        # Triage places them into the clinic with NO doctor named.
        for surname in ("Baba", "Dapo"):
            p = _patient(org_id, surname, "Patient")
            v = _registered(org_id, p)
            v.status, v.doctor_id = "REGISTERED", None
            assert triage.place(v, clinic="EMERGENCY", session=None) == ""
        db.session.commit()

        queue = consulting.doctor_queue(org_id, doc.id)
        assert len(queue) == 2, (
            "patients placed in this doctor's clinic are in nobody's room — "
            "they are stranded exactly as they were on the live site")


def test_a_doctor_does_not_see_another_clinics_patients(app, seeded):
    """The fix must not swing too far and dump the whole hospital on one doctor."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        p = _patient(org_id, "Afuwape", "Sadia")
        v = _registered(org_id, p)
        triage.place(v, clinic="OPD", session=None)      # different clinic
        db.session.commit()

        assert consulting.doctor_queue(org_id, doc.id) == []


def test_a_doctor_with_no_open_room_sees_only_their_named_patients(app, seeded):
    """Not being ready must not mean seeing every unassigned patient.

    A doctor who has gone home, or has not yet clicked "ready", must not have
    the clinic's waiting room appear in their queue. The test uses TWO doctors:
    one ready, one not — so the unassigned patient genuinely exists and is
    genuinely visible to somebody, and the assertion is about who.
    """
    with app.app_context():
        org_id = seeded["org"]
        ready_doc = _doctor(org_id, "doc_ready", "Dr Ready")
        idle_doc = _doctor(org_id, "doc_idle", "Dr Idle")
        db.session.commit()
        triage.open_session(org_id, ready_doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        p = _patient(org_id)
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        db.session.commit()

        assert len(consulting.doctor_queue(org_id, ready_doc.id)) == 1, \
            "the ready doctor cannot see the waiting patient"
        assert consulting.doctor_queue(org_id, idle_doc.id) == [], \
            "a doctor with no open room was shown the clinic's waiting room"


def test_calling_in_an_unassigned_patient_claims_them(app, seeded):
    """Whoever is free takes the next patient — as in a real clinic."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        p = _patient(org_id)
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        db.session.commit()
        assert v.doctor_id is None

        assert consulting.call_in(v, doc.id) == ""
        db.session.commit()
        assert v.doctor_id == doc.id, "the patient was never claimed"
        assert v.consulting_room == "Emergency Room"
        assert v.status == "IN_CONSULTATION"


def test_two_doctors_cannot_take_the_same_waiting_patient(app, seeded):
    """A TRUE race: both doctors read the patient as free, then both claim.

    An earlier version of this test called the patient in one after the other,
    so the second doctor was stopped by the status check ("already in
    consultation") and the race guard was never exercised at all. Mutating the
    guard away left the test still passing — it proved nothing. This version
    forces the real condition: B claims while still holding a stale view of an
    unassigned patient.
    """
    with app.app_context():
        org_id = seeded["org"]
        a = _doctor(org_id, "doc_a", "Dr A")
        b = _doctor(org_id, "doc_b", "Dr B")
        db.session.commit()
        triage.open_session(org_id, a, "EMERGENCY", "Emergency Room")
        triage.open_session(org_id, b, "EMERGENCY", "Room 2")
        db.session.commit()

        p = _patient(org_id)
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        db.session.commit()

        # A wins the claim.
        assert consulting.call_in(v, a.id) == ""
        db.session.commit()
        assert v.doctor_id == a.id

        # B is mid-request, still believing the patient is unassigned and
        # still waiting — exactly what a stale open browser tab holds.
        v.doctor_id = None
        v.status = "TRIAGED"
        db.session.flush()
        # ...but the DATABASE already records A as the owner.
        db.session.execute(
            PatientVisit.__table__.update()
            .where(PatientVisit.__table__.c.id == v.id)
            .values(doctor_id=a.id))

        err = consulting.call_in(v, b.id)
        assert err, "the race guard let a second doctor steal the patient"
        assert "another doctor" in err.lower()
        db.session.commit()
        assert db.session.get(PatientVisit, v.id).doctor_id == a.id


def test_the_room_page_marks_which_patients_are_unclaimed(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        am = db.session.query(User).filter_by(org_id=org_id,
                                              role="ADMIN_MANAGER").first()
        am.must_change_password = False
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=am.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT"))
        db.session.flush()
        triage.open_session(org_id, am, "EMERGENCY", "Emergency Room")
        p = _patient(org_id, "Baba", "Omo")
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        db.session.commit()
        username = am.username

    login(client, username)
    body = client.get("/consulting-room").get_data(as_text=True)
    assert "BABA" in body.upper(), "the waiting patient is still invisible"
    assert "for the clinic" in body, "no sign this patient is unclaimed"


# ================================================================ round two
# The founder reported the SAME symptom again after the first fix. Three
# separate causes were found; each gets a test so none can come back.

def test_a_patient_placed_yesterday_still_shows_this_morning(app, seeded):
    """CAUSE 1: the queue was limited to visits started TODAY.

    A patient placed at 23:50 disappeared from the doctor's room at midnight
    while still sitting in the waiting area. An OPEN visit is open until
    somebody closes it, whatever the calendar says.
    """
    from datetime import timedelta
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        p = _patient(org_id)
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        # ...placed late last night
        v.started_at = now_naive() - timedelta(days=1, hours=2)
        v.triaged_at = now_naive() - timedelta(days=1, hours=1)
        db.session.commit()

        assert len(consulting.doctor_queue(org_id, doc.id)) == 1, (
            "a patient placed before midnight vanished from the doctor's room "
            "while still waiting in the hospital")


def test_a_consultation_started_before_midnight_is_still_in_the_room(app, seeded):
    from datetime import timedelta
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        p = _patient(org_id)
        v = _triaged(org_id, p, doc)
        consulting.call_in(v, doc.id)
        v.started_at = now_naive() - timedelta(days=1)
        db.session.commit()
        assert consulting.in_consultation(org_id, doc.id) is not None


def test_clinic_matching_tolerates_case_and_stray_spaces(app, seeded):
    """CAUSE 2: an exact string match. A patient is not seen by a comparison."""
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        p = _patient(org_id)
        v = _registered(org_id, p)
        triage.place(v, clinic="EMERGENCY", session=None)
        v.clinic = " Emergency "          # however it got in the database
        db.session.commit()

        assert len(consulting.doctor_queue(org_id, doc.id)) == 1, \
            "a clinic saved with odd casing or spacing hid the patient"
        assert consulting.call_in(v, doc.id) == "", \
            "the same patient could be seen but not called in"


def test_triage_preselects_a_free_doctor_instead_of_nobody(app, client, seeded):
    """CAUSE 3 — the root cause. The dropdown defaulted to 'wait for a doctor'.

    Busy triage staff take the default. So patients were placed with no doctor
    even when somebody was ready and idle. Defaulting to a real free doctor
    makes the safe thing the easy thing.
    """
    with app.app_context():
        org_id = seeded["org"]
        am = db.session.query(User).filter_by(org_id=org_id,
                                              role="ADMIN_MANAGER").first()
        am.must_change_password = False
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=am.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT"))
        db.session.flush()
        session, err = triage.open_session(org_id, am, "OPD", "Room 1")
        assert err == ""
        p = _patient(org_id)
        _registered(org_id, p)
        db.session.commit()
        username, sid = am.username, session.id

    login(client, username)
    body = client.get("/triage/").get_data(as_text=True)
    assert f'value="{sid}"' in body
    # the real doctor must be the pre-selected option, not "no doctor"
    marker = body[body.find(f'value="{sid}"'):][:60]
    assert "selected" in marker, \
        "Triage still defaults to leaving the patient with no doctor"


def test_no_doctor_is_still_offered_when_nobody_is_free(app, client, seeded):
    """The escape hatch must survive: sometimes truly nobody is available."""
    with app.app_context():
        org_id = seeded["org"]
        am = db.session.query(User).filter_by(org_id=org_id,
                                              role="ADMIN_MANAGER").first()
        am.must_change_password = False
        p = _patient(org_id)
        _registered(org_id, p)          # waiting, and NO doctor is ready
        db.session.commit()
        username = am.username

    login(client, username)
    body = client.get("/triage/").get_data(as_text=True)
    assert "ABATAN" in body.upper(), "the patient never reached the bench"
    # The escape hatch must always be offered, whether or not a doctor is free.
    assert "no doctor yet, place in the clinic" in body


def test_triage_offers_the_clinic_that_actually_has_a_doctor(app, seeded):
    """THE ROOT CAUSE, found by running the founder's exact scenario.

    suggest_clinic() answers "where does this KIND of patient normally go?" —
    a general adult goes to OPD. But if the only doctor on duty is sitting in
    Accident & Emergency, offering OPD pre-selects a clinic with nobody in it,
    the patient is placed with no doctor, and they wait for a room that will
    not open today. That is exactly what happened on the live site.

    The clinically sensible default is kept WHEN somebody covers it; otherwise
    Triage is offered the clinic that actually has a free doctor.
    """
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()

        adult = _patient(org_id)
        adult.category = "GENERAL"       # normally OPD
        db.session.commit()

        assert triage.suggest_clinic(adult) == "OPD"
        assert triage.suggest_clinic_with_cover(org_id, adult) == "EMERGENCY", (
            "Triage offered a clinic with no doctor in it, so the patient "
            "would be placed unassigned and wait for a room nobody opens")
        assert triage.suggest_doctor(org_id, "EMERGENCY") is not None


def test_the_clinically_right_clinic_wins_when_it_is_covered(app, seeded):
    """The cover rule must not override real clinical placement."""
    with app.app_context():
        org_id = seeded["org"]
        opd = _doctor(org_id, "doc_opd", "Dr OPD")
        emg = _doctor(org_id, "doc_emg", "Dr Emergency")
        db.session.commit()
        triage.open_session(org_id, opd, "OPD", "Room 1")
        triage.open_session(org_id, emg, "EMERGENCY", "Emergency Room")
        db.session.commit()

        adult = _patient(org_id)
        adult.category = "GENERAL"
        db.session.commit()
        assert triage.suggest_clinic_with_cover(org_id, adult) == "OPD"


def test_suggest_doctor_tolerates_odd_clinic_spelling(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        doc = _doctor(org_id)
        db.session.commit()
        triage.open_session(org_id, doc, "EMERGENCY", "Emergency Room")
        db.session.commit()
        assert triage.suggest_doctor(org_id, " emergency ") is not None
