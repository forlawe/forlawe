"""Live SLA countdown + honest on-duty tag on the complaint detail page.

Two small, deliberate behaviours:

  * /complaints/<cid>/status.json — the tiny poll that keeps an open detail
    page honest when a colleague resolves or extends the complaint from
    another screen. The countdown itself ticks client-side; this endpoint
    only re-reads the record.
  * The escalation dropdown tags the Admin Manager actually on the duty
    roster for today — the only role with real duty data — and shows no
    fake availability signal for anyone else.
"""
from datetime import timedelta

from app.models import Complaint, Department, db, new_code, now_naive
from tests.conftest import login


def _complaint(org_id, dept, *, hours_left=6.0, status="ACKNOWLEDGED"):
    now = now_naive()
    c = Complaint(org_id=org_id, ref="C" + new_code(8), department_id=dept.id,
                  category="Long waiting time",
                  description="Waited three hours and nobody said why.",
                  phone="08012345678", status=status, sla_hours=24,
                  submitted_at=now, sla_deadline_at=now + timedelta(hours=hours_left))
    db.session.add(c)
    db.session.flush()
    return c


# ================================================================ status.json
def test_status_json_reports_the_live_state(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, hours_left=3.5)
        cid = c.id
        db.session.commit()
    login(client, "hod1")                       # HOD of the seeded department
    r = client.get(f"/complaints/{cid}/status.json")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["breached"] is False
    assert 3.0 < data["hours_left"] <= 3.5
    assert data["deadline"]


def test_status_json_reports_breach_honestly(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, hours_left=-2.0)
        cid = c.id
        db.session.commit()
    login(client, "hod1")
    data = client.get(f"/complaints/{cid}/status.json").get_json()
    assert data["breached"] is True
    assert data["hours_left"] < 0


def test_status_json_hides_other_departments(app, client, seeded):
    with app.app_context():
        other = Department(org_id=seeded["org"], name="Surgical Ward")
        db.session.add(other)
        db.session.flush()
        c = _complaint(seeded["org"], other)
        cid = c.id
        db.session.commit()
    login(client, "hod1")
    # Polling must not be a way to read another department's complaint state.
    assert client.get(f"/complaints/{cid}/status.json").status_code == 403


def test_status_json_requires_login(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept)
        cid = c.id
        db.session.commit()
    r = client.get(f"/complaints/{cid}/status.json", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers.get("Location", "")


# ================================================================ detail page
def test_detail_page_renders_the_live_sla_pill(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, hours_left=3.0)
        cid = c.id
        db.session.commit()
    login(client, "hod1")
    html = client.get(f"/complaints/{cid}").data.decode()
    assert 'id="sla-pill"' in html
    assert f'data-cid="{cid}"' in html
    # The countdown polls the tiny JSON endpoint (built by the page script).
    assert "status.json" in html and "120000" in html


def test_resolved_complaint_gets_no_live_pill(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, status="RESOLVED")
        cid = c.id
        db.session.commit()
    login(client, "hod1")
    html = client.get(f"/complaints/{cid}").data.decode()
    assert 'id="sla-pill"' not in html


def test_escalation_dropdown_tags_only_the_on_duty_admin_manager(app, client, seeded):
    # conftest rosters Alice (am1) for today and Bob (am2) for tomorrow.
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, hours_left=6.0)
        cid = c.id
        db.session.commit()
    login(client, "md")
    html = client.get(f"/complaints/{cid}").data.decode()
    lines = [l for l in html.splitlines() if "on duty today" in l]
    assert lines, "the on-duty Admin Manager should be tagged in the dropdown"
    assert all("Alice Manager" in l for l in lines)
    # Bob is rostered for TOMORROW — he must not carry today's tag.
    assert all("Bob Manager" not in l for l in lines)


def test_no_roster_entry_means_no_tag(app, client, seeded):
    from app.models import DutyRoster
    with app.app_context():
        for row in db.session.query(DutyRoster).all():
            db.session.delete(row)
        db.session.flush()
        dept = db.session.get(Department, seeded["dept"])
        c = _complaint(seeded["org"], dept, hours_left=6.0)
        cid = c.id
        db.session.commit()
    login(client, "md")
    html = client.get(f"/complaints/{cid}").data.decode()
    assert "on duty today" not in html
