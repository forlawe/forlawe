"""Menu visibility per role.

REPORTED FROM THE LIVE SITE: "When I login as HOD Adenira of Theater I still
see the System Admin menus."

Hiding a link is presentation, not security — every route still enforces its
own role check. But the menu and the routes must agree, or staff either see
doors they cannot open or miss doors they need.
"""
from app.models import Department, User, db
from app.navigation import permissions_for
from tests.conftest import login


def _user(org_id, username, role, dept_name=None):
    dept = None
    if dept_name:
        dept = (db.session.query(Department)
                .filter_by(org_id=org_id, name=dept_name).first())
        if dept is None:
            dept = Department(org_id=org_id, name=dept_name)
            db.session.add(dept)
            db.session.flush()
    u = User(org_id=org_id, username=username, name=username.title(),
             role=role, department_id=dept.id if dept else None)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


# ------------------------------------------------------------------ the report
def test_a_clinical_hod_does_not_get_the_administrators_menu(app, seeded):
    """The exact report: HOD of Theatre seeing System Administrator menus."""
    with app.app_context():
        hod = _user(seeded["org"], "adenira", "HOD", "Theatre")
        db.session.commit()
        can = permissions_for(hod)

        assert can["admin"] is False, "an HOD could reach the admin settings"
        assert can["inspections"] is False, \
            "an HOD got the Admin Manager's hospital-wide inspection tool"
        assert can["cashdesk"] is False, \
            "the HOD of Theatre could work the money desks"
        assert can["reception"] is False
        assert can["hims"] is False


def test_a_clinical_hod_still_gets_what_they_actually_do(app, seeded):
    """Least privilege must never get in the way of seeing a patient."""
    with app.app_context():
        hod = _user(seeded["org"], "adenira2", "HOD", "Theatre")
        db.session.commit()
        can = permissions_for(hod)

        assert can["consulting"] is True, "an HOD lost their own consulting room"
        assert can["roster"] is True, "an HOD could not check their own duty"
        assert can["complaints"] is True
        assert can["tracking"] is True


def test_the_hims_hod_runs_the_hims_desk(app, seeded):
    """Front-desk work is granted by DEPARTMENT, not by rank."""
    with app.app_context():
        hims_hod = _user(seeded["org"], "hodhims", "HOD",
                         "Health Information Management")
        db.session.commit()
        can = permissions_for(hims_hod)
        assert can["hims"] is True
        assert can["reception"] is True
        assert can["admin"] is False, "still not an administrator"


def test_the_finance_hod_runs_the_money_desks_and_nothing_more(app, seeded):
    with app.app_context():
        money = _user(seeded["org"], "hodfin", "HOD", "Finance & Accounts")
        db.session.commit()
        can = permissions_for(money)
        assert can["cashdesk"] is True
        assert can["admin"] is False
        assert can["inspections"] is False


def test_the_administrator_still_sees_everything(app, seeded):
    with app.app_context():
        admin = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        can = permissions_for(admin)
        assert all(can.values()), f"the administrator lost: " \
            f"{[k for k, v in can.items() if not v]}"


def test_a_signed_out_visitor_sees_nothing(app, seeded):
    """Fail closed. A broken login must never expose the admin menu."""
    can = permissions_for(None)
    assert not any(can.values())


# ------------------------------------------------------------------ the page
def test_the_rendered_menu_matches_the_permissions(app, client, seeded):
    with app.app_context():
        _user(seeded["org"], "theatrehod", "HOD", "Theatre")
        db.session.commit()

    login(client, "theatrehod")
    body = client.get("/").get_data(as_text=True)
    nav = body[body.find('id="mainnav"'):body.find("</nav>")]

    assert 'href="/admin"' not in nav, \
        "the admin link is still in an HOD's menu"
    assert 'href="/billing"' not in nav
    assert 'href="/paypoint"' not in nav
    assert 'href="/consulting-room"' in nav, "the HOD lost their own room"
    assert 'href="/roster"' in nav


def test_the_admin_menu_is_present_for_the_administrator(app, client, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)
    nav = client.get("/").get_data(as_text=True)
    assert 'href="/admin"' in nav


# ------------------------------------------------------------------ back arrow
def test_every_page_has_a_back_arrow(app, client, seeded):
    """Staff kept getting stranded on pages opened from a link."""
    with app.app_context():
        u = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)

    for path in ("/reception/", "/hims/", "/triage/", "/tracking",
                 "/consulting-room", "/onward", "/roster"):
        body = client.get(path).get_data(as_text=True)
        assert 'class="backbar"' in body, f"no back bar on {path}"
        # The link must actually DO something — checking only that the
        # function exists let a mutation that unwired the click still pass.
        assert 'onclick="hmsBack()"' in body, \
            f"the back arrow on {path} is wired to nothing"
        assert "function hmsBack" in body, f"hmsBack missing on {path}"


def test_the_dashboard_has_no_back_arrow(app, client, seeded):
    """Back FROM the home page has nowhere sensible to go."""
    with app.app_context():
        u = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)
    assert 'class="backbar"' not in client.get("/").get_data(as_text=True)


# ================================================================ enforcement
# HIDING A LINK IS NOT SECURITY. The Theatre HOD's menu no longer shows
# Reception — but he could still TYPE /reception/new and reach the desk,
# because the routes only asked "are you an HOD?". These prove the server
# enforces the same answer the menu gives.

def test_a_theatre_hod_is_refused_the_desks_he_cannot_see(app, client, seeded):
    with app.app_context():
        _user(seeded["org"], "theatre2", "HOD", "Theatre")
        db.session.commit()
    login(client, "theatre2")

    for path in ("/reception/", "/reception/new", "/billing", "/paypoint",
                 "/hims/", "/hims/register"):
        r = client.get(path)
        assert r.status_code == 403, (
            f"{path} returned {r.status_code} — a Theatre HOD reached a desk "
            f"that is hidden from his menu")


def test_the_hims_hod_is_allowed_through(app, client, seeded):
    """The guard must not lock out the people who need the desk."""
    with app.app_context():
        _user(seeded["org"], "hims2", "HOD", "Health Information Management")
        db.session.commit()
    login(client, "hims2")
    assert client.get("/hims/").status_code == 200
    assert client.get("/reception/").status_code == 200


def test_the_administrator_is_never_locked_out(app, client, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    login(client, username)
    for path in ("/reception/", "/billing", "/paypoint", "/hims/"):
        assert client.get(path).status_code == 200, f"admin blocked from {path}"
