"""DEMO ACCOUNT: tagged hospital name + admin/Password demo sign-in.

The owner asked for the starter hospital (Lagos State Teaching Hospital) to
be the DEMO ACCOUNT: visibly tagged, sign-in admin / Password, and no forced
password change standing between a visitor and the dashboard. Production
seeding (demo=False / no SEED_DEMO) keeps the strong passwords and the
forced first-login change.
"""
from app import create_app
from app.models import Organization, User, db
from app.seeddata import (DEMO_ACCOUNT_TAG, DEMO_ADMIN_PASSWORD,
                          DEMO_HOSPITAL_NAME, auto_seed, make_demo, seed_data)
from tests.conftest import login


def _org_and_admin(app):
    # the fixture's app context keeps one long-lived session; make_demo (and
    # auto_seed) run in their own session, so expire cached rows before
    # re-reading or the identity map would hand back pre-demo state.
    db.session.expire_all()
    from app.rls import background_all_orgs
    with background_all_orgs():
        org = db.session.query(Organization).first()
        admin = db.session.query(User).filter_by(username="admin").first()
        md = db.session.query(User).filter_by(username="md").first()
    return org, admin, md


def test_demo_seed_tags_hospital_and_sets_admin_password(app):
    assert db.session.query(Organization).count() == 0
    seed_data(app, demo=True)
    org, admin, md = _org_and_admin(app)

    assert org.name == DEMO_HOSPITAL_NAME + DEMO_ACCOUNT_TAG
    assert org.name == "Lagos State Teaching Hospital (Demo Account)"

    # the showcase sign-in works exactly as advertised
    assert admin is not None
    assert admin.check_password(DEMO_ADMIN_PASSWORD)
    assert admin.check_password("Password")
    assert admin.must_change_password is False

    # other demo accounts keep strong passwords, but are NOT locked behind a
    # forced change — a visitor must be able to walk straight in
    assert md.check_password("Mdceo#2026!")
    assert md.must_change_password is False


def test_demo_seed_login_end_to_end(app):
    seed_data(app, demo=True)
    app.config["TESTING"] = True
    client = app.test_client()
    resp = login(client, "admin", "Password")
    assert resp.status_code in (200, 302)
    # and the forced-password-change page is NOT where we end up — the demo
    # login goes straight into the app
    assert "change-password" not in (resp.headers.get("Location") or "")


def test_plain_seed_stays_production_safe(app):
    seed_data(app)
    org, admin, md = _org_and_admin(app)

    # production seed: no demo tag, strong admin password, forced change
    assert org.name == DEMO_HOSPITAL_NAME
    assert DEMO_ACCOUNT_TAG not in org.name
    assert admin.check_password("Admin#2026!")
    assert not admin.check_password("Password")
    assert admin.must_change_password is True
    assert md.must_change_password is True


def test_auto_seed_with_seed_demo_env(app, monkeypatch):
    assert db.session.query(Organization).count() == 0
    monkeypatch.setenv("AUTO_SEED", "1")
    monkeypatch.setenv("SEED_DEMO", "1")
    app2 = create_app(scheduler=False)
    org, admin, _ = _org_and_admin(app2)
    assert org.name == "Lagos State Teaching Hospital (Demo Account)"
    assert admin.check_password("Password")
    assert admin.must_change_password is False


def test_auto_seed_without_seed_demo_env_unchanged(app, monkeypatch):
    assert db.session.query(Organization).count() == 0
    monkeypatch.setenv("AUTO_SEED", "1")
    monkeypatch.delenv("SEED_DEMO", raising=False)
    app2 = create_app(scheduler=False)
    org, admin, _ = _org_and_admin(app2)
    assert org.name == DEMO_HOSPITAL_NAME
    assert not admin.check_password("Password")
    assert admin.must_change_password is True


def test_make_demo_converts_existing_hospital(app):
    seed_data(app)                     # production-style hospital already exists
    org, admin, md = _org_and_admin(app)
    assert admin.must_change_password is True

    made = make_demo(app)
    org, admin, md = _org_and_admin(app)
    assert made is not None
    assert org.name == "Lagos State Teaching Hospital (Demo Account)"
    assert admin.check_password("Password")
    assert admin.must_change_password is False
    # forced change lifted for every account, other passwords untouched
    assert md.must_change_password is False
    assert md.check_password("Mdceo#2026!")

    # idempotent — tag is never doubled
    make_demo(app)
    org, _, _ = _org_and_admin(app)
    assert org.name.count(DEMO_ACCOUNT_TAG.strip()) == 1
