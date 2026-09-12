"""F-007 regression: every role's post-login redirect must land, never crash.

The dashboard branch for the generic STAFF role redirected to a nonexistent
endpoint (`deptdesk.my_department` instead of `deptdesk.desk`). Any ordinary
staff member got a Werkzeug BuildError — a 500 — immediately after logging in.
Because only management roles had integration tests, the crash was invisible.

This file pins the invariant for EVERY role in the app: logging in and landing
on /dashboard must return 200 or a redirect, never 500.
"""
from app.models import ROLES, User, db

from conftest import login


def test_every_role_lands_on_dashboard_without_crash(client, seeded, monkeypatch):
    """Login as each role and hit the post-login landing page.

    500 (or any exception page) fails. Redirects (302) are fine — some roles
    are sent onward to MFA setup or password change; the invariant is that
    the redirect TARGET builds, which is exactly what the F-007 bug broke.
    """
    # One login per role, back to back — relax the limiter's scale for this
    # probe so the rate limiter (correctly) rate-limiting 9 rapid logins
    # doesn't mask what we're actually testing.
    monkeypatch.setattr(client.application, "config",
                        {**client.application.config, "RATE_LIMIT_SCALE": 10_000})
    # Create every probe user in ONE app context, then release the session —
    # interleaving app-context writes with client requests trips SQLite's
    # write lock (WAL) in tests.
    with client.application.app_context():
        for i, role in enumerate(ROLES):
            u = User(org_id=1, username=f"roleprobe{i}", name=f"Probe {role}",
                     role=role)
            u.set_password("Passw0rd!x")
            u.must_change_password = False
            db.session.add(u)
        db.session.commit()
        db.session.remove()

    for i, role in enumerate(ROLES):
        username = f"roleprobe{i}"
        r = login(client, username)
        assert r.status_code in (200, 302), f"login failed for role {role}"
        page = client.get("/dashboard")
        assert page.status_code in (200, 302), (
            f"role {role} got HTTP {page.status_code} on /dashboard — post-login "
            f"landing is broken (F-007 class of bug)")


def test_staff_role_redirect_targets_a_real_endpoint(client, seeded):
    """The exact F-007 scenario: a STAFF-role user's /dashboard visit must
    redirect to /my-department and that page must actually render."""
    with client.application.app_context():
        u = User(org_id=1, username="plainstaff", name="Plain Staff",
                 role="STAFF")
        u.set_password("Passw0rd!x")
        u.must_change_password = False
        db.session.add(u)
        db.session.commit()

    assert login(client, "plainstaff").status_code in (200, 302)
    r = client.get("/dashboard")
    assert r.status_code == 302
    assert "/my-department" in r.headers["Location"]
    followed = client.get("/dashboard", follow_redirects=True)
    assert followed.status_code == 200
    assert b"Something went wrong" not in followed.data, \
        "STAFF redirect landed on the 500 page"
