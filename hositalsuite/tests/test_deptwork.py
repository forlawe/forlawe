"""The department desk: scoped sight, honest efficiency, and real teamwork.

Covers the founder's items ii and iii:
  * an HOD/staff member sees ONLY their own department
  * efficiency is measured against the patient flow INTO the department, daily
  * several staff can work at once — on the same task or different ones
"""
from datetime import timedelta

from app import deptwork
from app import roles as R
from app.models import (Department, JourneySegment, Patient, User, WorkClaim,
                        db, now_naive)
from tests.conftest import csrf, login


def _dept(org_id, name):
    d = db.session.query(Department).filter_by(org_id=org_id, name=name).first()
    if d is None:
        d = Department(org_id=org_id, name=name)
        db.session.add(d)
        db.session.flush()
    return d


def _staff(org_id, username, dept, role="STAFF"):
    u = User(org_id=org_id, username=username, name=username.title(), role=role,
             department_id=dept.id if dept else None)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


def _seg(org_id, dept, *, minutes=None, staff=None, hours_ago=1):
    # Use midday today to avoid midnight edge where Lagos date rolls over
    # but hours_ago pushes into yesterday (Africa/Lagos timezone).
    base = now_naive().replace(hour=12, minute=0, second=0, microsecond=0)
    if hours_ago == 1:
        start = base
    else:
        start = now_naive() - timedelta(hours=hours_ago)
        # If that falls outside today bounds, clamp to today midday
        from app.deptwork import _today_bounds as _tb
        s, e = _tb()
        if not (s <= start <= e):
            start = base
    row = JourneySegment(org_id=org_id, department_id=dept.id, stage="PHARMACY",
                         entered_at=start,
                         staff_id=staff.id if staff else None)
    if minutes is not None:
        row.ended_at = start + timedelta(minutes=minutes)
        row.seconds = minutes * 60
    db.session.add(row)
    db.session.flush()
    return row


# ================================================================ FLOW TODAY
def test_the_department_sees_todays_flow_to_itself_only(app, seeded):
    with app.app_context():
        org = seeded["org"]
        pharm = _dept(org, "Pharmacy")
        lab = _dept(org, "Laboratory")
        for _ in range(6):
            _seg(org, pharm, minutes=10)
        for _ in range(4):
            _seg(org, lab, minutes=50)
        db.session.commit()

        flow = deptwork.flow_today(org, pharm.id)
        assert flow["arrived"] == 6, "another department's patients leaked in"
        assert flow["handled"] == 6
        assert flow["median_minutes"] == 10


def test_a_quiet_department_is_told_so_not_shown_zero_per_cent(app, seeded):
    with app.app_context():
        org = seeded["org"]
        empty = _dept(org, "Physiotherapy")
        db.session.commit()
        flow = deptwork.flow_today(org, empty.id)
        assert flow["arrived"] == 0
        assert "Nothing has come" in flow["verdict"]
        assert "0%" not in flow["verdict"]


def test_too_few_patients_is_never_reported_as_a_confident_number(app, seeded):
    """Three patients is an anecdote, not a measurement."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Records")
        for _ in range(3):
            _seg(org, d, minutes=5)
        db.session.commit()
        flow = deptwork.flow_today(org, d.id)
        assert flow["reliable"] is False
        assert "too early to say" in flow["verdict"]


def test_a_department_falling_behind_is_told_plainly(app, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Busy Clinic")
        for _ in range(2):
            _seg(org, d, minutes=10)
        for _ in range(8):
            _seg(org, d, minutes=None)          # still standing there
        db.session.commit()
        flow = deptwork.flow_today(org, d.id)
        assert flow["still_here"] == 8
        assert "falling behind" in flow["verdict"]


def test_patients_still_waiting_never_flatter_the_average(app, seeded):
    """An open stretch has no duration yet. Guessing one would lie."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Dressing Room")
        for _ in range(5):
            _seg(org, d, minutes=20)
        _seg(org, d, minutes=None, hours_ago=3)   # 3h and counting, still open
        db.session.commit()
        flow = deptwork.flow_today(org, d.id)
        assert flow["average_minutes"] == 20, \
            "an unfinished patient was counted in the average"
        assert flow["arrived"] == 6 and flow["handled"] == 5


def test_yesterdays_work_is_not_counted_as_todays(app, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Old Clinic")
        for _ in range(5):
            _seg(org, d, minutes=10)
        old = _seg(org, d, minutes=10)
        old.entered_at = now_naive() - timedelta(days=2)
        db.session.commit()
        assert deptwork.flow_today(org, d.id)["arrived"] == 5


# ================================================================ EFFORT
def test_effort_is_reported_as_workload_and_never_ranked(app, seeded):
    """Sorting by output turns a list into a ranking whatever you label it."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Ward A")
        zainab = _staff(org, "zainab", d)
        adamu = _staff(org, "adamu", d)
        for _ in range(9):
            _seg(org, d, minutes=5, staff=adamu)
        for _ in range(2):
            _seg(org, d, minutes=45, staff=zainab)
        db.session.commit()

        effort = deptwork.staff_effort_today(org, d.id)
        names = [e["name"] for e in effort]
        assert names == sorted(names), \
            "the list is sorted by output — that is a league table"
        z = next(e for e in effort if e["name"] == "Zainab")
        assert z["reliable"] is False, \
            "two patients were reported as a confident average"


def test_effort_only_counts_this_department(app, seeded):
    with app.app_context():
        org = seeded["org"]
        a, b = _dept(org, "Ward B"), _dept(org, "Ward C")
        u = _staff(org, "shared1", a)
        for _ in range(5):
            _seg(org, a, minutes=10, staff=u)
        for _ in range(5):
            _seg(org, b, minutes=10, staff=u)
        db.session.commit()
        rows = deptwork.staff_effort_today(org, a.id)
        assert rows[0]["patients"] == 5


# ================================================================ TEAMWORK
def test_several_staff_can_work_the_same_task_at_the_same_time(app, seeded):
    """The whole point. A lock here would be software telling a ward how to nurse."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Front Desk")
        a, b, c = (_staff(org, f"clerk{i}", d) for i in range(3))
        db.session.commit()

        r1, o1 = deptwork.claim(org, a, "RECEPTION", department_id=d.id)
        r2, o2 = deptwork.claim(org, b, "RECEPTION", department_id=d.id)
        r3, o3 = deptwork.claim(org, c, "RECEPTION", department_id=d.id)
        db.session.commit()

        assert r2 is not None and r3 is not None, "a colleague was refused"
        assert len(o3) == 2, "the third worker was not told who else was on it"
        assert len(deptwork.open_claims(org, d.id)) == 3


def test_two_staff_can_work_different_tasks_in_one_department(app, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Pharmacy Store")
        a, b = _staff(org, "pha", d), _staff(org, "phb", d)
        db.session.commit()
        deptwork.claim(org, a, "PHARMACY", department_id=d.id)
        deptwork.claim(org, b, "CLEANING", department_id=d.id)
        db.session.commit()
        kinds = {c.kind for c in deptwork.open_claims(org, d.id)}
        assert kinds == {"PHARMACY", "CLEANING"}


def test_the_same_person_cannot_double_count_their_own_effort(app, seeded):
    """A double-tap on a phone is not a second worker."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Lab Bench")
        u = _staff(org, "labtech", d)
        db.session.commit()
        first, _ = deptwork.claim(org, u, "LABORATORY", department_id=d.id)
        again, _ = deptwork.claim(org, u, "LABORATORY", department_id=d.id)
        db.session.commit()
        assert first.id == again.id
        assert len(deptwork.open_claims(org, d.id)) == 1


def test_joining_a_task_speaks_to_the_people_already_on_it(app, seeded):
    """Voice is a standing requirement, and silent help is help nobody knows about."""
    from app.models import AppNotification
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Triage Bench")
        a, b = _staff(org, "nursea", d), _staff(org, "nurseb", d)
        db.session.commit()
        deptwork.claim(org, a, "TRIAGE", department_id=d.id)
        deptwork.claim(org, b, "TRIAGE", department_id=d.id)
        db.session.commit()

        said = (db.session.query(AppNotification)
                .filter_by(org_id=org, template_key="colleague_joined").all())
        assert said, "nobody was told a colleague had joined them"
        assert said[0].user_id == a.id
        assert "Nurseb" in said[0].body and "called twice" in said[0].body


def test_stepping_off_records_how_long_you_were_on_it(app, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Store")
        u = _staff(org, "storeman", d)
        db.session.commit()
        row, _ = deptwork.claim(org, u, "OTHER", department_id=d.id)
        row.started_at = now_naive() - timedelta(minutes=25)
        deptwork.release(row)
        db.session.commit()
        assert row.ended_at is not None
        assert 24 <= row.minutes <= 26


def test_a_forgotten_claim_is_closed_with_an_honestly_unknown_time(app, seeded):
    """Guessing a duration would quietly corrupt every average on the screen."""
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Night Ward")
        u = _staff(org, "nightnurse", d)
        db.session.commit()
        row, _ = deptwork.claim(org, u, "OTHER", department_id=d.id)
        row.started_at = now_naive() - timedelta(hours=20)
        db.session.commit()

        assert deptwork.close_forgotten_claims(org) == 1
        db.session.commit()
        assert row.ended_at is not None
        assert row.seconds is None, "a duration was invented for a forgotten claim"


# ================================================================ THE PAGE
def test_a_staff_member_sees_only_their_own_departments_desk(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        pharm = _dept(org, "Pharmacy")
        lab = _dept(org, "Laboratory")
        _staff(org, "pharmstaff", pharm)
        R.ensure_builtin_roles(org)
        db.session.commit()
        lab_id = lab.id

    login(client, "pharmstaff")
    body = client.get("/my-department").get_data(as_text=True)
    assert "Pharmacy" in body
    # Check the department SWITCHER, not the whole page: "Laboratory" also
    # appears innocently in the work-kind dropdown ("Laboratory work"), and a
    # bare substring check on the body passed for the wrong reason.
    switcher = body[:body.find("Came here today")]
    assert "/my-department?dept=" not in switcher or f"dept={lab_id}" not in switcher, \
        "another department leaked into the switcher"

    # And a guessed id must not be a way round the whole feature.
    assert client.get(f"/my-department?dept={lab_id}").status_code == 403


def test_the_page_says_out_loud_what_it_is_hiding(app, client, seeded):
    """A short list must never be ambiguous between 'quiet' and 'hidden'."""
    with app.app_context():
        org = seeded["org"]
        _staff(org, "notestaff", _dept(org, "Pharmacy"))
        R.ensure_builtin_roles(org)
        db.session.commit()
    login(client, "notestaff")
    body = client.get("/my-department").get_data(as_text=True)
    assert "Pharmacy only" in body or "your own department" in body


def test_staff_with_no_department_are_told_why_the_page_is_empty(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        _staff(org, "nodept", None)
        R.ensure_builtin_roles(org)
        db.session.commit()
    login(client, "nodept")
    body = client.get("/my-department").get_data(as_text=True)
    assert "No department has been set" in body


def test_claiming_work_from_the_page_works_and_shows_the_others(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Pharmacy")
        _staff(org, "worker1", d)
        other = _staff(org, "worker2", d)
        R.ensure_builtin_roles(org)
        db.session.commit()
        deptwork.claim(org, other, "PHARMACY", department_id=d.id)
        db.session.commit()
        did = d.id

    login(client, "worker1")
    token = csrf(client, "/my-department")
    r = client.post("/my-department/claim",
                    data={"_csrf": token, "kind": "PHARMACY",
                          "department_id": did},
                    follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Worker2" in body and "already on it" in body


def test_you_cannot_wipe_a_colleagues_record_of_their_own_work(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        d = _dept(org, "Pharmacy")
        _staff(org, "junior1", d)
        other = _staff(org, "junior2", d)
        R.ensure_builtin_roles(org)
        db.session.commit()
        row, _ = deptwork.claim(org, other, "PHARMACY", department_id=d.id)
        db.session.commit()
        cid = row.id

    login(client, "junior1")
    token = csrf(client, "/my-department")
    r = client.post(f"/my-department/claim/{cid}/done", data={"_csrf": token})
    assert r.status_code == 403


def test_a_staff_member_cannot_reach_the_role_admin_screen(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        _staff(org, "curious1", _dept(org, "Pharmacy"))
        R.ensure_builtin_roles(org)
        db.session.commit()
    login(client, "curious1")
    for path in ("/admin/roles", "/admin/roles/assign", "/admin"):
        assert client.get(path).status_code == 403, f"{path} was reachable"
