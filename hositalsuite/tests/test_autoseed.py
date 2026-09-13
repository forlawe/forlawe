"""First-boot bootstrap tests (AUTO_SEED): free-plan hosts have no shell."""
import os

from app import create_app
from app.models import Organization, User, db


def test_auto_seed_bootstraps_empty_db_once(app, monkeypatch):
    # the `app` fixture's DB was dropped/recreated by conftest without seeding:
    assert db.session.query(Organization).count() == 0

    monkeypatch.setenv("AUTO_SEED", "1")
    # the hospital's contact numbers come from the environment so a fresh
    # deployment is never missing its emergency numbers on the welcome page
    monkeypatch.setenv("SEED_HOSPITAL_PHONE", "0809 000 1111")
    monkeypatch.setenv("SEED_HOSPITAL_PHONE_ALT", "0809 000 2222")
    app2 = create_app(scheduler=False)
    with app2.app_context():
        # These are VERIFICATION queries, not request code: the second boot
        # re-armed row-level security on the tables, and on PostgreSQL a bare
        # app-context query of the protected `user` table fails closed and
        # sees nothing. Declare the cross-hospital intent, like the scheduler
        # does. (The seed itself ran BEFORE RLS was armed — production logins
        # are request-scoped and unaffected.)
        from app.rls import background_all_orgs
        with background_all_orgs():
            assert db.session.query(Organization).count() == 1
            org = db.session.query(Organization).first()
            assert org.phone == "0809 000 1111"
            assert org.phone_alt == "0809 000 2222"
            admin = db.session.query(User).filter_by(username="admin").first()
            assert admin is not None and admin.must_change_password is True
            assert db.session.query(User).count() == 10

    # second boot must NOT reseed or duplicate anything
    app3 = create_app(scheduler=False)
    with app3.app_context():
        from app.rls import background_all_orgs
        with background_all_orgs():
            assert db.session.query(Organization).count() == 1
            assert db.session.query(User).count() == 10


def test_no_auto_seed_without_flag(app, monkeypatch):
    monkeypatch.delenv("AUTO_SEED", raising=False)
    app2 = create_app(scheduler=False)
    with app2.app_context():
        assert db.session.query(Organization).count() == 0
