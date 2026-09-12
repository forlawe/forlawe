"""HOD escalation — raise a complaint upward BEFORE it times out.

The founder's words: "HOD see complaints related to their
Department/Unit/Station and be able to respond or escalate before it time out
if they want MD/CEO or any other higher authority."

Two halves. Sight (an HOD sees only their own department's complaints) and
action (they may escalate early, on purpose, with a reason).
"""
from datetime import timedelta

from app import escalation
from app import roles as R
from app.models import (AppNotification, AuditLog, Complaint, Department,
                        User, db, new_code, now_naive)
from tests.conftest import csrf, login


def _dept(org_id, name):
    d = db.session.query(Department).filter_by(org_id=org_id, name=name).first()
    if d is None:
        d = Department(org_id=org_id, name=name)
        db.session.add(d)
        db.session.flush()
    return d


def _hod(org_id, username, dept):
    u = User(org_id=org_id, username=username, name=username.title(), role="HOD",
             department_id=dept.id)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    dept.hod_user_id = u.id
    return u


def _complaint(org_id, dept, *, hours_left=6.0, status="ACKNOWLEDGED"):
    now = now_naive()
    c = Complaint(org_id=org_id, ref="C" + new_code(8), department_id=dept.id,
                  category="Long waiting time",
                  description="Waited three hours to be seen and nobody said why.",
                  phone="08012345678", status=status, sla_hours=24,
                  submitted_at=now,
                  sla_deadline_at=now + timedelta(hours=hours_left))
    db.session.add(c)
    db.session.flush()
    return c


# ================================================================ SIGHT
def test_a_hod_sees_only_their_own_departments_complaints(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        lab = _dept(org, "Laboratory")
        _hod(org, "theatrehead", theatre)
        mine = _complaint(org, theatre)
        theirs = _complaint(org, lab)
        db.session.commit()
        mine_ref, theirs_ref, theirs_id = mine.ref, theirs.ref, theirs.id

    login(client, "theatrehead")
    body = client.get("/complaints").get_data(as_text=True)
    assert mine_ref in body
    assert theirs_ref not in body, "another department's complaint leaked into the list"

    # Hiding it from the list is presentation. THIS is the security.
    assert client.get(f"/complaints/{theirs_id}").status_code == 403, \
        "an HOD reached another department's complaint by typing its id"


def test_the_md_still_sees_every_departments_complaints(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        a, b = _dept(org, "Theatre"), _dept(org, "Laboratory")
        ca, cb = _complaint(org, a), _complaint(org, b)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        md.must_change_password = False
        db.session.commit()
        refs, name = (ca.ref, cb.ref), md.username

    login(client, name)
    body = client.get("/complaints").get_data(as_text=True)
    for ref in refs:
        assert ref in body, "the MD lost sight of a department"


def test_the_list_says_out_loud_that_it_is_filtered(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        _hod(org, "notehead", _dept(org, "Theatre"))
        db.session.commit()
    login(client, "notehead")
    assert "Theatre only" in client.get("/complaints").get_data(as_text=True)


# ================================================================ ESCALATION
def test_a_hod_may_escalate_their_own_complaint_before_the_deadline(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc1", theatre)
        c = _complaint(org, theatre, hours_left=6)
        db.session.commit()
        assert escalation.may_escalate(hod, c) is True


def test_a_hod_may_not_escalate_another_departments_complaint(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        hod = _hod(org, "esc2", _dept(org, "Theatre"))
        c = _complaint(org, _dept(org, "Laboratory"))
        db.session.commit()
        assert escalation.may_escalate(hod, c) is False


def test_a_closed_complaint_cannot_be_re_opened_by_escalating_it(app, seeded):
    """Otherwise 'escalate' becomes a back door round the resolution note."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc3", theatre)
        c = _complaint(org, theatre, status="CLOSED")
        db.session.commit()
        assert escalation.may_escalate(hod, c) is False


def test_the_escalation_list_contains_only_real_people(app, seeded):
    """An escalation to an empty chair is a complaint that quietly dies."""
    with app.app_context():
        org = seeded["org"]
        people = escalation.authorities(org)
        assert people, "there was nobody to escalate to at all"
        assert all(u.active and u.org_id == org for u in people)
        assert people[0].role == "MD_CEO", "the list is not most-senior-first"
        assert all(u.role in escalation.AUTHORITY_LADDER for u in people), \
            "somebody who is not a higher authority is offered as one"


def test_escalating_early_is_recorded_as_a_decision_not_a_failure(app, seeded):
    """An HOD who spots a problem early must never be scored as one who lapsed."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc4", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, theatre, hours_left=6)
        db.session.commit()

        result = escalation.escalate(c, by_user=hod, to_user=md,
                                     reason="No budget at department level to fix the generator.")
        db.session.commit()

        assert result["in_time"] is True
        assert c.status == "ESCALATED" and c.escalated is True

        row = (db.session.query(AuditLog)
               .filter_by(org_id=org, action="COMPLAINT_ESCALATED_BY_HOD").first())
        assert row is not None, \
            "a deliberate escalation was not distinguished from an automatic timeout"
        assert "generator" in row.detail


def test_escalating_does_not_buy_the_department_more_time(app, seeded):
    """Or 'escalate' becomes the button everybody presses to clear the red light."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc5", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, theatre, hours_left=3)
        db.session.commit()
        before = c.sla_deadline_at

        escalation.escalate(c, by_user=hod, to_user=md, reason="Needs the MD.")
        db.session.commit()
        assert c.sla_deadline_at == before, "escalating silently extended the SLA"


def test_the_higher_authority_is_told_out_loud(app, seeded):
    """Voice is a standing requirement — a message nobody opens is not delivery."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc6", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, theatre, hours_left=5)
        db.session.commit()

        escalation.escalate(c, by_user=hod, to_user=md, reason="Beyond my department.")
        db.session.commit()

        said = (db.session.query(AppNotification)
                .filter_by(org_id=org, template_key="complaint_for_you").all())
        assert said, "the MD was never told out loud"
        assert said[0].user_id == md.id
        assert "Theatre" in said[0].body


def test_a_hod_is_warned_before_the_clock_runs_out_not_after(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _hod(org, "esc7", theatre)
        _complaint(org, theatre, hours_left=2)          # inside the warning window
        _complaint(org, theatre, hours_left=20)         # plenty of time, stay quiet
        db.session.commit()

        assert escalation.warn_hods_running_out(org) == 1, \
            "warned about the wrong number of complaints"
        db.session.commit()
        said = (db.session.query(AppNotification)
                .filter_by(org_id=org, template_key="complaint_running_out").all())
        assert len(said) == 1
        assert said[0].user_id == hod.id
        assert "escalate" in said[0].body.lower()


# ================================================================ THE PAGE
def test_the_escalate_form_is_on_the_page_for_the_right_hod(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        _hod(org, "page1", theatre)
        c = _complaint(org, theatre, hours_left=5)
        db.session.commit()
        cid = c.id

    login(client, "page1")
    body = client.get(f"/complaints/{cid}").get_data(as_text=True)
    assert f"/complaints/{cid}/escalate" in body
    assert "Escalate to higher authority" in body


def test_escalating_from_the_page_works_end_to_end(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        _hod(org, "page2", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, theatre, hours_left=5)
        db.session.commit()
        cid, mdid = c.id, md.id

    login(client, "page2")
    token = csrf(client, f"/complaints/{cid}")
    r = client.post(f"/complaints/{cid}/escalate",
                    data={"_csrf": token, "to_user_id": mdid,
                          "reason": "The generator has failed and I have no budget."},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Escalated to" in r.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Complaint, cid).status == "ESCALATED"


def test_an_escalation_with_no_reason_is_refused(app, client, seeded):
    """The person receiving it needs to know what they are being asked to do."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        _hod(org, "page3", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, theatre, hours_left=5)
        db.session.commit()
        cid, mdid = c.id, md.id

    login(client, "page3")
    token = csrf(client, f"/complaints/{cid}")
    client.post(f"/complaints/{cid}/escalate",
                data={"_csrf": token, "to_user_id": mdid, "reason": "no"},
                follow_redirects=True)
    with app.app_context():
        assert db.session.get(Complaint, cid).status != "ESCALATED"


def test_a_hod_cannot_escalate_another_departments_complaint_over_http(app, client, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        _hod(org, "page4", _dept(org, "Theatre"))
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        c = _complaint(org, _dept(org, "Laboratory"), hours_left=5)
        db.session.commit()
        cid, mdid = c.id, md.id

    login(client, "page4")
    token = csrf(client, "/complaints")
    r = client.post(f"/complaints/{cid}/escalate",
                    data={"_csrf": token, "to_user_id": mdid,
                          "reason": "Trying to reach a department I do not head."})
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Complaint, cid).status != "ESCALATED"
