"""Monitoring & Tracking Engine.

The single most important test in this file is
`test_a_broken_tracking_engine_never_stops_a_patient_being_seen`. Measurement
is secondary to care: if this engine breaks, the hospital must still work.
"""
from datetime import date, timedelta

import pytest

from app import tracking
from app.models import (JourneySegment, Patient, PatientVisit, RosterEntry,
                        User, db, now_naive)
from tests.conftest import csrf, login

_seq = [0]


def _patient(org_id, surname="Abatan", first="Folake"):
    _seq[0] += 1
    p = Patient(org_id=org_id, hospital_number=f"IJE/2026/{_seq[0]:05d}",
                surname=surname, first_name=first, sex="F")
    db.session.add(p)
    db.session.flush()
    return p


def _intake(org_id, surname="Abatan", first="Folake"):
    from app.models import ReceptionIntake
    _seq[0] += 1
    row = ReceptionIntake(org_id=org_id, ref=f"RCP-TEST-{_seq[0]:05d}",
                          surname=surname, first_name=first, sex="F",
                          age_years=40, payer_type="SELF", stage="RECEPTION")
    db.session.add(row)
    db.session.flush()
    return row


def _visit(org_id, patient):
    v = PatientVisit(org_id=org_id, patient_id=patient.id,
                     visit_no=f"V-{patient.id}", visit_type="NEW",
                     status="REGISTERED")
    db.session.add(v)
    db.session.flush()
    return v


def _seg(org_id, stage, minutes, *, visit_id=None, patient_id=None,
         department_id=None, staff_id=None, days_ago=0, open_ended=False):
    """A finished stretch that happened `minutes` long, `days_ago` ago."""
    entered = now_naive() - timedelta(days=days_ago, minutes=minutes)
    row = JourneySegment(org_id=org_id, stage=stage, visit_id=visit_id,
                         patient_id=patient_id, department_id=department_id,
                         staff_id=staff_id, entered_at=entered)
    if not open_ended:
        row.ended_at = entered + timedelta(minutes=minutes)
        row.seconds = minutes * 60
    db.session.add(row)
    db.session.flush()
    return row


# ================================================================ THE RULE
def test_a_broken_tracking_engine_never_stops_a_patient_being_seen(app, seeded,
                                                                   monkeypatch):
    """THE most important test here.

    A measurement bug must never stop a receptionist taking a patient in. If
    this ever fails, the engine has been wired in a way that puts statistics
    ahead of care — undo it.
    """
    def explode(*a, **kw):
        raise RuntimeError("tracking database is on fire")

    with app.app_context():
        monkeypatch.setattr(tracking, "_open_segment", explode)
        # Must return None, not raise.
        assert tracking.enter(seeded["org"], "RECEPTION", intake_id=1) is None

        monkeypatch.setattr(tracking, "open_segments", explode)
        assert tracking.leave(seeded["org"], visit_id=1) == []
        assert tracking.close_journey(seeded["org"], visit_id=1) == []


def test_reception_still_works_when_tracking_is_broken(app, client, seeded,
                                                       monkeypatch):
    """End to end proof: the desk keeps working with a dead engine."""
    from app.models import ReceptionIntake
    import app.views.reception as rv

    def explode(*a, **kw):
        raise RuntimeError("tracking is broken")

    monkeypatch.setattr(rv.tracking, "enter", explode)

    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"],
                                             role="ADMIN_MANAGER").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)

    r = client.post("/reception/new", data={
        "_csrf": csrf(client, "/reception/new"),
        "surname": "Abatan", "first_name": "Folake", "sex": "F",
        "age_years": "72", "nok_name": "Tunde", "nok_phone": "08039876543",
        "nok_relationship": "Husband", "payer_type": "SELF",
    }, follow_redirects=True)

    assert r.status_code == 200, "a tracking fault broke the reception desk"
    with app.app_context():
        assert db.session.query(ReceptionIntake).count() == 1, \
            "the patient was lost because tracking failed"


# ================================================================ writing
def test_entering_a_new_stage_closes_the_previous_one(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()

        first = tracking.enter(org_id, "RECEPTION", visit_id=v.id, patient_id=p.id)
        db.session.commit()
        assert first.is_open

        second = tracking.enter(org_id, "BILLING", visit_id=v.id, patient_id=p.id)
        db.session.commit()
        assert first.ended_at is not None, "the patient is in two places at once"
        assert first.seconds is not None
        assert second.is_open


def test_a_duration_is_never_negative(app, seeded):
    """Clocks drift. A negative duration would poison every average."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        db.session.commit()
        row = tracking.enter(org_id, "RECEPTION", patient_id=p.id)
        row.entered_at = now_naive() + timedelta(minutes=5)   # future
        tracking._close(row)
        db.session.commit()
        assert row.seconds >= 0


def test_reception_segments_are_joined_to_the_visit(app, seeded):
    """Otherwise the front half of the journey is orphaned and unmeasurable."""
    with app.app_context():
        org_id = seeded["org"]
        intake = _intake(org_id)
        db.session.commit()
        tracking.enter(org_id, "RECEPTION", intake_id=intake.id)
        tracking.enter(org_id, "BILLING", intake_id=intake.id)
        db.session.commit()

        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        tracking.attach_visit(org_id, intake.id, v.id, p.id)
        db.session.commit()

        rows = tracking.journey_for(org_id, v.id)
        assert len(rows) == 2
        assert all(r.patient_id == p.id for r in rows)


def test_closing_a_journey_leaves_nothing_open(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        tracking.enter(org_id, "LABORATORY", visit_id=v.id, patient_id=p.id)
        tracking.enter(org_id, "PHARMACY", visit_id=v.id, patient_id=p.id,
                       close_previous=False)
        db.session.commit()
        assert len(tracking.open_segments(org_id, visit_id=v.id)) == 2

        tracking.close_journey(org_id, visit_id=v.id)
        db.session.commit()
        assert tracking.open_segments(org_id, visit_id=v.id) == []


def test_an_unknown_stage_is_refused_not_stored(app, seeded):
    with app.app_context():
        assert tracking.enter(seeded["org"], "NOT_A_REAL_STAGE", intake_id=1) is None


# ================================================================ the maths
def test_door_to_door_is_wall_clock_not_the_sum_of_parts(app, seeded):
    """Summing parts drops the walking and queueing between desks."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        start = now_naive() - timedelta(minutes=100)
        a = JourneySegment(org_id=org_id, stage="RECEPTION", visit_id=v.id,
                           entered_at=start,
                           ended_at=start + timedelta(minutes=10), seconds=600)
        # 60-minute gap the patient really experienced but nobody logged
        b = JourneySegment(org_id=org_id, stage="PHARMACY", visit_id=v.id,
                           entered_at=start + timedelta(minutes=70),
                           ended_at=start + timedelta(minutes=100), seconds=1800)
        db.session.add_all([a, b])
        db.session.commit()

        segments = tracking.journey_for(org_id, v.id)
        assert tracking.total_minutes(segments) == 100, \
            "the gap between desks was silently dropped"


def test_the_median_is_reported_because_one_outlier_ruins_an_average(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(5):
            _seg(org_id, "PHARMACY", 10)
        _seg(org_id, "PHARMACY", 300)          # one forgotten patient
        db.session.commit()

        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "PHARMACY")
        assert row["median"] == 10, "the median was dragged by one outlier"
        assert row["average"] > row["median"], "the mean should show the skew"


def test_impossible_durations_are_excluded_from_averages(app, seeded):
    """A desk that forgot to tick someone off must not poison the figures."""
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(5):
            _seg(org_id, "LABORATORY", 20)
        _seg(org_id, "LABORATORY", 60 * 20)     # 20 hours — not real
        db.session.commit()

        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "LABORATORY")
        assert row["count"] == 5, "an impossible 20-hour stretch was counted"
        assert row["median"] == 20


def test_too_little_data_is_admitted_not_guessed(app, seeded):
    """Three patients is an anecdote, not a measurement."""
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(3):
            _seg(org_id, "TRIAGE", 12)
        db.session.commit()
        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "TRIAGE")
        assert row["reliable"] is False
        assert row["rating"] == "TOO FEW"


def test_an_open_segment_is_not_counted_as_finished(app, seeded):
    """Guessing a duration for someone still standing there flatters the numbers."""
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(5):
            _seg(org_id, "PHARMACY", 10)
        _seg(org_id, "PHARMACY", 90, open_ended=True)
        db.session.commit()
        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "PHARMACY")
        assert row["count"] == 5


def test_a_slow_stage_is_named_in_plain_english(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "PHARMACY", 90)        # target is 20
        db.session.commit()
        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "PHARMACY")
        assert row["rating"] == "HOLDING EVERYONE UP"


def test_a_fast_stage_is_praised(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "RECEPTION", 4)        # target is 10
        db.session.commit()
        row = next(s for s in tracking.stage_performance(org_id, 7)
                   if s["stage"] == "RECEPTION")
        assert row["rating"] == "EXCELLENT"


def test_the_time_window_is_respected(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(5):
            _seg(org_id, "TRIAGE", 10, days_ago=0)
        for _ in range(5):
            _seg(org_id, "TRIAGE", 90, days_ago=40)
        db.session.commit()
        recent = next(s for s in tracking.stage_performance(org_id, 7)
                      if s["stage"] == "TRIAGE")
        assert recent["count"] == 5 and recent["median"] == 10


# ================================================================ live board
def test_the_live_board_shows_who_is_waiting_and_flags_the_stuck(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id, "Waiting", "Long")
        db.session.commit()
        _seg(org_id, "PHARMACY", 120, patient_id=p.id, open_ended=True)
        db.session.commit()

        board = tracking.live_board(org_id)
        assert len(board) == 1
        assert board[0]["stuck"] is True, "a 2-hour pharmacy wait was not flagged"
        assert board[0]["waited"] >= 119


def test_a_patient_who_clearly_went_home_is_flagged_separately(app, seeded):
    """Not hidden — a genuinely abandoned patient must still be visible."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        db.session.commit()
        _seg(org_id, "PHARMACY", 60 * 12, patient_id=p.id, open_ended=True)
        db.session.commit()
        board = tracking.live_board(org_id)
        assert board[0]["abandoned"] is True


# ================================================================ advice
def test_advice_is_given_in_plain_english(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "PHARMACY", 120)
        db.session.commit()
        tips = tracking.suggest_allocation(org_id)
        assert any("Pharmacy" in t for t in tips)
        assert all(not t.startswith("{") for t in tips), "advice must not be jargon"


def test_a_quiet_hospital_is_told_it_is_fine(app, seeded):
    with app.app_context():
        tips = tracking.suggest_allocation(seeded["org"])
        assert any("flowing well" in t for t in tips)


def test_uneven_doctor_load_produces_a_suggestion(app, seeded):
    from app import triage
    with app.app_context():
        org_id = seeded["org"]
        busy = User(org_id=org_id, username="doc_busy", name="Dr Busy", role="HOD")
        busy.set_password("Passw0rd!x")
        free = User(org_id=org_id, username="doc_free", name="Dr Free", role="HOD")
        free.set_password("Passw0rd!x")
        db.session.add_all([busy, free])
        db.session.flush()
        # Use now_naive().date() not date.today() — timezone safe (Lagos vs UTC)
        duty_day = now_naive().date()
        for u in (busy, free):
            db.session.add(RosterEntry(org_id=org_id, duty_date=duty_day,
                                       user_id=u.id, kind="DUTY", shift="DAY",
                                       scope="DEPARTMENT"))
        db.session.flush()
        triage.open_session(org_id, busy, "OPD", "Room 1", day=duty_day)
        triage.open_session(org_id, free, "OPD", "Room 2", day=duty_day)
        for i in range(4):
            p = _patient(org_id, f"Load{i}", "X")
            v = _visit(org_id, p)
            v.status = "TRIAGED"
            v.doctor_id = busy.id
        db.session.commit()

        tips = tracking.suggest_allocation(org_id)
        assert any("Dr Free" in t for t in tips), tips


# ================================================================ headline
def test_the_headline_counts_only_finished_visits(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        done_p = _patient(org_id, "Done", "P")
        done_v = _visit(org_id, done_p)
        still_p = _patient(org_id, "Still", "P")
        still_v = _visit(org_id, still_p)
        db.session.commit()
        _seg(org_id, "RECEPTION", 30, visit_id=done_v.id, patient_id=done_p.id)
        _seg(org_id, "PHARMACY", 30, visit_id=still_v.id, patient_id=still_p.id,
             open_ended=True)
        db.session.commit()

        head = tracking.headline(org_id, 7)
        assert head["patients_completed"] == 1
        assert head["in_hospital_now"] == 1


def test_the_trend_shows_week_on_week(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        _seg(org_id, "RECEPTION", 20, visit_id=v.id, patient_id=p.id)
        db.session.commit()
        weeks = tracking.trend(org_id, 4)
        assert len(weeks) == 4
        assert weeks[-1]["patients"] >= 1, "this week's data is missing"


# ================================================================ NOT an EMR
def test_journey_tracking_holds_no_medical_record(app, seeded):
    banned = {"diagnosis", "symptoms", "temperature", "blood_pressure",
              "pulse", "weight", "glucose", "reading", "result", "test_result",
              "prescription", "medication", "complaint", "findings", "notes"}
    columns = {c.name for c in JourneySegment.__table__.columns}
    leaked = banned & columns
    assert not leaked, f"EMR field(s) appeared on journey tracking: {leaked}"


# ================================================================ routes
def _login(client, app, seeded, role="ADMIN_MANAGER"):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"], role=role).first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


def test_the_dashboard_answers_even_with_no_data_at_all(app, client, seeded):
    """A brand-new hospital must see an empty dashboard, not a crash."""
    _login(client, app, seeded)
    r = client.get("/tracking")
    assert r.status_code == 200
    assert "not enough" in r.get_data(as_text=True).lower()


def test_the_dashboard_shows_real_figures(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "PHARMACY", 45)
        db.session.commit()
    _login(client, app, seeded)
    body = client.get("/tracking").get_data(as_text=True)
    assert "Pharmacy" in body
    assert "0:45m" in body


def test_one_patients_journey_page_works(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        _seg(org_id, "RECEPTION", 12, visit_id=v.id, patient_id=p.id)
        _seg(org_id, "TRIAGE", 8, visit_id=v.id, patient_id=p.id)
        db.session.commit()
        vid = v.id
    _login(client, app, seeded)
    r = client.get(f"/tracking/patient/{vid}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Reception" in body and "Triage" in body


def test_a_journey_from_another_hospital_is_refused(app, client, seeded):
    """Multi-tenant: one hospital must never read another's patients."""
    from app.models import Organization
    with app.app_context():
        other = Organization(code="OTHER", name="Other Hospital")
        db.session.add(other)
        db.session.flush()
        p = Patient(org_id=other.id, hospital_number="OTH/1", surname="Not",
                    first_name="Yours", sex="F")
        db.session.add(p)
        db.session.flush()
        v = PatientVisit(org_id=other.id, patient_id=p.id, visit_no="V-X",
                         visit_type="NEW", status="REGISTERED")
        db.session.add(v)
        db.session.commit()
        vid = v.id
    _login(client, app, seeded)
    assert client.get(f"/tracking/patient/{vid}").status_code == 404


def test_a_hostile_time_window_cannot_hang_the_page(app, client, seeded):
    _login(client, app, seeded)
    assert client.get("/tracking?days=999999").status_code == 200
    assert client.get("/tracking?days=-5").status_code == 200
    assert client.get("/tracking?days=abc").status_code == 200


def test_the_csv_export_downloads(app, client, seeded):
    with app.app_context():
        for _ in range(5):
            _seg(seeded["org"], "TRIAGE", 15)
        db.session.commit()
    _login(client, app, seeded)
    r = client.get("/tracking/export?days=7")
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]
    assert "median_minutes" in r.get_data(as_text=True)


# ================================================================ the leak
def test_no_segment_is_left_open_when_a_visit_closes(app, client, seeded):
    """A patient who has gone home must not show as waiting forever.

    THE BUG THIS CATCHES (found by walking a real patient through, not by a
    unit test): the folder was created and `visit.id` was still None because
    the session had not been flushed, so the Reception half of the journey was
    linked to visit_id=None. The HIMS segment was therefore never closed, and
    the live board showed the patient standing at HIMS all day — long after she
    had gone home.
    """
    from app.models import ReceptionIntake
    with app.app_context():
        org_id = seeded["org"]
        u = db.session.query(User).filter_by(org_id=org_id,
                                             role="ADMIN_MANAGER").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)

    client.post("/reception/new", data={
        "_csrf": csrf(client, "/reception/new"),
        "surname": "Abatan", "first_name": "Folake", "sex": "F",
        "age_years": "72", "nok_name": "Tunde", "nok_phone": "08039876543",
        "nok_relationship": "Husband", "payer_type": "SELF",
    }, follow_redirects=True)

    with app.app_context():
        iid = db.session.query(ReceptionIntake).one().id
    for step in ("to-billing", "to-payment", "paid"):
        client.post(f"/reception/{iid}/{step}",
                    data={"_csrf": csrf(client, "/reception/")},
                    follow_redirects=True)
    client.post(f"/reception/{iid}/open-folder",
                data={"_csrf": csrf(client, "/reception/")},
                follow_redirects=True)

    with app.app_context():
        org_id = seeded["org"]
        visit = db.session.query(PatientVisit).one()

        # Every early segment must now belong to the visit...
        orphans = (db.session.query(JourneySegment)
                   .filter(JourneySegment.org_id == org_id,
                           JourneySegment.visit_id.is_(None)).count())
        assert orphans == 0, (
            "Reception segments were never linked to the visit — the front "
            "half of the journey is unmeasurable and will never close")

        # ...and only ONE (where she is standing now) may be open.
        open_rows = (db.session.query(JourneySegment)
                     .filter(JourneySegment.org_id == org_id,
                             JourneySegment.ended_at.is_(None)).all())
        assert len(open_rows) == 1, (
            f"{len(open_rows)} segments left open: "
            f"{[r.stage for r in open_rows]} — the patient will appear to be "
            f"in two places at once")
        assert open_rows[0].stage == "TRIAGE"

        # And the whole journey is measurable door to door.
        segments = tracking.journey_for(org_id, visit.id)
        assert len(segments) >= 4, "the front half of the journey is missing"
        assert {s.stage for s in segments} >= {"RECEPTION", "BILLING",
                                               "PAYMENT", "HIMS", "TRIAGE"}


def test_open_segments_matches_on_any_identifier(app, seeded):
    """Early rows carry only an intake id; later rows carry a visit id."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        intake = _intake(org_id)
        db.session.commit()
        early = tracking.enter(org_id, "RECEPTION", intake_id=intake.id)
        later = tracking.enter(org_id, "TRIAGE", visit_id=v.id,
                               close_previous=False)
        db.session.commit()

        found = tracking.open_segments(org_id, intake_id=intake.id, visit_id=v.id)
        assert {r.id for r in found} == {early.id, later.id}, \
            "a journey spanning intake and visit ids was only half-closed"


def test_a_failed_tracking_write_does_not_poison_the_transaction(app, seeded):
    """FOUND ON REAL POSTGRESQL — it could never have shown up on SQLite.

    PostgreSQL aborts the WHOLE transaction when any statement fails and then
    refuses every later statement until it is rolled back. So catching a
    tracking error was not enough: the caller's transaction was already
    poisoned, and the patient work that came AFTER our failure would die too —
    the desk would break for a reason nobody could see.

    A savepoint contains the damage. This proves it: we force a bad tracking
    write, then do real patient work in the SAME session and require it to
    succeed and persist.
    """
    from app.models import ReceptionIntake
    with app.app_context():
        org_id = seeded["org"]

        # A tracking write the database may reject (no such intake).
        # SQLite does not enforce foreign keys by default and will accept it;
        # PostgreSQL rejects it. EITHER outcome is fine — what must never
        # happen is the caller's transaction being left unusable afterwards.
        tracking.enter(org_id, "RECEPTION", intake_id=999_999)

        # The session must still be usable for REAL patient work.
        intake = ReceptionIntake(org_id=org_id, ref="RCP-AFTER-FAIL",
                                 surname="Still", first_name="Works", sex="F",
                                 age_years=30, payer_type="SELF",
                                 stage="RECEPTION")
        db.session.add(intake)
        db.session.commit()

        saved = (db.session.query(ReceptionIntake)
                 .filter_by(ref="RCP-AFTER-FAIL").one_or_none())
        assert saved is not None, (
            "a failed tracking write poisoned the transaction and the patient "
            "was lost — the savepoint is missing or broken")


# ================================================================ voice + cleanup
# Voice is a standing requirement of EVERY feature. A dashboard nobody opens is
# a dashboard nobody acts on, so the engine speaks about the two things worth
# interrupting a working day for — and stays quiet otherwise.
def test_a_forgotten_patient_is_spoken_about(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id, "Abatan", "Folake")
        db.session.commit()
        _seg(org_id, "PHARMACY", 90, patient_id=p.id, open_ended=True)
        db.session.commit()

        assert tracking.announce_forgotten(org_id) == 1
        db.session.commit()
        rows = db.session.query(AppNotification).filter_by(
            template_key="patient_forgotten").all()
        assert rows, "nobody was told about the forgotten patient"
        assert "1 hour 30 minutes" in rows[0].body
        # ...and by the name she is actually CALLED, not register order.
        assert "folake" in rows[0].body.lower(), rows[0].body
        assert "abatan" not in rows[0].body.lower(), \
            "announced by surname — inconsistent with every other stage"


def test_a_department_holding_everyone_up_is_spoken_about(app, seeded):
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "PHARMACY", 120)      # target 20
        db.session.commit()
        assert tracking.announce_bottleneck(org_id, days=7) == 1
        db.session.commit()
        rows = db.session.query(AppNotification).filter_by(
            template_key="flow_bottleneck").all()
        assert rows and "Pharmacy" in rows[0].body


def test_the_engine_stays_quiet_when_nothing_is_wrong(app, seeded):
    """An alert that fires constantly is ignored within a week."""
    from app.models import AppNotification
    with app.app_context():
        org_id = seeded["org"]
        for _ in range(6):
            _seg(org_id, "PHARMACY", 5)        # well inside target
        db.session.commit()
        assert tracking.announce_bottleneck(org_id, days=7) == 0
        assert tracking.announce_forgotten(org_id) == 0
        db.session.commit()
        assert db.session.query(AppNotification).filter(
            AppNotification.template_key.in_(
                ("flow_bottleneck", "patient_forgotten"))).count() == 0


def test_abandoned_stretches_are_closed_with_an_HONEST_unknown_duration(app, seeded):
    """A desk forgot to press done. Guessing a duration corrupts every average."""
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        db.session.commit()
        _seg(org_id, "PHARMACY", 60 * 20, patient_id=p.id, open_ended=True)
        db.session.commit()

        assert tracking.close_abandoned(org_id) == 1
        db.session.commit()
        row = db.session.query(JourneySegment).one()
        assert row.ended_at is not None, "the ghost is still on the live board"
        assert row.seconds is None, \
            "a duration was invented for a patient nobody measured"


def test_cleanup_does_not_touch_a_patient_who_is_genuinely_still_there(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        db.session.commit()
        _seg(org_id, "PHARMACY", 30, patient_id=p.id, open_ended=True)
        db.session.commit()
        assert tracking.close_abandoned(org_id) == 0
        assert db.session.query(JourneySegment).one().ended_at is None


def test_the_scheduler_runs_the_flow_job_without_breaking_the_others(app, seeded):
    """A fault measuring one hospital must not stop the rest of automation."""
    from app.scheduler import JOB_SEQUENCE, job_patient_flow
    assert job_patient_flow in JOB_SEQUENCE, \
        "the flow job never runs, so nothing is ever cleaned up or announced"
    with app.app_context():
        job_patient_flow(app)          # empty hospital must not raise


def test_the_flow_job_survives_a_broken_tracking_engine(app, seeded, monkeypatch):
    from app.scheduler import job_patient_flow
    from app import tracking as t

    def explode(*a, **kw):
        raise RuntimeError("statistics are on fire")

    monkeypatch.setattr(t, "close_abandoned", explode)
    with app.app_context():
        job_patient_flow(app)          # must not raise


# ================================================================ visibility
def test_the_main_dashboard_shows_patient_flow(app, client, seeded):
    """A dashboard behind another menu is a dashboard nobody opens."""
    with app.app_context():
        for _ in range(6):
            _seg(seeded["org"], "TRIAGE", 12)
        db.session.commit()
    _login(client, app, seeded)
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Patient flow" in body
    assert "/tracking" in body


def test_the_dashboard_survives_a_broken_flow_summary(app, client, seeded,
                                                      monkeypatch):
    """Statistics must never take down the front page for everyone."""
    from app import tracking as t

    def explode(*a, **kw):
        raise RuntimeError("statistics are on fire")

    # main.py imports tracking inside the view, so patch the module itself.
    monkeypatch.setattr(t, "headline", explode)
    _login(client, app, seeded)
    assert client.get("/dashboard").status_code == 200


def test_a_folder_links_to_the_journey_of_each_visit(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _patient(org_id)
        v = _visit(org_id, p)
        db.session.commit()
        pid, vid = p.id, v.id
    _login(client, app, seeded)
    body = client.get(f"/hims/folder/{pid}").get_data(as_text=True)
    assert f"/tracking/patient/{vid}" in body, \
        "no way to get from a patient's folder to their journey"
