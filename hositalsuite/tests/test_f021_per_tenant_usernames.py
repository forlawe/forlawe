"""F-021: usernames are scoped per hospital.

Two hospitals may both have an "admin". Login resolves the hospital first
(host mapping / single-tenant server) and matches inside it; a context-free
login with an ambiguous name is refused with guidance, never guessed. Inside
ONE hospital the name is still unique — that rule didn't go away.
"""
from __future__ import annotations

import pytest

from app import accounts
from app.models import db, Organization, User


@pytest.fixture()
def two_orgs(app, seeded):
    """Org A (the seeded one) + Org B, both with a user named 'shared.admin'."""
    from werkzeug.security import generate_password_hash
    with app.app_context():
        b = Organization(code="ORGB", name="Second General Hospital")
        db.session.add(b)
        db.session.flush()
        for org_id in (seeded["org"], b.id):
            u = User(org_id=org_id, username="shared.admin", name="Shared Admin",
                     role="ADMIN_MANAGER",
                     password_hash=generate_password_hash("Passw0rd!x"),
                     active=True, approved=True, email_verified=True)
            db.session.add(u)
        db.session.commit()
        yield {"a": seeded["org"], "b": b.id}


def test_same_username_allowed_in_two_hospitals(app, two_orgs):
    with app.app_context():
        rows = User.query.filter_by(username="shared.admin").all()
        assert len(rows) == 2 and rows[0].org_id != rows[1].org_id


def test_same_username_rejected_inside_one_hospital(app, two_orgs):
    with app.app_context():
        assert not accounts.username_available(two_orgs["a"], "shared.admin")
        assert accounts.username_available(two_orgs["a"], "other.admin")


def test_scoped_login_finds_the_right_hospital_user(app, two_orgs):
    with app.app_context():
        a = accounts.find_login_user("shared.admin", org_id=two_orgs["a"])
        b = accounts.find_login_user("shared.admin", org_id=two_orgs["b"])
        assert a.org_id == two_orgs["a"] and b.org_id == two_orgs["b"]


def test_unscoped_ambiguous_login_is_refused_not_guessed(app, two_orgs):
    with app.app_context():
        assert accounts.find_login_user("shared.admin") is None
        assert accounts.find_login_user_ambiguous("shared.admin") is True


def test_unscoped_login_still_works_for_unique_names(app, two_orgs):
    with app.app_context():
        assert accounts.find_login_user("admin") is not None   # seeded admin, unique


def test_login_page_guides_on_ambiguous_username(client, two_orgs):
    page = client.get("/login").get_data(as_text=True)
    token = page.split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/login", data={"username": "shared.admin",
                                    "password": "Passw0rd!x", "_csrf": token})
    assert r.status_code == 400
    assert "more than one hospital" in r.get_data(as_text=True)


def test_lockout_is_scoped_per_hospital(app, two_orgs):
    """A brute-force attack on one hospital's 'shared.admin' must NOT lock
    the other hospital's account."""
    from app.views.auth import _lock_row
    with app.app_context():
        lock_a = _lock_row("shared.admin", two_orgs["a"])
        lock_a.failures = 99
        lock_a.locked_until = db.session.query(db.func.max(User.id)).scalar() and lock_a.locked_until
        from app.models import now_naive
        from datetime import timedelta
        lock_a.locked_until = now_naive() + timedelta(minutes=10)
        db.session.commit()
        lock_b = _lock_row("shared.admin", two_orgs["b"])
        assert lock_b.id != lock_a.id
        assert (lock_b.locked_until or 0) == 0 or lock_b.locked_until is None
